<template>
  <el-dialog :model-value="modelValue" title="版本历史" width="720px" @close="$emit('update:modelValue', false)">
    <el-table :data="versions" size="small" v-loading="loading" max-height="360">
      <el-table-column prop="version_no" label="版本" width="80" />
      <el-table-column prop="created_at" label="时间" width="200" />
      <el-table-column prop="remark" label="备注" />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button link type="primary" @click="preview(row)">查看</el-button>
          <el-button link type="warning" @click="diffWith(row)">Diff</el-button>
          <el-button link type="danger" @click="doRollback(row)">回滚</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="detailVisible" title="版本内容" width="640px" append-to-body>
      <pre class="snap">{{ detail }}</pre>
    </el-dialog>
    <el-dialog v-model="diffVisible" title="与当前版本 Diff" width="720px" append-to-body>
      <pre class="snap" v-html="diffHtml"></pre>
    </el-dialog>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as Diff from 'diff'
import { getDoc, getVersion, listVersions, rollback } from '@/api/doc'

const props = defineProps({
  modelValue: Boolean,
  docId: { type: Number, required: true },
})
const emit = defineEmits(['update:modelValue', 'restored'])

const versions = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const detail = ref('')
const diffVisible = ref(false)
const diffHtml = ref('')

async function refresh() {
  loading.value = true
  try {
    versions.value = await listVersions(props.docId)
  } finally {
    loading.value = false
  }
}

async function preview(row) {
  const v = await getVersion(props.docId, row.id)
  detail.value = v.content_snapshot
  detailVisible.value = true
}

async function diffWith(row) {
  const v = await getVersion(props.docId, row.id)
  const cur = await getDoc(props.docId)
  const parts = Diff.diffLines(v.content_snapshot || '', cur.content || '')
  diffHtml.value = parts
    .map((p) => {
      const cls = p.added ? 'add' : p.removed ? 'del' : ''
      const text = p.value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
      return `<span class="${cls}">${text}</span>`
    })
    .join('')
  diffVisible.value = true
}

async function doRollback(row) {
  try {
    await ElMessageBox.confirm(`确认回滚到版本 ${row.version_no}？将生成新快照。`, '回滚', {
      type: 'warning',
    })
    const doc = await rollback(props.docId, row.id)
    ElMessage.success('已回滚')
    emit('restored', doc)
    await refresh()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || '回滚失败')
  }
}

watch(
  () => props.modelValue,
  (v) => {
    if (v) refresh()
  }
)
</script>

<style scoped>
.snap {
  white-space: pre-wrap;
  font-family: ui-monospace, Menlo, Consolas, monospace;
  font-size: 12px;
  max-height: 480px;
  overflow: auto;
  background: #fafafa;
  padding: 12px;
  border-radius: 6px;
}
:deep(.add) { background: #e1f3d8; }
:deep(.del) { background: #fde2e2; }
</style>
