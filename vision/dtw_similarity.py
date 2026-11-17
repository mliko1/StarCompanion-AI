# -*- coding: utf-8 -*-
"""
星伴AI 动作相似度评价模块（动态时间规整 DTW）

用途：对比儿童动作与标准示范动作的时间序列相似程度，
用于"模仿动作"类任务的评分。输入为已归一化（0~1 坐标、
帧间对齐的）关键点序列。

说明：本模块为纯算法，不依赖摄像头，可用 tests/test_dtw.py 验证。
DTW 属于"动作相似度"研究方向的第一版实现，文档中如实标注。
"""

import math

import numpy as np


def seq_to_features(seq):
    """关键点序列 -> 特征矩阵 (帧数 × 特征维度)。
    seq: [帧] -> [ (x,y) 关键点 ]，展平为每帧向量。"""
    feats = []
    for frame in seq:
        vec = []
        for pt in frame:
            vec.extend([float(pt[0]), float(pt[1])])
        feats.append(np.asarray(vec, dtype=np.float64))
    return feats


def dtw_distance(feats_a, feats_b):
    """标准 DTW 累计距离。输入为特征向量列表。"""
    n, m = len(feats_a), len(feats_b)
    if n == 0 or m == 0:
        return float("inf")
    d = np.full((n + 1, m + 1), np.inf)
    d[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = np.linalg.norm(feats_a[i - 1] - feats_b[j - 1])
            d[i, j] = cost + min(d[i - 1, j], d[i, j - 1], d[i - 1, j - 1])
    return float(d[n, m])


def similarity(seq_a, seq_b, scale=2.0):
    """动作相似度（0~1，越接近1越相似）。
    对序列长度差异不敏感（DTW 天然支持不同长度/速度）。"""
    fa = seq_to_features(seq_a)
    fb = seq_to_features(seq_b)
    dist = dtw_distance(fa, fb)
    length = max(len(fa), len(fb), 1)
    # 归一化：平均每帧代价
    avg = dist / length
    return 1.0 / (1.0 + scale * avg)
