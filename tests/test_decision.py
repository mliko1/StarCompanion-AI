# -*- coding: utf-8 -*-
"""core.decision 模块单元测试（无需摄像头）。

运行：python tests/test_decision.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.decision import (compute_pdi, independent_rate, completion_rate,
                           suggest, trend_of)  # noqa: E402


def test_pdi():
    assert compute_pdi([]) == 0.0
    assert compute_pdi([0, 0]) == 0.0              # 全独立 -> PDI=0
    assert compute_pdi([4, 4]) == 1.0              # 全家长协助 -> PDI=1
    assert abs(compute_pdi([0, 2, 4]) - 0.5) < 1e-9  # (0+2+4)/(4*3)=0.5
    print("PASS: test_pdi")


def test_independent_rate():
    s = [{"completed": True, "prompt_level": 0},
         {"completed": True, "prompt_level": 2},
         {"completed": False, "prompt_level": 0},
         {"completed": True, "prompt_level": 0}]
    assert abs(independent_rate(s) - 0.5) < 1e-9  # 2独立完成/4
    print("PASS: test_independent_rate")


def test_completion_rate():
    s = [{"completed": True}, {"completed": False},
         {"completed": True}, {"completed": True}]
    assert abs(completion_rate(s) - 0.75) < 1e-9
    print("PASS: test_completion_rate")


def test_suggest_observe():
    """数据不足 -> 应包含 observe 建议。"""
    s = [{"completed": True, "prompt_level": 0}]
    adv = suggest(s)
    types = {a["type"] for a in adv}
    assert "observe" in types
    print("PASS: test_suggest_observe", types)


def test_suggest_reduce():
    """独立率高 -> 应包含 reduce 建议。"""
    s = [{"completed": True, "prompt_level": 0} for _ in range(8)]
    adv = suggest(s)
    types = {a["type"] for a in adv}
    assert "reduce" in types, types
    print("PASS: test_suggest_reduce", types)


def test_suggest_assist():
    """依赖高(全等级4) -> 应包含 assist 建议。"""
    s = [{"completed": True, "prompt_level": 4} for _ in range(8)]
    adv = suggest(s)
    types = {a["type"] for a in adv}
    assert "assist" in types, types
    print("PASS: test_suggest_assist", types)


def test_trend():
    assert trend_of([0, 1, 1, 1]) > 0   # 上升
    assert trend_of([1, 1, 0, 0]) < 0   # 下降
    print("PASS: test_trend")


if __name__ == "__main__":
    test_pdi()
    test_independent_rate()
    test_completion_rate()
    test_suggest_observe()
    test_suggest_reduce()
    test_suggest_assist()
    test_trend()
    print("decision 模块单元测试全部通过")
