# -*- coding: utf-8 -*-
"""
星伴AI 第二阶段第1步：摄像头实时人体姿态识别
功能：打开摄像头，检测画面中的人，实时绘制 33 个人体关键点和骨架连线，
     并在左上角显示当前识别状态和帧率。
按 q 键或 ESC 键退出窗口。

运行方式（在项目根目录、已激活 .venv 时）：
    python vision/pose_camera.py
"""

import time

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

MODEL_PATH = "vision/models/pose_landmarker_full.task"  # 完整版模型，精度更高

# 33 个关键点的骨架连线规则（哪些点之间要画线）
POSE_CONNECTIONS = [
    # 头部
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (7, 8),
    (9, 10),
    # 躯干
    (11, 12), (11, 23), (12, 24), (23, 24),
    # 左臂 / 右臂
    (11, 13), (13, 15), (12, 14), (14, 16),
    (15, 17), (15, 19), (15, 21), (17, 19),
    (16, 18), (16, 20), (16, 22), (18, 20),
    (21, 23), (22, 24),
    # 左腿 / 右腿
    (23, 25), (25, 27), (27, 29), (29, 31), (27, 31),
    (24, 26), (26, 28), (28, 30), (30, 32), (28, 32),
]

# 新版本 MediaPipe：识别结果通过回调函数返回
latest_result = None
smoothed_lms = None    # 平滑后的关键点（减少抖动）
SMOOTH_ALPHA = 0.35    # 平滑系数：越小骨架越稳但跟手越慢，越大跟手快但会抖
HEAD_POINTS = [0, 7, 8]  # 头部只画：鼻尖(0)、左耳(7)、右耳(8)，不画面部连线


def on_result(result, _image, _ts_ms):
    global latest_result, smoothed_lms
    latest_result = result
    if result.pose_landmarks:
        new_lms = result.pose_landmarks[0]
        if smoothed_lms is None or len(smoothed_lms) != len(new_lms):
            smoothed_lms = list(new_lms)
        else:
            # 指数平滑：新点和上一帧的点按比例融合
            for i, lm in enumerate(new_lms):
                prev = smoothed_lms[i]
                smoothed_lms[i] = type(lm)(
                    x=SMOOTH_ALPHA * lm.x + (1 - SMOOTH_ALPHA) * prev.x,
                    y=SMOOTH_ALPHA * lm.y + (1 - SMOOTH_ALPHA) * prev.y,
                    z=SMOOTH_ALPHA * lm.z + (1 - SMOOTH_ALPHA) * prev.z,
                    visibility=lm.visibility,
                )


def main():
    # ---------- 创建姿态识别器（CPU 运行，不需要显卡） ----------
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

    # ---------- 打开摄像头 ----------
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("错误：无法打开摄像头，请检查设备或隐私设置")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("摄像头已打开，按 q 键退出")
    fps, t_last = 0.0, time.time()

    while True:
        ok, frame = cap.read()
        if not ok:
            print("错误：摄像头画面读取失败，程序退出")
            break

        # 镜像翻转：像照镜子一样，左右方向更符合直觉，也减少左右手混淆
        frame = cv2.flip(frame, 1)

        # 帧率计算
        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / max(now - t_last, 1e-6))
        t_last = now

        # 把画面交给 MediaPipe（异步模式）
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        landmarker.detect_async(mp_image, int(now * 1000))

        # ---------- 画关键点和骨架（身体全部画，头部只画少量点） ----------
        h, w = frame.shape[:2]
        if smoothed_lms:
            for i, lm in enumerate(smoothed_lms):
                if i in HEAD_POINTS:
                    # 头部：画小的青色点，不画线
                    cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 3,
                               (255, 255, 0), -1)
                elif i > 10:
                    # 身体：绿色点
                    cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 4,
                               (0, 255, 0), -1)
                # 其余 1~6、9、10 的面部点不画
            for a, b in POSE_CONNECTIONS:
                if a < 11 or b < 11:
                    continue
                pa, pb = smoothed_lms[a], smoothed_lms[b]
                cv2.line(frame, (int(pa.x * w), int(pa.y * h)),
                         (int(pb.x * w), int(pb.y * h)), (0, 200, 255), 2)
            status = "Person detected"
        else:
            status = "No person"

        # 左上角显示状态和帧率（OpenCV 不支持中文，用英文避免乱码）
        cv2.putText(frame, f"{status} | FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, "Press Q to quit", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)

        cv2.imshow("XingBanAI Pose", frame)
        if cv2.waitKey(1) in (ord("q"), 27):  # q 或 ESC
            break

    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()
    print("已退出，摄像头释放完毕")


if __name__ == "__main__":
    main()
