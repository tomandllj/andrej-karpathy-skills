<template>
  <div class="panel-inner">
    <div class="panel-title">批注列表</div>
    <el-empty v-if="!comments.length" description="暂无批注，预览区选中文字可添加" :image-size="64" />
    <div v-for="c in comments" :key="c.id" class="card" @click="$emit('focus', c.id)">
      <div class="meta">
        <strong>{{ c.anon_name }}</strong>
        <el-tag size="small" :type="c.status === 'resolved' ? 'success' : 'warning'">
          {{ c.status === 'resolved' ? '已解决' : '待处理' }}
        </el-tag>
      </div>
      <div class="quote">「{{ c.selected_text }}」</div>
      <div v-if="isLost(c)" class="comment-lost">原文位置已丢失，快照：{{ c.selected_text }}</div>
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

      <div v-for="r in c.replies || []" :key="r.id" class="reply">
        <div class="meta">
          <strong>{{ r.anon_name }}</strong>
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
const props = defineProps({
  comments: { type: Array, default: () => [] },
  isOwner: Boolean,
  clientKey: String,
  markdown: { type: String, default: '' },
})

defineEmits(['focus', 'reply', 'resolve', 'remove', 'edit'])

function isLost(c) {
  const slice = (props.markdown || '').slice(c.offset_start, c.offset_end)
  return slice !== c.selected_text
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
</script>

<style scoped>
.panel-inner { padding: 12px; }
.panel-title { font-weight: 600; margin-bottom: 10px; }
.card {
  border: 1px solid #ebeef5; border-radius: 8px; padding: 10px;
  margin-bottom: 10px; background: #fff; cursor: pointer;
}
.card:hover { border-color: #f5a623; }
.meta { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.quote {
  margin: 6px 0; padding: 6px 8px; background: #fafafa; color: #606266;
  font-size: 12px; border-left: 3px solid #f5a623; border-radius: 4px;
}
.body { white-space: pre-wrap; font-size: 14px; }
.time { color: #909399; font-size: 12px; margin-top: 4px; }
.ops { margin-top: 6px; display: flex; gap: 4px; flex-wrap: wrap; }
.reply {
  margin-top: 8px; margin-left: 10px; padding: 8px;
  background: #f8fafc; border-radius: 6px; border: 1px dashed #e4e7ed;
}
</style>
