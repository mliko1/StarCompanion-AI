# -*- coding: utf-8 -*-
"""动作识别量化评估：分动作 Precision / Recall / F1 + 交叉误报矩阵。

两种数据：
1. 内置合成样本（默认）：来自 tests/test_action_engine.py 的标注姿态，
   用于回归检测规则是否被改动破坏；
2. 真实标注 JSONL：每行
   {"landmarks": {idx:[x,y,z,visibility]}, "hands": {"L":[[x,y,z,vis],...]}, "labels": ["动作id"]}。
   labels 可为空数组；landmarks 为 33 个 MediaPipe Pose 关键点（索引 0~32）；
   hands 可选，含 21 点手部关键点时会自动参与规则判定。

用法：
    python tests/evaluate_recognition.py
    python tests/evaluate_recognition.py --dataset data/labeled/pose_eval.jsonl

输出：
    logs/recognition_eval.csv       每帧预测与命中情况
    docs/recognition_eval.md        分动作指标与汇总
"""

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vision"))

from action_engine import Pt, detect_actions  # noqa: E402

DEFAULT_DATASET = "builtin"
CSV_PATH = os.path.join(ROOT, "logs", "recognition_eval.csv")
MD_PATH = os.path.join(ROOT, "docs", "recognition_eval.md")


def builtin_dataset():
    """从动作单测的合成标注样本构造评估数据（非真实儿童数据）。"""
    tests_dir = os.path.join(ROOT, "tests")
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    import test_action_engine as fixtures  # noqa: E402
    rows = []
    for name, spec in fixtures.SAMPLE.items():
        pose = dict(fixtures.NEUTRAL)
        pose.update(spec["pose"])
        rows.append({
            "source": f"builtin:{name}",
            "landmarks": {str(i): list(pose[i]) for i in range(33)},
            "labels": [name],
        })
    rows.append({
        "source": "builtin:neutral",
        "landmarks": {str(i): list(fixtures.NEUTRAL[i]) for i in range(33)},
        "labels": ["stand_up", "arms_down"],
    })
    return rows


def load_dataset(path):
    if not path or path == DEFAULT_DATASET:
        return builtin_dataset(), "内置合成标注样本"
    rows = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            rows.append({
                "source": obj.get("source", f"jsonl:{lineno}"),
                "landmarks": obj["landmarks"],
                "hands": obj.get("hands") or {},
                "labels": list(obj.get("labels") or []),
            })
    return rows, path


def to_landmarks(raw):
    out = []
    for i in range(33):
        v = raw[str(i)] if str(i) in raw else raw[i]
        v = list(v)
        if len(v) == 2:
            v += [0.0, 1.0]
        elif len(v) == 3:
            v += [1.0]
        out.append(Pt(float(v[0]), float(v[1]), float(v[2]), float(v[3])))
    return out


def to_hands(raw):
    """{'L': [[x,y,z,vis], ...], 'R': ...} -> {'L': [Pt...], 'R': [Pt...]}。"""
    out = {}
    for side, pts in (raw or {}).items():
        converted = []
        for p in pts:
            p = list(p)
            if len(p) == 2:
                p += [0.0, 1.0]
            elif len(p) == 3:
                p += [1.0]
            converted.append(Pt(float(p[0]), float(p[1]),
                                float(p[2]), float(p[3])))
        out[side] = converted
    return out


def evaluate(rows):
    per_action = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    crosstalk = Counter()
    frame_rows = []
    for row in rows:
        lms = to_landmarks(row["landmarks"])
        hands = to_hands(row.get("hands"))
        predicted = set(detect_actions(lms, hands=hands))
        labels = set(row["labels"])
        for aid in labels & predicted:
            per_action[aid]["tp"] += 1
        for aid in labels - predicted:
            per_action[aid]["fn"] += 1
        for aid in predicted - labels:
            per_action[aid]["fp"] += 1
            if labels:
                for truth in labels:
                    crosstalk[(truth, aid)] += 1
        frame_rows.append({
            "source": row["source"],
            "labels": "|".join(sorted(labels)),
            "predicted": "|".join(sorted(predicted)),
            "tp": "|".join(sorted(labels & predicted)),
            "fn": "|".join(sorted(labels - predicted)),
            "fp": "|".join(sorted(predicted - labels)),
        })
    return per_action, crosstalk, frame_rows


def prf(counts):
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


def summarise(per_action):
    totals = {"tp": 0, "fp": 0, "fn": 0}
    for c in per_action.values():
        for k in totals:
            totals[k] += c[k]
    micro = prf(totals)
    macro = tuple(sum(prf(c)[i] for c in per_action.values()) /
                  len(per_action) if per_action else 0.0 for i in range(3))
    return totals, micro, macro


def write_outputs(per_action, crosstalk, frame_rows, source_name):
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(MD_PATH), exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=["source", "labels", "predicted", "tp", "fn", "fp"])
        writer.writeheader()
        writer.writerows(frame_rows)

    totals, micro, macro = summarise(per_action)
    lines = [
        "# 动作识别量化评估",
        "",
        f"- 数据来源：{source_name}",
        f"- 标注帧数：{len(frame_rows)}",
        f"- 口径：逐帧动作 id 集合对比；多动作标签按集合计算 TP/FP/FN。",
        "- 注意：内置样本是合成姿态（回归用），不是真实儿童数据；真实精度请用 JSONL 标注数据。",
        "",
        "## 汇总",
        "",
        "| 口径 | Precision | Recall | F1 |",
        "|---|---:|---:|---:|",
        "| Micro | {:.3f} | {:.3f} | {:.3f} |".format(*micro),
        "| Macro | {:.3f} | {:.3f} | {:.3f} |".format(*macro),
        "",
        f"合计：TP={totals['tp']}，FP={totals['fp']}，FN={totals['fn']}",
        "",
        "## 分动作指标",
        "",
        "| 动作 | 支持数 | TP | FP | FN | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for aid in sorted(per_action):
        c = per_action[aid]
        p, r, f1 = prf(c)
        support = c["tp"] + c["fn"]
        lines.append(
            "| {} | {} | {} | {} | {} | {:.3f} | {:.3f} | {:.3f} |".format(
                aid, support, c["tp"], c["fp"], c["fn"], p, r, f1))
    lines += ["", "## 交叉误报（真实标签 → 误报动作）", "",
              "| 真实动作 | 误报动作 | 次数 |", "|---|---|---:|"]
    for (truth, wrong), n in crosstalk.most_common(30):
        lines.append(f"| {truth} | {wrong} | {n} |")
    if not crosstalk:
        lines.append("| — | — | 0 |")
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return totals, micro, macro


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DEFAULT_DATASET,
                        help="'builtin' 或标注 JSONL 路径")
    args = parser.parse_args()
    rows, name = load_dataset(args.dataset)
    per_action, crosstalk, frame_rows = evaluate(rows)
    totals, micro, macro = write_outputs(per_action, crosstalk, frame_rows, name)
    print(f"数据源: {name}")
    print(f"标注帧数: {len(frame_rows)}")
    print("Micro P/R/F1: {:.3f}/{:.3f}/{:.3f}".format(*micro))
    print("Macro P/R/F1: {:.3f}/{:.3f}/{:.3f}".format(*macro))
    print(f"TP={totals['tp']} FP={totals['fp']} FN={totals['fn']}")
    print(f"明细: {CSV_PATH}")
    print(f"报告: {MD_PATH}")


if __name__ == "__main__":
    main()
