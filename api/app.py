# -*- coding: utf-8 -*-
"""网页端拉起本地桌面训练端（家长在网页点一下即可，无需 bat/命令行）。

安全：仅允许本机（127.0.0.1）调用，避免局域网设备远程启动桌面程序。
未安装 PySide6 或路径异常时优雅返回错误，不影响网页主流程。
"""

import os
import subprocess
import sys

from fastapi import APIRouter, Request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
if not os.path.exists(PY):
    PY = sys.executable
DESKTOP = os.path.join(ROOT, "desktop", "main_window.py")

router = APIRouter(prefix="/api/app", tags=["app"])


@router.post("/launch-desktop")
def launch_desktop(req: Request):
    host = req.client.host if req.client else ""
    if host not in ("127.0.0.1", "::1", "localhost"):
        return {"ok": False, "msg": "仅允许本机打开桌面端"}
    if not os.path.exists(DESKTOP):
        return {"ok": False, "msg": "桌面端文件不存在"}
    try:
        creationflags = 0x08000000 if sys.platform == "win32" else 0
        subprocess.Popen([PY, DESKTOP], cwd=ROOT,
                         creationflags=creationflags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"ok": True, "msg": "儿童训练端已启动，请查看桌面窗口"}
    except Exception as e:
        return {"ok": False, "msg": f"启动失败：{e}"}
