<template>
  <div
    class="preview-body"
    ref="root"
    @mouseup="onMouseUp"
    v-html="html"
  />

  <Teleport to="body">
    <div
      v-if="floatVisible"
      class="anno-float-bar"
      ref="floatBar"
      :style="floatStyle"
      role="toolbar"
      aria-label="选区操作"
      @mousedown.prevent
    >
      <button type="button" class="anno-float-btn" @click="onAddComment">
        <span class="anno-float-icon" aria-hidden="true">💬</span>
        批注
      </button>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  annotateOffsets,
  preprocessMermaid,
  renderMarkdown,
  renderMermaidIn,
} from '@/utils/markdown'

const props = defineProps({
  markdown: { type: String, default: '' },
  comments: { type: Array, default: () => [] },
  allowSelect: { type: Boolean, default: false },
  activeCommentId: { type: [Number, String], default: null },
  peerCursors: { type: Array, default: () => [] },
})

const emit = defineEmits(['select-text', 'bubble-click'])

/** Markdown 预览：渲染正文、高亮批注，并处理选区浮条。 */
const root = ref(null)
const floatBar = ref(null)
const html = ref('')
const floatVisible = ref(false)
const floatPos = ref({ top: 0, left: 0 })
const pendingSelection = ref(null)

/** 预览刷新代数：增大后丢弃进行中的 Mermaid 渲染。 */
let refreshGen = 0
/** 正文变更后的防抖定时器。 */
let refreshTimer = null
const REFRESH_DEBOUNCE_MS = 150

const floatStyle = computed(() => ({
  top: `${floatPos.value.top}px`,
  left: `${floatPos.value.left}px`,
}))

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function parseAnnoIds(el) {
  return (el.getAttribute('data-anno-ids') || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

/** Exact id match — avoids `*=` matching 1 inside 11 / 21. */
function findAnnoEls(id) {
  if (!root.value || id == null || id === '') return []
  const target = String(id)
  return [...root.value.querySelectorAll('.anno-hl, .anno-bubble')].filter((el) =>
    parseAnnoIds(el).includes(target)
  )
}

function syncActiveClass() {
  if (!root.value) return
  root.value.querySelectorAll('.anno-hl.active, .anno-bubble.active').forEach((el) => {
    el.classList.remove('active')
  })
  for (const el of findAnnoEls(props.activeCommentId)) {
    el.classList.add('active')
  }
}

/**
 * Apply highlight markers into HTML by wrapping exact selected_text occurrences
 * that still match current markdown offsets. Uses data-anno-ids for focus.
 */
function applyHighlights(mdHtml, md, comments) {
  const groups = annotateOffsets(md, comments).filter((g) => !g.lost && g.selected_text)
  if (!groups.length) return mdHtml

  // Sort longer first to reduce partial overlaps mishandling
  const sorted = [...groups].sort((a, b) => b.selected_text.length - a.selected_text.length)
  let out = mdHtml
  for (const g of sorted) {
    const needle = escapeHtml(g.selected_text)
    if (!needle) continue
    const ids = g.ids.join(',')
    const count = g.ids.length
    const resolvedCls = g.all_resolved ? ' is-resolved' : ''
    const replacement =
      `<mark class="anno-hl${resolvedCls}" data-anno-ids="${ids}">${needle}</mark>` +
      `<span class="anno-bubble${resolvedCls}" data-anno-ids="${ids}" title="${g.all_resolved ? '已解决' : '批注'}">💬${count}</span>`
    // replace first plain occurrence not already inside a mark
    const idx = out.indexOf(needle)
    if (idx >= 0) {
      // crude check: skip if already marked nearby
      const before = out.slice(Math.max(0, idx - 40), idx)
      if (before.includes('anno-hl')) continue
      out = out.slice(0, idx) + replacement + out.slice(idx + needle.length)
    }
  }
  return out
}

/** 立即刷新预览 HTML 与 Mermaid；过期代数的结果直接丢弃。 */
async function refresh() {
  const gen = ++refreshGen
  const pre = preprocessMermaid(props.markdown)
  let rendered = renderMarkdown(pre)
  rendered = applyHighlights(rendered, props.markdown, props.comments)
  html.value = rendered
  await nextTick()
  if (gen !== refreshGen) return
  await renderMermaidIn(root.value, { isCancelled: () => gen !== refreshGen })
  if (gen !== refreshGen) return
  bindBubbles()
  syncActiveClass()
  drawPeerCarets()
}

/** 防抖调度预览刷新，避免连续输入时反复跑 Mermaid。 */
function scheduleRefresh() {
  dismissFloat()
  clearTimeout(refreshTimer)
  refreshTimer = setTimeout(() => {
    refreshTimer = null
    refresh()
  }, REFRESH_DEBOUNCE_MS)
}

function bindBubbles() {
  if (!root.value) return
  root.value.querySelectorAll('.anno-bubble, .anno-hl').forEach((el) => {
    el.onclick = (e) => {
      e.stopPropagation()
      const ids = parseAnnoIds(el).map(Number).filter((n) => Number.isFinite(n) && n > 0)
      // Multi-ids on one mark: activate first id (bubble / mark share the same list)
      if (ids[0]) emit('bubble-click', ids[0])
    }
  })
}

/* ===== 正文与预览文字的顺序对齐（重复文本也不会配错位置） ===== */

/** 收集预览可见文字和文本节点表；跳过批注气泡、Mermaid 图和光标自身。 */
function collectPreviewText(rootEl) {
  const walker = document.createTreeWalker(rootEl, NodeFilter.SHOW_TEXT, {
    acceptNode(n) {
      const p = n.parentElement
      if (!p || p.closest('.anno-bubble, .mermaid, svg, .peer-caret')) {
        return NodeFilter.FILTER_REJECT
      }
      return NodeFilter.FILTER_ACCEPT
    },
  })
  let text = ''
  const nodes = []
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const len = n.textContent.length
    nodes.push({ node: n, len })
    text += n.textContent
  }
  return { text, nodes }
}

/**
 * 按顺序对齐 Markdown 与可见文字，返回双向下标表：
 * mdToVis[i] = 正文第 i 个字符处对应可见文字位置；visToMd 反之。
 * 正文里被渲染吃掉的字符（井号、星号、换行等）只推进正文侧。
 */
function alignMdText(md, vis) {
  const n = md.length
  const m = vis.length
  const mdToVis = new Array(n + 1).fill(0)
  const visToMd = new Array(m + 1).fill(0)
  const isWs = (ch) => /\s/.test(ch || '')
  let i = 0
  let j = 0
  while (i < n || j < m) {
    if (i < n && j < m && md[i] === vis[j]) {
      i++
      j++
    } else if (i < n && isWs(md[i]) && (j >= m || !isWs(vis[j]))) {
      // 中文：正文里的换行和空行在页面上不产生文字
      i++
    } else if (i < n && j < m && !isWs(md[i]) && !isWs(vis[j])) {
      // 中文：井号、星号这类语法字符渲染时被吃掉
      i++
    } else if (j < m && (i >= n || !isWs(md[i]))) {
      // 中文：页面上注入而正文没有的文字（如渲染失败提示）
      j++
    } else {
      i++
      j++
    }
    mdToVis[i] = j
    visToMd[j] = i
  }
  return { mdToVis, visToMd }
}

/** DOM 选区焦点 → 可见文字位置；不在预览文字里返回 -1。 */
function visibleIndexOf(nodes, focusNode, focusOffset) {
  if (!focusNode) return -1
  let node = focusNode
  let offset = focusOffset
  if (node.nodeType !== Node.TEXT_NODE) {
    const child = node.childNodes[offset] || node
    const walker = document.createTreeWalker(child, NodeFilter.SHOW_TEXT)
    const first = walker.nextNode()
    if (!first) return -1
    node = first
    offset = 0
  }
  let acc = 0
  for (const { node: n, len } of nodes) {
    if (n === node) return acc + Math.min(offset, len)
    acc += len
  }
  return -1
}

/** 可见文字位置 → 具体文本节点和节点内偏移。 */
function nodeAtVisIndex(nodes, vi) {
  let acc = 0
  for (const { node, len } of nodes) {
    if (vi <= acc + len) return { node, offset: Math.max(0, vi - acc) }
    acc += len
  }
  const last = nodes[nodes.length - 1]
  return last ? { node: last.node, offset: last.len } : null
}

/** 把浏览器选区焦点换算成正文偏移，供分享页上报光标。 */
function mdOffsetAtSelection(sel) {
  if (!root.value || !sel || !sel.focusNode || !root.value.contains(sel.focusNode)) return -1
  const { text, nodes } = collectPreviewText(root.value)
  if (!nodes.length) return -1
  const vi = visibleIndexOf(nodes, sel.focusNode, sel.focusOffset)
  if (vi < 0) return -1
  const { visToMd } = alignMdText(props.markdown || '', text)
  const md = visToMd[Math.min(vi, text.length)]
  return Number.isFinite(md) && md >= 0 ? md : -1
}

/* ===== 远端光标：把 Markdown 偏移画成预览里的彩色竖线 ===== */

/** 移除已画的远端光标。 */
function clearPeerCarets() {
  if (!root.value) return
  root.value.querySelectorAll('.peer-caret').forEach((el) => el.remove())
}

/** 在文本节点指定位置插入一个光标元素。 */
function insertPeerCaret(node, offset, c) {
  const span = document.createElement('span')
  span.className = 'peer-caret'
  span.style.setProperty('--peer-color', c.color || '#e11d48')
  const line = document.createElement('i')
  line.className = 'peer-caret-line'
  const label = document.createElement('span')
  label.className = 'peer-name'
  label.textContent = c.name || '访客'
  span.append(line, label)
  const range = document.createRange()
  range.setStart(node, Math.min(offset, node.textContent.length))
  range.collapse(true)
  range.insertNode(span)
}

/** 逐个把远端光标插入预览；只做 DOM 定位，不重跑渲染。 */
function drawPeerCarets() {
  clearPeerCarets()
  const rootEl = root.value
  const md = props.markdown || ''
  if (!rootEl || !md || !props.peerCursors.length) return
  const { text, nodes } = collectPreviewText(rootEl)
  if (!nodes.length) return
  const { mdToVis } = alignMdText(md, text)
  for (const c of props.peerCursors) {
    const offset = Number(c.offset)
    if (!Number.isFinite(offset) || offset < 0) continue
    const vi = mdToVis[Math.min(offset, md.length)]
    if (!Number.isFinite(vi) || vi < 0) continue
    const point = nodeAtVisIndex(nodes, Math.min(vi, text.length))
    if (!point) continue
    insertPeerCaret(point.node, point.offset, c)
  }
}

function dismissFloat() {
  floatVisible.value = false
  pendingSelection.value = null
}

function placeFloatNearRect(rect) {
  const barW = 96
  const barH = 40
  const gap = 8
  const vw = window.innerWidth
  const vh = window.innerHeight

  let top = rect.top - barH - gap
  if (top < 8) {
    top = Math.min(rect.bottom + gap, vh - barH - 8)
  }

  let left = rect.left + rect.width / 2 - barW / 2
  left = Math.max(8, Math.min(left, vw - barW - 8))

  floatPos.value = { top, left }
}

/**
 * Map DOM selection back to markdown offsets by searching selected text in md.
 * Prefer exact unique match; if multiple, use first occurrence near caret heuristics.
 * Shows floating bar only — does not open compose UI until user clicks「批注」.
 */
function onMouseUp(e) {
  if (!props.allowSelect) return
  // Ignore mouseup that originated on the float bar itself
  if (floatBar.value && (e.target === floatBar.value || floatBar.value.contains(e.target))) {
    return
  }

  const sel = window.getSelection()
  if (!sel || sel.isCollapsed || !root.value) {
    dismissFloat()
    return
  }
  if (!root.value.contains(sel.anchorNode)) {
    dismissFloat()
    return
  }
  const text = sel.toString().trim()
  if (!text || text.length < 1) {
    dismissFloat()
    return
  }

  const md = props.markdown || ''
  let offset_start = md.indexOf(text)
  if (offset_start < 0) {
    offset_start = md.replace(/\r\n/g, '\n').indexOf(text)
  }
  if (offset_start < 0) {
    dismissFloat()
    return
  }
  const offset_end = offset_start + text.length
  const selected_text = md.slice(offset_start, offset_end)
  const ctxStart = Math.max(0, offset_start - 32)
  const ctxEnd = Math.min(md.length, offset_end + 32)
  pendingSelection.value = {
    selected_text,
    offset_start,
    offset_end,
    context_prefix: md.slice(ctxStart, offset_start),
    context_suffix: md.slice(offset_end, ctxEnd),
  }

  try {
    const range = sel.getRangeAt(0)
    const rect = range.getBoundingClientRect()
    if (rect.width || rect.height) {
      placeFloatNearRect(rect)
      floatVisible.value = true
    } else {
      dismissFloat()
    }
  } catch {
    dismissFloat()
  }
}

function onAddComment() {
  if (!pendingSelection.value) return
  const payload = { ...pendingSelection.value }
  dismissFloat()
  // Clear native selection so the bar doesn't reappear
  const sel = window.getSelection()
  if (sel) sel.removeAllRanges()
  emit('select-text', payload)
}

function onDocMouseDown(e) {
  if (!floatVisible.value) return
  if (floatBar.value && (e.target === floatBar.value || floatBar.value.contains(e.target))) {
    return
  }
  // Any outside click (including restarting a selection in preview) hides the bar;
  // a fresh mouseup with a valid selection will show it again.
  dismissFloat()
}

function onSelectionChange() {
  if (!floatVisible.value) return
  const sel = window.getSelection()
  if (!sel || !sel.rangeCount) return
  if (sel.isCollapsed) return
  if (root.value && sel.anchorNode && !root.value.contains(sel.anchorNode)) {
    dismissFloat()
  }
}

function onKeyDown(e) {
  if (e.key === 'Escape' && floatVisible.value) {
    dismissFloat()
    const sel = window.getSelection()
    if (sel) sel.removeAllRanges()
  }
}

function onScrollOrResize() {
  if (!floatVisible.value) return
  const sel = window.getSelection()
  if (!sel || sel.isCollapsed || !sel.rangeCount) {
    dismissFloat()
    return
  }
  try {
    const rect = sel.getRangeAt(0).getBoundingClientRect()
    placeFloatNearRect(rect)
  } catch {
    dismissFloat()
  }
}

/**
 * Scroll mark to center and pulse flash. Returns false if mark not in DOM (lost).
 */
function flashComment(id) {
  const els = findAnnoEls(id)
  if (!els.length) return false
  const mark = els.find((el) => el.classList.contains('anno-hl')) || els[0]
  mark.scrollIntoView({ behavior: 'smooth', block: 'center' })
  for (const el of els) {
    el.classList.remove('flash')
    void el.offsetWidth
    el.classList.add('flash')
  }
  setTimeout(() => {
    els.forEach((el) => el.classList.remove('flash'))
  }, 1200)
  return true
}

defineExpose({ flashComment, findAnnoEls, mdOffsetAtSelection })

watch(
  () => [props.markdown, props.comments],
  () => {
    scheduleRefresh()
  },
  { deep: true }
)

watch(
  () => props.activeCommentId,
  async () => {
    await nextTick()
    syncActiveClass()
  }
)

watch(
  () => props.allowSelect,
  (v) => {
    if (!v) dismissFloat()
  }
)

/* 中文：远端光标更新只重画竖线，不重跑渲染 */
watch(
  () => props.peerCursors,
  () => drawPeerCarets(),
  { deep: true }
)

onMounted(() => {
  refresh()
  document.addEventListener('mousedown', onDocMouseDown, true)
  document.addEventListener('keydown', onKeyDown, true)
  document.addEventListener('selectionchange', onSelectionChange)
  window.addEventListener('scroll', onScrollOrResize, true)
  window.addEventListener('resize', onScrollOrResize)
})

onBeforeUnmount(() => {
  refreshGen += 1
  clearTimeout(refreshTimer)
  refreshTimer = null
  document.removeEventListener('mousedown', onDocMouseDown, true)
  document.removeEventListener('keydown', onKeyDown, true)
  document.removeEventListener('selectionchange', onSelectionChange)
  window.removeEventListener('scroll', onScrollOrResize, true)
  window.removeEventListener('resize', onScrollOrResize)
})
</script>

<style scoped>
.preview-body {
  min-height: 100%;
}
</style>

<style>
/* Floating selection bar — global so Teleport styles apply */
.anno-float-bar {
  position: fixed;
  z-index: 4000;
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 4px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid var(--border-subtle, rgba(55, 53, 47, 0.09));
  box-shadow: var(--shadow-md, 0 4px 16px rgba(15, 15, 15, 0.06), 0 1px 3px rgba(15, 15, 15, 0.04));
  transform: translateZ(0);
  animation: anno-float-in 0.12s ease-out;
  user-select: none;
}
@keyframes anno-float-in {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.anno-float-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  border: 0;
  border-radius: 8px;
  background: var(--accent-soft, #dbeafe);
  color: var(--accent, #2563eb);
  font-size: 13px;
  font-weight: 600;
  font-family: var(--font-sans, inherit);
  letter-spacing: -0.01em;
  cursor: pointer;
  transition: background 0.12s ease, color 0.12s ease;
}
.anno-float-btn:hover {
  background: var(--accent, #2563eb);
  color: #fff;
}
.anno-float-btn:active {
  background: var(--accent-hover, #1d4ed8);
  color: #fff;
}
.anno-float-icon {
  font-size: 14px;
  line-height: 1;
}

/* 中文：远端光标（v-html 注入的元素，需全局样式） */
.peer-caret {
  position: relative;
  display: inline-block;
  width: 0;
  vertical-align: baseline;
}
.peer-caret-line {
  display: inline-block;
  width: 2px;
  height: 1.2em;
  margin-left: -1px;
  background: var(--peer-color, #e11d48);
  border-radius: 1px;
}
.peer-caret .peer-name {
  position: absolute;
  left: 0;
  bottom: calc(1.2em + 2px);
  padding: 1px 6px;
  font-size: 11px;
  line-height: 1.4;
  white-space: nowrap;
  color: #fff;
  background: var(--peer-color, #e11d48);
  border-radius: 4px;
  pointer-events: none;
  opacity: 0.95;
}
</style>
