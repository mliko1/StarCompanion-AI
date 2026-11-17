# -*- coding: utf-8 -*-
"""dtw_similarity 模块的单元测试（无需摄像头）。

运行：python tests/test_dtw.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vision.dtw_similarity import similarity  # noqa: E402


def make_seq(n, f):
    """生成 n 帧、每帧3个关键点，坐标由函数 f(t) 决定。"""
    return [[(f(t, k), f(t, k) + 0.1) for k in range(3)]
            for t in [i / n for i in range(n)]]


def test_identical():
    """完全相同序列：相似度接近1。"""
    a = make_seq(10, lambda t, k: t + k * 0.1)
    s = similarity(a, a)
    assert s > 0.95, s
    print("PASS: test_identical", round(s, 3))


def test_different_length():
    """同一动作不同速度/长度：DTW 应仍给出较高相似度。"""
    a = make_seq(10, lambda t, k: t + k * 0.1)
    b = make_seq(20, lambda t, k: t + k * 0.1)
    s = similarity(a, b)
    assert s > 0.8, s
    print("PASS: test_different_length", round(s, 3))


def test_different_motion():
    """不同动作：相似度应明显更低。"""
    a = make_seq(10, lambda t, k: t + k * 0.1)
    b = make_seq(10, lambda t, k: 1 - t + k * 0.1)
    s1 = similarity(a, a)
    s2 = similarity(a, b)
    assert s2 < s1, (s1, s2)
    print("PASS: test_different_motion", round(s1, 3), ">", round(s2, 3))


def test_symmetry():
    """DTW 对称性。"""
    a = make_seq(8, lambda t, k: t * 0.5)
    b = make_seq(12, lambda t, k: t)
    assert abs(similarity(a, b) - similarity(b, a)) < 1e-9
    print("PASS: test_symmetry")


if __name__ == "__main__":
    test_identical()
    test_different_length()
    test_different_motion()
    test_symmetry()
    print("DTW 单元测试全部通过")
