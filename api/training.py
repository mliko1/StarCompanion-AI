# -*- coding: utf-8 -*-
"""训练控制接口：开始 / 暂停 / 恢复 / 结束 / 状态。"""

from fastapi import APIRouter
from pydantic import BaseModel

from services.training_service import training

router = APIRouter(prefix="/api/training", tags=["training"])


class StartRequest(BaseModel):
    task_id: str
    child_id: int | None = None
    scene_id: int | None = None
    prompt_level: int = 0
    hold_sec: float = 2.0


class StartPlanRequest(BaseModel):
    task_ids: list[str]
    child_id: int | None = None
    scene_id: int | None = None
    prompt_level: int = 0
    hold_sec: float = 2.0


@router.post("/start")
def start(req: StartRequest):
    return training.start(req.task_id, req.child_id, req.scene_id,
                          req.prompt_level, req.hold_sec)


@router.post("/start_plan")
def start_plan(req: StartPlanRequest):
    """方案模式：依次连续训练多个动作（练完一个自动进入下一个）。"""
    return training.start_plan(req.task_ids, req.child_id, req.scene_id,
                               req.prompt_level, req.hold_sec)


@router.post("/pause")
def pause():
    return training.pause()


@router.post("/resume")
def resume():
    return training.resume()


@router.post("/stop")
def stop():
    return training.stop()


@router.get("/status")
def status():
    return training.status()
