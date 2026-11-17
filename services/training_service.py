# -*- coding: utf-8 -*-
"""训练任务调度服务（开始/暂停/恢复/结束 + 状态管理）。

支持两类任务：
- 动作类（action）：声明式动作引擎，持续保持目标姿态 hold_sec 秒即完成。
- 生活技能类（skill）：YOLO 物品检测 + 人-物交互识别 + 连续行为 FSM，
  实现"寻找→接近→拿起→移动→放入收纳盒"多步骤任务理解（升级建议核心）。

所有视觉事件通过 services.vision_events 统一格式记录，
同时写入内存缓冲（实时查询）与数据库 vision_record（AI 原始结果，不被人工覆盖）。

状态机：idle -> running <-> paused -> done / aborted
"""

import datetime
import os
import sys
import threading
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VISION_DIR = os.path.join(ROOT, "vision")
if VISION_DIR not in sys.path:
    sys.path.insert(0, VISION_DIR)

import action_engine  # noqa: E402
from behavior_sequence import BehaviorFSM  # noqa: E402
from interaction_detector import InteractionDetector  # noqa: E402

from database import crud  # noqa: E402
from services.camera_service import camera  # noqa: E402
from services.vision_events import make_event, events  # noqa: E402

DEFAULT_HOLD_SEC = 2.0

STEP_NAMES_CN = {
    "find_toy": "寻找玩具",
    "approach_toy": "接近玩具",
    "pick_toy": "拿起玩具",
    "move_toy": "移动玩具",
    "place_toy": "放入收纳盒",
}


class TrainingService:
    _instance = None
    _class_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self.state = "idle"          # idle/running/paused/done/aborted
        self.session_id = None
        self.session_code = None
        self.task = None
        self.task_params = None
        self.hold_sec = DEFAULT_HOLD_SEC
        self.thread = None
        self._stop_flag = threading.Event()
        self._pause_flag = threading.Event()
        self.message = ""
        # action 任务状态
        self.hold_start = None
        self.detected_now = False
        self.current_action = None
        # skill 任务状态
        self.skill = None
        self.current_step = None
        self.current_interaction = "uncertain"
        self.completed_steps = []

    # ---------- 对外接口 ----------
    def start(self, task_id, child_id=None, scene_id=None, prompt_level=0,
              hold_sec=DEFAULT_HOLD_SEC):
        if self.state == "running":
            return {"ok": False, "msg": "已有训练在进行中，请先结束"}

        task = crud.get_task_by_task_id(task_id)
        if task is None:
            return {"ok": False, "msg": f"任务 {task_id} 不存在"}

        cam_ok = camera.start()
        if not cam_ok["ok"]:
            return {"ok": False, "msg": cam_ok["msg"]}

        children = crud.list_children()
        if child_id is None and children:
            child_id = children[0].id
        if scene_id is None:
            scenes = crud.list_scenes()
            if scenes:
                scene_id = scenes[0].id

        session_code = uuid.uuid4().hex[:16]
        session = crud.create_session(session_code, child_id, task.id,
                                      scene_id, prompt_level)
        self.session_id = session.id
        self.session_code = session_code
        self.task = task
        self.task_params = task.params or {}
        self.hold_sec = hold_sec
        self.state = "running"
        self.message = f"开始训练：{task.name}"
        self.detected_now = False
        self.hold_start = None
        self.skill = None
        self.current_step = None
        self.completed_steps = []
        self._stop_flag.clear()
        self._pause_flag.clear()

        # skill 任务：加载 YOLO 模型并初始化 FSM
        if task.type == "skill":
            target = self.task_params.get("target", "bottle")
            containers = self.task_params.get(
                "containers", ["book", "cup", "remote", "bowl"])
            self.skill = {
                "fsm": BehaviorFSM(),
                "inter": None,
                "target": target,
                "containers": containers,
                "started": False,
                "prev_completed": set(),
                "prev_uncertain": 0,
            }

        target = self._run_skill if task.type == "skill" else self._run_action
        self.thread = threading.Thread(target=target, daemon=True)
        self.thread.start()
        return {"ok": True, "msg": self.message, "session_id": self.session_id,
                "session_code": session_code}

    def pause(self):
        if self.state != "running":
            return {"ok": False, "msg": "当前没有可暂停的训练"}
        self._pause_flag.set()
        self.state = "paused"
        if self.session_id:
            crud.update_session(self.session_id, status="paused")
        self.message = "训练已暂停"
        return {"ok": True, "msg": self.message}

    def resume(self):
        if self.state != "paused":
            return {"ok": False, "msg": "当前没有处于暂停的训练"}
        self._pause_flag.clear()
        self.state = "running"
        if self.session_id:
            crud.update_session(self.session_id, status="running")
        self.message = "训练已恢复"
        return {"ok": True, "msg": self.message}

    def stop(self):
        if self.state not in ("running", "paused"):
            return {"ok": False, "msg": "当前没有进行中的训练"}
        self._stop_flag.set()
        if self.thread is not None:
            self.thread.join(timeout=1.0)
            self.thread = None
        if self.task and self.task.type == "skill":
            self._finish_skill(completed=False)
        else:
            self._finish(completed=False)
        return {"ok": True, "msg": "训练已结束"}

    def status(self):
        return {
            "state": self.state,
            "session_id": self.session_id,
            "session_code": self.session_code,
            "task_name": self.task.name if self.task else None,
            "task_type": self.task.type if self.task else None,
            "target_action": self.task_params.get("action_id") if self.task_params else None,
            "target_object": self.task_params.get("target") if self.task_params else None,
            "detected_now": self.detected_now,
            "current_action": self.current_action,
            "current_step": self.current_step,
            "current_interaction": self.current_interaction,
            "completed_steps": self.completed_steps,
            "message": self.message,
            "events": events.recent(20),
            "camera": camera.status(),
        }

    # ---------- 动作类任务 ----------
    def _run_action(self):
        target_action = self.task_params.get("action_id")
        while not self._stop_flag.is_set():
            if self._pause_flag.is_set():
                time.sleep(0.1)
                continue
            smoothed, _raw = camera.get_landmarks()
            now = time.time()
            if not smoothed:
                self.detected_now = False
                self.hold_start = None
                time.sleep(0.05)
                continue
            try:
                hits = action_engine.detect_actions(smoothed)
            except Exception:
                hits = []
            self.current_action = hits[0] if hits else None
            hit = target_action in hits
            if hit:
                self.detected_now = True
                if self.hold_start is None:
                    self.hold_start = now
                if now - self.hold_start >= self.hold_sec:
                    self._finish(completed=True)
                    return
            else:
                self.detected_now = False
                self.hold_start = None
            time.sleep(0.05)

    # ---------- 生活技能类（多步骤）任务 ----------
    def _run_skill(self):
        import object_detector  # 延迟加载 ultralytics（较重），仅 skill 任务触发
        try:
            object_detector.load_model()
        except Exception as e:
            self.message = f"YOLO 模型加载失败: {e}"
            self._finish_skill(completed=False)
            return
        skill = self.skill
        fsm = skill["fsm"]
        while not self._stop_flag.is_set():
            if self._pause_flag.is_set():
                time.sleep(0.1)
                continue

            frame = camera.get_raw_frame()
            now = time.time()
            if frame is None:
                time.sleep(0.05)
                continue
            fh, fw = frame.shape[:2]

            # YOLO 物品检测
            try:
                detections = object_detector.detect_objects(frame, conf=0.35)
            except Exception:
                detections = []

            # 组装 World：玩具 / 收纳盒（归一化坐标）
            toy = cont = None
            for det in detections:
                if det["name"] == skill["target"] and toy is None:
                    toy = self._norm_det(det, fw, fh)
                elif det["name"] in skill["containers"] and cont is None:
                    cont = self._norm_det(det, fw, fh)

            # 人-物交互状态
            interaction = "uncertain"
            _smoothed, raw_lms = camera.get_landmarks()
            if raw_lms is not None:
                if skill["inter"] is None:
                    skill["inter"] = InteractionDetector(skill["target"], fw, fh)
                interaction, _ev, _ch = skill["inter"].update(
                    raw_lms, detections, now)

            if not skill["started"]:
                skill["started"] = True
                fsm.start(now)
                events.add(make_event("task_started", self.task.name, now,
                                      session_id=self.session_id))

            st = fsm.update({"now": now, "interaction": interaction,
                             "toy": toy, "container": cont}, now)
            self.current_step = st["current_step"]
            self.current_interaction = interaction
            self.completed_steps = list(st["completed_steps"])

            self._record_skill_events(st, now)

            if st["status"] == "done":
                self._finish_skill(completed=True)
                return
            time.sleep(0.03)

    def _record_skill_events(self, st, now):
        skill = self.skill
        cur = set(st["completed_steps"])
        for step in cur - skill["prev_completed"]:
            events.add(make_event(
                "step_completed", STEP_NAMES_CN.get(step, step), now,
                task_step=step, confidence=1.0, session_id=self.session_id))
        skill["prev_completed"] = cur

        unc = st.get("uncertain_events") or []
        if len(unc) > skill["prev_uncertain"]:
            for _t, etype, detail in unc[skill["prev_uncertain"]:]:
                events.add(make_event(
                    "uncertainty", str(etype), _t,
                    task_step=st["current_step"], session_id=self.session_id,
                    details={"detail": str(detail)}))
            skill["prev_uncertain"] = len(unc)

    @staticmethod
    def _norm_det(det, w, h):
        x1, y1, x2, y2 = det["bbox"]
        return {"name": det["name"],
                "bbox": (x1 / w, y1 / h, x2 / w, y2 / h),
                "center": (det["center"][0] / w, det["center"][1] / h),
                "confidence": det["confidence"]}

    # ---------- 结束 ----------
    def _finish(self, completed):
        self.state = "done" if completed else "aborted"
        if self.session_id:
            s = crud.get_session(self.session_id)
            elapsed = 0.0
            if s and s.start_time:
                elapsed = (datetime.datetime.now() - s.start_time).total_seconds()
            crud.update_session(
                self.session_id, status=self.state, completed=completed,
                end_time=datetime.datetime.now(), elapsed_sec=round(elapsed, 1))
            crud.add_action_record(
                self.session_id, step_name=self.task.name if self.task else None,
                action_id=self.task_params.get("action_id") if self.task_params else None,
                detected=completed, confidence=1.0 if completed else 0.0)
        events.add(make_event("task_finished", self.message, time.time(),
                              session_id=self.session_id,
                              details={"completed": completed}))
        self.message = "训练完成" if completed else "训练已结束"

    def _finish_skill(self, completed):
        self.state = "done" if completed else "aborted"
        if self.session_id:
            s = crud.get_session(self.session_id)
            elapsed = 0.0
            if s and s.start_time:
                elapsed = (datetime.datetime.now() - s.start_time).total_seconds()
            crud.update_session(
                self.session_id, status=self.state, completed=completed,
                end_time=datetime.datetime.now(), elapsed_sec=round(elapsed, 1))
            for i, step in enumerate(self.completed_steps):
                crud.add_action_record(
                    self.session_id, step_order=i,
                    step_name=STEP_NAMES_CN.get(step, step),
                    action_id=step, detected=True, confidence=1.0)
        events.add(make_event(
            "task_finished", self.task.name if self.task else "", time.time(),
            session_id=self.session_id,
            details={"completed": completed, "steps": self.completed_steps}))
        self.message = "训练完成" if completed else "训练已结束"


# 全局单例
training = TrainingService()
