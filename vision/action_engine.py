# -*- coding: utf-8 -*-
"""
星伴AI 声明式动作识别引擎（可无限扩展，加动作=改 JSON，不写代码）

核心思想：人的动作是无限的，不可能逐个手写。因此把动作拆成
"原子特征 + 规则组合"，每个动作只是一条 JSON 规则。

原子特征（每帧从姿态关键点算出一个标量）：
    dy       a.y - b.y      （a 相对 b 的高低，负=更高）
    dx       a.x - b.x      （a 相对 b 的左右）
    dist     a 与 b 的距离
    ratio    dist(a,b) / dist(c,d)  （距离比，对距离远近免疫）
    angle    以 b 为顶点的夹角（度）
    dy_ratio (b.y - a.y) / dist(c,d)（肩宽归一化的高低比，正值= a 比 b 高）
    vis      a 的可见性（置信度）

规则：多个条件 AND 组合，每个条件 {f,a,b[,c,d],op,val}，op ∈ < > <= >=。
动作级字段 min_visibility：该动作所有关键点的可见性门槛（默认 0.3），
用于置信度门控（P1 多条件举手对肩/肘/腕要求更高可见性）。

点引用：整数索引、"mid:i:j"（中点）、"hc:L"/"hc:R"（手掌中心）、
        "chest"/"belly"（胸/腹中心）。

动作定义在 data/actions.json，本引擎只负责解释执行。
"""

import json
import math
import os
from collections import namedtuple

from clap_core import point_reliable
from action_base import clap_check, ClapCounter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTIONS_JSON = os.path.join(ROOT, "data", "actions.json")

Pt = namedtuple("Pt", ["x", "y", "z", "visibility"])

_OPS = {
    "<": lambda v, t: v < t,
    ">": lambda v, t: v > t,
    "<=": lambda v, t: v <= t,
    ">=": lambda v, t: v >= t,
}

# 个体化幅度缩放作用于「幅度/伸直程度类」特征：
#   dy_ratio 肩宽归一化高低比（举手"手腕高出肩"的核心特征）
#   ratio    距离比（拍手"掌心距/肩宽"的核心特征）
#   angle    关节夹角（举手"手臂伸直"的核心特征，仅放宽 >/>=，见下）
# 方向性（dx）与可见性（vis）等特征不做缩放，避免误判。
AMPLITUDE_FEATURES = {"dy_ratio", "ratio", "angle"}


def _scaled_val(f, op, val, scale):
    """个体化幅度缩放：scale<1 表示孩子动作幅度小，放宽判定。

    op 为 >/>= 时降低阈值、</<= 时提高阈值，保证 scale<1 更宽松；
    scale=1.0 或非幅度类特征时原样返回（默认行为完全不变）。
    angle 的 </<=（如"摸头"肘角<130）不缩放，避免把干扰动作一起放宽；
    只放宽 >/>=（如"举手"肘角>90），适配手臂没完全伸直的孩子。
    """
    if scale == 1.0 or f not in AMPLITUDE_FEATURES:
        return val
    if f == "angle" and op in ("<", "<="):
        return val
    if op in ("<", "<="):
        return val / scale
    return val * scale


def _pt_indices(p):
    """返回点引用涉及的关键点索引集合。"""
    if isinstance(p, int):
        return {p}
    if p.startswith("mid:"):
        _, i, j = p.split(":")
        return {int(i), int(j)}
    if p == "hc:L":
        return {15, 17, 19, 21}
    if p == "hc:R":
        return {16, 18, 20, 22}
    if p in ("chest", "belly"):
        return {11, 12, 23, 24}
    raise ValueError(f"未知点引用: {p}")


def _resolve(lms, p):
    """点引用 -> Pt 坐标。"""
    if isinstance(p, int):
        lm = lms[p]
        return Pt(lm.x, lm.y, lm.z, lm.visibility)
    if p.startswith("mid:"):
        _, i, j = p.split(":")
        i, j = int(i), int(j)
        return Pt((lms[i].x + lms[j].x) / 2, (lms[i].y + lms[j].y) / 2,
                  0.0, min(lms[i].visibility, lms[j].visibility))
    if p == "hc:L":
        idx = [15, 17, 19, 21]
    elif p == "hc:R":
        idx = [16, 18, 20, 22]
    elif p == "chest":
        idx = [11, 12]          # 双肩中点
    else:                        # belly：躯干中心（肩+髋平均）
        idx = [11, 12, 23, 24]
    return Pt(sum(lms[i].x for i in idx) / len(idx),
              sum(lms[i].y for i in idx) / len(idx),
              0.0, min(lms[i].visibility for i in idx))


def _hypot(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def _angle(a, b, c):
    ba = (a.x - b.x, a.y - b.y)
    bc = (c.x - b.x, c.y - b.y)
    na = math.hypot(*ba)
    nc = math.hypot(*bc)
    if na < 1e-6 or nc < 1e-6:
        return 0.0
    cos = max(-1.0, min(1.0, (ba[0] * bc[0] + ba[1] * bc[1]) / (na * nc)))
    return math.degrees(math.acos(cos))


def _eval(lms, cond, scale=1.0):
    f = cond["f"]
    if f == "dy":
        v = _resolve(lms, cond["a"]).y - _resolve(lms, cond["b"]).y
    elif f == "dx":
        v = _resolve(lms, cond["a"]).x - _resolve(lms, cond["b"]).x
    elif f == "dist":
        v = _hypot(_resolve(lms, cond["a"]), _resolve(lms, cond["b"]))
    elif f == "ratio":
        v = _hypot(_resolve(lms, cond["a"]), _resolve(lms, cond["b"])) / \
            max(_hypot(_resolve(lms, cond["c"]), _resolve(lms, cond["d"])), 1e-6)
    elif f == "angle":
        v = _angle(_resolve(lms, cond["a"]), _resolve(lms, cond["b"]),
                   _resolve(lms, cond["c"]))
    elif f == "dy_ratio":
        # 肩宽归一化的高低比：(b.y - a.y) / dist(c, d)，正值= a 比 b 高。
        # 对人物远近/体型免疫（P1 多条件举手用）。
        v = (_resolve(lms, cond["b"]).y - _resolve(lms, cond["a"]).y) / \
            max(_hypot(_resolve(lms, cond["c"]), _resolve(lms, cond["d"])), 1e-6)
    elif f == "vis":
        # 关键点可见性（置信度），供规则内显式门控。
        v = _resolve(lms, cond["a"]).visibility
    else:
        raise ValueError(f"未知特征: {f}")
    val = _scaled_val(f, cond["op"], cond["val"], scale)
    return _OPS[cond["op"]](v, val)


def load_actions(path=ACTIONS_JSON):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["actions"]


def _resolve_conflicts(hits, actions, protect=None):
    """冲突消解：高优先级动作可压制其 excludes 里声明的动作；出现任意
    非 base（非静止姿态）动作时，隐藏所有 base 静止姿态（如"站直"）。

    protect：受保护的动作 id 集合（当前训练目标），任何动作都不得压制它们。
    解决"孩子做对了目标动作，却被相似动作（如摸头）的 excludes 抹掉"的问题。

    返回按 actions 原始顺序排列的 id 列表，保证显示顺序稳定。"""
    keep = set(hits)
    protected = set(protect or ())

    # 1) 按优先级从高到低处理 excludes（单方向压制，避免同时报多个重叠动作）
    ordered = sorted((a for a in actions if a["id"] in keep),
                     key=lambda a: a.get("priority", 0), reverse=True)
    for a in ordered:
        if a["id"] not in keep:
            continue
        for ex in a.get("excludes", []):
            if ex in protected:
                continue
            keep.discard(ex)

    # 2) 只要存在非静止动作，就隐藏静止姿态（站直等）
    base_ids = {a["id"] for a in actions if a.get("base")}
    if keep - base_ids:
        keep -= base_ids

    return [a["id"] for a in actions if a["id"] in keep]


def detect_actions(lms, actions=None, amplitude_scale=1.0,
                   allowed=None, protect=None):
    """返回命中的所有动作 id 列表。lms 为原始关键点。

    规则结构：a["rules"] 是一组条件组（组内 AND，组间 OR）。
    例如"摸头"可用左手或右手，写成两组。
    命中后再做冲突消解（excludes / 优先级 / base 静止姿态）。

    amplitude_scale：个体化幅度缩放，<1 表示孩子动作幅度小，
    对 dy_ratio/ratio/angle(仅 >/>=) 阈值放宽判定；默认 1.0 不变。
    allowed：动作白名单（id 集合）。训练单个动作时只检测目标动作，
    从源头避免"摸头"等相似动作抢判定；None 表示全量检测（兼容旧调用）。
    protect：受保护动作 id 集合，冲突消解时不得被压制。
    """
    if not lms:
        return []
    actions = actions if actions is not None else load_actions()
    allow_set = set(allowed) if allowed is not None else None
    hits = set()
    for a in actions:
        if allow_set is not None and a["id"] not in allow_set:
            continue
        needed = set()
        for group in a["rules"]:
            for c in group:
                for key in ("a", "b", "c", "d"):
                    if key in c:
                        needed |= _pt_indices(c[key])
        if not all(point_reliable(lms[i], min_visibility=a.get("min_visibility", 0.3))
                   for i in needed):
            continue
        if any(all(_eval(lms, c, amplitude_scale) for c in group)
               for group in a["rules"]):
            hits.add(a["id"])
    return _resolve_conflicts(hits, actions, protect=protect)


class ActionTracker:
    """有状态动作检测器：detect_actions + 拍手骤降防伪 + 稳定性确认。

    - clap 是瞬时动作：追加骤降防伪，只有合拢前 0.35 秒内比例快速骤降
      才认定命中，避免缓慢靠近被误判为拍手；
    - 其他动作：连续 stable_frames 帧命中才输出，避免单帧抖动/误触被记录；
    - allowed 白名单：训练单个动作时只检测目标动作，避免相似动作抢判定；
    - protect 保护集：目标动作不被其他动作的 excludes 压制。

    用法：
        tracker = ActionTracker(allowed={"raise_left"}, protect={"raise_left"})
        hits = tracker.detect(lms, now)   # now 为当前时间戳（秒）
    """

    def __init__(self, actions=None, amplitude_scale=1.0, speed_scale=1.0,
                 allowed=None, protect=None, stable_frames=3):
        self.actions = actions if actions is not None else load_actions()
        self.amplitude_scale = amplitude_scale
        self.speed_scale = speed_scale
        self.allowed = allowed
        self.protect = protect
        self.stable_frames = max(1, int(stable_frames))
        self._clap = ClapCounter(speed_scale=speed_scale)
        self._streak = {}

    def reset(self):
        self._clap.reset()
        self._streak.clear()

    def detect(self, lms, now):
        hits = detect_actions(lms, self.actions,
                              amplitude_scale=self.amplitude_scale,
                              allowed=self.allowed, protect=self.protect)
        # 每帧都维护 clap 的 ratio 历史（骤降防伪需要"分开→合拢"的完整
        # 时序，不能只在单帧命中 clap 时才更新，否则高 ratio 入不了历史）。
        contact, ratio = clap_check(lms, self._clap.contact)
        if contact is None:
            self._clap.contact = False
        else:
            self._clap.update(ratio, contact, now)
        # clap 命中 = 单帧规则命中 且 骤降防伪通过（真合拢）
        if "clap" in hits and not self._clap.contact:
            hits = [h for h in hits if h != "clap"]
        # 稳定性确认：非瞬时动作需连续命中 stable_frames 帧才输出，
        # 避免单帧抖动/误触被当成完成；clap 已有骤降防伪，跳过此步。
        stable = []
        for hid in hits:
            if hid == "clap":
                stable.append(hid)
                continue
            self._streak[hid] = self._streak.get(hid, 0) + 1
            if self._streak[hid] >= self.stable_frames:
                stable.append(hid)
        for hid in list(self._streak):
            if hid not in hits:
                del self._streak[hid]
        return stable
