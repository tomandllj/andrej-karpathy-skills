<template>
  <div class="wrap" v-loading="loading">
    <DocWorkspace
      v-if="doc"
      :doc-id="doc.id"
      :initial-doc="doc"
      :share-token="token"
      mode="share"
    />
  </div>
</template>

<script setup>
/** 分享链接入口：先验证分享是否有效；有效但未登录才转登录页，回来后记进「收到的」再打开。 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { claimShare, getByShareToken } from '@/api/doc'
import { getEntry } from '@/api/auth'
import { adminMe, clearAdminToken, getAdminToken } from '@/api/admin'
import DocWorkspace from '@/components/DocWorkspace.vue'

const props = defineProps({ token: { type: String, required: true } })
const router = useRouter()
const loading = ref(true)
const doc = ref(null)

onMounted(async () => {
  // 中文：先验证分享本身。无效就直接提示，不引导登录、不暴露登录地址
  try {
    doc.value = await getByShareToken(props.token)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '分享链接无效')
    loading.value = false
    return
  }

  // 中文：分享有效，再看登录态
  if (getAdminToken()) {
    try {
      await adminMe()
    } catch {
      clearAdminToken()
    }
  }
  if (!getAdminToken()) {
    // 中文：未登录转登录页，登录后回到这条分享链接
    try {
      const entry = await getEntry()
      const path = entry?.login_path
      if (path) {
        router.replace({ path, query: { next: `/s/${props.token}` } })
        return
      }
    } catch {
      /* 走下面统一提示 */
    }
    ElMessage.error('登录服务未就绪，请稍后再试')
    loading.value = false
    return
  }

  // 中文：已登录：把「我收到了这篇」记到服务器，首页「收到的」里才会出现
  try {
    await claimShare(props.token)
  } catch {
    /* 记录失败不阻塞打开，本次仍按分享权限看 */
  }
  loading.value = false
})
</script>

<style scoped>
.wrap { height: 100%; }
</style>
