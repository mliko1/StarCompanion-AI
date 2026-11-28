// 真实账号体系：密码只存服务端哈希，浏览器只保留用户名与 HttpOnly Cookie 会话
import { http } from './api'

const USER_KEY = 'xb_user'

function msg(e, fallback) {
  return (e.response && e.response.data && e.response.data.detail) || fallback
}

export async function login(username, password) {
  try {
    const { data } = await http.post('/api/auth/login', { username, password })
    localStorage.setItem(USER_KEY, data.user)
    return { ok: true, user: data.user }
  } catch (e) {
    return { ok: false, msg: msg(e, '登录失败，请稍后再试') }
  }
}

export async function register(username, password) {
  try {
    const { data } = await http.post('/api/auth/register', { username, password })
    return { ok: true, msg: data.msg }
  } catch (e) {
    return { ok: false, msg: msg(e, '注册失败，请稍后再试') }
  }
}

export async function logout() {
  try {
    await http.post('/api/auth/logout')
  } catch (e) {
    // 即使请求失败也清除本地状态
  }
  localStorage.removeItem(USER_KEY)
}

export async function changePassword(oldPassword, newPassword) {
  try {
    const { data } = await http.post('/api/auth/change-password', {
      old_password: oldPassword, new_password: newPassword,
    })
    localStorage.removeItem(USER_KEY)
    return { ok: true, msg: data.msg }
  } catch (e) {
    return { ok: false, msg: msg(e, '修改失败，请稍后再试') }
  }
}

export async function isLoggedIn() {
  try {
    const { data } = await http.get('/api/auth/me')
    if (data.authenticated) localStorage.setItem(USER_KEY, data.user)
    else localStorage.removeItem(USER_KEY)
    return !!data.authenticated
  } catch (e) {
    return false
  }
}

export function currentUser() {
  return localStorage.getItem(USER_KEY) || ''
}
