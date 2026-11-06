import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import './styles.css'
import { initTheme } from './utils/theme'

initTheme()

/* 中文：从旧端口一键搬家 —— 旧端口的迁移页把浏览器存储放在 #import= 里带过来 */
try {
  if (location.hash.startsWith('#import=')) {
    const data = JSON.parse(decodeURIComponent(location.hash.slice('#import='.length)))
    for (const [k, v] of Object.entries(data || {})) {
      if (typeof k === 'string' && typeof v === 'string' && v) localStorage.setItem(k, v)
    }
    history.replaceState(null, '', location.pathname + location.search)
  }
} catch {
  /* 坏数据就忽略，不影响正常打开 */
}

const app = createApp(App)
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
app.use(ElementPlus)
app.use(router)
app.mount('#app')
