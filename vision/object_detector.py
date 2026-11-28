# -*- coding: utf-8 -*-
"""
星伴AI 第三阶段 模块一：目标物品检测
基于 ultralytics YOLO yolo11n（COCO 预训练 80 类，CPU 可实时运行）。

诚实说明（重要）：
1. 默认使用 COCO 预训练模型，本身不含自训练成分；
2. COCO 80 类与 MediaPipe 姿态无法识别的任意物品，都可通过网页端「校准」
   页训练出 custom_<name>.pt，再通过 load_custom_model() 作为第二检测源加载；
3. 支持的常用目标类别见 TARGET_CLASSES，可在运行时配置。

运行方式（在项目根目录）：
    python vision/object_detector.py
按 q 键退出。
"""

import locale
import os
import sys
import time

import cv2
from ultralytics import YOLO

# ultralytics 导入后会把 sys.stdout 改成 UTF-8，导致 Windows 控制台/子进程以 GBK
# 读取中文输出时报 UnicodeDecodeError。这里恢复为系统默认编码，保证中文 print 正常。
try:
    _enc = locale.getpreferredencoding(False) or "utf-8"
    sys.stdout.reconfigure(encoding=_enc, errors="replace")
    sys.stderr.reconfigure(encoding=_enc, errors="replace")
except Exception:
    pass

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

# 家庭自定义模型作为「第二检测源」：与 COCO 模型并存，用于识别 COCO / MediaPipe
# 无法识别的任意个性化物品（由网页端「校准」页采集训练得到）。支持多个并存。
CUSTOM_MODELS = {}        # {class_name: YOLO 模型}
CUSTOM_CLASS_NAMES = {}   # {class_name: {id: name}}


def load_model(model_path=MODEL_PATH):
    """加载 YOLO 模型（首次运行会自动下载 yolo11n.pt，约5MB）。"""
    global MODEL, CLASS_NAMES
    MODEL = YOLO(model_path)
    CLASS_NAMES = MODEL.names  # {0: 'person', 1: 'bicycle', ...}
    return MODEL


def has_custom_model(class_name):
    """判断是否存在家庭校准模型 custom_<class_name>.pt。"""
    path = os.path.join("vision", "models", f"custom_{class_name}.pt")
    return os.path.exists(path)


def list_custom_models():
    """列出所有已训练的家庭自定义模型类名（扫描 vision/models/custom_*.pt）。"""
    models_dir = os.path.join("vision", "models")
    if not os.path.isdir(models_dir):
        return []
    names = []
    for fn in sorted(os.listdir(models_dir)):
        if fn.startswith("custom_") and fn.endswith(".pt"):
            names.append(fn[len("custom_"):-len(".pt")])
    return names


def load_custom_model(class_name):
    """加载家庭校准后的自定义模型 custom_<class_name>.pt，作为第二检测源。

    成功返回 True。支持多个自定义模型并存（例如玩具与收纳盒各一个），
    detect_objects() 会同时返回 COCO 与所有已加载自定义模型的检测结果。
    """
    global CUSTOM_MODELS, CUSTOM_CLASS_NAMES
    path = os.path.join("vision", "models", f"custom_{class_name}.pt")
    if not os.path.exists(path):
        return False
    model = YOLO(path)
    CUSTOM_MODELS[class_name] = model
    CUSTOM_CLASS_NAMES[class_name] = model.names
    return True


def _collect(model, class_names, frame, conf, ids=None):
    """运行一次模型推理，收集标准化检测结果（像素坐标）。"""
    results = model.predict(frame, conf=conf, classes=ids,
                            imgsz=480, verbose=False)
    detections = []
    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
            detections.append({
                "name": class_names[int(box.cls[0])],
                "bbox": (x1, y1, x2, y2),
                "confidence": float(box.conf[0]),
                "center": ((x1 + x2) / 2, (y1 + y2) / 2),
                "area": (x2 - x1) * (y2 - y1),
                "track_id": None,
            })
    return detections


def detect_objects(frame, conf=CONF_THRESHOLD, classes=None):
    """对单帧图像做物品检测。

    输入: frame - OpenCV BGR 图像（原始帧，非镜像）
    输出: [ {name, bbox, confidence, center, area}, ... ]，像素坐标。
    若已加载家庭自定义模型（load_custom_model），会同时返回该模型的检测结果。
    """
    if MODEL is None:
        load_model()
    if classes is None:
        classes = TARGET_CLASSES
    ids = [i for i, n in CLASS_NAMES.items() if n in classes]

    detections = _collect(MODEL, CLASS_NAMES, frame, conf, ids)
    # 第二检测源：家庭自定义模型（识别 COCO / MediaPipe 无法识别的任意物品）
    for _cls, _model in CUSTOM_MODELS.items():
        detections += _collect(_model, CUSTOM_CLASS_NAMES[_cls], frame, conf)
    return detections


def _collect_tracking(model, class_names, frame, conf, source, ids=None):
    """用 Ultralytics 内置 ByteTrack 跟踪，给每个检测结果稳定 track_id。"""
    results = model.track(frame, persist=True, conf=conf, classes=ids,
                          imgsz=480, verbose=False)
    detections = []
    for r in results:
        if r.boxes is None:
            continue
        for box in r.boxes:
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
            raw_id = None
            if getattr(box, "id", None) is not None:
                try:
                    raw_id = int(box.id[0])
                except (ValueError, TypeError, IndexError):
                    raw_id = None
            detections.append({
                "name": class_names[int(box.cls[0])],
                "bbox": (x1, y1, x2, y2),
                "confidence": float(box.conf[0]),
                "center": ((x1 + x2) / 2, (y1 + y2) / 2),
                "area": (x2 - x1) * (y2 - y1),
                # 不同检测源 ID 可能重复，加前缀区分（COCO / 各家庭模型）
                "track_id": f"{source}:{raw_id}" if raw_id is not None else None,
            })
    return detections


def track_objects(frame, conf=CONF_THRESHOLD, classes=None):
    """带目标跟踪的物品检测：返回与 detect_objects 相同结构，额外含 track_id。

    跟踪失败时自动回退到普通检测，保证功能不中断。
    """
    if MODEL is None:
        load_model()
    if classes is None:
        classes = TARGET_CLASSES
    ids = [i for i, n in CLASS_NAMES.items() if n in classes]
    try:
        detections = _collect_tracking(MODEL, CLASS_NAMES, frame, conf,
                                       "coco", ids)
        for cname, model in CUSTOM_MODELS.items():
            detections += _collect_tracking(
                model, CUSTOM_CLASS_NAMES[cname], frame, conf, cname)
        return detections
    except Exception:
        return detect_objects(frame, conf=conf, classes=classes)


def reset_tracking():
    """清空跟踪器状态（新开一次训练时调用，避免沿用上次 ID）。"""
    for model in [MODEL] + list(CUSTOM_MODELS.values()):
        if model is None:
            continue
        try:
            predictor = getattr(model, "predictor", None)
            if predictor is not None and hasattr(predictor, "trackers"):
                predictor.trackers = [[]]
        except Exception:
            pass


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
