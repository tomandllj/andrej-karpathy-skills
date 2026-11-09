<template>
  <el-dialog
    :model-value="modelValue"
    title="分享文档"
    width="640px"
    class="share-dialog"
    @close="$emit('update:modelValue', false)"
  >
    <!-- 中文：只读链接免登录可看；选接收人则站内直接投递 -->
    <p class="hint">只读链接无需登录即可查看；选择接收人后，文档会直接投递到对方的「收到的」。</p>

    <div class="create-row">
      <div class="field">
        <label>权限</label>
        <el-select v-model="permission" style="width: 150px">
          <el-option label="只读" value="read" />
          <el-option label="仅评论" value="comment" />
          <el-option label="可编辑" value="edit" />
        </el-select>
      </div>
      <div class="field">
        <label>接收人</label>
        <el-select
          v-model="recipientIds"
          multiple
          filterable
          clearable
          collapse-tags
          collapse-tags-tooltip
          placeholder="不选 = 链接不限人"
          style="width: 240px"
        >
          <el-option v-for="user in users" :key="user.id" :label="user.username" :value="user.id" />
        </el-select>
      </div>
      <el-button type="primary" :loading="loading" @click="create">生成链接</el-button>
    </div>

    <div v-if="lastUrl" class="link-box">
      <label>最新链接</label>
      <el-input :model-value="lastUrl" readonly>
        <template #append>
          <el-button @click="copy(lastUrl)">复制</el-button>
        </template>
      </el-input>
    </div>

    <div class="section-label">已有分享</div>
    <el-table :data="shares" size="small" empty-text="暂无分享" class="share-table">
      <el-table-column prop="permission" label="权限" width="90">
        <template #default="{ row }">
          {{ { read: '只读', comment: '仅评论', edit: '可编辑' }[row.permission] || row.permission }}
        </template>
      </el-table-column>
      <el-table-column label="接收人" min-width="110">
        <template #default="{ row }">
          {{ row.recipients?.length ? row.recipients.join('、') : '不限' }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="light" round>
            {{ row.is_active ? '有效' : '已关闭' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="链接">
        <template #default="{ row }">
          <el-button link type="primary" @click="copy(absUrl(row))">复制</el-button>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120">
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
/** 分享对话框：选权限和接收人生成链接，并管理已有分享状态。 */
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createShare, listShares, listUsers, updateShare } from '@/api/doc'

const props = defineProps({
  modelValue: Boolean,
  docId: { type: Number, required: true },
})
defineEmits(['update:modelValue'])

const permission = ref('comment')
/** 选中的接收人账号编号；空数组表示链接不限人。 */
const recipientIds = ref([])
/** 登录后可用的账号名单，给下拉框选。 */
const users = ref([])
const loading = ref(false)
const shares = ref([])
const lastUrl = ref('')

function absUrl(share) {
  return `${location.origin}${share.share_url_path}`
}

async function refresh() {
  shares.value = await listShares(props.docId)
}

/** 拉一次账号名单；失败只提示，不阻塞对话框。 */
async function loadUsers() {
  try {
    users.value = await listUsers()
  } catch {
    users.value = []
  }
}

async function create() {
  loading.value = true
  try {
    const s = await createShare(props.docId, permission.value, recipientIds.value)
    lastUrl.value = absUrl(s)
    await refresh()
    ElMessage.success(
      s.recipients?.length ? `已生成分享链接，并投递给 ${s.recipients.length} 位接收人` : '已生成分享链接'
    )
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
    if (v) {
      refresh().catch(() => {})
      loadUsers()
    }
  }
)
</script>

<style scoped>
/* 中文：分享对话框局部排版，色值跟全局 token */
.hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--text-muted);
}
.create-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
/* 中文：权限标签和下拉框同一行显示 */
.field {
  display: flex;
  align-items: center;
  gap: 8px;
}
.field label,
.link-box label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}
.link-box {
  margin-bottom: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  border-radius: var(--radius-md);
  background: var(--bg-page);
  border: 1px solid var(--border-subtle);
}
.section-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.share-table {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border-subtle);
}
</style>
