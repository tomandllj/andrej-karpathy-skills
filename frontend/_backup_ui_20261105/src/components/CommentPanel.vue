<template>
  <div class="panel-inner" ref="panelRoot">
    <div class="panel-head">
      <div>
        <div class="panel-title">批注</div>
        <div class="panel-sub">预览区选中文字后点「批注」</div>
      </div>
      <el-tag size="small" effect="plain" round>{{ comments.length }}</el-tag>
    </div>

    <el-empty
      v-if="!sortedComments.length"
      description="暂无批注"
      :image-size="56"
    />

    <div
      v-for="c in sortedComments"
      :key="c.id"
      class="card"
      :class="{
        active: Number(activeCommentId) === Number(c.id),
        lost: isLost(c),
      }"
      :data-comment-id="c.id"
      @click="$emit('focus', c.id)"
    >
      <div class="meta">
        <div class="who">
          <span class="avatar">{{ (c.anon_name || '匿')[0] }}</span>
          <strong>{{ c.anon_name }}</strong>
        </div>
        <el-tag size="small" effect="light" round :type="c.status === 'resolved' ? 'success' : 'warning'">
          {{ c.status === 'resolved' ? '已解决' : '待处理' }}
        </el-tag>
      </div>
      <div class="quote">「{{ c.selected_text }}」</div>
      <div v-if="isLost(c)" class="comment-lost">原文已删除</div>
      <div class="body">{{ c.content }}</div>
      <div class="time">{{ c.created_at }}</div>
      <div class="ops" @click.stop>
        <el-button link type="primary" size="small" @click="$emit('reply', c)">回复</el-button>
        <el-button
          v-if="canEdit(c)"
          link
          size="small"
          @click="$emit('edit', c)"
        >编辑</el-button>
        <el-button
          v-if="isOwner"
          link
          size="small"
          @click="$emit('resolve', c)"
        >{{ c.status === 'resolved' ? '重开' : '已解决' }}</el-button>
        <el-button
          v-if="canEdit(c)"
          link
          type="danger"
          size="small"
          @click="$emit('remove', c)"
        >删除</el-button>
      </div>

      <div
        v-for="r in c.replies || []"
        :key="r.id"
        class="reply"
        :class="{ active: Number(activeCommentId) === Number(c.id) }"
        @click.stop="$emit('focus', c.id)"
      >
        <div class="meta">
          <div class="who">
            <span class="avatar sm">{{ (r.anon_name || '匿')[0] }}</span>
            <strong>{{ r.anon_name }}</strong>
          </div>
          <span class="time">{{ r.created_at }}</span>
        </div>
        <div class="body">{{ r.content }}</div>
        <div class="ops" @click.stop>
          <el-button v-if="canEdit(r)" link size="small" @click="$emit('edit', r)">编辑</el-button>
          <el-button v-if="canEdit(r)" link type="danger" size="small" @click="$emit('remove', r)">删除</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/** 批注侧栏：按正文位置从上到下展示根批注及其回复。 */
import { computed, nextTick, ref, watch } from 'vue'
import { resolveAnchor } from '@/utils/anchor'

const props = defineProps({
  comments: { type: Array, default: () => [] },
  isOwner: Boolean,
  clientKey: String,
  markdown: { type: String, default: '' },
  activeCommentId: { type: [Number, String], default: null },
})

defineEmits(['focus', 'reply', 'resolve', 'remove', 'edit'])

const panelRoot = ref(null)

/** 有效批注按位置升序，失锚沉底。 */
const sortedComments = computed(() => {
  return [...(props.comments || [])].sort((a, b) => {
    const aLost = isLost(a)
    const bLost = isLost(b)
    if (aLost !== bLost) return aLost ? 1 : -1
    const as = Number(a.offset_start) || 0
    const bs = Number(b.offset_start) || 0
    if (as !== bs) return as - bs
    return (Number(a.id) || 0) - (Number(b.id) || 0)
  })
})

/** 判断批注是否已失锚。 */
function isLost(c) {
  if (!c) return true
  if (c._lost) return true
  return resolveAnchor(props.markdown, c).lost
}

function canEdit(c) {
  if (props.isOwner) return true
  // client_key is not returned from API; front tracks own comment ids in session
  // Fallback: allow attempt — backend enforces. Also match via local owned set.
  return ownedIds.has(c.id)
}

// Track comments created in this browser via localStorage
const OWNED_KEY = 'md_annotate_owned_comments'
function loadOwned() {
  try {
    return new Set(JSON.parse(localStorage.getItem(OWNED_KEY) || '[]'))
  } catch {
    return new Set()
  }
}
const ownedIds = loadOwned()

// Heuristic: when list refreshes, we cannot know ownership from API.
// Store ids when user creates — DocWorkspace should also write; here we expose helper via window event.
if (typeof window !== 'undefined') {
  window.addEventListener('md-annotate-owned', (e) => {
    ownedIds.add(e.detail)
    localStorage.setItem(OWNED_KEY, JSON.stringify([...ownedIds]))
  })
}

function scrollToComment(id) {
  if (!panelRoot.value || id == null) return false
  const el = panelRoot.value.querySelector(`.card[data-comment-id="${id}"]`)
  if (!el) return false
  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  return true
}

watch(
  () => props.activeCommentId,
  async (id) => {
    if (id == null) return
    await nextTick()
    scrollToComment(id)
  }
)

defineExpose({ scrollToComment })
</script>

<style scoped>
.panel-inner {
  padding: 16px 14px 24px;
}
.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 14px;
  padding: 0 2px;
}
.panel-title {
  font-weight: 600;
  font-size: 14px;
  letter-spacing: -0.01em;
}
.panel-sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-muted);
}
.card {
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 10px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}
.card:hover {
  border-color: rgba(79, 70, 229, 0.35);
  box-shadow: var(--shadow-sm);
}
.card.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-ring), var(--shadow-sm);
  background: #fafafe;
}
.card.lost {
  opacity: 0.72;
  background: var(--bg-muted);
}
.meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.who {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.who strong {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(145deg, #818cf8, #4f46e5);
  flex-shrink: 0;
}
.avatar.sm {
  width: 18px;
  height: 18px;
  font-size: 10px;
}
.quote {
  margin: 8px 0;
  padding: 8px 10px;
  background: var(--warning-soft);
  color: var(--text-secondary);
  font-size: 12px;
  border-left: 3px solid #e8b339;
  border-radius: 0 8px 8px 0;
  line-height: 1.45;
}
.body {
  white-space: pre-wrap;
  font-size: 13.5px;
  line-height: 1.55;
  color: var(--text-primary);
}
.time {
  color: var(--text-muted);
  font-size: 11.5px;
  margin-top: 6px;
}
.ops {
  margin-top: 8px;
  display: flex;
  gap: 2px;
  flex-wrap: wrap;
}
.reply {
  margin-top: 10px;
  margin-left: 4px;
  padding: 10px;
  background: var(--bg-muted);
  border-radius: 10px;
  border: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.reply:hover {
  border-color: rgba(79, 70, 229, 0.28);
}
.reply.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent-ring);
}
</style>
