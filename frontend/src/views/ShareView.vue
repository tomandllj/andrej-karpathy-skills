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
/** 分享链接入口：先验证分享是否有效；只读链接免登录直接看，其余需登录后再打开。 */
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

/** 未登录时去登录页，登录后回到这条分享链接；拿不到登录地址才返回 false。 */
async function redirectToLogin() {
  try {
    const entry = await getEntry()
    const path = entry?.login_path
    if (path) {
      router.replace({ path, query: { next: `/s/${props.token}` } })
      return true
    }
  } catch {
    /* 走下面统一提示 */
  }
  return false
}

onMounted(async () => {
  // 中文：登录态自检，过期的 token 先清掉
  if (getAdminToken()) {
    try {
      await adminMe()
    } catch {
      clearAdminToken()
    }
  }

  // 中文：先验证分享本身。无效就直接提示；限接收人的分享未登录时先去登录
  try {
    doc.value = await getByShareToken(props.token)
  } catch (e) {
    if (e?.response?.status === 403 && !getAdminToken()) {
      if (await redirectToLogin()) return
    }
    ElMessage.error(e?.response?.data?.detail || '分享链接无效')
    loading.value = false
    return
  }

  // 中文：只读分享免登录直接看；碰巧已登录则顺手记进「收到的」（仅限接收人）
  if (doc.value.permission === 'read') {
    if (getAdminToken()) {
      claimShare(props.token).catch(() => {})
    }
    loading.value = false
    return
  }

  // 中文：仅评论 / 可编辑需要登录，回来后记进「收到的」再打开
  if (!getAdminToken()) {
    if (await redirectToLogin()) return
    ElMessage.error('登录服务未就绪，请稍后再试')
    loading.value = false
    return
  }

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
