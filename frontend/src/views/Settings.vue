<template>
  <div>
    <h2 class="page-title">档案与系统设置</h2>

    <el-card shadow="never" class="block">
      <template #header>账号</template>
      <div class="account">
        <span class="muted">当前账号：{{ account || '—' }}</span>
        <div class="account-actions">
          <el-button size="small" round @click="passwordDialog = true">修改密码</el-button>
          <el-button size="small" round @click="onLogout">退出登录</el-button>
        </div>
      </div>
    </el-card>

    <el-dialog v-model="passwordDialog" title="修改密码" width="420px" :close-on-click-modal="false">
      <el-form label-width="90px">
        <el-form-item label="原密码" required>
          <el-input v-model="pwdForm.old" type="password" show-password autocomplete="current-password" placeholder="请输入当前密码" />
        </el-form-item>
        <el-form-item label="新密码" required>
          <el-input v-model="pwdForm.new" type="password" show-password autocomplete="new-password" placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="确认新密码" required>
          <el-input v-model="pwdForm.confirm" type="password" show-password autocomplete="new-password" placeholder="再次输入新密码" @keyup.enter="onChangePassword" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closePasswordDialog">取消</el-button>
        <el-button type="primary" :loading="pwdSaving" @click="onChangePassword">确认修改</el-button>
      </template>
    </el-dialog>

    <el-card shadow="never" class="block">
      <template #header>
        <div class="card-head">
          <span>儿童档案</span>
          <el-button type="primary" size="small" round @click="openAdd">新增儿童</el-button>
        </div>
      </template>
      <el-table :data="children" size="small">
        <el-table-column prop="id" label="#" width="50" />
        <el-table-column prop="nickname" label="昵称" />
        <el-table-column prop="birth_year" label="出生年份" width="90" />
        <el-table-column prop="gender" label="性别" width="70" />
        <el-table-column prop="notes" label="备注" show-overflow-tooltip />
        <el-table-column label="操作" width="130">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" link type="danger" @click="removeChild(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!children.length" class="muted">暂无档案，点击右上角「新增儿童」添加</div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑儿童档案' : '新增儿童档案'" width="420px">
      <el-form label-width="80px">
        <el-form-item label="昵称" required>
          <el-input v-model="form.nickname" placeholder="如 小明" />
        </el-form-item>
        <el-form-item label="出生年份">
          <el-input-number v-model="form.birth_year" :min="2000" :max="2030" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="性别">
          <el-select v-model="form.gender" placeholder="请选择" style="width: 100%">
            <el-option label="男" value="男" />
            <el-option label="女" value="女" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="3" placeholder="如：喜欢积木、对声音敏感等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveChild">保存</el-button>
      </template>
    </el-dialog>

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
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import { currentUser, logout, changePassword } from '../auth'

const router = useRouter()
const children = ref([])
const tasks = ref([])
const account = currentUser()

const passwordDialog = ref(false)
const pwdSaving = ref(false)
const pwdForm = ref({ old: '', new: '', confirm: '' })

function closePasswordDialog() {
  passwordDialog.value = false
  pwdForm.value = { old: '', new: '', confirm: '' }
}

async function onChangePassword() {
  const { old, new: next, confirm } = pwdForm.value
  if (!old) { ElMessage.warning('请输入原密码'); return }
  if (!next || next.length < 6) { ElMessage.warning('新密码至少 6 位'); return }
  if (next !== confirm) { ElMessage.warning('两次输入的新密码不一致'); return }
  pwdSaving.value = true
  try {
    const r = await changePassword(old, next)
    if (r.ok) {
      closePasswordDialog()
      ElMessage.success(r.msg || '密码已修改，请重新登录')
      router.replace('/login')
    } else {
      ElMessage.warning(r.msg || '修改失败')
    }
  } finally {
    pwdSaving.value = false
  }
}

const dialogVisible = ref(false)
const editingId = ref(null)
const form = ref({ nickname: '', birth_year: null, gender: '', notes: '' })

function onLogout() {
  logout()
  router.replace('/login')
}

function resetForm() {
  form.value = { nickname: '', birth_year: null, gender: '', notes: '' }
}

function openAdd() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.value = {
    nickname: row.nickname,
    birth_year: row.birth_year,
    gender: row.gender || '',
    notes: row.notes || '',
  }
  dialogVisible.value = true
}

async function saveChild() {
  const name = (form.value.nickname || '').trim()
  if (!name) { ElMessage.warning('请填写昵称'); return }
  const payload = { ...form.value, nickname: name }
  try {
    if (editingId.value) {
      await api.updateChild(editingId.value, payload)
      ElMessage.success('已更新')
    } else {
      await api.createChild(payload)
      ElMessage.success('已添加')
    }
    dialogVisible.value = false
    await loadChildren()
  } catch (e) {
    const detail = e.response && e.response.data && e.response.data.detail
    ElMessage.warning(detail || '保存失败')
  }
}

async function removeChild(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.nickname}」的档案吗？`, '提示', { type: 'warning' })
  } catch { return }
  const r = await api.deleteChild(row.id)
  ElMessage({ type: r.data.ok ? 'success' : 'warning', message: r.data.msg })
  await loadChildren()
}

async function loadChildren() {
  const c = await api.children()
  children.value = c.data.children
}

onMounted(async () => {
  const [c, t] = await Promise.all([api.children(), api.tasks()])
  children.value = c.data.children
  tasks.value = t.data.tasks
})
</script>

<style scoped>
.account { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.account-actions { display: flex; gap: 8px; }
.card-head { display: flex; align-items: center; justify-content: space-between; }
.tips { padding-left: 20px; line-height: 2.1; color: #5b6480; }
.tips code {
  background: #eef1f8; padding: 2px 8px; border-radius: 6px;
  color: #0b63ce; font-family: Consolas, monospace; font-size: 13px;
}
</style>
