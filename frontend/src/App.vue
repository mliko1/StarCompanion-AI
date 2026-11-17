<template>
  <div class="app">
    <aside class="sidebar">
      <div class="brand">星伴<span>AI</span></div>
      <nav class="nav">
        <router-link v-for="item in menus" :key="item.path" :to="item.path"
                     class="nav-item" :class="{ active: $route.path === item.path }">
          <span class="icon">{{ item.icon }}</span><span>{{ item.title }}</span>
        </router-link>
      </nav>
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
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Segoe UI", "Microsoft YaHei", system-ui, sans-serif; background: #f5f7fa; color: #333; }
.app { min-height: 100vh; }
.sidebar { position: fixed; left: 0; top: 0; bottom: 0; width: 200px; background: #fff; border-right: 1px solid #eee; padding: 20px 12px; z-index: 10; }
.brand { font-size: 20px; font-weight: 700; padding: 0 12px 24px; }
.brand span { color: #409eff; }
.nav { display: flex; flex-direction: column; gap: 4px; }
.nav-item { display: flex; align-items: center; gap: 10px; padding: 12px 14px; border-radius: 10px; color: #555; text-decoration: none; font-size: 14px; }
.nav-item:hover { background: #f0f5ff; }
.nav-item.active { background: #e6f0ff; color: #409eff; font-weight: 600; }
.icon { font-size: 18px; }
.content { margin-left: 200px; padding: 24px; min-height: 100vh; }
.page-title { font-size: 20px; margin-bottom: 16px; }
.block { margin-bottom: 16px; }
.tabbar { display: none; }

@media (max-width: 768px) {
  .sidebar { display: none; }
  .content { margin-left: 0; padding: 16px 16px 72px; }
  .tabbar { display: flex; position: fixed; left: 0; right: 0; bottom: 0; background: #fff; border-top: 1px solid #eee; z-index: 10; }
  .tab-item { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 8px 0; color: #999; text-decoration: none; font-size: 11px; }
  .tab-item .icon { font-size: 20px; }
  .tab-item.active { color: #409eff; }
}
</style>
