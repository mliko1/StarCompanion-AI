<template>
  <div>
    <h2 class="page-title">首页仪表盘</h2>

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

    <el-card shadow="never" class="block">
      <template #header>当前训练状态</template>
      <template v-if="status">
        <div class="status-line"><span class="k">状态</span><el-tag :type="stateType" effect="light" round>{{ stateText }}</el-tag></div>
        <div class="status-line" v-if="status.task_name"><span class="k">当前任务</span><span class="v">{{ status.task_name }}</span></div>
        <div class="status-line"><span class="k">摄像头</span><span class="v">{{ status.camera && status.camera.running ? '运行中' : '未启动' }}</span></div>
        <div class="status-line" v-if="status.camera && status.camera.person_detected"><span class="k">人物</span><span class="v">已检测到</span></div>
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
import LineIcon from '../components/LineIcon.vue'

const stats = ref(null)
const status = ref(null)
const sessions = ref([])
const suggestions = ref([])

const cards = computed(() => {
  if (!stats.value) return []
  return [
    { label: '累计训练次数', value: stats.value.total, icon: 'activity' },
    { label: '任务完成率', value: (stats.value.completion_rate * 100).toFixed(0) + '%', icon: 'completion' },
    { label: '提示依赖指数 PDI', value: stats.value.pdi.toFixed(2), icon: 'pdi' },
    { label: '独立完成率', value: (stats.value.independent_rate * 100).toFixed(0) + '%', icon: 'independence' },
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
.status-line { display: flex; align-items: center; gap: 10px; padding: 6px 0; }
.status-line .k { color: #8b93a5; width: 70px; font-size: 13px; }
.status-line .v { color: #344054; font-size: 14px; font-weight: 500; }
.advice {
  padding: 11px 14px; margin-bottom: 10px; border-radius: 10px;
  background: #f7f9fc;
  font-size: 14px; color: #475467;
}
</style>
