<template>
  <div>
    <div class="page-head">
      <h2 class="page-title">训练报告</h2>
      <el-button size="small" round @click="load">刷新数据</el-button>
    </div>

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
      <template #header>训练记录明细</template>
      <el-table :data="sessions" size="small">
        <el-table-column prop="task_name" label="任务" />
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
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import api from '../api'
import LineIcon from '../components/LineIcon.vue'

const data = ref(null)
const sessions = ref([])
const promptChart = ref(null)
const sceneChart = ref(null)
const trendChart = ref(null)
const promptLabels = ['独立', '视觉', '语音', '示范', '家长协助']

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
  const [d, s] = await Promise.all([api.dashboard(), api.sessions(50)])
  data.value = d.data
  sessions.value = s.data.sessions
  await nextTick()
  renderCharts(d.data)
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

onMounted(load)
setInterval(load, 5000)
</script>

<style scoped>
.page-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.page-head .page-title { margin-bottom: 0; }
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
</style>
