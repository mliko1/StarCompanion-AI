# -*- coding: utf-8 -*-
"""报告 / 统计 / 人工确认接口。"""

from fastapi import APIRouter
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
    return {"ok": True, "id": r.id}
