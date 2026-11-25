# -*- coding: utf-8 -*-
"""ESP32 智能交互盒接口：连接 / 状态 / LED / 蜂鸣（P2 硬件联动）。

设备未连接时所有调用优雅降级（ok=False），不阻塞训练主流程。
"""

from fastapi import APIRouter
from pydantic import BaseModel

from services import device_service

router = APIRouter(prefix="/api/device", tags=["device"])


class PortRequest(BaseModel):
    port: str = "COM3"


class BuzzRequest(BaseModel):
    ms: int = 500


class LedRequest(BaseModel):
    on: bool = True


@router.get("/status")
def status():
    return device_service.device_status()


@router.post("/connect")
def connect(req: PortRequest):
    return device_service.connect_device(req.port)


@router.post("/disconnect")
def disconnect():
    from hardware.esp32_controller import esp32
    esp32.close()
    return {"ok": True, "msg": "设备已断开"}


@router.post("/led")
def led(req: LedRequest):
    return device_service.set_led(req.on)


@router.post("/buzz")
def buzz(req: BuzzRequest):
    return device_service.buzz(req.ms)
