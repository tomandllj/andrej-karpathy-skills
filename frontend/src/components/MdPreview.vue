<template>
  <div
    class="preview-body"
    ref="root"
    @mouseup="onMouseUp"
    v-html="html"
  />
</template>

<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
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
})

const emit = defineEmits(['select-text', 'bubble-click'])

const root = ref(null)
const html = ref('')

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
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
    const replacement =
      `<mark class="anno-hl" data-anno-ids="${ids}">${needle}</mark>` +
      `<span class="anno-bubble" data-anno-ids="${ids}" title="批注">💬${count}</span>`
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

async function refresh() {
  const pre = preprocessMermaid(props.markdown)
  let rendered = renderMarkdown(pre)
  rendered = applyHighlights(rendered, props.markdown, props.comments)
  html.value = rendered
  await nextTick()
  await renderMermaidIn(root.value)
  bindBubbles()
}

function bindBubbles() {
  if (!root.value) return
  root.value.querySelectorAll('.anno-bubble, .anno-hl').forEach((el) => {
    el.onclick = (e) => {
      e.stopPropagation()
      const ids = (el.getAttribute('data-anno-ids') || '').split(',').map(Number)
      if (ids[0]) emit('bubble-click', ids[0])
    }
  })
}

/**
 * Map DOM selection back to markdown offsets by searching selected text in md.
 * Prefer exact unique match; if multiple, use first occurrence near caret heuristics.
 */
function onMouseUp() {
  if (!props.allowSelect) return
  const sel = window.getSelection()
  if (!sel || sel.isCollapsed || !root.value) return
  if (!root.value.contains(sel.anchorNode)) return
  const text = sel.toString().trim()
  if (!text || text.length < 1) return

  const md = props.markdown || ''
  let offset_start = md.indexOf(text)
  if (offset_start < 0) {
    // try without collapsing whitespace differences
    offset_start = md.replace(/\r\n/g, '\n').indexOf(text)
  }
  if (offset_start < 0) {
    return
  }
  const offset_end = offset_start + text.length
  emit('select-text', {
    selected_text: md.slice(offset_start, offset_end),
    offset_start,
    offset_end,
  })
  // keep selection briefly so user sees what was picked
}

function flashComment(id) {
  if (!root.value) return
  const el =
    root.value.querySelector(`.anno-hl[data-anno-ids*="${id}"]`) ||
    root.value.querySelector(`.anno-bubble[data-anno-ids*="${id}"]`)
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  el.classList.remove('flash')
  // force reflow
  void el.offsetWidth
  el.classList.add('flash')
  setTimeout(() => el.classList.remove('flash'), 1300)
}

defineExpose({ flashComment })

watch(() => [props.markdown, props.comments], refresh, { deep: true })
onMounted(refresh)
</script>
