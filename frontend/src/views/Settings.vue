<template>
  <div>
    <h2 class="page-title">档案与系统设置</h2>

    <el-card shadow="never" class="block">
      <template #header>账号</template>
      <div class="account">
        <span class="muted">当前账号：{{ account || '—' }}</span>
        <el-button size="small" round @click="onLogout">退出登录</el-button>
      </div>
    </el-card>

    <el-card shadow="never" class="block">
      <template #header>匿名儿童档案</template>
      <el-table :data="children" size="small">
        <el-table-column prop="id" label="#" width="60" />
        <el-table-column prop="nickname" label="昵称" />
        <el-table-column prop="birth_year" label="出生年份" width="100" />
        <el-table-column prop="gender" label="性别" width="80" />
      </el-table>
      <div v-if="!children.length" class="muted">暂无档案</div>
    </el-card>

    <el-card shadow="never" class="block">
      <template #header>训练任务列表（{{ tasks.length }} 项）</template>
      <el-table :data="tasks" size="small" max-height="360">
        <el-table-column prop="name" label="任务名称" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.type === 'action' ? '' : 'warning'">
              {{ row.type === 'action' ? '动作' : '生活技能' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="110" />
        <el-table-column prop="difficulty" label="难度" width="70" />
      </el-table>
    </el-card>

    <el-card shadow="never" class="block">
      <template #header>使用说明</template>
      <ul class="tips">
        <li>电脑运行后端后，手机/平板在同一 Wi-Fi 下，用浏览器打开「电脑局域网 IP:8000」访问。</li>
        <li>电脑局域网 IP 可在命令行输入 <code>ipconfig</code> 查看「IPv4 地址」。</li>
        <li>数据保存在本机 <code>data/xingban.db</code>，多设备共享同一份数据。</li>
        <li>AI 识别结果仅作辅助参考，不能替代专业康复人员判断。</li>
      </ul>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { currentUser, logout } from '../auth'

const router = useRouter()
const children = ref([])
const tasks = ref([])
const account = currentUser()

function onLogout() {
  logout()
  router.replace('/login')
}

onMounted(async () => {
  const [c, t] = await Promise.all([api.children(), api.tasks()])
  children.value = c.data.children
  tasks.value = t.data.tasks
})
</script>

<style scoped>
.account { display: flex; align-items: center; justify-content: space-between; }
.tips { padding-left: 20px; line-height: 2.1; color: #5b6480; }
.tips code {
  background: #eef1f8; padding: 2px 8px; border-radius: 6px;
  color: #0b63ce; font-family: Consolas, monospace; font-size: 13px;
}
</style>
