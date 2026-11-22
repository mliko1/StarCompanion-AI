# -*- coding: utf-8 -*-
"""生活技能惯用手接入 + 标定采集脚本 单元测试（无需摄像头）。

验证：
1. InteractionDetector 的惯用手优先顺序；
2. collect_calibration 的特征提取与统计。

运行：python tests/test_calibration.py（需项目 .venv，依赖 cv2/ultralytics）
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vision"))
sys.path.insert(0, os.path.dirname(__file__))

from interaction_detector import InteractionDetector  # noqa: E402
from collect_calibration import extract_features, summarize  # noqa: E402
from test_action_engine import make_pose  # noqa: E402


def test_hand_order():
    """惯用手决定手部遍历顺序，默认/unknown 取左先。"""
    d = InteractionDetector("bottle", 1280, 720)
    assert d._hand_order()[0][1] == "left"          # 默认
    assert InteractionDetector("bottle", 1280, 720,
                               preferred_hand="right")._hand_order()[0][1] == "right"
    assert InteractionDetector("bottle", 1280, 720,
                               preferred_hand="left")._hand_order()[0][1] == "left"
    assert InteractionDetector("bottle", 1280, 720,
                               preferred_hand="both")._hand_order()[0][1] == "left"
    print("PASS: test_hand_order")


def test_extract_features_raise():
    """举手姿态：dy_ratio > 0.1 且 angle > 90。"""
    pose = make_pose({14: (0.40, 0.22), 16: (0.40, 0.10),
                      18: (0.38, 0.11), 20: (0.40, 0.12), 22: (0.42, 0.11)})
    feat = extract_features(pose, "raise_right")
    assert feat["dy_ratio"] > 0.1
    assert feat["angle"] > 90
    print("PASS: test_extract_features_raise", feat)


def test_extract_features_clap():
    """拍手姿态：掌心距/肩宽 ratio < 0.55。"""
    pose = make_pose({13: (0.62, 0.42), 15: (0.55, 0.30),
                      17: (0.56, 0.32), 19: (0.55, 0.33), 21: (0.54, 0.32),
                      14: (0.38, 0.42), 16: (0.45, 0.30),
                      18: (0.44, 0.32), 20: (0.45, 0.33), 22: (0.46, 0.32)})
    feat = extract_features(pose, "clap")
    assert feat["ratio"] < 0.55
    print("PASS: test_extract_features_clap", feat)


def test_summarize():
    samples = [{"dy_ratio": 0.1}, {"dy_ratio": 0.2}, {"dy_ratio": 0.3}]
    st = summarize(samples)
    assert st["dy_ratio"]["n"] == 3
    assert st["dy_ratio"]["median"] == 0.2
    assert st["dy_ratio"]["max"] == 0.3
    print("PASS: test_summarize")


if __name__ == "__main__":
    test_hand_order()
    test_extract_features_raise()
    test_extract_features_clap()
    test_summarize()
    print("calibration 单元测试全部通过")
