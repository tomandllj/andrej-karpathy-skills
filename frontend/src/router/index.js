import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import DocView from '@/views/DocView.vue'
import ShareView from '@/views/ShareView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/doc/:id', name: 'doc', component: DocView, props: true },
    { path: '/s/:token', name: 'share', component: ShareView, props: true },
  ],
})

export default router
