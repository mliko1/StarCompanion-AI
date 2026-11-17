<template>
  <div>
    <h2 class="page-title">训练操作</h2>

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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'

const tasks = ref([])
const scenes = ref([])
const taskId = ref('')
const sceneId = ref('')
const promptLevel = ref(0)
const status = ref(null)
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

const stateMap = { idle: '空闲', running: '训练中', paused: '已暂停', done: '已完成', aborted: '已结束' }
const stateText = computed(() => stateMap[state.value] || state.value)
const stateType = computed(() =>
  ({ running: 'primary', paused: 'warning', done: 'success', aborted: 'info', idle: 'info' }[state.value] || 'info'))

function stepName(key) { return STEP_MAP[key] || key || '—' }

async function loadBase() {
  const [t, s] = await Promise.all([api.tasks(), api.scenes()])
  tasks.value = t.data.tasks
  scenes.value = s.data.scenes
  if (scenes.value.length) sceneId.value = scenes.value[0].id
}
async function refreshStatus() {
  try {
    const r = await api.trainingStatus()
    status.value = r.data
  } catch (e) { console.warn(e) }
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
.video-wrap { display: flex; justify-content: center; }
.video { width: 100%; max-width: 640px; border-radius: 8px; background: #000; }
.placeholder { width: 100%; max-width: 640px; height: 360px; display: flex; align-items: center; justify-content: center; background: #f0f0f0; color: #999; }
.steps { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
.step-chip { padding: 4px 10px; border-radius: 14px; background: #f0f0f0; color: #999; font-size: 13px; }
.step-chip.done { background: #e8f5e9; color: #67c23a; }
.step-chip.current { background: #e6f0ff; color: #409eff; font-weight: 600; }
</style>
