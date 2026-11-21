// 演示版账号系统：账号只保存在浏览器 localStorage，不涉及后端与真实加密
const USERS_KEY = 'xb_users'
const SESSION_KEY = 'xb_session'

function readUsers() {
  try {
    return JSON.parse(localStorage.getItem(USERS_KEY)) || []
  } catch (e) {
    return []
  }
}

function writeUsers(users) {
  localStorage.setItem(USERS_KEY, JSON.stringify(users))
}

// 首次打开时写入演示账号 demo / 123456
export function ensureDemoUser() {
  const users = readUsers()
  if (!users.some(u => u.username === 'demo')) {
    users.push({ username: 'demo', password: '123456' })
    writeUsers(users)
  }
}

export function register(username, password) {
  const name = (username || '').trim()
  if (name.length < 2) return { ok: false, msg: '用户名至少 2 个字符' }
  if ((password || '').length < 6) return { ok: false, msg: '密码至少 6 位' }
  const users = readUsers()
  if (users.some(u => u.username === name)) return { ok: false, msg: '该用户名已被注册' }
  users.push({ username: name, password })
  writeUsers(users)
  return { ok: true }
}

export function login(username, password) {
  const name = (username || '').trim()
  const user = readUsers().find(u => u.username === name && u.password === password)
  if (!user) return { ok: false, msg: '用户名或密码不正确' }
  localStorage.setItem(SESSION_KEY, name)
  return { ok: true }
}

export function logout() {
  localStorage.removeItem(SESSION_KEY)
}

export function isLoggedIn() {
  return !!localStorage.getItem(SESSION_KEY)
}

export function currentUser() {
  return localStorage.getItem(SESSION_KEY) || ''
}
