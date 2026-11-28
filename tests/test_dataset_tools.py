# -*- coding: utf-8 -*-
"""标注采样与评估数据格式单测（无需摄像头）。"""

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "vision"))

from action_engine import Pt  # noqa: E402
import collect_pose_dataset as collector  # noqa: E402
import evaluate_recognition as evaluator  # noqa: E402


def test_pose_and_hands_serialization():
    lms = [Pt(i / 100.0, 0.5, 0.0, 0.9) for i in range(33)]
    pose = collector.pose_to_dict(lms)
    assert len(pose) == 33 and "32" in pose
    hand = [Pt(0.1, 0.2, 0.0, 1.0) for _ in range(21)]
    hands = collector.hands_to_dict({"L": hand, "R": hand})
    assert set(hands) == {"L", "R"} and len(hands["L"]) == 21
    restored = evaluator.to_hands(hands)
    assert len(restored["L"][0]) == 4


def test_validate_dataset():
    lms = [Pt(0.5, 0.5, 0.0, 0.9) for i in range(33)]
    row = {
        "source": "unit-test",
        "labels": ["raise_right"],
        "landmarks": collector.pose_to_dict(lms),
        "hands": {},
    }
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "dataset.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        total, counts = collector.validate(path)
        assert total == 1 and counts["raise_right"] == 1

        rows, _ = evaluator.load_dataset(path)
        assert len(rows) == 1
        predicted = set(evaluator.detect_actions(
            evaluator.to_landmarks(rows[0]["landmarks"])))
        assert isinstance(predicted, set)


def test_validate_reject_unknown_label():
    lms = [Pt(0.5, 0.5, 0.0, 0.9) for i in range(33)]
    row = {"labels": ["not_an_action"],
           "landmarks": collector.pose_to_dict(lms)}
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "bad.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        try:
            collector.validate(path)
            raise AssertionError("未知动作应被拒绝")
        except ValueError:
            pass


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS:", name)
    print("test_dataset_tools：3/3 通过")


if __name__ == "__main__":
    main()
