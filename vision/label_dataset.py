# -*- coding: utf-8 -*-
"""
星伴AI 自训练数据集标注脚本（第二步：画框标注）

配合 collect_dataset.py 使用：先拍照，再用本脚本给图片画目标框，
生成 YOLO 训练所需的标签文件（归一化坐标）。

目录约定（与 collect_dataset.py 一致）：
    data/custom_dataset/images/<class>/xxx.jpg   # 原始图片
    data/custom_dataset/labels/<class>/xxx.txt   # 本脚本生成的标签

用法（项目根目录）：
    python vision/label_dataset.py --class box

操作：
    鼠标拖拽    在画面中画一个目标框（可画多个）
    n / 空格    保存本图全部框，跳到下一张
    s           本图无目标（跳过，写空标签）
    d           撤销最后一个框
    c           清空本图所有框
    q           退出（已标注的图会保存）

标注要点：
    1. 框尽量贴紧目标外轮廓，不要留过多背景；
    2. 被遮挡目标：只框可见部分；
    3. 每张图框住的目标类别应与 --class 一致（单类标注）。
"""

import argparse
import os

import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "custom_dataset")
IMG_ROOT = os.path.join(DATA_DIR, "images")
LBL_ROOT = os.path.join(DATA_DIR, "labels")

# 全局状态（供鼠标回调使用）
_box_start = None       # 拖拽起点 (x, y)
_box_drawing = False    # 是否正在拖拽
_boxes = []             # 当前图片已画好的框 [(x1,y1,x2,y2), ...]
_cur_box = None         # 正在拖拽中的临时框


def _on_mouse(event, x, y, flags, param):
    global _box_start, _box_drawing, _cur_box
    if event == cv2.EVENT_LBUTTONDOWN:
        _box_start = (x, y)
        _box_drawing = True
        _cur_box = None
    elif event == cv2.EVENT_MOUSEMOVE and _box_drawing:
        if _box_start:
            _cur_box = (_box_start[0], _box_start[1], x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        _box_drawing = False
        if _box_start:
            x1, y1 = _box_start
            x2, y2 = max(x, 1), max(y, 1)
            # 归一化顺序，过滤误点（框太小视为无效）
            l, r = min(x1, x2), max(x1, x2)
            t, b = min(y1, y2), max(y1, y2)
            if r - l >= 5 and b - t >= 5:
                _boxes.append((l, t, r, b))
        _box_start = None
        _cur_box = None


def _draw(frame):
    """把已画的框和拖拽中的框叠加到图像副本上。"""
    img = frame.copy()
    for (l, t, r, b) in _boxes:
        cv2.rectangle(img, (l, t), (r, b), (0, 200, 0), 2)
    if _cur_box:
        l, t, r, b = _cur_box
        cv2.rectangle(img, (min(l, r), min(t, b), max(l, r), max(t, b)),
                      (0, 255, 255), 2)
    h, w = img.shape[:2]
    cv2.putText(img, f"boxes: {len(_boxes)}", (10, h - 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2)
    cv2.putText(img, "drag=box  n=save+next  s=skip  d=undo  c=clear  q=quit",
                (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
    return img


def _save_label(img_path, cls, boxes, img_w, img_h):
    """写 YOLO 标签：class_id cx cy w h（全部归一化）。"""
    label_dir = os.path.join(LBL_ROOT, cls)
    os.makedirs(label_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(img_path))[0]
    out_path = os.path.join(label_dir, base + ".txt")
    with open(out_path, "w", encoding="utf-8") as f:
        for (l, t, r, b) in boxes:
            cx = (l + r) / 2 / img_w
            cy = (t + b) / 2 / img_h
            w = (r - l) / img_w
            h = (b - t) / img_h
            f.write(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
    return out_path


def main():
    global _boxes, _cur_box
    ap = argparse.ArgumentParser(description="自训练数据集标注")
    ap.add_argument("--class", dest="cls", default="box", help="类别名（英文）")
    args = ap.parse_args()

    img_dir = os.path.join(IMG_ROOT, args.cls)
    if not os.path.isdir(img_dir):
        print(f"未找到图片目录：{img_dir}")
        print("请先运行 python vision/collect_dataset.py --class " + args.cls)
        return

    files = sorted(
        f for f in os.listdir(img_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")))
    if not files:
        print(f"目录为空：{img_dir}")
        return

    label_dir = os.path.join(LBL_ROOT, args.cls)
    os.makedirs(label_dir, exist_ok=True)
    done = {os.path.splitext(f)[0] for f in os.listdir(label_dir)}

    print(f"类别: {args.cls} | 共 {len(files)} 张，已标注 {len(done)} 张")
    print("操作：拖拽画框  n/空格=保存下一张  s=跳过  d=撤销  c=清空  q=退出")

    win = "XingBanAI Labeler"
    cv2.namedWindow(win)
    cv2.setMouseCallback(win, _on_mouse)

    idx = 0
    while idx < len(files):
        name = files[idx]
        path = os.path.join(img_dir, name)
        frame = cv2.imread(path)
        if frame is None:
            idx += 1
            continue
        h, w = frame.shape[:2]
        _boxes = []
        _cur_box = None

        while True:
            cv2.imshow(win, _draw(frame))
            key = cv2.waitKey(20) & 0xFF
            if key in (ord("n"), ord(" "), 13):  # n / 空格 / 回车
                if _boxes:
                    out = _save_label(path, args.cls, _boxes, w, h)
                    print(f"[标注] {name} -> {len(_boxes)} 个框")
                else:
                    out = _save_label(path, args.cls, [], w, h)
                    print(f"[空] {name}（无目标）")
                break
            elif key == ord("s"):  # 跳过：写空标签
                _save_label(path, args.cls, [], w, h)
                print(f"[跳过] {name}")
                break
            elif key == ord("d"):  # 撤销最后一个框
                if _boxes:
                    _boxes.pop()
            elif key == ord("c"):  # 清空
                _boxes = []
                _cur_box = None
            elif key in (ord("q"), 27):  # 退出
                cv2.destroyAllWindows()
                print(f"已退出，完成到第 {idx} 张（共 {len(files)} 张）")
                return
        idx += 1

    cv2.destroyAllWindows()
    print("全部图片标注完成。可运行 python vision/train_custom_yolo.py 开始训练。")


if __name__ == "__main__":
    main()
