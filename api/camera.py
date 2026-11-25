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


@router.post("/start")
def start_camera():
    """启动摄像头（开始训练时前端可先调用，大屏立即有画面）。"""
    return camera.start()


@router.get("/snapshot_pose")
def snapshot_pose():
    """带骨架的单帧快照（JPEG），桌面端 AI 监控区显示。"""
    frame = camera.get_pose_frame()
    if frame is None:
        return Response(status_code=503)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    if not ok:
        return Response(status_code=500)
    return Response(content=buf.tobytes(), media_type="image/jpeg")


@router.get("/stream_pose")
def stream_pose():
    """MJPEG 流：叠加 MediaPipe 骨架线条的画面（训练大屏用）。"""

    def gen():
        while True:
            frame = camera.get_pose_frame()
            if frame is not None:
                ok, buf = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ok:
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                           + buf.tobytes() + b"\r\n")

    return StreamingResponse(
        gen(), media_type="multipart/x-mixed-replace; boundary=frame")


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
