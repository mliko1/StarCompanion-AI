# -*- coding: utf-8 -*-
"""
星伴AI 动作识别评估脚本（统一测试机制，无需摄像头）。

两级测试：
1. 核心动作精细评估（举手/拍手）：构造正样本 + 易混淆负样本，
   逐动作统计 TP/FP/FN，输出 Precision / Recall / F1；
2. 全量动作回归：对 test_action_engine.SAMPLE 里每个代表性动作，
   校验"标准姿态应检出、中性站姿不应误报"。

指标口径（诚实标注）：
- 本脚本为「模拟关键点测试」：关键点为手工构造，非真实视频/摄像头采集；
- 识别延迟、真实视频/摄像头测试不在此脚本覆盖（需真机数据），如实留空。

运行（项目根目录）：python tests/eval_action_engine.py
"""

import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vision"))
sys.path.insert(0, os.path.dirname(__file__))

from action_engine import load_actions, detect_actions  # noqa: E402
from test_action_engine import NEUTRAL, make_pose, SAMPLE  # noqa: E402

ACTIONS = load_actions()
NAME = {a["id"]: a["name"] for a in ACTIONS}

METRIC_DIR = os.path.join(os.path.dirname(__file__), "metrics")
METRIC_CSV = os.path.join(METRIC_DIR, "action_metrics.csv")

TEST_ENV = "Windows CPU / Python 3.12 / 模拟关键点（无真实视频）"

# ---------------------------------------------------------------------------
# 一、核心动作精细评估数据集
# overrides 为相对 NEUTRAL 的关键点位移（key 为整数索引），None=中性站姿。
# 正样本 = 该动作应被检出；负样本 = 该动作不应被检出（含易混淆姿态）。
# ---------------------------------------------------------------------------
DATASET = {
    "raise_right": {
        "positives": [
            {14: (0.40, 0.20), 16: (0.40, 0.06),
             18: (0.38, 0.07), 20: (0.40, 0.08), 22: (0.42, 0.07)},
            {14: (0.40, 0.24), 16: (0.40, 0.16),
             18: (0.38, 0.17), 20: (0.40, 0.18), 22: (0.42, 0.17)},
            {14: (0.40, 0.26), 16: (0.40, 0.18),
             18: (0.38, 0.19), 20: (0.40, 0.20), 22: (0.42, 0.19)},
        ],
        "negatives": [
            None,  # 中性站姿
            {13: (0.60, 0.22), 15: (0.60, 0.10),
             17: (0.62, 0.11), 19: (0.60, 0.12), 21: (0.58, 0.11)},  # 举左手
            {14: (0.62, 0.26), 16: (0.44, 0.16),
             18: (0.42, 0.17), 20: (0.44, 0.18), 22: (0.46, 0.17)},  # 敬礼(曲肘)
            {14: (0.40, 0.32), 16: (0.40, 0.30)},  # 手腕略高但未达门槛
            {14: (0.63, 0.24), 16: (0.50, 0.05),
             18: (0.48, 0.06), 20: (0.50, 0.07), 22: (0.52, 0.06)},  # 摸头(曲肘)
        ],
    },
    "raise_left": {
        "positives": [
            {13: (0.60, 0.20), 15: (0.60, 0.06),
             17: (0.62, 0.07), 19: (0.60, 0.08), 21: (0.58, 0.07)},
            {13: (0.60, 0.24), 15: (0.60, 0.16),
             17: (0.62, 0.17), 19: (0.60, 0.18), 21: (0.58, 0.17)},
            {13: (0.60, 0.26), 15: (0.60, 0.18),
             17: (0.62, 0.19), 19: (0.60, 0.20), 21: (0.58, 0.19)},
        ],
        "negatives": [
            None,  # 中性站姿
            {14: (0.40, 0.20), 16: (0.40, 0.06),
             18: (0.38, 0.07), 20: (0.40, 0.08), 22: (0.42, 0.07)},  # 举右手
            {13: (0.38, 0.26), 15: (0.56, 0.16),
             17: (0.58, 0.17), 19: (0.56, 0.18), 21: (0.54, 0.17)},  # 敬礼(曲肘)
            {13: (0.60, 0.32), 15: (0.60, 0.30)},  # 手腕略高但未达门槛
        ],
    },
    "both_hands_up": {
        "positives": [
            {13: (0.60, 0.20), 15: (0.60, 0.06),
             17: (0.62, 0.07), 19: (0.60, 0.08), 21: (0.58, 0.07),
             14: (0.40, 0.20), 16: (0.40, 0.06),
             18: (0.38, 0.07), 20: (0.40, 0.08), 22: (0.42, 0.07)},
        ],
        "negatives": [
            None,  # 中性站姿
            {14: (0.40, 0.20), 16: (0.40, 0.06),
             18: (0.38, 0.07), 20: (0.40, 0.08), 22: (0.42, 0.07)},  # 单举右手
            {13: (0.60, 0.20), 15: (0.60, 0.06),
             17: (0.62, 0.07), 19: (0.60, 0.08), 21: (0.58, 0.07)},  # 单举左手
        ],
    },
    "clap": {
        "positives": [
            {13: (0.62, 0.42), 15: (0.55, 0.30),
             17: (0.56, 0.32), 19: (0.55, 0.33), 21: (0.54, 0.32),
             14: (0.38, 0.42), 16: (0.45, 0.30),
             18: (0.44, 0.32), 20: (0.45, 0.33), 22: (0.46, 0.32)},
            {13: (0.60, 0.42), 15: (0.52, 0.30),
             17: (0.53, 0.32), 19: (0.52, 0.33), 21: (0.51, 0.32),
             14: (0.40, 0.42), 16: (0.48, 0.30),
             18: (0.47, 0.32), 20: (0.48, 0.33), 22: (0.49, 0.32)},
        ],
        "negatives": [
            None,  # 中性站姿
            # 双手上举（高于胸线但掌心距大）
            {13: (0.68, 0.22), 15: (0.76, 0.12),
             14: (0.32, 0.22), 16: (0.24, 0.12),
             17: (0.77, 0.13), 19: (0.76, 0.14), 21: (0.75, 0.13),
             18: (0.23, 0.13), 20: (0.24, 0.14), 22: (0.25, 0.13)},
            # 手放腿上（低于胸线，胸线条件应排除）
            {15: (0.58, 0.72), 16: (0.42, 0.72),
             17: (0.59, 0.73), 19: (0.58, 0.74), 21: (0.57, 0.73),
             18: (0.41, 0.73), 20: (0.42, 0.74), 22: (0.43, 0.73)},
        ],
    },
}


def _metrics(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    return precision, recall, f1


def eval_core():
    """核心动作精细评估。"""
    rows = []
    for action_id, spec in DATASET.items():
        tp = sum(1 for ov in spec["positives"]
                 if action_id in detect_actions(make_pose(ov)))
        fn = len(spec["positives"]) - tp
        fp = sum(1 for ov in spec["negatives"]
                 if action_id in detect_actions(make_pose(ov)))
        p, r, f1 = _metrics(tp, fp, fn)
        rows.append({
            "scope": "core", "action_id": action_id,
            "name": NAME.get(action_id, action_id),
            "pos": len(spec["positives"]), "neg": len(spec["negatives"]),
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
            "test_level": "simulation", "latency_sec": "",
        })
    return rows


def eval_full_regression():
    """全量回归：标准姿态应检出、中性站姿不应误报。"""
    rows = []
    neutral_hits = set(detect_actions(make_pose()))
    for action_id, spec in SAMPLE.items():
        tp = 1 if action_id in detect_actions(make_pose(spec["pose"])) else 0
        fn = 1 - tp
        fp = 1 if action_id in neutral_hits else 0
        p, r, f1 = _metrics(tp, fp, fn)
        rows.append({
            "scope": "full", "action_id": action_id,
            "name": NAME.get(action_id, action_id),
            "pos": 1, "neg": 1, "tp": tp, "fp": fp, "fn": fn,
            "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
            "test_level": "simulation", "latency_sec": "",
        })
    return rows


def _print_table(title, rows):
    print(title)
    header = (f"{'动作':<14} {'TP':>3} {'FP':>3} {'FN':>3} "
              f"{'Precision':>9} {'Recall':>7} {'F1':>7}")
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['name']:<14} {r['tp']:>3} {r['fp']:>3} {r['fn']:>3} "
              f"{r['precision']:>9.4f} {r['recall']:>7.4f} {r['f1']:>7.4f}")
    print()


def run():
    core_rows = eval_core()
    full_rows = eval_full_regression()

    print("=" * 62)
    print("星伴AI 动作识别评估（模拟关键点测试）")
    print(f"环境：{TEST_ENV}")
    print("=" * 62)
    _print_table("【一、核心动作精细评估】", core_rows)
    _print_table("【二、全量动作回归】", full_rows)

    # 写 CSV 记录表
    os.makedirs(METRIC_DIR, exist_ok=True)
    fieldnames = ["scope", "action_id", "name", "pos", "neg",
                  "tp", "fp", "fn", "precision", "recall", "f1",
                  "test_level", "latency_sec"]
    all_rows = core_rows + full_rows
    with open(METRIC_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_rows)
    print(f"指标已写入: {METRIC_CSV}")

    # 断言：核心动作召回 100% 且精度 >= 0.6；全量回归召回 100%
    for r in core_rows:
        assert r["recall"] == 1.0, f"{r['name']} 漏检（召回 {r['recall']}）"
        assert r["precision"] >= 0.6, \
            f"{r['name']} 误报过多（精度 {r['precision']}）"
    for r in full_rows:
        assert r["recall"] == 1.0, f"{r['name']} 标准姿态未检出"
    print("评估断言全部通过（核心动作精度>=0.6 且召回100%；全量回归召回100%）")
    print("说明：本结果仅代表「模拟关键点测试通过」，不代表真实视频/摄像头测试。")


if __name__ == "__main__":
    run()
