<template>
  <div class="workspace">
    <header class="top">
      <div class="left">
        <el-button class="back-btn" text @click="$router.push('/')">
          <el-icon class="el-icon--left"><ArrowLeft /></el-icon>
          返回
        </el-button>
        <el-tag size="small" effect="plain" round :type="permTagType">{{ permLabel }}</el-tag>
        <el-tag v-if="isOwner" size="small" effect="light" round type="success">创建人</el-tag>
        <el-radio-group v-model="viewMode" size="small" class="view-switch">
          <el-radio-button value="split">双栏</el-radio-button>
          <el-radio-button value="preview">仅预览</el-radio-button>
        </el-radio-group>
        <el-button-group class="action-group">
          <el-button v-if="isOwner" size="small" @click="shareVisible = true">分享</el-button>
          <el-button v-if="isOwner" size="small" @click="versionVisible = true">版本</el-button>
          <el-button size="small" @click="onExport">导出</el-button>
        </el-button-group>
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
          @click="reportEditorCaret"
          @keyup="reportEditorCaret"
        />
        <!-- 中文：分享页来的人的光标，名字和颜色按人区分 -->
        <div class="peer-overlay" aria-hidden="true">
          <div
            v-for="c in editorCursorPos"
            :key="c.key"
            class="peer-caret-editor"
            :style="{ left: c.left + 'px', top: c.top + 'px', height: c.height + 'px', '--peer-color': c.color }"
          >
            <span class="peer-name">{{ c.name }}</span>
          </div>
        </div>
      </div>
      <div class="preview-pane" ref="previewPane" @mouseup="onPreviewCaretMouseUp">
        <MdPreview
          ref="previewRef"
          :markdown="content"
          :comments="comments"
          :allow-select="canComment"
          :active-comment-id="activeCommentId"
          :peer-cursors="peerCursors"
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
          :can-resolve="canComment"
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

    <el-dialog
      v-model="commentDialog"
      title="添加批注"
      width="420px"
      destroy-on-close
      @opened="focusCommentInput"
    >
      <el-form label-position="top">
        <el-form-item label="选中原文">
          <!-- 中文：只展示选中内容，禁止修改并灰显 -->
          <el-input type="textarea" :model-value="pending?.selected_text" disabled :rows="2" />
        </el-form-item>
        <el-form-item label="昵称">
          <!-- 中文：署名固定为登录用户名，禁止修改并灰显 -->
          <el-input :model-value="anonName" disabled />
        </el-form-item>
        <el-form-item label="批注内容">
          <el-input
            ref="commentInputRef"
            v-model="commentText"
            type="textarea"
            :rows="3"
            placeholder="写下你的意见"
            @keydown="onCommentKeydown"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="commentDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitComment">提交</el-button>
      </template>
    </el-dialog>

    <!-- 中文：在线协作者悬浮卡；作者页和分享页都显示，online 关时隐藏 -->
    <div v-if="onlineEnabled && onlineCount" class="online-widget">
      <button
        v-if="!onlineOpen"
        type="button"
        class="online-badge"
        title="在线协作者"
        @click="onlineOpen = true"
      >
        <el-icon :size="14"><User /></el-icon>
        <span>{{ onlineCount }}</span>
      </button>
      <div v-else class="online-card">
        <div class="online-head">
          <span>在线 {{ onlineCount }}</span>
          <button type="button" class="online-close" @click="onlineOpen = false">收起</button>
        </div>
        <div v-for="u in onlineList" :key="u.key" class="online-row">
          <span class="online-dot" :style="{ background: u.color }"></span>
          <span class="online-name">{{ u.name }}</span>
          <span class="online-time">{{ formatPeerTime(u.joinedAt) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/** 文档工作区：双栏编辑/预览、批注侧栏与分享版本入口。 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, User } from '@element-plus/icons-vue'
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
  renameRecentDoc,
  saveLocalDoc,
} from '@/utils/localDocs'
import { adminMe, getLastUsername } from '@/api/admin'
import { titleFromContent } from '@/utils/docTitle'
import { fetchFeatureFlags } from '@/api/features'
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
const commentDialog = ref(false)
const pending = ref(null)
// 中文：批注署名固定用登录用户名，禁止自行修改
const anonName = ref(getLastUsername() || getAnonName())
/** 在线列表展示名：登录后取 /me 的真实名（管理员显示「管理员」，普通用户显示用户名）。 */
const displayName = ref(anonName.value)

/** 拉取当前登录者的展示名，供在线列表和光标标注使用。 */
async function loadDisplayName() {
  try {
    const { data } = await adminMe()
    if (data?.name) displayName.value = data.name
  } catch {
    /* 未登录或失败时保留本地名 */
  }
}
const commentText = ref('')
const commentInputRef = ref(null)
const submitting = ref(false)
const clientKey = getClientKey()
const previewRef = ref(null)
const editorRef = ref(null)
const commentPanelRef = ref(null)
const previewPane = ref(null)
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
const canComment = computed(() => isOwner.value || permission.value === 'comment' || permission.value === 'edit')
/** 是否分享页视角：光标绘制只在作者页，分享页只上报。 */
const isShare = computed(() => props.mode === 'share')
/** config.ini 功能开关，默认开；onMounted 时拉取。 */
const oncursorEnabled = ref(true)
const onlineEnabled = ref(true)
const permLabel = computed(() => {
  if (isOwner.value) return '可管理'
  return { read: '只读', comment: '仅评论', edit: '可编辑' }[permission.value] || '未知'
})
const permTagType = computed(() => {
  if (isOwner.value) return 'success'
  return { read: 'info', comment: 'warning', edit: 'primary' }[permission.value] || 'info'
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

/** 保存正文，并把标题写成正文第一行。成功返回 true。 */
async function doSave() {
  if (!canEditContent.value) return false
  try {
    const nextTitle = titleFromContent(content.value)
    const data = await updateDoc(
      props.docId,
      { title: nextTitle, content: content.value },
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
      renameRecentDoc(props.docId, data.title)
    }
    return true
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
    return false
  }
}

/** 立刻保存当前正文，并提示是否成功。 */
async function saveNow() {
  clearTimeout(saveTimer)
  saveTimer = null
  if (!canEditContent.value) {
    ElMessage.warning('当前权限不可保存')
    return
  }
  const ok = await doSave()
  if (ok) ElMessage.success('已保存')
}

/** 弹窗打开后，把光标放到批注内容里。 */
function focusCommentInput() {
  nextTick(() => {
    commentInputRef.value?.focus()
  })
}

/** 批注框里回车提交，Shift+回车换行。输入法选词时的回车不提交。 */
function onCommentKeydown(e) {
  if (e.key !== 'Enter' || e.shiftKey || e.isComposing || e.keyCode === 229) return
  e.preventDefault()
  if (submitting.value) return
  submitComment()
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

/** 改批注正文；若打开后别人先改过，则提示冲突并重拉，不覆盖。 */
async function onEditComment(comment) {
  const expectedUpdatedAt = comment.updated_at || ''
  try {
    const { value } = await ElMessageBox.prompt('修改批注内容', '编辑批注', {
      inputValue: comment.content,
      inputType: 'textarea',
    })
    await updateComment(
      props.docId,
      comment.id,
      {
        content: value,
        client_key: clientKey,
        expected_updated_at: expectedUpdatedAt,
      },
      { shareToken: props.shareToken }
    )
    await reloadComments()
  } catch (e) {
    if (e === 'cancel') return
    if (e?.response?.status === 409) {
      ElMessage.warning(e?.response?.data?.detail || '该批注已被他人修改，请刷新后重试')
      await reloadComments()
      return
    }
    ElMessage.error(e?.response?.data?.detail || '修改失败')
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
 * 分享视角点击时，同步把光标报到该批注的锚点位置。
 */
async function focusComment(id) {
  if (id == null) return
  const rootId = resolveRootId(id)
  const root = comments.value.find((c) => Number(c.id) === Number(rootId))

  // 中文：分享页在批注栏（或气泡、高亮）点这条时，作者页光标也指到这里
  if (isShare.value && root && Number.isFinite(Number(root.offset_start)) && root.offset_start >= 0) {
    reportCursorOffset(Number(root.offset_start))
  }

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

/** 文档打开时的快捷键：Esc 取消选中，Ctrl+S 立刻保存。 */
function onWorkspaceKeyDown(e) {
  if (e.key === 'Escape') clearActiveComment()
  if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === 's') {
    e.preventDefault()
    e.stopPropagation()
    if (!e.repeat) saveNow()
  }
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

/** 用回滚后的正文替换编辑区，标题改成正文第一行。 */
function onRestored(doc) {
  content.value = doc.content || ''
  reloadComments()
  const nextTitle = titleFromContent(content.value)
  updateDoc(props.docId, { title: nextTitle }, { shareToken: props.shareToken })
    .then((data) => {
      if (!isOwner.value) return
      saveLocalDoc({
        id: props.docId,
        owner_secret: getOwnerSecret(props.docId),
        title: data.title,
      })
      renameRecentDoc(props.docId, data.title)
    })
    .catch((e) => {
      ElMessage.error(e?.response?.data?.detail || '标题保存失败')
    })
}

function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const url = `${proto}://${location.host}/ws/doc/${props.docId}`
  ws = new WebSocket(url)
  ws.onopen = () => {
    // 中文：作者页和分享页都登记上线（online 开时），彼此能看到在线列表
    sendPeerJoin()
  }
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data)
      if (msg.event === 'presence.join') {
        onPeerJoin(msg.data)
        return
      }
      if (msg.event === 'presence.list') {
        onPresenceList(msg.data)
        return
      }
      if (msg.event === 'cursor') {
        onRemoteCursor(msg.data)
        return
      }
      if (msg.event === 'peer.leave') {
        onPeerLeave(msg.data)
        return
      }
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

/** 向文档房间登记上线（连接时和心跳时都发）；online 关时不发。 */
let peerHeartbeatTimer = 0
function sendPeerJoin() {
  if (!onlineEnabled.value) return
  if (!ws || ws.readyState !== WebSocket.OPEN) return
  const name = displayName.value || '访客'
  ws.send(
    JSON.stringify({
      event: 'join',
      data: {
        client_key: clientKey,
        name,
      },
    })
  )
  // 中文：服务端不把 join 回发给自己，在线列表里把自己也记上，名字后加 (我)
  const prev = peers.value[clientKey]
  peers.value = {
    ...peers.value,
    [clientKey]: prev
      ? { ...prev, name: `${name} (我)`, ts: Date.now() }
      : {
          name: `${name} (我)`,
          color: peerColorOf(clientKey),
          offset: null,
          joinedAt: Date.now(),
          ts: Date.now(),
        },
  }
}

/* ===== 分享页光标上报（只在分享视角发送） ===== */

/** 光标上报节流间隔。 */
const CURSOR_SEND_MS = 120
let lastCursorSendAt = 0
let cursorSendTimer = 0
let pendingCursorOffset = -1

/** 编辑区点击或按键后，把光标位置报给文档房间。 */
function reportEditorCaret() {
  if (!isShare.value) return
  const el = editorRef.value
  if (!el) return
  reportCursorOffset(el.selectionStart || 0)
}

/** 预览区点击后，把所见位置换算回正文偏移再上报。 */
function onPreviewCaretMouseUp() {
  if (!isShare.value) return
  const offset = previewRef.value?.mdOffsetAtSelection?.(window.getSelection())
  if (Number.isFinite(offset) && offset >= 0) reportCursorOffset(offset)
}

/** 光标上报节流：120ms 内合并，位置变了才发；oncursor 关时短路。 */
function reportCursorOffset(offset) {
  if (!isShare.value || !oncursorEnabled.value) return
  pendingCursorOffset = offset
  const wait = CURSOR_SEND_MS - (Date.now() - lastCursorSendAt)
  if (wait <= 0) flushCursor()
  else {
    clearTimeout(cursorSendTimer)
    cursorSendTimer = setTimeout(flushCursor, wait)
  }
}

/** 真正通过 WebSocket 发送光标。 */
function flushCursor() {
  clearTimeout(cursorSendTimer)
  cursorSendTimer = 0
  if (!ws || ws.readyState !== WebSocket.OPEN) return
  if (pendingCursorOffset < 0) return
  lastCursorSendAt = Date.now()
  ws.send(
    JSON.stringify({
      event: 'cursor',
      data: {
        client_key: clientKey,
        name: displayName.value || '访客',
        offset: pendingCursorOffset,
      },
    })
  )
}

/* ===== 作者页接收：在线列表 + 光标 ===== */

/** 固定 8 色，按 client_key 哈希取色，重名也能分开。 */
const PEER_COLORS = ['#e11d48', '#2563eb', '#16a34a', '#d97706', '#7c3aed', '#0891b2', '#db2777', '#65a30d']
/** 在线协作者表：client_key → { name, color, offset, joinedAt, ts }。 */
const peers = ref({})
/** 有光标位置的协作者，传给预览和编辑区叠加层；oncursor 关时恒为空。 */
const peerCursors = computed(() => {
  if (!oncursorEnabled.value) return []
  return Object.entries(peers.value)
    .filter(([, c]) => c.offset != null)
    .map(([key, c]) => ({ key, ...c }))
})
/** 在线人数。 */
const onlineCount = computed(() => Object.keys(peers.value).length)
/** 在线列表，按加入先后排序。 */
const onlineList = computed(() =>
  Object.entries(peers.value)
    .map(([key, c]) => ({ key, ...c }))
    .sort((x, y) => x.joinedAt - y.joinedAt)
)
/** 悬浮卡是否展开。 */
const onlineOpen = ref(false)
/** 编辑区光标像素位置。 */
const editorCursorPos = ref([])

/** 按 client_key 决定光标颜色。 */
function peerColorOf(key) {
  let h = 0
  for (const ch of String(key || '')) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return PEER_COLORS[h % PEER_COLORS.length]
}

/** 收到某人上线：新人建档，老人只续期；不动光标和加入时间。自己的回声也标 (我)。 */
function onPeerJoin(data) {
  if (!data?.client_key) return
  const key = data.client_key
  let name = String(data.name || '访客').slice(0, 12)
  if (key === clientKey) name = `${name} (我)`
  const prev = peers.value[key]
  const next = { ...peers.value }
  next[key] = prev
    ? { ...prev, name, ts: Date.now() }
    : { name, color: peerColorOf(key), offset: null, joinedAt: Date.now(), ts: Date.now() }
  peers.value = next
}

/** 收到某人光标：新增或按人覆盖；只在作者页维护（分享页不画别人的光标），自己的不画。 */
function onRemoteCursor(data) {
  if (isShare.value || !data?.client_key || data.client_key === clientKey) return
  const offset = Number(data.offset)
  if (!Number.isFinite(offset) || offset < 0) return
  const key = data.client_key
  const prev = peers.value[key]
  const next = { ...peers.value }
  next[key] = {
    ...(prev || { color: peerColorOf(key), joinedAt: Date.now() }),
    name: String(data.name || '访客').slice(0, 12),
    offset,
    ts: Date.now(),
  }
  peers.value = next
}

/** 某人断开：移除在线记录和光标；自己 key 的离开是旧连接清理，跳过。 */
function onPeerLeave(data) {
  if (!data?.client_key || data.client_key === clientKey) return
  const next = { ...peers.value }
  delete next[data.client_key]
  peers.value = next
}

/** 连接时服务端推来的当前在线名单：晚进来也能立刻看到所有人。 */
function onPresenceList(data) {
  if (!Array.isArray(data?.peers)) return
  for (const p of data.peers) {
    onPeerJoin(p)
    const offset = Number(p?.offset)
    if (Number.isFinite(offset) && offset >= 0) onRemoteCursor({ ...p, offset })
  }
}

/** 清掉超过 60 秒没动静的协作者（断线漏发离开时兜底）。 */
let peerSweepTimer = 0
function sweepStalePeers() {
  const now = Date.now()
  const next = {}
  let changed = false
  for (const [key, c] of Object.entries(peers.value)) {
    if (now - c.ts <= 60000) next[key] = c
    else changed = true
  }
  if (changed) peers.value = next
}

/** 把时间戳写成 2026.11.06 13:55。 */
function formatPeerTime(ts) {
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}.${pad(d.getMonth() + 1)}.${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

let editorMirror = null

/** 造一个和编辑器同字体的隐形镜像，用来把偏移量成像素。 */
function ensureEditorMirror(editor) {
  const style = getComputedStyle(editor)
  if (!editorMirror || !editorMirror.isConnected) {
    editorMirror = document.createElement('div')
    editorMirror.setAttribute('aria-hidden', 'true')
    editor.parentElement.appendChild(editorMirror)
  }
  const m = editorMirror
  m.className = 'editor-mirror'
  m.style.width = editor.clientWidth + 'px'
  m.style.font = style.font
  m.style.lineHeight = style.lineHeight
  m.style.letterSpacing = style.letterSpacing
  m.style.tabSize = style.tabSize
  m.style.padding = style.padding
  return m
}

/** 把正文偏移量成编辑区内的 left/top 和行高。 */
function measureEditorOffset(editor, mirror, offset) {
  const md = content.value || ''
  mirror.textContent = md.slice(0, Math.min(offset, md.length))
  const marker = document.createElement('span')
  marker.textContent = '\u200b'
  mirror.appendChild(marker)
  const line = parseFloat(getComputedStyle(mirror).lineHeight) || 20
  const base = editor.getBoundingClientRect()
  const rect = marker.getBoundingClientRect()
  return {
    left: Math.max(0, rect.left - base.left),
    top: Math.max(0, rect.top - base.top),
    height: line,
  }
}

/** 按最新远端光标重算编辑区叠加层的位置。 */
function computeEditorCursorPos() {
  const editor = editorRef.value
  if (!editor || viewMode.value !== 'split' || !peerCursors.value.length) {
    editorCursorPos.value = []
    return
  }
  const mirror = ensureEditorMirror(editor)
  const out = []
  for (const c of peerCursors.value) {
    const pos = measureEditorOffset(editor, mirror, c.offset)
    out.push({ key: c.key, name: c.name, color: c.color, ...pos })
  }
  editorCursorPos.value = out
}

/** 窗口尺寸变了要重新量光标位置。 */
function onPeerResize() {
  computeEditorCursorPos()
}

onMounted(async () => {
  // persist owner secret if present from create flow already in localStorage
  if (isOwner.value && getOwnerSecret(props.docId)) {
    saveLocalDoc({
      id: props.docId,
      owner_secret: getOwnerSecret(props.docId),
      title: props.initialDoc.title || titleFromContent(content.value),
    })
  }
  if (!canEditContent.value) viewMode.value = 'preview'
  await reloadComments()
  // 中文：连房间前先拿到登录者的真实展示名，上线登记和光标都用它
  await loadDisplayName()
  // 中文：先拉功能开关再连房间，避免开关关了还发 join / 光标
  try {
    const flags = await fetchFeatureFlags()
    oncursorEnabled.value = flags.oncursor
    onlineEnabled.value = flags.online
  } catch {
    /* 拉不到就按默认全开 */
  }
  connectWs()
  peerSweepTimer = window.setInterval(sweepStalePeers, 30000)
  peerHeartbeatTimer = window.setInterval(sendPeerJoin, 25000)
  window.addEventListener('resize', onPeerResize)
  document.addEventListener('keydown', onWorkspaceKeyDown, true)
  document.addEventListener('pointerdown', onWorkspacePointerDown, true)
})

onBeforeUnmount(() => {
  clearTimeout(saveTimer)
  clearTimeout(cursorSendTimer)
  clearInterval(peerSweepTimer)
  clearInterval(peerHeartbeatTimer)
  onPanelResizeEnd()
  window.removeEventListener('resize', onPeerResize)
  document.removeEventListener('keydown', onWorkspaceKeyDown, true)
  document.removeEventListener('pointerdown', onWorkspacePointerDown, true)
  if (editorMirror) {
    editorMirror.remove()
    editorMirror = null
  }
  if (ws) {
    ws.onclose = null
    ws.close()
  }
})

/* 中文：协作者、正文或视图变化后重算编辑区叠加位置 */
watch([peers, content, viewMode], () => computeEditorCursorPos(), { flush: 'post' })

watch(
  () => props.initialDoc,
  (d) => {
    if (!d) return
    content.value = d.content || ''
    lastMappedContent = content.value
    isOwner.value = !!d.is_owner || !!getOwnerSecret(props.docId)
    permission.value = d.permission || (isOwner.value ? 'edit' : 'read')
  }
)
</script>

<style scoped>
/* 中文：工作区壳层 — Teal Flat 顶栏与双栏画布 */
.workspace {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-elevated);
}
/* 中文：右下角在线协作者悬浮卡 */
.online-widget {
  position: absolute;
  right: 16px;
  bottom: 16px;
  z-index: 30;
}
.online-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 32px;
  padding: 0 12px;
  border: 0;
  border-radius: 16px;
  background: var(--accent);
  color: #fff;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: var(--shadow-md, 0 4px 16px rgba(15, 15, 15, 0.12));
}
.online-badge:hover {
  opacity: 0.9;
}
.online-card {
  min-width: 230px;
  max-width: 300px;
  padding: 8px 0 6px;
  border-radius: 12px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-elevated);
  box-shadow: var(--shadow-md, 0 4px 16px rgba(15, 15, 15, 0.12));
}
.online-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 12px 8px;
  font-size: 12px;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border-subtle);
}
.online-close {
  border: 0;
  background: transparent;
  color: var(--accent);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}
.online-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  font-size: 13px;
}
.online-dot {
  flex: none;
  width: 8px;
  height: 8px;
  border-radius: 999px;
}
.online-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-body);
}
.online-time {
  margin-left: auto;
  flex: none;
  font-size: 12px;
  color: var(--text-muted);
}
.top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px 12px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-subtle);
  background: var(--bg-elevated);
  flex-wrap: wrap;
}
.left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1 1 100%;
  min-width: 0;
}
.view-switch,
.action-group {
  flex: none;
}
/* 中文：返回固定在顶栏最左，不往右推 */
.back-btn {
  flex: none;
  color: var(--text-secondary) !important;
  padding: 4px 8px !important;
  height: 28px;
}
.view-switch :deep(.el-radio-button__inner) {
  padding: 6px 12px;
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
  position: relative;
  background: var(--bg-elevated);
  border-right: 1px solid var(--border-subtle);
}
/* 中文：远端光标叠加层，不挡编辑操作 */
.peer-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 3;
}
/* 中文：镜像只用来量位置，永远不可见 */
.editor-mirror {
  position: absolute;
  top: 0;
  left: 0;
  visibility: hidden;
  white-space: pre-wrap;
  overflow-wrap: break-word;
  box-sizing: border-box;
  pointer-events: none;
}
.peer-caret-editor {
  position: absolute;
  width: 2px;
  margin-left: -1px;
  border-radius: 1px;
  background: var(--peer-color, #e11d48);
}
.peer-caret-editor .peer-name {
  position: absolute;
  left: -1px;
  bottom: calc(100% + 2px);
  padding: 1px 6px;
  font-size: 11px;
  line-height: 1.4;
  font-family: var(--font-sans, inherit);
  white-space: nowrap;
  color: #fff;
  background: var(--peer-color, #e11d48);
  border-radius: 4px;
}
.preview-pane {
  background: var(--bg-elevated);
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
  background: var(--accent);
}
body.is-panel-resizing {
  cursor: col-resize !important;
  user-select: none !important;
}
.panel {
  width: 100%;
  min-width: 0;
  background: var(--sidebar-bg);
  border-left: 1px solid var(--sidebar-border);
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
  background: var(--bg-elevated);
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
  .panel {
    border-left: none;
  }
}
</style>
