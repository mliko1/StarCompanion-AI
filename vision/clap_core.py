# -*- coding: utf-8 -*-
"""
兼容转发层（P0 消重后保留，避免破坏既有 import）。

原 clap_core.py 的公共逻辑已下沉到：
- pose_utils（point_reliable / hand_center / dist2d / angle_at / 平滑）
- action_base（clap_check / fast_close_enough / ClapCounter / raise_check）

仍 `from clap_core import ...` 的模块（action_engine / action_library /
debug_pose / clap_hands）可继续工作，无需改动。
"""

from pose_utils import point_reliable, hand_center  # noqa: F401
from action_base import (  # noqa: F401
    clap_check, fast_close_enough, ClapCounter,
    CONTACT_HIGH, CONTACT_LOW, REARM_RATIO, REARM_TIME, FAST_DROP, FAST_SPEED,
)

__all__ = [
    "point_reliable", "hand_center",
    "clap_check", "fast_close_enough", "ClapCounter",
    "CONTACT_HIGH", "CONTACT_LOW", "REARM_RATIO", "REARM_TIME",
    "FAST_DROP", "FAST_SPEED",
]
