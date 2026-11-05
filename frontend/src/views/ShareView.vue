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
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getByShareToken } from '@/api/doc'
import DocWorkspace from '@/components/DocWorkspace.vue'

const props = defineProps({ token: { type: String, required: true } })
const loading = ref(true)
const doc = ref(null)

onMounted(async () => {
  try {
    doc.value = await getByShareToken(props.token)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '分享链接无效')
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.wrap { height: 100%; }
</style>
