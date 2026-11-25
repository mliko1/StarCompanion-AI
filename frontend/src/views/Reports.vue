<template>
  <div>
    <div class="page-head">
      <h2 class="page-title">训练报告</h2>
      <div class="head-actions">
        <el-select v-model="childId" placeholder="全部儿童" clearable style="width: 170px" @change="load">
          <el-option v-for="c in children" :key="c.id" :label="c.nickname" :value="c.id" />
        </el-select>
        <el-button size="small" round @click="load">刷新数据</el-button>
      </div>
    </div>

    <el-card shadow="never" class="block">
      <template #header>
        <div class="card-head">
          <span>个体化训练报告</span>
          <el-button type="primary" size="small" round @click="openLastReport">查看最近训练报告</el-button>
        </div>
      </template>
      <div class="report-intro">
        <div class="intro-line"><span class="intro-label">报告内容</span><span>目标对照 · 能力现状 · 步骤明细 · 趋势与提示依赖 · 家庭建议 · 后续任务 · 家长反馈</span></div>
        <div class="intro-line"><span class="intro-label">查看方式</span><span>点击右上角按钮查看最近一份，或在下方历史记录中点「查看报告」</span></div>
      </div>
    </el-card>

    <el-card shadow="never" class="block">
      <template #header>历史训练报告</template>
      <div class="history-filter">
        <el-select v-model="historyChild" placeholder="全部儿童" size="small" clearable style="width:140px">
          <el-option v-for="c in children" :key="c.id" :label="c.nickname" :value="c.id" />
        </el-select>
        <el-date-picker v-model="historyRange" type="daterange" size="small" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width:250px" />
        <el-button size="small" type="primary" plain @click="loadHistory">查询</el-button>
      </div>
      <el-table :data="historyReports" size="small" border v-loading="historyLoading" max-height="360" class="history-table">
        <el-table-column prop="report_date" label="报告日期" width="112" align="center" />
        <el-table-column label="儿童" width="96" align="center">
          <template #default="{ row }">{{ childName(row.child_id) }}</template>
        </el-table-column>
        <el-table-column prop="task_name" label="训练任务" min-width="120" align="center" />
        <el-table-column label="完成情况" width="132" align="center">
          <template #default="{ row }"><el-tag size="small" :type="row.completed ? 'success' : 'warning'">{{ row.score_label || '—' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="用时" width="86" align="center">
          <template #default="{ row }">{{ row.elapsed_sec != null ? row.elapsed_sec + ' 秒' : '—' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="生成时间" min-width="148" align="center" />
        <el-table-column label="操作" width="92" align="center" fixed="right">
          <template #default="{ row }"><el-button size="small" link type="primary" @click="openSaved(row.report_id)">查看报告</el-button></template>
        </el-table-column>
      </el-table>
      <div v-if="!historyReports.length && !historyLoading" class="empty-hint">暂无历史报告，完成一次训练后自动生成。</div>
    </el-card>

    <el-card shadow="never" class="block">
      <template #header>总体数据分析解读</template>
      <p class="interpretation">{{ interpretation || '正在加载…' }}</p>
    </el-card>

    <el-row :gutter="16">
      <el-col :span="12" :md="6" v-for="card in cards" :key="card.label">
        <el-card shadow="never" class="stat-card block">
          <div class="stat-top">
            <span class="stat-label">{{ card.label }}</span>
            <LineIcon :name="card.icon" class="stat-ico" />
          </div>
          <div class="stat-value">{{ card.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <div class="charts">
      <div class="chart" ref="promptChart"></div>
      <div class="chart" ref="sceneChart"></div>
      <div class="chart wide" ref="trendChart"></div>
    </div>

    <el-card shadow="never" class="block">
      <template #header>后续训练计划推荐（根据表现自动调整难度）</template>
      <el-table :data="plan" size="small">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="name" label="训练任务" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="kindType(row.kind)" size="small">{{ kindText(row.kind) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="难度" width="100">
          <template #default="{ row }">
            <span class="stars">{{ '★'.repeat(row.difficulty || 1) }}<span class="stars-off">{{ '★'.repeat(Math.max(0, 3 - (row.difficulty || 1))) }}</span></span>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="推荐理由" />
      </el-table>
      <div v-if="!plan.length" class="muted">暂无足够数据生成计划，完成几次训练后会自动生成</div>
    </el-card>

    <el-card shadow="never" class="block">
      <template #header>训练记录明细</template>
      <el-table :data="sessions" size="small">
        <el-table-column prop="task_name" label="任务" />
        <el-table-column prop="child" label="儿童" width="90" />
        <el-table-column prop="scene" label="场景" width="90" />
        <el-table-column label="提示等级" width="100">
          <template #default="{ row }">{{ promptLabels[row.prompt_level] || row.prompt_level }}</template>
        </el-table-column>
        <el-table-column label="结果" width="90">
          <template #default="{ row }">
            <el-tag :type="row.completed ? 'success' : 'danger'" size="small">
              {{ row.completed ? '完成' : '未完成' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="elapsed_sec" label="用时(秒)" width="90" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openReport(row.session_id || row.id)">查看报告</el-button>
          </template>
        </el-table-column>
      </el-table>
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

        <el-divider content-position="left">一、本次训练要点速览</el-divider>
        <ul class="pr-list highlights">
          <li v-for="(h, i) in report.highlights" :key="i">{{ h }}</li>
        </ul>

        <el-divider content-position="left">二、目标完成情况（基线 → 当前 → 目标）</el-divider>
        <el-table :data="[report.goal_progress]" size="small" border class="pr-table">
          <el-table-column prop="goal" label="训练目标" min-width="110" />
          <el-table-column label="基线" min-width="130">
            <template #default="{ row }">{{ row.baseline_label }}<div class="pr-mini">（{{ row.baseline_n }} 次历史）</div></template>
          </el-table-column>
          <el-table-column prop="current_label" label="本次表现" min-width="130" />
          <el-table-column prop="target" label="下一阶段目标" min-width="190" />
        </el-table>

        <el-divider content-position="left">三、领域能力现状（{{ report.ability.dimension }}）</el-divider>
        <div class="pr-grid">
          <div class="pr-card ok"><b>优势 / 亮点</b><p>{{ report.ability.strength }}</p></div>
          <div class="pr-card warn"><b>待支持项</b><p>{{ report.ability.weakness }}</p></div>
        </div>
        <ul class="pr-list"><li v-for="(s, i) in report.ability.support_needed" :key="i">{{ s }}</li></ul>

        <el-divider content-position="left">四、步骤完成明细与数据说明</el-divider>
        <el-table :data="report.step_details" size="small" border class="pr-table">
          <el-table-column prop="order" label="#" width="42" />
          <el-table-column prop="name" label="步骤" min-width="140" />
          <el-table-column label="完成情况" width="100">
            <template #default="{ row }"><el-tag size="small" :type="row.completed ? 'success' : 'warning'">{{ row.completed ? '完成' : '未完成' }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="confidence" label="置信度" width="90" />
        </el-table>
        <el-alert :type="report.data_quality.level === 'good' ? 'success' : 'warning'" :closable="false" :title="report.data_quality.note" class="pr-alert" />

        <el-divider content-position="left">五、近期趋势与提示依赖</el-divider>
        <div class="pr-grid">
          <div class="pr-card ok"><b>近期趋势</b><p>{{ report.trend.summary }}</p><p class="pr-mini">最近 5 次完成 {{ report.trend.recent_completion }}</p></div>
          <div class="pr-card warn"><b>提示依赖度 PDI {{ report.prompt_dependency.pdi }}</b><p>{{ report.prompt_dependency.comment }}</p></div>
        </div>

        <el-divider content-position="left">六、家庭延伸训练建议</el-divider>
        <ul class="pr-list"><li v-for="(t, i) in report.home_tips" :key="i">{{ t }}</li></ul>

        <el-divider content-position="left">七、后续训练任务与难度建议</el-divider>
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

        <el-divider content-position="left">八、家长反馈（可选）</el-divider>
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
        <el-button type="primary" @click="goTrainWithPlan" :disabled="!report || !report.next_plan.length">按建议去训练</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import api from '../api'
import LineIcon from '../components/LineIcon.vue'

const router = useRouter()
const data = ref(null)
const sessions = ref([])
const children = ref([])
const childId = ref(null)
const plan = ref([])
const reportVisible = ref(false)
const report = ref(null)
const historyReports = ref([])
const historyChild = ref(null)
const historyRange = ref(null)
const historyLoading = ref(false)
const promptChart = ref(null)
const sceneChart = ref(null)
const trendChart = ref(null)
const promptLabels = ['独立', '视觉', '语音', '示范', '家长协助']

const KIND_TEXT = { strengthen: '需加强', consolidate: '巩固', new: '新动作', review: '复习' }
const KIND_TYPE = { strengthen: 'danger', consolidate: 'warning', new: 'primary', review: 'info' }
function kindText(k) { return KIND_TEXT[k] || k }
function kindType(k) { return KIND_TYPE[k] || 'info' }

const interpretation = computed(() => data.value ? data.value.interpretation : '')

const cards = computed(() => {
  if (!data.value) return []
  const d = data.value
  return [
    { label: '训练次数', value: d.total, icon: 'activity' },
    { label: '任务完成率', value: (d.completion_rate * 100).toFixed(0) + '%', icon: 'completion' },
    { label: '提示依赖指数 PDI', value: d.pdi.toFixed(2), icon: 'pdi' },
    { label: '独立完成率', value: (d.independent_rate * 100).toFixed(0) + '%', icon: 'independence' },
  ]
})

async function load() {
  const [d, s] = await Promise.all([api.dashboard(childId.value), api.sessions(50)])
  data.value = d.data
  plan.value = d.data.plan || []
  sessions.value = s.data.sessions
  await nextTick()
  renderCharts(d.data)
}

async function loadChildren() {
  try {
    const c = await api.children()
    children.value = c.data.children
  } catch (e) { console.warn(e) }
}

async function openReport(sessionId) {
  try {
    const r = await api.professionalReport(sessionId)
    report.value = r.data
    reportVisible.value = true
  } catch (e) { console.warn(e); ElMessage.warning('专业报告加载失败') }
}

function childName(id) {
  const c = children.value.find(c => c.id === id)
  return c ? c.nickname : (id ? `#${id}` : '—')
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const params = {}
    if (historyChild.value) params.child_id = historyChild.value
    if (historyRange.value && historyRange.value.length === 2) {
      params.date_from = historyRange.value[0]
      params.date_to = historyRange.value[1]
    }
    const r = await api.reportHistory(params)
    historyReports.value = r.data.reports
  } catch (e) { console.warn(e) } finally { historyLoading.value = false }
}

async function openSaved(reportId) {
  try {
    const r = await api.savedReport(reportId)
    report.value = r.data
    reportVisible.value = true
  } catch (e) { console.warn(e); ElMessage.warning('报告加载失败') }
}

async function openLastReport() {
  try {
    const r = await api.latestSession()
    if (!r.data.session_id) { ElMessage.warning('暂无训练记录'); return }
    await openReport(r.data.session_id)
  } catch (e) { console.warn(e) }
}

function goTrainWithPlan() {
  if (!report.value || !report.value.next_plan.length) return
  const ids = report.value.next_plan.map(p => p.task_id).filter(Boolean)
  if (!ids.length) { ElMessage.warning('暂无可训练任务'); return }
  sessionStorage.setItem('plan_task_ids', JSON.stringify(ids))
  reportVisible.value = false
  router.push('/training')
}

const _charts = {}

function _chart(el, key) {
  if (!_charts[key]) _charts[key] = echarts.init(el)
  return _charts[key]
}

function renderCharts(d) {
  const axis = {
    axisLine: { lineStyle: { color: 'rgba(120,130,180,0.25)' } },
    axisLabel: { color: '#7a8199', fontSize: 11 },
    axisTick: { show: false },
    splitLine: { lineStyle: { color: 'rgba(120,130,180,0.15)', type: 'dashed' } },
  }
  const titleStyle = { color: '#3a4055', fontSize: 14, fontWeight: 600 }
  if (promptChart.value) {
    _chart(promptChart.value, 'prompt').setOption({
      title: { text: '提示等级分布', left: 12, top: 6, textStyle: titleStyle },
      tooltip: { trigger: 'axis' }, grid: { left: 40, right: 20, top: 44, bottom: 30 },
      xAxis: { type: 'category', data: d.prompt_labels, ...axis },
      yAxis: { type: 'value', ...axis },
      series: [{ type: 'bar', data: d.prompt_distribution, barMaxWidth: 34, itemStyle: { color: '#0b63ce', borderRadius: [6, 6, 0, 0] } }],
    }, true)
  }
  if (sceneChart.value) {
    const scenes = d.scene_breakdown || []
    _chart(sceneChart.value, 'scene').setOption({
      title: { text: '各场景完成情况', left: 12, top: 6, textStyle: titleStyle },
      tooltip: { trigger: 'axis' },
      legend: { data: ['完成', '未完成'], top: 6, right: 12, itemWidth: 10, itemHeight: 10, textStyle: { color: '#7a8199', fontSize: 11 } },
      grid: { left: 40, right: 20, top: 46, bottom: 30 },
      xAxis: { type: 'category', data: scenes.map(s => s.scene), ...axis },
      yAxis: { type: 'value', ...axis },
      series: [
        { name: '完成', type: 'bar', stack: 'a', data: scenes.map(s => s.done), itemStyle: { color: '#3f9e6e' } },
        { name: '未完成', type: 'bar', stack: 'a', data: scenes.map(s => s.count - s.done), itemStyle: { color: '#d06a63' } },
      ],
    }, true)
  }
  if (trendChart.value) {
    const trend = d.trend || []
    _chart(trendChart.value, 'trend').setOption({
      title: { text: '训练次数趋势', left: 12, top: 6, textStyle: titleStyle },
      tooltip: { trigger: 'axis' }, grid: { left: 40, right: 20, top: 44, bottom: 30 },
      xAxis: { type: 'category', data: trend.map(t => t.day), ...axis },
      yAxis: { type: 'value', ...axis },
      series: [{ type: 'line', data: trend.map(t => t.count), smooth: true, areaStyle: { opacity: 0.16 }, itemStyle: { color: '#4a90e8' } }],
    }, true)
  }
}

onMounted(async () => {
  await loadChildren()
  await load()
  await loadHistory()
})
setInterval(load, 10000)
</script>

<style scoped>
.page-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
.page-head .page-title { margin-bottom: 0; }
.head-actions { display: flex; align-items: center; gap: 10px; }
.interpretation { color: #3f4d63; line-height: 1.9; font-size: 14px; margin: 0; }
.stars { color: #e8a13c; letter-spacing: 1px; }
.stars-off { color: #d9dee8; }
.charts { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 18px; }
.chart {
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border: 1px solid rgba(255, 255, 255, 0.55);
  border-radius: var(--card-radius); height: 300px; padding: 12px;
  box-shadow: 0 8px 28px rgba(60, 70, 130, 0.08);
}
.wide { grid-column: 1 / -1; }
@media (max-width: 768px) { .charts { grid-template-columns: 1fr; } .wide { grid-column: 1; } }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.report-intro { display: flex; flex-direction: column; gap: 10px; }
.intro-line { display: flex; align-items: flex-start; gap: 12px; font-size: 13px; color: #4b5568; line-height: 1.7; }
.intro-label { flex: 0 0 60px; color: #98a2b8; font-size: 12px; padding-top: 1px; }
.history-filter { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 2px 0 14px; }
.history-table { width: 100%; }
.empty-hint { color: #a3a9bd; font-size: 12px; padding: 12px 0; text-align: center; }
.highlights { background: #f5f8ff; border-radius: 8px; padding: 10px 14px 10px 30px; }
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
:deep(.pr-dialog) { margin-top: 2vh !important; }
:deep(.pr-dialog .el-dialog__body) { max-height: 74vh; overflow-y: auto; padding-top: 8px; }
:deep(.pr-dialog .el-divider) { margin: 16px 0 12px; }
</style>
