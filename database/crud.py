# -*- coding: utf-8 -*-
"""数据库 CRUD 函数（供 API 层调用，每个函数独立会话）。"""

import datetime

from sqlalchemy import func

from core.personalization import PROFILE_PARAMS
from database import models
from database.db import SessionLocal


# ---------- 儿童档案 ----------
def list_children():
    db = SessionLocal()
    try:
        return db.query(models.ChildInfo).order_by(models.ChildInfo.id).all()
    finally:
        db.close()


def get_or_create_child(nickname="匿名儿童"):
    db = SessionLocal()
    try:
        c = db.query(models.ChildInfo).filter_by(nickname=nickname).first()
        if not c:
            c = models.ChildInfo(nickname=nickname)
            db.add(c)
            db.commit()
            db.refresh(c)
        return c
    finally:
        db.close()


def create_child(nickname, birth_year=None, gender=None, notes=None):
    db = SessionLocal()
    try:
        c = models.ChildInfo(nickname=nickname, birth_year=birth_year,
                             gender=gender, notes=notes)
        db.add(c)
        db.commit()
        db.refresh(c)
        return c
    finally:
        db.close()


def update_child(child_id, nickname=None, birth_year=None, gender=None,
                 notes=None):
    db = SessionLocal()
    try:
        c = db.get(models.ChildInfo, child_id)
        if c:
            if nickname is not None:
                c.nickname = nickname
            if birth_year is not None:
                c.birth_year = birth_year
            if gender is not None:
                c.gender = gender
            if notes is not None:
                c.notes = notes
            db.commit()
            db.refresh(c)
        return c
    finally:
        db.close()


def delete_child(child_id):
    """删除儿童档案；存在训练记录时拒绝删除（返回 False）。"""
    db = SessionLocal()
    try:
        c = db.get(models.ChildInfo, child_id)
        if not c:
            return False
        n = (db.query(models.TrainingSession)
             .filter_by(child_id=child_id).count())
        if n > 0:
            return False
        db.delete(c)
        db.commit()
        return True
    finally:
        db.close()


# ---------- 任务库 ----------
def list_tasks():
    db = SessionLocal()
    try:
        return db.query(models.TrainingTask).order_by(
            models.TrainingTask.category,
            models.TrainingTask.difficulty).all()
    finally:
        db.close()


def get_task_by_task_id(task_id):
    db = SessionLocal()
    try:
        return db.query(models.TrainingTask).filter_by(task_id=task_id).first()
    finally:
        db.close()


# ---------- 场景 ----------
def list_scenes():
    db = SessionLocal()
    try:
        return db.query(models.SceneInfo).order_by(models.SceneInfo.id).all()
    finally:
        db.close()


def get_scene_by_name(name):
    db = SessionLocal()
    try:
        return db.query(models.SceneInfo).filter_by(name=name).first()
    finally:
        db.close()


# ---------- 训练会话 ----------
def create_session(session_code, child_id, task_id, scene_id, prompt_level=0):
    db = SessionLocal()
    try:
        s = models.TrainingSession(
            session_code=session_code, child_id=child_id, task_id=task_id,
            scene_id=scene_id, prompt_level=prompt_level, status="running")
        db.add(s)
        db.commit()
        db.refresh(s)
        return s
    finally:
        db.close()


def get_session(session_id):
    db = SessionLocal()
    try:
        return db.get(models.TrainingSession, session_id)
    finally:
        db.close()


def get_session_by_code(session_code):
    db = SessionLocal()
    try:
        return db.query(models.TrainingSession).filter_by(
            session_code=session_code).first()
    finally:
        db.close()


def update_session(session_id, **kwargs):
    db = SessionLocal()
    try:
        s = db.get(models.TrainingSession, session_id)
        if s:
            for k, v in kwargs.items():
                setattr(s, k, v)
            db.commit()
        return s
    finally:
        db.close()


def list_recent_sessions(limit=20):
    db = SessionLocal()
    try:
        return db.query(models.TrainingSession).order_by(
            models.TrainingSession.id.desc()).limit(limit).all()
    finally:
        db.close()


# ---------- 动作记录 ----------
def add_action_record(session_id, step_order=None, step_name=None,
                      action_id=None, detected=False, confidence=None):
    db = SessionLocal()
    try:
        r = models.ActionRecord(
            session_id=session_id, step_order=step_order, step_name=step_name,
            action_id=action_id, detected=detected, confidence=confidence)
        db.add(r)
        db.commit()
        db.refresh(r)
        return r
    finally:
        db.close()


# ---------- 视觉记录 + 人工确认（人机协同：分开存储） ----------
def add_vision_record(session_id, model_version_id=None, raw_result=None,
                      confidence=None, uncertainty=False, uncertainty_reason=None):
    db = SessionLocal()
    try:
        r = models.VisionRecord(
            session_id=session_id, model_version_id=model_version_id,
            raw_result=raw_result, confidence=confidence,
            uncertainty=uncertainty, uncertainty_reason=uncertainty_reason)
        db.add(r)
        db.commit()
        db.refresh(r)
        return r
    finally:
        db.close()


def list_vision_records(limit=100, pending_only=False):
    db = SessionLocal()
    try:
        q = db.query(models.VisionRecord).order_by(models.VisionRecord.id.desc())
        if pending_only:
            reviewed = db.query(models.ManualReview.vision_record_id).subquery()
            q = q.filter(models.VisionRecord.uncertain.is_(True)).filter(
                ~models.VisionRecord.id.in_(reviewed))
        return q.limit(limit).all()
    finally:
        db.close()


def add_manual_review(vision_record_id, reviewer="家长", is_correct=True,
                      corrected_result=None, note=None):
    db = SessionLocal()
    try:
        r = models.ManualReview(
            vision_record_id=vision_record_id, reviewer=reviewer,
            is_correct=is_correct, corrected_result=corrected_result, note=note)
        db.add(r)
        db.commit()
        db.refresh(r)
        return r
    finally:
        db.close()


def list_manual_reviews(limit=100):
    db = SessionLocal()
    try:
        return db.query(models.ManualReview).order_by(
            models.ManualReview.id.desc()).limit(limit).all()
    finally:
        db.close()


# ---------- 辅助建议 ----------
def add_recommendation(session_id=None, advice_type=None, text=None,
                       pdi=None, independent_rate=None, completion_rate=None):
    db = SessionLocal()
    try:
        r = models.Recommendation(
            session_id=session_id, advice_type=advice_type, text=text,
            pdi=pdi, independent_rate=independent_rate,
            completion_rate=completion_rate)
        db.add(r)
        db.commit()
        db.refresh(r)
        return r
    finally:
        db.close()


def list_recommendations(limit=20):
    db = SessionLocal()
    try:
        return db.query(models.Recommendation).order_by(
            models.Recommendation.id.desc()).limit(limit).all()
    finally:
        db.close()


# ---------- 模型版本 ----------
def list_model_versions():
    db = SessionLocal()
    try:
        return db.query(models.ModelVersion).order_by(models.ModelVersion.id).all()
    finally:
        db.close()


# ---------- 个体化档案（个体化适应） ----------
def upsert_personal_profile(child_id, task_id, param_key, param_kind="numeric",
                            samples=None, reviews=None, status="pending",
                            confidence=0.0):
    """新增或更新某个孩子×任务×参数的个体化档案。

    task_id 为 task_definition.id（Integer）；纯逻辑 PersonalProfile 里的
    字符串 task_id 由服务层通过 get_task_by_task_id 转换为主键 id 后传入。
    """
    db = SessionLocal()
    try:
        r = (db.query(models.PersonalProfile)
             .filter_by(child_id=child_id, task_id=task_id, param_key=param_key)
             .first())
        if r is None:
            r = models.PersonalProfile(child_id=child_id, task_id=task_id,
                                       param_key=param_key)
            db.add(r)
        r.param_kind = param_kind
        r.samples = list(samples or [])
        r.reviews = list(reviews or [])
        r.status = status
        r.confidence = confidence
        db.commit()
        db.refresh(r)
        return r
    finally:
        db.close()


def get_personal_profile(child_id, task_id, param_key):
    db = SessionLocal()
    try:
        return (db.query(models.PersonalProfile)
                .filter_by(child_id=child_id, task_id=task_id,
                           param_key=param_key)
                .first())
    finally:
        db.close()


def list_personal_profiles(child_id=None, task_id=None):
    db = SessionLocal()
    try:
        q = db.query(models.PersonalProfile)
        if child_id is not None:
            q = q.filter(models.PersonalProfile.child_id == child_id)
        if task_id is not None:
            q = q.filter(models.PersonalProfile.task_id == task_id)
        return q.order_by(models.PersonalProfile.id).all()
    finally:
        db.close()


def sync_personal_profile_from_logic(profile):
    """把纯逻辑 PersonalProfile 对象同步入库。

    profile.task_id 约定为 task_definition.id（Integer），由调用方完成转换；
    每个参数的 status/confidence 由 profile 实时计算后回填。
    """
    db = SessionLocal()
    try:
        for param_key, slot in profile._params.items():
            row = (db.query(models.PersonalProfile)
                   .filter_by(child_id=profile.child_id, task_id=profile.task_id,
                              param_key=param_key)
                   .first())
            if row is None:
                row = models.PersonalProfile(child_id=profile.child_id,
                                             task_id=profile.task_id,
                                             param_key=param_key)
                db.add(row)
            row.param_kind = PROFILE_PARAMS.get(param_key, {}).get("kind", "numeric")
            row.samples = list(slot["samples"])
            row.reviews = list(slot["reviews"])
            row.status = profile.status(param_key)
            row.confidence = profile.confidence(param_key)
        db.commit()
    finally:
        db.close()
