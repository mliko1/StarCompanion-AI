import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import Training from './views/Training.vue'
import Reports from './views/Reports.vue'
import Review from './views/Review.vue'
import Settings from './views/Settings.vue'

const routes = [
  { path: '/', component: Dashboard, meta: { title: '首页' } },
  { path: '/training', component: Training, meta: { title: '训练操作' } },
  { path: '/reports', component: Reports, meta: { title: '训练报告' } },
  { path: '/review', component: Review, meta: { title: '人工确认' } },
  { path: '/settings', component: Settings, meta: { title: '档案与设置' } },
]

// hash 模式：后端静态挂载无需额外的路由回退配置
export default createRouter({
  history: createWebHashHistory(),
  routes,
})
