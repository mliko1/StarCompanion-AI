# -*- coding: utf-8 -*-
"""数据库模型：11 张规范表（数据库应用设计大赛核心设计）。

表名与《星伴AI项目升级修改建议与实施路线》文档一致：
child_profile / task_definition / task_step / scene_info / training_session /
step_event / prompt_record / vision_result / manual_review / analysis_result / model_version

设计要点：
1. AI 识别结果（vision_result）与人工确认（manual_review）分开存储，
   人工修正只新增记录，不覆盖原始模型结果。
2. 提示等级（0 独立 / 1 视觉 / 2 语音 / 3 动作示范 / 4 家长协助）
   带 CHECK 约束，只记录、不自动决定减辅助。
3. 记录模型版本（model_version）与任务版本（task_version），
   便于比较不同版本的识别效果。
"""

import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database.db import Base


def now():
    return datetime.datetime.now()


class ChildInfo(Base):
    """匿名儿童档案（保护隐私，只存昵称与出生年份）。"""
    __tablename__ = "child_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nickname = Column(String(64), nullable=False, unique=True)
    birth_year = Column(Integer)
    gender = Column(String(8))
    notes = Column(Text)
    created_at = Column(DateTime, default=now)

    sessions = relationship("TrainingSession", back_populates="child")


class TrainingTask(Base):
    """训练任务定义（动作类 action / 生活技能类 skill）。"""
    __tablename__ = "task_definition"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), nullable=False, unique=True)
    name = Column(String(128), nullable=False)
    type = Column(String(16), nullable=False)
    params = Column(JSON)
    difficulty = Column(Integer, default=1)
    category = Column(String(32))
    steps = Column(JSON)
    task_version = Column(String(32), default="1.0")  # 任务版本
    created_at = Column(DateTime, default=now)

    steps_rel = relationship("TaskStep", back_populates="task",
                             cascade="all, delete-orphan")


class TaskStep(Base):
    """训练任务步骤（生活技能类任务的分解步骤）。"""
    __tablename__ = "task_step"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("task_definition.id"), nullable=False)
    step_order = Column(Integer, nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(Text)
    timeout_sec = Column(Float, default=30.0)

    task = relationship("TrainingTask", back_populates="steps_rel")


class SceneInfo(Base):
    """家庭场景信息（客厅/卧室/餐桌等）。"""
    __tablename__ = "scene_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, unique=True)
    description = Column(Text)
    created_at = Column(DateTime, default=now)


class ModelVersion(Base):
    """模型版本信息（用于不同版本识别效果对比）。"""
    __tablename__ = "model_version"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    version = Column(String(32), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=now)


class TrainingSession(Base):
    """训练记录（一次训练一条，含状态与结果）。"""
    __tablename__ = "training_session"
    __table_args__ = (
        CheckConstraint("prompt_level >= 0 AND prompt_level <= 4",
                        name="ck_prompt_level"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_code = Column(String(64), nullable=False, unique=True)
    child_id = Column(Integer, ForeignKey("child_profile.id"))
    task_id = Column(Integer, ForeignKey("task_definition.id"))
    scene_id = Column(Integer, ForeignKey("scene_info.id"))
    prompt_level = Column(Integer, default=0)
    status = Column(String(16), default="running")
    start_time = Column(DateTime, default=now)
    end_time = Column(DateTime)
    elapsed_sec = Column(Float, default=0.0)
    completed = Column(Boolean, default=False)
    valid = Column(Boolean, default=True)
    uncertainty_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=now)

    child = relationship("ChildInfo", back_populates="sessions")
    task = relationship("TrainingTask")
    scene = relationship("SceneInfo")


class ActionRecord(Base):
    """步骤事件记录（训练过程中逐步骤的动作/步骤判定结果）。"""
    __tablename__ = "step_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("training_session.id"), nullable=False)
    step_order = Column(Integer)
    step_name = Column(String(128))
    action_id = Column(String(64))
    detected = Column(Boolean, default=False)
    confidence = Column(Float)
    timestamp = Column(DateTime, default=now)


class PromptRecord(Base):
    """提示等级变更记录（记录每次提示等级调整，可追溯）。"""
    __tablename__ = "prompt_record"
    __table_args__ = (
        CheckConstraint("prompt_level >= 0 AND prompt_level <= 4",
                        name="ck_prompt_level"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("training_session.id"), nullable=False)
    prompt_level = Column(Integer, nullable=False)
    changed_at = Column(DateTime, default=now)
    reason = Column(Text)


class VisionRecord(Base):
    """视觉识别结果（AI 原始结果，不被人工修正覆盖）。"""
    __tablename__ = "vision_result"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("training_session.id"))
    model_version_id = Column(Integer, ForeignKey("model_version.id"))
    raw_result = Column(JSON)
    confidence = Column(Float)
    uncertainty = Column(Boolean, default=False)
    uncertainty_reason = Column(Text)
    data_quality = Column(String(32))  # good / uncertain / missing 等
    timestamp = Column(DateTime, default=now)


class ManualReview(Base):
    """人工确认记录（与 AI 结果分开，只新增、不覆盖原始结果）。"""
    __tablename__ = "manual_review"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vision_record_id = Column(Integer, ForeignKey("vision_result.id"), nullable=False)
    reviewer = Column(String(64))
    is_correct = Column(Boolean, nullable=False)
    corrected_result = Column(JSON)
    note = Column(Text)
    created_at = Column(DateTime, default=now)


class Recommendation(Base):
    """分析结果记录（规则决策引擎输出的辅助建议，可追溯）。"""
    __tablename__ = "analysis_result"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("training_session.id"))
    advice_type = Column(String(32))
    text = Column(Text)
    pdi = Column(Float)
    independent_rate = Column(Float)
    completion_rate = Column(Float)
    created_at = Column(DateTime, default=now)
