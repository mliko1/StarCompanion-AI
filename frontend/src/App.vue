<template>
  <div class="app">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-logo">★</span>
        <span class="brand-text">星伴<em>AI</em></span>
      </div>
      <nav class="nav">
        <router-link v-for="item in menus" :key="item.path" :to="item.path"
                     class="nav-item" :class="{ active: $route.path === item.path }">
          <span class="icon">{{ item.icon }}</span><span>{{ item.title }}</span>
        </router-link>
      </nav>
      <div class="sidebar-foot">家庭康复训练辅助</div>
    </aside>

    <main class="content">
      <router-view />
    </main>

    <nav class="tabbar">
      <router-link v-for="item in menus" :key="item.path" :to="item.path"
                   class="tab-item" :class="{ active: $route.path === item.path }">
        <span class="icon">{{ item.icon }}</span><span>{{ item.title }}</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
const menus = [
  { path: '/', title: '首页', icon: '🏠' },
  { path: '/training', title: '训练', icon: '🎯' },
  { path: '/reports', title: '报告', icon: '📊' },
  { path: '/review', title: '确认', icon: '✅' },
  { path: '/settings', title: '设置', icon: '⚙️' },
]
</script>

<style>
/* ============ 全局设计系统 ============ */
:root {
  --primary: #5b7cfa;
  --primary-2: #8b5cf6;
  --primary-grad: linear-gradient(135deg, #5b7cfa 0%, #8b5cf6 100%);
  --bg: #f4f6fb;
  --text: #2b2f3e;
  --muted: #8a91a6;
  --card-radius: 16px;
  --shadow: 0 6px 24px rgba(40, 60, 130, 0.08);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; }
body {
  font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}
.app { min-height: 100vh; }

/* ---------- 侧边栏 ---------- */
.sidebar {
  position: fixed; left: 0; top: 0; bottom: 0; width: 224px;
  background: linear-gradient(180deg, #1d2140 0%, #2b2f5e 100%);
  padding: 24px 16px; z-index: 10;
  display: flex; flex-direction: column;
}
.brand { display: flex; align-items: center; gap: 10px; padding: 0 8px 28px; }
.brand-logo {
  width: 34px; height: 34px; border-radius: 10px;
  background: var(--primary-grad); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; box-shadow: 0 4px 14px rgba(91, 124, 250, 0.5);
}
.brand-text { font-size: 21px; font-weight: 700; color: #fff; letter-spacing: 0.5px; }
.brand-text em { font-style: normal; background: var(--primary-grad); -webkit-background-clip: text; background-clip: text; color: transparent; }
.nav { display: flex; flex-direction: column; gap: 6px; flex: 1; }
.nav-item {
  display: flex; align-items: center; gap: 12px;
  padding: 13px 16px; border-radius: 12px;
  color: rgba(255, 255, 255, 0.62); text-decoration: none;
  font-size: 15px; transition: all 0.18s ease;
}
.nav-item:hover { background: rgba(255, 255, 255, 0.07); color: #fff; }
.nav-item.active {
  background: var(--primary-grad); color: #fff; font-weight: 600;
  box-shadow: 0 6px 18px rgba(91, 124, 250, 0.45);
}
.icon { font-size: 19px; width: 24px; text-align: center; }
.sidebar-foot { color: rgba(255, 255, 255, 0.3); font-size: 12px; text-align: center; padding-top: 12px; }

/* ---------- 内容区 ---------- */
.content { margin-left: 224px; padding: 28px; min-height: 100vh; }
.page-title { font-size: 24px; font-weight: 700; margin-bottom: 20px; color: var(--text); }
.block { margin-bottom: 18px; }

/* ---------- Element Plus 卡片统一美化 ---------- */
.el-card {
  border-radius: var(--card-radius) !important;
  border: none !important;
  box-shadow: var(--shadow) !important;
}
.el-card__header { border-bottom: 1px solid #eef0f6 !important; font-weight: 600; color: var(--text); }

/* ---------- 统计卡片 ---------- */
.stat-card { position: relative; overflow: hidden; border-radius: var(--card-radius) !important; }
.stat-card::after {
  content: ''; position: absolute; right: -28px; top: -28px;
  width: 96px; height: 96px; border-radius: 50%;
  background: var(--card-tint, rgba(91, 124, 250, 0.08));
}
.stat-icon {
  width: 42px; height: 42px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; margin-bottom: 10px;
  background: var(--card-tint, rgba(91, 124, 250, 0.12));
}
.stat-label { color: var(--muted); font-size: 13px; }
.stat-value { font-size: 30px; font-weight: 700; margin-top: 4px; letter-spacing: -0.5px; }

/* ---------- 通用 ---------- */
.muted { color: #b6bccd; font-size: 13px; text-align: center; padding: 20px; }

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
  .tab-item .icon { font-size: 21px; }
  .tab-item.active { color: var(--primary); font-weight: 600; }
}
</style>
