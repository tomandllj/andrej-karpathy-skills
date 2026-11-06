import http from './http'

const TOKEN_KEY = 'admin_token'
const LOGIN_PATH_KEY = 'admin_login_path'
const LAST_USER_KEY = 'admin_last_username'

/** 读取本地保存的管理员会话 token。 */
export function getAdminToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

/** 写入管理员会话 token。 */
export function setAdminToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

/** 清除管理员会话 token。 */
export function clearAdminToken() {
  localStorage.removeItem(TOKEN_KEY)
}

/** 记住本次有效的登录路径，退出时用它回到登录页。 */
export function rememberLoginPath(path) {
  const value = String(path || '').trim()
  if (value.startsWith('/') && value.length > 1) {
    sessionStorage.setItem(LOGIN_PATH_KEY, value)
  }
}

/** 读取上次记住的登录路径。 */
export function getLoginPath() {
  return sessionStorage.getItem(LOGIN_PATH_KEY) || ''
}

/** 记住上次成功登录的账号（不存密码）。 */
export function rememberLastUsername(name) {
  const value = String(name || '').trim()
  if (value) localStorage.setItem(LAST_USER_KEY, value)
}

/** 读取上次成功登录的账号。 */
export function getLastUsername() {
  return localStorage.getItem(LAST_USER_KEY) || ''
}

/**
 * 核对当前路径是否为 config.ini 中的登录入口（不返回真实路径）。
 * @param {string} path 当前浏览器 pathname
 */
export function adminGate(path) {
  return http.post('/api/admin/gate', { path })
}

/** 确认当前管理员 token 是否仍有效。 */
export function adminMe() {
  const token = getAdminToken()
  return http.get('/api/admin/me', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
}
