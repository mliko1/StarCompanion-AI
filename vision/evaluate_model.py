# -*- coding: utf-8 -*-
"""
星伴AI 模型评估脚本（第四步：Precision / Recall / F1）

对已标注的验证集，把模型预测框与人工标注框按 IoU 匹配，
统计 TP / FP / FN，计算 Precision、Recall、F1（IoU 阈值默认 0.5）。

用法（项目根目录）：
    # 评估 COCO 预训练 yolo11n（默认）
    python vision/evaluate_model.py

    # 评估自训练后的权重
    python vision/evaluate_model.py --model vision/models/custom_box.pt

说明：
    - 使用 data/custom_dataset/val.txt（由 train_custom_yolo.py 生成）作为验证集；
    - 若没有自训练数据，本脚本会提示先走完 采集→标注→训练 流程；
    - 结果仅供参考：单目 2D + 规则阈值的精度为行为记录级，非医学测量级。
"""

import argparse
import os

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "custom_dataset")
DEFAULT_MODEL = os.path.join(ROOT, "vision", "models", "yolo11n.pt")


def _iou(a, b):
    """计算两个 [x1,y1,x2,y2] 框的 IoU。"""
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _load_labels(img_path):
    """把图片路径换成标签路径并读取归一化框 -> 像素框。"""
    lbl_path = img_path.replace(os.sep + "images" + os.sep,
                                os.sep + "labels" + os.sep)
    lbl_path = os.path.splitext(lbl_path)[0] + ".txt"
    boxes = []
    if not os.path.exists(lbl_path):
        return boxes
    img = cv2.imread(img_path)
    if img is None:
        return boxes
    h, w = img.shape[:2]
    with open(lbl_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            cls, cx, cy, bw, bh = parts[0], *map(float, parts[1:5])
            x1 = (cx - bw / 2) * w
            y1 = (cy - bh / 2) * h
            x2 = (cx + bw / 2) * w
            y2 = (cy + bh / 2) * h
            boxes.append((int(cls), (x1, y1, x2, y2)))
    return boxes


def main():
    ap = argparse.ArgumentParser(description="评估检测模型 Precision/Recall/F1")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="权重路径")
    ap.add_argument("--conf", type=float, default=0.45, help="置信度阈值")
    ap.add_argument("--iou", type=float, default=0.5, help="匹配 IoU 阈值")
    ap.add_argument("--val-txt", default=os.path.join(DATA_DIR, "val.txt"),
                    help="验证集图片清单（每行一个路径）")
    args = ap.parse_args()

    if not os.path.exists(args.val_txt):
        print("未找到验证集清单：", args.val_txt)
        print("请先完成自训练数据准备：")
        print("  python vision/collect_dataset.py --class box")
        print("  python vision/label_dataset.py  --class box")
        print("  python vision/train_custom_yolo.py --name box")
        return

    with open(args.val_txt, "r", encoding="utf-8") as f:
        paths = [p.strip() for p in f if p.strip() and os.path.exists(p.strip())]
    if not paths:
        print("验证集清单为空或图片不存在。")
        return

    from ultralytics import YOLO
    model = YOLO(args.model)

    tp = fp = fn = 0
    per_img = []
    for path in paths:
        gt = _load_labels(path)
        gt_boxes = [b for _, b in gt]
        res = model.predict(path, conf=args.conf, imgsz=480, verbose=False)
        preds = []
        for r in res:
            for box in r.boxes:
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
                preds.append((float(box.conf[0]), (x1, y1, x2, y2)))

        matched_gt = set()
        for conf, pb in preds:
            best_iou, best_j = 0.0, -1
            for j, gb in enumerate(gt_boxes):
                if j in matched_gt:
                    continue
                iou = _iou(pb, gb)
                if iou > best_iou:
                    best_iou, best_j = iou, j
            if best_iou >= args.iou and best_j >= 0:
                tp += 1
                matched_gt.add(best_j)
            else:
                fp += 1
        fn += len(gt_boxes) - len(matched_gt)
        per_img.append((len(preds), len(gt_boxes)))

    precision = tp / (tp + fp) if tp + fp > 0 else 0.0
    recall = tp / (tp + fn) if tp + fn > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if precision + recall > 0 else 0.0)

    print("=" * 46)
    print(f"模型        : {args.model}")
    print(f"验证集图片  : {len(paths)} 张")
    print(f"IoU 阈值    : {args.iou}   置信度阈值: {args.conf}")
    print("-" * 46)
    print(f"TP (正确命中)  : {tp}")
    print(f"FP (误检)      : {fp}")
    print(f"FN (漏检)      : {fn}")
    print("-" * 46)
    print(f"Precision : {precision:.4f}")
    print(f"Recall    : {recall:.4f}")
    print(f"F1-score  : {f1:.4f}")
    print("=" * 46)

    if tp + fp + fn == 0:
        print("提示：验证集没有任何标注目标，无法评估。请用 label_dataset.py 完成标注。")


if __name__ == "__main__":
    main()
