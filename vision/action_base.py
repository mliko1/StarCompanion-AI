# -*- coding: utf-8 -*-
"""
星伴AI 统一动作判断核心（P0 消重成果）。

把举手与拍手的公共判断逻辑下沉到这一层，供
raise_hand / clap_hands / task_session 以及后端服务共用，消除各模块里
重复实现的 raise_check / clap_check / 计数防伪逻辑。

设计约定：
- 举手（持续动作）用"平滑关键点"判定，配合防抖与保持计时；
- 拍手（瞬时动作）用"原始关键点"判定——平滑会削平快速拍击的深谷导致漏计。
"""

import math
from collections import deque

from pose_utils import (angle_at, dist2d, hand_center, hand_center_21,
                        point_reliable, L_SHOULDER, R_SHOULDER, L_ELBOW,
                        R_ELBOW, L_WRIST, R_WRIST, L_HIP, R_HIP)

# ---------------------------------------------------------------------------
# 拍手判定参数（实测标定）
# ---------------------------------------------------------------------------
CONTACT_HIGH = 0.80   # 迟滞退出门槛（曾合拢后需超过它才算分开）
CONTACT_LOW = 0.55    # 迟滞进入门槛（跌破即合拢）
REARM_RATIO = 0.65    # 快速连击的重新武装线
REARM_TIME = 0.25     # 重新武装的时间底线（秒）
FAST_DROP = 0.2       # 骤降最小幅度
FAST_SPEED = 1.5      # 骤降最小速度（比例/秒）

# ---------------------------------------------------------------------------
# 举手判定参数
# ---------------------------------------------------------------------------
RAISE_ENTER = 0.06    # 进入"举起"：手腕需高出肩膀 0.06
RAISE_EXIT = 0.01     # 退出"举起"：手腕回落到只高出 0.01
# 肩宽归一化门槛（P1）：等价于固定 0.06/0.01 在肩宽 0.2 下的比例，
# 对人物远近/体型免疫。
RAISE_ENTER_RATIO = 0.30
RAISE_EXIT_RATIO = 0.05
RAISE_ELBOW_MIN = 90.0  # 多条件举手：肘部夹角下限（度），排除摸鼻/敬礼等明显曲肘


def raise_check(lms, side, was_raised, min_elbow=RAISE_ELBOW_MIN,
                min_visibility=0.3, reliable_margin=None, use_ratio=True):
    """举手判定（多条件：高低 + 肘部角度门控，可选肩宽归一化）。

    返回 (是否举起, 肘部夹角)。返回 None 表示手臂出画、判断不可靠。
    迟滞避免临界点反复翻转：进入需高出门槛，退出等回落到更小门槛。

    P1 多条件：
    - use_ratio=True（默认）：用肩宽归一化高低比（对远近/体型免疫），
      进入 RAISE_ENTER_RATIO、退出 RAISE_EXIT_RATIO；
    - use_ratio=False：退回固定像素高低 RAISE_ENTER / RAISE_EXIT；
    - min_elbow（默认 RAISE_ELBOW_MIN）：肘部夹角需大于该阈值才认定举起，
      排除"手摸头/叉腰"等手腕高但肘弯曲的误判；传 None 关闭。
    - min_visibility / reliable_margin 控制置信度门控语义：
      默认宽松（visibility>0.3，真正出画才不可靠），
      举手独立脚本可传更严格值（如 visibility>0.5 + 边缘 0.03）。
    """
    s_i = R_SHOULDER if side == "right" else L_SHOULDER
    e_i = R_ELBOW if side == "right" else L_ELBOW
    w_i = R_WRIST if side == "right" else L_WRIST
    s, e, w = lms[s_i], lms[e_i], lms[w_i]
    angle = angle_at(s, e, w)
    if not (point_reliable(s, min_visibility, reliable_margin) and
            point_reliable(w, min_visibility, reliable_margin)):
        return None, angle
    if use_ratio:
        shoulder_w = dist2d(lms[L_SHOULDER], lms[R_SHOULDER]) or 1e-6
        raise_amt = (s.y - w.y) / shoulder_w
        raised = raise_amt > (RAISE_EXIT_RATIO if was_raised
                              else RAISE_ENTER_RATIO)
    else:
        raised = w.y < s.y - (RAISE_EXIT if was_raised else RAISE_ENTER)
    if raised and min_elbow is not None:
        raised = angle > min_elbow
    return raised, angle


def clap_check(lms, was_contact, hands=None):
    """拍手判定（掌心距/肩宽比例 + 胸线条件 + 迟滞）。

    返回 (contact, ratio)。None 表示关键点不可靠。
    注意：lms 应传原始（未平滑）关键点；hands 为 21 点手部识别结果，
    可用时用 21 点掌心，避免 Pose 4 点掌心把"靠近"误判成"合拢"。"""
    lw, rw = lms[L_WRIST], lms[R_WRIST]
    ls, rs = lms[L_SHOULDER], lms[R_SHOULDER]
    if not all(point_reliable(p) for p in (lw, rw, ls, rs)):
        return None, 0.0
    l_center = hand_center_21(hands.get("L")) if hands else None
    r_center = hand_center_21(hands.get("R")) if hands else None
    if l_center and r_center:
        lcx, lcy = l_center
        rcx, rcy = r_center
    else:
        lcx, lcy = hand_center(lms, "L")
        rcx, rcy = hand_center(lms, "R")
    shoulder = dist2d(ls, rs) or 1e-6
    ratio = math.hypot(lcx - rcx, lcy - rcy) / shoulder

    lh, rh = lms[L_HIP], lms[R_HIP]
    if point_reliable(lh) and point_reliable(rh):
        chest_y = (ls.y + rs.y + lh.y + rh.y) / 4
    else:
        chest_y = max(ls.y, rs.y) + 0.15  # 髋部出画时的退让估计
    above_chest = lcy < chest_y and rcy < chest_y

    thr = CONTACT_HIGH if was_contact else CONTACT_LOW
    return (above_chest and ratio < thr), ratio


def fast_close_enough(hist, now, speed_scale=1.0):
    """真拍手的"指纹"：合拢前 0.35 秒内比例骤降（快速相向撞击）。

    缓慢漂近的手（普通手势、整理动作）不满足此特征，不计入。
    hist: [(时间, ratio), ...] 近期比例历史。
    speed_scale：个体化速度容差缩放，>1 表示动作慢，骤降幅度/速度门槛按
    1/speed_scale 放宽（动作慢的孩子拍手慢也认定命中）。默认 1.0 不变。
    """
    recent = [(t, r) for t, r in hist if now - t <= 0.35]
    if len(recent) < 2:
        return False
    r_max = max(r for _, r in recent)
    t_max = max(t for t, r in recent if r == r_max)
    drop = r_max - recent[-1][1]
    dt = max(now - t_max, 0.03)
    eff_drop = FAST_DROP / speed_scale
    eff_speed = FAST_SPEED / speed_scale
    return drop >= eff_drop and drop / dt >= eff_speed


class ClapCounter:
    """拍手计数器：单帧计数 + 重新武装 + 骤降防伪。"""

    def __init__(self, on_count=None, speed_scale=1.0):
        self.contact = False
        self.count = 0
        self.last_time = 0.0
        self.max_ratio = 0.0
        self.ratio_hist = deque(maxlen=20)
        self.on_count = on_count
        self.speed_scale = speed_scale  # 个体化速度容差缩放

    def reset(self):
        """任务切换时清零计数与历史，供复用。"""
        self.contact = False
        self.count = 0
        self.last_time = 0.0
        self.max_ratio = 0.0
        self.ratio_hist.clear()

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
            if not rearmed or not fast_close_enough(self.ratio_hist, now,
                                                    self.speed_scale):
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


class RaiseTracker:
    """举手防抖器：连续 debounce 帧状态一致才切换对外状态。

    raw 为 None（出画）时冻结状态不更新；否则连续一致帧才切换，
    消除抬手瞬间的抖动误判。
    """

    def __init__(self, debounce=8):
        self.debounce = debounce
        self.disp = False
        self.cnt = 0

    def reset(self, disp=False):
        self.disp = disp
        self.cnt = 0

    def update(self, raw):
        """raw: True/False/None。返回当前稳定状态。"""
        if raw is None:
            self.cnt = 0
            return self.disp
        if raw == self.disp:
            self.cnt = 0
        else:
            self.cnt += 1
            if self.cnt >= self.debounce:
                self.disp, self.cnt = raw, 0
        return self.disp
