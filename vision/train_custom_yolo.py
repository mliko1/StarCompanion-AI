# -*- coding: utf-8 -*-
"""
星伴AI 自训练脚本（第三步：微调 YOLO 识别自定义物品）

解决"收纳盒"等 COCO 80 类之外物品无法识别的问题。
输入：collect_dataset.py 采集的图片 + label_dataset.py 标注的标签。
输出：微调后的权重，保存到 vision/models/custom_<name>.pt。

用法（项目根目录）：
    python vision/train_custom_yolo.py --name box --epochs 60

说明：
    - 数据目录约定：data/custom_dataset/images/<class>/ 与 labels/<class>/；
    - 自动按 80/20 划分训练/验证集（可 --val-ratio 调整）；
    - 基于 vision/models/yolo11n.pt 预训练权重微调（CPU 可跑，约 15 FPS 量级）；
    - 训练完成后可直接用于 skill_task_session.py 中，
      用 --target box 之类的自定义类别名替换 COCO 类名。
"""

import argparse
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "custom_dataset")
IMG_ROOT = os.path.join(DATA_DIR, "images")
LBL_ROOT = os.path.join(DATA_DIR, "labels")
BASE_MODEL = os.path.join(ROOT, "vision", "models", "yolo11n.pt")
OUT_DIR = os.path.join(ROOT, "vision", "models")


def _discover_classes():
    """扫描 images/ 下所有子目录，返回 {class_name: [image_path, ...]}。"""
    classes = {}
    if not os.path.isdir(IMG_ROOT):
        return classes
    for cls in sorted(os.listdir(IMG_ROOT)):
        img_dir = os.path.join(IMG_ROOT, cls)
        if not os.path.isdir(img_dir):
            continue
        files = sorted(
            f for f in os.listdir(img_dir)
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")))
        classes[cls] = [os.path.join(img_dir, f) for f in files]
    return classes


def _prepare_split(classes, val_ratio, seed=0):
    """把每个类按比例划分，写 train.txt / val.txt 与 data.yaml。"""
    train_paths, val_paths = [], []
    for cls, imgs in classes.items():
        random.seed(seed)
        random.shuffle(imgs)
        n_val = max(1, int(len(imgs) * val_ratio)) if len(imgs) > 1 else 0
        val_paths += imgs[:n_val]
        train_paths += imgs[n_val:]

    train_txt = os.path.join(DATA_DIR, "train.txt")
    val_txt = os.path.join(DATA_DIR, "val.txt")
    with open(train_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(train_paths))
    with open(val_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(val_paths))

    names = list(classes.keys())
    yaml_path = os.path.join(DATA_DIR, "data.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write("# 星伴AI 自训练数据集配置（自动生成）\n")
        f.write(f"train: {train_txt.replace(os.sep, '/')}\n")
        f.write(f"val: {val_txt.replace(os.sep, '/')}\n")
        f.write(f"nc: {len(names)}\n")
        f.write("names: [" + ", ".join(repr(n) for n in names) + "]\n")
    return train_paths, val_paths, yaml_path, names


def main():
    ap = argparse.ArgumentParser(description="微调 YOLO 识别自定义物品")
    ap.add_argument("--name", default="box", help="导出的权重名（如 box / storage_box）")
    ap.add_argument("--epochs", type=int, default=60, help="训练轮数")
    ap.add_argument("--imgsz", type=int, default=480, help="训练分辨率")
    ap.add_argument("--batch", type=int, default=8, help="批大小（CPU 建议 8）")
    ap.add_argument("--val-ratio", type=float, default=0.2, help="验证集比例")
    ap.add_argument("--device", default="cpu", help="训练设备 cpu / 0")
    args = ap.parse_args()

    classes = _discover_classes()
    if not classes:
        print("未找到任何已采集的类别。请先运行：")
        print("  python vision/collect_dataset.py --class <名字>")
        print("  python vision/label_dataset.py  --class <名字>")
        return

    total = sum(len(v) for v in classes.values())
    print("发现类别：")
    for cls, imgs in classes.items():
        lbl_dir = os.path.join(LBL_ROOT, cls)
        n_lbl = (len(os.listdir(lbl_dir)) if os.path.isdir(lbl_dir) else 0)
        print(f"  {cls}: {len(imgs)} 张图片, {n_lbl} 个标签文件")
    print(f"合计图片: {total}")
    if total < 20:
        print("提示：图片太少（<20），训练效果会很差，建议每类至少 150 张。")

    train_paths, val_paths, yaml_path, names = _prepare_split(
        classes, args.val_ratio)
    print(f"划分：训练 {len(train_paths)} 张 / 验证 {len(val_paths)} 张")
    print(f"配置：{yaml_path}")
    print(f"类别：{names}")

    # 延迟导入，避免未安装 ultralytics 时启动即报错
    from ultralytics import YOLO

    model = YOLO(BASE_MODEL)
    model.train(
        data=yaml_path,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=0,           # Windows 下避免多进程 dataloader 报错
        project=os.path.join(ROOT, "data", "custom_dataset", "runs"),
        name=args.name,
        exist_ok=True,
        verbose=True,
    )

    # 导出：把 best.pt 复制为 vision/models/custom_<name>.pt，方便技能任务直接加载
    best_src = os.path.join(ROOT, "data", "custom_dataset", "runs",
                            args.name, "weights", "best.pt")
    if os.path.exists(best_src):
        out_path = os.path.join(OUT_DIR, f"custom_{args.name}.pt")
        import shutil
        shutil.copyfile(best_src, out_path)
        print(f"\n训练完成！自定义权重已导出到：{out_path}")
        print("使用方式：")
        print(f"  1) 在 skill_task_session.py 中把 --target 改成你的自定义类名；")
        print(f"  2) 或直接运行 object_detector.py 后加载该权重。")
    else:
        print(f"\n训练结束，但未找到 best.pt（可能在 {best_src} 之外），请到 runs/{args.name}/weights/ 查看。")


if __name__ == "__main__":
    main()
