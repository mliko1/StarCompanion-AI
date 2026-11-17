# -*- coding: utf-8 -*-
"""统一视觉事件数据格式（升级建议文档第九节核心要求）。

每个视觉事件至少包含：事件类型、事件名称、时间戳、置信度、关联任务步骤。
事件同时写入内存缓冲（供接口实时读取）与数据库 vision_record
（AI 原始结果，与人工确认 manual_review 分开存储，不被覆盖）。
"""

import collections
import threading

# 事件类型 -> 中文说明
EVENT_TYPES = {
    "step_started": "步骤开始",
    "step_completed": "步骤完成",
    "interaction_changed": "交互状态变化",
    "uncertainty": "不确定",
    "object_detected": "物品检测",
    "action_detected": "动作识别",
    "task_started": "任务开始",
    "task_finished": "任务结束",
}


def make_event(event_type, event_name, timestamp, task_step=None,
               confidence=None, session_id=None, details=None):
    """构造一个统一格式的视觉事件 dict。"""
    return {
        "event_type": event_type,
        "event_name": event_name,
        "timestamp": round(timestamp, 3),
        "confidence": confidence,
        "task_step": task_step,
        "session_id": session_id,
        "details": details or {},
    }


class EventBuffer:
    """线程安全的事件环形缓冲（保留最近 N 条，供接口实时读取）。"""

    def __init__(self, maxlen=200):
        self._buf = collections.deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def add(self, event):
        with self._lock:
            self._buf.append(event)

    def recent(self, n=50):
        with self._lock:
            return list(self._buf)[-n:]

    def clear(self):
        with self._lock:
            self._buf.clear()


# 全局事件缓冲
events = EventBuffer()
