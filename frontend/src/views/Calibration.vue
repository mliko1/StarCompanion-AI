<template>
  <div>
    <h2 class="page-title">家庭校准</h2>
    <p class="sub">像人脸识别一样：把物品放在镜头前展示，系统自动采集并自动训练，无需手动拍照。</p>

    <!-- 第 1 步 -->
    <el-card shadow="never" class="block">
      <template #header>第 1 步 · 给物品起个名字</template>
      <div class="row">
        <el-input
          v-model="className"
          placeholder="如 my_box（字母/数字/下划线）"
          style="width: 260px"
          :disabled="busy"
        />
        <el-button type="primary" :disabled="busy" @click="startCollect">开始展示</el-button>
        <el-button :disabled="state !== 'collecting'" @click="cancel">取消</el-button>
      </div>
      <p class="hint">把物品放进画面中央的绿色框，缓慢转动不同角度，系统会自动拍照。</p>
    </el-card>

    <!-- 第 2 步 -->
    <el-card shadow="never" class="block">
      <template #header>
        第 2 步 · 镜头前展示（自动采集）
        <el-tag
          v-if="state === 'collecting'"
          size="small"
          :type="count >= minShots ? 'success' : 'info'"
          class="count-tag"
        >
          已自动采集 {{ count }} 张 / 建议 ≥ {{ minShots }}
        </el-tag>
      </template>
      <div class="cam-row">
        <div class="video-frame">
          <img v-if="cameraOn" :src="streamUrl" class="video" alt="摄像头画面" />
          <div v-else class="video placeholder">摄像头未启动</div>
          <div v-if="cameraOn && state === 'collecting'" class="guide-box" :style="guideStyle">
            <span class="guide-label">物品放入此框</span>
          </div>
        </div>
        <div class="controls">
          <el-button
            type="success"
            size="large"
            :disabled="state !== 'collecting' || count < 5"
            @click="finish"
          >
            结束展示并训练
          </el-button>
          <p v-if="state === 'collecting'" class="hint">
            现在把物品放进绿框，缓慢转动 / 移动它，画面每变化一次系统就自动拍一张。
          </p>
          <el-alert
            v-if="state === 'training'"
            class="msg"
            type="info"
            :closable="false"
            title="训练中：系统自动训练到最佳识别效果，可能需要 10~30 分钟，完成后自动提示。"
          />
        </div>
      </div>
    </el-card>

    <!-- 结果提示 -->
    <el-alert
      v-if="alert"
      class="msg-block"
      :type="alert.type"
      :closable="false"
      :title="alert.text"
    />

    <!-- 已训练模型 -->
    <el-card shadow="never" class="block">
      <template #header>已训练的家庭模型</template>
      <el-table :data="models" size="small">
        <el-table-column prop="class_name" label="类名" />
        <el-table-column prop="filename" label="模型文件" />
        <el-table-column label="大小" width="120">
          <template #default="{ row }">{{ fmtSize(row.size_bytes) }}</template>
        </el-table-column>
      </el-table>
      <div v-if="!models.length" class="muted">
        还没有训练好的模型。训练完成后，这个物品就能被系统自动识别。
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const className = ref('my_box')
const state = ref('idle')
const count = ref(0)
const minShots = ref(20)
const cameraOn = ref(false)
const models = ref([])
const message = ref('')
const error = ref(null)
const ratio = ref(0.6)
const streamUrl = '/api/camera/stream'

const busy = computed(() => state.value === 'collecting' || state.value === 'training')

const alert = computed(() => {
  if (state.value === 'error' && error.value) return { type: 'error', text: error.value }
  if (state.value === 'done') return { type: 'success', text: message.value || '训练完成！' }
  return null
})

const guideStyle = computed(() => {
  const m = (1 - ratio.value) / 2
  return {
    left: (m * 100) + '%',
    top: (m * 100) + '%',
    width: (ratio.value * 100) + '%',
    height: (ratio.value * 100) + '%',
  }
})

function fmtSize(n) {
  if (!n) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let v = n
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return v.toFixed(1) + ' ' + units[i]
}

async function refresh() {
  try {
    const r = await api.calibrationStatus()
    const s = r.data
    state.value = s.state
    count.value = s.count
    minShots.value = s.min_shots
    cameraOn.value = !!s.camera_running
    models.value = s.models || []
    message.value = s.message
    error.value = s.error
    if (s.guide_box_ratio) ratio.value = s.guide_box_ratio
  } catch (e) {
    console.warn(e)
  }
}

async function startCollect() {
  const name = (className.value || '').trim()
  if (!name) { ElMessage.warning('请先填写类名'); return }
  const r = await api.startCalibration({ class_name: name })
  ElMessage({ type: r.data.ok ? 'success' : 'warning', message: r.data.msg })
  refresh()
}

async function finish() {
  const r = await api.finishCalibration()
  ElMessage({ type: r.data.ok ? 'success' : 'warning', message: r.data.msg })
  refresh()
}

async function cancel() {
  const r = await api.stopCalibration()
  ElMessage({ type: r.data.ok ? 'success' : 'warning', message: r.data.msg })
  refresh()
}

let timer = null
onMounted(() => {
  refresh()
  timer = setInterval(refresh, 1500)
})
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.sub { color: #8b93a5; font-size: 14px; margin: -12px 0 20px; }
.row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.hint { color: #93a1b5; font-size: 13px; margin-top: 10px; line-height: 1.7; }
.count-tag { margin-left: 12px; }
.msg { margin-top: 14px; }
.msg-block { margin-bottom: 18px; }
.cam-row { display: flex; gap: 20px; align-items: flex-start; flex-wrap: wrap; }
.video-frame {
  position: relative; width: 100%; max-width: 560px;
  border-radius: 14px; overflow: hidden; background: #000;
  box-shadow: 0 10px 30px rgba(20, 30, 60, 0.18);
}
.video { width: 100%; display: block; }
.placeholder {
  width: 100%; height: 360px; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #eef1f8 0%, #e6e9f5 100%);
  color: #a3a9bd; font-size: 15px;
}
.guide-box {
  position: absolute; border: 3px solid #2ee06a; border-radius: 6px;
  box-sizing: border-box;
  box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.28);
  pointer-events: none;
}
.guide-label {
  position: absolute; top: -30px; left: 0; color: #2ee06a; font-size: 13px;
  font-weight: 600; white-space: nowrap; text-shadow: 0 1px 3px rgba(0, 0, 0, 0.6);
}
.controls { display: flex; flex-direction: column; gap: 14px; }
</style>
