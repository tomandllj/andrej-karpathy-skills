<template>
  <div class="home">
    <header class="topnav">
      <div class="brand">
        <span class="logo" aria-hidden="true">MD</span>
        <div class="brand-text">
          <strong>文档协助</strong>
          <span>Markdown · 分享链接 · 实时批注</span>
        </div>
      </div>
      <div class="actions">
        <el-input
          v-model="keyword"
          clearable
          placeholder="搜索本机文档…"
          class="search"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" class="cta" @click="onCreate">
          <el-icon class="el-icon--left"><Plus /></el-icon>
          新建文档
        </el-button>
      </div>
    </header>

    <section class="hero">
      <div class="hero-copy">
        <h1>像文档产品一样写作与协作</h1>
        <p class="sub">
          双栏编辑与预览、选中批注、分享权限、版本回滚与 Mermaid，面向评审与同步写作。
        </p>
      </div>
      <div class="hero-stats">
        <div class="stat">
          <strong>{{ docs.length }}</strong>
          <span>本机文档</span>
        </div>
        <div class="stat">
          <strong>3</strong>
          <span>分享权限</span>
        </div>
        <div class="stat">
          <strong>WS</strong>
          <span>实时同步</span>
        </div>
      </div>
    </section>

    <section class="library">
      <div class="section-head">
        <div>
          <h2>本机文档</h2>
        </div>
        <el-tag effect="plain" round type="info">局域网也可访问</el-tag>
      </div>

      <div v-if="!filtered.length" class="empty">
        <div class="empty-art" aria-hidden="true">
          <div class="sheet s1"></div>
          <div class="sheet s2"></div>
          <div class="sheet s3"></div>
        </div>
        <h3>{{ keyword ? '没有匹配的文档' : '还没有文档' }}</h3>
        <p>{{ keyword ? '试试其他关键词，或新建一份空白文档。' : '创建第一份文档，即可开始双栏写作与批注协作。' }}</p>
        <el-button type="primary" @click="onCreate">
          <el-icon class="el-icon--left"><Plus /></el-icon>
          新建文档
        </el-button>
      </div>

      <div v-else class="grid">
        <article
          v-for="row in filtered"
          :key="row.id"
          class="doc-card"
          @click="openDoc(row)"
        >
          <div class="doc-icon" aria-hidden="true">📄</div>
          <div class="doc-body">
            <h3>{{ row.title || '无标题文档' }}</h3>
            <p class="meta">
              <span>#{{ row.id }}</span>
              <span>·</span>
              <span>{{ formatTime(row.updated_at || row.saved_at) }}</span>
            </p>
          </div>
          <div class="doc-actions" @click.stop>
            <el-button text type="primary" @click="openDoc(row)">打开</el-button>
            <el-button text type="danger" @click="onRemove(row)">删除</el-button>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { createDoc, deleteDoc, fetchDocList } from '@/api/doc'
import {
  listLocalDocs,
  removeLocalDoc,
  saveLocalDoc,
} from '@/utils/localDocs'

const router = useRouter()
const keyword = ref('')
const docs = ref([])

const filtered = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return docs.value
  return docs.value.filter((d) => (d.title || '').toLowerCase().includes(q))
})

function formatTime(v) {
  if (!v) return '刚刚'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  return d.toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function refresh() {
  const local = listLocalDocs()
  if (!local.length) {
    docs.value = []
    return
  }
  try {
    const remote = await fetchDocList(local.map((d) => d.id))
    const map = new Map(remote.map((r) => [r.id, r]))
    docs.value = local
      .map((l) => {
        const r = map.get(l.id)
        if (!r) return null
        return { ...l, ...r }
      })
      .filter(Boolean)
  } catch (e) {
    docs.value = local
    ElMessage.warning('拉取远端列表失败，展示本机缓存')
  }
}

async function onCreate() {
  try {
    const seed = `# 新文档

开始编写…

### 自上而下（TD）

\`\`\`mermaid
flowchart TD
    A[开始] --> B{条件判断}
    B -->|是| C[执行操作]
    B -->|否| D[跳过]
    C --> E[结束]
    D --> E
\`\`\`
`
    const doc = await createDoc({ title: '无标题文档', content: seed })
    saveLocalDoc({ id: doc.id, owner_secret: doc.owner_secret, title: doc.title })
    ElMessage.success('已创建')
    router.push(`/doc/${doc.id}`)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '创建失败')
  }
}

function openDoc(row) {
  router.push(`/doc/${row.id}`)
}

async function onRemove(row) {
  try {
    await ElMessageBox.confirm(`确认软删除「${row.title}」？`, '删除文档', { type: 'warning' })
    await deleteDoc(row.id)
    removeLocalDoc(row.id)
    ElMessage.success('已删除')
    await refresh()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

onMounted(refresh)
</script>

<style scoped>
.home {
  min-height: 100%;
  max-width: 1080px;
  margin: 0 auto;
  padding: 28px 28px 64px;
}

.topnav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 28px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.logo {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #fff;
  background: linear-gradient(145deg, #6366f1 0%, #4f46e5 55%, #4338ca 100%);
  box-shadow: 0 8px 20px rgba(79, 70, 229, 0.28);
  flex-shrink: 0;
}
.brand-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.brand-text strong {
  font-size: 16px;
  letter-spacing: -0.02em;
}
.brand-text span {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.search {
  width: 240px;
}
.cta {
  height: 36px;
  padding: 0 16px;
  border-radius: 10px;
}

.hero {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 20px;
  padding: 28px;
  border-radius: 18px;
  background:
    radial-gradient(1200px 280px at 10% -20%, rgba(99, 102, 241, 0.18), transparent 55%),
    linear-gradient(180deg, #ffffff 0%, #fbfaf8 100%);
  border: 1px solid var(--border-subtle);
  box-shadow: var(--shadow-sm);
  margin-bottom: 28px;
}
.hero h1 {
  margin: 0 0 10px;
  font-size: 28px;
  line-height: 1.25;
  letter-spacing: -0.03em;
  font-weight: 700;
}
.sub {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14.5px;
  max-width: 46ch;
}
.hero-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  align-content: center;
}
.stat {
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 14px 12px;
  text-align: center;
}
.stat strong {
  display: block;
  font-size: 20px;
  letter-spacing: -0.03em;
  color: var(--text-primary);
}
.stat span {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-muted);
}

.library {
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  box-shadow: var(--shadow-sm);
  padding: 22px 22px 18px;
}
.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}
.section-head h2 {
  margin: 0;
  font-size: 16px;
  letter-spacing: -0.01em;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.doc-card {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px;
  border-radius: 12px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-sidebar);
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}
.doc-card:hover {
  border-color: rgba(79, 70, 229, 0.28);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
  background: #fff;
}
.doc-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border: 1px solid var(--border-subtle);
  flex-shrink: 0;
}
.doc-body {
  flex: 1;
  min-width: 0;
}
.doc-body h3 {
  margin: 2px 0 6px;
  font-size: 14.5px;
  font-weight: 600;
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.meta {
  margin: 0;
  display: flex;
  gap: 6px;
  color: var(--text-muted);
  font-size: 12px;
}
.doc-actions {
  display: flex;
  flex-direction: column;
  gap: 2px;
  opacity: 0.7;
}
.doc-card:hover .doc-actions { opacity: 1; }

.empty {
  text-align: center;
  padding: 48px 20px 40px;
}
.empty-art {
  width: 120px;
  height: 88px;
  margin: 0 auto 18px;
  position: relative;
}
.sheet {
  position: absolute;
  left: 50%;
  width: 72px;
  height: 88px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid var(--border-subtle);
  box-shadow: var(--shadow-sm);
}
.sheet.s1 { transform: translateX(-62%) rotate(-8deg); top: 4px; background: #eef2ff; }
.sheet.s2 { transform: translateX(-38%) rotate(4deg); top: 0; }
.sheet.s3 {
  transform: translateX(-50%);
  top: 8px;
  background: linear-gradient(180deg, #fff 0%, #f7f6f3 100%);
}
.sheet.s3::before,
.sheet.s3::after {
  content: '';
  position: absolute;
  left: 14px;
  right: 14px;
  height: 6px;
  border-radius: 3px;
  background: rgba(55, 53, 47, 0.08);
}
.sheet.s3::before { top: 22px; }
.sheet.s3::after { top: 36px; width: 55%; }
.empty h3 {
  margin: 0 0 6px;
  font-size: 17px;
  letter-spacing: -0.02em;
}
.empty p {
  margin: 0 0 18px;
  color: var(--text-muted);
  font-size: 13.5px;
}

@media (max-width: 860px) {
  .home { padding: 18px 16px 48px; }
  .hero { grid-template-columns: 1fr; padding: 20px; }
  .hero h1 { font-size: 24px; }
  .hero-stats { grid-template-columns: repeat(3, 1fr); }
  .search { width: 180px; }
  .brand-text span { display: none; }
}
</style>
