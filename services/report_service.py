# -*- coding: utf-8 -*-
"""报告统计服务：聚合训练数据，计算 PDI/独立完成率/趋势/建议。"""

from core import decision as dec
from core.plan import build_plan
from database import models
from database.db import SessionLocal


def dashboard_stats(child_id=None):
    """首页仪表盘 + 报告页所需的全部统计（一次查询，可按儿童过滤）。"""
    db = SessionLocal()
    try:
        q = db.query(models.TrainingSession)
        if child_id is not None:
            q = q.filter(models.TrainingSession.child_id == child_id)
        sessions = q.all()
        total = len(sessions)
        completed = sum(1 for s in sessions if s.completed)
        completion_rate = round(completed / total, 3) if total else 0.0

        valid_sessions = [s for s in sessions if s.valid]
        n_valid = len(valid_sessions)
        pdi = round(dec.compute_pdi([s.prompt_level for s in valid_sessions]), 3)
        indep_rate = round(dec.independent_rate(
            _as_decision_rows(valid_sessions)), 3)
        unc_count = sum(1 for s in valid_sessions if s.uncertainty_count > 0)
        unc_ratio = round(unc_count / n_valid, 3) if n_valid else 0.0

        dist = [0] * 5
        for s in valid_sessions:
            if s.prompt_level is not None:
                dist[s.prompt_level] += 1

        scene_map = {}
        by_day = {}
        for s in sessions:
            scene = s.scene.name if s.scene else "未标注"
            d = scene_map.setdefault(scene, {"count": 0, "done": 0})
            d["count"] += 1
            d["done"] += 1 if s.completed else 0

            day = s.created_at.strftime("%Y-%m-%d") if s.created_at else "未知"
            dd = by_day.setdefault(day, {"count": 0, "done": 0})
            dd["count"] += 1
            dd["done"] += 1 if s.completed else 0

        trend = dec.trend_of([1 if s.completed else 0 for s in sessions])
        suggestions = dec.suggest(_as_decision_rows(valid_sessions),
                                  uncertainty_ratio=unc_ratio, trend=trend)

        return {
            "total": total,
            "completed": completed,
            "completion_rate": completion_rate,
            "pdi": pdi,
            "independent_rate": indep_rate,
            "uncertainty_ratio": unc_ratio,
            "n_valid": n_valid,
            "prompt_distribution": dist,
            "prompt_labels": ["独立", "视觉", "语音", "示范", "家长协助"],
            "scene_breakdown": [
                {"scene": k, "count": v["count"], "done": v["done"]}
                for k, v in scene_map.items()],
            "trend": [
                {"day": k, "count": v["count"], "done": v["done"]}
                for k, v in sorted(by_day.items())],
            "suggestions": suggestions,
            "interpretation": _interpret(total, completion_rate, pdi,
                                          indep_rate, unc_ratio),
            "plan": build_plan(child_id)["plan"],
        }
    finally:
        db.close()


def list_sessions_detailed(limit=20):
    """最近训练记录（带任务名/场景/儿童昵称）。"""
    db = SessionLocal()
    try:
        rows = (db.query(models.TrainingSession, models.TrainingTask.name,
                         models.SceneInfo.name, models.ChildInfo.nickname)
                .outerjoin(models.TrainingTask,
                           models.TrainingSession.task_id == models.TrainingTask.id)
                .outerjoin(models.SceneInfo,
                           models.TrainingSession.scene_id == models.SceneInfo.id)
                .outerjoin(models.ChildInfo,
                           models.TrainingSession.child_id == models.ChildInfo.id)
                .order_by(models.TrainingSession.id.desc())
                .limit(limit).all())
        out = []
        for s, task_name, scene_name, child_name in rows:
            out.append({
                "id": s.id, "session_code": s.session_code,
                "task_name": task_name, "scene": scene_name, "child": child_name,
                "prompt_level": s.prompt_level, "status": s.status,
                "start_time": _iso(s.start_time), "end_time": _iso(s.end_time),
                "elapsed_sec": s.elapsed_sec, "completed": s.completed,
                "valid": s.valid, "uncertainty_count": s.uncertainty_count,
            })
        return out
    finally:
        db.close()


def list_vision_detailed(limit=100, pending_only=False):
    """视觉识别记录（含模型名；pending_only 只返回待人工确认的不确定记录）。"""
    db = SessionLocal()
    try:
        q = (db.query(models.VisionRecord, models.ModelVersion.name)
             .outerjoin(models.ModelVersion,
                        models.VisionRecord.model_version_id == models.ModelVersion.id)
             .order_by(models.VisionRecord.id.desc()))
        if pending_only:
            reviewed = db.query(models.ManualReview.vision_record_id).subquery()
            q = q.filter(models.VisionRecord.uncertain.is_(True)).filter(
                ~models.VisionRecord.id.in_(reviewed))
        rows = q.limit(limit).all()
        out = []
        for v, mv_name in rows:
            out.append({
                "id": v.id, "session_id": v.session_id, "model": mv_name,
                "raw_result": v.raw_result, "confidence": v.confidence,
                "uncertainty": v.uncertainty, "uncertainty_reason": v.uncertainty_reason,
                "timestamp": _iso(v.timestamp),
            })
        return out
    finally:
        db.close()


def _as_decision_rows(sessions):
    return [
        {"completed": s.completed, "prompt_level": s.prompt_level, "valid": s.valid}
        for s in sessions
    ]


def _iso(dt):
    return dt.isoformat() if dt else None


def session_report(session_id):
    """单次训练报告：训练结束后反馈给家长的详细分析。"""
    db = SessionLocal()
    try:
        s = db.get(models.TrainingSession, session_id)
        if not s:
            return None
        task = db.get(models.TrainingTask, s.task_id) if s.task_id else None
        scene = db.get(models.SceneInfo, s.scene_id) if s.scene_id else None
        child = db.get(models.ChildInfo, s.child_id) if s.child_id else None
        steps = (db.query(models.ActionRecord)
                 .filter_by(session_id=session_id)
                 .order_by(models.ActionRecord.step_order).all())

        prompt_labels = ["独立", "视觉", "语音", "示范", "家长协助"]
        prompt_label = (prompt_labels[s.prompt_level]
                        if s.prompt_level is not None and 0 <= s.prompt_level < 5
                        else None)

        return {
            "session_id": s.id,
            "task_name": task.name if task else None,
            "task_type": task.type if task else None,
            "scene": scene.name if scene else None,
            "child": child.nickname if child else None,
            "prompt_level": s.prompt_level,
            "prompt_label": prompt_label,
            "completed": s.completed,
            "elapsed_sec": s.elapsed_sec,
            "steps": [
                {"order": st.step_order, "name": st.step_name,
                 "detected": st.detected, "confidence": st.confidence}
                for st in steps
            ],
            "evaluation": _evaluate_session(s, prompt_label),
            "advice": _next_advice(s, task),
        }
    finally:
        db.close()


def _interpret(total, completion_rate, pdi, indep_rate, unc_ratio):
    if total == 0:
        return "暂无训练记录，完成首次训练后将自动生成专业分析与建议。"
    parts = []
    if completion_rate >= 0.8:
        parts.append(f"总体完成率 {completion_rate*100:.0f}%，整体表现良好；")
    elif completion_rate >= 0.5:
        parts.append(f"总体完成率 {completion_rate*100:.0f}%，处于中等水平，仍有提升空间；")
    else:
        parts.append(f"总体完成率 {completion_rate*100:.0f}%，偏低，建议适当降低任务难度；")

    if pdi <= 1.0:
        parts.append("提示依赖指数（PDI）较低，孩子独立性较好；")
    elif pdi <= 2.5:
        parts.append("提示依赖指数（PDI）中等，仍需一定辅助；")
    else:
        parts.append("提示依赖指数（PDI）偏高，较依赖辅助，建议逐步减少提示；")

    parts.append(f"独立完成率 {indep_rate*100:.0f}%。")
    if unc_ratio > 0.3:
        parts.append("识别不确定事件偏多，建议改善光线或调整摄像头角度。")
    return "".join(parts)


def _evaluate_session(s, prompt_label):
    if s.completed:
        if s.prompt_level == 0:
            return "本次训练孩子能够完全独立完成，表现出色，能力正在稳步提升。"
        return f"本次训练在「{prompt_label}」提示下完成，建议后续逐步减少辅助，向独立完成努力。"
    return "本次训练未能完成，建议适当降低难度或增加辅助，先帮助孩子建立成功体验与信心。"


def _next_advice(s, task):
    if s.completed:
        return "建议保持当前难度继续巩固，并逐步减少提示辅助，向更高难度进阶。"
    return "建议降低一档难度或提高提示等级，帮助孩子先获得成功体验，再逐步提升。"
