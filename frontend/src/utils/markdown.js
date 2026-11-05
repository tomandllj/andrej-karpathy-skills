import { marked } from 'marked'
import DOMPurify from 'dompurify'
import mermaid from 'mermaid'

marked.setOptions({
  gfm: true,
  breaks: true,
})

mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  securityLevel: 'loose',
})

let mermaidId = 0

export function renderMarkdown(md) {
  const raw = marked.parse(md || '')
  return DOMPurify.sanitize(raw, {
    ADD_TAGS: ['iframe'],
    ADD_ATTR: ['target', 'rel'],
  })
}

/** Convert ```mermaid fences into <div class="mermaid"> for client render */
export function preprocessMermaid(md) {
  return (md || '').replace(/```mermaid\s*([\s\S]*?)```/gi, (_, code) => {
    const safe = code.replace(/</g, '&lt;').replace(/>/g, '&gt;')
    return `\n<div class="mermaid">${safe}</div>\n`
  })
}

export async function renderMermaidIn(el) {
  if (!el) return
  const nodes = el.querySelectorAll('.mermaid')
  for (const node of nodes) {
    if (node.dataset.processed === '1') continue
    const code = node.textContent || ''
    const id = `mmd-${Date.now()}-${mermaidId++}`
    try {
      const { svg } = await mermaid.render(id, code)
      node.innerHTML = svg
      node.dataset.processed = '1'
    } catch (err) {
      node.innerHTML = `<pre style="color:#f56c6c;text-align:left">Mermaid 渲染失败:\n${String(err.message || err)}</pre>`
      node.dataset.processed = '1'
    }
  }
}

/**
 * Map markdown char offsets to ranges in rendered preview by matching selected_text snapshots.
 * Phase-1: if current md slice !== selected_text, mark as lost.
 */
export function annotateOffsets(md, comments) {
  const roots = (comments || []).filter((c) => !c.parent_id)
  const groups = new Map()
  for (const c of roots) {
    const key = `${c.offset_start}:${c.offset_end}`
    const slice = (md || '').slice(c.offset_start, c.offset_end)
    const lost = slice !== c.selected_text
    if (!groups.has(key)) {
      groups.set(key, {
        offset_start: c.offset_start,
        offset_end: c.offset_end,
        selected_text: c.selected_text,
        lost,
        ids: [],
      })
    }
    const g = groups.get(key)
    g.ids.push(c.id)
    if (lost) g.lost = true
  }
  return Array.from(groups.values())
}
