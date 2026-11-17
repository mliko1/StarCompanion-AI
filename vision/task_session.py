# -*- coding: utf-8 -*-
"""
星伴AI 第二阶段第4步：训练任务流程原型
系统依次下发 3 个训练任务（举右手、举左手、拍手5次），
视觉判定完成情况，记录每个任务的用时和结果到 logs/training_session.csv。

这演示了"任务下发 -> 视觉判定 -> 量化记录"的完整闭环。

按 q 键或 ESC 键退出（点窗口右上角 X 也可以）。

运行方式（在项目根目录）：
    python vision/task_session.py
"""

import csv
import math
import os
import time
from collections import deque

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

MODEL_PATH = "vision/models/pose_landmarker_full.task"
LOG_PATH = "logs/training_session.csv"

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

TASKS = [
    {"type": "raise", "side": "right", "hold": 2.0,
     "label": "TASK 1/3: Raise RIGHT hand 2s"},
    {"type": "raise", "side": "left", "hold": 2.0,
     "label": "TASK 2/3: Raise LEFT hand 2s"},
    {"type": "clap", "times": 5,
     "label": "TASK 3/3: Clap hands x5"},
]

latest_result = None
smoothed_lms = None


def point_reliable(lm):
    """画面内且置信度足够才可用；真正出画返回 False。"""
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
                # 出画：锁定最后可靠位置


def dist2d(p1, p2):
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


def hand_center(lms, side):
    idx = (L_WRIST, 17, 19, 21) if side == "L" else (R_WRIST, 18, 20, 22)
    x = sum(lms[i].x for i in idx) / 4
    y = sum(lms[i].y for i in idx) / 4
    return x, y


def raise_check(lms, side, was_raised):
    """举手判定（迟滞）。返回 (True/False/None, 提示)。None=出画不可靠。"""
    s_i = R_SHOULDER if side == "right" else L_SHOULDER
    e_i = 14 if side == "right" else 13
    w_i = R_WRIST if side == "right" else L_WRIST
    s, e, w = lms[s_i], lms[e_i], lms[w_i]
    if not (point_reliable(s) and point_reliable(w)):
        return None, "Keep arms in frame!"
    raised = w.y < s.y - (0.01 if was_raised else 0.06)
    return raised, None


def clap_check(lms, was_contact):
    """拍手判定（掌心距/肩宽，迟滞 0.55/0.80，高于胸线）。"""
    lw, rw = lms[L_WRIST], lms[R_WRIST]
    ls, rs = lms[L_SHOULDER], lms[R_SHOULDER]
    lh, rh = lms[L_HIP], lms[R_HIP]
    if not (point_reliable(lw) and point_reliable(rw) and
            point_reliable(ls) and point_reliable(rs)):
        return None, 0.0
    lcx, lcy = hand_center(lms, "L")
    rcx, rcy = hand_center(lms, "R")
    ratio = math.hypot(lcx - rcx, lcy - rcy) / max(dist2d(ls, rs), 1e-6)
    if point_reliable(lh) and point_reliable(rh):
        chest_y = (ls.y + rs.y + lh.y + rh.y) / 4
    else:
        chest_y = max(ls.y, rs.y) + 0.15
    above = lcy < chest_y and rcy < chest_y
    if was_contact:
        return (above and ratio < 0.80), ratio
    return (above and ratio < 0.55), ratio


def draw_pos(lm, w, h):
    return int((1 - lm.x) * w), int(lm.y * h)


def fast_close_enough(hist, now):
    """真拍手的'指纹'：合拢前0.35秒内比例骤降（快速相向撞击）。
    缓慢漂近的手（如普通手势、整理动作）不满足此特征，不计入。
    hist: [(时间, ratio), ...] 近期比例历史。"""
    recent = [(t, r) for t, r in hist if now - t <= 0.35]
    if len(recent) < 2:
        return False
    r_max = max(r for _, r in recent)
    t_max = max(t for t, r in recent if r == r_max)
    drop = r_max - recent[-1][1]
    dt = max(now - t_max, 0.03)
    return drop >= 0.2 and drop / dt >= 1.5


class StableText:
    """屏幕提示文字稳定器：新消息须持续出现 hold 秒才上屏，
    滤掉状态逐帧抖动造成的文字闪烁。"""

    def __init__(self, hold=0.25):
        self.msg = ""
        self.cand = None
        self.cand_t = 0.0
        self.hold = hold

    def update(self, candidate, now):
        if candidate == self.msg:
            self.cand = None
            return self.msg
        if candidate != self.cand:
            self.cand, self.cand_t = candidate, now
        elif now - self.cand_t >= self.hold:
            self.msg, self.cand = candidate, None
        return self.msg


def draw_skeleton(frame, w, h):
    if not smoothed_lms:
        return
    for i, lm in enumerate(smoothed_lms):
        if i in HEAD_POINTS:
            cv2.circle(frame, draw_pos(lm, w, h), 3, (255, 255, 0), -1)
        elif i > 10:
            cv2.circle(frame, draw_pos(lm, w, h), 4, (0, 255, 0), -1)
    for a, b in POSE_CONNECTIONS:
        pa, pb = smoothed_lms[a], smoothed_lms[b]
        cv2.line(frame, draw_pos(pa, w, h), draw_pos(pb, w, h),
                 (0, 200, 255), 2)


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

    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(["任务", "开始", "结束", "用时秒", "结果", "备注"])

    print("=" * 50)
    print("星伴AI 训练任务原型")
    print("共 3 个任务：举右手2秒 -> 举左手2秒 -> 拍手5次")
    print("按 q 键退出")
    print("=" * 50)

    task_idx = 0            # 当前任务序号
    task_start = None       # 当前任务开始时刻
    # 举手任务状态
    disp = False            # 该侧手臂的稳定举起状态
    cnt = 0
    hold_start = None       # 开始持续举起的时间
    # 拍手任务状态
    contact_disp = False
    clap_cnt = 0
    cnt2 = 0
    done_until = 0.0        # 完成提示的截止时间
    # 拍手诊断：dip_cnt 记录比例跌破0.55的原始次数（去重0.3秒），
    # 与 clap_cnt 对比即可判断漏计/多计发生在哪一环
    diag_t, last_dip_t, dip_cnt = 0.0, 0.0, 0
    last_clap_time = 0.0        # 上次计数的时刻（快速连击的重新武装用）
    max_ratio_since = 0.0       # 上次计数后的最大比例（完全分开的重新武装用）
    ratio_hist = deque(maxlen=20)  # 近期比例历史（骤降检测用）
    stable2 = StableText()      # 屏幕提示稳定器
    session_rows = []

    fps, t_last = 0.0, time.time()

    while True:
        ok, frame_raw = cap.read()
        if not ok:
            print("错误：摄像头画面读取失败")
            break

        frame = cv2.flip(frame_raw, 1)
        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / max(now - t_last, 1e-6))
        t_last = now

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_raw)
        landmarker.detect_async(mp_image, int(now * 1000))

        h, w = frame.shape[:2]
        draw_skeleton(frame, w, h)

        overlay1 = "Press Q to quit"
        overlay2 = ""
        overlay3 = ""

        if task_idx < len(TASKS):
            task = TASKS[task_idx]
            if task_start is None:
                task_start = now
                print(f"[任务] {task['label']}")

            if smoothed_lms:
                if task["type"] == "raise":
                    raw, warn = raise_check(lms=smoothed_lms,
                                            side=task["side"],
                                            was_raised=disp)
                    if raw is None:
                        cnt = 0
                        overlay2 = warn or ""
                    else:
                        if raw == disp:
                            cnt = 0
                        else:
                            cnt += 1
                            if cnt >= 8:
                                disp, cnt = raw, 0
                        if disp:
                            if hold_start is None:
                                hold_start = now
                            held = now - hold_start
                            overlay2 = (f"holding {held:.1f} / "
                                        f"{task['hold']:.0f}s")
                            if held >= task["hold"]:
                                dur = now - task_start
                                print(f"[完成] {task['label']} 用时 {dur:.1f} 秒")
                                session_rows.append(
                                    [task["label"],
                                     time.strftime("%H:%M:%S",
                                                   time.localtime(task_start)),
                                     time.strftime("%H:%M:%S"),
                                     round(dur, 1), "完成", ""])
                                task_idx += 1
                                task_start = None
                                disp, cnt, hold_start = False, 0, None
                                done_until = now + 2.0
                        else:
                            hold_start = None
                            overlay2 = "Raise and HOLD the hand"
                else:  # clap
                    # 拍手是快动作：用未平滑的原始关键点判定。
                    # 平滑会削平快速拍击的比例深谷，导致漏计。
                    if latest_result and latest_result.pose_landmarks:
                        raw_lms = latest_result.pose_landmarks[0]
                    else:
                        raw_lms = smoothed_lms
                    raw, ratio = clap_check(raw_lms, contact_disp)
                    # 诊断：比例跌破0.55视为一次原始拍击信号（0.3秒去重）
                    if raw is not None and ratio < 0.55 and now - last_dip_t > 0.3:
                        dip_cnt += 1
                        last_dip_t = now
                        print(f"[dip#{dip_cnt}] ratio={ratio:.2f} "
                              f"已计{clap_cnt} disp={contact_disp}")
                    # 每0.5秒输出一次总体诊断
                    if now - diag_t > 0.5:
                        diag_t = now
                        print(f"[诊断] claps={clap_cnt} dips={dip_cnt} "
                              f"ratio={ratio:.2f} disp={contact_disp}")
                    if raw is None:
                        cnt2 = 0
                        overlay2 = "Keep arms in frame!"
                    else:
                        # 计数规则（三重防伪，支持快速连击）：
                        # 1) 跌破0.55进入合拢；2) 重置条件：分开过0.65
                        #    或距上次计数超过0.25秒；3) 合拢前0.35秒内
                        #    比例骤降（真拍手特征），缓慢漂近不计。
                        ratio_hist.append((now, ratio))
                        if ratio > max_ratio_since:
                            max_ratio_since = ratio
                        if raw != contact_disp:
                            if raw:
                                rearmed = (max_ratio_since >= 0.65 or
                                           now - last_clap_time >= 0.25)
                                if not rearmed:
                                    pass
                                elif fast_close_enough(ratio_hist, now):
                                    contact_disp = True
                                    clap_cnt += 1
                                    last_clap_time = now
                                    max_ratio_since = 0.0
                                    print(f"[进度] 拍手 {clap_cnt}/{task['times']}")
                                else:
                                    print(f"[拒绝] ratio={ratio:.2f} "
                                          f"合拢速度不足（非拍手动作）")
                            else:
                                contact_disp = False
                        overlay2 = f"claps {clap_cnt} / {task['times']}"
                        overlay3 = f"ratio {ratio:.2f}"
                        if clap_cnt >= task["times"]:
                            dur = now - task_start
                            print(f"[完成] {task['label']} 用时 {dur:.1f} 秒")
                            session_rows.append(
                                [task["label"],
                                 time.strftime("%H:%M:%S",
                                               time.localtime(task_start)),
                                 time.strftime("%H:%M:%S"),
                                 round(dur, 1), "完成",
                                 f"共{clap_cnt}次"])
                            task_idx += 1
                            task_start = None
                            contact_disp, clap_cnt, cnt2 = False, 0, 0
                            done_until = now + 2.0

            overlay1 = task["label"]
            if now < done_until:
                overlay2 = "WELL DONE!"
        else:
            overlay1 = "ALL DONE!"
            total = (session_rows[-1][3] if session_rows else 0)
            overlay2 = "Session complete - well done!"
            overlay3 = f"Check logs/training_session.csv"

        color1 = (0, 255, 0) if overlay1.startswith(("TASK", "ALL")) \
            else (255, 255, 255)
        # 提示类消息走稳定器：短暂闪现（<0.25秒）不上屏，消除闪烁
        if overlay2 in ("Keep arms in frame!", "Raise and HOLD the hand"):
            overlay2 = stable2.update(overlay2, now)
        cv2.putText(frame, overlay1, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color1, 2)
        cv2.putText(frame, overlay2, (10, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(frame, overlay3, (10, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, h - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)

        cv2.imshow("XingBanAI Training", frame)
        key = cv2.waitKey(1)
        if (key in (ord("q"), 27) or
                cv2.getWindowProperty("XingBanAI Training",
                                      cv2.WND_PROP_VISIBLE) < 1):
            if task_idx < len(TASKS) and task_start is not None:
                task = TASKS[task_idx]
                session_rows.append(
                    [task["label"],
                     time.strftime("%H:%M:%S",
                                   time.localtime(task_start)),
                     time.strftime("%H:%M:%S"),
                     round(now - task_start, 1), "未完成(中途退出)", ""])
            break

    if session_rows:
        with open(LOG_PATH, "a", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerows(session_rows)

    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()
    print(f"已退出。本次训练记录（{'已' if session_rows else '未'}写入）：")
    for row in session_rows:
        print("   ", row)
    print(f"完整记录保存在 {LOG_PATH}")


if __name__ == "__main__":
    main()
