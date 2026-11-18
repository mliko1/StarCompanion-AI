import axios from 'axios'

const http = axios.create({ baseURL: '', timeout: 10000 })

export default {
  // 基础
  status: () => http.get('/api/status'),
  tasks: () => http.get('/api/tasks'),
  scenes: () => http.get('/api/scenes'),
  children: () => http.get('/api/children'),
  plan: () => http.get('/api/plan'),
  // 训练控制
  startTraining: (payload) => http.post('/api/training/start', payload),
  pauseTraining: () => http.post('/api/training/pause'),
  resumeTraining: () => http.post('/api/training/resume'),
  stopTraining: () => http.post('/api/training/stop'),
  trainingStatus: () => http.get('/api/training/status'),
  // 摄像头
  cameraStatus: () => http.get('/api/camera/status'),
  // 报告
  dashboard: () => http.get('/api/reports/dashboard'),
  sessions: (limit = 20) => http.get('/api/reports/sessions', { params: { limit } }),
  vision: (pendingOnly = false) =>
    http.get('/api/reports/vision', { params: { pending_only: pendingOnly } }),
  submitReview: (payload) => http.post('/api/reports/review', payload),
}
