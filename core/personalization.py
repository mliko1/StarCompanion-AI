# -*- coding: utf-8 -*-
"""
星伴AI 个体化适应模块（创新点：从「固定动作识别」→「个体化任务完成判断」）。

背景问题：
    孤独症儿童动作方式差异很大。同样是「拿起积木」，
    A 可能用左手、B 用右手、C 需要双手、D 动作慢。
    若沿用「必须右手抬高到某个固定位置才算完成」，会产生大量误判。

本模块提供个体化参考范围引擎（纯逻辑，不依赖摄像头/数据库，可单测）：

1. 每个孩子 × 每个任务，维护一组个体化参数
   （惯用手 preferred_hand / 幅度缩放 amplitude_scale / 保持时长缩放
     hold_sec_scale / 速度缩放 speed_scale）；
2. 参考范围「逐步建立」：首次训练仅记录并标记待确认，
   多次训练 + 人工审核后才收敛，绝不把第一次动作直接当标准；
3. 不确定的识别结果自动标记「需人工确认」，交给家长/老师。

判定口径（诚实）：
   本模块只做「个体化参数与参考范围」的统计与适配建议，
   不形成医学诊断；建议仅供辅助，须经专业人员审核。

设计约定：
   数值型参数用稳健统计（中位数 + 四分位范围 P25/P75），抗单次异常值；
   分类型参数（惯用手）用众数 + 一致率。
"""

import statistics
from collections import Counter

# ---------------------------------------------------------------------------
# 个体化参数元数据
# ---------------------------------------------------------------------------
# kind: categorical（分类型，众数+一致率） / numeric（数值型，中位数+四分位）
PROFILE_PARAMS = {
    "preferred_hand": {
        "kind": "categorical",
        "values": ("left", "right", "both", "unknown"),
        "default": "unknown",
        "desc": "孩子完成该任务时惯用哪只手（由家长/老师首次确认）",
    },
    "amplitude_scale": {
        "kind": "numeric",
        "default": 1.0,
        "lo": 0.4, "hi": 2.0,
        "desc": "动作幅度容差缩放（如只能抬到肩高 80% 的孩子取 0.8）",
    },
    "hold_sec_scale": {
        "kind": "numeric",
        "default": 1.0,
        "lo": 0.5, "hi": 4.0,
        "desc": "保持时长容差缩放（动作慢的孩子取 >1，放宽完成时限）",
    },
    "speed_scale": {
        "kind": "numeric",
        "default": 1.0,
        "lo": 0.5, "hi": 3.0,
        "desc": "动作速度容差缩放（拍手慢等瞬时动作的时序阈值放宽）",
    },
}

# ---------------------------------------------------------------------------
# 参考范围建立的状态机阈值（「不是第一次当标准」的量化落地）
# ---------------------------------------------------------------------------
PENDING_MAX_SAMPLES = 1    # 样本数 <= 1：仅记录，待人工确认
STABLE_MIN_SAMPLES = 5     # 样本数 >= 5：具备收敛为稳定的样本基础
STABLE_MIN_REVIEWS = 3     # 且人工确认一致次数 >= 3：才判定为 stable

# 数值型「偏离参考范围」判定的 IQR 倍率（超出 P25-1.5*IQR ~ P75+1.5*IQR 视为异常）
OUTLIER_IQR = 1.5


# ---------------------------------------------------------------------------
# 统计工具
# ---------------------------------------------------------------------------
def _quantile(values, q):
    """返回有序列表 values 的 q 分位（0<=q<=1），线性插值。"""
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def numeric_reference(samples):
    """数值型参考范围：{n, median, p25, p75, iqr}。样本不足时各统计量为 None。"""
    n = len(samples)
    if n == 0:
        return {"n": 0, "median": None, "p25": None, "p75": None, "iqr": None}
    median = statistics.median(samples)
    p25 = _quantile(samples, 0.25)
    p75 = _quantile(samples, 0.75)
    iqr = p75 - p25 if (p25 is not None and p75 is not None) else None
    return {"n": n, "median": median, "p25": p25, "p75": p75, "iqr": iqr}


def categorical_reference(samples):
    """分类型参考范围：{n, mode, agreement}。agreement = 众数占比 0~1。"""
    n = len(samples)
    if n == 0:
        return {"n": 0, "mode": None, "agreement": None}
    mode, cnt = Counter(samples).most_common(1)[0]
    return {"n": n, "mode": mode, "agreement": cnt / n}


def reference_for(kind, samples):
    return numeric_reference(samples) if kind == "numeric" \
        else categorical_reference(samples)


# ---------------------------------------------------------------------------
# 单个 (child, task) 的个体化档案
# ---------------------------------------------------------------------------
class PersonalProfile:
    """一个孩子在一个任务上的个体化档案（内存版，纯逻辑）。

    用法：
        p = PersonalProfile(child_id=1, task_id="action_raise_right")
        p.record("preferred_hand", "left", reviewed=True, correct=True)
        p.record("amplitude_scale", 0.8)
        p.status("amplitude_scale")      # -> 'pending' | 'building' | 'stable'
        p.needs_confirmation("amplitude_scale", 0.75)  # -> bool
    """

    def __init__(self, child_id, task_id):
        self.child_id = child_id
        self.task_id = task_id
        self._params = {}  # param_key -> {"samples": [...], "reviews": [...]}

    # ---- 记录 ----
    def record(self, param_key, value, reviewed=False, correct=None):
        """记录一次观察值。reviewed=True 表示该次观察经过人工审核，
        correct 表示审核结论是否为「与参考一致/正确」（可 None 表示仅确认无结论）。"""
        slot = self._params.setdefault(param_key, {"samples": [], "reviews": []})
        slot["samples"].append(value)
        if reviewed:
            slot["reviews"].append({"value": value, "correct": bool(correct)})
        return self

    def samples(self, param_key):
        return list(self._params.get(param_key, {}).get("samples", []))

    def reviews(self, param_key):
        return list(self._params.get(param_key, {}).get("reviews", []))

    # ---- 参考范围 ----
    def reference(self, param_key):
        kind = PROFILE_PARAMS.get(param_key, {}).get("kind", "numeric")
        return reference_for(kind, self.samples(param_key))

    def status(self, param_key):
        """pending / building / stable。"""
        n = len(self.samples(param_key))
        reviews = self.reviews(param_key)
        review_ok = sum(1 for r in reviews if r["correct"])
        if n <= PENDING_MAX_SAMPLES:
            return "pending"
        if n >= STABLE_MIN_SAMPLES and review_ok >= STABLE_MIN_REVIEWS:
            return "stable"
        return "building"

    def confidence(self, param_key):
        """0~1。样本量 + 人工审核并重：没有人工审核，置信度封顶 0.4。"""
        n = len(self.samples(param_key))
        reviews = self.reviews(param_key)
        sample_factor = min(1.0, n / STABLE_MIN_SAMPLES)
        if reviews:
            ok = sum(1 for r in reviews if r["correct"])
            review_factor = ok / len(reviews)
            return round(0.5 * sample_factor + 0.5 * review_factor, 3)
        return round(0.4 * sample_factor, 3)

    def needs_confirmation(self, param_key, value=None):
        """该参数当前是否「不确定，需人工确认」。

        触发条件（任一）：
        1. 样本不足（<= PENDING_MAX_SAMPLES）——还没建立参考范围；
        2. 传入 value 且数值型：偏离参考范围（四分位异常）；
        3. 传入 value 且分类型：与已确认的众数不一致。
        """
        n = len(self.samples(param_key))
        if n <= PENDING_MAX_SAMPLES:
            return True
        if value is None:
            return False
        kind = PROFILE_PARAMS.get(param_key, {}).get("kind", "numeric")
        if kind == "numeric":
            ref = numeric_reference(self.samples(param_key))
            iqr = ref["iqr"]
            if iqr is None or iqr <= 0:
                return abs(value - ref["median"]) > 1e-9
            return value < ref["p25"] - OUTLIER_IQR * iqr or \
                value > ref["p75"] + OUTLIER_IQR * iqr
        # 分类型：与参考众数不一致即需确认
        ref = categorical_reference(self.samples(param_key))
        return value != ref["mode"]

    def to_dict(self):
        return {
            "child_id": self.child_id,
            "task_id": self.task_id,
            "params": {
                k: {"samples": v["samples"], "reviews": v["reviews"]}
                for k, v in self._params.items()
            },
        }

    @classmethod
    def from_dict(cls, d):
        p = cls(d["child_id"], d["task_id"])
        for k, v in d.get("params", {}).items():
            p._params[k] = {"samples": list(v.get("samples", [])),
                            "reviews": list(v.get("reviews", []))}
        return p

    def set_slot(self, param_key, samples=None, reviews=None):
        """直接设置某参数的样本与人工确认记录（用于从数据库恢复档案）。"""
        self._params[param_key] = {"samples": list(samples or []),
                                   "reviews": list(reviews or [])}
        return self


# ---------------------------------------------------------------------------
# 个体化适配（把个体化参数应用到任务/动作判定）
# ---------------------------------------------------------------------------
def mirror_action(action_id):
    """左右镜像动作 id：*_right <-> *_left；无侧向则原样返回。

    约定：动作库中带 _right/_left 的均为左右对称动作，
    组合动作（如 raise_right_lift_left -> raise_left_lift_right）需双向翻转，
    故用占位符整体替换，避免 _right/_left 互相覆盖。
    """
    if "_right" not in action_id and "_left" not in action_id:
        return action_id
    tmp = action_id.replace("_right", "__RIGHT__").replace("_left", "__LEFT__")
    return tmp.replace("__RIGHT__", "_left").replace("__LEFT__", "_right")


def adapt_action_for_hand(action_id, preferred_hand):
    """按孩子惯用手适配「单侧动作」的目标动作 id。

    preferred_hand:
        'right' / 'unknown' : 保持原动作；
        'left'              : 若原动作是右手动作，镜像到左手（举右手→举左手）；
        'both'              : 保持原动作（不强制镜像，由上层结合双手变体决策）。
    """
    hand = (preferred_hand or "unknown").lower()
    if hand == "left" and action_id.endswith("_right"):
        return mirror_action(action_id)
    return action_id


def scale_threshold(base, scale):
    """个体化幅度/阈值缩放：base * scale，并在合理区间内（下限 0 保护）。"""
    try:
        s = float(scale)
    except (TypeError, ValueError):
        s = 1.0
    return max(0.0, base * s)


def effective_scale(profile, param_key, default=1.0):
    """从档案取数值型参数的参考中位数作为缩放系数；未建立时返回默认。"""
    ref = profile.reference(param_key)
    median = ref.get("median")
    if median is None:
        return default
    return median


def effective_params(profile):
    """从档案计算「有效个体化参数」字典（供训练主循环直接使用）。

    两类参数生效口径不同（体现「不是第一次当标准」）：
    - 分类型（preferred_hand 惯用手）：家长/老师明确确认的事实，众数即生效；
    - 数值型（幅度/时长/速度）：需积累超过 PENDING_MAX_SAMPLES 个样本才生效，
      样本不足时回退默认值，保证「数据不足按固定标准跑、数据够了才按个人标准跑」。
    """
    out = {}
    for key, meta in PROFILE_PARAMS.items():
        ref = profile.reference(key)
        if meta["kind"] == "numeric":
            if ref["n"] > PENDING_MAX_SAMPLES and ref["median"] is not None:
                out[key] = ref["median"]
            else:
                out[key] = meta["default"]
        else:
            out[key] = ref["mode"] if ref["mode"] is not None else meta["default"]
    return out


def adapt_task_params(params, profile):
    """把个体化档案应用到任务参数（返回新 dict，不修改原值）。

    当前落地两项最通用的适配：
    - action_id 按惯用手镜像；
    - hold_sec 按 hold_sec_scale 缩放（动作慢的孩子放宽完成时限）。
    其余适配（幅度/速度）由动作引擎在特征阈值处调用 scale_threshold 注入。
    """
    adapted = dict(params or {})
    eff = effective_params(profile)
    if adapted.get("action_id"):
        adapted["action_id"] = adapt_action_for_hand(
            adapted["action_id"], eff.get("preferred_hand", "unknown"))
    if adapted.get("hold_sec") is not None:
        scale = eff.get("hold_sec_scale", 1.0)
        adapted["hold_sec"] = round(scale_threshold(adapted["hold_sec"], scale), 2)
    return adapted


# ---------------------------------------------------------------------------
# 档案存储（内存版；数据库持久化见 database/models.py + crud.py）
# ---------------------------------------------------------------------------
class ProfileStore:
    """按 (child_id, task_id) 组织的内存档案仓库。"""

    def __init__(self):
        self._profiles = {}

    def _key(self, child_id, task_id):
        return (child_id, task_id)

    def get(self, child_id, task_id):
        key = self._key(child_id, task_id)
        if key not in self._profiles:
            self._profiles[key] = PersonalProfile(child_id, task_id)
        return self._profiles[key]

    def record(self, child_id, task_id, param_key, value,
               reviewed=False, correct=None):
        p = self.get(child_id, task_id)
        p.record(param_key, value, reviewed=reviewed, correct=correct)
        return p

    def all(self):
        return list(self._profiles.values())
