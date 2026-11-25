# 星伴AI —— 基于计算机视觉与个体化行为分析的孤独症儿童家庭康复训练辅助系统

面向孤独症儿童家庭康复训练场景，使用普通摄像头识别儿童动作、姿态及人与物品的交互行为，
辅助家庭康复训练过程中的**行为记录、提示依赖分析、训练数据管理与个体化辅助决策**。

> ⚠️ **免责声明**：本系统不是医疗诊断软件，不替代专业康复人员，也不能直接判断康复效果。
> AI 识别结果仅供辅助参考，提示等级调整等建议须经专业康复人员审核。

## 功能特性

- **人体姿态识别**：MediaPipe Pose 33 关键点，含平滑滤波与出画锁定
- **动作识别**：举手、拍手，以及 100 个动作的声明式规则引擎（`action_engine.py`）
- **多步骤任务理解（核心）**：YOLO 物品检测 + 人-物交互识别 + 连续行为 FSM，
  实现「寻找→接近→拿起→移动→放入收纳盒」端到端任务
- **个性化训练方案**：根据儿童历史完成情况自动生成「需加强 → 巩固 → 新动作」
  训练计划，练得越差的动作越优先安排（`core/plan.py` + `GET /api/plan`）
- **方案模式连续训练**：今日推荐按完成率标出每个动作训练次数（需加强 3~5 次 / 巩固 2 次 /
  新动作 2 次 / 复习 1 次）；点「按推荐开始训练」即按推荐动作与轮次自动连续训练，
  做完一轮自动进入下一轮 / 下一个动作，语音逐轮播报「第几个动作·第几轮」，
  每个动作独立记录完成情况（`POST /api/training/start_plan` 支持 `reps`）
- **训练大屏自动弹出（v2.7）**：点「开始训练」或「按推荐开始训练」时自动弹出独立的
  大屏窗口（`/#/training-screen`），左侧大画面显示摄像头 MJPEG 流，右侧显示当前任务、
  目标动作/物品、实时识别、步骤进度与暂停/恢复/结束控制；支持一键全屏，
  大屏与主训练页状态实时同步；可取消勾选「自动弹出大屏」或手动打开；
  大屏采用与主站一致的浅色配色，画面叠加 MediaPipe 骨架线条（`/api/camera/stream_pose`），
  有人进入完成动作时实时显示骨架；点「开始训练 / 按推荐开始训练」先自动拉起摄像头
  （`POST /api/camera/start`），大屏打开即有画面
- **实时语音播报**：训练指令、步骤完成、任务完成全程语音提示，
  基于 Windows System.Speech 中文女声（Huihui，语速放慢、文案口语化，`services/tts.py`）
- **儿童桌面训练端**：打开自动加载今日计划（免手动选任务）、摄像头画面、
  方案进度实时高亮、结束弹出完成数/用时/PDI/独立完成率
- **网页系统**：训练控制（开始/暂停/恢复/结束）、报告统计、人工确认、档案管理
- **个体化辅助决策**：提示依赖指数（PDI）、独立完成率、可解释规则建议
- **个体化适应**：每个孩子×每个任务逐步建立个人参考范围（惯用手/幅度/时长/速度容差），
  首次训练仅记录待确认、多次训练 + 人工审核才收敛，不确定结果交家长确认；
  已接入动作判定（惯用手镜像、幅度/角度/速度阈值缩放、步骤超时缩放）；
  v2.3 起按任务启用动作白名单与目标动作保护，举手不再被摸头等相似动作抢判
- **家庭校准（物体个体化，v2.2 新增）**：像人脸识别一样，家长把自家的收纳盒/物品
  放进画面中央的**绿色引导框**缓慢转动，系统自动采集 + 自动生成 YOLO 标注 + 早停自动训练
  到收敛，产出家庭专属模型 `custom_<类名>.pt`；训练完成后自动纳入技能任务的放置目标候选，
  无需手动画框或改配置（`api/calibration.py` + `services/calibration_service.py`
  + `vision/family_calibrate.py`）
- **训练结束专业报告（v2.4）**：每次训练结束自动弹出完整的个体化分析报告（家长可读），
  含要点速览、基线→当前→下一目标对照、领域能力现状、步骤明细与数据质量、
  近期趋势与提示依赖度 PDI、家庭延伸建议、后续任务难度、家长反馈与免责声明（共八部分）；
  报告集中在导航栏「报告」栏目查看
  （顶部「查看最近训练报告」按钮 / 训练记录中的「查看报告」），训练页只做训练控制、
  不重复报告功能；报告内可一键「按建议去训练」跳转训练页执行推荐方案
  （`services/professional_report.py`
  + `GET /api/reports/professional/{id}`，结构参考国标康复评估表与 ABA 进展报告）
- **报告页专业解读**：按儿童筛选统计，自动给出完成率 / PDI 解读与后续训练计划推荐
- **儿童档案管理**：网页端新增 / 编辑 / 删除儿童档案（昵称 / 出生年份 / 性别 / 备注），
  已有训练记录的档案禁止误删
- **报告持久化与历史查询（v2.5）**：每场训练结束自动生成一份当日全新报告快照并落库
  （`training_report` 表，13 张表），不随后续数据变化；报告栏目可按儿童 / 日期范围
  查询历史报告并查看当场原文（`GET /api/reports/history`、`/saved/{id}`）
- **不确定态与人工复核闭环（P0/P1）**：命中率中等或主动中止时不直接判成功/失败，
  标记 `uncertain` 交家长确认；确认页可填纠正结果并回写会话结论（`POST /api/reports/review`）
- **完整演示自检（P0）**：`python tests/demo_flow_check.py --runs 10` 连跑 10 轮
  「推荐→开始→状态→结束→报告」并写 `logs/demo_run_log.csv`（已通过 10/10，无异常）
- **桌面端 AI 监控（P1）**：PySide6 桌面端显示带骨架的摄像头画面、目标动作、
  当前识别、状态与轮次进度；结果弹窗复用网页端专业报告要点，两端数据展示统一
- **ESP32 硬件联动（P2）**：新增 `/api/device/*`（连接/状态/LED/蜂鸣），
  训练成功自动亮 LED + 蜂鸣、结束熄灭；未连接设备时优雅降级不阻塞训练
- **规范数据库 12 张表**：AI 识别结果与人工确认分开存储，可追溯
- **多设备访问**：电脑运行算法与摄像头，手机/平板通过局域网浏览器操作

## 系统截图

### 首页仪表盘

训练统计、当前训练状态与个体化辅助建议：

![首页仪表盘](docs/screenshots/dashboard.png)

### 训练操作页

选择任务 / 场景 / 提示等级，开始、暂停、恢复、结束训练，实时显示摄像头画面与识别状态；
技能任务会列出放置目标候选，其中「家庭自定义」项来自家庭校准生成的专属模型：

![训练操作页](docs/screenshots/training.png)

### 家庭校准页

给物品起名后镜头前展示，系统自动采集、自动标注并训练到收敛；
下方列出已训练好的家庭专属模型：

![家庭校准页](docs/screenshots/calibration.png)

### 训练结束专业报告

训练结束后到导航栏「报告」栏目查看（顶部按钮或记录里的「查看报告」），
按专业评估报告结构展示目标对照、能力现状、后续任务难度建议与家长反馈区：

![训练结束专业报告](docs/screenshots/professional_report.png)

### 训练报告页

训练次数、完成率、PDI、独立完成率，以及提示等级分布、场景表现、趋势图表（ECharts），
并附专业分析解读与后续训练计划推荐，支持按儿童筛选：

![训练报告页](docs/screenshots/reports.png)

### 人工确认页

AI 识别结果与人工确认分开存储，可对不确定的识别结果进行人工确认：

![人工确认页](docs/screenshots/review.png)

> 注：截图取自本地演示账号与测试训练数据，非真实儿童训练数据。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI + Uvicorn + SQLAlchemy + SQLite + Pydantic |
| 前端 | Vue3 + Element Plus + ECharts + Axios |
| 视觉 | OpenCV + MediaPipe Pose + Ultralytics YOLO + NumPy |
| 算法 | 规则式交互识别 + FSM 有限状态机 + DTW 相似度 |
| 语音 | Windows System.Speech（SAPI5，独立进程异步播报，训练指令实时提示；`services/tts.py`） |
| 硬件/桌面端 | ESP32 串口控制器（需实物联调）、PySide6 儿童训练端（对接后端） |

## 目录结构

```text
├── vision/                 计算机视觉算法（姿态/动作/交互/行为FSM/物品检测）
│   ├── 自训练流水线：collect_dataset → label_dataset → train_custom_yolo → evaluate_model
│   └── family_calibrate.py：家庭校准一键脚本（引导拍照 → 自动标注 → 微调训练）
├── services/               业务服务层（摄像头/训练调度/方案模式/报告/专业报告/语音TTS/视觉事件/家庭校准）
├── api/                    接口路由（训练/方案训练/摄像头/报告/专业报告/历史报告/个体化/家庭校准）
├── database/               SQLAlchemy 模型 + CRUD + 种子数据（12 张表）
├── server/                 FastAPI 入口（main.py / run.py）
├── frontend/               Vue3 前端工程
├── core/                   decision.py（PDI 辅助决策）+ plan.py（方案推荐）+
│                           personalization.py（个体化参考范围引擎）
├── hardware/               ESP32 交互盒串口控制器 + 固件（需实物联调）
├── desktop/                PySide6 儿童训练端（推荐计划/连续训练/语音/摄像头画面）
├── tests/                  单元测试（动作/FSM/决策/个体化/阈值缩放/标定）
├── data/                   任务库（tasks.json/actions.json）
└── docs/                   项目文档
```

## 家长极简使用（不用命令行）

家长**不需要知道 bat 或命令行**，两种方式任选：

1. **图形启动器（推荐）**：双击项目根目录的 **`星伴AI启动器.pyw`**，弹出一个窗口，
   点「打开训练系统」→ 自动启动后端并打开浏览器；点「打开儿童训练大屏」可放大摄像头；
   点「创建桌面快捷方式」后，以后从桌面「星伴AI」图标打开；不想用时点「停止系统」。
2. **网页里一键开桌面端**：进入系统首页，点右上角「打开儿童训练端」按钮，
   直接弹出 PySide6 儿童训练窗口（仅电脑本机可用），无需再双击 bat。

> 首次部署者仍需按下面「快速开始」装一次依赖；装好后家长每天只用上面两种方式。

## 快速开始

### 1. 环境要求

- Windows，Python 3.12（MediaPipe Windows 包仅支持到 3.12）
- 全程 CPU 运行，无需 NVIDIA GPU

### 2. 安装依赖

```powershell
# 创建并激活虚拟环境（示例）
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt
```

### 3. 模型文件说明

- `vision/models/pose_landmarker_full.task`：已随仓库提供（MediaPipe 姿态模型，约 9MB）
- `vision/models/yolo11n.pt`：**首次运行会自动下载**（约 5MB），无需手动处理

### 4. 启动网页系统

```powershell
# 方式一：双击「启动训练系统.bat」
# 方式二：命令行
python -m server.run
```

启动成功后（约 6~12 秒），浏览器打开 `http://127.0.0.1:8000`。

手机/平板（同一 Wi-Fi）打开 `http://电脑局域网IP:8000`（`ipconfig` 查看 IPv4 地址）。

> 前端已构建（`frontend/dist/` 随仓库提供），**无需安装 Node.js 即可直接使用**。
> 只有当你修改了前端代码（`frontend/src/`）时，才需要进入 `frontend/` 目录执行
> `npm install && npm run build` 重新构建。

### 4.5 启动桌面训练端

```powershell
# 先启动后端（python -m server.run），再另开一个窗口运行桌面端
python desktop/main_window.py
```

桌面端为儿童训练专用界面（宋体、大按钮）：
- 打开自动加载「今日训练计划」（按历史完成情况个性化推荐，免手动选任务）；
- 一键「开始训练」按计划连续练多个动作，练完一个自动进入下一个；
- 每个动作有语音指令播报，画面实时显示摄像头与进度（`[√]`完成 `[>]`当前）；
- 结束弹出本次完成动作数、用时、累计 PDI 与独立完成率；
- 若上次训练未正常结束，打开时会自动检测，点「结束」即可清掉后重练。

### 5. 直接运行视觉脚本

```powershell
python vision/task_session.py                              # 举手/拍手训练任务
python vision/action_library.py                            # 动作库实时演示
python vision/skill_task_session.py --target bottle        # 多步骤生活技能任务
```

### 6. 自定义物品自训练（解决「收纳盒」识别）

YOLO 使用 COCO 预训练模型，**无法识别「收纳盒」**这类自定义物品。
本项目提供完整自训练流水线：**采集 → 标注 → 训练 → 评估**。

```powershell
# ① 采集图片（空格拍一张 / s 连拍 / q 退出）
python vision/collect_dataset.py --class box

# ② 画框标注（拖拽画框 / n 保存下一张 / s 跳过 / q 退出）
python vision/label_dataset.py --class box

# ③ 微调训练（基于 yolo11n.pt，CPU 可跑）
python vision/train_custom_yolo.py --name box --epochs 60

# ④ 评估精度（Precision / Recall / F1）
python vision/evaluate_model.py --model vision/models/custom_box.pt
```

- 采集数量建议：单类 150~300 张，覆盖多角度/多距离/多光照；
- 训练完成后，把 `skill_task_session.py` 的 `--target` 换成你的自定义类名即可；
- 权重自动导出到 `vision/models/custom_<name>.pt`。

### 7. 家庭校准（推荐：像人脸识别一样，无需手动画框）

不同家庭的收纳盒长得不一样，家庭校准让系统认识**你家**的物品，产出专属模型
`custom_<类名>.pt`。提供两种方式，二选一：

**方式 A：网页自动采集（推荐，无需手动拍照）**

1. 打开网页系统，进入左侧菜单「校准」页；
2. 第 1 步填入类名（如 `my_box`），点「开始展示」；
3. 把物品放进画面中央的**绿色引导框**，缓慢转动 / 移动，画面每变化一次系统自动拍一张，
   并用绿框自动生成 YOLO 标签（建议 ≥ 20 张）；
4. 点「结束展示并训练」，系统以 300 轮 + 早停（patience=50）**自动训练到最佳识别效果**；
5. 训练完成后模型自动纳入技能任务的放置目标候选，**无需改任何配置**，训练页会显示
   「my_box · 家庭自定义」标签并直接参与识别。

对应接口（启动后访问 `http://127.0.0.1:8000/docs` 可查看 FastAPI 自动文档）：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/calibration/models` | 已训练的家庭模型列表 |
| GET | `/api/calibration/status` | 采集/训练状态、已采集张数、模型列表 |
| POST | `/api/calibration/collect/start` | 开始展示，body：`{"class_name": "my_box"}` |
| POST | `/api/calibration/finish` | 结束展示并自动训练到收敛 |
| POST | `/api/calibration/stop` | 放弃本次展示（不训练） |

状态机：`idle → collecting → training → done / error`。

**方式 B：命令行脚本（手动控制拍照时机）**

```powershell
python vision/family_calibrate.py --name my_box --epochs 50
```

- 空格 = 拍一张（物品尽量占满绿框）；`s` = 连拍模式（每 0.5 秒一张，方便转动换角度）；
  `q` = 退出拍照并自动开始训练；建议 30~50 张，覆盖多角度 / 多距离 / 多光照；
- 绿色引导框即标注框，脚本自动生成 YOLO 标签，无需手动标注；
- 产出 `vision/models/custom_my_box.pt`，之后把技能任务的目标类名换成 `my_box` 即可使用。

> 两种方式共用数据集目录 `data/custom_dataset/`（`images/` + `labels/`），
> 训练均复用 `vision/train_custom_yolo.py`（CPU 可跑，几十张图约 10~30 分钟）。

### 8. ESP32 交互盒固件

`hardware/esp32_controller.py` 为电脑端串口控制器（需 `pip install pyserial`），
配套固件在 `hardware/esp32_firmware/esp32_firmware.ino`（Arduino IDE 烧录）。
串口协议：`LED:ON/OFF`、`BUZZ:毫秒`，按键上报 `BTN:1/0`。

### 9. 运行单元测试

```powershell
python tests/test_behavior_fsm.py
python tests/test_dtw.py
python tests/test_decision.py
python tests/test_action_engine.py
python tests/test_personalization.py       # 个体化参考范围引擎
python tests/test_adaptive_thresholds.py   # 幅度/速度阈值缩放
python tests/test_calibration.py           # 惯用手接入 + 家庭标定脚本
python tests/test_action_robustness.py     # 白名单/目标保护/角度个体化/稳定性
```

> `test_calibration.py` 依赖 `cv2`/`ultralytics`，请在项目 `.venv` 下运行：
> `.\.venv\Scripts\python.exe tests\test_calibration.py`

## 数据库设计（12 张表）

`child_profile`（儿童档案）/ `task_definition`（任务定义）/ `task_step`（任务步骤）/
`scene_info`（场景）/ `training_session`（训练记录）/ `step_event`（步骤事件）/
`prompt_record`（提示等级）/ `vision_result`（AI 识别原始结果）/ `manual_review`（人工确认）/
`analysis_result`（分析结果）/ `model_version`（模型版本）/ `personal_profile`（个体化档案）

核心原则：**AI 识别结果与人工确认分开存储**，人工修正只新增、不覆盖原始模型结果。

## 提示等级标准

| 等级 | 含义 |
|---|---|
| 0 | 独立完成 |
| 1 | 视觉提示 |
| 2 | 语音提示 |
| 3 | 动作示范 |
| 4 | 家长协助 |

PDI（提示依赖指数）= Σpᵢ / (4N)，独立完成率 = 独立完成任务次数 / 有效任务次数 × 100%。

## 关键技术结论（调试实证）

1. **识别用原始帧，显示用镜像帧**：镜像画面喂给模型会导致左右手判定颠倒
2. **快慢动作分策略**：持续动作（举手）用重平滑+长防抖；瞬时动作（拍手）用原始关键点+短确认
3. **迟滞门槛防临界抖动**：进入/退出状态用两道不同门槛
4. **阈值参数必须实测标定**：印证「个体化行为分析」方向；v2.2 已落地「家庭校准」
   （镜头前展示物品 → 自动采集 / 自动标注 / 早停训练）与个体化参考范围引擎，
   可按儿童 / 家庭自动适配阈值与目标物品
5. **已知局限**（单目 2D 方案固有边界）：手臂完全出画无法识别、宽松衣物影响精度、
   精度为行为记录级而非医学测量级；COCO 预训练模型本身**无法识别收纳盒**等自定义物品，
   v2.2 起可通过「家庭校准」训练专属模型解决（见快速开始第 7 节），
   未校准前仍需用碗 / 书 / 杯等 COCO 可识别物品替代

## 开发环境

- 操作系统：Windows 笔记本，Intel Arc 140V 集成显卡（CPU 方案）
- Python 3.12.13（虚拟环境），pip 26.x
- 依赖版本见 `requirements.txt`

## 常见问题 FAQ

**Q1：摄像头打不开 / 画面不出来？**
- 确认后端已启动（黑色窗口显示 `Uvicorn running on http://0.0.0.0:8000`）；
- 确认摄像头未被其他程序（微信、腾讯会议等）占用；
- 检查 Windows「设置 → 隐私 → 相机」是否允许桌面应用访问摄像头。

**Q2：报错 `Unable to open file at ...pose_landmarker_full.task`？**
- MediaPipe 底层无法打开**含中文的绝对路径**。本项目已改为相对路径规避；
- 若仍遇到，请勿将项目放在含中文的目录下。

**Q3：yolo11n.pt 下载慢或失败？**
- 首次运行由 ultralytics 自动下载（约 5MB）；
- 可手动从 Ultralytics 官网下载后放入 `vision/models/`。

**Q4：后端启动慢（6~12 秒无反应）？**
- 首次启动需建库 + 导入任务库种子数据，属正常，请耐心等待。

**Q5：手机/平板连不上？**
- 确认与电脑连接**同一 Wi-Fi**；
- 使用电脑局域网 IPv4 地址（`ipconfig` 查询），而非 `localhost`；
- 首次访问时在 Windows 防火墙中放行 8000 端口。

## 更新日志

- **v3.0**（2026-11）：家长免命令行启动
  - 新增图形启动器 `星伴AI启动器.pyw`：一键启动/停止系统、打开大屏、创建桌面快捷方式；
    无黑色命令行窗口
  - 首页新增「打开儿童训练端」按钮，通过 `POST /api/app/launch-desktop` 直接拉起
    PySide6 桌面端（仅本机可调用），家长不再需要双击 bat
- **v2.9**（2026-11）：P0/P1/P2 任务清单收口
  - P0：不确定态（命中率中等/主动中止）不误判成功失败，标记 uncertain 待复核；
    新增 10 轮完整演示自检 `tests/demo_flow_check.py` 与 `logs/demo_run_log.csv`
  - P1：人工复核可填纠正结果并回写会话；PySide6 桌面端新增骨架监控画面、
    动作/识别/状态/进度显示，结果弹窗复用专业报告要点统一两端展示
  - P2：新增 `/api/device/*` 设备接口，训练成功联动 LED + 蜂鸣、
    结束熄灭；未连接时优雅降级
- **v2.8**（2026-11）：大屏浅色配色 + 骨架线条 + 自动开摄像头
  - 大屏改用与主站一致的浅色系；`camera_service.get_pose_frame()` 叠加 MediaPipe 骨架
    （连线 + 关键点，只画可靠点），新增 `GET /api/camera/stream_pose`
  - 点击开始 / 按推荐训练先调 `POST /api/camera/start` 自动打开摄像头，大屏也会自检测并拉起
- **v2.7**（2026-11）：训练大屏自动弹出
  - 新增独立路由 `/#/training-screen` 与大屏页面：大画面摄像头 + 实时识别状态 +
    步骤/方案进度 + 暂停/恢复/结束控制 + 一键全屏
  - 开始训练 / 按推荐开始训练时在点击的同步上下文中弹出大屏窗口（避免被浏览器拦截），
    提供「自动弹出大屏」勾选与「手动打开大屏」按钮
- **v2.6**（2026-11）：今日推荐一键连续训练 + 每动作训练次数
  - `core/plan.py` 为推荐动作计算 `reps`（需加强 3~5 / 巩固 2 / 新动作 2 / 复习 1）；
    训练页推荐区展示每个动作训练次数与总轮次
  - 推荐区新增「按推荐开始训练」按钮，按推荐动作与轮次自动连续训练；
    `POST /api/training/start_plan` 新增 `reps` 参数，语音逐轮播报动作与轮次
  - 实时状态显示方案进度（第几个动作 / 第几轮 + 进度条）
- **v2.5**（2026-11）：报告扩展为八部分 + 每场训练自动生成并支持历史查询
  - 新增 `training_report` 表：每场训练结束自动落库一份完整报告快照，重复查看不覆盖；
    报告栏目可按儿童 / 日期范围筛选历史报告，点击查看当场原文
  - 报告扩展为八部分：要点速览、目标对照、能力现状、步骤明细与数据质量、
    近期趋势与 PDI 提示依赖、家庭延伸建议、后续任务难度、家长反馈
  - 新增 `GET /api/reports/history` 与 `GET /api/reports/saved/{id}`
- **v2.4**（2026-11）：训练结束生成完整专业报告（家长可读）+ 报告驱动后续训练
  - 新增 `services/professional_report.py`：参照国标康复评估分析表与 ABA 进展报告结构，
    输出「基本信息 + 目标基线/当前/下一目标 + 领域能力现状（优势/弱势/待支持）
    + 步骤与数据质量说明 + 后续任务难度建议 + 家长反馈 + 免责声明」；
    报告驱动 `next_plan` 可直接一键开始下一组训练
  - v2.4.1：专业报告集中到「报告」栏目，训练页不再重复报告入口；报告内可一键跳转训练
    页执行推荐动作序列；训练结束时改为提示到报告栏目查看
  - 报告弹窗支持内部滚动与家长反馈填写
  - 新增 `GET /api/reports/professional/{id}` 与 `GET /api/reports/latest_session`
- **v2.3**（2026-11）：动作识别鲁棒性 + 语音柔和化
  - 任务白名单：训练单个动作时只检测目标动作，从源头避免"摸头"等相似动作抢判定；
    目标动作受保护，不再被其他动作的 `excludes` 压制（解决"做对了却没记录"）
  - 角度纳入个体化缩放：仅放宽 `angle >` 门槛，适配手臂未完全伸直的孩子；
    `angle <`（摸头等干扰动作）不缩放，避免误判被放大
  - 稳定性确认：非瞬时动作连续多帧命中才记录，拍手仍走原有骤降防伪
  - 语音改用中文女声 Huihui、放慢语速、文案口语化；新增 `test_action_robustness.py`
- **v2.2**（2026-11）：家庭校准（物体个体化）+ 训练报告闭环
  - 新增「校准」网页页与 `/api/calibration/*` 接口：镜头前展示物品自动采集、
    自动绿框标注、早停自动训练到收敛，产出 `custom_<类名>.pt` 家庭专属模型；
    训练完成后自动纳入技能任务放置目标候选，无需改配置
  - 新增命令行 `vision/family_calibrate.py`（空格拍照 / s 连拍 / q 训练）；
    `train_custom_yolo.py` 增加 `--patience` 早停并修复 GBK 控制台编码
  - `object_detector.py` 支持同时加载多个家庭自定义模型，与 COCO 检测结果合并
  - 训练结束自动弹出「本次训练报告」（步骤 / 评价 / 建议），新增 `GET /api/reports/session/{id}`
  - 报告页增加按儿童筛选、专业解读与后续训练计划推荐；新增儿童档案增删改（含备注）
- **v2.1**（2026-11）：个体化适应——每个孩子×每个任务逐步建立个人参考范围
  （惯用手/幅度/时长/速度），首次训练仅记录待确认、多次训练 + 人工审核才收敛；
  已接入动作判定（惯用手镜像、幅度/速度阈值缩放、步骤超时缩放、惯用手优先追踪），
  新增 `personal_profile` 表、个体化接口与真机标定采集脚本
- **v2.0**（2026-11）：网页系统改造——FastAPI 后端 + SQLite 规范数据库（11 表）+
  Vue3 前端 + 多步骤任务理解（把物品放入收纳盒）+ 统一视觉事件格式 + 硬件/桌面端框架
- **v1.0**：视觉算法阶段——姿态识别、举手/拍手、人-物交互识别、行为 FSM、动作库

## License

[MIT](./LICENSE)
