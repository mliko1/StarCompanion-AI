# -*- coding: utf-8 -*-
"""统一摄像头服务（全局单例，整个系统只开一次摄像头）。

解决问题：原 vision/*.py 每个脚本各自 cv2.VideoCapture，导致
多模块重复开摄像头、占用冲突、线程阻塞。本服务集中管理。

设计：
- 后台线程循环读帧 + MediaPipe 姿态识别，接口只读取最新帧/关键点，不阻塞。
- 打开失败回退 MSMF；stop 时正确释放摄像头与模型。
"""

import os
import sys
import threading
import time

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VISION_DIR = os.path.join(ROOT, "vision")
if VISION_DIR not in sys.path:
    sys.path.insert(0, VISION_DIR)

from pose_utils import LandmarkSmoother  # noqa: E402
# 注意：MediaPipe 底层无法打开含中文的绝对路径，必须用相对路径
# （配合 start() 里的 os.chdir(ROOT) 保证相对路径正确解析）。
MODEL_PATH = os.path.join("vision", "models", "pose_landmarker_full.task")

SMOOTH_ALPHA = 0.35


class CameraService:
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
        self.cap = None
        self.running = False
        self.thread = None
        self.frame_lock = threading.Lock()
        self.latest_frame = None      # BGR 镜像帧（网页显示用）
        self.raw_frame = None         # BGR 原始帧（识别用，保证左右手正确）
        self.smoothed_lms = None      # 平滑关键点（持续动作用）
        self.raw_lms = None           # 原始关键点（拍手等快动作用）
        # 复用公共平滑器：置信度不足(visibility<=0.3)或出画的关键点锁定不更新
        self.smoother = LandmarkSmoother(alpha=SMOOTH_ALPHA, min_visibility=0.3)
        self.landmarker = None
        self.fps = 0.0
        self.error = None
        self._t_last = time.time()

    # ---------- MediaPipe 异步回调 ----------
    def _on_result(self, result, _image, _ts_ms):
        if not result.pose_landmarks:
            return
        self.raw_lms = result.pose_landmarks[0]
        self.smoothed_lms = self.smoother.update(self.raw_lms)

    def start(self):
        if self.running:
            return {"ok": True, "msg": "摄像头已在运行"}

        os.chdir(ROOT)  # 切到项目根，保证 MediaPipe 相对模型路径可解析

        for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF):
            cap = cv2.VideoCapture(0, backend)
            if cap.isOpened():
                self.cap = cap
                break
        if self.cap is None or not self.cap.isOpened():
            self.error = "无法打开摄像头（可能被其他程序占用或未授权）"
            return {"ok": False, "msg": self.error}

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        try:
            options = vision.PoseLandmarkerOptions(
                base_options=BaseOptions(
                    model_asset_path=MODEL_PATH,
                    delegate=BaseOptions.Delegate.CPU,
                ),
                running_mode=vision.RunningMode.LIVE_STREAM,
                min_pose_detection_confidence=0.6,
                min_tracking_confidence=0.7,
                result_callback=self._on_result,
            )
            self.landmarker = vision.PoseLandmarker.create_from_options(options)
        except Exception as e:  # 模型文件缺失等
            self.cap.release()
            self.cap = None
            self.error = f"姿态识别模型初始化失败: {e}"
            return {"ok": False, "msg": self.error}

        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return {"ok": True, "msg": "摄像头已启动"}

    def _loop(self):
        while self.running:
            if self.cap is None:
                break
            ok, frame = self.cap.read()
            if not ok:
                self.error = "摄像头画面读取失败"
                time.sleep(0.1)
                continue
            now = time.time()
            self.fps = 0.9 * self.fps + 0.1 * (1.0 / max(now - self._t_last, 1e-6))
            self._t_last = now

            with self.frame_lock:
                self.raw_frame = frame.copy()            # 原始帧：识别用
                self.latest_frame = cv2.flip(frame, 1)  # 镜像帧：显示用

            if self.landmarker is not None:
                try:
                    # 用原始帧做姿态识别，保证左右手不颠倒
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
                    self.landmarker.detect_async(mp_image, int(now * 1000))
                except Exception:
                    pass

    def get_frame(self):
        with self.frame_lock:
            return None if self.latest_frame is None else self.latest_frame.copy()

    def get_raw_frame(self):
        """返回原始帧（未镜像），供 YOLO 物品检测等识别使用。"""
        with self.frame_lock:
            return None if self.raw_frame is None else self.raw_frame.copy()

    def get_landmarks(self):
        """返回 (smoothed_lms, raw_lms)。"""
        return self.smoothed_lms, self.raw_lms

    def status(self):
        return {
            "running": self.running,
            "fps": round(self.fps, 1),
            "person_detected": self.smoothed_lms is not None,
            "error": self.error,
        }

    def stop(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1.0)
            self.thread = None
        # 先释放摄像头（快），保证接口不阻塞、设备立刻可用
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.latest_frame = None
        self.raw_frame = None
        self.smoothed_lms = None
        self.raw_lms = None
        self.smoother.reset()

        # MediaPipe LIVE_STREAM 下 landmarker.close() 需等异步回调收尾，可能耗时数秒。
        # 放到守护线程异步释放，避免阻塞 stop 接口导致前端超时；
        # 期间 running 已为 False、cap 已释放，下次 start 可正常重新打开。
        landmarker = self.landmarker
        self.landmarker = None
        if landmarker is not None:
            def _close():
                try:
                    landmarker.close()
                except Exception:
                    pass
            threading.Thread(target=_close, daemon=True).start()

        return {"ok": True, "msg": "摄像头已释放"}


# 全局单例，供各服务与接口共享
camera = CameraService()
