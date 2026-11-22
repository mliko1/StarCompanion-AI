# -*- coding: utf-8 -*-
"""个体化阈值注入（幅度/速度缩放）单元测试。

验证「幅度小 -> 放宽判定、动作慢 -> 放宽拍手时序」：
1. _scaled_val 只缩放幅度类特征（dy_ratio/ratio），scale=1 原样；
2. detect_actions(amplitude_scale<1) 对"抬得不够高"的举手放宽检出；
3. fast_close_enough(speed_scale>1) 对"拍得慢"放宽骤降判定。

运行：python tests/test_adaptive_thresholds.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vision"))
sys.path.insert(0, os.path.dirname(__file__))

from action_engine import _scaled_val, detect_actions  # noqa: E402
from action_base import fast_close_enough  # noqa: E402
from test_action_engine import make_pose  # noqa: E402


def test_scaled_val_semantics():
    # scale=1 完全不变
    assert _scaled_val("dy_ratio", ">", 0.1, 1.0) == 0.1
    # dy_ratio 是 > 阈值，scale<1 降低门槛（0.1 -> 0.08）
    assert abs(_scaled_val("dy_ratio", ">", 0.1, 0.8) - 0.08) < 1e-9
    # ratio 是 < 阈值，scale<1 提高允许值（0.55 -> 0.6875，放宽）
    assert abs(_scaled_val("ratio", "<", 0.55, 0.8) - 0.6875) < 1e-9
    # 非幅度特征（方向/可见性）不缩放
    assert _scaled_val("dx", ">", 0.1, 0.8) == 0.1
    assert _scaled_val("vis", ">", 0.3, 0.8) == 0.3
    print("PASS: test_scaled_val_semantics")


def test_amplitude_scale_relaxes_raise():
    """孩子右臂基本伸直、但只抬到肩高约 0.06 肩宽（< 0.1 默认门槛）。

    右肩(0.40,0.34)、右腕(0.25,0.328)、右肘取二者中点(0.325,0.334)，
    肩-肘-腕夹角≈180°（满足 angle>90），dy_ratio≈0.06 不达标；
    右腕横向偏移 dx=-0.15，避免命中"右臂前平举"（其 excludes 会压制 raise_right）。
    """
    pose = make_pose({14: (0.325, 0.334), 16: (0.25, 0.328)})
    assert "raise_right" not in detect_actions(pose)          # 默认不命中
    # 孩子幅度只有 50%：门槛 0.1 -> 0.05，此时 0.06 命中
    assert "raise_right" in detect_actions(pose, amplitude_scale=0.5)
    print("PASS: test_amplitude_scale_relaxes_raise")


def test_speed_scale_relaxes_clap_timing():
    """骤降幅度 0.18 < FAST_DROP(0.2)，默认不认定真拍手。"""
    hist = [(0.0, 0.90), (0.10, 0.72)]
    assert fast_close_enough(hist, 0.10) is False
    # 动作慢的孩子：speed_scale=1.2 放宽幅度/速度门槛后认定
    assert fast_close_enough(hist, 0.10, speed_scale=1.2) is True
    print("PASS: test_speed_scale_relaxes_clap_timing")


if __name__ == "__main__":
    test_scaled_val_semantics()
    test_amplitude_scale_relaxes_raise()
    test_speed_scale_relaxes_clap_timing()
    print("adaptive_thresholds 单元测试全部通过")
