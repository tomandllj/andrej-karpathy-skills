<template>
  <div class="wrap" v-loading="loading">
    <DocWorkspace
      v-if="doc"
      :doc-id="Number(id)"
      :initial-doc="doc"
      mode="owner"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getDoc } from '@/api/doc'
import { getOwnerSecret, rememberRecentDoc } from '@/utils/localDocs'
import DocWorkspace from '@/components/DocWorkspace.vue'

const props = defineProps({ id: { type: [String, Number], required: true } })
const loading = ref(true)
const doc = ref(null)

onMounted(async () => {
  try {
    doc.value = await getDoc(props.id, { ownerSecret: getOwnerSecret(props.id) })
    rememberRecentDoc({
      id: doc.value.id,
      title: doc.value.title,
      // 中文：文件夹按当前视角记录 —— 收到的文档记自己的归类，不记创建者的
      folder_id: doc.value.folder_id ?? null,
      origin: doc.value.origin || null,
    })
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载文档失败')
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.wrap { height: 100%; }
</style>
