# -*- coding: utf-8 -*-
"""
behavior_sequence.BehaviorFSM 的单元测试（无需摄像头）。

运行方式（在项目根目录）：python tests/test_behavior_fsm.py
全部通过会打印 PASS；任何断言失败会抛出 AssertionError。
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vision.behavior_sequence import BehaviorFSM  # noqa: E402

TOY = {"center": (0.5, 0.6), "bbox": (0.45, 0.55, 0.55, 0.65)}
BOX = {"center": (0.7, 0.4), "bbox": (0.62, 0.33, 0.78, 0.47)}
TOY_MOVED = {"center": (0.68, 0.42), "bbox": (0.63, 0.37, 0.73, 0.47)}


def world(now, interaction="uncertain", toy=None, container=None):
    return {"now": now, "interaction": interaction,
            "toy": toy, "container": container}


def test_full_task():
    """完整任务：5步依序完成，事件链正确。"""
    fsm = BehaviorFSM()
    t = 100.0
    fsm.start(t)

    # 步骤1 find_toy：玩具出现但不足1秒，不应完成
    st = fsm.update(world(t + 0.5, toy=TOY), t + 0.5)
    assert st["current_step"] == "find_toy"
    # 持续出现满1秒后完成（首次出现于t+0.5，t+1.7时已持续1.2秒）
    st = fsm.update(world(t + 1.7, toy=TOY), t + 1.7)
    assert st["current_step"] == "approach_toy", st
    assert st["completed_steps"] == ["find_toy"]

    # 步骤2 approach_toy：手靠近
    st = fsm.update(world(t + 3.0, interaction="approaching",
                          toy=TOY), t + 3.0)
    assert st["current_step"] == "pick_toy", st

    # 步骤3 pick_toy：touching不应推进；必须picking
    st = fsm.update(world(t + 4.0, interaction="touching_candidate",
                          toy=TOY), t + 4.0)
    assert st["current_step"] == "pick_toy", st
    st = fsm.update(world(t + 5.0, interaction="picking_candidate",
                          toy=TOY), t + 5.0)
    assert st["current_step"] == "move_toy", st

    # 步骤4 move_toy：玩具还在原位不应完成；移远后完成
    st = fsm.update(world(t + 6.0, interaction="picking_candidate",
                          toy=TOY), t + 6.0)
    assert st["current_step"] == "move_toy", st
    st = fsm.update(world(t + 7.0, interaction="picking_candidate",
                          toy=TOY_MOVED), t + 7.0)
    assert st["current_step"] == "place_toy", st

    # 步骤5 place_toy：进入框但停留不足1.5秒不应完成
    st = fsm.update(world(t + 7.5, toy=TOY_MOVED, container=BOX), t + 7.5)
    assert st["current_step"] == "place_toy", st
    st = fsm.update(world(t + 9.0, toy=TOY_MOVED, container=BOX), t + 9.0)
    assert st["status"] == "done", st
    assert len(st["step_durations"]) == 5
    assert st["uncertain_events"] == []
    print("PASS: test_full_task")


def test_timeout_marks_uncertain_not_fail():
    """超时只标记不确定，不判失败，条件恢复后仍可完成。"""
    fsm = BehaviorFSM()
    t = 200.0
    fsm.start(t)
    # find_toy 超过30秒超时且玩具一直不出现
    st = fsm.update(world(t + 35.0), t + 35.0)
    assert st["current_step"] == "find_toy", "超时不应跳步"
    assert len(st["uncertain_events"]) == 1, st
    # 之后玩具出现，仍能正常完成该步骤
    fsm.update(world(t + 40.0, toy=TOY), t + 40.0)
    st = fsm.update(world(t + 41.5, toy=TOY), t + 41.5)
    assert st["current_step"] == "approach_toy", st
    print("PASS: test_timeout_marks_uncertain_not_fail")


def test_pause_and_resume():
    """中途信号消失（暂停），恢复后继续，不重置进度。"""
    fsm = BehaviorFSM()
    t = 300.0
    fsm.start(t)
    fsm.update(world(t + 1.2, toy=TOY), t + 1.2)          # 开始观察玩具
    fsm.update(world(t + 3.0, interaction="approaching",
                     toy=TOY), t + 3.0)                   # find 完成
    fsm.update(world(t + 3.5, interaction="approaching",
                     toy=TOY), t + 3.5)                   # approach 完成
    # 长时间中断（人离开画面）
    st = fsm.update(world(t + 20.0), t + 20.0)
    assert st["current_step"] == "pick_toy", st
    assert st["completed_steps"] == ["find_toy", "approach_toy"]
    # 恢复：拿起信号出现，继续推进
    st = fsm.update(world(t + 25.0, interaction="picking_candidate",
                          toy=TOY), t + 25.0)
    assert st["current_step"] == "move_toy", st
    print("PASS: test_pause_and_resume")


def test_restart_clears_everything():
    """重新开始：进度、事件、不确定记录全部清空。"""
    fsm = BehaviorFSM()
    t = 400.0
    fsm.start(t)
    fsm.update(world(t + 35.0), t + 35.0)   # 制造一次超时不确定
    assert len(fsm.summary()["uncertain_events"]) == 1
    fsm.restart(t + 36.0)
    st = fsm.summary()
    assert st["status"] == "running"
    assert st["current_step"] == "find_toy"
    assert st["completed_steps"] == []
    assert st["uncertain_events"] == []
    print("PASS: test_restart_clears_everything")


def test_no_auto_success():
    """全 uncertain 输入下任务永不自动完成。"""
    fsm = BehaviorFSM()
    t = 500.0
    fsm.start(t)
    for i in range(100):
        st = fsm.update(world(t + i, interaction="uncertain"), t + i)
    assert st["status"] == "running"
    assert st["current_step"] == "find_toy"
    print("PASS: test_no_auto_success")


if __name__ == "__main__":
    test_full_task()
    test_timeout_marks_uncertain_not_fail()
    test_pause_and_resume()
    test_restart_clears_everything()
    test_no_auto_success()
    print("全部单元测试通过")

