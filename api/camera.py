# -*- coding: utf-8 -*-
"""摄像头接口：状态 + MJPEG 视频流（供网页 <img> 显示画面）。"""

import cv2
from fastapi import APIRouter
from fastapi.responses import Response, StreamingResponse

from services.camera_service import camera

router = APIRouter(prefix="/api/camera", tags=["camera"])


@router.get("/status")
def status():
    return camera.status()


@router.get("/snapshot")
def snapshot():
    """单帧快照（JPEG），供桌面端显示画面（无需解析 MJPEG 流）。"""
    frame = camera.get_frame()
    if frame is None:
        return Response(status_code=503)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
    if not ok:
        return Response(status_code=500)
    return Response(content=buf.tobytes(), media_type="image/jpeg")


@router.get("/stream")
def stream():
    """MJPEG 流：网页端 <img src="/api/camera/stream"> 即可显示实时画面。"""

    def gen():
        while True:
            frame = camera.get_frame()
            if frame is not None:
                ok, buf = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                if ok:
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                           + buf.tobytes() + b"\r\n")

    return StreamingResponse(
        gen(), media_type="multipart/x-mixed-replace; boundary=frame")
