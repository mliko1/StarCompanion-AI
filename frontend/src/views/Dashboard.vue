<template>
  <div>
    <h2 class="page-title">首页仪表盘</h2>

    <el-row :gutter="16">
      <el-col :span="12" :md="6" v-for="card in cards" :key="card.label">
        <el-card shadow="hover" class="stat-card block">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value">{{ card.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="block">
      <template #header>当前训练状态</template>
      <template v-if="status">
        <p>状态：<el-tag :type="stateType">{{ stateText }}</el-tag></p>
        <p v-if="status.task_name">当前任务：{{ status.task_name }}</p>
        <p>摄像头：{{ status.camera && status.camera.running ? '运行中' : '未启动' }}</p>
        <p v-if="status.camera && status.camera.person_detected">检测到人物</p>
      </template>
      <template v-else>加载中…</template>
    </el-card>

    <el-card shadow="never" class="block">
      <template #header>个体化辅助建议（参考）</template>
      <div v-for="(a, i) in suggestions" :key="i" class="advice">{{ a.text }}</div>
      <div v-if="!suggestions.length" class="muted">暂无建议，训练数据积累后自动生成</div>
    </el-card>

    <el-card shadow="never" class="block">
      <template #header>最近训练记录</template>
      <el-table :data="sessions" size="small">
        <el-table-column prop="task_name" label="任务" />
        <el-table-column prop="scene" label="场景" width="90" />
        <el-table-column label="结果" width="90">
          <template #default="{ row }">
            <el-tag :type="row.completed ? 'success' : 'danger'" size="small">
              {{ row.completed ? '完成' : '未完成' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="elapsed_sec" label="用时(秒)" width="90" />
      </el-table>
      <div v-if="!sessions.length" class="muted">暂无训练记录</div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'

const stats = ref(null)
const status = ref(null)
const sessions = ref([])
const suggestions = ref([])

const cards = computed(() => {
  if (!stats.value) return []
  return [
    { label: '累计训练次数', value: stats.value.total },
    { label: '任务完成率', value: (stats.value.completion_rate * 100).toFixed(0) + '%' },
    { label: '提示依赖指数 PDI', value: stats.value.pdi.toFixed(2) },
    { label: '独立完成率', value: (stats.value.independent_rate * 100).toFixed(0) + '%' },
  ]
})

const stateMap = { idle: '空闲', running: '训练中', paused: '已暂停', done: '已完成', aborted: '已结束' }
const stateText = computed(() => status.value ? (stateMap[status.value.state] || status.value.state) : '')
const stateType = computed(() =>
  ({ running: 'primary', paused: 'warning', done: 'success', aborted: 'info', idle: 'info' }[status.value && status.value.state] || 'info'))

async function load() {
  try {
    const [d, s, ss] = await Promise.all([api.dashboard(), api.status(), api.sessions(8)])
    stats.value = d.data
    status.value = s.data.training
    sessions.value = ss.data.sessions
    suggestions.value = d.data.suggestions || []
  } catch (e) { console.warn(e) }
}
onMounted(load)
setInterval(load, 5000)
</script>

<style scoped>
.stat-label { color: #999; font-size: 13px; }
.stat-value { font-size: 28px; font-weight: 700; margin-top: 6px; }
.advice { padding: 10px 14px; margin-bottom: 8px; background: #f0f7ff; border-left: 4px solid #409eff; border-radius: 6px; font-size: 14px; }
.muted { color: #bbb; font-size: 13px; }
</style>
