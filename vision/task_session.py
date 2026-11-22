# -*- coding: utf-8 -*-
"""
星伴AI 第二阶段第4步：训练任务流程原型
系统依次下发 3 个训练任务（举右手、举左手、拍手5次），
视觉判定完成情况，记录每个任务的用时和结果到 logs/training_session.csv。

这演示了"任务下发 -> 视觉判定 -> 量化记录"的完整闭环。

（P0 消重：几何/可靠性/平滑复用 pose_utils，举手/拍手判定与计数复用
  action_base 的 raise_check / clap_check / RaiseTracker / ClapCounter）

按 q 键或 ESC 键退出（点窗口右上角 X 也可以）。

运行方式（在项目根目录）：
    python vision/task_session.py
"""

import csv
import os
import time

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

from pose_utils import (LandmarkSmoother, draw_pos, HEAD_POINTS,
                        POSE_CONNECTIONS)
from action_base import raise_check, clap_check, RaiseTracker, ClapCounter

MODEL_PATH = "vision/models/pose_landmarker_full.task"
LOG_PATH = "logs/training_session.csv"

SMOOTH_ALPHA = 0.30
EDGE_MARGIN = 0.03

TASKS = [
    {"type": "raise", "side": "right", "hold": 2.0,
     "label": "TASK 1/3: Raise RIGHT hand 2s"},
    {"type": "raise", "side": "left", "hold": 2.0,
     "label": "TASK 2/3: Raise LEFT hand 2s"},
    {"type": "clap", "times": 5,
     "label": "TASK 3/3: Clap hands x5"},
]

latest_result = None
smoother = LandmarkSmoother(
    alpha=SMOOTH_ALPHA, edge_alpha=0.12, min_visibility=0.3,
    edge_margin=EDGE_MARGIN * 2)


def on_result(result, _image, _ts_ms):
    global latest_result
    latest_result = result
    if result.pose_landmarks:
        smoother.update(result.pose_landmarks[0])


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
    if not smoother.smoothed:
        return
    for i, lm in enumerate(smoother.smoothed):
        if i in HEAD_POINTS:
            cv2.circle(frame, draw_pos(lm, w, h), 3, (255, 255, 0), -1)
        elif i > 10:
            cv2.circle(frame, draw_pos(lm, w, h), 4, (0, 255, 0), -1)
    for a, b in POSE_CONNECTIONS:
        pa, pb = smoother.smoothed[a], smoother.smoothed[b]
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
    hold_start = None       # 开始持续举起的时间
    done_until = 0.0        # 完成提示的截止时间
    # 统一核心：举手防抖 + 拍手计数（含骤降防伪）
    raise_track = RaiseTracker(8)
    counter = ClapCounter()
    # 拍手诊断：dip_cnt 记录比例跌破0.55的原始次数（去重0.3秒），
    # 与 counter.count 对比即可判断漏计/多计发生在哪一环
    diag_t, last_dip_t, dip_cnt = 0.0, 0.0, 0
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
        smoothed_lms = smoother.smoothed

        if task_idx < len(TASKS):
            task = TASKS[task_idx]
            if task_start is None:
                task_start = now
                print(f"[任务] {task['label']}")

            if smoothed_lms:
                if task["type"] == "raise":
                    raw, _angle = raise_check(smoothed_lms, task["side"],
                                              raise_track.disp)
                    disp = raise_track.update(raw)
                    if raw is None:
                        overlay2 = "Keep arms in frame!"
                    elif disp:
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
                            raise_track.reset()
                            hold_start = None
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
                    raw, ratio = clap_check(raw_lms, counter.contact)
                    # 诊断：比例跌破0.55视为一次原始拍击信号（0.3秒去重）
                    if raw is not None and ratio < 0.55 and \
                            now - last_dip_t > 0.3:
                        dip_cnt += 1
                        last_dip_t = now
                        print(f"[dip#{dip_cnt}] ratio={ratio:.2f} "
                              f"已计{counter.count} disp={counter.contact}")
                    # 每0.5秒输出一次总体诊断
                    if now - diag_t > 0.5:
                        diag_t = now
                        print(f"[诊断] claps={counter.count} dips={dip_cnt} "
                              f"ratio={ratio:.2f} disp={counter.contact}")
                    if raw is None:
                        counter.contact = False
                        overlay2 = "Keep arms in frame!"
                    else:
                        # 计数规则由 ClapCounter 统一封装：
                        # 单帧计数 + 重新武装 + 骤降防伪（缓慢漂近不计）
                        if counter.update(ratio, raw, now):
                            print(f"[进度] 拍手 {counter.count}/{task['times']}")
                        overlay2 = f"claps {counter.count} / {task['times']}"
                        overlay3 = f"ratio {ratio:.2f}"
                        if counter.count >= task["times"]:
                            dur = now - task_start
                            print(f"[完成] {task['label']} 用时 {dur:.1f} 秒")
                            session_rows.append(
                                [task["label"],
                                 time.strftime("%H:%M:%S",
                                               time.localtime(task_start)),
                                 time.strftime("%H:%M:%S"),
                                 round(dur, 1), "完成",
                                 f"共{counter.count}次"])
                            task_idx += 1
                            task_start = None
                            counter.reset()
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
