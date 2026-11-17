# -*- coding: utf-8 -*-
"""
拍手检测核心逻辑（统一版，供 clap_hands 与 task_session 共用）。

相对早期版本的改进（实测标定得出）：
1. 用"未平滑的原始关键点"计算比例——平滑会削平快速拍击的深谷导致漏计；
2. 单帧立即计数 + 重新武装（分开到0.65以上 或 超0.25秒），支持快速连击；
3. 骤降特征校验：真拍手是快速撞击，慢速漂近的手不算。
"""

import math
from collections import deque

L_SHOULDER, R_SHOULDER = 11, 12
L_HIP, R_HIP = 23, 24
L_WRIST, R_WRIST = 15, 16

CONTACT_HIGH = 0.80   # 迟滞退出门槛（曾合拢后需超过它才算分开）
CONTACT_LOW = 0.55    # 迟滞进入门槛（跌破即合拢）
REARM_RATIO = 0.65    # 快速连击的重新武装线
REARM_TIME = 0.25     # 重新武装的时间底线（秒）
FAST_DROP = 0.2       # 骤降最小幅度
FAST_SPEED = 1.5      # 骤降最小速度（比例/秒）


def point_reliable(lm):
    return (lm.visibility > 0.3 and
            -0.01 < lm.x < 1.01 and -0.01 < lm.y < 1.01)


def hand_center(lms, side):
    """手掌中心 = 手腕+小指根+食指根+拇指 四点平均。"""
    idx = (L_WRIST, 17, 19, 21) if side == "L" else (R_WRIST, 18, 20, 22)
    return (sum(lms[i].x for i in idx) / 4,
            sum(lms[i].y for i in idx) / 4)


def clap_check(lms, was_contact):
    """返回 (contact, ratio)。None 表示关键点不可靠。
    注意：lms 应传原始（未平滑）关键点。"""
    lw, rw = lms[L_WRIST], lms[R_WRIST]
    ls, rs = lms[L_SHOULDER], lms[R_SHOULDER]
    if not all(point_reliable(p) for p in (lw, rw, ls, rs)):
        return None, 0.0
    lcx, lcy = hand_center(lms, "L")
    rcx, rcy = hand_center(lms, "R")
    shoulder = math.hypot(ls.x - rs.x, ls.y - rs.y) or 1e-6
    ratio = math.hypot(lcx - rcx, lcy - rcy) / shoulder

    lh, rh = lms[L_HIP], lms[R_HIP]
    if point_reliable(lh) and point_reliable(rh):
        chest_y = (ls.y + rs.y + lh.y + rh.y) / 4
    else:
        chest_y = max(ls.y, rs.y) + 0.15
    above_chest = lcy < chest_y and rcy < chest_y

    thr = CONTACT_HIGH if was_contact else CONTACT_LOW
    return (above_chest and ratio < thr), ratio


def fast_close_enough(hist, now):
    """真拍手的指纹：合拢前0.35秒内比例骤降。"""
    recent = [(t, r) for t, r in hist if now - t <= 0.35]
    if len(recent) < 2:
        return False
    r_max = max(r for _, r in recent)
    t_max = max(t for t, r in recent if r == r_max)
    drop = r_max - recent[-1][1]
    dt = max(now - t_max, 0.03)
    return drop >= FAST_DROP and drop / dt >= FAST_SPEED


class ClapCounter:
    """拍手计数器：单帧计数 + 重新武装 + 骤降防伪。"""

    def __init__(self, on_count=None):
        self.contact = False
        self.count = 0
        self.last_time = 0.0
        self.max_ratio = 0.0
        self.ratio_hist = deque(maxlen=20)
        self.on_count = on_count

    def update(self, ratio, contact, now):
        """每帧调用，返回是否新计一次拍手。"""
        self.ratio_hist.append((now, ratio))
        if ratio > self.max_ratio:
            self.max_ratio = ratio
        if contact == self.contact:
            return False
        if contact:
            rearmed = (self.max_ratio >= REARM_RATIO or
                       now - self.last_time >= REARM_TIME)
            if not rearmed or not fast_close_enough(self.ratio_hist, now):
                return False
            self.contact = True
            self.count += 1
            self.last_time = now
            self.max_ratio = 0.0
            if self.on_count:
                self.on_count(self.count)
            return True
        self.contact = False
        return False
