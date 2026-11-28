import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import Training from './views/Training.vue'
import Reports from './views/Reports.vue'
import Review from './views/Review.vue'
import Settings from './views/Settings.vue'
import Calibration from './views/Calibration.vue'
import TrainingScreen from './views/TrainingScreen.vue'
import Login from './views/Login.vue'
import { isLoggedIn } from './auth'

const routes = [
  { path: '/login', component: Login, meta: { title: '登录', public: true } },
  { path: '/', component: Dashboard, meta: { title: '首页' } },
  { path: '/training', component: Training, meta: { title: '训练操作' } },
  { path: '/training-screen', component: TrainingScreen, meta: { title: '训练大屏' } },
  { path: '/reports', component: Reports, meta: { title: '训练报告' } },
  { path: '/review', component: Review, meta: { title: '人工确认' } },
  { path: '/settings', component: Settings, meta: { title: '档案与设置' } },
  { path: '/calibration', component: Calibration, meta: { title: '家庭校准' } },
]

// hash 模式：后端静态挂载无需额外的路由回退配置
const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// 以服务端会话为准：后端重启后 Cookie 失效，打开系统第一件事就是登录
router.beforeEach(async (to) => {
  const logged = await isLoggedIn()
  if (!to.meta.public && !logged) return { path: '/login' }
  if (to.path === '/login' && logged) return { path: '/' }
  return true
})

export default router
