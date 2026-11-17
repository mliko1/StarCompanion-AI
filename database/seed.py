# -*- coding: utf-8 -*-
"""种子数据：任务库导入 + 默认场景/模型/儿童档案（幂等，只插入缺失项）。"""

import json
import os

from database import models
from database.db import SessionLocal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS_JSON = os.path.join(ROOT, "data", "tasks.json")

# 生活技能类任务的 5 个连续行为步骤（与 behavior_sequence 一致）
SKILL_STEPS = [
    {"name": "寻找玩具", "timeout_sec": 30},
    {"name": "接近玩具", "timeout_sec": 30},
    {"name": "拿起玩具", "timeout_sec": 30},
    {"name": "移动玩具", "timeout_sec": 30},
    {"name": "放入收纳盒", "timeout_sec": 45},
]

DEFAULT_SCENES = ["客厅", "卧室", "餐桌", "游戏区"]
DEFAULT_MODELS = [
    {"name": "pose_landmarker", "version": "full",
     "description": "MediaPipe 33 关键点姿态识别（完整版）"},
    {"name": "yolo11n", "version": "1.0",
     "description": "Ultralytics YOLO11n COCO 预训练目标检测"},
]


def seed_tasks():
    db = SessionLocal()
    try:
        if db.query(models.TrainingTask).count() > 0:
            return 0
        if not os.path.exists(TASKS_JSON):
            return 0
        with open(TASKS_JSON, encoding="utf-8") as f:
            data = json.load(f)
        for t in data["tasks"]:
            steps = SKILL_STEPS if t["type"] == "skill" else None
            db.add(models.TrainingTask(
                task_id=t["task_id"], name=t["name"], type=t["type"],
                params=t.get("params"), difficulty=t.get("difficulty", 1),
                category=t.get("category", ""), steps=steps))
        db.commit()
        return len(data["tasks"])
    finally:
        db.close()


def seed_scenes():
    db = SessionLocal()
    try:
        n = 0
        for name in DEFAULT_SCENES:
            if not db.query(models.SceneInfo).filter_by(name=name).first():
                db.add(models.SceneInfo(name=name))
                n += 1
        db.commit()
        return n
    finally:
        db.close()


def seed_models():
    db = SessionLocal()
    try:
        n = 0
        for m in DEFAULT_MODELS:
            if not db.query(models.ModelVersion).filter_by(name=m["name"]).first():
                db.add(models.ModelVersion(**m))
                n += 1
        db.commit()
        return n
    finally:
        db.close()


def seed_child():
    db = SessionLocal()
    try:
        if db.query(models.ChildInfo).count() == 0:
            db.add(models.ChildInfo(nickname="默认儿童"))
            db.commit()
            return 1
        return 0
    finally:
        db.close()


def seed_all():
    return {
        "tasks": seed_tasks(),
        "scenes": seed_scenes(),
        "models": seed_models(),
        "children": seed_child(),
    }
