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
from collections import OrderedDict

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VISION_DIR = os.path.join(ROOT, "vision")
if VISION_DIR not in sys.path:
    sys.path.insert(0, VISION_DIR)

from pose_utils import (  # noqa: E402
    LandmarkSmoother, POSE_CONNECTIONS_DISPLAY, draw_pos, point_reliable,
)
# 注意：MediaPipe 底层无法打开含中文的绝对路径，必须用相对路径
# （配合 start() 里的 os.chdir(ROOT) 保证相对路径正确解析）。
MODEL_PATH = os.path.join("vision", "models", "pose_landmarker_full.task")
HAND_MODEL_PATH = os.path.join("vision", "models", "hand_landmarker.task")

SMOOTH_ALPHA = 0.35
MAX_ALIGN_FRAMES = 8  # 姿态/手部按帧号对齐时最多保留几帧历史


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
        self.hand_landmarks = {}      # {'L': [21点], 'R': [21点]}，与 pose 帧号对齐
        # 复用公共平滑器：置信度不足(visibility<=0.3)或出画的关键点锁定不更新
        self.smoother = LandmarkSmoother(alpha=SMOOTH_ALPHA, min_visibility=0.3)
        self.landmarker = None
        self.hand_landmarker = None
        self.frame_seq = 0            # 每读一帧自增，供上层去重（同一帧只消费一次）
        self._frame_ts = {}           # ts_ms -> frame_seq
        self._pose_cache = OrderedDict()
        self._hand_cache = OrderedDict()
        self.fps = 0.0
        self.error = None
        self._t_last = time.time()

    # ---------- MediaPipe 异步回调 ----------
    def _cache(self, cache, ts_ms, value):
        cache[ts_ms] = value
        while len(cache) > MAX_ALIGN_FRAMES:
            cache.popitem(last=False)

    def _on_result(self, result, _image, ts_ms):
        value = None
        if result.pose_landmarks:
            value = (result.pose_landmarks[0],
                     self.smoother.update(result.pose_landmarks[0]))
            self.raw_lms, self.smoothed_lms = value
        self._cache(self._pose_cache, ts_ms, value)

    def _on_hand_result(self, result, _image, ts_ms):
        """手部 21 点回调。MediaPipe 的 handedness 假设输入是镜像自拍，
        本项目送的是原始帧，所以左右标签要对调。"""
        hands = {}
        if result.hand_landmarks:
            for i, lms in enumerate(result.hand_landmarks):
                label = "unknown"
                if result.handedness and i < len(result.handedness):
                    cats = result.handedness[i]
                    if cats:
                        label = cats[0].category_name
                side = "L" if label == "Right" else "R" if label == "Left" else "?"
                hands[side] = lms
        self._cache(self._hand_cache, ts_ms, hands)

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

        # 手部模型失败不阻断摄像头：退回 Pose 的 4 点掌心，保证系统可用
        try:
            hand_options = vision.HandLandmarkerOptions(
                base_options=BaseOptions(
                    model_asset_path=HAND_MODEL_PATH,
                    delegate=BaseOptions.Delegate.CPU,
                ),
                running_mode=vision.RunningMode.LIVE_STREAM,
                num_hands=2,
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
                result_callback=self._on_hand_result,
            )
            self.hand_landmarker = vision.HandLandmarker.create_from_options(
                hand_options)
        except Exception as e:
            self.hand_landmarker = None
            print(f"[camera] 手部模型未启用: {e}")

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
            ts_ms = int(now * 1000)
            self.frame_seq += 1
            self._frame_ts[ts_ms] = self.frame_seq
            if len(self._frame_ts) > MAX_ALIGN_FRAMES * 4:
                for old in list(self._frame_ts)[:-MAX_ALIGN_FRAMES * 2]:
                    self._frame_ts.pop(old, None)
            self.fps = 0.9 * self.fps + 0.1 * (1.0 / max(now - self._t_last, 1e-6))
            self._t_last = now

            with self.frame_lock:
                self.raw_frame = frame.copy()            # 原始帧：识别用
                self.latest_frame = cv2.flip(frame, 1)  # 镜像帧：显示用

            # 用原始帧做识别，保证左右手不颠倒；pose 与 hand 用同一帧号对齐
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
            if self.landmarker is not None:
                try:
                    self.landmarker.detect_async(mp_image, ts_ms)
                except Exception:
                    pass
            if self.hand_landmarker is not None:
                try:
                    self.hand_landmarker.detect_async(mp_image, ts_ms)
                except Exception:
                    pass

    def get_frame(self):
        with self.frame_lock:
            return None if self.latest_frame is None else self.latest_frame.copy()

    def get_raw_frame(self):
        """返回原始帧（未镜像），供 YOLO 物品检测等识别使用。"""
        with self.frame_lock:
            return None if self.raw_frame is None else self.raw_frame.copy()

    def get_pose_frame(self):
        """返回叠加骨架线条的镜像显示帧（大屏用）。

        骨架点来自平滑后的原始关键点；显示帧是镜像的，
        用 draw_pos() 把 x 翻过来，保证骨架与画面里的人对齐。
        没有人或关键点不可靠时不画，避免出画时骨架乱飞。
        """
        frame = self.get_frame()
        if frame is None:
            return None
        lms = self.smoothed_lms
        if not lms:
            return frame
        h, w = frame.shape[:2]
        needed = {i for pair in POSE_CONNECTIONS_DISPLAY for i in pair}
        pts = {}
        for i, lm in enumerate(lms):
            if i in needed and point_reliable(lm):
                pts[i] = draw_pos(lm, w, h)
        # 只画精简身体骨架：不画面部/手指，避免大屏上线条过密
        for a, b in POSE_CONNECTIONS_DISPLAY:
            if a in pts and b in pts:
                cv2.line(frame, pts[a], pts[b], (210, 160, 70), 3, cv2.LINE_AA)
        # 关键点只画参与连线的点，圆点略缩小
        for (x, y) in pts.values():
            cv2.circle(frame, (x, y), 5, (60, 130, 230), -1, cv2.LINE_AA)
            cv2.circle(frame, (x, y), 2, (255, 255, 255), -1, cv2.LINE_AA)
        return frame

    def get_landmarks(self):
        """返回 (smoothed_lms, raw_lms)。"""
        return self.smoothed_lms, self.raw_lms

    def get_detection(self):
        """返回同一帧的姿态与手部关键点：dict(frame_id, lms, raw, hands)。

        hands 为 {'L': [21点], 'R': [21点]}；某路回调缺失时对应值为 None。
        frame_id 是采集帧序号，上层据此确保同一帧只被训练循环消费一次，
        避免轮询比摄像头快时重复计数。
        """
        ts = next(reversed(self._pose_cache), None)
        if ts is None:
            return {"frame_id": self.frame_seq, "lms": None,
                    "raw": None, "hands": None}
        pose = self._pose_cache.get(ts)
        hands = self._hand_cache.get(ts)
        return {
            "frame_id": self._frame_ts.get(ts, self.frame_seq),
            "lms": pose[1] if pose else None,
            "raw": pose[0] if pose else None,
            "hands": hands or None,
        }

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
        self.hand_landmarks = {}
        self._pose_cache.clear()
        self._hand_cache.clear()
        self._frame_ts.clear()
        self.smoother.reset()

        # MediaPipe LIVE_STREAM 下 landmarker.close() 需等异步回调收尾，可能耗时数秒。
        # 放到守护线程异步释放，避免阻塞 stop 接口导致前端超时；
        # 期间 running 已为 False、cap 已释放，下次 start 可正常重新打开。
        landmarkers = [m for m in (self.landmarker, self.hand_landmarker)
                       if m is not None]
        self.landmarker = None
        self.hand_landmarker = None
        if landmarkers:
            def _close():
                for m in landmarkers:
                    try:
                        m.close()
                    except Exception:
                        pass
            threading.Thread(target=_close, daemon=True).start()

        return {"ok": True, "msg": "摄像头已释放"}


# 全局单例，供各服务与接口共享
camera = CameraService()
