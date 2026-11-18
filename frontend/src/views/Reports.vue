<template>
  <div>
    <div class="page-head">
      <h2 class="page-title">训练报告</h2>
      <el-button size="small" round @click="load">刷新数据</el-button>
    </div>

    <el-row :gutter="16">
      <el-col :span="12" :md="6" v-for="card in cards" :key="card.label">
        <el-card shadow="hover" class="stat-card block" :style="{ '--card-tint': card.tint }">
          <div class="stat-icon">{{ card.icon }}</div>
          <div class="stat-label">{{ card.label }}</div>
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
    { label: '训练次数', value: d.total, icon: '🏋️', tint: 'rgba(91,124,250,0.13)' },
    { label: '任务完成率', value: (d.completion_rate * 100).toFixed(0) + '%', icon: '✅', tint: 'rgba(103,194,58,0.14)' },
    { label: '提示依赖指数 PDI', value: d.pdi.toFixed(2), icon: '📉', tint: 'rgba(139,92,246,0.13)' },
    { label: '独立完成率', value: (d.independent_rate * 100).toFixed(0) + '%', icon: '🌟', tint: 'rgba(230,162,60,0.15)' },
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
  const base = { textStyle: { color: '#555' } }
  if (promptChart.value) {
    _chart(promptChart.value, 'prompt').setOption({
      title: { text: '提示等级分布', left: 'center', ...base.textStyle },
      tooltip: {}, grid: { left: 40, right: 20, top: 40, bottom: 30 },
      xAxis: { type: 'category', data: d.prompt_labels },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: d.prompt_distribution, itemStyle: { color: '#5b7cfa' } }],
    }, true)
  }
  if (sceneChart.value) {
    const scenes = d.scene_breakdown || []
    _chart(sceneChart.value, 'scene').setOption({
      title: { text: '各场景完成情况', left: 'center', ...base.textStyle },
      tooltip: { trigger: 'axis' }, legend: { data: ['完成', '未完成'] },
      grid: { left: 40, right: 20, top: 50, bottom: 30 },
      xAxis: { type: 'category', data: scenes.map(s => s.scene) },
      yAxis: { type: 'value' },
      series: [
        { name: '完成', type: 'bar', stack: 'a', data: scenes.map(s => s.done), itemStyle: { color: '#67c23a' } },
        { name: '未完成', type: 'bar', stack: 'a', data: scenes.map(s => s.count - s.done), itemStyle: { color: '#f56c6c' } },
      ],
    }, true)
  }
  if (trendChart.value) {
    const trend = d.trend || []
    _chart(trendChart.value, 'trend').setOption({
      title: { text: '训练次数趋势', left: 'center', ...base.textStyle },
      tooltip: { trigger: 'axis' }, grid: { left: 40, right: 20, top: 40, bottom: 30 },
      xAxis: { type: 'category', data: trend.map(t => t.day) },
      yAxis: { type: 'value' },
      series: [{ type: 'line', data: trend.map(t => t.count), smooth: true, areaStyle: { opacity: 0.2 }, itemStyle: { color: '#5b7cfa' } }],
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
  background: #fff; border-radius: var(--card-radius); height: 300px; padding: 8px;
  box-shadow: var(--shadow);
}
.wide { grid-column: 1 / -1; }
@media (max-width: 768px) { .charts { grid-template-columns: 1fr; } .wide { grid-column: 1; } }
</style>
