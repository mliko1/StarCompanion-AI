# -*- coding: utf-8 -*-
"""
星伴AI 第二阶段第3步：拍手检测
用"手腕间距 / 肩宽"的比例关系判断双手是否合拢（对距离远近免疫），
双手必须高于胸线，排除手放腿上的误判。
每拍一次记录时间戳和与上一次的间隔到 logs/clap_log.csv。

（P0 消重：几何/可靠性/平滑复用 pose_utils，拍手判定复用 action_base）

按 q 键或 ESC 键退出（点窗口右上角 X 也可以）。

运行方式（在项目根目录）：
    python vision/clap_hands.py
"""

import csv
import os
import time

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

from pose_utils import (LandmarkSmoother, draw_pos, HEAD_POINTS,
                        POSE_CONNECTIONS, hms_to_sec, L_WRIST, R_WRIST)
from action_base import clap_check, ClapCounter

MODEL_PATH = "vision/models/pose_landmarker_full.task"
LOG_PATH = "logs/clap_log.csv"

SMOOTH_ALPHA = 0.30
EDGE_MARGIN = 0.03

latest_result = None
# 拍手用原始关键点判定，平滑仅用于绘制；边缘区加强平滑（0.12）压边界抖动
smoother = LandmarkSmoother(
    alpha=SMOOTH_ALPHA, edge_alpha=0.12, min_visibility=0.3,
    edge_margin=EDGE_MARGIN * 2)


def on_result(result, _image, _ts_ms):
    global latest_result
    latest_result = result
    if result.pose_landmarks:
        smoother.update(result.pose_landmarks[0])


class ClapLogger:
    """记录每次拍手：序号、时间、与上一次的间隔。"""

    def __init__(self, path):
        self.path = path
        self.count = 0
        self.last_ts = None
        if not os.path.exists(path):
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerow(["拍手序号", "时间", "距上次间隔秒"])

    def record(self):
        self.count += 1
        now = time.strftime("%H:%M:%S")
        now_s = hms_to_sec(now)
        gap = round(now_s - self.last_ts, 2) if self.last_ts else ""
        if gap != "" and gap < 0:
            gap += 86400
        self.last_ts = now_s
        with open(self.path, "a", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow([self.count, now, gap])
        print(f"[记录] 第 {self.count} 次拍手 @ {now}，距上次 {gap} 秒")


def main():
    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path=MODEL_PATH,
            delegate=BaseOptions.Delegate.CPU,
        ),
        running_mode=vision.RunningMode.LIVE_STREAM,
        min_pose_detection_confidence=0.6,
        min_tracking_confidence=0.7,
        result_callback=on_result,
    )
    landmarker = vision.PoseLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("错误：无法打开摄像头")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    logger = ClapLogger(LOG_PATH)
    counter = ClapCounter()     # 统一拍手计数器（单帧计数+骤降防伪）
    debug_t = 0.0              # 上次诊断输出时间
    print("摄像头已打开，在胸前连续拍手试试；按 q 键退出")

    fps, t_last = 0.0, time.time()

    while True:
        ok, frame_raw = cap.read()
        if not ok:
            print("错误：摄像头画面读取失败")
            break

        frame = cv2.flip(frame_raw, 1)  # 显示用镜像，识别用原始
        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / max(now - t_last, 1e-6))
        t_last = now

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_raw)
        landmarker.detect_async(mp_image, int(now * 1000))

        h, w = frame.shape[:2]
        status = "No person"
        smoothed_lms = smoother.smoothed
        if smoothed_lms:
            for i, lm in enumerate(smoothed_lms):
                if i in HEAD_POINTS:
                    cv2.circle(frame, draw_pos(lm, w, h), 3, (255, 255, 0), -1)
                elif i > 10:
                    cv2.circle(frame, draw_pos(lm, w, h), 4, (0, 255, 0), -1)
            for a, b in POSE_CONNECTIONS:
                pa, pb = smoothed_lms[a], smoothed_lms[b]
                cv2.line(frame, draw_pos(pa, w, h), draw_pos(pb, w, h),
                         (0, 200, 255), 2)

            # ---------- 拍手检测（用原始关键点，统一核心） ----------
            raw_lms = (latest_result.pose_landmarks[0]
                       if latest_result and latest_result.pose_landmarks
                       else smoothed_lms)
            contact_raw, ratio = clap_check(raw_lms, counter.contact)

            if now - debug_t > 0.5:
                debug_t = now
                print(f"[诊断] ratio={ratio:.2f} "
                      f"contact={counter.contact} claps={counter.count}")

            if contact_raw is not None:
                if counter.update(ratio, contact_raw, now):
                    logger.record()
            else:
                counter.contact = False

            # 两手腕之间画连线，合拢时变绿加粗
            lw_pos = draw_pos(smoothed_lms[L_WRIST], w, h)
            rw_pos = draw_pos(smoothed_lms[R_WRIST], w, h)
            cv2.line(frame, lw_pos, rw_pos,
                     (0, 255, 0) if counter.contact else (200, 200, 200),
                     4 if counter.contact else 1)
            cv2.putText(frame, f"wrist/shoulder: {ratio:.2f}",
                        ((lw_pos[0] + rw_pos[0]) // 2 - 60,
                         (lw_pos[1] + rw_pos[1]) // 2 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            status = f"CLAPS: {logger.count}" if counter.contact \
                else "Person detected"

        status_color = (0, 255, 0) if status.startswith("CLAPS") \
            else (255, 255, 255)
        cv2.putText(frame, f"{status} | FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        cv2.putText(frame, "Clap hands at chest level; press Q to quit",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)

        cv2.imshow("XingBanAI Clap Hands", frame)
        key = cv2.waitKey(1)
        if (key in (ord("q"), 27) or
                cv2.getWindowProperty("XingBanAI Clap Hands",
                                      cv2.WND_PROP_VISIBLE) < 1):
            break

    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()
    print(f"已退出。共 {logger.count} 次拍手，记录保存在 {LOG_PATH}")


if __name__ == "__main__":
    main()
