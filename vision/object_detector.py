# -*- coding: utf-8 -*-
"""
星伴AI 第三阶段 模块一：目标物品检测
基于 ultralytics YOLO yolo11n（COCO 预训练 80 类，CPU 可实时运行）。

诚实说明（重要）：
1. 本模块只是"调用预训练模型"，没有任何自训练成分；
2. COCO 80 类中没有"收纳盒"这一类，本程序不支持识别收纳盒。
   演示任务中请用 COCO 能识别的物品替代（如碗 bowl、书 book）；
3. 支持的常用目标类别见 TARGET_CLASSES，可在运行时配置。

运行方式（在项目根目录）：
    python vision/object_detector.py
按 q 键退出。
"""

import time

import cv2
from ultralytics import YOLO

MODEL_PATH = "vision/models/yolo11n.pt"

# 本项目关心的目标物品（COCO 类别名，可按需增删）
# 注：实测发现小瓶子易被误判为 cell phone（COCO 小物品类经典混淆），
# 且任务不需要手机，故移除该类以消除歧义。
TARGET_CLASSES = [
    "teddy bear",   # 玩具（毛绒玩具，演示任务主角）
    "bottle",       # 瓶子（无毛绒玩具时可充当"被拿取物品"）
    "cup",          # 杯子
    "bowl",         # 碗（可充当"收纳盒"的替代道具）
    "book",         # 书（同样可作"收纳盒"替代道具）
]

CONF_THRESHOLD = 0.45   # 置信度阈值：低于此值的检测不采信

MODEL = None
CLASS_NAMES = {}


def load_model(model_path=MODEL_PATH):
    """加载 YOLO 模型（首次运行会自动下载 yolo11n.pt，约5MB）。"""
    global MODEL, CLASS_NAMES
    MODEL = YOLO(model_path)
    CLASS_NAMES = MODEL.names  # {0: 'person', 1: 'bicycle', ...}
    return MODEL


def detect_objects(frame, conf=CONF_THRESHOLD, classes=None):
    """对单帧图像做物品检测。

    输入: frame - OpenCV BGR 图像（原始帧，非镜像）
    输出: [ {name, bbox, confidence, center, area}, ... ]，像素坐标。
    """
    if MODEL is None:
        load_model()
    if classes is None:
        classes = TARGET_CLASSES
    ids = [i for i, n in CLASS_NAMES.items() if n in classes]

    results = MODEL.predict(frame, conf=conf, classes=ids,
                            imgsz=480, verbose=False)
    detections = []
    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
            detections.append({
                "name": CLASS_NAMES[int(box.cls[0])],
                "bbox": (x1, y1, x2, y2),
                "confidence": float(box.conf[0]),
                "center": ((x1 + x2) / 2, (y1 + y2) / 2),
                "area": (x2 - x1) * (y2 - y1),
            })
    return detections


def draw_detections(frame, detections):
    """在原始帧上绘制检测框（调用方翻转后再显示，与第二阶段约定一致）。"""
    for det in detections:
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        cx, cy = int(det["center"][0]), int(det["center"][1])
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 160, 0), 2)
        cv2.circle(frame, (cx, cy), 4, (255, 160, 0), -1)
        label = f"{det['name']} {det['confidence']:.2f}"
        cv2.putText(frame, label, (x1, max(y1 - 8, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 160, 0), 2)
    return frame


def main():
    """独立演示：实时检测并绘制目标物品，显示FPS。"""
    load_model()
    print("XingBanAI Object Detector (YOLO yolo11n, CPU)")
    print(f"Target classes: {TARGET_CLASSES}")
    print("Put objects in view; press Q to quit")

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("错误：无法打开摄像头")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    fps, t_last = 0.0, time.time()

    while True:
        ok, frame_raw = cap.read()
        if not ok:
            print("错误：摄像头画面读取失败")
            break

        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / max(now - t_last, 1e-6))
        t_last = now

        detections = detect_objects(frame_raw)
        draw_detections(frame_raw, detections)

        frame = cv2.flip(frame_raw, 1)  # 显示用镜像
        names = ", ".join(f"{d['name']}({d['confidence']:.2f})"
                          for d in detections) or "no target object"
        cv2.putText(frame, f"FPS: {fps:.1f} | {names}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 160, 0), 2)
        cv2.putText(frame, "Target objects are boxed; press Q to quit",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)

        cv2.imshow("XingBanAI Object Detector", frame)
        key = cv2.waitKey(1)
        if (key in (ord("q"), 27) or
                cv2.getWindowProperty("XingBanAI Object Detector",
                                      cv2.WND_PROP_VISIBLE) < 1):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("已退出")


if __name__ == "__main__":
    main()
