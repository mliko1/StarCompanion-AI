<template>
  <div class="login">
    <div class="login-inner">
      <div class="login-card">
        <h1 class="name">星伴<em>AI</em></h1>
        <p class="sub">家庭康复训练辅助</p>

        <template v-if="mode === 'login'">
          <div class="field">
            <el-input v-model="form.username" size="large" placeholder="用户名" />
          </div>
          <div class="field">
            <el-input v-model="form.password" size="large" type="password" show-password placeholder="密码" @keyup.enter="submit" />
          </div>
          <el-button class="btn-main" @click="submit">登 录</el-button>
          <div class="links">
            <span @click="mode = 'register'">注册新账号</span>
            <span class="muted-link" @click="forgot">忘记密码？</span>
          </div>
          <div class="demo" @click="demoLogin">演示账号一键登录（demo / 123456）</div>
        </template>

        <template v-else>
          <div class="field">
            <el-input v-model="form.username" size="large" placeholder="设置用户名" />
          </div>
          <div class="field">
            <el-input v-model="form.password" size="large" type="password" show-password placeholder="设置密码（至少 6 位）" />
          </div>
          <div class="field">
            <el-input v-model="form.confirm" size="large" type="password" show-password placeholder="再次输入密码" @keyup.enter="submit" />
          </div>
          <el-button class="btn-main" @click="submit">注 册</el-button>
          <div class="links">
            <span @click="backToLogin">返回登录</span>
          </div>
        </template>

        <p class="agreement">登录即代表同意《用户协议》与《隐私政策》</p>
      </div>

      <p class="warm">慢一点也没关系，我们陪着你。</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ensureDemoUser, login, register, isLoggedIn } from '../auth'

const router = useRouter()
const mode = ref('login')
const form = ref({ username: '', password: '', confirm: '' })

onMounted(() => {
  ensureDemoUser()
  if (isLoggedIn()) router.replace('/')
})

function backToLogin() {
  mode.value = 'login'
  form.value.password = ''
  form.value.confirm = ''
}

function forgot() {
  ElMessage.info('演示版暂不支持找回密码，请使用演示账号或重新注册')
}

function submit() {
  const { username, password, confirm } = form.value
  if (!username.trim()) return ElMessage.warning('请输入用户名')
  if (!password) return ElMessage.warning('请输入密码')

  if (mode.value === 'register') {
    if (password !== confirm) return ElMessage.warning('两次输入的密码不一致')
    const r = register(username, password)
    if (!r.ok) return ElMessage.error(r.msg)
    ElMessage.success('注册成功，请登录')
    mode.value = 'login'
    form.value.password = ''
    form.value.confirm = ''
    return
  }

  const r = login(username, password)
  if (!r.ok) return ElMessage.error(r.msg)
  ElMessage.success('欢迎回来')
  router.replace('/')
}

function demoLogin() {
  const r = login('demo', '123456')
  if (!r.ok) return ElMessage.error(r.msg)
  router.replace('/')
}
</script>

<style scoped>
.login {
  position: fixed; inset: 0; overflow: auto;
  background: #f3f7fc;
}
.login-inner {
  min-height: 100vh; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 32px 16px;
}

.login-card {
  width: min(380px, 92vw);
  background: #ffffff;
  border: 1px solid #e6edf6;
  border-radius: 16px;
  padding: 40px 34px 26px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
  text-align: center;
}
.name {
  font-size: 22px; font-weight: 600; color: #0f172a;
  letter-spacing: 3px; margin: 0;
}
.name em {
  font-style: normal; font-size: 11px; font-weight: 600;
  color: #8b93a5; letter-spacing: 1px;
  margin-left: 6px; vertical-align: 2px;
}
.sub { font-size: 13px; color: #8b93a5; margin: 10px 0 28px; letter-spacing: 0.5px; }

.field { margin-bottom: 12px; text-align: left; }
.field :deep(.el-input__wrapper) {
  background: #ffffff; box-shadow: 0 0 0 1px #d2d2d7 inset;
  border-radius: 12px; padding: 0 14px; height: 48px;
}
.field :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #0b63ce inset, 0 0 0 4px rgba(11, 99, 206, 0.16);
}
.field :deep(.el-input__inner) { font-size: 15px; color: #1d1d1f; }
.field :deep(.el-input__inner::placeholder) { color: #86868b; }

.btn-main {
  width: 100%; height: 48px; margin-top: 8px;
  border: none; border-radius: 12px;
  background: linear-gradient(to bottom left, #0b63ce 0%, #4a90e8 100%);
  color: #ffffff; font-size: 15px; font-weight: 500; letter-spacing: 0.5px;
}
.btn-main:hover { background: linear-gradient(to bottom left, #0a58ba 0%, #3f83d8 100%); color: #ffffff; }

.links {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 16px; font-size: 13px;
}
.links span {
  color: #0b63ce; cursor: pointer;
  text-decoration: none !important;
  border-bottom: 0 !important;
}
.links span:hover { opacity: 0.8; }
.links .muted-link { color: #86868b; }
.demo { margin-top: 16px; font-size: 12.5px; color: #86868b; cursor: pointer; }
.demo:hover { color: #0b63ce; }

.agreement { margin-top: 20px; font-size: 11px; color: #86868b; line-height: 1.6; }
.warm {
  color: #93a1b5; font-size: 12px; letter-spacing: 1.5px;
  margin-top: 22px;
}
</style>
