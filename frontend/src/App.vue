<template>
  <div class="app">
    <aside v-if="!isLogin && !isScreen" class="sidebar">
      <div class="brand">
        <span class="brand-text">星伴<em>AI</em></span>
      </div>
      <nav class="nav">
        <router-link v-for="item in menus" :key="item.path" :to="item.path"
                     class="nav-item" :class="{ active: $route.path === item.path }">
          <span class="icon"><LineIcon :name="item.icon" /></span><span>{{ item.title }}</span>
        </router-link>
      </nav>
      <div class="sidebar-foot">
        <div class="user-line">
          <span class="user-name">{{ user || '未登录' }}</span>
          <el-button link type="primary" @click="onLogout">退出登录</el-button>
        </div>
        <div class="foot-tip">家庭康复训练辅助</div>
      </div>
    </aside>

    <main class="content" :class="{ 'content-full': isLogin || isScreen }">
      <router-view />
    </main>

    <nav v-if="!isLogin && !isScreen" class="tabbar">
      <router-link v-for="item in menus" :key="item.path" :to="item.path"
                   class="tab-item" :class="{ active: $route.path === item.path }">
        <span class="icon"><LineIcon :name="item.icon" /></span><span>{{ item.title }}</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LineIcon from './components/LineIcon.vue'
import { currentUser, logout } from './auth'

const user = ref(currentUser())
const router = useRouter()

async function onLogout() {
  await logout()
  user.value = ''
  router.replace('/login')
}

watch(() => route.path, () => { user.value = currentUser() })

const menus = [
  { path: '/', title: '首页', icon: 'home' },
  { path: '/training', title: '训练', icon: 'training' },
  { path: '/calibration', title: '校准', icon: 'calibrate' },
  { path: '/reports', title: '报告', icon: 'reports' },
  { path: '/review', title: '确认', icon: 'review' },
  { path: '/settings', title: '设置', icon: 'settings' },
]

const route = useRoute()
const isLogin = computed(() => route.path === '/login')
const isScreen = computed(() => route.path === '/training-screen')
</script>

<style>
/* ============ 全局设计系统 ============ */
:root {
  --primary: #0b63ce;
  --primary-2: #4a90e8;
  --primary-grad: linear-gradient(to bottom left, #0b63ce 0%, #4a90e8 100%);
  --bg: #f3f7fc;
  --surface: #ffffff;
  --text: #26374d;
  --muted: #7b8aa0;
  --line: rgba(17, 32, 56, 0.06);
  --card-radius: 16px;
  --shadow-soft: 0 2px 10px rgba(31, 54, 90, 0.05);

  /* Element Plus 主色（按钮、标签、选中态统一成蓝色） */
  --el-color-primary: #0b63ce;
  --el-color-primary-light-3: #4a90e8;
  --el-color-primary-light-5: #7fb0f0;
  --el-color-primary-light-7: #b3d0f7;
  --el-color-primary-light-8: #cfe0fa;
  --el-color-primary-light-9: #eef5fe;
  --el-color-primary-dark-2: #0a58ba;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; }
body {
  font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}
.app { min-height: 100vh; background: var(--bg); }

/* ---------- 侧边栏 ---------- */
.sidebar {
  position: fixed; left: 0; top: 0; bottom: 0; width: 224px;
  background: #f7f9fc;
  border-right: 1px solid #eaeff7;
  padding: 22px 14px; z-index: 10;
  display: flex; flex-direction: column;
}
.brand { padding: 2px 10px 30px; }
.brand-text {
  font-size: 21px; font-weight: 600; color: #0f172a;
  letter-spacing: 4px;
}
.brand-text em {
  font-style: normal; font-size: 11px; font-weight: 600;
  color: #8b93a5; letter-spacing: 1px;
  margin-left: 6px; vertical-align: 2px;
}
.nav { display: flex; flex-direction: column; gap: 6px; flex: 1; }
.nav-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 12px; border-radius: 10px;
  color: #344054; text-decoration: none;
  font-size: 14px;
  transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease;
  border: 1px solid transparent;
}
.nav-item .icon { color: #7c8ca6; transition: color 0.18s ease; }
.nav-item:hover { background: #eef2f8; color: #0f172a; }
.nav-item:hover .icon { color: #475467; }
.nav-item.active {
  background: #ffffff; color: #0f172a; font-weight: 600;
  border-color: #e6edf6;
}
.nav-item.active .icon { color: var(--primary); }
.icon { width: 24px; display: flex; align-items: center; justify-content: center; }
.sidebar-foot { color: #8296ae; font-size: 12px; text-align: center; padding-top: 12px; }
.user-line {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 10px; margin-bottom: 8px;
  background: #eef2f8; border-radius: 8px;
}
.user-name { color: #344054; font-weight: 600; max-width: 110px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.user-line .el-button { font-size: 12px; padding: 0; }
.foot-tip { color: #8296ae; }

/* ---------- 内容区 ---------- */
.content { margin-left: 224px; padding: 40px 48px 56px; min-height: 100vh; position: relative; }
.content:not(.content-full) > div { max-width: 1120px; margin: 0 auto; }
.page-title { font-size: 28px; font-weight: 600; margin-bottom: 24px; color: #0f172a; letter-spacing: -0.4px; }
.block { margin-bottom: 18px; }

/* ---------- Element Plus 卡片统一美化 ---------- */
.el-card {
  border-radius: 14px !important;
  border: 1px solid #e6edf6 !important;
  background: var(--surface) !important;
  box-shadow: none !important;
}
.el-card__header {
  background: transparent !important;
  border-bottom: 1px solid var(--line) !important;
  font-weight: 600; color: #344054; font-size: 15px;
}

/* ---------- 统计卡片 ---------- */
.stat-card {
  border-radius: 14px !important;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}
.stat-card:hover {
  transform: translateY(-2px);
  border-color: #d7e3f3 !important;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05) !important;
}
.stat-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.stat-ico { width: 16px; height: 16px; color: #b0b8c7; }
.stat-label { color: #8b93a5; font-size: 13px; }
.stat-value {
  font-size: 30px; font-weight: 600; color: #1f2430; margin-top: 10px;
  letter-spacing: -0.6px; font-variant-numeric: tabular-nums;
}

/* ---------- 通用 ---------- */
.muted { color: #93a1b5; font-size: 13px; text-align: center; padding: 20px; }

/* ---------- 移动端底部导航 ---------- */
.tabbar { display: none; }

@media (max-width: 768px) {
  .sidebar { display: none; }
  .content { margin-left: 0; padding: 16px 16px 76px; }
  .page-title { font-size: 20px; }
  .tabbar {
    display: flex; position: fixed; left: 0; right: 0; bottom: 0;
    background: #fff; border-top: 1px solid #eef0f6;
    box-shadow: 0 -4px 16px rgba(40, 60, 130, 0.06); z-index: 10;
  }
  .tab-item {
    flex: 1; display: flex; flex-direction: column; align-items: center;
    gap: 3px; padding: 9px 0; color: #9aa1b3; text-decoration: none; font-size: 11px;
  }
  .tab-item .icon { color: #98a1b3; }
  .tab-item .line-ico { width: 20px; height: 20px; }
  .tab-item.active { color: var(--primary); font-weight: 600; }
  .tab-item.active .icon { color: var(--primary); }
}

/* ---------- 表格统一美化 ---------- */
.el-table {
  font-size: 14px; color: #3f4d63; border-radius: 12px; overflow: hidden;
  background: transparent !important;
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: #f6f9fd;
  --el-table-row-hover-bg-color: #f7fafe;
  --el-table-border-color: rgba(17, 32, 56, 0.05);
}
.el-table th.el-table__cell {
  background: #f6f9fd !important;
  color: #6b7a8f !important;
  font-weight: 600;
  font-size: 13px;
  height: 44px;
}
.el-table tr, .el-table td.el-table__cell { background: transparent !important; }
.el-table td.el-table__cell { padding: 12px 0; border-bottom: 1px solid rgba(17, 32, 56, 0.05); }
.el-table__body tr:hover > td.el-table__cell { background: #f7fafe !important; }
.el-table::before { display: none; }

/* ---------- 表单控件 ---------- */
.el-input__wrapper,
.el-textarea__inner,
.el-select__wrapper {
  border-radius: 10px !important;
  box-shadow: 0 0 0 1px #dfe8f3 inset !important;
  transition: box-shadow 0.18s ease;
}
.el-input__wrapper.is-focus,
.el-select__wrapper.is-focused {
  box-shadow: 0 0 0 1px var(--primary) inset !important;
}
.el-button { border-radius: 8px; border-color: #dce5f0; }
.el-button:hover { border-color: #c8d7ea; }

/* ---------- 标签：低饱和 ---------- */
.el-tag { border: none !important; border-radius: 6px; font-weight: 500; }
.el-tag--success { background: #e3f4ea !important; color: #227a4b !important; }
.el-tag--danger { background: #fdeae8 !important; color: #bf4238 !important; }
.el-tag--warning { background: #fdf1dd !important; color: #9a6a1f !important; }
.el-tag--info { background: #f1f4f8 !important; color: #6b7a8f !important; }
.el-tag--primary { background: #eaf2fd !important; color: #0b63ce !important; }

/* ---------- 纯色背景 ---------- */
.content-full { margin-left: 0 !important; padding: 0 !important; }

</style>
