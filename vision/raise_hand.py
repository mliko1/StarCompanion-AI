# -*- coding: utf-8 -*-
"""
星伴AI 第二阶段第2步：举手动作检测
在实时姿态识别的基础上，用"手腕是否高于肩膀"这一相对位置关系判断举手，
并用肘部夹角辅助展示。举手开始/结束时，把起止时间和持续时长记录到
logs/raise_hand_log.csv —— 这是"训练行为量化记录"的最小雏形。

按 q 键或 ESC 键退出。

运行方式（在项目根目录）：
    python vision/raise_hand.py
"""

import csv
import math
import os
import time

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

MODEL_PATH = "vision/models/pose_landmarker_full.task"
LOG_PATH = "logs/raise_hand_log.csv"

SMOOTH_ALPHA = 0.30
HEAD_POINTS = [0, 7, 8]

# 关键点编号：左肩11 左肘13 左腕15；右肩12 右肘14 右腕16
L_SHOULDER, L_ELBOW, L_WRIST = 11, 13, 15
R_SHOULDER, R_ELBOW, R_WRIST = 12, 14, 16

POSE_CONNECTIONS = [
    (11, 12), (11, 23), (12, 24), (23, 24),
    (11, 13), (13, 15), (12, 14), (14, 16),
    (15, 17), (15, 19), (15, 21), (17, 19),
    (16, 18), (16, 20), (16, 22), (18, 20),
    (21, 23), (22, 24),
    (23, 25), (25, 27), (27, 29), (29, 31), (27, 31),
    (24, 26), (26, 28), (28, 30), (30, 32), (28, 32),
]

latest_result = None
smoothed_lms = None
EDGE_MARGIN = 0.03     # 距画面边缘 3% 以内视为"边缘区"


def point_reliable(lm, margin=EDGE_MARGIN):
    """关键点可靠性检查：置信度足够，且不贴近画面边缘。
    手臂出画时模型只能"猜"位置，坐标会剧烈抖动，必须视为不可靠。"""
    return (lm.visibility > 0.5 and
            margin < lm.x < 1 - margin and
            margin < lm.y < 1 - margin)


def on_result(result, _image, _ts_ms):
    global latest_result, smoothed_lms
    latest_result = result
    if result.pose_landmarks:
        new_lms = result.pose_landmarks[0]
        if smoothed_lms is None or len(smoothed_lms) != len(new_lms):
            smoothed_lms = list(new_lms)
        else:
            for i, lm in enumerate(new_lms):
                prev = smoothed_lms[i]
                if point_reliable(lm):
                    # 边缘区自动加强平滑，抑制出画前的剧烈抖动
                    a = 0.15 if not point_reliable(lm, EDGE_MARGIN * 3) \
                        else SMOOTH_ALPHA
                    smoothed_lms[i] = type(lm)(
                        x=a * lm.x + (1 - a) * prev.x,
                        y=a * lm.y + (1 - a) * prev.y,
                        z=a * lm.z + (1 - a) * prev.z,
                        visibility=lm.visibility,
                    )
                # 不可靠（出画/遮挡）：保持最后一个可靠位置，不更新
                # —— 骨架锁定不抖，但绝不编造新位置


def draw_pos(lm, w, h):
    """识别在原始帧上完成，显示帧是镜像的，因此绘制时 x 要换成 1-x。"""
    return int((1 - lm.x) * w), int(lm.y * h)


def angle_at(p1, p2, p3):
    """计算以 p2 为顶点、p1 和 p3 为两端的夹角（单位：度）。"""
    v1 = (p1.x - p2.x, p1.y - p2.y)
    v2 = (p3.x - p2.x, p3.y - p2.y)
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    n1 = (v1[0] ** 2 + v1[1] ** 2) ** 0.5
    n2 = (v2[0] ** 2 + v2[1] ** 2) ** 0.5
    if n1 * n2 == 0:
        return 0.0
    cos_a = max(-1.0, min(1.0, dot / (n1 * n2)))
    return math.degrees(math.acos(cos_a))


def arm_state(lms, shoulder, elbow, wrist, was_raised):
    """返回 (是否举起, 肘部夹角)。返回 None 表示手臂出画、判断不可靠。
    可靠时采用迟滞判断，避免临界点反复翻转：
    进入"举起"需要手腕高出肩膀 0.06；退出"举起"要等手腕回落到只高出 0.01。"""
    s, e, w = lms[shoulder], lms[elbow], lms[wrist]
    if not (point_reliable(s) and point_reliable(w)):
        return None, angle_at(s, e, w)
    if was_raised:
        raised = w.y < s.y - 0.01
    else:
        raised = w.y < s.y - 0.06
    return raised, angle_at(s, e, w)


class RaiseLogger:
    """记录举手事件：开始时间、结束时间、持续时长，写入 CSV。"""

    def __init__(self, path):
        self.path = path
        self.active = {}  # {"left": 开始时刻, "right": ...}
        if not os.path.exists(path):
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerow(["手臂", "开始时间", "结束时间", "持续秒"])

    @staticmethod
    def _to_sec(hms):
        h, m, s = hms.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)

    def update(self, side, raised):
        now = time.strftime("%H:%M:%S")
        if raised and side not in self.active:
            self.active[side] = now
            print(f"[记录] {side} 开始举手 @ {now}")
        elif not raised and side in self.active:
            start = self.active.pop(side)
            start_s = self._to_sec(start)
            end_s = self._to_sec(now)
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
    l_disp, r_disp = False, False   # 对外显示/记录的稳定状态
    l_cnt, r_cnt = 0, 0
    DEBOUNCE = 8  # 连续 8 帧（约0.27秒）一致才切换状态
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
            l_raw, l_angle = arm_state(smoothed_lms, L_SHOULDER, L_ELBOW, L_WRIST, l_disp)
            r_raw, r_angle = arm_state(smoothed_lms, R_SHOULDER, R_ELBOW, R_WRIST, r_disp)

            arm_warn = (l_raw is None) or (r_raw is None)

            # None = 手臂出画，冻结状态不更新；否则连续 DEBOUNCE 帧一致才切换
            if l_raw is not None:
                if l_raw == l_disp:
                    l_cnt = 0
                else:
                    l_cnt += 1
                    if l_cnt >= DEBOUNCE:
                        l_disp, l_cnt = l_raw, 0
            else:
                l_cnt = 0
            if r_raw is not None:
                if r_raw == r_disp:
                    r_cnt = 0
                else:
                    r_cnt += 1
                    if r_cnt >= DEBOUNCE:
                        r_disp, r_cnt = r_raw, 0
            else:
                r_cnt = 0

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
