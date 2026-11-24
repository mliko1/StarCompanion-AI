# -*- coding: utf-8 -*-
"""
星伴AI 家庭校准脚本（一键完成：引导拍照 → 自动标注 → 微调训练）

解决问题：不同家庭的收纳盒长得不一样，无法用单一模型通用识别。
方案：家长首次使用时，把自家的收纳盒放进画面中央的【绿色引导框】，
按空格拍照；脚本自动用绿框作为标注框生成 YOLO 标签（无需手动画框），
拍照结束后一键微调，得到该家庭专属的识别模型 custom_<name>.pt。

这是「个体化适应」理念从"人"到"物"的延伸：
    - 动作个体化：适配每个孩子的动作习惯（core/personalization.py）
    - 物体个体化：适配每个家庭的收纳盒（本脚本）

用法（项目根目录）：
    python vision/family_calibrate.py --name my_box

操作：
    空格 = 拍一张（收纳盒尽量占满中央绿框）
    s    = 连拍模式（每 0.5 秒自动拍一张，方便转动盒子换角度）
    q    = 退出拍照并自动开始训练

采集建议：至少 30~50 张，覆盖不同角度（俯视/平视/斜视）、距离、光照。
训练：基于 yolo11n.pt 微调，CPU 可跑（几十张图约 10~30 分钟）。
"""

import argparse
import os
import subprocess
import sys
import time

import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "custom_dataset")
IMG_ROOT = os.path.join(DATA_DIR, "images")
LBL_ROOT = os.path.join(DATA_DIR, "labels")
MODELS_DIR = os.path.join(ROOT, "vision", "models")

# 中央引导框占画面比例（家长把盒子放进这个框，框即标注）
GUIDE_BOX_RATIO = 0.6
MIN_SHOTS = 30  # 建议最少采集张数


def guide_box(frame_w, frame_h):
    """返回中央引导框 (x1, y1, x2, y2)。"""
    w = int(frame_w * GUIDE_BOX_RATIO)
    h = int(frame_h * GUIDE_BOX_RATIO)
    x1 = (frame_w - w) // 2
    y1 = (frame_h - h) // 2
    return (x1, y1, x1 + w, y1 + h)


def save_with_label(frame, cls, box, img_w, img_h):
    """保存图片 + 自动写中央框标签（YOLO 格式：0 cx cy w h，归一化）。"""
    img_dir = os.path.join(IMG_ROOT, cls)
    lbl_dir = os.path.join(LBL_ROOT, cls)
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(lbl_dir, exist_ok=True)

    name = time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"
    img_path = os.path.join(img_dir, name + ".jpg")
    lbl_path = os.path.join(lbl_dir, name + ".txt")
    cv2.imwrite(img_path, frame)

    x1, y1, x2, y2 = box
    cx = (x1 + x2) / 2 / img_w
    cy = (y1 + y2) / 2 / img_h
    w = (x2 - x1) / img_w
    h = (y2 - y1) / img_h
    with open(lbl_path, "w", encoding="utf-8") as f:
        f.write(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
    return img_path


def collect(cls):
    """引导式采集 + 自动标注。"""
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("DirectShow 打开失败，尝试 MSMF...")
        cap = cv2.VideoCapture(0, cv2.CAP_MSMF)
    if not cap.isOpened():
        print("错误：无法打开摄像头")
        return 0
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    count = 0
    burst = False
    last_shot = 0.0

    print("=" * 60)
    print(f"家庭校准采集：类名 {cls}")
    print("把收纳盒尽量占满画面中央的绿框，然后：")
    print("  空格 = 拍一张 | s = 连拍(自动) | q = 退出并训练")
    print(f"建议至少 {MIN_SHOTS} 张，覆盖多角度/多距离/多光照")
    print("=" * 60)

    while True:
        ok, frame_raw = cap.read()
        if not ok:
            print("错误：画面读取失败")
            break
        frame = cv2.flip(frame_raw, 1)
        h, w = frame.shape[:2]
        box = guide_box(w, h)
        x1, y1, x2, y2 = box

        now = time.time()
        if burst and now - last_shot >= 0.5:
            save_with_label(frame, cls, box, w, h)
            count += 1
            last_shot = now

        # 绘制中央引导绿框
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, f"class: {cls}  saved: {count}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        mode = "BURST(auto)" if burst else "SINGLE"
        cv2.putText(frame, f"[space]=save  [s]=burst  [q]=quit  mode={mode}",
                    (10, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
        hint = "盒子占满绿框" if count < MIN_SHOTS else "数量够了，可按 q 训练"
        cv2.putText(frame, hint, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        cv2.imshow("XingBanAI Family Calibrate", frame)
        key = cv2.waitKey(1)
        if key in (ord("q"), 27):
            break
        elif key == ord(" "):
            save_with_label(frame, cls, box, w, h)
            count += 1
        elif key == ord("s"):
            burst = not burst
            last_shot = now

    cap.release()
    cv2.destroyAllWindows()
    print(f"拍照结束，共 {count} 张。")
    return count


def train(cls, epochs):
    """调用现有训练脚本微调（subprocess 复用，不重复实现）。"""
    print("\n" + "=" * 60)
    print("开始训练（CPU 微调，可能需要 10~30 分钟，请耐心等待）...")
    print("=" * 60)
    cmd = [sys.executable, os.path.join(ROOT, "vision", "train_custom_yolo.py"),
           "--name", cls, "--epochs", str(epochs)]
    subprocess.call(cmd, cwd=ROOT)

    model_path = os.path.join(MODELS_DIR, f"custom_{cls}.pt")
    if os.path.exists(model_path):
        print("\n" + "=" * 60)
        print(f"家庭校准完成！专属模型已生成：{model_path}")
        print("现在技能任务里把目标类名改成你的类名即可使用。")
        print("=" * 60)
    else:
        print("\n训练结束，但未找到导出模型，请检查上方训练日志。")


def main():
    ap = argparse.ArgumentParser(description="星伴AI 家庭校准（一键采集+标注+训练）")
    ap.add_argument("--name", default="box", help="家庭专属类名（英文，如 my_box）")
    ap.add_argument("--epochs", type=int, default=50, help="训练轮数（单目标 40~60 够）")
    args = ap.parse_args()

    cls = args.name.strip()
    if not cls or not cls.replace("_", "").replace("-", "").isalnum():
        print("类名只能包含字母/数字/下划线/连字符")
        return

    n = collect(cls)
    if n < 10:
        print(f"\n只拍了 {n} 张，太少，训练效果会很差。建议至少 {MIN_SHOTS} 张。")
        print("可重新运行本脚本补充采集。")
        return

    train(cls, args.epochs)


if __name__ == "__main__":
    main()
