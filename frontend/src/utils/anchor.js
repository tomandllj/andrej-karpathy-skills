import { diffChars } from 'diff'

/** 前后文长度，与后端 CONTEXT_MAX 一致。 */
export const CONTEXT_LEN = 32
/** 有前后文时，重合比例须严格高于此才重挂。 */
const MIN_CONTEXT_RATIO = 0.2

/**
 * 从正文裁出引用前后各一段上下文。
 * @param {string} md
 * @param {number} start
 * @param {number} end
 */
export function sliceContext(md, start, end) {
  const text = md || ''
  const s = Math.max(0, Number(start) || 0)
  const e = Math.max(s, Number(end) || 0)
  return {
    context_prefix: text.slice(Math.max(0, s - CONTEXT_LEN), s),
    context_suffix: text.slice(e, Math.min(text.length, e + CONTEXT_LEN)),
  }
}

/**
 * 计算 needle 与实际前后文的重合比例（从贴引用的一侧对齐）。
 * @param {string} expected
 * @param {string} actual
 * @param {'prefix' | 'suffix'} side
 */
function contextOverlapRatio(expected, actual, side) {
  if (!expected) return 1
  if (!actual) return 0
  const n = Math.min(expected.length, actual.length)
  if (n <= 0) return 0
  let matched = 0
  if (side === 'prefix') {
    for (let i = 1; i <= n; i++) {
      if (expected.slice(-i) === actual.slice(-i)) matched = i
      else break
    }
  } else {
    for (let i = 1; i <= n; i++) {
      if (expected.slice(0, i) === actual.slice(0, i)) matched = i
      else break
    }
  }
  return matched / expected.length
}

/**
 * 判断已存前后文与某候选位置是否足够像。
 * @param {string} md
 * @param {number} start
 * @param {number} end
 * @param {string | null | undefined} prefix
 * @param {string | null | undefined} suffix
 */
function contextMatches(md, start, end, prefix, suffix) {
  const hasPrefix = !!(prefix && prefix.length)
  const hasSuffix = !!(suffix && suffix.length)
  if (!hasPrefix && !hasSuffix) return true
  const around = sliceContext(md, start, end)
  let score = 0
  let weight = 0
  if (hasPrefix) {
    score += contextOverlapRatio(prefix, around.context_prefix, 'prefix')
    weight += 1
  }
  if (hasSuffix) {
    score += contextOverlapRatio(suffix, around.context_suffix, 'suffix')
    weight += 1
  }
  return weight > 0 && score / weight > MIN_CONTEXT_RATIO
}

/**
 * 找出 quote 在 md 中的全部起始下标。
 * @param {string} md
 * @param {string} quote
 */
function findAllOccurrences(md, quote) {
  const out = []
  if (!quote) return out
  let from = 0
  while (from <= md.length) {
    const i = md.indexOf(quote, from)
    if (i < 0) break
    out.push(i)
    from = i + Math.max(1, quote.length)
  }
  return out
}

/**
 * 刷新或外部改文后解析批注锚点。
 * @param {string} md
 * @param {{ offset_start?: number, offset_end?: number, selected_text?: string, context_prefix?: string | null, context_suffix?: string | null }} comment
 * @returns {{ start: number, end: number, lost: boolean, selected_text: string }}
 */
export function resolveAnchor(md, comment) {
  const text = md || ''
  const quote = comment?.selected_text || ''
  const start = Number(comment?.offset_start) || 0
  const end = Number(comment?.offset_end) || 0
  const prefix = comment?.context_prefix || ''
  const suffix = comment?.context_suffix || ''
  const hasContext = !!(prefix || suffix)

  if (!quote) {
    return { start, end: start, lost: true, selected_text: '' }
  }

  // 旧偏移处引用仍在，且前后文够像 → 留在原处
  if (end > start && text.slice(start, end) === quote) {
    if (!hasContext || contextMatches(text, start, end, prefix, suffix)) {
      return { start, end, lost: false, selected_text: quote }
    }
  }

  const hits = findAllOccurrences(text, quote)
  if (!hits.length) {
    return { start, end: start, lost: true, selected_text: quote }
  }

  if (hasContext) {
    const scored = hits
      .map((i) => {
        const e = i + quote.length
        const around = sliceContext(text, i, e)
        let sum = 0
        let w = 0
        if (prefix) {
          sum += contextOverlapRatio(prefix, around.context_prefix, 'prefix')
          w += 1
        }
        if (suffix) {
          sum += contextOverlapRatio(suffix, around.context_suffix, 'suffix')
          w += 1
        }
        return {
          i,
          e,
          ratio: w ? sum / w : 1,
          dist: Math.abs(i - start),
        }
      })
      .filter((x) => x.ratio > MIN_CONTEXT_RATIO)
    if (!scored.length) {
      return { start, end: start, lost: true, selected_text: quote }
    }
    scored.sort((a, b) => b.ratio - a.ratio || a.dist - b.dist)
    const best = scored[0]
    return {
      start: best.i,
      end: best.e,
      lost: false,
      selected_text: quote,
    }
  }

  // 旧数据无前后文：唯一出现才重挂；多处取离旧偏移最近
  if (hits.length === 1) {
    const i = hits[0]
    return {
      start: i,
      end: i + quote.length,
      lost: false,
      selected_text: quote,
    }
  }
  let best = hits[0]
  let bestDist = Math.abs(best - start)
  for (const i of hits) {
    const d = Math.abs(i - start)
    if (d < bestDist) {
      best = i
      bestDist = d
    }
  }
  return {
    start: best,
    end: best + quote.length,
    lost: false,
    selected_text: quote,
  }
}

/**
 * 按 diff 把批注区间从旧正文映射到新正文（模拟 Word 起止标记）。
 * @param {string} oldMd
 * @param {string} newMd
 * @param {number} start
 * @param {number} end
 * @returns {{ start: number, end: number, lost: boolean }}
 */
export function mapRangeThroughEdit(oldMd, newMd, start, end) {
  let s = Math.max(0, Number(start) || 0)
  let e = Math.max(s, Number(end) || 0)
  if (e <= s) {
    return { start: s, end: s, lost: true }
  }
  if (oldMd === newMd) {
    return { start: s, end: e, lost: false }
  }

  const parts = diffChars(oldMd || '', newMd || '')
  let oldPos = 0
  let newStart = s
  let newEnd = e

  for (const part of parts) {
    const len = part.value.length
    if (part.added) {
      if (oldPos < s) {
        newStart += len
        newEnd += len
      } else if (oldPos < e) {
        newEnd += len
      }
    } else if (part.removed) {
      const remStart = oldPos
      const remEnd = oldPos + len
      const before = Math.max(0, Math.min(remEnd, s) - remStart)
      const inside = Math.max(0, Math.min(remEnd, e) - Math.max(remStart, s))
      newStart -= before
      newEnd -= before + inside
      oldPos += len
    } else {
      oldPos += len
    }
  }

  if (newEnd <= newStart) {
    return { start: newStart, end: newStart, lost: true }
  }
  return { start: newStart, end: newEnd, lost: false }
}

/**
 * 编辑后更新内存中的根批注锚点；删空则失锚并保留引用快照。
 * @param {object} comment
 * @param {string} oldMd
 * @param {string} newMd
 * @returns {object}
 */
export function applyEditToComment(comment, oldMd, newMd) {
  if (!comment || comment.parent_id) return comment
  const mapped = mapRangeThroughEdit(
    oldMd,
    newMd,
    comment.offset_start,
    comment.offset_end
  )
  if (mapped.lost) {
    return {
      ...comment,
      offset_start: mapped.start,
      offset_end: mapped.end,
      _lost: true,
    }
  }
  const selected = (newMd || '').slice(mapped.start, mapped.end)
  const ctx = sliceContext(newMd, mapped.start, mapped.end)
  const next = {
    ...comment,
    offset_start: mapped.start,
    offset_end: mapped.end,
    selected_text: selected,
    context_prefix: ctx.context_prefix,
    context_suffix: ctx.context_suffix,
    _lost: false,
  }
  if (Array.isArray(comment.replies) && comment.replies.length) {
    next.replies = comment.replies.map((r) => ({
      ...r,
      offset_start: mapped.start,
      offset_end: mapped.end,
      selected_text: selected,
      context_prefix: ctx.context_prefix,
      context_suffix: ctx.context_suffix,
    }))
  }
  return next
}

/**
 * 对批注列表做刷新态解析，写回起止并打 _lost。
 * @param {string} md
 * @param {object[]} comments
 */
export function resolveComments(md, comments) {
  return (comments || []).map((c) => {
    if (c.parent_id) return c
    // 本次编辑已标失锚的，不再全文猜挂
    if (c._lost) return c
    const resolved = resolveAnchor(md, c)
    if (resolved.lost) {
      return { ...c, _lost: true }
    }
    const ctx = sliceContext(md, resolved.start, resolved.end)
    const next = {
      ...c,
      offset_start: resolved.start,
      offset_end: resolved.end,
      selected_text: resolved.selected_text,
      context_prefix: c.context_prefix ?? ctx.context_prefix,
      context_suffix: c.context_suffix ?? ctx.context_suffix,
      _lost: false,
    }
    if (Array.isArray(c.replies) && c.replies.length) {
      next.replies = c.replies.map((r) => ({
        ...r,
        offset_start: resolved.start,
        offset_end: resolved.end,
        selected_text: resolved.selected_text,
        context_prefix: next.context_prefix,
        context_suffix: next.context_suffix,
      }))
    }
    return next
  })
}
