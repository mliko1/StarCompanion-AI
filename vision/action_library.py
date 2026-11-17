# -*- coding: utf-8 -*-
"""
星伴AI 动作库实时演示（20+ 动作识别）

用法（项目根目录）：python vision/action_library.py
屏幕显示当前命中的所有动作；动作变化时写入 logs/action_log.csv。
按 q 或点窗口 X 退出。
"""

import csv
import os
import time

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

from action_engine import load_actions, detect_actions
from clap_core import point_reliable

ACTIONS = load_actions()

MODEL_PATH = "vision/models/pose_landmarker_full.task"
LOG_PATH = "logs/action_log.csv"
HEAD_POINTS = [0, 7, 8]
SMOOTH_ALPHA = 0.3

POSE_CONNECTIONS = [
    (11, 12), (11, 23), (12, 24), (23, 24),
    (11, 13), (13, 15), (12, 14), (14, 16),
    (23, 25), (25, 27), (24, 26), (26, 28),
]

latest_result = None
smoothed = None


def on_result(result, _img, _ts):
    global latest_result, smoothed
    latest_result = result
    if result.pose_landmarks:
        new = result.pose_landmarks[0]
        if smoothed is None or len(smoothed) != len(new):
            smoothed = list(new)
        else:
            for i, lm in enumerate(new):
                if point_reliable(lm):
                    p = smoothed[i]
                    smoothed[i] = type(lm)(
                        x=SMOOTH_ALPHA * lm.x + (1 - SMOOTH_ALPHA) * p.x,
                        y=SMOOTH_ALPHA * lm.y + (1 - SMOOTH_ALPHA) * p.y,
                        z=SMOOTH_ALPHA * lm.z + (1 - SMOOTH_ALPHA) * p.z,
                        visibility=lm.visibility)


def draw_pos(lm, w, h):
    return int((1 - lm.x) * w), int(lm.y * h)


def main():
    name_by_id = {a["id"]: a["name"] for a in ACTIONS}
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(["时间", "动作"])

    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH,
                                 delegate=BaseOptions.Delegate.CPU),
        running_mode=vision.RunningMode.LIVE_STREAM,
        min_pose_detection_confidence=0.6,
        min_tracking_confidence=0.7,
        result_callback=on_result)
    landmarker = vision.PoseLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("错误：无法打开摄像头")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    last_ids = None
    fps, t_last = 0.0, time.time()
    print(f"动作库共 {len(ACTIONS)} 个动作，摆姿势试试；按 q 退出")

    while True:
        ok, frame_raw = cap.read()
        if not ok:
            break
        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / max(now - t_last, 1e-6))
        t_last = now

        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_raw)
        landmarker.detect_async(mp_img, int(now * 1000))
        frame = cv2.flip(frame_raw, 1)
        h, w = frame.shape[:2]

        ids = []
        if smoothed:
            for i, lm in enumerate(smoothed):
                if i in HEAD_POINTS:
                    cv2.circle(frame, draw_pos(lm, w, h), 3, (255, 255, 0), -1)
                elif i > 10:
                    cv2.circle(frame, draw_pos(lm, w, h), 4, (0, 255, 0), -1)
            for a, b in POSE_CONNECTIONS:
                cv2.line(frame, draw_pos(smoothed[a], w, h),
                         draw_pos(smoothed[b], w, h), (0, 200, 255), 2)
            ids = detect_actions(smoothed)

        # 动作变化时记录
        if ids != last_ids:
            if ids:
                with open(LOG_PATH, "a", newline="", encoding="utf-8-sig") as f:
                    csv.writer(f).writerow(
                        [time.strftime("%H:%M:%S"), "、".join(name_by_id[i] for i in ids)])
            last_ids = ids

        names = "、".join(name_by_id[i] for i in ids) or "无动作"
        color = (0, 255, 0) if ids else (200, 200, 200)
        cv2.putText(frame, f"动作: {names}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.putText(frame, f"FPS: {fps:.1f} | 共{len(ACTIONS)}个动作",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)

        cv2.imshow("XingBanAI Action Library", frame)
        if (cv2.waitKey(1) in (ord("q"), 27) or
                cv2.getWindowProperty("XingBanAI Action Library",
                                      cv2.WND_PROP_VISIBLE) < 1):
            break

    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()
    print(f"已退出，动作记录见 {LOG_PATH}")


if __name__ == "__main__":
    main()
