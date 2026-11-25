# -*- coding: utf-8 -*-
"""
个性化训练方案推荐（针对不同儿童对动作的完成程度，自动制定训练计划）。

核心逻辑：
1. 统计每个动作任务的历史完成率与尝试次数；
2. 完成率 < 50%  → 需要加强（优先安排）；
3. 完成率 50%~99% → 巩固（次之）；
4. 从未练过的动作 → 进阶（按难度从低到高挑 2 个）；
5. 完成率 100%   → 已掌握（最多安排 1 个复习）。

原则：练得越差的越优先练，已经会的少练、不重复无效训练。
"""

from database import models
from database.db import SessionLocal


def build_plan(child_id=None, limit=5):
    db = SessionLocal()
    try:
        # 1. 所有动作类任务
        tasks = (db.query(models.TrainingTask)
                 .filter(models.TrainingTask.type == "action").all())

        # 2. 该儿童的训练记录
        q = db.query(models.TrainingSession)
        if child_id is not None:
            q = q.filter(models.TrainingSession.child_id == child_id)
        sessions = q.all()

        # 3. 按任务统计完成情况
        stats = {}
        for s in sessions:
            if s.task_id is None:
                continue
            st = stats.setdefault(s.task_id, {"tries": 0, "done": 0})
            st["tries"] += 1
            if s.completed:
                st["done"] += 1

        need_improve, consolidate, mastered = [], [], []
        practiced_ids = set()
        for t in tasks:
            st = stats.get(t.id, {"tries": 0, "done": 0})
            if st["tries"] == 0:
                continue
            practiced_ids.add(t.id)
            rate = st["done"] / st["tries"]
            item = {
                "task_id": t.task_id, "name": t.name,
                "difficulty": t.difficulty or 1, "category": t.category,
                "tries": st["tries"], "done": st["done"], "rate": round(rate, 2),
            }
            if rate >= 1.0:
                mastered.append(item)
            elif rate < 0.5:
                need_improve.append(item)
            else:
                consolidate.append(item)

        # 未练过的动作（按难度升序，作为进阶候选）
        fresh = []
        for t in tasks:
            if t.id not in practiced_ids:
                fresh.append({
                    "task_id": t.task_id, "name": t.name,
                    "difficulty": t.difficulty or 1, "category": t.category,
                    "tries": 0, "done": 0, "rate": 0.0,
                })
        fresh.sort(key=lambda x: x["difficulty"])

        # 4. 组装计划（练得越差越靠前）
        need_improve.sort(key=lambda x: (x["rate"], -x["tries"]))
        consolidate.sort(key=lambda x: -x["rate"])
        plan = []
        for item in need_improve:
            plan.append(_entry(item, "strengthen", "该动作完成率偏低，需重点加强"))
        for item in consolidate:
            plan.append(_entry(item, "consolidate", "已初步掌握，继续巩固提高"))
        for item in fresh[:2]:
            plan.append(_entry(item, "new", "新动作，循序渐进进阶"))
        if mastered:
            plan.append(_entry(mastered[0], "review", "已掌握，安排一次复习巩固"))

        return {
            "child_id": child_id,
            "summary": {
                "need_improve": len(need_improve),
                "consolidate": len(consolidate),
                "mastered": len(mastered),
                "fresh": len(fresh),
            },
            "plan": plan[:limit],
        }
    finally:
        db.close()


def _entry(item, kind, reason):
    """生成推荐条目，并给出该动作建议训练次数（轮次）。

    次数规则（与 kind 对应，可直接用于方案连续训练）：
    - strengthen 完成率偏低：3 轮，重点加强；
    - consolidate 巩固：2 轮；
    - new 新动作：2 轮，循序渐进；
    - review 已掌握复习：1 轮。
    另外完成率越低适当加练，最多 5 轮，避免无效重复。
    """
    base = {"strengthen": 3, "consolidate": 2, "new": 2, "review": 1}.get(kind, 2)
    rate = item.get("rate", 0)
    if kind == "strengthen" and rate < 0.25:
        base = 5
    elif kind == "consolidate" and rate >= 0.8:
        base = 1
    return {**item, "kind": kind, "reason": reason, "reps": base}
