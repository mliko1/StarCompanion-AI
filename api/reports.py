# -*- coding: utf-8 -*-
"""报告 / 统计 / 人工确认接口。"""

from fastapi import APIRouter
from pydantic import BaseModel

from database import crud
from services import report_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/dashboard")
def dashboard():
    return report_service.dashboard_stats()


@router.get("/sessions")
def sessions(limit: int = 20):
    return {"sessions": report_service.list_sessions_detailed(limit)}


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
