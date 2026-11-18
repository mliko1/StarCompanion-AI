<template>
  <div>
    <h2 class="page-title">人工确认</h2>
    <p class="hint">AI 识别结果与人工确认分开保存，人工修正不会覆盖原始模型结果。</p>

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
        <el-table-column label="操作" width="200">
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
import api from '../api'

const records = ref([])

async function load() {
  const r = await api.vision(true)
  records.value = r.data.records
}

async function confirm(row, isCorrect) {
  await api.submitReview({ vision_record_id: row.id, is_correct: isCorrect })
  ElMessage.success('已保存人工确认')
  load()
}

onMounted(load)
</script>

<style scoped>
.hint {
  color: #5b6480; font-size: 13px; margin-bottom: 16px;
  padding: 12px 16px; border-radius: 12px;
  background: #f2f5ff; border: 1px solid #e3e9ff;
}
</style>
