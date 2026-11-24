# -*- coding: utf-8 -*-
"""训练结束后的个体化专业报告生成（提供给家长查看）。

结构参考（已调研）：
- DB61/T 2099.6-2025《0岁~6岁残疾儿童康复服务规范 第6部分：孤独症》
  附录A.1 评估结果分析表：领域能力现状 / 优势 / 弱势 / 待支持需求；
- 广东省孤独症儿童康复档案·学生学习进度报告表：
  3=独立完成，2=语言提示下完成，1=触体帮助下完成，0=不能独立完成；
- ABA Progress Report 通用结构：基线-当前-目标对照、数据背景、
  优势与障碍、下一步计划、家长反馈。

输出为纯 dict；所有结论为辅助参考，不构成医学诊断。
"""

import datetime

from database import models
from database.db import SessionLocal
from core.plan import build_plan

PROMPT_LABELS = ["独立完成", "视觉提示", "语音提示", "动作示范", "家长协助"]
SCORE_LABELS = {
    3: "能独立完成",
    2: "在语言/视觉提示下完成",
    1: "在动作示范或家长协助下完成",
    0: "本次未能完成",
}
DOMAIN_FINE = ("捏", "抓", "手指", "穿", "串", "折", "剪", "写")


def _dimension(task):
    """把任务映射到康复领域（用于分领域现状描述）。"""
    if not task:
        return "综合训练"
    if task.type == "skill":
        return "生活自理"
    name = task.name or ""
    if any(k in name for k in DOMAIN_FINE):
        return "精细动作"
    return "粗大运动"


def _score(completed, prompt_level):
    """按国标 3/2/1/0 口径给本次表现打分。"""
    if not completed:
        return 0
    if prompt_level == 0:
        return 3
    if prompt_level in (1, 2):
        return 2
    return 1


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


def build_professional_report(session_id):
    """生成一次训练的完整专业报告；session 不存在返回 None。"""
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
        vision_rows = (db.query(models.VisionRecord)
                       .filter_by(session_id=session_id).all())
        uncertain = sum(1 for v in vision_rows if v.uncertainty)
        reviewed = 0
        if vision_rows:
            ids = [v.id for v in vision_rows]
            reviewed = (db.query(models.ManualReview)
                        .filter(models.ManualReview.vision_record_id.in_(ids))
                        .count())
        history = (db.query(models.TrainingSession)
                   .filter(models.TrainingSession.child_id == s.child_id,
                           models.TrainingSession.task_id == s.task_id,
                           models.TrainingSession.id != s.id)
                   .order_by(models.TrainingSession.start_time.desc())
                   .limit(10).all())

        score = _score(s.completed, s.prompt_level or 0)
        prompt_label = (PROMPT_LABELS[s.prompt_level]
                        if s.prompt_level is not None
                        and 0 <= s.prompt_level <= 4 else "未记录")
        done_steps = [st.step_name for st in steps if st.detected]
        todo_steps = [st.step_name for st in steps if not st.detected]

        # 基线：同儿童同任务的既往完成率（最多取最近 10 次）
        if history:
            hist_rate = sum(1 for h in history if h.completed) / len(history)
            baseline = round(hist_rate * 3)
            baseline_n = len(history)
        else:
            baseline, baseline_n = None, 0

        if score == 3:
            target = "在 2 次不同场景中保持独立完成，逐步减少提示"
        elif score == 2:
            target = "减少一级提示辅助，向独立完成过渡"
        elif score == 1:
            target = "先稳定完成当前提示等级，再逐步减少家长协助"
        else:
            target = "降低任务难度或增加动作示范，先建立成功体验"

        # 领域现状（参照国标评估分析表：现状 / 优势 / 弱势 / 待支持）
        if score == 3:
            strength = "本次能独立完成目标动作，动作控制与任务理解表现稳定。"
        elif score == 2:
            strength = "在少量提示下能够完成，说明已理解任务要求，具备独立完成的基础。"
        elif score == 1:
            strength = "在较强辅助下仍能完成，配合度与任务参与度良好。"
        else:
            strength = "本次未能完成，但训练过程本身提供了可分析的基线数据。"
        if todo_steps:
            weak = "以下步骤尚未独立完成：" + "、".join(todo_steps) + "。"
        elif s.prompt_level and s.prompt_level > 0:
            weak = f"目前仍需「{prompt_label}」，独立性尚有提升空间。"
        else:
            weak = "暂未发现明显弱势项，建议继续观察不同场景下的泛化表现。"

        support = []
        if not s.completed:
            support.append("降低难度或增加提示等级，先保证成功体验")
        if s.prompt_level and s.prompt_level >= 2:
            support.append("逐步撤除辅助，目标为独立完成")
        if uncertain >= 2:
            support.append("改善光线与摄像头角度，减少识别不确定事件")
        if not support:
            support.append("保持当前难度，增加不同场景练习以促进泛化")

        # 数据质量说明（诚实口径）
        quality = "good"
        quality_note = "识别数据完整，无明显不确定事件。"
        if uncertain >= 2:
            quality, quality_note = "uncertain", (
                f"本次有 {uncertain} 条识别不确定事件，结论仅供参考，"
                "建议结合人工确认后使用。")
        elif not vision_rows:
            quality, quality_note = "limited", (
                "本次未留存视觉识别记录，本报告主要依据训练结果与人工观察。")

        # 后续训练计划：基于报告表现调整难度与提示建议
        plan_data = build_plan(s.child_id) if s.child_id else {"plan": []}
        next_plan = []
        for p in (plan_data.get("plan") or [])[:5]:
            item = dict(p)
            if score <= 1:
                item["prompt_suggestion"] = "建议从视觉/语音提示开始，降低难度"
            elif score == 2:
                item["prompt_suggestion"] = "尝试减少一级提示，保持难度"
            else:
                item["prompt_suggestion"] = "独立完成为主，可适当增加难度"
            next_plan.append(item)
        if not next_plan:
            next_plan.append({
                "task_id": task.task_id if task else None,
                "name": task.name if task else "当前任务",
                "kind": "review",
                "difficulty": task.difficulty if task else 1,
                "reason": data_quality_reason(s, history),
                "prompt_suggestion": "保持当前设置，继续观察",
            })

        # ---- 扩展分析要点 ----
        # 历史趋势（近 10 次完成率 / 提示等级走势）
        history_points = []
        for h in reversed(history):
            history_points.append({
                "date": _fmt(h.start_time),
                "completed": bool(h.completed),
                "prompt_level": h.prompt_level,
                "score": _score(h.completed, h.prompt_level or 0),
            })
        recent = history_points[-5:]
        trend = "数据不足，完成 3 次以上可观察趋势"
        if len(recent) >= 3:
            first = sum(1 for p in recent[:len(recent)//2] if p["completed"])
            last = sum(1 for p in recent[len(recent)//2:] if p["completed"])
            if last > first:
                trend = "近期完成率呈上升趋势，训练效果正在显现"
            elif last < first:
                trend = "近期完成率有所波动下降，建议降低难度或增加辅助"
            else:
                trend = "近期表现基本稳定，可尝试小幅提升难度或泛化场景"

        # 提示依赖度分析（PDI 简化口径：提示等级 / 4）
        pdi = round((s.prompt_level or 0) / 4, 2)
        if pdi <= 0.25:
            pdi_comment = "独立性良好，能以极少辅助完成任务"
        elif pdi <= 0.5:
            pdi_comment = "轻度依赖提示，建议逐步撤除视觉/语言辅助"
        elif pdi <= 0.75:
            pdi_comment = "提示依赖较明显，建议先稳定完成再减少辅助"
        else:
            pdi_comment = "高度依赖家长协助，建议从降低难度入手建立成功体验"

        # 分步骤表现明细
        step_details = [{
            "order": (st.step_order or 0) + 1,
            "name": st.step_name or "—",
            "completed": bool(st.detected),
            "confidence": round(st.confidence or 0, 2),
        } for st in steps]
        if not step_details:
            step_details = [{
                "order": 1, "name": task.name if task else "目标动作",
                "completed": bool(s.completed),
                "confidence": 1.0 if s.completed else 0.0,
            }]

        # 家长在家观察要点（可操作建议，不虚构能力）
        home_tips = []
        if pdi > 0.5:
            home_tips.append("在家练习时先给一步提示，等孩子完成后再给下一步，避免连续指令")
        if not s.completed:
            home_tips.append("把任务拆成更小的步骤，先练习最容易成功的一步，累计成功体验")
        else:
            home_tips.append("用同样的口令和动作在家复现一次，帮助把课堂技能迁移到生活")
        home_tips.append("记录孩子今天主动尝试的次数，哪怕未完成也值得肯定")
        home_tips.append("训练时长每次 5~10 分钟为宜，孩子情绪不佳时暂停，不强迫")

        age = None
        if child and child.birth_year:
            age = datetime.date.today().year - child.birth_year

        return {
            "meta": {
                "session_id": s.id,
                "session_code": s.session_code,
                "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "child": child.nickname if child else "未关联档案",
                "age": age,
                "task": task.name if task else "未关联任务",
                "task_type": task.type if task else None,
                "scene": scene.name if scene else None,
                "start_time": _fmt(s.start_time),
                "end_time": _fmt(s.end_time),
                "elapsed_sec": round(s.elapsed_sec or 0, 1),
            },
            "summary": {
                "completed": bool(s.completed),
                "prompt_level": s.prompt_level,
                "prompt_label": prompt_label,
                "score": score,
                "score_label": SCORE_LABELS[score],
                "dimension": _dimension(task),
            },
            "goal_progress": {
                "goal": task.name if task else "当前训练目标",
                "baseline": baseline,
                "baseline_label": SCORE_LABELS[baseline] if baseline is not None else "首次训练，暂无基线",
                "baseline_n": baseline_n,
                "current": score,
                "current_label": SCORE_LABELS[score],
                "target": target,
            },
            "steps": {
                "total": len(steps),
                "completed": len(done_steps),
                "done_names": done_steps,
                "pending_names": todo_steps,
            },
            "ability": {
                "dimension": _dimension(task),
                "current_status": SCORE_LABELS[score],
                "strength": strength,
                "weakness": weak,
                "support_needed": support,
            },
            "data_quality": {"level": quality, "note": quality_note,
                             "uncertain_count": uncertain,
                             "reviewed_count": reviewed},
            "highlights": [
                f"本次训练{'已独立完成' if s.completed else '在辅助下完成/未独立完成'}，"
                f"提示等级为「{prompt_label}」",
                f"用时 {round(s.elapsed_sec or 0, 1)} 秒，完成步骤 {len(done_steps)}/{len(steps) or 1}",
                trend,
                pdi_comment,
            ],
            "prompt_dependency": {
                "pdi": pdi,
                "level": s.prompt_level,
                "label": prompt_label,
                "comment": pdi_comment,
            },
            "trend": {
                "summary": trend,
                "history": history_points,
                "recent_completion": (
                    f"{sum(1 for p in recent if p['completed'])}/{len(recent)}"
                    if recent else "—"),
            },
            "step_details": step_details,
            "home_tips": home_tips,
            "next_plan": next_plan,
            "parent_feedback": {
                "observation": "",
                "difficulty_fit": "",
                "notes": "",
            },
            "disclaimer": (
                "本报告由系统根据训练记录自动生成，仅供家长与康复人员参考，"
                "不构成医学诊断或康复效果结论。提示等级调整与训练方案变更"
                "须经专业康复人员审核。"
            ),
        }
    finally:
        db.close()


def generate_and_save(session_id):
    """训练结束时调用：生成报告并落库（每场训练一份，重复调用不覆盖）。"""
    payload = build_professional_report(session_id)
    if not payload:
        return None
    db = SessionLocal()
    try:
        exists = (db.query(models.TrainingReport)
                  .filter_by(session_id=session_id).first())
        if exists:
            return exists.id
        row = models.TrainingReport(
            session_id=session_id,
            child_id=(db.get(models.TrainingSession, session_id).child_id),
            session_code=payload["meta"].get("session_code"),
            task_name=payload["meta"].get("task"),
            report_date=datetime.date.today().isoformat(),
            payload=payload,
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def get_saved(report_id):
    """读取已保存的报告快照。"""
    db = SessionLocal()
    try:
        row = db.get(models.TrainingReport, report_id)
        return row.payload if row else None
    finally:
        db.close()


def list_saved(child_id=None, date_from=None, date_to=None, limit=100):
    """历史报告列表（可按儿童、日期范围筛选），按生成时间倒序。"""
    db = SessionLocal()
    try:
        q = db.query(models.TrainingReport)
        if child_id is not None:
            q = q.filter(models.TrainingReport.child_id == child_id)
        if date_from:
            q = q.filter(models.TrainingReport.report_date >= date_from)
        if date_to:
            q = q.filter(models.TrainingReport.report_date <= date_to)
        rows = q.order_by(models.TrainingReport.created_at.desc()).limit(limit).all()
        return [{
            "report_id": r.id,
            "session_id": r.session_id,
            "child_id": r.child_id,
            "session_code": r.session_code,
            "task_name": r.task_name,
            "report_date": r.report_date,
            "created_at": r.created_at.isoformat(timespec="seconds") if r.created_at else None,
            "completed": (r.payload.get("summary") or {}).get("completed"),
            "score_label": (r.payload.get("summary") or {}).get("score_label"),
            "elapsed_sec": (r.payload.get("meta") or {}).get("elapsed_sec"),
        } for r in rows]
    finally:
        db.close()


def data_quality_reason(s, history):
    """没有推荐计划时的兜底理由。"""
    if not s.completed:
        return "本次未独立完成，建议巩固当前任务"
    if history:
        done = sum(1 for h in history if h.completed)
        return f"既往 {len(history)} 次中完成 {done} 次，建议继续巩固"
    return "首次训练完成，建议继续观察稳定性"
