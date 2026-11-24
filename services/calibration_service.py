# -*- coding: utf-8 -*-
"""家庭校准服务：镜头前自动采集 → 自动标注 → 自动训练（到收敛）→ 状态查询。

采集方式（像人脸识别一样，无需手动拍照）：
    家长把物品放进画面中央的绿色引导框，缓慢转动/移动它；
    服务持续检测引导框内画面的变化，画面每发生一次明显变化就自动拍一张，
    并用引导框自动生成 YOLO 标签。

训练方式（无需设置轮数）：
    家长展示结束后点「结束」，服务自动用较大的轮数 + 早停（patience）训练，
    验证精度连续不再提升即提前停止，相当于「自动训练到最佳识别效果」。

状态机：idle -> collecting -> training -> done / error
"""

import os
import subprocess
import sys
import threading
import time

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VISION_DIR = os.path.join(ROOT, "vision")
if VISION_DIR not in sys.path:
    sys.path.insert(0, VISION_DIR)

DATA_DIR = os.path.join(ROOT, "data", "custom_dataset")
IMG_ROOT = os.path.join(DATA_DIR, "images")
LBL_ROOT = os.path.join(DATA_DIR, "labels")
MODELS_DIR = os.path.join(VISION_DIR, "models")

GUIDE_BOX_RATIO = 0.6   # 引导框占画面 60%（与 family_calibrate 一致）
MIN_SHOTS = 20          # 建议最少采集张数

# 自动采集参数
MOTION_THRESHOLD = 200.0     # 引导框画面变化的 MSE 阈值（越小越灵敏）
TEXTURE_THRESHOLD = 40.0     # 引导框内画面方差阈值（排除空背景误拍）
MIN_CAPTURE_INTERVAL = 0.4   # 两次自动拍照最小间隔（秒）

# 自动训练参数：大轮数 + 早停，练到验证精度不再提升即停
AUTO_EPOCHS = 300
AUTO_PATIENCE = 50


def guide_box(frame_w, frame_h):
    """返回中央引导框 (x1, y1, x2, y2)。"""
    w = int(frame_w * GUIDE_BOX_RATIO)
    h = int(frame_h * GUIDE_BOX_RATIO)
    x1 = (frame_w - w) // 2
    y1 = (frame_h - h) // 2
    return (x1, y1, x1 + w, y1 + h)


def list_models():
    """扫描已训练的自定义模型，返回 [{class_name, filename, size_bytes}]。"""
    models = []
    if not os.path.isdir(MODELS_DIR):
        return models
    for fn in sorted(os.listdir(MODELS_DIR)):
        if fn.startswith("custom_") and fn.endswith(".pt"):
            cls = fn[len("custom_"):-len(".pt")]
            path = os.path.join(MODELS_DIR, fn)
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
            models.append({
                "class_name": cls,
                "filename": fn,
                "size_bytes": size,
            })
    return models


class CalibrationService:
    _instance = None
    _class_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self.state = "idle"      # idle / collecting / training / done / error
        self.class_name = None
        self.count = 0
        self.message = ""
        self.error = None
        self._seq = 0
        self._thread = None

    # ---------- 内部工具 ----------
    def _save_with_label(self, frame, cls, img_w, img_h):
        """保存图片 + 用中央引导框生成 YOLO 标签，返回图片路径。"""
        img_dir = os.path.join(IMG_ROOT, cls)
        lbl_dir = os.path.join(LBL_ROOT, cls)
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(lbl_dir, exist_ok=True)

        self._seq += 1
        name = f"{int(time.time() * 1000)}_{self._seq:04d}"
        img_path = os.path.join(img_dir, name + ".jpg")
        lbl_path = os.path.join(lbl_dir, name + ".txt")
        cv2.imwrite(img_path, frame)

        x1, y1, x2, y2 = guide_box(img_w, img_h)
        cx = (x1 + x2) / 2 / img_w
        cy = (y1 + y2) / 2 / img_h
        w = (x2 - x1) / img_w
        h = (y2 - y1) / img_h
        with open(lbl_path, "w", encoding="utf-8") as f:
            f.write(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
        return img_path

    def _ensure_camera(self):
        from services.camera_service import camera
        return camera.start()

    # ---------- 采集（自动） ----------
    def start_collect(self, class_name):
        if self.state in ("collecting", "training"):
            return {"ok": False, "msg": f"当前状态为 {self.state}，请先结束"}
        cls = (class_name or "").strip()
        if not cls or not cls.replace("_", "").replace("-", "").isalnum():
            return {"ok": False, "msg": "类名只能包含字母/数字/下划线/连字符"}
        cam = self._ensure_camera()
        if not cam["ok"]:
            self.state = "error"
            self.error = cam["msg"]
            return {"ok": False, "msg": cam["msg"]}
        self.class_name = cls
        self.count = 0
        self._seq = 0
        self.state = "collecting"
        self.error = None
        self.message = "请把物品放进绿色引导框，缓慢转动展示，系统自动采集"
        self._thread = threading.Thread(target=self._auto_collect_loop, daemon=True)
        self._thread.start()
        return {"ok": True, "msg": self.message}

    def _auto_collect_loop(self):
        """自动采集：检测引导框内画面变化，变化即自动拍照。"""
        from services.camera_service import camera
        ref_gray = None
        last_shot = 0.0
        while self.state == "collecting":
            frame = camera.get_raw_frame()
            if frame is None:
                time.sleep(0.05)
                continue
            h, w = frame.shape[:2]
            x1, y1, x2, y2 = guide_box(w, h)
            if x2 - x1 < 10 or y2 - y1 < 10:
                time.sleep(0.05)
                continue
            gray = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
            now = time.time()
            texture = float(gray.var())
            if ref_gray is None:
                ref_gray = gray.copy()
                # 第一帧框内已有物体则直接拍一张作为基准
                if texture > TEXTURE_THRESHOLD:
                    self._save_with_label(frame, self.class_name, w, h)
                    self.count += 1
                    last_shot = now
                time.sleep(0.05)
                continue
            diff = cv2.absdiff(gray, ref_gray)
            mse = float((diff.astype(np.float32) ** 2).mean())
            if (mse > MOTION_THRESHOLD and texture > TEXTURE_THRESHOLD
                    and (now - last_shot) >= MIN_CAPTURE_INTERVAL):
                self._save_with_label(frame, self.class_name, w, h)
                self.count += 1
                ref_gray = gray.copy()
                last_shot = now
            time.sleep(0.05)

    # ---------- 结束展示 + 自动训练 ----------
    def finish_and_train(self):
        if self.state != "collecting":
            return {"ok": False, "msg": "当前不在展示中（状态 " + self.state + "）"}
        if self.count < 5:
            return {"ok": False,
                    "msg": f"只采集到 {self.count} 张，太少，请继续在镜头前展示物品"}
        self.state = "training"
        self.message = "训练中：系统自动训练到最佳识别效果，请耐心等待"
        self.error = None
        self._thread = threading.Thread(
            target=self._train_loop, args=(self.class_name,), daemon=True)
        self._thread.start()
        return {"ok": True, "msg": self.message}

    def _train_loop(self, cls):
        cmd = [sys.executable, os.path.join(VISION_DIR, "train_custom_yolo.py"),
               "--name", cls,
               "--epochs", str(AUTO_EPOCHS),
               "--patience", str(AUTO_PATIENCE)]
        try:
            subprocess.call(cmd, cwd=ROOT)
            model_path = os.path.join(MODELS_DIR, f"custom_{cls}.pt")
            if os.path.exists(model_path):
                self.state = "done"
                self.message = f"训练完成！已能识别 {cls}，模型：custom_{cls}.pt"
            else:
                self.state = "error"
                self.error = "训练结束但未生成模型，请查看服务端日志"
                self.message = self.error
        except Exception as e:
            self.state = "error"
            self.error = f"训练失败: {e}"
            self.message = self.error

    def stop(self):
        """放弃本次展示（不训练），回到空闲状态。"""
        if self.state == "training":
            return {"ok": False, "msg": "训练进行中，无法中途停止，请等待完成"}
        self.state = "idle"
        self.message = "已取消本次展示"
        return {"ok": True, "msg": self.message}

    # ---------- 状态 ----------
    def status(self):
        from services.camera_service import camera
        return {
            "state": self.state,
            "class_name": self.class_name,
            "count": self.count,
            "message": self.message,
            "error": self.error,
            "min_shots": MIN_SHOTS,
            "guide_box_ratio": GUIDE_BOX_RATIO,
            "camera_running": camera.running,
            "models": list_models(),
        }


# 全局单例，供接口共享
calibration = CalibrationService()
