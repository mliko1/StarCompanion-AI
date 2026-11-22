# -*- coding: utf-8 -*-
"""
星伴AI 真机标定数据采集脚本（为个体化幅度/速度阈值标定提供数据）。

用途：
    个体化适应需要知道"这个孩子的正常动作幅度/速度"，才能把固定阈值
    缩放成他的个人标准。本脚本在孩子做动作时，实时采集动作引擎同源的
    原子特征数值，退出时输出统计（样本数 / 中位数 / P25 / P75 / 峰值），
    供标定 amplitude_scale（幅度）与 speed_scale（速度）参考值。

支持动作（命令行 --action）：
    raise_right / raise_left  采集 dy_ratio（手腕高出肩的肩宽比）+ angle（肘夹角）
    clap                      采集 ratio（掌心距/肩宽）

标定建议（采集后人工换算，不自动下结论）：
    - 举手幅度：amplitude_scale ≈ 孩子稳定 dy_ratio 峰值 / 标准门槛 0.1；
      例如孩子只能到 0.06，则 amplitude_scale ≈ 0.6（仅作参考，需多次+人工审核）。
    - 拍手速度：观察 ratio 序列的骤降幅度/速度，结合固定 FAST_DROP/FAST_SPEED
      换算 speed_scale。

运行（项目根目录）：
    python vision/collect_calibration.py --action raise_right
按 s 键保存一帧样本，按 q 键退出并输出统计 + 写入 CSV。
"""

import argparse
import csv
import os
import statistics
import time

import cv2

from pose_utils import (angle_at, dist2d, hand_center,
                        L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW,
                        L_WRIST, R_WRIST)

MODEL_PATH = "vision/models/pose_landmarker_full.task"
OUT_DIR = "data/calibration"

_parser = argparse.ArgumentParser(description="星伴AI 标定数据采集")
_parser.add_argument("--action", default="raise_right",
                     choices=["raise_right", "raise_left", "clap"],
                     help="要标定的动作")
_args, _ = _parser.parse_known_args()
ACTION = _args.action


def extract_features(lms, action):
    """从原始关键点提取该动作的核心特征 dict（与动作引擎同源）。"""
    if action in ("raise_right", "raise_left"):
        right = (action == "raise_right")
        s_i = R_SHOULDER if right else L_SHOULDER
        e_i = R_ELBOW if right else L_ELBOW
        w_i = R_WRIST if right else L_WRIST
        shoulder_w = dist2d(lms[L_SHOULDER], lms[R_SHOULDER]) or 1e-6
        dy_ratio = (lms[s_i].y - lms[w_i].y) / shoulder_w
        angle = angle_at(lms[s_i], lms[e_i], lms[w_i])
        return {"dy_ratio": round(dy_ratio, 4), "angle": round(angle, 1)}
    if action == "clap":
        lcx, lcy = hand_center(lms, "L")
        rcx, rcy = hand_center(lms, "R")
        shoulder = dist2d(lms[L_SHOULDER], lms[R_SHOULDER]) or 1e-6
        ratio = ((lcx - rcx) ** 2 + (lcy - rcy) ** 2) ** 0.5 / shoulder
        return {"ratio": round(ratio, 4)}
    return {}


def _quantile(values, q):
    s = sorted(values)
    if not s:
        return None
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def summarize(samples):
    """对一组特征 dict 逐列统计。"""
    keys = list(samples[0].keys()) if samples else []
    out = {}
    for k in keys:
        vals = [s[k] for s in samples if k in s]
        out[k] = {
            "n": len(vals),
            "median": round(statistics.median(vals), 4) if vals else None,
            "p25": round(_quantile(vals, 0.25), 4) if vals else None,
            "p75": round(_quantile(vals, 0.75), 4) if vals else None,
            "max": round(max(vals), 4) if vals else None,
        }
    return out


def main():
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python import vision

    latest = {"result": None}

    def on_result(result, _img, _ts):
        latest["result"] = result

    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH,
                                 delegate=BaseOptions.Delegate.CPU),
        running_mode=vision.RunningMode.LIVE_STREAM,
        min_pose_detection_confidence=0.6,
        min_tracking_confidence=0.7,
        result_callback=on_result,
    )
    landmarker = vision.PoseLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("DirectShow 接口打开失败，尝试 MSMF 接口...")
        cap = cv2.VideoCapture(0, cv2.CAP_MSMF)
    if not cap.isOpened():
        print("错误：无法打开摄像头")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    samples = []
    cur_feat = {}
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 56)
    print(f"标定采集：{ACTION}")
    print("按 s 保存一帧样本，按 q 退出并输出统计")
    print("=" * 56)

    fps, t_last = 0.0, time.time()
    while True:
        ok, frame_raw = cap.read()
        if not ok:
            print("错误：摄像头画面读取失败")
            break
        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / max(now - t_last, 1e-6))
        t_last = now

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_raw)
        landmarker.detect_async(mp_image, int(now * 1000))

        pr = latest["result"]
        cur_feat = {}
        if pr and pr.pose_landmarks:
            # 用原始关键点（不平滑），保留真实幅度/速度
            cur_feat = extract_features(pr.pose_landmarks[0], ACTION)

        frame = cv2.flip(frame_raw, 1)
        y = 30
        cv2.putText(frame, f"CALIBRATE: {ACTION}  samples={len(samples)}",
                    (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 220, 0), 2)
        y += 30
        for k, v in cur_feat.items():
            cv2.putText(frame, f"{k} = {v}", (10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            y += 26
        cv2.putText(frame, "s=save sample  q=quit", (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, frame.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)

        cv2.imshow("XingBanAI Calibration", frame)
        key = cv2.waitKey(1)
        if key == ord("s"):
            if cur_feat:
                samples.append(cur_feat)
                print(f"[样本#{len(samples)}] {cur_feat}")
            else:
                print("[忽略] 当前无关键点")
        elif key in (ord("q"), 27) or cv2.getWindowProperty(
                "XingBanAI Calibration", cv2.WND_PROP_VISIBLE) < 1:
            break

    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()

    if not samples:
        print("未采集到样本，退出。")
        return

    stats = summarize(samples)
    csv_path = os.path.join(OUT_DIR, f"{ACTION}_features.csv")
    keys = list(samples[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["sample_id"] + keys)
        for i, s in enumerate(samples, 1):
            w.writerow([i] + [s.get(k, "") for k in keys])

    print("\n" + "=" * 56)
    print(f"{ACTION} 标定统计（共 {len(samples)} 个样本）")
    print("=" * 56)
    for k, st in stats.items():
        print(f"{k}: 中位数={st['median']}  P25={st['p25']}  "
              f"P75={st['p75']}  峰值={st['max']}")
    print(f"\n样本明细已写入: {csv_path}")
    print("标定建议：结合多次训练 + 人工审核，换算 amplitude_scale / speed_scale，")
    print("再通过个体化档案写入（如 POST /api/personalization/confirm_hand 确认惯用手，")
    print("数值型参数由训练记录逐步收敛）。")


if __name__ == "__main__":
    main()
