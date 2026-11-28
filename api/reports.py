# -*- coding: utf-8 -*-
"""报告 / 统计 / 人工确认接口。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import crud
from database.db import SessionLocal as report_session_local
from services import report_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/dashboard")
def dashboard(child_id: int | None = None):
    return report_service.dashboard_stats(child_id)


@router.get("/sessions")
def sessions(limit: int = 20):
    return {"sessions": report_service.list_sessions_detailed(limit)}


@router.get("/session/{session_id}")
def session_report(session_id: int):
    return report_service.session_report(session_id)


@router.get("/professional/{session_id}")
def professional_report(session_id: int):
    """训练结束后的个体化专业报告（给家长查看）。"""
    from services.professional_report import build_professional_report
    return build_professional_report(session_id)


@router.get("/history")
def report_history(child_id: int | None = None, date_from: str | None = None,
                   date_to: str | None = None, limit: int = 100):
    """历史训练报告列表（可按儿童与日期范围筛选）。"""
    from services.professional_report import list_saved
    return {"reports": list_saved(child_id, date_from, date_to, limit)}


@router.get("/saved/{report_id}")
def saved_report(report_id: int):
    """读取已保存的报告快照（训练当场生成的原文）。"""
    from services.professional_report import get_saved
    r = get_saved(report_id)
    if not r:
        raise HTTPException(status_code=404, detail="报告不存在")
    return r


@router.get("/latest_session")
def latest_session(child_id: int | None = None):
    """最近一次训练记录 id（用于事后查看专业报告）。"""
    from database.db import SessionLocal
    from database import models
    db = SessionLocal()
    try:
        q = db.query(models.TrainingSession)
        if child_id is not None:
            q = q.filter(models.TrainingSession.child_id == child_id)
        s = q.order_by(models.TrainingSession.start_time.desc()).first()
        return {"session_id": s.id if s else None}
    finally:
        db.close()


@router.get("/vision")
def vision(limit: int = 100, pending_only: bool = False):
    return {"records": report_service.list_vision_detailed(limit, pending_only)}


class ReviewRequest(BaseModel):
    vision_record_id: int
    reviewer: str = "家长"
    is_correct: bool
    corrected_result: dict | None = None
    note: str | None = None


def _apply_review_to_profile(vision_record_id, req):
    """人工复核回流个体化档案：只首次复核生效，避免重复提交反复改阈值。"""
    from database import models
    from core.personalization import (PersonalProfile, PROFILE_PARAMS,
                                      effective_params)

    db = report_session_local()
    try:
        if (db.query(models.ManualReview)
                .filter_by(vision_record_id=vision_record_id).count() != 1):
            return None
        vr = db.get(models.VisionRecord, vision_record_id)
        if not vr or not vr.session_id:
            return None
        s = db.get(models.TrainingSession, vr.session_id)
        if not s or not s.child_id or not s.task_id:
            return None
        child_id, task_id = s.child_id, s.task_id
    finally:
        db.close()

    profile = PersonalProfile(child_id, task_id)
    for row in crud.list_personal_profiles(child_id=child_id, task_id=task_id):
        profile.set_slot(row.param_key, row.samples, row.reviews)
    corrected = req.corrected_result or {}
    text = " ".join(str(v) for v in corrected.values() if v is not None)

    # 明确给出惯用手（或纠正文本里写了左/右手）时，作为已审核样本记录
    hand = corrected.get("preferred_hand")
    if hand not in PROFILE_PARAMS["preferred_hand"]["values"]:
        hand = None
        if "左手" in text or "_left" in text:
            hand = "left"
        elif "右手" in text or "_right" in text:
            hand = "right"
    if hand:
        profile.record("preferred_hand", hand, reviewed=True, correct=True)

    # 幅度容差：识别正确记录 1.0；识别有误则适度放宽（下限 0.4），
    # 让"孩子动作幅度小导致漏判"在后续训练中逐步得到适配。
    current = effective_params(profile).get("amplitude_scale", 1.0)
    sample = 1.0 if req.is_correct else round(max(0.4, min(1.0, current * 0.85)), 3)
    profile.record("amplitude_scale", sample,
                   reviewed=True, correct=bool(req.is_correct))
    crud.sync_personal_profile_from_logic(profile)
    return sample


@router.post("/review")
def review(req: ReviewRequest):
    r = crud.add_manual_review(req.vision_record_id, req.reviewer,
                               req.is_correct, req.corrected_result, req.note)
    try:
        _apply_review_to_profile(req.vision_record_id, req)
    except Exception as e:
        print(f"[review] 个体化回流失败: {e}")
    # 复核回写（P1-11）：把对应不确定会话标记为已确认，统计不再当作待确认
    try:
        from database.db import SessionLocal
        from database import models
        db = SessionLocal()
        try:
            vr = db.get(models.VisionRecord, req.vision_record_id)
            if vr and vr.session_id:
                s = db.get(models.TrainingSession, vr.session_id)
                if s and s.status == "uncertain":
                    s.status = "confirmed"
                    s.completed = bool(req.is_correct)
                    db.commit()
        finally:
            db.close()
    except Exception:
        pass
    return {"ok": True, "id": r.id}
