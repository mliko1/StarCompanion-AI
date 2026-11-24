# -*- coding: utf-8 -*-
"""家庭校准接口：开始展示（自动采集）/ 结束展示（自动训练）/ 状态 / 模型列表。"""

from fastapi import APIRouter
from pydantic import BaseModel

from services.calibration_service import calibration, list_models

router = APIRouter(prefix="/api/calibration", tags=["calibration"])


class CollectRequest(BaseModel):
    class_name: str


@router.get("/models")
def models():
    return {"models": list_models()}


@router.get("/status")
def status():
    return calibration.status()


@router.post("/collect/start")
def start_collect(req: CollectRequest):
    return calibration.start_collect(req.class_name)


@router.post("/finish")
def finish():
    """结束展示，自动开始训练（无需指定轮数，自动训练到收敛）。"""
    return calibration.finish_and_train()


@router.post("/stop")
def stop():
    """放弃本次展示（不训练）。"""
    return calibration.stop()
