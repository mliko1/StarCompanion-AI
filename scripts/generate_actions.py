# -*- coding: utf-8 -*-
"""
星伴AI 动作库生成脚本（一次性授权工具，运行时只读 JSON）。

把 100 个动作按"声明式规则"系统化产出：左右对称、按身体部位模板批量生成，
最终写入 data/actions.json（动作库）与 data/tasks.json（训练任务库）。
加/改动作：改本脚本里的定义后重跑即可；引擎 action_engine.py 零改动。

运行：py scripts/generate_actions.py
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTIONS_JSON = os.path.join(ROOT, "data", "actions.json")
TASKS_JSON = os.path.join(ROOT, "data", "tasks.json")

A = []          # 动作库
SKILLS = [      # 生活技能任务（非动作，保持不变）
    {"task_id": "pick_place_bottle", "name": "拿起瓶子放入目标", "type": "skill",
     "params": {"target": "bottle", "containers": ["book", "cup", "remote", "bowl", "clock", "keyboard"]},
     "difficulty": 2, "category": "生活技能"},
    {"task_id": "pick_place_cup", "name": "拿起杯子放到目标", "type": "skill",
     "params": {"target": "cup", "containers": ["book", "bowl", "remote", "clock", "keyboard"]},
     "difficulty": 2, "category": "生活技能"},
]


def add(pid, name, category, rules, priority=None, excludes=None, base=False):
    d = {"id": pid, "name": name, "category": category, "rules": rules}
    if priority is not None:
        d["priority"] = priority
    if excludes:
        d["excludes"] = excludes
    if base:
        d["base"] = True
    A.append(d)


# ---------- 原子条件构造 ----------
def dy(a, b, op, val):
    return {"f": "dy", "a": a, "b": b, "op": op, "val": val}


def dx(a, b, op, val):
    return {"f": "dx", "a": a, "b": b, "op": op, "val": val}


def ds(a, b, op, val):
    return {"f": "dist", "a": a, "b": b, "op": op, "val": val}


def rt(a, b, c0, d0, op, val):
    return {"f": "ratio", "a": a, "b": b, "c": c0, "d": d0, "op": op, "val": val}


def an(a, vertex, b, op, val):
    return {"f": "angle", "a": a, "b": vertex, "c": b, "op": op, "val": val}


# ---------- 关键点索引（MediaPipe 33 点，人物右侧在画面左侧即 x 较小） ----------
NOSE, L_EAR, R_EAR = 0, 7, 8
L_SHO, R_SHO = 11, 12
L_ELB, R_ELB = 13, 14
L_WRI, R_WRI = 15, 16
L_HIP, R_HIP = 23, 24
L_KNE, R_KNE = 25, 26
L_ANK, R_ANK = 27, 28
L_HEE, R_HEE = 29, 30
L_TOE, R_TOE = 31, 32

S = {
    "L": {"sho": L_SHO, "elb": L_ELB, "wri": L_WRI, "hip": L_HIP,
          "kne": L_KNE, "ank": L_ANK, "hee": L_HEE, "toe": L_TOE, "ear": L_EAR},
    "R": {"sho": R_SHO, "elb": R_ELB, "wri": R_WRI, "hip": R_HIP,
          "kne": R_KNE, "ank": R_ANK, "hee": R_HEE, "toe": R_TOE, "ear": R_EAR},
}

# =====================================================================
# 一、核心 23 个动作（沿用已调优的规则，保持不变）
# =====================================================================
add("raise_right", "举右手", "上肢", [[dy(R_WRI, R_SHO, "<", -0.06)]])
add("raise_left", "举左手", "上肢", [[dy(L_WRI, L_SHO, "<", -0.06)]])
add("both_hands_up", "双手上举", "上肢",
    [[dy(L_WRI, L_SHO, "<", -0.06), dy(R_WRI, R_SHO, "<", -0.06),
      an(L_SHO, L_ELB, L_WRI, ">", 140), an(R_SHO, R_ELB, R_WRI, ">", 140)]],
    priority=10, excludes=["raise_left", "raise_right"])
add("clap", "拍手", "上肢",
    [[rt("hc:L", "hc:R", L_SHO, R_SHO, "<", 0.55),
      dy("hc:L", "chest", "<", 0), dy("hc:L", "chest", ">", -0.12),
      dy("hc:R", "chest", "<", 0), dy("hc:R", "chest", ">", -0.12)]])
add("wave_right", "挥右手", "上肢",
    [[dy(R_WRI, R_SHO, "<", -0.06), dy(R_WRI, R_SHO, ">", -0.15),
      dx(R_WRI, R_SHO, "<", -0.12)]],
    priority=10, excludes=["raise_right"])
add("wave_left", "挥左手", "上肢",
    [[dy(L_WRI, L_SHO, "<", -0.06), dy(L_WRI, L_SHO, ">", -0.15),
      dx(L_WRI, L_SHO, ">", 0.12)]],
    priority=10, excludes=["raise_left"])
add("cross_arms", "双手交叉", "上肢",
    [[ds(L_WRI, R_WRI, "<", 0.12), dy(L_WRI, L_SHO, ">", 0.05)]],
    priority=25, excludes=["touch_belly", "touch_elbow_left", "touch_elbow_right"])
add("hands_on_hips", "叉腰", "上肢",
    [[ds(L_WRI, L_HIP, "<", 0.08), ds(R_WRI, R_HIP, "<", 0.08),
      dy(L_WRI, L_HIP, "<", 0.06), dy(R_WRI, R_HIP, "<", 0.06)]],
    priority=25, excludes=["hand_on_hip_left", "hand_on_hip_right",
                           "touch_hip_left", "touch_hip_right"])
add("hands_on_head", "抱头", "上肢",
    [[ds(L_WRI, NOSE, "<", 0.25), ds(R_WRI, NOSE, "<", 0.25),
      dy(L_WRI, NOSE, "<", 0.05), dy(R_WRI, NOSE, "<", 0.05),
      an(L_SHO, L_ELB, L_WRI, "<", 140), an(R_SHO, R_ELB, R_WRI, "<", 140)]],
    priority=25, excludes=["touch_head", "raise_left", "raise_right",
                           "touch_nose_left", "touch_nose_right",
                           "touch_forehead_left", "touch_forehead_right",
                           "touch_mouth_left", "touch_mouth_right",
                           "touch_ear_left", "touch_ear_right"])
add("stretch_chest", "扩胸", "上肢",
    [[rt(L_ELB, R_ELB, L_SHO, R_SHO, ">", 1.4),
      dy(L_ELB, L_SHO, ">", -0.06), dy(L_ELB, L_SHO, "<", 0.08),
      dy(R_ELB, R_SHO, ">", -0.06), dy(R_ELB, R_SHO, "<", 0.08)]])
add("nod_down", "低头", "头部",
    [[dy(NOSE, "chest", ">", -0.08), dy(L_SHO, L_HIP, "<", -0.15)]])
add("head_up", "抬头", "头部", [[dy(NOSE, "chest", "<", -0.25)]])
add("head_tilt_left", "歪头左", "头部", [[dy(L_EAR, R_EAR, ">", 0.03)]])
add("head_tilt_right", "歪头右", "头部", [[dy(L_EAR, R_EAR, "<", -0.03)]])
add("squat", "蹲下", "身体",
    [[dy(L_HIP, L_KNE, ">", -0.08), dy(R_HIP, R_KNE, ">", -0.08)]])
add("stand_up", "站直", "身体",
    [[dy(L_HIP, L_KNE, "<", -0.18), dy(R_HIP, R_KNE, "<", -0.18),
      dy(L_SHO, L_HIP, "<", 0)]], base=True)
add("lift_left_leg", "抬左腿", "身体",
    [[dy(L_ANK, R_ANK, "<", -0.08), dy(L_KNE, R_KNE, "<", -0.05)]])
add("lift_right_leg", "抬右腿", "身体",
    [[dy(R_ANK, L_ANK, "<", -0.08), dy(R_KNE, L_KNE, "<", -0.05)]])
add("bend_forward", "弯腰", "身体", [[dy(L_SHO, L_HIP, ">", -0.12)]])
add("touch_head", "摸头", "触碰",
    [[ds(L_WRI, NOSE, "<", 0.15), dy(L_WRI, NOSE, "<", -0.09), an(L_SHO, L_ELB, L_WRI, "<", 130)],
     [ds(R_WRI, NOSE, "<", 0.15), dy(R_WRI, NOSE, "<", -0.09), an(R_SHO, R_ELB, R_WRI, "<", 130)]],
    priority=5, excludes=["raise_right", "raise_left"])
add("touch_shoulder", "摸肩", "触碰",
    [[ds(L_WRI, R_SHO, "<", 0.13), dy(L_WRI, R_SHO, "<", 0.04), an(L_SHO, L_ELB, L_WRI, "<", 130)],
     [ds(R_WRI, L_SHO, "<", 0.13), dy(R_WRI, L_SHO, "<", 0.04), an(R_SHO, R_ELB, R_WRI, "<", 130)]])
add("touch_knee", "摸膝盖", "触碰",
    [[ds(L_WRI, L_KNE, "<", 0.16), dy(L_WRI, L_KNE, ">", -0.06), dy(L_KNE, L_HIP, ">", 0.10)],
     [ds(R_WRI, R_KNE, "<", 0.16), dy(R_WRI, R_KNE, ">", -0.06), dy(R_KNE, R_HIP, ">", 0.10)]])
add("touch_belly", "拍肚子", "触碰",
    [[ds(L_WRI, "belly", "<", 0.10), dy(L_WRI, "chest", ">", 0.04), an(L_SHO, L_ELB, L_WRI, "<", 130)],
     [ds(R_WRI, "belly", "<", 0.10), dy(R_WRI, "chest", ">", 0.04), an(R_SHO, R_ELB, R_WRI, "<", 130)]])

# =====================================================================
# 二、上肢扩展（26）
# =====================================================================
add("t_pose", "双臂侧平举", "上肢",
    [[dy(L_WRI, L_SHO, ">", -0.08), dy(L_WRI, L_SHO, "<", 0.08),
      dy(R_WRI, R_SHO, ">", -0.08), dy(R_WRI, R_SHO, "<", 0.08),
      dx(L_WRI, L_SHO, ">", 0.18), dx(R_WRI, R_SHO, "<", -0.18)]],
    priority=12, excludes=["raise_left", "raise_right", "arm_side_left", "arm_side_right"])
add("y_pose", "双臂斜上举", "上肢",
    [[dy(L_WRI, L_SHO, "<", -0.15), dy(R_WRI, R_SHO, "<", -0.15),
      dx(L_WRI, L_SHO, ">", 0.12), dx(R_WRI, R_SHO, "<", -0.12)]],
    priority=12, excludes=["raise_left", "raise_right", "both_hands_up", "arm_diag_up_left", "arm_diag_up_right"])
for s in ("R", "L"):
    p = S[s]
    add("arm_side_" + ("right" if s == "R" else "left"),
        ("右" if s == "R" else "左") + "臂侧平举", "上肢",
        [[dy(p["wri"], p["sho"], ">", -0.08), dy(p["wri"], p["sho"], "<", 0.08),
          dx(p["wri"], p["sho"], "<", -0.18) if s == "R" else dx(p["wri"], p["sho"], ">", 0.18)]],
        priority=10, excludes=["raise_right" if s == "R" else "raise_left",
                               "wave_right" if s == "R" else "wave_left"])
    add("arm_forward_" + ("right" if s == "R" else "left"),
        ("右" if s == "R" else "左") + "臂前平举", "上肢",
        [[dy(p["wri"], p["sho"], ">", -0.08), dy(p["wri"], p["sho"], "<", 0.12),
          dx(p["wri"], p["sho"], ">", -0.10), dx(p["wri"], p["sho"], "<", 0.10),
          an(p["sho"], p["elb"], p["wri"], ">", 130)]],
        priority=10, excludes=["raise_right" if s == "R" else "raise_left"])
    add("salute_" + ("right" if s == "R" else "left"),
        "敬礼" + ("右手" if s == "R" else "左手"), "上肢",
        [[ds(p["wri"], NOSE, "<", 0.16), dy(p["wri"], NOSE, "<", 0.06),
          dx(p["wri"], NOSE, "<", -0.03) if s == "R" else dx(p["wri"], NOSE, ">", 0.03),
          an(p["sho"], p["elb"], p["wri"], "<", 130)]],
        priority=20, excludes=["touch_head", "touch_forehead_left", "touch_forehead_right"])
    add("hand_on_chest_" + ("right" if s == "R" else "left"),
        ("右" if s == "R" else "左") + "手捂胸", "上肢",
        [[ds(L_WRI, R_WRI, ">", 0.22), ds(p["wri"], "chest", "<", 0.12),
          dy(p["wri"], "chest", ">", -0.05),
          an(p["sho"], p["elb"], p["wri"], "<", 130)]],
        priority=20, excludes=["touch_chest_left", "touch_chest_right"])
    add("hand_on_hip_" + ("right" if s == "R" else "left"),
        ("右" if s == "R" else "左") + "手叉腰", "上肢",
        [[ds(p["wri"], p["hip"], "<", 0.08), dy(p["wri"], p["hip"], "<", 0.06)]],
        priority=20, excludes=["touch_hip_left", "touch_hip_right"])
    add("elbow_out_" + ("right" if s == "R" else "left"),
        ("右" if s == "R" else "左") + "肘外展", "上肢",
        [[dy(p["elb"], p["sho"], ">", -0.06), dy(p["elb"], p["sho"], "<", 0.10),
          dx(p["elb"], p["sho"], "<", -0.10) if s == "R" else dx(p["elb"], p["sho"], ">", 0.10),
          dy(p["wri"], p["sho"], ">", 0.02)]])
    add("arm_diag_up_" + ("right" if s == "R" else "left"),
        ("右" if s == "R" else "左") + "臂斜上举", "上肢",
        [[dy(p["wri"], p["sho"], "<", -0.15),
          dx(p["wri"], p["sho"], "<", -0.08) if s == "R" else dx(p["wri"], p["sho"], ">", 0.08)]],
        priority=10, excludes=["raise_right" if s == "R" else "raise_left",
                               "wave_right" if s == "R" else "wave_left"])
    add("arm_half_" + ("right" if s == "R" else "left"),
        ("右" if s == "R" else "左") + "臂半举", "上肢",
        [[dy(p["wri"], p["sho"], "<", -0.06), dy(p["wri"], p["sho"], ">", -0.15),
          dx(p["wri"], p["sho"], ">", -0.10), dx(p["wri"], p["sho"], "<", 0.10),
          an(p["sho"], p["elb"], p["wri"], ">", 130)]],
        priority=10, excludes=["raise_right" if s == "R" else "raise_left"])
add("hug_self", "拥抱自己", "上肢",
    [[ds(L_WRI, R_SHO, "<", 0.15), ds(R_WRI, L_SHO, "<", 0.15),
      dy(L_WRI, R_SHO, "<", 0.06), dy(R_WRI, L_SHO, "<", 0.06),
      an(L_SHO, L_ELB, L_WRI, "<", 130), an(R_SHO, R_ELB, R_WRI, "<", 130)]],
    priority=20, excludes=["touch_shoulder", "cross_arms"])
add("hands_pray", "双手合十", "上肢",
    [[rt("hc:L", "hc:R", L_SHO, R_SHO, "<", 0.55),
      dy("hc:L", "chest", ">", 0.0), dy("hc:L", "chest", "<", 0.15),
      dy("hc:R", "chest", ">", 0.0), dy("hc:R", "chest", "<", 0.15)]],
    priority=10, excludes=["clap"])
add("hands_behind", "双手背后", "上肢",
    [[ds(L_WRI, R_WRI, "<", 0.15), dy(L_WRI, L_HIP, ">", 0.0),
      dy(L_WRI, L_HIP, "<", 0.12)]],
    priority=10, excludes=["cross_arms", "touch_belly"])
add("shrug", "耸肩", "上肢",
    [[dy(L_SHO, L_HIP, "<", -0.30), dy(R_SHO, R_HIP, "<", -0.30),
      dy(L_SHO, L_EAR, "<", 0.20), dy(R_SHO, R_EAR, "<", 0.20)]])
add("arms_down", "双臂下垂", "上肢",
    [[dy(L_WRI, L_SHO, ">", 0.06), dy(R_WRI, R_SHO, ">", 0.06)]], base=True)
add("wave_both", "双手挥动", "上肢",
    [[dy(L_WRI, L_SHO, "<", -0.06), dy(R_WRI, R_SHO, "<", -0.06),
      dx(L_WRI, L_SHO, ">", 0.12), dx(R_WRI, R_SHO, "<", -0.12)]],
    priority=12, excludes=["raise_left", "raise_right", "wave_left", "wave_right"])
add("clap_overhead", "头顶拍手", "上肢",
    [[rt("hc:L", "hc:R", L_SHO, R_SHO, "<", 0.5),
      dy("hc:L", NOSE, "<", -0.06), dy("hc:R", NOSE, "<", -0.06)]],
    priority=12, excludes=["clap", "both_hands_up", "hands_on_head"])
add("raise_both_forward", "双手前平举", "上肢",
    [[ds(L_WRI, R_WRI, ">", 0.18),
      dy(L_WRI, L_SHO, ">", -0.08), dy(L_WRI, L_SHO, "<", 0.12),
      dy(R_WRI, R_SHO, ">", -0.08), dy(R_WRI, R_SHO, "<", 0.12),
      dx(L_WRI, L_SHO, "<", 0.10), dx(L_WRI, L_SHO, ">", -0.10),
      dx(R_WRI, R_SHO, "<", 0.10), dx(R_WRI, R_SHO, ">", -0.10)]])

# =====================================================================
# 三、头部扩展（3）
# =====================================================================
add("look_left", "头向左转", "头部", [[dx(NOSE, "chest", ">", 0.08)]])
add("look_right", "头向右转", "头部", [[dx(NOSE, "chest", "<", -0.08)]])
add("head_deep_tilt_left", "头靠左肩", "头部",
    [[dy(L_EAR, R_EAR, ">", 0.10), dy(L_EAR, L_SHO, ">", -0.15)]],
    priority=10, excludes=["head_tilt_left"])
add("head_deep_tilt_right", "头靠右肩", "头部",
    [[dy(L_EAR, R_EAR, "<", -0.10), dy(R_EAR, R_SHO, ">", -0.15)]],
    priority=10, excludes=["head_tilt_right"])

# =====================================================================
# 四、躯干扩展（6）
# =====================================================================
add("lean_left", "身体左倾", "身体", [[dx(L_SHO, L_HIP, ">", 0.14)]])
add("lean_right", "身体右倾", "身体", [[dx(L_SHO, L_HIP, "<", -0.14)]])
add("twist_left", "上身左转", "身体", [[dx(L_SHO, L_HIP, ">", 0.12), dx(L_SHO, R_SHO, ">", 0.14)]])
add("twist_right", "上身右转", "身体", [[dx(L_SHO, L_HIP, "<", -0.12), dx(L_SHO, R_SHO, "<", 0.06)]])
add("deep_squat", "深蹲", "身体",
    [[dy(L_HIP, L_KNE, ">", -0.02), dy(R_HIP, R_KNE, ">", -0.02),
      dy(L_HIP, L_ANK, "<", 0.20)]], priority=10, excludes=["squat"])
add("sit_floor", "坐地", "身体",
    [[dy(L_HIP, L_KNE, ">", 0.0), dy(L_HIP, L_ANK, "<", 0.28),
      dy(L_SHO, L_HIP, "<", -0.05)]], priority=10, excludes=["squat", "deep_squat", "stand_up"])

# =====================================================================
# 五、下肢扩展（14）
# =====================================================================
for s in ("R", "L"):
    p = S[s]
    o = S["L" if s == "R" else "R"]
    add("kick_" + ("right" if s == "R" else "left"),
        ("右" if s == "R" else "左") + "前踢", "下肢",
        [[dy(p["kne"], p["hip"], ">", 0.02), dy(p["ank"], p["kne"], "<", -0.02),
          dy(p["ank"], o["ank"], "<", -0.10)]])
    add("side_raise_" + ("right" if s == "R" else "left") + "_leg",
        ("右" if s == "R" else "左") + "侧抬腿", "下肢",
        [[dy(p["ank"], o["ank"], "<", -0.10),
          dx(p["ank"], p["hip"], "<", -0.10) if s == "R" else dx(p["ank"], p["hip"], ">", 0.10)]])
    add("heel_butt_" + ("right" if s == "R" else "left"),
        ("右" if s == "R" else "左") + "后勾腿", "下肢",
        [[dy(p["ank"], p["hip"], "<", -0.05), dy(p["ank"], p["kne"], "<", 0.0),
          dy(p["kne"], p["hip"], "<", 0.02)]])
    add("lunge_" + ("right" if s == "R" else "left"),
        ("右" if s == "R" else "左") + "弓步", "下肢",
        [[dy(p["kne"], p["ank"], "<", 0.25),
          dx(p["kne"], p["hip"], "<", -0.05) if s == "R" else dx(p["kne"], p["hip"], ">", 0.05),
          dy(p["kne"], p["hip"], ">", 0.05)]])
    add("one_leg_" + ("right" if s == "R" else "left"),
        ("右" if s == "R" else "左") + "单脚站", "下肢",
        [[dy(p["ank"], o["ank"], "<", -0.20), dy(p["kne"], o["kne"], "<", -0.10)]])

add("tip_toe", "踮脚尖", "下肢",
    [[dy(L_HEE, L_TOE, "<", -0.06), dy(R_HEE, R_TOE, "<", -0.06)]])
add("legs_cross", "双腿交叉", "下肢", [[ds(L_KNE, R_KNE, "<", 0.07), ds(L_ANK, R_ANK, "<", 0.07)]])
add("wide_stance", "马步", "下肢",
    [[dx(L_ANK, R_ANK, ">", 0.35), dy(L_HIP, L_KNE, ">", -0.12)]])
add("kneel_left", "左膝跪地", "下肢",
    [[dy(L_KNE, L_ANK, "<", 0.15), dy(L_KNE, L_HIP, "<", 0.20),
      dy(R_KNE, R_ANK, ">", 0.15)]])
add("kneel_right", "右膝跪地", "下肢",
    [[dy(R_KNE, R_ANK, "<", 0.15), dy(R_KNE, R_HIP, "<", 0.20),
      dy(L_KNE, L_ANK, ">", 0.15)]])

# =====================================================================
# 六、触碰扩展（22，按部位 × 左右手）
# =====================================================================
# 目标点：中心(鼻/额/嘴) 左右手均可；同侧(耳/髋/大腿/踝/脚尖) 用同侧手；
#         对侧(肘) 用对侧手。
FACE_CENTER = [("touch_nose", "摸鼻", NOSE),
               ("touch_forehead", "摸额头", "mid:2:5"),
               ("touch_mouth", "摸嘴", "mid:9:10")]
for s in ("L", "R"):
    p = S[s]
    hand = p["wri"]
    arm = an(p["sho"], p["elb"], p["wri"], "<", 130)
    tag = "left" if s == "L" else "right"
    for pid, nm, tgt in FACE_CENTER:
        add(pid + "_" + tag, nm + ("（左手）" if s == "L" else "（右手）"), "触碰",
            [[ds(hand, tgt, "<", 0.13), dy(hand, tgt, ">", -0.06), dy(hand, tgt, "<", 0.06), arm]],
            priority=30, excludes=["touch_head"])
    # 同侧触碰：耳 / 髋 / 大腿 / 踝 / 脚尖
    add("touch_ear_" + tag, "摸耳" + ("（左手）" if s == "L" else "（右手）"), "触碰",
        [[ds(hand, p["ear"], "<", 0.12), dy(hand, p["ear"], ">", -0.06), dy(hand, p["ear"], "<", 0.06), arm]],
        priority=30, excludes=["touch_head"])
    add("touch_hip_" + tag, "摸髋" + ("（左手）" if s == "L" else "（右手）"), "触碰",
        [[ds(hand, p["hip"], "<", 0.10), dy(hand, p["hip"], "<", 0.06)]],
        priority=30)
    shin = "mid:%d:%d" % (p["kne"], p["ank"])
    add("touch_shin_" + tag, "摸小腿" + ("（左手）" if s == "L" else "（右手）"), "触碰",
        [[ds(hand, shin, "<", 0.16), dy(hand, shin, ">", -0.06),
          dy(p["ank"], p["kne"], ">", 0.10)]], priority=30)
    add("touch_ankle_" + tag, "摸脚踝" + ("（左手）" if s == "L" else "（右手）"), "触碰",
        [[ds(hand, p["ank"], "<", 0.16), dy(hand, p["ank"], ">", -0.06),
          dy(p["ank"], p["kne"], ">", 0.10)]], priority=30)
    add("touch_toe_" + tag, "摸脚尖" + ("（左手）" if s == "L" else "（右手）"), "触碰",
        [[ds(hand, p["toe"], "<", 0.16), dy(hand, p["toe"], ">", -0.04),
          dy(p["ank"], p["kne"], ">", 0.10)]], priority=30)
    # 对侧触碰：肘
    other = S["R" if s == "L" else "L"]
    add("touch_elbow_" + tag, "摸肘" + ("（左手）" if s == "L" else "（右手）"), "触碰",
        [[ds(hand, other["elb"], "<", 0.14), dy(hand, other["elb"], "<", 0.08), arm]],
        priority=30, excludes=["touch_shoulder"])
# 脖颈（中心目标，用胸前中点近似）
add("touch_neck_left", "摸脖子（左手）", "触碰",
    [[ds(L_WRI, R_WRI, ">", 0.22), ds(L_WRI, "mid:11:12", "<", 0.13),
      dy(L_WRI, "mid:11:12", "<", 0.04),
      an(L_SHO, L_ELB, L_WRI, "<", 130)]], priority=30)
add("touch_neck_right", "摸脖子（右手）", "触碰",
    [[ds(L_WRI, R_WRI, ">", 0.22), ds(R_WRI, "mid:11:12", "<", 0.13),
      dy(R_WRI, "mid:11:12", "<", 0.04),
      an(R_SHO, R_ELB, R_WRI, "<", 130)]], priority=30)

# =====================================================================
# 七、组合动作（6）
# =====================================================================
add("raise_right_lift_left", "举右手抬左腿", "组合",
    [[dy(R_WRI, R_SHO, "<", -0.06), dy(L_ANK, R_ANK, "<", -0.08)]],
    priority=15, excludes=["raise_right", "lift_left_leg"])
add("raise_left_lift_right", "举左手抬右腿", "组合",
    [[dy(L_WRI, L_SHO, "<", -0.06), dy(R_ANK, L_ANK, "<", -0.08)]],
    priority=15, excludes=["raise_left", "lift_right_leg"])
add("raise_right_lift_right", "举右手抬右腿", "组合",
    [[dy(R_WRI, R_SHO, "<", -0.06), dy(R_ANK, L_ANK, "<", -0.08)]],
    priority=15, excludes=["raise_right", "lift_right_leg"])
add("raise_left_lift_left", "举左手抬左腿", "组合",
    [[dy(L_WRI, L_SHO, "<", -0.06), dy(L_ANK, R_ANK, "<", -0.08)]],
    priority=15, excludes=["raise_left", "lift_left_leg"])
add("t_pose_one_leg", "单脚站T字", "组合",
    [[dy(L_WRI, L_SHO, ">", -0.08), dy(L_WRI, L_SHO, "<", 0.08),
      dy(R_WRI, R_SHO, ">", -0.08), dy(R_WRI, R_SHO, "<", 0.08),
      dx(L_WRI, L_SHO, ">", 0.18), dx(R_WRI, R_SHO, "<", -0.18),
      dy(L_ANK, R_ANK, "<", -0.20)]],
    priority=20, excludes=["t_pose", "one_leg_left"])
add("y_pose_one_leg", "单脚站Y字", "组合",
    [[dy(L_WRI, L_SHO, "<", -0.15), dy(R_WRI, R_SHO, "<", -0.15),
      dx(L_WRI, L_SHO, ">", 0.12), dx(R_WRI, R_SHO, "<", -0.12),
      dy(R_ANK, L_ANK, "<", -0.20)]],
    priority=20, excludes=["y_pose", "one_leg_right"])

# =====================================================================
# 输出
# =====================================================================
assert len(A) == 100, f"动作数量应为 100，实际 {len(A)}"
ids = [a["id"] for a in A]
assert len(ids) == len(set(ids)), "存在重复 id"

actions_doc = {
    "_说明": "星伴AI 动作库（声明式规则，共 100 个动作）。加动作=加一条 JSON，不改代码。特征：dy(高低)/dx(左右)/dist(距离)/ratio(距离比)/angle(角度)。点引用：整数索引、mid:i:j、hc:L/hc:R、chest、belly。字段：rules(条件组，组内AND组间OR)、excludes(命中压制)、priority(优先级)、base(静止姿态)。",
    "actions": A,
}
with open(ACTIONS_JSON, "w", encoding="utf-8") as f:
    json.dump(actions_doc, f, ensure_ascii=False, indent=2)

tasks = []
for a in A:
    tasks.append({
        "task_id": "action_" + a["id"],
        "name": a["name"],
        "type": "action",
        "params": {"action_id": a["id"]},
        "difficulty": 1,
        "category": a["category"] + "动作",
    })
tasks += SKILLS
tasks_doc = {"_说明": "星伴AI 训练任务库：动作由 data/actions.json 声明式驱动", "tasks": tasks}
with open(TASKS_JSON, "w", encoding="utf-8") as f:
    json.dump(tasks_doc, f, ensure_ascii=False, indent=2)

print(f"已生成 {len(A)} 个动作 -> data/actions.json")
print(f"已生成 {len(tasks)} 个任务 -> data/tasks.json")
