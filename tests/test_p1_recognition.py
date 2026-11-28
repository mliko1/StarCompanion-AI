# -*- coding: utf-8 -*-
"""P1 识别与数据闭环单测：跟踪 ID 锁定、连续置信度、复核回流。

运行：python tests/test_p1_recognition.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vision"))
sys.path.insert(0, ROOT)

from action_engine import (Pt, detect_actions_with_scores,  # noqa: E402
                           _cond_score)
from interaction_detector import InteractionDetector  # noqa: E402
from core.personalization import (PersonalProfile,  # noqa: E402
                                  effective_params)
from api import reports as reports_api  # noqa: E402


def make_pose():
    lms = [Pt(0.5, 0.5, 0, 1) for _ in range(33)]
    lms[11], lms[12] = Pt(0.4, 0.4, 0, 1), Pt(0.6, 0.4, 0, 1)
    lms[23], lms[24] = Pt(0.4, 0.7, 0, 1), Pt(0.6, 0.7, 0, 1)
    return lms


def test_score_monotonic():
    action = {"id": "hand_high", "name": "手举高", "category": "测试",
              "rules": [[{"f": "dy", "a": 15, "b": 11,
                          "op": "<", "val": 0.0}]]}
    lms = make_pose()
    lms[15] = Pt(0.4, 0.36, 0, 1)   # 刚过阈值 0.04
    _, s1 = detect_actions_with_scores(lms, [action])
    lms[15] = Pt(0.4, 0.10, 0, 1)   # 远高于阈值 0.30
    _, s2 = detect_actions_with_scores(lms, [action])
    assert "hand_high" in s1 and "hand_high" in s2
    assert s2["hand_high"] > s1["hand_high"], (s1, s2)


def test_interaction_tracks_same_object():
    d = InteractionDetector("teddy bear", 640, 480)
    pose = make_pose()
    pose[15] = Pt(0.5, 0.5, 0, 1)
    dets = [
        {"name": "teddy bear", "track_id": "coco:1", "confidence": 0.80,
         "bbox": (280, 220, 360, 300), "center": (320, 260)},
        {"name": "teddy bear", "track_id": "coco:2", "confidence": 0.95,
         "bbox": (80, 220, 160, 300), "center": (120, 260)},
    ]
    d.update(pose, dets, 0.0)
    assert d.target_track_id == "coco:1"  # 手靠近 1 号，未锁定更高置信度的 2 号
    assert d.evidence["track_id"] == "coco:1"
    assert 0 <= d.confidence <= 1


def test_review_feedback_uses_personal_profile(monkeypatch=None):
    """复核回流函数可独立调用；用假的 DB 访问避免依赖真实训练记录。"""
    calls = {}

    p = PersonalProfile(1, 2)
    p.record("amplitude_scale", 1.0)
    monkeypatch = {
        "list_personal_profiles": lambda **kw: [],
        "sync_personal_profile_from_logic": lambda prof: calls.update(prof=prof),
    }
    old_list, old_sync = reports_api.crud.list_personal_profiles, \
        reports_api.crud.sync_personal_profile_from_logic
    reports_api.crud.list_personal_profiles = monkeypatch["list_personal_profiles"]
    reports_api.crud.sync_personal_profile_from_logic = monkeypatch["sync_personal_profile_from_logic"]

    class VR:
        session_id = 99
    class S:
        child_id = 1
        task_id = 2
    class DB:
        def query(self, _m):
            class Q:
                def filter_by(self, **kw):
                    return self
                def count(self):
                    return 1
            return Q()
        def get(self, _m, _id):
            return VR() if _m.__name__ == "VisionRecord" else S()
        def close(self):
            pass
    old_session = reports_api.report_session_local
    reports_api.report_session_local = DB

    class Req:
        corrected_result = {"preferred_hand": "left"}
        is_correct = False
    try:
        reports_api._apply_review_to_profile(1, Req())
    finally:
        reports_api.crud.list_personal_profiles = old_list
        reports_api.crud.sync_personal_profile_from_logic = old_sync
        reports_api.report_session_local = old_session
    prof = calls["prof"]
    assert effective_params(prof)["preferred_hand"] == "left"
    assert 0.4 <= prof.samples("amplitude_scale")[-1] <= 1.0


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS:", t.__name__)
    print(f"test_p1_recognition：{len(tests)}/{len(tests)} 通过")


if __name__ == "__main__":
    main()
