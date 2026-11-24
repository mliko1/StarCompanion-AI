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

from core.personalization import (  # noqa: E402
    PersonalProfile, effective_params, adapt_action_for_hand,
    scale_threshold,
)

from database import crud  # noqa: E402
from services import tts  # noqa: E402
from services.camera_service import camera  # noqa: E402
from services.vision_events import make_event, events  # noqa: E402

DEFAULT_HOLD_SEC = 1.5

# 保持判定的抖动容差：连续 miss 超过该秒数才重置计时，
# 避免关键点轻微抖动导致"做对了却永远完不成"
MISS_TOLERANCE_SEC = 0.4

# 瞬时动作：用「原始关键点」识别（平滑会抹掉拍手这种瞬间合掌的峰值）
# 持续动作（举手等）：仍用「平滑关键点」，配合 hold_sec 防抖更稳
INSTANT_ACTIONS = {"clap", "clap_overhead", "wave_left", "wave_right", "wave_both"}

STEP_NAMES_CN = {
    "find_toy": "寻找玩具",
    "approach_toy": "接近玩具",
    "pick_toy": "拿起玩具",
    "move_toy": "移动玩具",
    "place_toy": "放入收纳盒",
}

# 步骤 -> 下一步（用于语音播报下一步指令）
_NEXT_STEP = {
    "find_toy": "approach_toy",
    "approach_toy": "pick_toy",
    "pick_toy": "move_toy",
    "move_toy": "place_toy",
}


def _custom_model_classes():
    """扫描已训练的家庭自定义模型类名（vision/models/custom_*.pt）。"""
    models_dir = os.path.join(ROOT, "vision", "models")
    if not os.path.isdir(models_dir):
        return []
    return [fn[len("custom_"):-len(".pt")]
            for fn in sorted(os.listdir(models_dir))
            if fn.startswith("custom_") and fn.endswith(".pt")]


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
        self.action_frames = 0      # 检测总帧数（用于置信度统计）
        self.action_hits = 0        # 目标动作命中帧数
        # skill 任务状态
        self.skill = None
        self.current_step = None
        self.current_interaction = "uncertain"
        self.completed_steps = []
        # 方案模式（连续训练多个动作）
        self.plan_mode = False
        self.plan_tasks = []
        self.plan_index = 0
        self.plan_total = 0
        self.plan_results = []
        self.plan_child_id = None
        self.plan_scene_id = None
        self.plan_prompt_level = 0
        self.plan_hold_sec = DEFAULT_HOLD_SEC
        # 个体化适应状态
        self.personal_profile = None   # PersonalProfile（纯逻辑对象）
        self.effective = {}            # 有效个体化参数 {param_key: value}

    # ---------- 对外接口 ----------
    def start(self, task_id, child_id=None, scene_id=None, prompt_level=0,
              hold_sec=DEFAULT_HOLD_SEC):
        if self.state == "running":
            return {"ok": False, "msg": "已有训练在进行中，请先结束"}

        self.plan_mode = False

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
        self._load_personalization()
        self._stop_flag.clear()
        self._pause_flag.clear()

        # skill 任务：加载 YOLO 模型并初始化 FSM
        if task.type == "skill":
            target = self.task_params.get("target", "bottle")
            containers = list(self.task_params.get(
                "containers", ["book", "cup", "remote", "bowl"]))
            # 自动纳入已训练的家庭自定义模型（custom_<name>.pt -> name）
            # 作为放置目标候选，训练完成即可用，无需手动改配置
            for _cls in _custom_model_classes():
                if _cls not in containers:
                    containers.append(_cls)
            self.skill = {
                "fsm": BehaviorFSM(
                    timeout_scale=self.effective.get("hold_sec_scale", 1.0)),
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

        # 语音播报指令（异步，不阻塞）
        if task.type == "skill":
            tts.speak("我们开始啦，先找到目标玩具哦")
        else:
            tts.speak(f"我们开始啦，来做{task.name}吧")

        return {"ok": True, "msg": self.message, "session_id": self.session_id,
                "session_code": session_code}

    def start_plan(self, task_ids, child_id=None, scene_id=None, prompt_level=0,
                   hold_sec=DEFAULT_HOLD_SEC):
        """方案模式：依次连续训练多个动作，练完一个自动进入下一个。"""
        if self.state == "running":
            return {"ok": False, "msg": "已有训练在进行中，请先结束"}

        tasks = []
        for tid in task_ids:
            t = crud.get_task_by_task_id(tid)
            if t is None:
                return {"ok": False, "msg": f"任务 {tid} 不存在"}
            tasks.append(t)
        if not tasks:
            return {"ok": False, "msg": "训练方案为空"}

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

        self.plan_mode = True
        self.plan_tasks = [t.task_id for t in tasks]
        self.plan_total = len(tasks)
        self.plan_index = 0
        self.plan_results = []
        self.plan_child_id = child_id
        self.plan_scene_id = scene_id
        self.plan_prompt_level = prompt_level
        self.plan_hold_sec = hold_sec
        self.state = "running"
        self.message = f"开始训练方案（共 {len(tasks)} 个动作）"
        self._stop_flag.clear()
        self._pause_flag.clear()

        self.thread = threading.Thread(target=self._run_plan, daemon=True)
        self.thread.start()

        tts.speak(f"今天有 {len(tasks)} 个小任务，我们开始吧")
        return {"ok": True, "msg": self.message, "plan_total": len(tasks)}

    def _run_plan(self):
        for i, tid in enumerate(self.plan_tasks):
            if self._stop_flag.is_set():
                break
            self.plan_index = i
            task = crud.get_task_by_task_id(tid)
            if task is None:
                self.plan_results.append({"task_id": tid, "completed": False})
                continue
            self._setup_single(task, self.plan_child_id, self.plan_scene_id,
                               self.plan_prompt_level, self.plan_hold_sec)
            tts.speak(f"第 {i + 1} 个，{task.name}，准备好咯")
            # 单个动作：练到完成（或中途被停止）
            ok = self._run_action()
            self.plan_results.append({"task_id": tid, "completed": ok})
        self._finish_plan()

    def _finish_plan(self, completed=True):
        done_count = sum(1 for r in self.plan_results if r["completed"])
        self.state = "done" if completed else "aborted"
        self.message = f"训练方案完成：{done_count}/{len(self.plan_results)} 个动作完成"
        events.add(make_event("plan_finished", self.message, time.time(),
                              details={"results": self.plan_results}))
        tts.speak(f"今天的训练结束啦，完成了 {done_count} 个动作，真棒！")
        self.plan_mode = False

    def _setup_single(self, task, child_id, scene_id, prompt_level, hold_sec):
        """为单个动作创建 session 并初始化状态（单任务模式与方案模式共用）。"""
        session_code = uuid.uuid4().hex[:16]
        session = crud.create_session(session_code, child_id, task.id,
                                      scene_id, prompt_level)
        self.session_id = session.id
        self.session_code = session_code
        self.task = task
        self.task_params = task.params or {}
        self.hold_sec = hold_sec
        self.message = f"开始训练：{task.name}"
        self.detected_now = False
        self.hold_start = None
        self.skill = None
        self.current_step = None
        self.completed_steps = []
        self._load_personalization()

        if task.type == "skill":
            target = self.task_params.get("target", "bottle")
            containers = list(self.task_params.get(
                "containers", ["book", "cup", "remote", "bowl"]))
            # 自动纳入已训练的家庭自定义模型（custom_<name>.pt -> name）
            # 作为放置目标候选，训练完成即可用，无需手动改配置
            for _cls in _custom_model_classes():
                if _cls not in containers:
                    containers.append(_cls)
            self.skill = {
                "fsm": BehaviorFSM(
                    timeout_scale=self.effective.get("hold_sec_scale", 1.0)),
                "inter": None,
                "target": target,
                "containers": containers,
                "started": False,
                "prev_completed": set(),
                "prev_uncertain": 0,
            }

    def _load_personalization(self):
        """从数据库加载当前孩子×任务的个体化档案，计算有效参数。

        数据不足或加载失败时退化为「固定标准」（effective 为空），
        个体化只会在多次训练 + 人工审核积累足够样本后才生效。
        """
        self.personal_profile = None
        self.effective = {}
        if not self.session_id:
            return
        try:
            s = crud.get_session(self.session_id)
            if not s or s.child_id is None or s.task_id is None:
                return
            rows = crud.list_personal_profiles(child_id=s.child_id,
                                               task_id=s.task_id)
            if not rows:
                return
            profile = PersonalProfile(s.child_id, s.task_id)
            for r in rows:
                profile.set_slot(r.param_key, r.samples, r.reviews)
            self.personal_profile = profile
            self.effective = effective_params(profile)
        except Exception as e:  # 个体化失败不阻断训练
            self.personal_profile = None
            self.effective = {}
            print(f"[个体化] 档案加载失败，回退固定标准: {e}")

    def _record_personalization(self, completed, elapsed):
        """训练结束时把本次观察写回个体化档案（逐步建立参考范围）。

        仅在「完成」时记录完成用时，作为 hold_sec_scale 的观察样本：
        observed = 完成总用时 / 基准保持时长（越大=动作越慢）。
        初期样本处于 pending 不生效，多次后才收敛为有效缩放系数。
        """
        if not self.personal_profile or not completed:
            return
        try:
            base = max(self.hold_sec, 0.5)
            observed = elapsed / base
            # 钳制到 hold_sec_scale 的合理区间，避免偶发长时间磨蹭污染参考范围
            observed = min(max(observed, 0.5), 4.0)
            self.personal_profile.record("hold_sec_scale", round(observed, 3))
            crud.sync_personal_profile_from_logic(self.personal_profile)
        except Exception as e:
            print(f"[个体化] 观察写回失败: {e}")

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
        if self.plan_mode:
            self._finish_plan(completed=False)
        elif self.task and self.task.type == "skill":
            self._finish_skill(completed=False)
        else:
            self._finish(completed=False)
        # 训练结束必须释放摄像头，否则一直占用（影响下次启动与别的程序）
        camera_status = camera.stop()
        return {"ok": True, "msg": "训练已结束", "camera": camera_status}

    def status(self):
        containers = None
        if self.task and self.task.type == "skill" and self.skill:
            containers = self.skill["containers"]
        return {
            "state": self.state,
            "session_id": self.session_id,
            "session_code": self.session_code,
            "task_name": self.task.name if self.task else None,
            "task_type": self.task.type if self.task else None,
            "target_action": self.task_params.get("action_id") if self.task_params else None,
            "target_object": self.task_params.get("target") if self.task_params else None,
            "containers": containers,
            "custom_models": _custom_model_classes(),
            "detected_now": self.detected_now,
            "current_action": self.current_action,
            "current_step": self.current_step,
            "current_interaction": self.current_interaction,
            "completed_steps": self.completed_steps,
            "message": self.message,
            "plan_mode": self.plan_mode,
            "plan_index": self.plan_index,
            "plan_total": self.plan_total,
            "plan_tasks": self.plan_tasks,
            "plan_results": self.plan_results,
            "events": events.recent(20),
            "camera": camera.status(),
        }

    # ---------- 动作类任务 ----------
    def _run_action(self):
        """训练单个动作直到完成或停止，返回是否完成（供方案模式循环调用）。"""
        # ---- 个体化适应：惯用手镜像 + 保持时长/幅度/速度缩放 ----
        orig_action = self.task_params.get("action_id")
        hand = self.effective.get("preferred_hand", "unknown")
        target_action = adapt_action_for_hand(orig_action, hand)
        hold_scale = self.effective.get("hold_sec_scale", 1.0)
        effective_hold = scale_threshold(self.hold_sec, hold_scale)
        amplitude_scale = self.effective.get("amplitude_scale", 1.0)
        speed_scale = self.effective.get("speed_scale", 1.0)
        if target_action != orig_action:
            self.message = (f"开始训练：{self.task.name}"
                            f"（个体化：{orig_action}→{target_action}）")
        instant = target_action in INSTANT_ACTIONS
        # 所有动作统一用有状态检测器：
        # - allowed 白名单：训练"举左手"时只检测举左手，摸头等相似动作不参与；
        # - protect 保护：目标动作不被其他动作的 excludes 压制；
        # - 稳定性确认：连续几帧命中才算数，避免单帧抖动误记录；
        # - clap 的骤降防伪由 ActionTracker 内部保留。
        target_set = {target_action} if target_action else None
        tracker = action_engine.ActionTracker(
            amplitude_scale=amplitude_scale,
            speed_scale=speed_scale,
            allowed=target_set,
            protect=target_set,
        )
        miss_since = None  # 最近一次 miss 的起始时间（用于抖动容差）
        self.action_frames = 0      # 每个动作重新统计命中率（置信度）
        self.action_hits = 0
        while not self._stop_flag.is_set():
            if self._pause_flag.is_set():
                time.sleep(0.1)
                continue
            smoothed, raw = camera.get_landmarks()
            now = time.time()
            lms = raw if instant else smoothed
            if not lms:
                self.detected_now = False
                self.hold_start = None
                miss_since = now
                time.sleep(0.05)
                continue
            try:
                hits = tracker.detect(lms, now)
            except Exception:
                hits = []
            self.current_action = hits[0] if hits else None
            hit = target_action in hits
            self.action_frames += 1
            if hit:
                self.action_hits += 1
            if hit:
                self.detected_now = True
                miss_since = None
                if self.hold_start is None:
                    self.hold_start = now
                if now - self.hold_start >= effective_hold:
                    self._finish(completed=True)
                    return True
            else:
                self.detected_now = False
                # 容差：短暂 miss（< MISS_TOLERANCE_SEC）不重置计时，
                # 只有连续 miss 超过容差才重新计时
                if miss_since is None:
                    miss_since = now
                elif now - miss_since > MISS_TOLERANCE_SEC:
                    self.hold_start = None
                    miss_since = now
            time.sleep(0.05)
        return False

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
        # 家庭个性化：加载目标物/放置目标对应的自定义模型（可多个并存）
        for _cname in list(skill["containers"]) + [skill["target"]]:
            if object_detector.has_custom_model(_cname):
                if object_detector.load_custom_model(_cname):
                    print(f"[skill] 已加载家庭自定义模型: {_cname}")
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
                    # 个体化：传入孩子惯用手，优先追踪该手
                    skill["inter"] = InteractionDetector(
                        skill["target"], fw, fh,
                        preferred_hand=self.effective.get(
                            "preferred_hand", "unknown"))
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
            # 语音播报：完成当前步骤 + 提示下一步
            cn = STEP_NAMES_CN.get(step, step)
            nxt = STEP_NAMES_CN.get(_NEXT_STEP.get(step))
            if nxt:
                tts.speak(f"做得好，{cn}完成啦，接下来{nxt}")
            else:
                tts.speak(f"做得好，{cn}完成啦")
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
        action_state = "done" if completed else "aborted"
        if self.plan_mode:
            self.state = "running"  # 方案模式：单个动作结束，方案仍在进行
        else:
            self.state = action_state
        # 命中率作为置信度（而非恒 1.0/0.0）
        conf = (self.action_hits / self.action_frames
                if self.action_frames > 0 else (1.0 if completed else 0.0))
        if self.session_id:
            s = crud.get_session(self.session_id)
            elapsed = 0.0
            if s and s.start_time:
                elapsed = (datetime.datetime.now() - s.start_time).total_seconds()
            crud.update_session(
                self.session_id, status=action_state, completed=completed,
                end_time=datetime.datetime.now(), elapsed_sec=round(elapsed, 1))
            crud.add_action_record(
                self.session_id, step_name=self.task.name if self.task else None,
                action_id=self.task_params.get("action_id") if self.task_params else None,
                detected=completed, confidence=round(conf, 3))
            # 写 AI 原始识别结果（与人工确认 manual_review 分开，不被覆盖）
            crud.add_vision_record(
                self.session_id,
                raw_result={"action_id": self.task_params.get("action_id"),
                            "completed": completed},
                confidence=round(conf, 3),
                uncertainty=not completed,
                uncertainty_reason=None if completed else "未达到保持时长")
            # 个体化适应：把本次完成用时写回档案（逐步建立参考范围）
            self._record_personalization(completed, elapsed)
        events.add(make_event("action_detected",
                              self.task.name if self.task else "动作",
                              time.time(), session_id=self.session_id,
                              confidence=round(conf, 3),
                              details={"action_id": self.task_params.get("action_id"),
                                       "completed": completed}))
        events.add(make_event("task_finished", self.message, time.time(),
                              session_id=self.session_id,
                              details={"completed": completed}))
        self.message = "训练完成" if completed else "训练已结束"
        if completed:
            tts.speak("太棒啦，任务完成咯！")

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
        if completed:
            tts.speak("太棒啦，任务完成咯！")


# 全局单例
training = TrainingService()
