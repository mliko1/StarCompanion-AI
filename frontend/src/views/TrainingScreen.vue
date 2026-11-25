<template>
  <div class="screen">
    <div class="screen-head">
      <div>
        <h1>训练大屏</h1>
        <p>实时摄像头画面与识别状态，跟随训练页同步</p>
      </div>
      <div class="head-btns">
        <el-tag v-if="status && status.state !== 'idle'" :type="stateType" effect="dark" size="large">{{ stateText }}</el-tag>
        <el-button size="small" @click="toggleFullscreen">{{ isFullscreen ? '退出全屏' : '全屏显示' }}</el-button>
        <el-button size="small" @click="closeWindow">关闭大屏</el-button>
      </div>
    </div>

    <div class="screen-body">
      <div class="video-area">
        <img v-if="cameraRunning" :src="streamUrl" class="video" alt="摄像头实时画面" />
        <div v-else class="video placeholder">
          <div class="ph-icon">摄像头</div>
          <p>摄像头未启动，请先在训练页开始训练</p>
        </div>
        <div v-if="status && status.state !== 'idle'" class="video-overlay">
          <div class="overlay-top">
            <span class="ov-task">{{ status.task_name || '当前训练' }}</span>
            <span v-if="status.plan_mode" class="ov-plan">
              第 {{ (status.plan_index || 0) + 1 }}/{{ (status.plan_tasks || []).length }} 个动作
              · {{ (status.plan_results || []).length }}/{{ status.plan_total }} 轮
            </span>
          </div>
          <div v-if="status.plan_mode" class="ov-progress">
            <el-progress :percentage="planPercent" :stroke-width="6" :show-text="false" />
          </div>
        </div>
      </div>

      <div class="info-panel">
        <div class="info-block">
          <h3>当前训练</h3>
          <template v-if="status && status.state !== 'idle'">
            <p><span>任务</span><b>{{ status.task_name || '—' }}</b></p>
            <p v-if="status.target_action"><span>目标动作</span><b>{{ status.target_action }}</b></p>
            <p v-if="status.target_object"><span>目标物品</span><b>{{ status.target_object }}</b></p>
            <p><span>当前识别</span>
              <b>{{ status.current_action || '无' }}</b>
              <el-tag v-if="status.detected_now" type="success" size="small">已命中</el-tag>
            </p>
            <p v-if="status.task_type === 'skill'"><span>当前步骤</span><b>{{ stepName(status.current_step) }}</b></p>
            <p v-if="status.task_type === 'skill'"><span>交互状态</span><b>{{ status.current_interaction || '—' }}</b></p>
          </template>
          <p v-else class="empty">尚未开始训练</p>
        </div>

        <div v-if="status && status.task_type === 'skill' && status.completed_steps" class="info-block">
          <h3>步骤完成情况</h3>
          <div class="steps">
            <span v-for="(s, i) in stepList" :key="s" class="step-chip"
                  :class="{ done: status.completed_steps.includes(s), current: status.current_step === s }">
              {{ i + 1 }}. {{ stepName(s) }}
            </span>
          </div>
        </div>

        <div class="info-block">
          <h3>训练控制</h3>
          <div class="control-btns">
            <el-button type="success" :disabled="state !== 'running'" @click="pause">暂停</el-button>
            <el-button type="primary" :disabled="state !== 'paused'" @click="resume">恢复</el-button>
            <el-button type="danger" :disabled="state !== 'running' && state !== 'paused'" @click="stop">结束训练</el-button>
          </div>
          <p class="tip">完成后请回到「报告」栏目查看专业分析报告。</p>
        </div>

        <div v-if="status && status.events && status.events.length" class="info-block">
          <h3>最近事件</h3>
          <ul class="events">
            <li v-for="(e, i) in status.events.slice(-6).reverse()" :key="i">
              <span class="ev-time">{{ fmtTime(e.ts) }}</span> {{ e.text || e.event || e.type }}
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const status = ref(null)
const streamUrl = '/api/camera/stream'
const isFullscreen = ref(false)

const STEP_MAP = {
  find_toy: '寻找玩具', approach_toy: '接近玩具', pick_toy: '拿起玩具',
  move_toy: '移动玩具', place_toy: '放入收纳盒',
}
const stepList = ['find_toy', 'approach_toy', 'pick_toy', 'move_toy', 'place_toy']
function stepName(s) { return STEP_MAP[s] || s || '—' }

const state = computed(() => status.value ? status.value.state : 'idle')
const stateType = computed(() => ({
  running: 'success', paused: 'warning', done: 'success', aborted: 'danger', idle: 'info',
}[state.value] || 'info'))
const stateText = computed(() => ({
  running: '训练中', paused: '已暂停', done: '已完成', aborted: '已结束', idle: '空闲',
}[state.value] || state.value))
const cameraRunning = computed(() => status.value && status.value.camera && status.value.camera.running)
const planPercent = computed(() => {
  const s = status.value
  if (!s || !s.plan_mode || !s.plan_total) return 0
  return Math.min(100, Math.round((s.plan_results || []).length / s.plan_total * 100))
})

function fmtTime(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString('zh-CN', { hour12: false })
}

async function refresh() {
  try {
    const r = await api.trainingStatus()
    status.value = r.data
  } catch (e) { console.warn(e) }
}

async function pause() { await api.pauseTraining(); refresh() }
async function resume() { await api.resumeTraining(); refresh() }
async function stop() {
  await api.stopTraining()
  refresh()
  ElMessage.success('训练已结束，请到报告栏目查看报告')
}

async function toggleFullscreen() {
  try {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen()
      isFullscreen.value = true
    } else {
      await document.exitFullscreen()
      isFullscreen.value = false
    }
  } catch (e) { console.warn(e) }
}

function closeWindow() { window.close() }

function onFsChange() { isFullscreen.value = !!document.fullscreenElement }

let timer = null
onMounted(() => {
  refresh()
  timer = setInterval(refresh, 1000)
  document.addEventListener('fullscreenchange', onFsChange)
})
onUnmounted(() => {
  clearInterval(timer)
  document.removeEventListener('fullscreenchange', onFsChange)
})
</script>

<style scoped>
.screen { height: 100vh; display: flex; flex-direction: column; padding: 18px 22px; background: #0d1424; color: #e8eefc; }
.screen-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.screen-head h1 { font-size: 22px; font-weight: 700; }
.screen-head p { color: #8fa3c8; font-size: 12px; margin-top: 4px; }
.head-btns { display: flex; align-items: center; gap: 10px; }
.screen-body { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 1fr) 330px; gap: 18px; }
.video-area { position: relative; border-radius: 16px; overflow: hidden; background: #050a14; display: flex; align-items: center; justify-content: center; min-height: 0; }
.video { width: 100%; height: 100%; object-fit: contain; display: block; }
.placeholder { flex-direction: column; gap: 12px; color: #6f82a6; font-size: 14px; }
.ph-icon { width: 72px; height: 72px; border-radius: 50%; background: #182238; display: flex; align-items: center; justify-content: center; font-size: 13px; }
.video-overlay { position: absolute; left: 0; right: 0; top: 0; padding: 14px 18px; background: linear-gradient(180deg, rgba(5,10,20,.78), transparent); }
.overlay-top { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.ov-task { font-size: 18px; font-weight: 700; text-shadow: 0 2px 6px #000; }
.ov-plan { font-size: 13px; color: #c9d6f0; }
.ov-progress { margin-top: 8px; }
.info-panel { display: flex; flex-direction: column; gap: 14px; overflow-y: auto; padding-right: 4px; }
.info-block { background: #151e33; border-radius: 14px; padding: 14px 16px; }
.info-block h3 { font-size: 14px; color: #9fb4db; margin-bottom: 10px; font-weight: 600; }
.info-block p { display: flex; align-items: center; gap: 8px; font-size: 13px; line-height: 2; color: #c8d5ef; }
.info-block p span { color: #7f92b5; min-width: 68px; }
.info-block p b { color: #fff; font-weight: 600; }
.info-block .empty { color: #7588aa; }
.control-btns { display: flex; gap: 8px; flex-wrap: wrap; }
.tip { margin-top: 10px; font-size: 11px !important; color: #7588aa !important; line-height: 1.6 !important; }
.steps { display: flex; flex-wrap: wrap; gap: 6px; }
.step-chip { padding: 4px 8px; border-radius: 14px; background: #1e2c48; color: #8fa3c8; font-size: 11px; }
.step-chip.done { background: #1f4d38; color: #7ee2a8; }
.step-chip.current { background: #1d3e6e; color: #9ecbff; }
.events { list-style: none; font-size: 11px; color: #9fb4db; line-height: 1.9; }
.ev-time { color: #6c80a4; margin-right: 6px; }
@media (max-width: 900px) { .screen-body { grid-template-columns: 1fr; } .info-panel { max-height: 40vh; } }
</style>
