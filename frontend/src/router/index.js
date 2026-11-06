import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import DocView from '@/views/DocView.vue'
import ShareView from '@/views/ShareView.vue'
import AdminLoginView from '@/views/AdminLoginView.vue'
import UnavailableView from '@/views/UnavailableView.vue'
import { adminMe, clearAdminToken, getAdminToken } from '@/api/admin'
import { getEntry } from '@/api/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
      // 中文：管理员和普通用户都能进，只要已登录
      meta: { requiresLogin: true },
    },
    {
      path: '/doc/:id',
      name: 'doc',
      component: DocView,
      props: true,
      meta: { requiresLogin: true },
    },
    // 中文：分享链接先由 ShareView 检查登录，未登录会转到 ini 登录页
    { path: '/s/:token', name: 'share', component: ShareView, props: true },
    // 中文：唯一登录/注册页，候选长路径进组件后须与 config.ini login_path 完全一致才显示
    {
      path: '/:adminKey([\\w-]{16,})',
      name: 'admin-login',
      component: AdminLoginView,
    },
    {
      path: '/404',
      name: 'unavailable',
      component: UnavailableView,
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: UnavailableView,
    },
  ],
})

/** 校验本地会话是否仍有效（管理员和普通用户共用同一套 token）。 */
async function ensureLoginSession() {
  const token = getAdminToken()
  if (!token) return false
  try {
    await adminMe()
    return true
  } catch {
    clearAdminToken()
    return false
  }
}

/** 公开登录入口路径（config.ini 的 login_path）；缓存一份，避免每次导航都请求后端。 */
let entryPathCache = ''

async function fetchEntryPath() {
  if (entryPathCache) return entryPathCache
  try {
    // 中文：getEntry 已解包一层 data，这里直接拿 login_path
    const entry = await getEntry()
    entryPathCache = entry?.login_path || ''
  } catch {
    entryPathCache = ''
  }
  return entryPathCache
}

router.beforeEach(async (to) => {
  if (!to.meta.requiresLogin) return true
  const ok = await ensureLoginSession()
  if (ok) return true
  // 中文：未登录跳到 ini 登录页（唯一登录/注册入口），登录后回到原本要开的页面
  const path = await fetchEntryPath()
  if (path) return { path, query: { next: to.fullPath }, replace: true }
  return { name: 'unavailable', replace: true }
})

export default router
