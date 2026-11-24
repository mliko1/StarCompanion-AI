<template>
  <div>
    <div class="page-head">
      <h2 class="page-title">训练操作</h2>
      <el-button size="small" round @click="openLastReport">查看最近训练报告</el-button>
    </div>

    <el-card shadow="never" class="block">
      <template #header>今日推荐训练计划（根据历史完成情况自动生成）</template>
      <div v-if="plan.length" class="plan-list">
        <div v-for="(p, i) in plan" :key="p.task_id" class="plan-item" @click="taskId = p.task_id">
          <span class="plan-no" :class="{ picked: taskId === p.task_id }">{{ i + 1 }}</span>
          <div class="plan-info">
            <div class="plan-name">
              {{ p.name }}
              <el-tag size="small" :type="kindType(p.kind)" effect="light">{{ kindText(p.kind) }}</el-tag>
              <span class="plan-rate">完成率 {{ (p.rate * 100).toFixed(0) }}%</span>
            </div>
            <div class="plan-reason">{{ p.reason }}</div>
          </div>
        </div>
      </div>
      <div v-else class="muted">暂无训练记录，点击下方「开始训练」即可开始第一次训练</div>
    </el-card>

    <el-card shadow="never" class="block">
      <template #header>选择训练任务</template>
      <el-form label-width="90px" label-position="left">
        <el-form-item label="训练任务">
          <el-select v-model="taskId" placeholder="请选择训练任务" filterable style="width: 100%">
            <el-option-group label="动作类（举手、拍手等）">
              <el-option v-for="t in actionTasks" :key="t.task_id" :label="t.name" :value="t.task_id" />
            </el-option-group>
            <el-option-group label="生活技能类（多步骤）">
              <el-option v-for="t in skillTasks" :key="t.task_id" :label="t.name" :value="t.task_id" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="家庭场景">
          <el-select v-model="sceneId" placeholder="请选择场景" style="width: 100%">
            <el-option v-for="s in scenes" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="提示等级">
          <el-select v-model="promptLevel" style="width: 100%">
            <el-option v-for="(label, i) in promptLabels" :key="i" :label="label" :value="i" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="selectedTask && selectedTask.type === 'skill'" label="自定义物品候选">
          <div class="cont-tags">
            <el-tag v-for="c in containerCandidates" :key="c" size="small"
                    :type="isCustomModel(c) ? 'success' : 'info'">
              {{ c }}{{ isCustomModel(c) ? ' · 家庭自定义' : '' }}
            </el-tag>
          </div>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="start" :disabled="state === 'running'">开始训练</el-button>
          <el-button @click="pause" :disabled="state !== 'running'">暂停</el-button>
          <el-button @click="resume" :disabled="state !== 'paused'">恢复</el-button>
          <el-button type="danger" @click="stop" :disabled="state !== 'running' && state !== 'paused'">结束</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="block">
      <template #header>摄像头画面（电脑端采集）</template>
      <div class="video-wrap">
        <img v-if="cameraRunning" :src="streamUrl" alt="摄像头画面" class="video" />
        <div v-else class="video placeholder">摄像头未启动</div>
      </div>
    </el-card>

    <el-card shadow="never" class="block">
      <template #header>实时识别状态</template>
      <template v-if="status && state !== 'idle'">
        <p>训练状态：<el-tag :type="stateType">{{ stateText }}</el-tag></p>

        <!-- 动作类任务 -->
        <template v-if="status.task_type !== 'skill'">
          <p v-if="status.target_action">目标动作：{{ status.target_action }}</p>
          <p>当前识别：{{ status.current_action || '无' }}
            <el-tag v-if="status.detected_now" type="success" size="small">已命中</el-tag>
          </p>
        </template>

        <!-- 生活技能类（多步骤）任务 -->
        <template v-else>
          <p v-if="status.target_object">目标物品：{{ status.target_object }}</p>
          <p v-if="status.containers" class="cont-line">
            自定义物品候选：
            <el-tag v-for="c in status.containers" :key="c" size="small"
                    :type="isCustomModel(c) ? 'success' : 'info'">
              {{ c }}{{ isCustomModel(c) ? ' · 家庭自定义' : '' }}
            </el-tag>
          </p>
          <p>当前步骤：<b>{{ stepName(status.current_step) }}</b></p>
          <p>交互状态：{{ status.current_interaction }}</p>
          <div class="steps">
            <span v-for="(s, i) in stepList" :key="s" class="step-chip"
                  :class="{ done: (status.completed_steps || []).includes(s), current: status.current_step === s }">
              {{ i + 1 }}. {{ stepName(s) }}
            </span>
          </div>
        </template>

        <p>{{ status.message }}</p>
      </template>
      <template v-else>尚未开始训练</template>
    </el-card>

    <el-dialog v-model="reportVisible" title="训练分析报告 · 家长反馈" width="760px" top="3vh" class="pr-dialog">
      <template v-if="report">
        <div class="pr-head">
          <div>
            <div class="pr-title">{{ report.meta.task }} · 个体化训练分析</div>
            <div class="pr-sub">{{ report.meta.child }}｜{{ report.meta.scene || '未记录场景' }}｜{{ report.meta.start_time }}｜用时 {{ report.meta.elapsed_sec }} 秒</div>
          </div>
          <el-tag :type="report.summary.completed ? 'success' : 'warning'" effect="dark">{{ report.summary.score_label }}</el-tag>
        </div>

        <el-divider content-position="left">一、目标完成情况（基线 → 当前 → 目标）</el-divider>
        <el-table :data="[report.goal_progress]" size="small" border class="pr-table">
          <el-table-column prop="goal" label="训练目标" min-width="110" />
          <el-table-column label="基线" min-width="130">
            <template #default="{ row }">{{ row.baseline_label }}<div class="pr-mini">（{{ row.baseline_n }} 次历史）</div></template>
          </el-table-column>
          <el-table-column prop="current_label" label="本次表现" min-width="130" />
          <el-table-column prop="target" label="下一阶段目标" min-width="190" />
        </el-table>

        <el-divider content-position="left">二、领域能力现状（{{ report.ability.dimension }}）</el-divider>
        <div class="pr-grid">
          <div class="pr-card ok"><b>优势 / 亮点</b><p>{{ report.ability.strength }}</p></div>
          <div class="pr-card warn"><b>待支持项</b><p>{{ report.ability.weakness }}</p></div>
        </div>
        <ul class="pr-list">
          <li v-for="(s, i) in report.ability.support_needed" :key="i">{{ s }}</li>
        </ul>

        <el-divider content-position="left">三、步骤完成与数据说明</el-divider>
        <p class="pr-text">共 {{ report.steps.total }} 个步骤，独立完成 {{ report.steps.completed }} 个<span v-if="report.steps.pending_names.length">；待加强：{{ report.steps.pending_names.join('、') }}</span>。</p>
        <el-alert :type="report.data_quality.level === 'good' ? 'success' : 'warning'" :closable="false" :title="report.data_quality.note" class="pr-alert" />

        <el-divider content-position="left">四、后续训练任务与难度建议</el-divider>
        <el-table :data="report.next_plan" size="small" border class="pr-table">
          <el-table-column type="index" label="#" width="42" />
          <el-table-column prop="name" label="任务" min-width="110" />
          <el-table-column label="类型" width="88">
            <template #default="{ row }"><el-tag size="small" :type="kindType(row.kind)">{{ kindText(row.kind) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="难度" width="90">
            <template #default="{ row }">{{ '★'.repeat(row.difficulty || 1) }}</template>
          </el-table-column>
          <el-table-column prop="prompt_suggestion" label="提示建议" min-width="180" />
        </el-table>

        <el-divider content-position="left">五、家长反馈（可选）</el-divider>
        <el-form label-position="top" size="small">
          <el-form-item label="今天在家的观察">
            <el-input v-model="report.parent_feedback.observation" type="textarea" :rows="2" placeholder="如：孩子主动模仿了动作，情绪很好" />
          </el-form-item>
          <el-form-item label="难度是否合适">
            <el-select v-model="report.parent_feedback.difficulty_fit" placeholder="请选择" style="width:100%">
              <el-option label="偏难" value="hard" />
              <el-option label="合适" value="fit" />
              <el-option label="偏简单" value="easy" />
            </el-select>
          </el-form-item>
        </el-form>
        <p class="pr-disclaimer">{{ report.disclaimer }}</p>
      </template>
      <template #footer>
        <el-button @click="reportVisible = false">关闭</el-button>
        <el-button type="primary" @click="applyPlan" :disabled="!report || !report.next_plan.length">按建议开始下一组训练</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const tasks = ref([])
const scenes = ref([])
const plan = ref([])
const taskId = ref('')
const sceneId = ref('')
const promptLevel = ref(0)
const status = ref(null)
const customModels = ref([])
const reportVisible = ref(false)
const report = ref(null)

const KIND_TEXT = { strengthen: '需加强', consolidate: '巩固', new: '新动作', review: '复习' }
const KIND_TYPE = { strengthen: 'danger', consolidate: 'warning', new: 'primary', review: 'info' }
function kindText(k) { return KIND_TEXT[k] || k }
function kindType(k) { return KIND_TYPE[k] || 'info' }
const promptLabels = ['独立完成', '视觉提示', '语音提示', '动作示范', '家长协助']
const streamUrl = '/api/camera/stream'

const STEP_MAP = {
  find_toy: '寻找玩具', approach_toy: '接近玩具', pick_toy: '拿起玩具',
  move_toy: '移动玩具', place_toy: '放入收纳盒',
}
const stepList = ['find_toy', 'approach_toy', 'pick_toy', 'move_toy', 'place_toy']

const actionTasks = computed(() => tasks.value.filter(t => t.type === 'action'))
const skillTasks = computed(() => tasks.value.filter(t => t.type === 'skill'))
const state = computed(() => status.value ? status.value.state : 'idle')
const cameraRunning = computed(() => status.value && status.value.camera && status.value.camera.running)
const selectedTask = computed(() => tasks.value.find(t => t.task_id === taskId.value))
const containerCandidates = computed(() => {
  const t = selectedTask.value
  if (!t || t.type !== 'skill') return []
  const base = (t.params && t.params.containers) || []
  const merged = [...base]
  customModels.value.forEach(c => { if (!merged.includes(c)) merged.push(c) })
  return merged
})
function isCustomModel(name) { return customModels.value.includes(name) }

const stateMap = { idle: '空闲', running: '训练中', paused: '已暂停', done: '已完成', aborted: '已结束' }
const stateText = computed(() => stateMap[state.value] || state.value)
const stateType = computed(() =>
  ({ running: 'primary', paused: 'warning', done: 'success', aborted: 'info', idle: 'info' }[state.value] || 'info'))

function stepName(key) { return STEP_MAP[key] || key || '—' }

async function loadBase() {
  const [t, s, p] = await Promise.all([api.tasks(), api.scenes(), api.plan()])
  tasks.value = t.data.tasks
  scenes.value = s.data.scenes
  plan.value = p.data.plan || []
  if (scenes.value.length) sceneId.value = scenes.value[0].id
  // 默认选中推荐方案第一个动作（免手动选任务）
  if (plan.value.length && !taskId.value) taskId.value = plan.value[0].task_id
  // 家庭自定义模型列表（训练完成后自动作为放置目标候选）
  try {
    const c = await api.calibrationModels()
    customModels.value = (c.data.models || []).map(m => m.class_name)
  } catch (e) { console.warn(e) }
}
async function refreshStatus() {
  try {
    const r = await api.trainingStatus()
    const prev = status.value ? status.value.state : null
    status.value = r.data
    const cur = r.data.state
    // 训练结束（running/paused -> done/aborted）时弹出本次训练报告
    if ((prev === 'running' || prev === 'paused') &&
        (cur === 'done' || cur === 'aborted') && r.data.session_id) {
      await loadReport(r.data.session_id)
    }
  } catch (e) { console.warn(e) }
}

async function loadReport(sessionId) {
  try {
    const r = await api.professionalReport(sessionId)
    report.value = r.data
    reportVisible.value = true
  } catch (e) {
    console.warn(e)
    ElMessage.warning('专业报告加载失败，请稍后重试')
  }
}

async function openLastReport() {
  try {
    const r = await api.latestSession()
    if (!r.data.session_id) { ElMessage.warning('暂无训练记录'); return }
    await loadReport(r.data.session_id)
  } catch (e) { console.warn(e) }
}

async function applyPlan() {
  const first = report.value && report.value.next_plan && report.value.next_plan[0]
  if (!first || !first.task_id) { ElMessage.warning('暂无可开始的推荐任务'); return }
  const r = await api.startPlan({
    child_id: status.value && status.value.child_id,
    scene_id: sceneId.value || null,
    prompt_level: promptLevel.value,
    hold_sec: 2.0,
    task_ids: report.value.next_plan.map(p => p.task_id).filter(Boolean),
  })
  ElMessage({ type: r.data.ok ? 'success' : 'warning', message: r.data.msg || '已按建议开始训练' })
  reportVisible.value = false
  refreshStatus()
}

async function start() {
  if (!taskId.value) { ElMessage.warning('请先选择训练任务'); return }
  const r = await api.startTraining({
    task_id: taskId.value, scene_id: sceneId.value || null,
    prompt_level: promptLevel.value, hold_sec: 2.0,
  })
  ElMessage({ type: r.data.ok ? 'success' : 'warning', message: r.data.msg })
  refreshStatus()
}
async function pause() { await api.pauseTraining(); refreshStatus() }
async function resume() { await api.resumeTraining(); refreshStatus() }
async function stop() { await api.stopTraining(); refreshStatus() }

onMounted(async () => {
  await loadBase()
  await refreshStatus()
})
setInterval(refreshStatus, 2000)
</script>

<style scoped>
.plan-list { display: flex; flex-direction: column; gap: 10px; }
.plan-item {
  display: flex; align-items: flex-start; gap: 12px; padding: 12px 14px;
  border-radius: 12px; background: #f7f8fc; cursor: pointer;
  transition: all 0.15s ease; border: 1px solid transparent;
}
.plan-item:hover { border-color: #d6defc; background: #f2f5ff; }
.plan-no {
  width: 24px; height: 24px; border-radius: 50%;
  background: #f2f5fa; color: #7c8ca6;
  border: 1px solid #e2e9f4;
  display: flex; align-items: center; justify-content: center;
  font-weight: 600; font-size: 12px; flex-shrink: 0;
  transition: all 0.18s ease;
}
.plan-no.picked {
  background: #eaf2fd; color: var(--primary);
  border-color: rgba(11, 99, 206, 0.32);
}
.plan-info { flex: 1; }
.plan-name { font-size: 15px; font-weight: 600; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.plan-rate { color: #8a91a6; font-size: 12px; font-weight: 400; }
.plan-reason { color: #8a91a6; font-size: 13px; margin-top: 3px; }
.cont-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.cont-line { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 4px 0; }
.video-wrap { display: flex; justify-content: center; }
.video {
  width: 100%; max-width: 640px; border-radius: 14px; background: #000;
  box-shadow: 0 10px 30px rgba(20, 30, 60, 0.18);
}
.placeholder {
  width: 100%; max-width: 640px; height: 360px;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #eef1f8 0%, #e6e9f5 100%);
  color: #a3a9bd; border-radius: 14px; font-size: 15px;
}
.steps { display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0; }
.step-chip {
  padding: 8px 16px; border-radius: 20px; background: #f1f3f8; color: #9aa1b3;
  font-size: 13px; font-weight: 500; transition: all 0.2s ease;
}
.step-chip.done { background: linear-gradient(135deg, #e7f7e4, #d3f0cf); color: #3e9b3e; }
.step-chip.current {
  background: var(--primary-grad); color: #fff; font-weight: 600;
  box-shadow: 0 4px 12px rgba(11, 99, 206, 0.28);
}
.report-head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.report-task { font-size: 17px; font-weight: 600; color: #1f2430; }
.report-desc { margin-bottom: 6px; }
.report-block { margin-top: 14px; }
.report-subtitle { font-size: 14px; font-weight: 600; color: #344054; margin-bottom: 6px; }
.report-text { color: #5b6480; line-height: 1.7; font-size: 14px; margin: 0; }
.pr-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.pr-title { font-size: 19px; font-weight: 700; color: #1f2430; }
.pr-sub { color: #8b93a5; font-size: 12px; margin-top: 5px; }
.pr-table { margin: 6px 0; }
.pr-mini { color: #a3a9bd; font-size: 11px; }
.pr-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.pr-card { padding: 12px 14px; border-radius: 10px; font-size: 13px; line-height: 1.7; }
.pr-card b { font-size: 13px; }
.pr-card p { margin: 5px 0 0; }
.pr-card.ok { background: #eef8ed; color: #3e7d3e; }
.pr-card.warn { background: #fff6e8; color: #a06a1f; }
.pr-list { margin: 10px 0 0; padding-left: 20px; color: #5b6480; font-size: 13px; line-height: 1.9; }
.pr-text { color: #5b6480; font-size: 13px; line-height: 1.8; }
.pr-alert { margin: 10px 0; }
.pr-disclaimer { color: #a3a9bd; font-size: 11px; line-height: 1.7; margin: 14px 0 0; }
.page-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.page-head .page-title { margin-bottom: 0; }
:deep(.pr-dialog) { margin-top: 2vh !important; }
:deep(.pr-dialog .el-dialog__body) { max-height: 74vh; overflow-y: auto; padding-top: 8px; }
:deep(.pr-dialog .el-divider) { margin: 16px 0 12px; }
</style>
