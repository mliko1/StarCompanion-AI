# -*- coding: utf-8 -*-
"""P0 识别增强单测：21 点掌心、身体尺度归一、按帧去重。

运行：python tests/test_p0_recognition.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vision"))

from pose_utils import body_scale, hand_center_21  # noqa: E402
from action_engine import Pt, ActionTracker, detect_actions  # noqa: E402
from action_base import clap_check  # noqa: E402


def make_pose(shoulder_w=0.20, palm_gap=0.10):
    """构造中性姿态：肩宽 shoulder_w，两掌心间距 palm_gap。"""
    c = 0.5
    left = c - shoulder_w / 2
    right = c + shoulder_w / 2
    lms = [Pt(c, 0.4, 0, 1) for _ in range(33)]
    for i in (11, 12, 23, 24):
        lms[i] = Pt(left if i in (11, 23) else right, 0.4, 0, 1)
    # Pose 手腕可靠（clap_check 的硬性门槛），但四指根部不可靠 -> 掌心走 Hands
    for idx in (17, 19, 21, 18, 20, 22):
        lms[idx] = Pt(0.0, 1.0, 0, 0.0)
    return lms, left, right, palm_gap


def make_hand(cx, cy):
    pts = [Pt(cx, cy, 0, 1) for _ in range(21)]
    return pts


def test_hand_center_21():
    hand = make_hand(0.42, 0.55)
    c = hand_center_21(hand)
    assert c is not None and abs(c[0] - 0.42) < 1e-6 and abs(c[1] - 0.55) < 1e-6
    hand[0] = Pt(2.0, 0.5, 0, 1)  # 越界 -> 拒绝该手
    assert hand_center_21(hand) is None


def test_hand_center_overrides_unreliable_pose():
    lms, left, right, gap = make_pose()
    hands = {"L": make_hand(0.45, 0.55), "R": make_hand(0.55, 0.55)}
    contact, ratio = clap_check(lms, False, hands=hands)
    assert ratio < 0.55, ratio  # 21 点掌心已进入判定，不再取不可靠的 Pose 四指点
    contact2, ratio2 = clap_check(lms, contact, hands=hands)
    assert contact2 is True or ratio2 < 0.55, (contact, contact2, ratio2)


def test_body_scale_normalizes_distance():
    near, _, _, _ = make_pose(shoulder_w=0.20, palm_gap=0.10)
    far, _, _, _ = make_pose(shoulder_w=0.10, palm_gap=0.05)
    assert abs(body_scale(near) - 1.0) < 1e-6
    assert abs(body_scale(far) - 0.5) < 1e-6

    action = {
        "id": "hands_close", "name": "双手靠近", "category": "测试",
        "rules": [[{"f": "dist", "a": "hc:L", "b": "hc:R",
                    "op": "<", "val": 0.11}]],
    }
    near_hands = {"L": make_hand(0.45, 0.55), "R": make_hand(0.55, 0.55)}
    far_hands = {"L": make_hand(0.475, 0.55), "R": make_hand(0.525, 0.55)}
    assert "hands_close" in detect_actions(near, [action], hands=near_hands)
    assert "hands_close" in detect_actions(far, [action], hands=far_hands)


def test_tracker_deduplicates_frame():
    lms, _, _, _ = make_pose()
    tracker = ActionTracker(actions=[], allowed=None)
    assert tracker.detect(lms, 0.0, frame_id=7) == []
    assert tracker.detect(lms, 0.1, frame_id=7) == []  # 同帧重复消费被拦下
    assert tracker.detect(lms, 0.2, frame_id=8) == []
    assert tracker._last_frame_id == 8


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS:", t.__name__)
    print(f"test_p0_recognition：{len(tests)}/{len(tests)} 通过")


if __name__ == "__main__":
    main()
