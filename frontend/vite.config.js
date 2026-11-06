import { readFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

/** 优先读根目录 .dev-port（run.py 写入），没有时再用环境变量 BACKEND_PORT。 */
function resolveBackendPort() {
  try {
    const raw = readFileSync(fileURLToPath(new URL('../.dev-port', import.meta.url)), 'utf8').trim()
    if (/^\d+$/.test(raw)) return raw
  } catch {
    /* 没有端口文件时走环境变量 */
  }
  return process.env.BACKEND_PORT || '8003'
}

const backendPort = resolveBackendPort()
const frontendPort = Number(process.env.FRONTEND_PORT || 5173)

/** 仅开发服务器读取 ini 账号密码；vite build 固定为空，避免打进发布包。 */
function readDevAdminCredentials(isServe) {
  if (!isServe) return { username: '', password: '' }
  try {
    const text = readFileSync(fileURLToPath(new URL('../config.ini', import.meta.url)), 'utf8')
    const section = (text.split(/\[admin\]/i)[1] || '').split(/\n\s*\[/)[0]
    const pick = (key) => {
      const matched = section.match(new RegExp(`^\\s*${key}\\s*=\\s*(.*)$`, 'm'))
      return matched ? matched[1].trim() : ''
    }
    return { username: pick('username'), password: pick('password') }
  } catch {
    return { username: '', password: '' }
  }
}

export default defineConfig(({ command }) => {
  const devAdmin = readDevAdminCredentials(command === 'serve')
  return {
  define: {
    'import.meta.env.VITE_DEV_ADMIN_USERNAME': JSON.stringify(devAdmin.username),
    'import.meta.env.VITE_DEV_ADMIN_PASSWORD': JSON.stringify(devAdmin.password),
  },
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: frontendPort,
    fs: {
      allow: [fileURLToPath(new URL('..', import.meta.url))],
    },
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      },
      '/ws': {
        target: `ws://127.0.0.1:${backendPort}`,
        ws: true,
        changeOrigin: true,
      },
    },
  },
  }
})
