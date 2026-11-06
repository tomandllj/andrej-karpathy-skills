<template>
  <!-- 中文：校验路径中 -->
  <div v-if="checking" class="gate-page" aria-busy="true">
    <p class="gate-hint">加载中…</p>
  </div>

  <!-- 中文：校验接口本身失败（例如后端还是旧进程） -->
  <div v-else-if="gateError" class="gate-page">
    <h1 class="gate-title">暂时无法打开</h1>
    <p class="gate-hint">{{ gateError }}</p>
  </div>

  <!-- 中文：路径与 config.ini 不一致时不展示登录表单 -->
  <div v-else-if="!pathAllowed" class="gate-page">
    <h1 class="gate-title">页面不存在</h1>
    <p class="gate-hint">请检查地址是否正确</p>
  </div>

  <!-- 中文：分栏登录——左文稿预览、右表单或锁定倒计时 -->
  <div v-else class="login-page">
    <aside class="preview-panel" aria-label="文稿预览">
      <div class="preview-inner">
        <div class="wordmark">
          <span class="logo" aria-hidden="true">MD</span>
          <h1 class="brand-title">文档协助</h1>
          <p class="brand-lead">Markdown 写作与评审</p>
        </div>

        <!-- 中文：一页正文，高亮句下面跟一条页边批注 -->
        <article class="sheet" aria-hidden="true">
          <header class="sheet-head">
            <p class="sheet-title">接口说明</p>
            <span class="sheet-meta">草稿</span>
          </header>
          <p class="sheet-body">
            本周把返回约定收成一页。
            <mark class="sheet-hl">返回字段以服务端为准</mark>
          </p>
          <p class="margin-note">
            <span class="note-label">批注</span>
            <span class="note-text">和上一版不一致，请核对</span>
          </p>
          <p class="sheet-body">分享给同事看这一页，需要时再回滚到上一版。</p>
        </article>
      </div>
    </aside>

    <main class="form-panel">
      <div class="form-shell" :class="{ locked: locked }">
        <!-- 中文：锁定时显示大号倒计时 -->
        <div v-if="locked" class="lock-panel" role="status" aria-live="polite">
          <div
            class="lock-ring"
            :style="{ '--p': lockProgress }"
            aria-hidden="true"
          >
            <span class="lock-seconds">{{ retryAfter }}</span>
          </div>
          <h2 class="panel-title">请稍后再试</h2>
          <p class="panel-desc">登录失败次数过多，{{ retryAfter }} 秒后可重新提交</p>
        </div>

        <!-- 中文：正常登录/注册表单，同一页切换 -->
        <template v-else>
          <header class="form-head">
            <h2 class="panel-title">{{ isRegister ? '注册账号' : '登录' }}</h2>
            <p class="panel-desc">
              {{ isRegister ? '注册后可以接收别人分享的文档，也能新建自己的文档。' : '管理员和普通账号都在这里登录。' }}
            </p>
          </header>

          <el-form class="form" @submit.prevent="onSubmit">
            <el-form-item label="账号">
              <el-input
                ref="userInputRef"
                v-model="username"
                size="large"
                autocomplete="username"
                placeholder=""
                @keyup.enter="onSubmit"
              />
            </el-form-item>
            <el-form-item label="密码">
              <el-input
                v-model="password"
                type="password"
                size="large"
                show-password
                :autocomplete="isRegister ? 'new-password' : 'current-password'"
                placeholder=""
                @keyup.enter="onSubmit"
              />
            </el-form-item>
            <el-form-item v-if="isRegister" label="确认密码">
              <el-input
                v-model="password2"
                type="password"
                size="large"
                show-password
                autocomplete="new-password"
                placeholder="再输入一次密码"
                @keyup.enter="onSubmit"
              />
            </el-form-item>

            <p v-if="errorMsg" class="err-msg" role="alert">{{ errorMsg }}</p>

            <el-button
              class="submit"
              size="large"
              :loading="loading"
              :disabled="!username.trim() || !password || (isRegister && !password2)"
              native-type="submit"
              @click="onSubmit"
            >
              {{ isRegister ? '注册并登录' : '登录' }}
            </el-button>
          </el-form>

          <p class="switch-line">
            {{ isRegister ? '已有账号？' : '还没有账号？' }}
            <a class="switch-link" href="#" @click.prevent="toggleMode">
              {{ isRegister ? '去登录' : '注册一个' }}
            </a>
          </p>
        </template>
      </div>
    </main>
  </div>
</template>

<script setup>
/** 仅当 pathname 与 config.ini login_path 一致时展示；本页同时承担登录与注册（唯一登录页）。 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login, register } from '@/api/auth'
import {
  adminGate,
  adminMe,
  getAdminToken,
  getLastUsername,
  rememberLastUsername,
  rememberLoginPath,
  setAdminToken,
} from '@/api/admin'

const route = useRoute()
const router = useRouter()

/** 正在向后端核对路径。 */
const checking = ref(true)
/** 当前 path 是否等于配置中的登录入口。 */
const pathAllowed = ref(false)
/** 校验接口失败时的说明（不是路径错误）。 */
const gateError = ref('')

const username = ref('')
const password = ref('')
/** 注册模式的确认密码。 */
const password2 = ref('')
/** 是否处于注册模式（同一页切换，不跳第二个登录页）。 */
const isRegister = ref(false)
const loading = ref(false)
const errorMsg = ref('')
const retryAfter = ref(0)
const locked = ref(false)
/** 本次锁定总秒数，用于进度环比例。 */
const lockTotal = ref(60)
const userInputRef = ref(null)

// 与后端注册一致：账号至少 3 位、密码 6 位，只能英文和数字（管理员密码不受此限制）
const USERNAME_RE = /^[A-Za-z0-9]{3,}$/
const PASSWORD_RE = /^[A-Za-z0-9]{6}$/

/** 只允许回到站内的首页、文档页和分享页，其它一律回首页。 */
function sanitizeNext(raw) {
  const value = String(raw || '')
  if (value.startsWith('/') && !value.startsWith('//')) {
    if (value === '/' || value.startsWith('/s/') || value.startsWith('/doc/')) return value
  }
  return '/'
}

/** 登录 / 注册来回切换：清错误与确认密码，账号保留。 */
function toggleMode() {
  isRegister.value = !isRegister.value
  errorMsg.value = ''
  password2.value = ''
  nextTick(() => userInputRef.value?.focus?.())
}

/** 倒计时定时器。 */
let tickTimer = null

/** 锁定进度 0–100（剩余越多环越满）。 */
const lockProgress = computed(() => {
  const total = Math.max(1, lockTotal.value)
  return Math.min(100, Math.max(0, (retryAfter.value / total) * 100))
})

/** 启动锁定倒计时（秒）。 */
function startLockCountdown(seconds) {
  const n = Math.max(0, Number(seconds) || 0)
  if (n <= 0) {
    clearLock()
    return
  }
  locked.value = true
  lockTotal.value = n
  retryAfter.value = n
  errorMsg.value = ''
  if (tickTimer) clearInterval(tickTimer)
  tickTimer = setInterval(() => {
    if (retryAfter.value <= 1) {
      clearLock()
      return
    }
    retryAfter.value -= 1
  }, 1000)
}

/** 解除锁定并清倒计时。 */
function clearLock() {
  locked.value = false
  retryAfter.value = 0
  if (tickTimer) {
    clearInterval(tickTimer)
    tickTimer = null
  }
  nextTick(() => {
    userInputRef.value?.focus?.()
  })
}

/** 从 axios 错误里取出锁定剩余秒数。 */
function readRetryAfter(err) {
  const data = err?.response?.data
  const detail = data?.detail
  if (detail && typeof detail === 'object' && detail.retry_after != null) {
    return Number(detail.retry_after)
  }
  const header = err?.response?.headers?.['retry-after']
  if (header != null) return Number(header)
  return 0
}

/** 开发模式预填 ini 账号密码；发布版只填上次登录的账号。 */
function prefillLogin() {
  if (import.meta.env.DEV) {
    username.value = import.meta.env.VITE_DEV_ADMIN_USERNAME || ''
    password.value = import.meta.env.VITE_DEV_ADMIN_PASSWORD || ''
    return
  }
  username.value = getLastUsername()
  password.value = ''
}

/** 提交登录或注册；429 时进入倒计时。 */
async function onSubmit() {
  if (!pathAllowed.value || locked.value || loading.value) return
  errorMsg.value = ''
  const name = username.value.trim()
  const pass = password.value
  if (!name || !pass) return
  if (isRegister.value) {
    // 中文：注册时按普通用户规则校验格式；管理员密码是 ini 长随机串，登录时不限制
    if (!USERNAME_RE.test(name)) {
      errorMsg.value = '账号至少 3 位，只能用英文字母和数字'
      return
    }
    if (!PASSWORD_RE.test(pass)) {
      errorMsg.value = '密码必须是 6 位英文字母或数字'
      return
    }
    if (pass !== password2.value) {
      errorMsg.value = '两次输入的密码不一致'
      return
    }
  }
  loading.value = true
  try {
    const data = isRegister.value
      ? await register({ username: name, password: pass })
      : await login({ username: name, password: pass, path: route.path })
    setAdminToken(data.token)
    rememberLastUsername(name)
    ElMessage.success(isRegister.value ? '注册成功' : '登录成功')
    router.replace(sanitizeNext(route.query.next))
  } catch (e) {
    if (e?.response?.status === 429) {
      startLockCountdown(readRetryAfter(e) || 60)
    } else {
      errorMsg.value =
        e?.response?.data?.detail ||
        e?.message ||
        (isRegister.value ? '注册失败' : '账号或密码错误')
      if (typeof errorMsg.value !== 'string') {
        errorMsg.value = errorMsg.value?.message || (isRegister.value ? '注册失败' : '账号或密码错误')
      }
    }
  } finally {
    loading.value = false
  }
}

/** 先核对路径是否与 ini 一致，通过后再处理已有会话。 */
async function bootstrap() {
  checking.value = true
  pathAllowed.value = false
  gateError.value = ''
  try {
    const { data } = await adminGate(route.path)
    pathAllowed.value = !!data?.ok
  } catch {
    pathAllowed.value = false
    gateError.value = '登录服务未就绪，请重新运行 python run.py'
  } finally {
    checking.value = false
  }
  if (!pathAllowed.value) return
  rememberLoginPath(route.path)

  const token = getAdminToken()
  if (!token) {
    prefillLogin()
    nextTick(() => userInputRef.value?.focus?.())
    return
  }
  try {
    await adminMe()
    // 中文：已登录者直接回 next（比如分享链接），没有 next 才回首页
    router.replace(sanitizeNext(route.query.next))
  } catch {
    setAdminToken('')
    prefillLogin()
    nextTick(() => userInputRef.value?.focus?.())
  }
}

onMounted(() => {
  bootstrap()
})

onBeforeUnmount(() => {
  if (tickTimer) clearInterval(tickTimer)
})
</script>

<style scoped>
/* 中文：路径未通过核对时的占位页 */
.gate-page {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 32px 16px;
  background: var(--bg-page);
  color: var(--text-body);
}
.gate-title {
  margin: 0;
  font-size: 24px;
  line-height: 1.15;
  font-weight: 500;
  letter-spacing: 0;
  color: var(--text-title);
}
.gate-hint {
  margin: 0;
  font-size: 14px;
  line-height: 20px;
  color: var(--text-muted);
}

/* 中文：登录固定浅色石板，避免跟系统暗色搅在一起；左栏另用深色 */
.login-page {
  --bg-page: #f8fafc;
  --bg-elevated: #ffffff;
  --bg-muted: #f1f5f9;
  --text-title: #0f172a;
  --text-body: #1e293b;
  --text-secondary: #334155;
  --text-muted: #64748b;
  --text-inverse: #ffffff;
  --border-subtle: #e2e8f0;
  --border-default: #cbd5e1;
  --border-strong: #94a3b8;
  --accent: #2563eb;
  --accent-hover: #1d4ed8;
  --accent-ring: rgba(37, 99, 235, 0.28);
  --warning: #d97706;
  --danger: #dc2626;
  --danger-soft: #fee2e2;
  --shadow-lg: 0 8px 24px rgba(15, 23, 42, 0.06);

  min-height: 100%;
  display: grid;
  grid-template-columns: minmax(480px, 1.35fr) minmax(380px, 0.8fr);
  background: var(--bg-page);
  color: var(--text-body);
}

/* 中文：左半屏深色，标题放大，白纸浮在上面 */
.preview-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 64px 48px;
  background: #0f172a;
}
.preview-inner {
  width: min(560px, 100%);
  animation: riseIn 320ms ease both;
}
.wordmark {
  margin-bottom: 32px;
}
.logo {
  width: 36px;
  height: 36px;
  margin-bottom: 20px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0;
  color: #ffffff;
  background: var(--accent);
}
.brand-title {
  margin: 0;
  font-size: clamp(40px, 4vw, 56px);
  line-height: 1.08;
  font-weight: 500;
  letter-spacing: -0.02em;
  color: #f8fafc;
}
.brand-lead {
  margin: 12px 0 0;
  font-size: 18px;
  line-height: 28px;
  color: #94a3b8;
}
.sheet {
  padding: 28px 32px 32px;
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.28);
}
.sheet-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.sheet-title {
  margin: 0;
  font-size: 16px;
  line-height: 24px;
  font-weight: 500;
  color: #0f172a;
}
.sheet-meta {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 16px;
  font-weight: 400;
  color: #64748b;
}
.sheet-body {
  margin: 0;
  font-size: 16px;
  line-height: 28px;
  font-weight: 400;
  color: #1e293b;
}
.sheet-hl {
  background: rgba(254, 243, 199, 0.95);
  border-bottom: 2px solid var(--warning);
  border-radius: 2px;
  padding: 0 2px;
  color: inherit;
}
.margin-note {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 12px 0 16px;
  padding-left: 12px;
  border-left: 2px solid var(--accent);
}
.note-label {
  flex-shrink: 0;
  font-size: 12px;
  line-height: 20px;
  color: #64748b;
}
.note-text {
  font-size: 14px;
  line-height: 22px;
  color: #334155;
}

/* 中文：右侧浅底上的登录卡片，跟左栏的深色分开 */
.form-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 32px;
  background: var(--bg-page);
}
.form-shell {
  width: min(400px, 100%);
  padding: 32px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  box-shadow: var(--shadow-lg);
  animation: riseIn 320ms ease both;
  animation-delay: 40ms;
}
.form-shell.locked {
  text-align: center;
}
.form-head {
  margin-bottom: 24px;
}
.panel-title {
  margin: 0;
  font-size: 24px;
  line-height: 1.15;
  font-weight: 500;
  letter-spacing: 0;
  color: var(--text-title);
}
.panel-desc {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 20px;
  color: var(--text-muted);
}

.form :deep(.el-form-item) {
  margin-bottom: 16px;
  display: block;
}
.form :deep(.el-form-item__label) {
  color: var(--text-muted);
  margin-bottom: 8px;
  line-height: 20px;
  font-weight: 500;
}
/* 中文：边框和焦点环跟全站输入框，这里只加高到好点的高度 */
.form :deep(.el-input__wrapper) {
  min-height: 44px;
}
.submit.el-button {
  width: 100%;
  min-height: 48px;
  margin-top: 8px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  border: none;
  --el-button-bg-color: var(--accent);
  --el-button-border-color: var(--accent);
  --el-button-text-color: var(--text-inverse);
  --el-button-hover-bg-color: var(--accent-hover);
  --el-button-hover-border-color: var(--accent-hover);
  --el-button-hover-text-color: var(--text-inverse);
  --el-button-active-bg-color: var(--accent-hover);
  --el-button-active-border-color: var(--accent-hover);
  --el-button-disabled-bg-color: var(--accent);
  --el-button-disabled-border-color: var(--accent);
  --el-button-disabled-text-color: var(--text-inverse);
  background: var(--accent);
  color: var(--text-inverse);
  transition: background var(--motion-fast), opacity var(--motion-fast);
}
.submit.el-button:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.submit.el-button.is-disabled {
  opacity: 0.45;
}

.err-msg {
  margin: 0 0 16px;
  padding: 12px;
  border-radius: var(--radius-sm);
  background: var(--danger-soft);
  color: var(--danger);
  font-size: 13px;
  line-height: 20px;
}

/* 中文：登录/注册切换行 */
.switch-line {
  margin: 16px 0 0;
  font-size: 13px;
  line-height: 20px;
  color: var(--text-muted);
  text-align: center;
}
.switch-link {
  color: var(--accent);
  text-decoration: none;
  cursor: pointer;
}
.switch-link:hover {
  text-decoration: underline;
}

/* 中文：锁定倒计时环，颜色跟蓝笔而不是另一套青 */
.lock-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.lock-ring {
  --p: 100;
  width: 128px;
  height: 128px;
  margin: 0 auto 16px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: conic-gradient(
    var(--accent) calc(var(--p) * 1%),
    var(--bg-muted) 0
  );
  transition: background var(--motion-base) linear;
}
.lock-ring::before {
  content: "";
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: #ffffff;
  grid-area: 1 / 1;
}
.lock-seconds {
  grid-area: 1 / 1;
  position: relative;
  z-index: 1;
  font-size: 32px;
  font-weight: 500;
  letter-spacing: 0;
  color: var(--text-title);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.lock-panel .panel-desc {
  max-width: 28ch;
}

@keyframes riseIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 960px) {
  .login-page {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
  }
  .preview-panel {
    padding: 40px 24px 32px;
    justify-content: flex-start;
  }
  .brand-title {
    font-size: 36px;
    letter-spacing: 0;
  }
  .form-panel {
    padding: 24px 16px 40px;
    align-items: flex-start;
  }
  .form-shell {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .preview-inner,
  .form-shell {
    animation: none;
  }
  .lock-ring {
    transition: none;
  }
}
</style>
