<template>
  <div class="app">
 <video class="bg-video" autoplay muted loop playsinline poster="/videos/snow-night-poster.jpg">
  <source src="/videos/snow-night.mp4" type="video/mp4" />
</video>
 
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
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(24px) saturate(150%);
  -webkit-backdrop-filter: blur(24px) saturate(150%);
  border-right: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow: 0 0 40px rgba(80, 90, 140, 0.08);
  padding: 24px 16px; z-index: 10;
  display: flex; flex-direction: column;
}
.brand { display: flex; align-items: center; gap: 10px; padding: 0 8px 28px; }
.brand-logo {
  width: 34px; height: 34px; border-radius: 10px;
  background: var(--primary-grad); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; box-shadow: 0 6px 16px rgba(101, 110, 200, 0.28);
}
.brand-text { font-size: 21px; font-weight: 700; color: #2b2f4a; letter-spacing: 0.5px; }
.brand-text em { font-style: normal; background: var(--primary-grad); -webkit-background-clip: text; background-clip: text; color: transparent; }
.nav { display: flex; flex-direction: column; gap: 6px; flex: 1; }
.nav-item {
  display: flex; align-items: center; gap: 12px;
  padding: 13px 16px; border-radius: 12px;
  color: rgba(43, 47, 74, 0.82); text-decoration: none;
  font-size: 15px; transition: all 0.18s ease;
}
.nav-item:hover { background: rgba(255, 255, 255, 0.55); color: #2b2f4a; }
.nav-item.active {
  background: rgba(255, 255, 255, 0.88); color: #4a4f86; font-weight: 600;
  box-shadow: 0 4px 16px rgba(90, 100, 170, 0.16);
}
.icon { font-size: 19px; width: 24px; text-align: center; }
.sidebar-foot { color: rgba(43, 47, 74, 0.55); font-size: 12px; text-align: center; padding-top: 12px; }

/* ---------- 内容区 ---------- */
.content { margin-left: 224px; padding: 28px; min-height: 100vh; }
.page-title { font-size: 24px; font-weight: 700; margin-bottom: 20px; color: #fff; text-shadow: 0 1px 10px rgba(20, 24, 60, 0.35); }
.block { margin-bottom: 18px; }

/* ---------- Element Plus 卡片统一美化 ---------- */
.el-card {
  border-radius: var(--card-radius) !important;
  border: 1px solid rgba(255, 255, 255, 0.55) !important;
  background: rgba(255, 255, 255, 0.86) !important;
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  box-shadow: 0 8px 28px rgba(60, 70, 130, 0.08) !important;
}
.el-card__header {
  background: transparent !important;
  border-bottom: 1px solid rgba(120, 130, 180, 0.12) !important;
  font-weight: 600; color: var(--text);
}

/* ---------- 统计卡片 ---------- */
.stat-card { position: relative; overflow: hidden; border-radius: var(--card-radius) !important; }
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

/* ---------- 表格统一美化 ---------- */
.el-table {
  font-size: 14px; color: #3a4055; border-radius: 12px; overflow: hidden;
  background: transparent !important;
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: transparent;
  --el-table-row-hover-bg-color: rgba(255, 255, 255, 0.5);
}
.el-table th.el-table__cell {
  background: rgba(255, 255, 255, 0.55) !important;
  color: #4a5270 !important;
  font-weight: 600;
  height: 46px;
}
.el-table tr, .el-table td.el-table__cell { background: transparent !important; }
.el-table td.el-table__cell { padding: 13px 0; }
.el-table__body tr:hover > td.el-table__cell { background: rgba(255, 255, 255, 0.5) !important; }
.el-table::before { display: none; }

/* ---------- 动态背景 ---------- */
.bg-video {
  position: fixed; inset: 0;
  width: 100%; height: 100%;
  object-fit: cover;
  z-index: 0;
}
.content { position: relative; z-index: 1; }

@media (prefers-reduced-motion: reduce) {
  .bg-video { display: none; }
}

</style>
