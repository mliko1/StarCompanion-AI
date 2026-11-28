# -*- coding: utf-8 -*-
"""摄像头姿态标注采样：产出可用于 evaluate_recognition.py 的真实 JSONL 数据集。

用法（项目根目录执行）：
    python scripts/collect_pose_dataset.py --output data/labeled/pose_eval.jsonl
    python scripts/collect_pose_dataset.py --actions raise_right,raise_left,touch_head
    python scripts/collect_pose_dataset.py --validate data/labeled/pose_eval.jsonl

按键：
    SPACE  保存当前帧（按当前标签）
    N / P  下一个 / 上一个动作标签
    0      切到"无动作"负样本
    A      自动采样开关（每 --interval 秒保存一帧）
    Q      退出

每条样本记录 MediaPipe Pose 33 点、可选 21 点手部关键点、人工标签，
以及当时的模型预测和置信度，方便后续做人工复核与 P/R/F1 评估。
"""

import argparse
import datetime
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _path in (ROOT, os.path.join(ROOT, "vision")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import cv2  # noqa: E402

from action_engine import detect_actions_with_scores, load_actions  # noqa: E402
from pose_utils import point_reliable  # noqa: E402
from services.camera_service import camera  # noqa: E402

DEFAULT_OUTPUT = os.path.join(ROOT, "data", "labeled", "pose_eval.jsonl")
DEFAULT_ACTIONS = [
    "raise_right", "raise_left", "both_hands_up", "clap",
    "wave_right", "wave_left", "touch_head", "touch_belly",
    "squat", "bend_forward", "nod_down", "stand_up",
]


def action_ids():
    return [a["id"] for a in load_actions()]


def normalize_points(lms):
    """关键点 -> [[x, y, z, visibility], ...]。"""
    return [[round(float(p.x), 5), round(float(p.y), 5),
             round(float(p.z), 5), round(float(getattr(p, "visibility", 1.0)), 3)]
            for p in lms]


def hands_to_dict(hands):
    out = {}
    if not hands:
        return out
    for side, pts in hands.items():
        if pts and len(pts) >= 21:
            out[side] = normalize_points(pts[:21])
    return out


def pose_to_dict(lms):
    if not lms:
        return {}
    pts = normalize_points(lms)
    return {str(i): pts[i] for i in range(33)}


def append_sample(path, sample):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(sample, ensure_ascii=False) + "\n")


def validate(path):
    known = set(action_ids())
    counts = {}
    total = 0
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"第 {lineno} 行不是合法 JSON: {e}")
            if "landmarks" not in obj or len(obj["landmarks"]) != 33:
                raise ValueError(f"第 {lineno} 行缺少 33 个姿态关键点")
            labels = obj.get("labels")
            if not isinstance(labels, list):
                raise ValueError(f"第 {lineno} 行 labels 必须是数组")
            unknown = set(labels) - known
            if unknown:
                raise ValueError(f"第 {lineno} 行含未知动作 id: {sorted(unknown)}")
            total += 1
            for label in labels or ["<negative>"]:
                counts[label] = counts.get(label, 0) + 1
    print(f"校验通过：{total} 条样本")
    for label in sorted(counts):
        print(f"  {label}: {counts[label]}")
    return total, counts


def _draw_overlay(frame, label, labels, samples, predicted, confident,
                  auto, reliable):
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, 118), (245, 248, 252), -1)
    lines = [
        f"Label: {label or 'NONE'} | Samples: {samples} | Auto: {'ON' if auto else 'OFF'}",
        f"Pred: {', '.join(predicted) if predicted else '-'}",
        f"Confidence: {confident:.3f} | Pose: {'OK' if reliable else 'MISSING'}",
        "SPACE save | N/P label | 0 negative | A auto | Q quit",
    ]
    for i, text in enumerate(lines):
        cv2.putText(frame, text, (14, 24 + i * 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62, (20, 40, 70), 2, cv2.LINE_AA)
    cv2.putText(frame, "Actions: " + "/".join(labels[:6]),
                (14, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (70, 90, 120), 1,
                cv2.LINE_AA)


def collect(output, labels, interval, min_visibility):
    started = camera.start()
    if not started.get("ok"):
        print(f"摄像头启动失败：{started.get('msg')}")
        return 1

    idx = 0
    samples = 0
    auto = False
    last_save = 0.0
    last_frame_id = None
    try:
        while True:
            frame = camera.get_pose_frame()
            if frame is None:
                time.sleep(0.05)
                continue
            det = camera.get_detection()
            lms = det["raw"]
            hands = det["hands"]
            reliable = bool(lms) and all(
                point_reliable(p, min_visibility) for p in lms)
            predicted, scores = ([], {})
            if lms:
                try:
                    predicted, scores = detect_actions_with_scores(
                        lms, hands=hands)
                except Exception as e:
                    print(f"[warn] 预测失败: {e}")
            label = labels[idx] if labels else ""
            confident = scores.get(label, 0.0) if label else 0.0
            _draw_overlay(frame, label, labels, samples, predicted,
                          confident, auto, reliable)
            cv2.imshow("Collect labeled poses", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key in (ord("n"),):
                idx = (idx + 1) % len(labels) if labels else 0
            elif key in (ord("p"),):
                idx = (idx - 1) % len(labels) if labels else 0
            elif key == ord("0"):
                if "" not in labels:
                    labels.append("")
                idx = labels.index("")
            elif key == ord("a"):
                auto = not auto
                print(f"自动采样：{'开启' if auto else '关闭'}")

            should_save = key == 32 or (
                auto and time.time() - last_save >= interval)
            if should_save and reliable and det["frame_id"] != last_frame_id:
                row = {
                    "source": "camera",
                    "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                    "frame_id": det["frame_id"],
                    "labels": [label] if label else [],
                    "landmarks": pose_to_dict(lms),
                    "hands": hands_to_dict(hands),
                    "predicted": predicted,
                    "confidence": round(confident, 3),
                }
                append_sample(output, row)
                samples += 1
                last_save = time.time()
                last_frame_id = det["frame_id"]
                print(f"已保存 #{samples}: {label or '<negative>'} "
                      f"(frame {det['frame_id']})")
            elif should_save and not reliable:
                print("当前姿态不可靠，未保存")
    finally:
        cv2.destroyAllWindows()
        camera.stop()
    print(f"完成：{samples} 条样本 -> {output}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--actions", help="逗号分隔的动作 id 列表")
    parser.add_argument("--interval", type=float, default=0.8,
                        help="自动采样间隔秒数")
    parser.add_argument("--min-visibility", type=float, default=0.5)
    parser.add_argument("--list-actions", action="store_true")
    parser.add_argument("--validate", metavar="JSONL",
                        help="只校验已有数据集，不打开摄像头")
    args = parser.parse_args()

    if args.list_actions:
        print("\n".join(action_ids()))
        return 0
    if args.validate:
        try:
            validate(args.validate)
            return 0
        except ValueError as e:
            print(f"校验失败：{e}")
            return 1

    if args.actions:
        labels = [x.strip() for x in args.actions.split(",") if x.strip()]
        known = set(action_ids())
        unknown = [x for x in labels if x not in known]
        if unknown:
            print(f"未知动作 id：{unknown}")
            return 1
    else:
        labels = list(DEFAULT_ACTIONS)
    return collect(args.output, labels, args.interval, args.min_visibility)


if __name__ == "__main__":
    raise SystemExit(main())
