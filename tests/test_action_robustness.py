# -*- coding: utf-8 -*-
"""动作识别鲁棒性单元测试。

覆盖四项改进：
1. 角度个体化：angle 的 >/>= 门槛随幅度缩放放宽，</<= 不放宽（不放大摸头误判）；
2. 任务白名单：训练单个动作时只检测目标动作，相似动作不抢判定；
3. 目标保护：当前训练目标不被其他动作的 excludes 压制；
4. 稳定性确认：非瞬时动作需连续多帧命中才输出，避免单帧抖动误记录。

运行：python tests/test_action_robustness.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vision"))
sys.path.insert(0, os.path.dirname(__file__))

from action_engine import (  # noqa: E402
    ActionTracker, _resolve_conflicts, _scaled_val, detect_actions, load_actions,
)
from test_action_engine import SAMPLE, make_pose  # noqa: E402


def test_angle_scale_only_relaxes_greater():
    """angle 的 > 门槛放宽，< 门槛保持不变（避免把摸头判定一起放宽）。"""
    assert abs(_scaled_val("angle", ">", 90, 0.8) - 72) < 1e-9
    assert abs(_scaled_val("angle", ">=", 90, 0.8) - 72) < 1e-9
    assert _scaled_val("angle", "<", 130, 0.8) == 130
    assert _scaled_val("angle", "<=", 130, 0.8) == 130
    assert _scaled_val("angle", ">", 90, 1.0) == 90
    assert _scaled_val("dx", ">", 0.1, 0.8) == 0.1
    print("PASS: test_angle_scale_only_relaxes_greater")


def test_angle_scale_relaxes_stiff_raise():
    """孩子手臂没完全伸直（肘角 95° < 默认 90° 边缘），幅度缩小后应被放宽检出。

    用肩-肘-腕夹角略高于 72° 但低于 90° 的姿态验证 angle 门槛生效。
    """
    acts = [a for a in load_actions() if a["id"] == "raise_right"]
    # 肩(0.40,0.34)、肘(0.30,0.30)、腕(0.353,0.215)：
    # 肘角约 80°，默认 angle>90 不命中；scale=0.8 门槛 72° 命中。
    pose = make_pose({14: (0.30, 0.30), 16: (0.353, 0.215)})
    assert "raise_right" not in detect_actions(pose, actions=acts)
    assert "raise_right" in detect_actions(pose, actions=acts,
                                           amplitude_scale=0.8)
    print("PASS: test_angle_scale_relaxes_stiff_raise")


def test_whitelist_blocks_similar_action():
    """白名单只返回目标动作，其他动作（含相似动作）不参与检测。"""
    pose = make_pose(SAMPLE["raise_left"]["pose"])
    only = detect_actions(pose, allowed={"raise_left"})
    assert only == ["raise_left"], only
    # 中性站姿在白名单下不应返回站直/双臂下垂（它们不在白名单里）
    assert detect_actions(make_pose(), allowed={"raise_left"}) == []
    print("PASS: test_whitelist_blocks_similar_action")


def test_protect_prevents_suppression():
    """touch_head 的 excludes 含 raise_left；保护后目标动作不得被压制。"""
    acts = load_actions()
    hits = {"raise_left", "touch_head"}
    assert "raise_left" not in _resolve_conflicts(hits, acts)
    assert "raise_left" in _resolve_conflicts(hits, acts,
                                              protect={"raise_left"})
    print("PASS: test_protect_prevents_suppression")


def test_stability_requires_consecutive_frames():
    """连续 3 帧命中才输出；中断后重新计数。"""
    tracker = ActionTracker(allowed={"raise_left"}, protect={"raise_left"},
                            stable_frames=3)
    pose = make_pose(SAMPLE["raise_left"]["pose"])
    neutral = make_pose()
    assert tracker.detect(pose, 0.00) == []
    assert tracker.detect(pose, 0.05) == []
    assert tracker.detect(pose, 0.10) == ["raise_left"]
    assert tracker.detect(neutral, 0.15) == []
    assert tracker.detect(pose, 0.20) == []
    assert tracker.detect(pose, 0.25) == []
    assert tracker.detect(pose, 0.30) == ["raise_left"]
    print("PASS: test_stability_requires_consecutive_frames")


if __name__ == "__main__":
    test_angle_scale_only_relaxes_greater()
    test_angle_scale_relaxes_stiff_raise()
    test_whitelist_blocks_similar_action()
    test_protect_prevents_suppression()
    test_stability_requires_consecutive_frames()
    print("action_robustness 单元测试全部通过")
