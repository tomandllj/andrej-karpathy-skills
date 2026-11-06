import http from './http'

/**
 * 公开注册：账号至少 3 位、密码 6 位，都只能是英文和数字。
 * @param {{ username: string, password: string }} body
 */
export function register(body) {
  return http.post('/api/auth/register', body).then((r) => r.data)
}

/**
 * 统一登录：管理员按账号名自动识别（须带当前页面路径）；返回 { token, expires_in, username }。
 * @param {{ username: string, password: string, path?: string }} body
 */
export function login(body) {
  return http.post('/api/auth/login', body).then((r) => r.data)
}

/**
 * 公开拿登录入口路径（config.ini 的 login_path）；未登录跳转和退出回跳都用它。
 * @returns {Promise<{ login_path: string }>}
 */
export function getEntry() {
  return http.get('/api/entry').then((r) => r.data)
}
