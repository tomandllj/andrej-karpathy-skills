<template>
  <el-dialog :model-value="modelValue" title="分享文档" width="520px" @close="$emit('update:modelValue', false)">
    <el-form label-width="90px">
      <el-form-item label="权限">
        <el-select v-model="permission" style="width: 200px">
          <el-option label="只读 read" value="read" />
          <el-option label="仅评论 comment" value="comment" />
          <el-option label="可编辑 edit" value="edit" />
        </el-select>
        <el-button type="primary" style="margin-left: 12px" :loading="loading" @click="create">
          生成链接
        </el-button>
      </el-form-item>
      <el-form-item v-if="lastUrl" label="链接">
        <el-input :model-value="lastUrl" readonly>
          <template #append>
            <el-button @click="copy(lastUrl)">复制</el-button>
          </template>
        </el-input>
      </el-form-item>
    </el-form>

    <el-divider>已有分享</el-divider>
    <el-table :data="shares" size="small" empty-text="暂无分享">
      <el-table-column prop="permission" label="权限" width="100" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '有效' : '已关闭' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="链接">
        <template #default="{ row }">
          <el-button link type="primary" @click="copy(absUrl(row))">复制</el-button>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button
            v-if="row.is_active"
            link
            type="warning"
            @click="toggle(row, false)"
          >关闭</el-button>
          <el-button v-else link type="success" @click="toggle(row, true)">启用</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createShare, listShares, updateShare } from '@/api/doc'

const props = defineProps({
  modelValue: Boolean,
  docId: { type: Number, required: true },
})
defineEmits(['update:modelValue'])

const permission = ref('comment')
const loading = ref(false)
const shares = ref([])
const lastUrl = ref('')

function absUrl(share) {
  return `${location.origin}${share.share_url_path}`
}

async function refresh() {
  shares.value = await listShares(props.docId)
}

async function create() {
  loading.value = true
  try {
    const s = await createShare(props.docId, permission.value)
    lastUrl.value = absUrl(s)
    await refresh()
    ElMessage.success('已生成分享链接')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '创建失败')
  } finally {
    loading.value = false
  }
}

async function toggle(row, active) {
  try {
    await updateShare(row.id, { is_active: active }, props.docId)
    await refresh()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.info(text)
  }
}

watch(
  () => props.modelValue,
  (v) => {
    if (v) refresh().catch(() => {})
  }
)
</script>
