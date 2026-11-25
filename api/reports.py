# -*- coding: utf-8 -*-
"""报告 / 统计 / 人工确认接口。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import crud
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


@router.post("/review")
def review(req: ReviewRequest):
    r = crud.add_manual_review(req.vision_record_id, req.reviewer,
                               req.is_correct, req.corrected_result, req.note)
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
