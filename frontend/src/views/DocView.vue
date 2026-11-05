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
import { getOwnerSecret } from '@/utils/localDocs'
import DocWorkspace from '@/components/DocWorkspace.vue'

const props = defineProps({ id: { type: [String, Number], required: true } })
const loading = ref(true)
const doc = ref(null)

onMounted(async () => {
  try {
    doc.value = await getDoc(props.id, { ownerSecret: getOwnerSecret(props.id) })
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
