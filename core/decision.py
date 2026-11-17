# -*- coding: utf-8 -*-
"""
星伴AI 核心模块：提示依赖感知的个体化辅助决策（创新点 4.1）

依据构想报告 4.1：
- 五级提示等级：0独立 / 1视觉 / 2语音 / 3动作示范 / 4家长协助
- 提示依赖指数 PDI = Σpᵢ / (4N)，N 为有效训练次数，范围 0~1
- 独立完成率 = 独立完成任务次数 / 有效任务次数 × 100%
- 初期用可解释的规则决策生成辅助建议（报告列出的 5 类建议）

重要伦理边界（如实执行）：
- 建议仅供辅助参考，不形成医学诊断或疗效结论；
- 不自主试错，不替代专业康复人员。

本模块为纯逻辑，可用 tests/test_decision.py 验证。
"""

# 五级提示等级（报告 4.1）
PROMPT_LEVELS = {
    0: "独立完成",
    1: "视觉提示",
    2: "语音提示",
    3: "动作示范",
    4: "家长协助",
}

# 决策建议类型（报告 3.3 列出的 5 类）
ADVICE_TYPES = {
    "maintain": "建议保持当前提示方式",
    "reduce": "表现稳定，可请专业人员审核是否降低提示程度",
    "assist": "当前任务仍需适当辅助",
    "observe": "训练数据不足，建议继续观察",
    "confirm": "视觉识别结果不确定，需要家长确认",
}


def compute_pdi(prompt_levels):
    """提示依赖指数 PDI = Σp / (4N)。prompt_levels: 有效训练的提示等级列表。"""
    levels = [p for p in prompt_levels if p is not None]
    if not levels:
        return 0.0
    return sum(levels) / (4 * len(levels))


def independent_rate(sessions):
    """独立完成率 = 独立完成(等级0且完成)次数 / 有效次数。

    sessions: [{completed: bool, prompt_level: int, valid: bool}, ...]
    """
    valid = [s for s in sessions if s.get("valid", 1)]
    if not valid:
        return 0.0
    indep = sum(1 for s in valid
                if s.get("completed") and s.get("prompt_level") == 0)
    return indep / len(valid)


def completion_rate(sessions):
    valid = [s for s in sessions if s.get("valid", 1)]
    if not valid:
        return 0.0
    return sum(1 for s in valid if s.get("completed")) / len(valid)


def suggest(sessions, uncertainty_ratio=0.0, trend=0.0):
    """规则决策引擎：根据训练状态生成可解释建议列表。

    输入：
        sessions: 有效训练记录列表
        uncertainty_ratio: 视觉识别不确定比例
        trend: 近期完成率趋势（正=上升，负=下降）
    输出：[{type, text, level(1提示/2建议/3注意)}]
    """
    n = len([s for s in sessions if s.get("valid", 1)])
    pdi = compute_pdi([s.get("prompt_level") for s in sessions])
    ir = independent_rate(sessions)
    cr = completion_rate(sessions)

    out = []
    # 数据不足优先
    if n < 5:
        out.append(dict(type="observe", text=ADVICE_TYPES["observe"],
                        pdi=round(pdi, 3), independent_rate=round(ir, 3),
                        completion_rate=round(cr, 3), level=1))
    # 识别不确定需人工确认
    if uncertainty_ratio > 0.3:
        out.append(dict(type="confirm", text=ADVICE_TYPES["confirm"],
                        pdi=round(pdi, 3), independent_rate=round(ir, 3),
                        completion_rate=round(cr, 3), level=3))
    # 表现差/依赖高 -> 仍需辅助
    if cr < 0.6 or pdi > 0.7:
        out.append(dict(type="assist", text=ADVICE_TYPES["assist"],
                        pdi=round(pdi, 3), independent_rate=round(ir, 3),
                        completion_rate=round(cr, 3), level=3))
    # 独立率高或趋势上升 -> 可考虑降低提示
    elif ir > 0.6 or trend > 0:
        out.append(dict(type="reduce", text=ADVICE_TYPES["reduce"],
                        pdi=round(pdi, 3), independent_rate=round(ir, 3),
                        completion_rate=round(cr, 3), level=2))
    else:
        out.append(dict(type="maintain", text=ADVICE_TYPES["maintain"],
                        pdi=round(pdi, 3), independent_rate=round(ir, 3),
                        completion_rate=round(cr, 3), level=1))
    return out


def trend_of(history):
    """根据按时间排列的完成情况（0/1）序列估计趋势，返回斜率近似值。"""
    seq = [1 if c else 0 for c in history]
    if len(seq) < 3:
        return 0.0
    mid = len(seq) // 2
    return sum(seq[mid:]) - sum(seq[:mid])
