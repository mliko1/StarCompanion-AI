# -*- coding: utf-8 -*-
"""
星伴AI 第二阶段第2步：举手动作检测
在实时姿态识别的基础上，用"手腕是否高于肩膀"这一相对位置关系判断举手，
并用肘部夹角辅助展示。举手开始/结束时，把起止时间和持续时长记录到
logs/raise_hand_log.csv —— 这是"训练行为量化记录"的最小雏形。

（P0 消重：几何/可靠性/平滑复用 pose_utils，举手判定复用 action_base）

按 q 键或 ESC 键退出。

运行方式（在项目根目录）：
    python vision/raise_hand.py
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
from action_base import raise_check, RaiseTracker

MODEL_PATH = "vision/models/pose_landmarker_full.task"
LOG_PATH = "logs/raise_hand_log.csv"

SMOOTH_ALPHA = 0.30
EDGE_MARGIN = 0.03     # 距画面边缘 3% 以内视为"边缘区"

latest_result = None
# 举手独立脚本沿用严格可靠性语义：置信度 >0.5 且不贴近边缘（出画冻结）
smoother = LandmarkSmoother(
    alpha=SMOOTH_ALPHA, edge_alpha=0.15, min_visibility=0.5,
    reliable_margin=EDGE_MARGIN, edge_margin=EDGE_MARGIN * 3)


def on_result(result, _image, _ts_ms):
    global latest_result
    latest_result = result
    if result.pose_landmarks:
        smoother.update(result.pose_landmarks[0])


class RaiseLogger:
    """记录举手事件：开始时间、结束时间、持续时长，写入 CSV。"""

    def __init__(self, path):
        self.path = path
        self.active = {}  # {"left": 开始时刻, "right": ...}
        if not os.path.exists(path):
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerow(["手臂", "开始时间", "结束时间", "持续秒"])

    def update(self, side, raised):
        now = time.strftime("%H:%M:%S")
        if raised and side not in self.active:
            self.active[side] = now
            print(f"[记录] {side} 开始举手 @ {now}")
        elif not raised and side in self.active:
            start = self.active.pop(side)
            start_s = hms_to_sec(start)
            end_s = hms_to_sec(now)
            if end_s < start_s:  # 跨越午夜的小概率情况
                end_s += 86400
            dur = round(end_s - start_s, 1)
            if dur < 0.5:
                # 持续不足 0.5 秒的事件判定为抖动，不写入 CSV
                print(f"[过滤] {side} 持续 {dur} 秒，判定为抖动，不记录")
                return
            with open(self.path, "a", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerow([side, start, now, dur])
            print(f"[记录] {side} 放下手 @ {now}，持续 {dur} 秒")


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

    logger = RaiseLogger(LOG_PATH)
    # 防抖：连续 DEBOUNCE 帧状态一致才真正切换，消除抬手瞬间的抖动误判
    DEBOUNCE = 8  # 连续 8 帧（约0.27秒）一致才切换状态
    l_track, r_track = RaiseTracker(DEBOUNCE), RaiseTracker(DEBOUNCE)
    print("摄像头已打开，试着举起手臂；按 q 键退出")

    fps, t_last = 0.0, time.time()

    while True:
        ok, frame_raw = cap.read()
        if not ok:
            print("错误：摄像头画面读取失败")
            break

        # 识别用原始帧；显示用镜像帧（像照镜子）
        frame = cv2.flip(frame_raw, 1)
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

            # ---------- 举手检测（出画冻结 + 迟滞 + 连续帧防抖） ----------
            l_raw, l_angle = raise_check(
                smoothed_lms, "left", l_track.disp,
                min_visibility=0.5, reliable_margin=EDGE_MARGIN)
            r_raw, r_angle = raise_check(
                smoothed_lms, "right", r_track.disp,
                min_visibility=0.5, reliable_margin=EDGE_MARGIN)

            arm_warn = (l_raw is None) or (r_raw is None)

            # None = 手臂出画，冻结状态不更新；否则连续 DEBOUNCE 帧一致才切换
            l_disp = l_track.update(l_raw)
            r_disp = r_track.update(r_raw)

            logger.update("left", l_disp)
            logger.update("right", r_disp)

            # 在手腕旁显示肘部夹角，举起时手腕画大圈高亮
            for raised, wrist_i, ang in ((l_disp, L_WRIST, l_angle),
                                         (r_disp, R_WRIST, r_angle)):
                lm = smoothed_lms[wrist_i]
                pos = draw_pos(lm, w, h)
                cv2.putText(frame, f"elbow:{ang:.0f}", (pos[0] + 10, pos[1]),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                if raised:
                    cv2.circle(frame, pos, 12, (0, 255, 0), 3)

            if arm_warn:
                status = "Keep arms in frame!"
            elif l_disp or r_disp:
                status = ("RAISE HAND: " +
                          ("L" if l_disp else "") + ("R" if r_disp else ""))
            else:
                status = "Person detected"

        status_color = (0, 255, 0) if status.startswith("RAISE") else \
                       (0, 255, 255) if status.startswith("Keep") else (255, 255, 255)
        cv2.putText(frame, f"{status} | FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        cv2.putText(frame, "Raise hand and hold; press Q to quit", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)

        cv2.imshow("XingBanAI Raise Hand", frame)
        key = cv2.waitKey(1)
        # 按键只在视频窗口获得焦点时有效；点窗口右上角的 X 也能正常退出
        if (key in (ord("q"), 27) or
                cv2.getWindowProperty("XingBanAI Raise Hand",
                                      cv2.WND_PROP_VISIBLE) < 1):
            break

    # 程序退出时，把还没放下的手臂也记录为结束
    for side in list(logger.active.keys()):
        logger.update(side, False)

    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()
    print(f"已退出。举手记录保存在 {LOG_PATH}")


if __name__ == "__main__":
    main()
