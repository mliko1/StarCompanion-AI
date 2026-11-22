# -*- coding: utf-8 -*-
"""个体化适应接口：查询个体化档案 + 家长确认惯用手。

惯用手（preferred_hand）是家长/老师明确确认的事实，确认后立即生效；
数值型参数（幅度/时长/速度）由训练过程逐步积累样本收敛，不在此手动设置。
"""

from fastapi import APIRouter
from pydantic import BaseModel

from core.personalization import PersonalProfile
from database import crud

router = APIRouter(prefix="/api/personalization", tags=["personalization"])

_HAND_VALUES = ("left", "right", "both", "unknown")


class ConfirmHandRequest(BaseModel):
    child_id: int
    task_id: str          # 任务字符串 id（如 action_raise_right）
    preferred_hand: str   # left / right / both / unknown
    reviewer: str = "家长"


@router.get("/profiles")
def profiles(child_id: int | None = None, task_id: int | None = None):
    """查询个体化档案（含观察样本/人工确认/状态/置信度）。"""
    rows = crud.list_personal_profiles(child_id=child_id, task_id=task_id)
    return {"profiles": [_profile_to_dict(r) for r in rows]}


@router.post("/confirm_hand")
def confirm_hand(req: ConfirmHandRequest):
    """家长/老师确认孩子完成某任务时的惯用手（确认后立即生效）。"""
    if req.preferred_hand not in _HAND_VALUES:
        return {"ok": False, "msg": f"preferred_hand 取值非法：{req.preferred_hand}"}
    task = crud.get_task_by_task_id(req.task_id)
    if task is None:
        return {"ok": False, "msg": f"任务 {req.task_id} 不存在"}
    profile = _load_profile(req.child_id, task.id)
    profile.record("preferred_hand", req.preferred_hand,
                   reviewed=True, correct=True)
    crud.sync_personal_profile_from_logic(profile)
    return {
        "ok": True,
        "child_id": req.child_id,
        "task_id": req.task_id,
        "preferred_hand": req.preferred_hand,
        "status": profile.status("preferred_hand"),
        "confidence": profile.confidence("preferred_hand"),
    }


def _load_profile(child_id, task_id_int):
    """从数据库加载 (child, task) 个体化档案为纯逻辑 PersonalProfile。"""
    profile = PersonalProfile(child_id, task_id_int)
    rows = crud.list_personal_profiles(child_id=child_id, task_id=task_id_int)
    for r in rows:
        profile.set_slot(r.param_key, r.samples, r.reviews)
    return profile


def _profile_to_dict(r):
    return {
        "id": r.id,
        "child_id": r.child_id,
        "task_id": r.task_id,
        "param_key": r.param_key,
        "param_kind": r.param_kind,
        "samples": r.samples,
        "reviews": r.reviews,
        "status": r.status,
        "confidence": r.confidence,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }
