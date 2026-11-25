<template>
  <div>
    <h2 class="page-title">人工确认</h2>
    <p class="hint">AI 识别结果与人工确认分开保存，人工修正不会覆盖原始模型结果。</p>

    <el-card shadow="never" class="block">
      <template #header>
        <span>确认孩子的惯用手</span>
      </template>
      <p class="hint">孩子完成动作时惯用哪只手？确认后，系统会按孩子的习惯判定（例如"举右手"会按惯用左手自动切换为"举左手"）。</p>
      <el-form :inline="true">
        <el-form-item label="孩子">
          <el-select v-model="handForm.child_id" placeholder="选择孩子" style="width: 150px">
            <el-option v-for="c in children" :key="c.id" :label="c.nickname" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="任务">
          <el-select v-model="handForm.task_id" placeholder="选择任务" filterable style="width: 180px">
            <el-option v-for="t in tasks" :key="t.task_id" :label="t.name" :value="t.task_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="惯用手">
          <el-radio-group v-model="handForm.preferred_hand">
            <el-radio-button label="left">左手</el-radio-button>
            <el-radio-button label="right">右手</el-radio-button>
            <el-radio-button label="both">双手</el-radio-button>
            <el-radio-button label="unknown">不确定</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="submitHand">保存惯用手</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="block">
      <template #header>
        <span>待确认的识别结果</span>
        <el-button size="small" style="float: right" @click="load">刷新</el-button>
      </template>
      <el-table :data="records" size="small">
        <el-table-column prop="id" label="#" width="60" />
        <el-table-column label="识别时间" width="180">
          <template #default="{ row }">{{ (row.timestamp || '').replace('T', ' ').slice(0, 19) }}</template>
        </el-table-column>
        <el-table-column prop="model" label="模型" width="120" />
        <el-table-column label="不确定原因" min-width="160">
          <template #default="{ row }">{{ row.uncertainty_reason || '-' }}</template>
        </el-table-column>
        <el-table-column label="置信度" width="90">
          <template #default="{ row }">{{ row.confidence != null ? row.confidence.toFixed(2) : '-' }}</template>
        </el-table-column>
        <el-table-column label="纠正结果" min-width="150">
          <template #default="{ row }">
            <el-input v-model="row.corrected_text" size="small" placeholder="有误时填写正确结果" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button size="small" type="success" @click="confirm(row, true)">识别正确</el-button>
            <el-button size="small" type="warning" @click="confirm(row, false)">识别有误</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!records.length" class="muted">暂无待确认记录</div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const records = ref([])
const children = ref([])
const tasks = ref([])
const handForm = ref({ child_id: null, task_id: null, preferred_hand: 'right' })

async function load() {
  const r = await api.vision(true)
  records.value = r.data.records
}

async function loadMeta() {
  children.value = (await api.children()).data.children
  const all = (await api.tasks()).data.tasks
  tasks.value = all.filter((t) => t.type === 'action')
}

async function submitHand() {
  if (handForm.value.child_id == null || !handForm.value.task_id) {
    ElMessage.warning('请先选择孩子和任务')
    return
  }
  const r = await api.confirmHand(handForm.value)
  if (r.data && r.data.ok) ElMessage.success('已记录该孩子的惯用手')
  else ElMessage.error((r.data && r.data.msg) || '保存失败')
}

async function confirm(row, isCorrect) {
  if (!isCorrect && !row.corrected_text) {
    ElMessage.warning('识别有误时请填写正确结果')
    return
  }
  const corrected = row.corrected_text
    ? { text: row.corrected_text, action_id: row.corrected_text }
    : null
  await api.submitReview({
    vision_record_id: row.id, is_correct: isCorrect,
    corrected_result: corrected, note: row.corrected_text || null,
  })
  ElMessage.success('已保存人工确认' + (isCorrect ? '' : '并回写纠正结果'))
  load()
}

onMounted(() => {
  load()
  loadMeta()
})
</script>

<style scoped>
.hint {
  color: #5b6480; font-size: 13px; margin-bottom: 16px;
  padding: 12px 16px; border-radius: 12px;
  background: #f2f5ff; border: 1px solid #e3e9ff;
}
</style>
