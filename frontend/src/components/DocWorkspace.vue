<template>
  <div class="workspace">
    <header class="top">
      <div class="left">
        <el-button text @click="$router.push('/')">← 首页</el-button>
        <el-input
          v-model="title"
          class="title-input"
          :disabled="!canEditMeta"
          @change="saveTitle"
        />
        <el-tag size="small" :type="permTagType">{{ permLabel }}</el-tag>
        <el-tag v-if="isOwner" size="small" type="success">创建人</el-tag>
      </div>
      <div class="right">
        <el-radio-group v-model="viewMode" size="small">
          <el-radio-button value="split">双栏</el-radio-button>
          <el-radio-button value="preview">仅预览</el-radio-button>
        </el-radio-group>
        <el-button v-if="isOwner" @click="shareVisible = true">分享</el-button>
        <el-button v-if="isOwner" @click="versionVisible = true">版本</el-button>
        <el-button @click="onExport">导出 MD</el-button>
        <el-button :type="panelOpen ? 'primary' : 'default'" @click="panelOpen = !panelOpen">
          批注 {{ commentsFlat.length }}
        </el-button>
        <span class="save-hint">{{ saveHint }}</span>
      </div>
    </header>

    <div class="main" :class="{ 'with-panel': panelOpen }">
      <div class="editor-pane" v-show="viewMode === 'split'">
        <textarea
          class="editor"
          v-model="content"
          :disabled="!canEditContent"
          :placeholder="canEditContent ? '编写 Markdown… 支持 ```mermaid 代码块' : '当前权限不可编辑正文'"
          @input="onContentInput"
        />
      </div>
      <div class="preview-pane" ref="previewPane">
        <MdPreview
          ref="previewRef"
          :markdown="content"
          :comments="comments"
          :allow-select="canComment"
          @select-text="onSelectText"
          @bubble-click="focusComment"
        />
      </div>
      <aside class="panel" v-show="panelOpen">
        <CommentPanel
          :comments="comments"
          :is-owner="isOwner"
          :client-key="clientKey"
          :markdown="content"
          @focus="focusComment"
          @reply="onReply"
          @resolve="onResolve"
          @remove="onRemoveComment"
          @edit="onEditComment"
        />
      </aside>
    </div>

    <ShareDialog
      v-if="isOwner"
      v-model="shareVisible"
      :doc-id="docId"
    />
    <VersionDialog
      v-if="isOwner"
      v-model="versionVisible"
      :doc-id="docId"
      @restored="onRestored"
    />

    <el-dialog v-model="commentDialog" title="添加批注" width="420px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="选中原文">
          <el-input type="textarea" :model-value="pending?.selected_text" readonly :rows="2" />
        </el-form-item>
        <el-form-item label="匿名昵称">
          <el-input v-model="anonName" placeholder="例如：审阅人A" />
        </el-form-item>
        <el-form-item label="批注内容">
          <el-input v-model="commentText" type="textarea" :rows="3" placeholder="写下你的意见" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="commentDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitComment">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createComment,
  deleteComment,
  exportUrl,
  listComments,
  updateComment,
  updateDoc,
} from '@/api/doc'
import {
  getAnonName,
  getClientKey,
  getOwnerSecret,
  saveLocalDoc,
  setAnonName,
  updateLocalTitle,
} from '@/utils/localDocs'
import MdPreview from './MdPreview.vue'
import CommentPanel from './CommentPanel.vue'
import ShareDialog from './ShareDialog.vue'
import VersionDialog from './VersionDialog.vue'

const props = defineProps({
  docId: { type: Number, required: true },
  initialDoc: { type: Object, required: true },
  shareToken: { type: String, default: null },
  mode: { type: String, default: 'owner' },
})

const title = ref(props.initialDoc.title || '无标题文档')
const content = ref(props.initialDoc.content || '')
const isOwner = ref(!!props.initialDoc.is_owner || !!getOwnerSecret(props.docId))
const permission = ref(
  props.initialDoc.permission || (isOwner.value ? 'edit' : 'read')
)
const comments = ref([])
const panelOpen = ref(true)
const viewMode = ref(permission.value === 'read' || permission.value === 'comment' ? 'preview' : 'split')
const shareVisible = ref(false)
const versionVisible = ref(false)
const saveHint = ref('')
const commentDialog = ref(false)
const pending = ref(null)
const anonName = ref(getAnonName())
const commentText = ref('')
const submitting = ref(false)
const clientKey = getClientKey()
const previewRef = ref(null)
let saveTimer = null
let ws = null

const canEditContent = computed(() => isOwner.value || permission.value === 'edit')
const canEditMeta = computed(() => isOwner.value)
const canComment = computed(() => isOwner.value || permission.value === 'comment' || permission.value === 'edit')
const permLabel = computed(() => {
  if (isOwner.value) return '可管理'
  return { read: '只读', comment: '仅评论', edit: '可编辑' }[permission.value] || '未知'
})
const permTagType = computed(() => {
  if (isOwner.value) return 'success'
  return { read: 'info', comment: 'warning', edit: 'primary' }[permission.value] || 'info'
})

const commentsFlat = computed(() => {
  const out = []
  for (const c of comments.value) {
    out.push(c)
    if (c.replies?.length) out.push(...c.replies)
  }
  return out
})

async function reloadComments() {
  comments.value = await listComments(props.docId)
}

function onContentInput() {
  saveHint.value = '编辑中…'
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => doSave(), 1500)
}

async function doSave() {
  if (!canEditContent.value) return
  try {
    saveHint.value = '保存中…'
    const data = await updateDoc(
      props.docId,
      { title: title.value, content: content.value },
      { shareToken: props.shareToken }
    )
    if (isOwner.value) {
      saveLocalDoc({
        id: props.docId,
        owner_secret: getOwnerSecret(props.docId),
        title: data.title,
      })
    }
    saveHint.value = `已保存 ${new Date().toLocaleTimeString()}`
  } catch (e) {
    saveHint.value = '保存失败'
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  }
}

async function saveTitle() {
  if (!canEditMeta.value) return
  try {
    await updateDoc(props.docId, { title: title.value }, { shareToken: props.shareToken })
    updateLocalTitle(props.docId, title.value)
    ElMessage.success('标题已更新')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '标题保存失败')
  }
}

function onSelectText(payload) {
  if (!canComment.value) return
  pending.value = payload
  commentText.value = ''
  commentDialog.value = true
}

async function submitComment() {
  if (!pending.value) return
  if (!commentText.value.trim()) {
    ElMessage.warning('请填写批注内容')
    return
  }
  submitting.value = true
  try {
    setAnonName(anonName.value)
    const created = await createComment(
      props.docId,
      {
        selected_text: pending.value.selected_text,
        content: commentText.value.trim(),
        offset_start: pending.value.offset_start,
        offset_end: pending.value.offset_end,
        anon_name: anonName.value.trim() || '匿名',
        parent_id: pending.value.parent_id || null,
        client_key: clientKey,
      },
      { shareToken: props.shareToken }
    )
    window.dispatchEvent(new CustomEvent('md-annotate-owned', { detail: created.id }))
    try {
      const key = 'md_annotate_owned_comments'
      const set = new Set(JSON.parse(localStorage.getItem(key) || '[]'))
      set.add(created.id)
      localStorage.setItem(key, JSON.stringify([...set]))
    } catch {}
    commentDialog.value = false
    await reloadComments()
    ElMessage.success('批注已添加')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}

function onReply(comment) {
  pending.value = {
    selected_text: comment.selected_text,
    offset_start: comment.offset_start,
    offset_end: comment.offset_end,
    parent_id: comment.id,
  }
  commentText.value = ''
  commentDialog.value = true
}

async function onResolve(comment) {
  try {
    await updateComment(
      props.docId,
      comment.id,
      { status: comment.status === 'resolved' ? 'pending' : 'resolved', client_key: clientKey },
      { shareToken: props.shareToken }
    )
    await reloadComments()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
}

async function onRemoveComment(comment) {
  try {
    await ElMessageBox.confirm('确认删除该批注？', '删除', { type: 'warning' })
    await deleteComment(props.docId, comment.id, { shareToken: props.shareToken })
    await reloadComments()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

async function onEditComment(comment) {
  try {
    const { value } = await ElMessageBox.prompt('修改批注内容', '编辑批注', {
      inputValue: comment.content,
      inputType: 'textarea',
    })
    await updateComment(
      props.docId,
      comment.id,
      { content: value, client_key: clientKey },
      { shareToken: props.shareToken }
    )
    await reloadComments()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || '修改失败')
  }
}

function focusComment(id) {
  previewRef.value?.flashComment?.(id)
}

function onExport() {
  window.open(exportUrl(props.docId), '_blank')
}

function onRestored(doc) {
  content.value = doc.content
  title.value = doc.title
  reloadComments()
}

function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const url = `${proto}://${location.host}/ws/doc/${props.docId}`
  ws = new WebSocket(url)
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data)
      if (['comment.new', 'comment.update', 'comment.delete'].includes(msg.event)) {
        reloadComments()
      }
    } catch {
      /* ignore */
    }
  }
  ws.onclose = () => {
    setTimeout(connectWs, 3000)
  }
}

onMounted(async () => {
  // persist owner secret if present from create flow already in localStorage
  if (isOwner.value && getOwnerSecret(props.docId)) {
    saveLocalDoc({
      id: props.docId,
      owner_secret: getOwnerSecret(props.docId),
      title: title.value,
    })
  }
  if (!canEditContent.value) viewMode.value = 'preview'
  await reloadComments()
  connectWs()
})

onBeforeUnmount(() => {
  clearTimeout(saveTimer)
  if (ws) {
    ws.onclose = null
    ws.close()
  }
})

watch(
  () => props.initialDoc,
  (d) => {
    if (!d) return
    title.value = d.title
    content.value = d.content
    isOwner.value = !!d.is_owner || !!getOwnerSecret(props.docId)
    permission.value = d.permission || (isOwner.value ? 'edit' : 'read')
  }
)
</script>

<style scoped>
.workspace { height: 100%; display: flex; flex-direction: column; background: #fff; }
.top {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; padding: 8px 12px; border-bottom: 1px solid #ebeef5;
  background: #fafbfc; flex-wrap: wrap;
}
.left, .right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.title-input { width: 280px; }
.save-hint { color: #909399; font-size: 12px; min-width: 90px; }
.main {
  flex: 1; display: grid; grid-template-columns: 1fr 1fr; min-height: 0;
}
.main.with-panel { grid-template-columns: 1fr 1fr 320px; }
.main:not(.with-panel) .preview-pane { border-right: none; }
.editor-pane, .preview-pane, .panel {
  min-height: 0; overflow: auto; border-right: 1px solid #ebeef5;
}
.panel { border-right: none; background: #fcfcfd; }
.editor {
  width: 100%; height: 100%; border: 0; outline: none; resize: none;
  padding: 16px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 14px; line-height: 1.6; background: #fff;
}
.editor:disabled { background: #f5f7fa; color: #909399; }
.preview-pane { padding: 16px 20px; }
@media (max-width: 960px) {
  .main, .main.with-panel { grid-template-columns: 1fr; }
}
</style>
