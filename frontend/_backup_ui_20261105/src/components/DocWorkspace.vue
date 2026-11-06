<template>
  <div class="workspace">
    <header class="top">
      <div class="left">
        <el-button class="back-btn" text @click="$router.push('/')">
          <el-icon class="el-icon--left"><ArrowLeft /></el-icon>
          首页
        </el-button>
        <div class="title-wrap">
          <el-input
            v-model="title"
            class="title-input"
            :disabled="!canEditMeta"
            placeholder="无标题文档"
            @change="saveTitle"
          />
        </div>
        <el-tag size="small" effect="plain" round :type="permTagType">{{ permLabel }}</el-tag>
        <el-tag v-if="isOwner" size="small" effect="light" round type="success">创建人</el-tag>
      </div>
      <div class="right">
        <el-radio-group v-model="viewMode" size="small" class="view-switch">
          <el-radio-button value="split">双栏</el-radio-button>
          <el-radio-button value="preview">仅预览</el-radio-button>
        </el-radio-group>
        <div class="divider" aria-hidden="true"></div>
        <el-button v-if="isOwner" @click="shareVisible = true">分享</el-button>
        <el-button v-if="isOwner" @click="versionVisible = true">版本</el-button>
        <el-button @click="onExport">导出</el-button>
        <el-button :type="panelOpen ? 'primary' : 'default'" @click="panelOpen = !panelOpen">
          批注 {{ commentsFlat.length }}
        </el-button>
        <span class="save-hint" :class="{ ok: saveHint.startsWith('已保存'), bad: saveHint === '保存失败' }">{{ saveHint || '自动保存' }}</span>
      </div>
    </header>

    <div
      class="main"
      :class="{
        'with-panel': panelOpen,
        'mode-split': viewMode === 'split',
        'mode-preview': viewMode === 'preview',
      }"
      :style="{ '--panel-w': panelWidth + 'px' }"
    >
      <div class="editor-pane" v-show="viewMode === 'split'">
        <textarea
          ref="editorRef"
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
          :active-comment-id="activeCommentId"
          @select-text="onSelectText"
          @bubble-click="focusComment"
        />
      </div>
      <!-- 中文：预览与批注之间的拖拽调宽条 -->
      <div
        v-show="panelOpen"
        class="panel-resizer"
        title="拖动调整批注栏宽度"
        @mousedown.prevent="onPanelResizeStart"
      />
      <aside class="panel" v-show="panelOpen">
        <CommentPanel
          ref="commentPanelRef"
          :comments="comments"
          :is-owner="isOwner"
          :client-key="clientKey"
          :markdown="content"
          :active-comment-id="activeCommentId"
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
/** 文档工作区：双栏编辑/预览、批注侧栏与分享版本入口。 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import {
  batchUpdateCommentAnchors,
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
import {
  applyEditToComment,
  resolveAnchor,
  resolveComments,
} from '@/utils/anchor'
import MdPreview from './MdPreview.vue'
import CommentPanel from './CommentPanel.vue'
import ShareDialog from './ShareDialog.vue'
import VersionDialog from './VersionDialog.vue'

/** 批注栏默认宽，也是可拖的最小宽。 */
const PANEL_MIN_WIDTH = 320
/** 批注栏拖拽上限，避免挤没预览区。 */
const PANEL_MAX_WIDTH = 560

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
/** 批注栏像素宽；切换双栏/仅预览时不变。 */
const panelWidth = ref(PANEL_MIN_WIDTH)
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
const editorRef = ref(null)
const commentPanelRef = ref(null)
const activeCommentId = ref(null)
let saveTimer = null
let ws = null
/** 拖拽批注宽时的起始鼠标 X 与起始宽度。 */
let resizeStartX = 0
let resizeStartWidth = 0

/** 开始拖拽调整批注栏宽度。 */
function onPanelResizeStart(ev) {
  resizeStartX = ev.clientX
  resizeStartWidth = panelWidth.value
  document.body.classList.add('is-panel-resizing')
  window.addEventListener('mousemove', onPanelResizeMove)
  window.addEventListener('mouseup', onPanelResizeEnd)
}

/** 拖拽中按水平位移更新批注宽。 */
function onPanelResizeMove(ev) {
  const delta = resizeStartX - ev.clientX
  const next = Math.min(
    PANEL_MAX_WIDTH,
    Math.max(PANEL_MIN_WIDTH, resizeStartWidth + delta)
  )
  panelWidth.value = next
}

/** 结束拖拽并卸掉全局监听。 */
function onPanelResizeEnd() {
  document.body.classList.remove('is-panel-resizing')
  window.removeEventListener('mousemove', onPanelResizeMove)
  window.removeEventListener('mouseup', onPanelResizeEnd)
}

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

/** 上一份正文，用于 diff 平移批注区间。 */
let lastMappedContent = props.initialDoc.content || ''

/** 拉取批注后按当前正文解析锚点。 */
async function reloadComments() {
  const rows = await listComments(props.docId)
  comments.value = resolveComments(content.value, rows)
  lastMappedContent = content.value
}

/** 正文输入：平移/伸缩批注区间，删空则失锚。 */
function onContentInput() {
  const prev = lastMappedContent
  const next = content.value
  if (prev !== next && comments.value.length) {
    comments.value = comments.value.map((c) => applyEditToComment(c, prev, next))
  }
  lastMappedContent = next
  saveHint.value = '编辑中…'
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => doSave(), 1500)
}

/** 收集仍有效的根批注锚点，供写回后端。 */
function collectAnchorPayloads() {
  return comments.value
    .filter((c) => !c.parent_id && !c._lost)
    .map((c) => {
      const resolved = resolveAnchor(content.value, c)
      if (resolved.lost) return null
      return {
        id: c.id,
        offset_start: resolved.start,
        offset_end: resolved.end,
        selected_text: resolved.selected_text,
        context_prefix: c.context_prefix || '',
        context_suffix: c.context_suffix || '',
      }
    })
    .filter(Boolean)
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
    const anchors = collectAnchorPayloads()
    if (anchors.length) {
      await batchUpdateCommentAnchors(props.docId, anchors, {
        shareToken: props.shareToken,
      })
    }
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
        context_prefix: pending.value.context_prefix || '',
        context_suffix: pending.value.context_suffix || '',
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
    context_prefix: comment.context_prefix || '',
    context_suffix: comment.context_suffix || '',
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

/** 批注是否已失锚（编辑删空或解析失败）。 */
function isCommentLost(c) {
  if (!c) return true
  if (c._lost) return true
  return resolveAnchor(content.value, c).lost
}

/** Map reply id → root comment id (sidebar cards are keyed by root). */
function resolveRootId(id) {
  const n = Number(id)
  for (const c of comments.value) {
    if (Number(c.id) === n) return c.id
    if (c.replies?.some((r) => Number(r.id) === n)) return c.id
  }
  return id
}

function clearActiveComment() {
  activeCommentId.value = null
}

/**
 * 双栏时在编辑区选中批注区间并滚到可见位置。
 * @param {number} start
 * @param {number} end
 */
function revealInEditor(start, end) {
  const el = editorRef.value
  if (!el || viewMode.value !== 'split') return
  const len = el.value.length
  const s = Math.max(0, Math.min(Number(start) || 0, len))
  const e = Math.max(s, Math.min(Number(end) || 0, len))
  if (e <= s) return

  const style = window.getComputedStyle(el)
  const fontSize = parseFloat(style.fontSize) || 14
  const lineHeight = parseFloat(style.lineHeight) || fontSize * 1.7
  const paddingTop = parseFloat(style.paddingTop) || 0
  const linesBefore = el.value.slice(0, s).split('\n').length - 1
  el.scrollTop = Math.max(0, linesBefore * lineHeight + paddingTop - el.clientHeight * 0.35)

  if (!el.disabled) {
    try {
      el.focus({ preventScroll: true })
      el.setSelectionRange(s, e)
    } catch {
      /* 部分浏览器对不可聚焦控件会抛错，忽略 */
    }
  }
}

/**
 * 侧栏与预览、编辑区双向定位；失锚只滚侧栏并提示。
 */
async function focusComment(id) {
  if (id == null) return
  const rootId = resolveRootId(id)
  const root = comments.value.find((c) => Number(c.id) === Number(rootId))

  panelOpen.value = true
  activeCommentId.value = rootId

  await nextTick()
  commentPanelRef.value?.scrollToComment?.(rootId)

  if (!root || isCommentLost(root)) {
    ElMessage.warning('正文已改，无法定位')
    return
  }

  const resolved = resolveAnchor(content.value, root)
  if (resolved.lost) {
    ElMessage.warning('正文已改，无法定位')
    return
  }

  revealInEditor(resolved.start, resolved.end)

  const found = previewRef.value?.flashComment?.(rootId)
  if (found === false) {
    ElMessage.warning('正文已改，无法定位')
  }
}

function onWorkspaceKeyDown(e) {
  if (e.key === 'Escape') clearActiveComment()
}

function onWorkspacePointerDown(e) {
  if (activeCommentId.value == null) return
  const t = e.target
  if (!(t instanceof Element)) return
  // Keep active when interacting with marks, panel, dialogs, float bar
  if (
    t.closest(
      '.anno-hl, .anno-bubble, .panel, .anno-float-bar, .el-overlay, .el-dialog, .el-message-box, .el-message'
    )
  ) {
    return
  }
  clearActiveComment()
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
  document.addEventListener('keydown', onWorkspaceKeyDown, true)
  document.addEventListener('pointerdown', onWorkspacePointerDown, true)
})

onBeforeUnmount(() => {
  clearTimeout(saveTimer)
  onPanelResizeEnd()
  document.removeEventListener('keydown', onWorkspaceKeyDown, true)
  document.removeEventListener('pointerdown', onWorkspacePointerDown, true)
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
    content.value = d.content || ''
    lastMappedContent = content.value
    isOwner.value = !!d.is_owner || !!getOwnerSecret(props.docId)
    permission.value = d.permission || (isOwner.value ? 'edit' : 'read')
  }
)
</script>

<style scoped>
.workspace {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-elevated);
}
.top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-subtle);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(8px);
  flex-wrap: wrap;
  min-height: 56px;
}
.left, .right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.back-btn {
  color: var(--text-secondary) !important;
  padding: 6px 8px !important;
}
.title-wrap {
  min-width: 180px;
}
.title-input {
  width: min(360px, 42vw);
}
.title-input :deep(.el-input__wrapper) {
  box-shadow: none !important;
  background: transparent;
  padding-left: 4px;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.02em;
}
.title-input :deep(.el-input__wrapper:hover),
.title-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--border-subtle) inset !important;
  background: var(--bg-muted);
}
.view-switch :deep(.el-radio-button__inner) {
  padding: 6px 12px;
}
.divider {
  width: 1px;
  height: 22px;
  background: var(--border-subtle);
  margin: 0 2px;
}
.save-hint {
  color: var(--text-muted);
  font-size: 12px;
  min-width: 88px;
  padding: 4px 8px;
  border-radius: 999px;
  background: var(--bg-muted);
}
.save-hint.ok {
  color: var(--success);
  background: var(--success-soft);
}
.save-hint.bad {
  color: var(--danger);
  background: var(--danger-soft);
}
/* 中文：主区列布局；批注宽由 --panel-w 固定，不随双栏/仅预览变 */
.main {
  --panel-w: 320px;
  flex: 1;
  display: grid;
  min-height: 0;
  background: var(--bg-page);
}
.main.mode-split {
  grid-template-columns: 1fr 1fr;
}
.main.mode-split.with-panel {
  grid-template-columns: 1fr 1fr 5px var(--panel-w);
}
.main.mode-preview {
  grid-template-columns: 1fr;
}
.main.mode-preview.with-panel {
  grid-template-columns: 1fr 5px var(--panel-w);
}
.editor-pane,
.preview-pane,
.panel {
  min-height: 0;
  overflow: auto;
}
.editor-pane {
  background: #fff;
  border-right: 1px solid var(--border-subtle);
}
.preview-pane {
  background: #fff;
  padding: 28px 32px 48px;
  border-right: 1px solid var(--border-subtle);
}
.main.with-panel .preview-pane,
.main.mode-preview .preview-pane {
  border-right: none;
}
/* 中文：预览|批注拖拽手柄 */
.panel-resizer {
  width: 5px;
  margin: 0;
  padding: 0;
  cursor: col-resize;
  background: transparent;
  position: relative;
  z-index: 2;
  user-select: none;
  touch-action: none;
}
.panel-resizer::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 1px;
  width: 1px;
  background: var(--border-subtle);
}
.panel-resizer:hover::after,
body.is-panel-resizing .panel-resizer::after {
  left: 0;
  width: 3px;
  background: var(--el-color-primary, #409eff);
}
body.is-panel-resizing {
  cursor: col-resize !important;
  user-select: none !important;
}
.panel {
  width: 100%;
  min-width: 0;
  background: var(--bg-sidebar);
  border-right: none;
}
.editor {
  width: 100%;
  height: 100%;
  border: 0;
  outline: none;
  resize: none;
  padding: 28px 28px 48px;
  font-family: var(--font-mono);
  font-size: 14px;
  line-height: 1.7;
  background: #fff;
  color: var(--text-primary);
  tab-size: 2;
}
.editor::placeholder {
  color: var(--text-muted);
}
.editor:disabled {
  background: var(--bg-muted);
  color: var(--text-muted);
}
@media (max-width: 1100px) {
  .preview-pane { padding: 20px 18px 36px; }
  .editor { padding: 20px 18px 36px; }
}
@media (max-width: 960px) {
  .main.mode-split,
  .main.mode-split.with-panel,
  .main.mode-preview,
  .main.mode-preview.with-panel {
    grid-template-columns: 1fr;
  }
  .panel-resizer {
    display: none;
  }
  .editor-pane,
  .preview-pane {
    border-right: none;
    border-bottom: 1px solid var(--border-subtle);
    min-height: 42vh;
  }
  .title-input { width: min(240px, 55vw); }
}
</style>
