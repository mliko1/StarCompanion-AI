# -*- coding: utf-8 -*-
"""core.personalization 模块单元测试（无需摄像头/数据库）。

覆盖个体化适应的核心承诺：
1. 首次训练仅记录、不当作标准（pending + 需人工确认）；
2. 参考范围「多次训练 + 人工审核」才逐步收敛（building -> stable）；
3. 数值型用中位数+四分位（抗异常值），分类型用众数+一致率；
4. 偏离参考范围 -> 标记需人工确认；
5. 惯用手镜像、幅度/时长缩放等适配函数。

运行：python tests/test_personalization.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.personalization import (  # noqa: E402
    PersonalProfile, ProfileStore,
    numeric_reference, categorical_reference,
    mirror_action, adapt_action_for_hand, scale_threshold, adapt_task_params,
    effective_params,
)


def test_first_record_pending():
    """首次训练：仅记录，pending，必须人工确认——不把第一次当标准。"""
    p = PersonalProfile(1, "action_raise_right")
    p.record("amplitude_scale", 0.8)
    assert p.status("amplitude_scale") == "pending"
    assert p.needs_confirmation("amplitude_scale") is True
    assert p.confidence("amplitude_scale") <= 0.4
    print("PASS: test_first_record_pending")


def test_building_without_review():
    """多次训练但无人审核：只到 building，置信度封顶 0.4。"""
    p = PersonalProfile(1, "action_raise_right")
    for v in (0.8, 0.82, 0.84):
        p.record("amplitude_scale", v)
    assert p.status("amplitude_scale") == "building"
    assert p.confidence("amplitude_scale") <= 0.4
    print("PASS: test_building_without_review")


def test_stable_with_reviews():
    """多次训练 + 多次人工确认一致 -> stable，置信度显著上升。"""
    p = PersonalProfile(1, "action_raise_right")
    for v in (0.8, 0.82, 0.84, 0.86, 0.88):
        p.record("amplitude_scale", v, reviewed=True, correct=True)
    assert p.status("amplitude_scale") == "stable"
    assert p.confidence("amplitude_scale") >= 0.9
    print("PASS: test_stable_with_reviews")


def test_numeric_reference_robust():
    """数值型参考范围：中位数抗异常值，不随单个极端值漂移。"""
    ref = numeric_reference([0.8, 0.82, 0.84, 0.86, 0.88])
    assert abs(ref["median"] - 0.84) < 1e-9
    ref2 = numeric_reference([0.8, 0.82, 0.84, 0.86, 0.88, 5.0])
    assert 0.8 <= ref2["median"] <= 0.9  # 异常值 5.0 不拉偏中位数
    print("PASS: test_numeric_reference_robust")


def test_categorical_reference():
    ref = categorical_reference(["left", "left", "right"])
    assert ref["mode"] == "left"
    assert abs(ref["agreement"] - 2 / 3) < 1e-9
    print("PASS: test_categorical_reference")


def test_outlier_needs_confirmation():
    """已建立稳定范围后，正常值不确认、明显偏离值需确认。"""
    p = PersonalProfile(1, "t")
    for v in (0.8, 0.82, 0.84, 0.86, 0.88):
        p.record("amplitude_scale", v, reviewed=True, correct=True)
    assert p.needs_confirmation("amplitude_scale", 0.85) is False
    assert p.needs_confirmation("amplitude_scale", 2.0) is True
    print("PASS: test_outlier_needs_confirmation")


def test_categorical_mismatch_needs_confirmation():
    p = PersonalProfile(1, "t")
    for v in ("left", "left", "left"):
        p.record("preferred_hand", v, reviewed=True, correct=True)
    assert p.needs_confirmation("preferred_hand", "left") is False
    assert p.needs_confirmation("preferred_hand", "right") is True
    print("PASS: test_categorical_mismatch_needs_confirmation")


def test_mirror_action():
    assert mirror_action("raise_right") == "raise_left"
    assert mirror_action("raise_left") == "raise_right"
    assert mirror_action("raise_right_lift_left") == "raise_left_lift_right"
    assert mirror_action("clap") == "clap"
    assert mirror_action("both_hands_up") == "both_hands_up"
    print("PASS: test_mirror_action")


def test_adapt_action_for_hand():
    # 惯用左手：举右手 -> 举左手
    assert adapt_action_for_hand("raise_right", "left") == "raise_left"
    assert adapt_action_for_hand("raise_right", "right") == "raise_right"
    assert adapt_action_for_hand("raise_right", "both") == "raise_right"
    assert adapt_action_for_hand("raise_right", "unknown") == "raise_right"
    print("PASS: test_adapt_action_for_hand")


def test_scale_threshold():
    assert abs(scale_threshold(0.30, 0.8) - 0.24) < 1e-9
    assert scale_threshold(1.0, -1.0) == 0.0  # 下限 0 保护
    assert scale_threshold(1.0, None) == 1.0  # 异常 scale 回退 1.0
    print("PASS: test_scale_threshold")


def test_effective_params_pending():
    """数值型样本不足回退默认，分类型（惯用手，家长确认）即生效。"""
    p = PersonalProfile(1, "t")
    p.record("preferred_hand", "left", reviewed=True, correct=True)
    p.record("hold_sec_scale", 2.0)  # 只有 1 个样本
    eff = effective_params(p)
    assert eff["preferred_hand"] == "left"   # 家长确认的惯用手立即生效
    assert eff["hold_sec_scale"] == 1.0       # 数值型样本不足，回退默认
    print("PASS: test_effective_params_pending")


def test_adapt_task_params():
    """惯用手 + 时长缩放综合适配，且不修改原参数。"""
    p = PersonalProfile(1, "action_raise_right")
    p.record("preferred_hand", "left", reviewed=True, correct=True)
    for _ in range(3):  # 数值型需 >1 个样本才生效
        p.record("hold_sec_scale", 1.5, reviewed=True, correct=True)
    params = {"action_id": "raise_right", "hold_sec": 2.0}
    adapted = adapt_task_params(params, p)
    assert adapted["action_id"] == "raise_left"
    assert abs(adapted["hold_sec"] - 3.0) < 1e-9
    assert params["action_id"] == "raise_right"  # 原值未被修改
    assert params["hold_sec"] == 2.0
    print("PASS: test_adapt_task_params")


def test_store_and_roundtrip():
    store = ProfileStore()
    store.record(1, "action_clap", "speed_scale", 1.5, reviewed=True, correct=True)
    p = store.get(1, "action_clap")
    assert p.samples("speed_scale") == [1.5]

    d = p.to_dict()
    p2 = PersonalProfile.from_dict(d)
    assert p2.child_id == 1
    assert p2.samples("speed_scale") == [1.5]
    assert p2.reviews("speed_scale") == [{"value": 1.5, "correct": True}]
    print("PASS: test_store_and_roundtrip")


if __name__ == "__main__":
    test_first_record_pending()
    test_building_without_review()
    test_stable_with_reviews()
    test_numeric_reference_robust()
    test_categorical_reference()
    test_outlier_needs_confirmation()
    test_categorical_mismatch_needs_confirmation()
    test_mirror_action()
    test_adapt_action_for_hand()
    test_scale_threshold()
    test_effective_params_pending()
    test_adapt_task_params()
    test_store_and_roundtrip()
    print("personalization 模块单元测试全部通过")
