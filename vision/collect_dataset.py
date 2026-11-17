# -*- coding: utf-8 -*-
"""
星伴AI 自训练数据集采集脚本（第一步：拍照）

用途：为自定义物品（如铁盒）采集训练图片，用于后续 YOLO 微调。
用法（项目根目录）：
    python vision/collect_dataset.py --class box
    （默认类别名 box，可改成任意英文名，如 iron_box / teddy 等）

操作：
    空格键  保存一张图片
    s       连续模式：每 0.5 秒自动保存一张（再按 s 停止）
    q       退出

采集要点（保证训练质量）：
    1. 数量：单类建议 150~300 张；
    2. 多样性：不同角度（俯视/平视/斜视）、不同距离（近中远）、
       不同背景（桌面/地面/不同房间）、不同光照（白天/灯光）；
    3. 尽量让铁盒占画面主要区域，同时保留少量"小目标"照片；
    4. 换不同人/不同姿势拿盒子也拍一些，减少误检。

保存位置：data/custom_dataset/images/box/ 下，文件名含时间戳。
"""

import argparse
import os
import time

import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, "data", "custom_dataset", "images")


def main():
    ap = argparse.ArgumentParser(description="自训练数据集采集")
    ap.add_argument("--class", dest="cls", default="box",
                    help="类别名（英文）")
    args = ap.parse_args()

    out_dir = os.path.join(IMG_DIR, args.cls)
    os.makedirs(out_dir, exist_ok=True)

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("DirectShow 打开失败，尝试 MSMF...")
        cap = cv2.VideoCapture(0, cv2.CAP_MSMF)
    if not cap.isOpened():
        print("错误：无法打开摄像头")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    count = 0
    burst = False
    last_shot = 0.0
    print(f"类别: {args.cls} | 保存到 {out_dir}")
    print("空格=拍一张  s=连续模式  q=退出")

    while True:
        ok, frame_raw = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame_raw, 1)

        now = time.time()
        if burst and now - last_shot >= 0.5:
            _save(frame, out_dir, args.cls)
            count += 1
            last_shot = now

        # 左上角提示
        cv2.putText(frame, f"class: {args.cls}  saved: {count}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        mode = "BURST (auto)" if burst else "SINGLE"
        cv2.putText(frame, f"[space]=save  [s]=burst  [q]=quit  mode={mode}",
                    (10, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)

        cv2.imshow("XingBanAI Dataset Collector", frame)
        key = cv2.waitKey(1)
        if key in (ord("q"), 27):
            break
        elif key == ord(" "):
            _save(frame, out_dir, args.cls)
            count += 1
        elif key == ord("s"):
            burst = not burst
            last_shot = now

    cap.release()
    cv2.destroyAllWindows()
    print(f"已退出，共保存 {count} 张图片到 {out_dir}")


def _save(frame, out_dir, cls):
    name = time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time()*1000)%1000:03d}.jpg"
    path = os.path.join(out_dir, name)
    cv2.imwrite(path, frame)
    print(f"[保存] {path}")


if __name__ == "__main__":
    main()
