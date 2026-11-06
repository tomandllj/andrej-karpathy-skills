/** 浅色/暗色主题读写与初始化（持久化到 localStorage）。 */

const STORAGE_KEY = 'md_annotate_theme'

/** 返回当前主题：light | dark。 */
export function getTheme() {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'light' || saved === 'dark') return saved
  if (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark'
  }
  return 'light'
}

/** 应用主题到 html[data-theme] 并可选持久化。 */
export function setTheme(theme) {
  const next = theme === 'dark' ? 'dark' : 'light'
  document.documentElement.setAttribute('data-theme', next)
  localStorage.setItem(STORAGE_KEY, next)
  return next
}

/** 在应用启动时写入初始主题。 */
export function initTheme() {
  return setTheme(getTheme())
}

/** 在 light / dark 之间切换。 */
export function toggleTheme() {
  return setTheme(getTheme() === 'dark' ? 'light' : 'dark')
}
