# -*- coding: utf-8 -*-
"""
星伴AI 动作识别诊断工具（调阈值专用）

用途：对着摄像头做动作，屏幕实时显示关键特征值，帮助你判断
「做对了但没识别」到底差多少，从而精准调整 data/actions.json 的阈值。

用法（项目根目录）：
    python vision/debug_pose.py

屏幕左上角显示：
    - 右/左手腕相对肩的肩宽归一化高低比 dy_ratio（举手需 > 0.10）
    - 右/左手肘部夹角（举手需 > 90°）
    - 双腕距离 / 肩宽（拍手需 < 0.55）
    - 当前命中的动作

按 q 退出。

（P0 消重：平滑/绘制/距离/骨架连线复用 pose_utils）
"""

import os
import time

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

from action_engine import load_actions, detect_actions
from pose_utils import (LandmarkSmoother, draw_pos, dist2d, angle_at,
                        POSE_CONNECTIONS,
                        L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW,
                        L_WRIST, R_WRIST)

# 用脚本所在位置定位项目根目录（供 os.chdir 使用）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTIONS = load_actions()
# 注意：MediaPipe 底层无法打开「含中文」的绝对路径，这里必须用相对路径；
# main() 里会先 os.chdir(BASE_DIR) 切到项目根目录，保证相对路径可用。
MODEL_PATH = os.path.join("vision", "models", "pose_landmarker_full.task")

latest_result = None
smoother = LandmarkSmoother(alpha=0.30, min_visibility=0.3)


def on_result(result, _img, _ts):
    global latest_result
    latest_result = result
    if result.pose_landmarks:
        smoother.update(result.pose_landmarks[0])


def main():
    os.chdir(BASE_DIR)   # 切到项目根目录，相对路径才能指向正确文件
    name_by_id = {a["id"]: a["name"] for a in ACTIONS}
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

    print("诊断工具已启动。做动作时看屏幕左上角数值，按 q 退出")

    while True:
        ok, frame_raw = cap.read()
        if not ok:
            break
        now = time.time()
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_raw)
        landmarker.detect_async(mp_img, int(now * 1000))
        frame = cv2.flip(frame_raw, 1)
        h, w = frame.shape[:2]

        smoothed = smoother.smoothed
        if smoothed:
            for i, lm in enumerate(smoothed):
                if i > 10:
                    cv2.circle(frame, draw_pos(lm, w, h), 4, (0, 255, 0), -1)
            for a, b in POSE_CONNECTIONS:
                cv2.line(frame, draw_pos(smoothed[a], w, h),
                         draw_pos(smoothed[b], w, h), (0, 200, 255), 2)

            # 关键特征值（与 actions.json 阈值口径一致）
            shoulder_w = dist2d(smoothed[L_SHOULDER], smoothed[R_SHOULDER]) \
                or 1e-6
            ratio_r = ((smoothed[R_SHOULDER].y - smoothed[R_WRIST].y)
                       / shoulder_w)
            ratio_l = ((smoothed[L_SHOULDER].y - smoothed[L_WRIST].y)
                       / shoulder_w)
            angle_r = angle_at(smoothed[R_SHOULDER], smoothed[R_ELBOW],
                               smoothed[R_WRIST])
            angle_l = angle_at(smoothed[L_SHOULDER], smoothed[L_ELBOW],
                               smoothed[L_WRIST])
            hand_gap = dist2d(smoothed[L_WRIST], smoothed[R_WRIST])
            hand_ratio = hand_gap / shoulder_w

            hits = detect_actions(smoothed)
            names = "、".join(name_by_id[i] for i in hits) or "无动作"

            lines = [
                f"右手 dy_ratio: {ratio_r:+.3f} (需>0.10)  肘角: {angle_r:.0f} (需>90)",
                f"左手 dy_ratio: {ratio_l:+.3f} (需>0.10)  肘角: {angle_l:.0f} (需>90)",
                f"双腕距离/肩宽: {hand_ratio:.2f}  (拍手需 < 0.55)",
                f"命中动作: {names}",
            ]
            y = 28
            for line in lines:
                cv2.putText(frame, line, (10, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)
                y += 26
        else:
            cv2.putText(frame, "未检测到人体，请站到镜头前", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        cv2.imshow("XingBanAI Pose Debug", frame)
        if (cv2.waitKey(1) in (ord("q"), 27) or
                cv2.getWindowProperty("XingBanAI Pose Debug",
                                      cv2.WND_PROP_VISIBLE) < 1):
            break

    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()
    print("已退出")


if __name__ == "__main__":
    main()
