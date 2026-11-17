# -*- coding: utf-8 -*-
"""
星伴AI 第三阶段 模块三：连续行为步骤识别（有限状态机 FSM）

把模块二输出的交互状态流推进为任务步骤序列：
找到玩具 → 接近玩具 → 拿起玩具 → 移动玩具 → 放入收纳盒

设计原则：
- 第一版用 FSM，不用 LSTM/Transformer（步骤结构明确，规则足够）；
- 完成条件必须持续成立（多帧依据），防止短暂误检造成跳步；
- 每步有超时：超时不判失败，只标记"不确定"，允许暂停后恢复；
- 绝不无依据地自动认定训练成功。

输入（World 字典，由集成层每帧组装）：
    interaction: 模块二输出的交互状态字符串
    toy:         玩具检测结果 {"center": (cx, cy), "bbox": (...)}（归一化）
    container:   收纳盒检测结果（同上）
    now:         当前时间戳

输出（summary 字典）：current_step / completed_steps / step_durations /
    total_elapsed / status(idle|running|done) / uncertain_events / events

本模块为纯逻辑，不依赖摄像头，可用 tests/test_behavior_fsm.py 单元测试。
"""

import time

# 可调参数（实验阶段按数据标定）
STEP_TIMEOUTS = {
    "find_toy": 30.0,
    "approach_toy": 30.0,
    "pick_toy": 30.0,
    "move_toy": 30.0,
    "place_toy": 45.0,
}
MOVE_DISP = 0.12     # 拿起后位移阈值（归一化，约0.12屏宽；实测1米距离下
                     # 0.25约合40cm，日常"挪个地方"只有10~20cm，故下调）
PLACE_HOLD = 1.5     # 放入判定：玩具停留在收纳框内的时长（秒）
DETECT_HOLD = 1.0    # 找到判定：玩具持续出现在画面中的时长（秒）


def point_in_box(px, py, bbox, expand=1.0):
    """点是否在放大 expand 倍的边界框内。"""
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    return (abs(px - cx) <= (x2 - x1) * expand / 2 and
            abs(py - cy) <= (y2 - y1) * expand / 2)


def dist2(p, q):
    return (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2


class Step:
    """单个行为步骤：名称 + 说明 + 完成条件函数。"""

    def __init__(self, name, desc, complete_fn):
        self.name = name
        self.desc = desc
        self.complete_fn = complete_fn


class BehaviorFSM:
    """连续行为步骤状态机。

    用法：
        fsm = BehaviorFSM()
        fsm.start(now)
        st = fsm.update(world, now)   # 每帧调用
        fsm.restart(now)              # 任务重新开始
    """

    def __init__(self):
        self.steps = self._make_steps()
        self.reset()

    def _make_steps(self):
        """定义任务的 5 个步骤及完成条件。"""
        return [
            Step("find_toy", "寻找玩具：玩具出现在画面中",
                 lambda fsm, w: fsm._toy_seen_long_enough(w)),
            Step("approach_toy", "接近玩具：手靠近或接触玩具",
                 lambda fsm, w: w.get("interaction") in (
                     "approaching", "touching_candidate",
                     "picking_candidate")),
            Step("pick_toy", "拿起玩具：物品随手位移",
                 lambda fsm, w: w.get("interaction") == "picking_candidate"),
            Step("move_toy", "移动玩具：离开拿起位置足够远",
                 lambda fsm, w: fsm._moved_enough(w)),
            Step("place_toy", "放入收纳盒：稳定停留在收纳框内",
                 lambda fsm, w: fsm._placed_in_box(w)),
        ]

    def reset(self):
        self.status = "idle"          # idle | running | done
        self.idx = 0                  # 当前步骤索引
        self.task_start = None
        self.step_start = None
        self.step_durations = []      # [(步骤名, 用时秒), ...]
        self.uncertain_events = []    # [(时间, 类型, 说明), ...]
        self.events = []              # 全部事件
        self._toy_seen_since = None   # 玩具开始持续出现的时刻
        self._pickup_center = None    # 拿起位置的玩具中心
        self._place_since = None      # 玩具开始停留在框内的时刻
        self._last_now = None         # 最近一次 update 的仿真时间

    # ---- 生命周期 ----
    def start(self, now):
        self.reset()
        self.status = "running"
        self.task_start = now
        self.step_start = now
        self._event(now, "task_start", self.steps[0].desc)

    def restart(self, now):
        """任务重新开始（清空全部进度）。"""
        self._event(now, "task_restart", "")
        self.start(now)

    def _event(self, now, etype, detail):
        self.events.append((now, etype, detail))
        if etype == "step_timeout":
            self.uncertain_events.append((now, etype, detail))

    # ---- 各步骤的复合条件 ----
    def _toy_seen_long_enough(self, w):
        """find_toy：玩具需持续出现 DETECT_HOLD 秒。"""
        now = w["now"]
        if w.get("toy") is not None:
            if self._toy_seen_since is None:
                self._toy_seen_since = now
            return now - self._toy_seen_since >= DETECT_HOLD
        self._toy_seen_since = None
        return False

    def _moved_enough(self, w):
        """move_toy：玩具中心离开拿起位置超过 MOVE_DISP。"""
        toy = w.get("toy")
        if toy is None or self._pickup_center is None:
            return False
        return dist2(toy["center"], self._pickup_center) >= MOVE_DISP ** 2

    def _placed_in_box(self, w):
        """place_toy：玩具进入收纳框（放大1.3倍）并停留 PLACE_HOLD 秒。"""
        toy, box, now = w.get("toy"), w.get("container"), w["now"]
        if toy is None or box is None:
            self._place_since = None
            return False
        if not point_in_box(toy["center"][0], toy["center"][1],
                            box["bbox"], expand=1.6):
            self._place_since = None
            return False
        if self._place_since is None:
            self._place_since = now
        return now - self._place_since >= PLACE_HOLD

    # ---- 每帧推进 ----
    def update(self, world, now):
        """输入组装好的 World（含 now），返回当前状态字典。"""
        self._last_now = now
        if self.status != "running":
            return self.summary()
        step = self.steps[self.idx]

        # 超时检查：超时不判失败，标记不确定，继续等待（允许恢复）
        if now - self.step_start > STEP_TIMEOUTS[step.name]:
            dup = [e for e in self.uncertain_events
                   if e[2].startswith(step.name)]
            if not dup:
                self._event(now, "step_timeout",
                            f"{step.name} 超时，继续等待（不确定）")

        # 完成条件检查
        if step.complete_fn(self, world):
            dur = now - self.step_start
            self.step_durations.append((step.name, round(dur, 1)))
            self._event(now, "step_complete", f"{step.name} 用时{dur:.1f}s")
            self.idx += 1
            self.step_start = now
            self._toy_seen_since = None
            self._place_since = None
            if step.name == "pick_toy":
                toy = world.get("toy")
                self._pickup_center = toy["center"] if toy else None
            if self.idx >= len(self.steps):
                self.status = "done"
                self._event(now, "task_complete",
                            f"总用时{now - self.task_start:.1f}s")
        return self.summary()

    def summary(self):
        """输出当前任务状态字典（集成层据此记录与展示）。"""
        cur = self.steps[self.idx] if self.status == "running" else None
        total = (self._last_now - self.task_start
                 if self.status == "running" and self.task_start
                 and self._last_now else
                 (sum(d for _, d in self.step_durations)
                  if self.status == "done" else 0.0))
        return {
            "status": self.status,
            "current_step": cur.name if cur else None,
            "current_desc": cur.desc if cur else "",
            "completed_steps": [n for n, _ in self.step_durations],
            "total_steps": len(self.steps),
            "step_durations": self.step_durations,
            "total_elapsed": round(total, 1),
            "uncertain_events": self.uncertain_events,
            "events": self.events,
        }
