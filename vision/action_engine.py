# -*- coding: utf-8 -*-
"""
星伴AI 声明式动作识别引擎（可无限扩展，加动作=改 JSON，不写代码）

核心思想：人的动作是无限的，不可能逐个手写。因此把动作拆成
"原子特征 + 规则组合"，每个动作只是一条 JSON 规则。

原子特征（每帧从姿态关键点算出一个标量）：
    dy      a.y - b.y      （a 相对 b 的高低，负=更高）
    dx      a.x - b.x      （a 相对 b 的左右）
    dist    a 与 b 的距离
    ratio   dist(a,b) / dist(c,d)  （距离比，对距离远近免疫）
    angle   以 b 为顶点的夹角（度）

规则：多个条件 AND 组合，每个条件 {f,a,b[,c,d],op,val}，op ∈ < > <= >=。

点引用：整数索引、"mid:i:j"（中点）、"hc:L"/"hc:R"（手掌中心）、
        "chest"/"belly"（胸/腹中心）。

动作定义在 data/actions.json，本引擎只负责解释执行。
"""

import json
import math
import os
from collections import namedtuple

from clap_core import point_reliable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTIONS_JSON = os.path.join(ROOT, "data", "actions.json")

Pt = namedtuple("Pt", ["x", "y", "z", "visibility"])

_OPS = {
    "<": lambda v, t: v < t,
    ">": lambda v, t: v > t,
    "<=": lambda v, t: v <= t,
    ">=": lambda v, t: v >= t,
}


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


def _eval(lms, cond):
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
    else:
        raise ValueError(f"未知特征: {f}")
    return _OPS[cond["op"]](v, cond["val"])


def load_actions(path=ACTIONS_JSON):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["actions"]


def _resolve_conflicts(hits, actions):
    """冲突消解：高优先级动作可压制其 excludes 里声明的动作；出现任意
    非 base（非静止姿态）动作时，隐藏所有 base 静止姿态（如"站直"）。

    返回按 actions 原始顺序排列的 id 列表，保证显示顺序稳定。"""
    keep = set(hits)

    # 1) 按优先级从高到低处理 excludes（单方向压制，避免同时报多个重叠动作）
    ordered = sorted((a for a in actions if a["id"] in keep),
                     key=lambda a: a.get("priority", 0), reverse=True)
    for a in ordered:
        if a["id"] not in keep:
            continue
        for ex in a.get("excludes", []):
            keep.discard(ex)

    # 2) 只要存在非静止动作，就隐藏静止姿态（站直等）
    base_ids = {a["id"] for a in actions if a.get("base")}
    if keep - base_ids:
        keep -= base_ids

    return [a["id"] for a in actions if a["id"] in keep]


def detect_actions(lms, actions=None):
    """返回命中的所有动作 id 列表。lms 为原始关键点。

    规则结构：a["rules"] 是一组条件组（组内 AND，组间 OR）。
    例如"摸头"可用左手或右手，写成两组。
    命中后再做冲突消解（excludes / 优先级 / base 静止姿态）。"""
    if not lms:
        return []
    actions = actions if actions is not None else load_actions()
    hits = set()
    for a in actions:
        needed = set()
        for group in a["rules"]:
            for c in group:
                for key in ("a", "b", "c", "d"):
                    if key in c:
                        needed |= _pt_indices(c[key])
        if not all(point_reliable(lms[i]) for i in needed):
            continue
        if any(all(_eval(lms, c) for c in group) for group in a["rules"]):
            hits.add(a["id"])
    return _resolve_conflicts(hits, actions)
