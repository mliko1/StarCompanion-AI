# -*- coding: utf-8 -*-
"""星伴AI 后端 FastAPI 应用（v2）：整合训练控制 / 摄像头 / 报告 / 前端。

相对旧版（server/main.py.bak）的变化：
- 新增训练控制（start/pause/resume/stop/status）、摄像头状态与画面流；
- 数据库从原生 sqlite3 3 张表，升级为 SQLAlchemy 11 张规范表；
- 监听 0.0.0.0 + CORS，支持手机/平板通过局域网访问。
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api import calibration as calibration_api
from api import device as device_api
from api import camera as camera_api
from api import personalization as personalization_api
from api import reports as reports_api
from api import training as training_api
from database import crud
from database.db import init_db

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIST = os.path.join(ROOT, "frontend", "dist")

app = FastAPI(title="星伴AI 训练管理后端", version="2.0.0")

# 允许局域网内设备（手机/平板）访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    init_db()


# ---------- 基础接口 ----------
@app.get("/api/status")
def system_status():
    from services.training_service import training
    return {"service": "星伴AI", "training": training.status()}


@app.get("/api/tasks")
def list_tasks():
    return {"tasks": [_task_to_dict(t) for t in crud.list_tasks()]}


@app.get("/api/scenes")
def list_scenes():
    return {"scenes": [_scene_to_dict(s) for s in crud.list_scenes()]}


@app.get("/api/children")
def list_children():
    return {"children": [_child_to_dict(c) for c in crud.list_children()]}


@app.get("/api/plan")
def get_plan(child_id: int | None = None):
    """个性化训练方案推荐（基于该儿童历史完成情况）。"""
    from core.plan import build_plan
    return build_plan(child_id)


# ---------- 注册子路由 ----------
app.include_router(training_api.router)
app.include_router(camera_api.router)
app.include_router(reports_api.router)
app.include_router(personalization_api.router)
app.include_router(calibration_api.router)
app.include_router(device_api.router)


# ---------- 序列化 ----------
def _task_to_dict(t):
    return {
        "id": t.id, "task_id": t.task_id, "name": t.name, "type": t.type,
        "params": t.params, "difficulty": t.difficulty, "category": t.category,
        "steps": t.steps,
    }


def _scene_to_dict(s):
    return {"id": s.id, "name": s.name, "description": s.description}


def _child_to_dict(c):
    return {"id": c.id, "nickname": c.nickname,
            "birth_year": c.birth_year, "gender": c.gender, "notes": c.notes}


class ChildRequest(BaseModel):
    nickname: str
    birth_year: int | None = None
    gender: str | None = None
    notes: str | None = None


@app.post("/api/children")
def create_child(req: ChildRequest):
    c = crud.create_child(req.nickname, req.birth_year, req.gender, req.notes)
    return {"ok": True, "child": _child_to_dict(c)}


@app.put("/api/children/{child_id}")
def update_child(child_id: int, req: ChildRequest):
    c = crud.update_child(child_id, req.nickname, req.birth_year,
                          req.gender, req.notes)
    if not c:
        return {"ok": False, "msg": "档案不存在"}
    return {"ok": True, "child": _child_to_dict(c)}


@app.delete("/api/children/{child_id}")
def delete_child(child_id: int):
    ok = crud.delete_child(child_id)
    return {"ok": ok, "msg": "已删除" if ok else "删除失败：档案不存在或已有训练记录"}


# ---------- 前端挂载 ----------
# 前端构建产物（frontend/dist）随仓库提供，直接挂载
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    @app.get("/")
    def index():
        return ("<h2>前端未构建</h2><p>请进入 frontend 目录执行 "
                "<code>npm install &amp;&amp; npm run build</code></p>")
