import { marked } from 'marked'
import DOMPurify from 'dompurify'
import mermaid from 'mermaid'
import { resolveAnchor } from './anchor.js'

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

/** 把 Markdown 转成消毒后的 HTML。 */
export function renderMarkdown(md) {
  const raw = marked.parse(md || '')
  return DOMPurify.sanitize(raw, {
    ADD_TAGS: ['iframe'],
    ADD_ATTR: ['target', 'rel'],
  })
}

/** 把 ```mermaid 代码块预处理成待客户端渲染的容器。 */
export function preprocessMermaid(md) {
  return (md || '').replace(/```mermaid\s*([\s\S]*?)```/gi, (_, code) => {
    const safe = code.replace(/</g, '&lt;').replace(/>/g, '&gt;')
    return `\n<div class="mermaid">${safe}</div>\n`
  })
}

/** 移除 mermaid.render 可能残留在 document 上的临时节点。 */
function cleanupMermaidTemp(id) {
  if (!id) return
  document.getElementById(id)?.remove()
  document.getElementById(`d${id}`)?.remove()
}

/**
 * 在容器内把 .mermaid 节点渲染成 SVG。
 * @param {ParentNode | null} el 预览根节点
 * @param {{ isCancelled?: () => boolean }} [opts] 过期渲染可取消
 */
export async function renderMermaidIn(el, opts = {}) {
  if (!el) return
  const isCancelled = typeof opts.isCancelled === 'function' ? opts.isCancelled : () => false
  const nodes = [...el.querySelectorAll('.mermaid')]
  for (const node of nodes) {
    if (isCancelled()) return
    if (node.dataset.processed === '1') continue
    const code = (node.textContent || '').trim()
    if (!code) {
      node.dataset.processed = '1'
      continue
    }
    const id = `mmd-${Date.now()}-${mermaidId++}`
    try {
      const { svg } = await mermaid.render(id, code)
      cleanupMermaidTemp(id)
      if (isCancelled() || !el.contains(node)) return
      node.innerHTML = svg
      node.dataset.processed = '1'
    } catch (err) {
      cleanupMermaidTemp(id)
      if (isCancelled() || !el.contains(node)) return
      node.innerHTML = `<pre style="color:#f56c6c;text-align:left">Mermaid 渲染失败:\n${String(err.message || err)}</pre>`
      node.dataset.processed = '1'
    }
  }
}

/**
 * 按解析后的批注偏移归组；失锚的不参与高亮。
 * 同位置全部为 resolved 时 all_resolved=true（预览用浅绿高亮）。
 */
export function annotateOffsets(md, comments) {
  const roots = (comments || []).filter((c) => !c.parent_id)
  const groups = new Map()
  for (const c of roots) {
    if (c._lost) continue
    const resolved = resolveAnchor(md, c)
    if (resolved.lost) continue
    const key = `${resolved.start}:${resolved.end}`
    if (!groups.has(key)) {
      groups.set(key, {
        offset_start: resolved.start,
        offset_end: resolved.end,
        selected_text: resolved.selected_text,
        lost: false,
        ids: [],
        statuses: [],
      })
    }
    const g = groups.get(key)
    g.ids.push(c.id)
    g.statuses.push(c.status)
  }
  return Array.from(groups.values()).map((g) => {
    const { statuses, ...rest } = g
    return {
      ...rest,
      all_resolved:
        statuses.length > 0 && statuses.every((s) => s === 'resolved'),
    }
  })
}
