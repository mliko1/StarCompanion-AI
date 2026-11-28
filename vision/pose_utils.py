# -*- coding: utf-8 -*-
"""
星伴AI 姿态关键点公共工具层（P0 消重成果）。

统一提供各动作识别模块反复复制的基础能力，避免每个脚本各自造轮子：
1. 关键点编号与骨架连线常量；
2. 关键点可靠性评估（置信度 + 出画判定）；
3. 几何计算（两点距离、三点夹角、手掌中心、镜像坐标）；
4. 时序平滑（指数平滑 + 边缘区加强 + 出画锁定）。

供 raise_hand / clap_hands / task_session / action_engine 等模块复用。
"""

import math

# ---------------------------------------------------------------------------
# 关键点编号（MediaPipe Pose Landmarker 33 点模型）
# ---------------------------------------------------------------------------
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24

# 手掌四点（手腕 + 小指根 + 食指根 + 拇指）
HAND_POINTS_L = (15, 17, 19, 21)
HAND_POINTS_R = (16, 18, 20, 22)

# MediaPipe Hands 21 点中的掌心五点：手腕 + 食指/中指/无名指/小指掌指关节。
# 比 Pose 的 4 点掌心更稳，且能区分握拳/张手。
HAND_PALM_21 = (0, 5, 9, 13, 17)

HEAD_POINTS = [0, 7, 8]  # 鼻尖、左耳、右耳

# ---------------------------------------------------------------------------
# 骨架连线（身体，不含头面部）
# ---------------------------------------------------------------------------
POSE_CONNECTIONS = [
    (11, 12), (11, 23), (12, 24), (23, 24),
    (11, 13), (13, 15), (12, 14), (14, 16),
    (15, 17), (15, 19), (15, 21), (17, 19),
    (16, 18), (16, 20), (16, 22), (18, 20),
    (21, 23), (22, 24),
    (23, 25), (25, 27), (27, 29), (29, 31), (27, 31),
    (24, 26), (26, 28), (28, 30), (30, 32), (28, 32),
]

# 完整连线（含头面部），需要画头部时使用
POSE_CONNECTIONS_FULL = [
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (7, 8),
    (9, 10),
] + POSE_CONNECTIONS

# 展示用精简骨架：只画身体轮廓与四肢，不画面部/手指细节。
# 家长大屏上脸部线条太密会干扰观察，头部只用「肩膀→头部中心」两根线示意。
POSE_CONNECTIONS_DISPLAY = [
    (11, 12), (11, 0), (12, 0),
    (11, 23), (12, 24), (23, 24),
    (11, 13), (13, 15), (12, 14), (14, 16),
    (23, 25), (25, 27), (27, 29), (29, 31),
    (24, 26), (26, 28), (28, 30), (30, 32),
]

# ---------------------------------------------------------------------------
# 关键点可靠性评估
# ---------------------------------------------------------------------------
DEFAULT_MIN_VISIBILITY = 0.3


def point_reliable(lm, min_visibility=DEFAULT_MIN_VISIBILITY, margin=None):
    """关键点可靠性检查：置信度足够，且坐标在画面内。

    - margin=None：只要真正出画（坐标越界 -0.01~1.01）或置信度极低才不可靠，
      边缘区由平滑加强来压抖动（拍手/任务会话/动作引擎默认语义）。
    - margin=数值：距画面边缘 margin 以内视为不可靠（手臂出画冻结的严格语义）。

    手臂出画时模型只能"猜"位置，坐标会剧烈抖动，必须按场景取舍。"""
    if lm.visibility <= min_visibility:
        return False
    if margin is None:
        return -0.01 < lm.x < 1.01 and -0.01 < lm.y < 1.01
    return margin < lm.x < 1 - margin and margin < lm.y < 1 - margin


def near_edge(lm, margin):
    """点是否落在画面边缘 margin 以内（用于边缘区加强平滑）。"""
    return (lm.x < margin or lm.x > 1 - margin or
            lm.y < margin or lm.y > 1 - margin)


# ---------------------------------------------------------------------------
# 几何计算
# ---------------------------------------------------------------------------
def dist2d(p1, p2):
    """两点欧氏距离（2D）。p1/p2 为含 x/y 属性的对象。"""
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


def angle_at(p1, p2, p3):
    """以 p2 为顶点、p1 和 p3 为两端的夹角（单位：度）。"""
    v1 = (p1.x - p2.x, p1.y - p2.y)
    v2 = (p3.x - p2.x, p3.y - p2.y)
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    n1 = (v1[0] ** 2 + v1[1] ** 2) ** 0.5
    n2 = (v2[0] ** 2 + v2[1] ** 2) ** 0.5
    if n1 * n2 == 0:
        return 0.0
    cos_a = max(-1.0, min(1.0, dot / (n1 * n2)))
    return math.degrees(math.acos(cos_a))


def hand_center(lms, side=None, idx_points=None):
    """手掌中心：手腕 + 小指根 + 食指根 + 拇指 四点平均。

    - side="L"/"R"：按左右手常量取点；
    - idx_points=元组：显式指定点索引（供 interaction_detector 复用）；
    - 兼容旧调用 hand_center(lms, idx_points)（第二个位置参数传元组）。

    拍手时掌心贴合，用手掌中心测距远比单用手腕准确。"""
    if idx_points is None and isinstance(side, (tuple, list)):
        idx_points = side
        side = None
    if idx_points is None:
        idx_points = HAND_POINTS_L if side == "L" else HAND_POINTS_R
    x = sum(lms[i].x for i in idx_points) / len(idx_points)
    y = sum(lms[i].y for i in idx_points) / len(idx_points)
    return x, y


def hand_center_21(hand_lms):
    """从 MediaPipe Hands 的 21 个关键点取掌心（手腕 + 4 个掌指关节）。

    hand_lms 为 21 个 NormalizedLandmark/Pt；任一点越界则返回 None，
    调用方据此回退到 Pose 的 4 点掌心，避免错手污染判定。
    """
    if not hand_lms or len(hand_lms) < 21:
        return None
    pts = [hand_lms[i] for i in HAND_PALM_21]
    if any(not (0 <= p.x <= 1 and 0 <= p.y <= 1) for p in pts):
        return None
    return (sum(p.x for p in pts) / len(pts),
            sum(p.y for p in pts) / len(pts))


def body_scale(lms):
    """肩宽作为身体尺度基准，用于把绝对位移特征归一化。

    归一化坐标会随孩子离摄像头远近变化；用肩宽做尺子，
    同一个动作在不同距离下得到相近的特征值。参考肩宽 0.20 与现有
    actions.json 阈值标定时的中性姿态一致，保证老规则行为不变。
    """
    try:
        w = dist2d(lms[11], lms[12])
    except (IndexError, AttributeError, TypeError):
        return 1.0
    return w / 0.20 if w > 1e-6 else 1.0


def draw_pos(lm, w, h):
    """识别在原始帧完成、显示帧是镜像的，绘制时 x 换成 1-x。"""
    return int((1 - lm.x) * w), int(lm.y * h)


def hms_to_sec(hms):
    """'HH:MM:SS' -> 秒。"""
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


# ---------------------------------------------------------------------------
# 时序平滑
# ---------------------------------------------------------------------------
class LandmarkSmoother:
    """姿态关键点时序平滑器（指数平滑）。

    封装平滑状态（上一帧结果），逐帧 update：
    - 可靠点：按 alpha 与上一帧融合；边缘区自动改用 edge_alpha 加强平滑；
    - 不可靠点（出画/遮挡）：保持最后可靠位置，骨架锁定不抖，绝不编造新位置。
    """

    def __init__(self, alpha=0.30, edge_alpha=None, min_visibility=0.3,
                 reliable_margin=None, edge_margin=None):
        self.alpha = alpha
        self.edge_alpha = alpha * 0.4 if edge_alpha is None else edge_alpha
        self.min_visibility = min_visibility
        self.reliable_margin = reliable_margin  # None=出画才不可靠
        self.edge_margin = edge_margin          # None=不判定边缘区
        self.smoothed = None

    def reset(self):
        self.smoothed = None

    def update(self, new_lms):
        if self.smoothed is None or len(self.smoothed) != len(new_lms):
            self.smoothed = list(new_lms)
            return self.smoothed
        for i, lm in enumerate(new_lms):
            prev = self.smoothed[i]
            if point_reliable(lm, self.min_visibility, self.reliable_margin):
                a = self.alpha
                if (self.edge_margin is not None and
                        near_edge(lm, self.edge_margin)):
                    a = self.edge_alpha
                self.smoothed[i] = type(lm)(
                    x=a * lm.x + (1 - a) * prev.x,
                    y=a * lm.y + (1 - a) * prev.y,
                    z=a * lm.z + (1 - a) * prev.z,
                    visibility=lm.visibility,
                )
            # 不可靠：保持最后可靠位置，不更新
        return self.smoothed
