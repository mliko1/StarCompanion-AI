# -*- coding: utf-8 -*-
"""
星伴AI 第二阶段第3步：拍手检测
用"手腕间距 / 肩宽"的比例关系判断双手是否合拢（对距离远近免疫），
双手必须高于胸线，排除手放腿上的误判。
每拍一次记录时间戳和与上一次的间隔到 logs/clap_log.csv。

按 q 键或 ESC 键退出（点窗口右上角 X 也可以）。

运行方式（在项目根目录）：
    python vision/clap_hands.py
"""

import csv
import math
import os
import time

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

from clap_core import clap_check, ClapCounter

MODEL_PATH = "vision/models/pose_landmarker_full.task"
LOG_PATH = "logs/clap_log.csv"

SMOOTH_ALPHA = 0.30
HEAD_POINTS = [0, 7, 8]
EDGE_MARGIN = 0.03

L_SHOULDER, R_SHOULDER = 11, 12
L_HIP, R_HIP = 23, 24
L_WRIST, R_WRIST = 15, 16

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
debug_info = {}   # 供日志输出，透视判断的每一环


def point_reliable(lm, margin=None):
    """关键点可靠性检查：置信度足够，且坐标在画面内。
    只要还在画面内（哪怕贴近边缘）就视为可用——边缘区由平滑加强来压抖动；
    只有真正出画（坐标越界）或置信度极低才视为不可靠并锁定。"""
    return (lm.visibility > 0.3 and
            -0.01 < lm.x < 1.01 and
            -0.01 < lm.y < 1.01)


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
                    # 边缘区（含出画临界）自动加强平滑，抑制边界抖动
                    near_edge = (lm.x < EDGE_MARGIN * 2 or
                                 lm.x > 1 - EDGE_MARGIN * 2 or
                                 lm.y < EDGE_MARGIN * 2 or
                                 lm.y > 1 - EDGE_MARGIN * 2)
                    a = 0.12 if near_edge else SMOOTH_ALPHA
                    smoothed_lms[i] = type(lm)(
                        x=a * lm.x + (1 - a) * prev.x,
                        y=a * lm.y + (1 - a) * prev.y,
                        z=a * lm.z + (1 - a) * prev.z,
                        visibility=lm.visibility,
                    )
                # 不可靠（真正出画）：保持最后一个可靠位置，锁定不抖


def dist2d(p1, p2):
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


def hand_center(lms, side):
    """手掌中心：手腕(15/16)、小指根(17/18)、食指根(19/20)、拇指(21/22)的平均。
    拍手时掌心贴合，用手掌中心测距远比手腕准确。"""
    idx = (L_WRIST, 17, 19, 21) if side == "L" else (R_WRIST, 18, 20, 22)
    x = sum(lms[i].x for i in idx) / 4
    y = sum(lms[i].y for i in idx) / 4
    return x, y


def clap_state(lms, was_contact):
    """返回 (双手是否合拢, 掌心距/肩宽比例)。None 表示关键点不可靠。
    迟滞门槛基于实测数据（拍击时比例约0.30~0.51）：
    合拢 < 0.55，分开 > 0.80。双手必须高于胸线。
    髋部不可靠（出画）时，胸线退化为肩线下方 0.15 的估计值。"""
    lw, rw = lms[L_WRIST], lms[R_WRIST]
    ls, rs = lms[L_SHOULDER], lms[R_SHOULDER]
    lh, rh = lms[L_HIP], lms[R_HIP]
    rel_ok = all(point_reliable(p) for p in (lw, rw, ls, rs))
    if not rel_ok:
        debug_info.update(ratio=None, above_chest=None, rel_ok=False)
        return None, 0.0

    lcx, lcy = hand_center(lms, "L")
    rcx, rcy = hand_center(lms, "R")
    ratio = math.hypot(lcx - rcx, lcy - rcy) / max(dist2d(ls, rs), 1e-6)

    if point_reliable(lh) and point_reliable(rh):
        chest_y = (ls.y + rs.y + lh.y + rh.y) / 4
    else:
        chest_y = max(ls.y, rs.y) + 0.15  # 髋部出画时的退让估计

    above_chest = lcy < chest_y and rcy < chest_y

    if was_contact:
        contact = above_chest and ratio < 0.80
    else:
        contact = above_chest and ratio < 0.55

    debug_info.update(ratio=round(ratio, 3), above_chest=above_chest, rel_ok=True)
    return contact, ratio


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
        now_s = self._to_sec(now)
        gap = round(now_s - self.last_ts, 2) if self.last_ts else ""
        if gap != "" and gap < 0:
            gap += 86400
        self.last_ts = now_s
        with open(self.path, "a", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow([self.count, now, gap])
        print(f"[记录] 第 {self.count} 次拍手 @ {now}，距上次 {gap} 秒")

    @staticmethod
    def _to_sec(hms):
        h, m, s = hms.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)


def draw_pos(lm, w, h):
    """识别在原始帧上完成，显示帧是镜像的，绘制时 x 换成 1-x。"""
    return int((1 - lm.x) * w), int(lm.y * h)


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
