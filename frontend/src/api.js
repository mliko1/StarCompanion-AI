import axios from 'axios'

const http = axios.create({ baseURL: '', timeout: 10000 })

export default {
  // 基础
  status: () => http.get('/api/status'),
  tasks: () => http.get('/api/tasks'),
  scenes: () => http.get('/api/scenes'),
  children: () => http.get('/api/children'),
  createChild: (payload) => http.post('/api/children', payload),
  updateChild: (id, payload) => http.put(`/api/children/${id}`, payload),
  deleteChild: (id) => http.delete(`/api/children/${id}`),
  plan: () => http.get('/api/plan'),
  // 训练控制
  startTraining: (payload) => http.post('/api/training/start', payload),
  pauseTraining: () => http.post('/api/training/pause'),
  resumeTraining: () => http.post('/api/training/resume'),
  stopTraining: () => http.post('/api/training/stop'),
  trainingStatus: () => http.get('/api/training/status'),
  // 摄像头
  cameraStatus: () => http.get('/api/camera/status'),
  startCamera: () => http.post('/api/camera/start'),
  // 报告
  dashboard: (childId) => http.get('/api/reports/dashboard', { params: { child_id: childId } }),
  sessions: (limit = 20) => http.get('/api/reports/sessions', { params: { limit } }),
  sessionReport: (sessionId) => http.get(`/api/reports/session/${sessionId}`),
  professionalReport: (sessionId) => http.get(`/api/reports/professional/${sessionId}`),
  latestSession: () => http.get('/api/reports/latest_session'),
  reportHistory: (params) => http.get('/api/reports/history', { params }),
  savedReport: (reportId) => http.get(`/api/reports/saved/${reportId}`),
  vision: (pendingOnly = false) =>
    http.get('/api/reports/vision', { params: { pending_only: pendingOnly } }),
  submitReview: (payload) => http.post('/api/reports/review', payload),
  // 个体化适应
  personalProfiles: (childId) =>
    http.get('/api/personalization/profiles', { params: { child_id: childId } }),
  confirmHand: (payload) => http.post('/api/personalization/confirm_hand', payload),
  // 家庭校准（镜头前自动采集 + 自动训练到收敛）
  calibrationModels: () => http.get('/api/calibration/models'),
  calibrationStatus: () => http.get('/api/calibration/status'),
  startCalibration: (payload) => http.post('/api/calibration/collect/start', payload),
  finishCalibration: () => http.post('/api/calibration/finish'),
  stopCalibration: () => http.post('/api/calibration/stop'),
}
