<template>
  <div class="home">
    <header class="bar">
      <h1>MD批注协作平台</h1>
      <div class="actions">
        <el-input
          v-model="keyword"
          clearable
          placeholder="搜索本机文档标题"
          style="width: 240px"
        />
        <el-button type="primary" @click="onCreate">新建文档</el-button>
      </div>
    </header>

    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-head">
          <span>本机文档</span>
          <el-tag size="small" type="info">归属密钥保存在浏览器 localStorage</el-tag>
        </div>
      </template>

      <el-empty v-if="!filtered.length" description="暂无本机文档，点击右上角新建" />
      <el-table v-else :data="filtered" stripe @row-click="openDoc">
        <el-table-column prop="title" label="标题" min-width="220" />
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="updated_at" label="更新时间" width="220">
          <template #default="{ row }">
            {{ row.updated_at || row.saved_at || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="openDoc(row)">打开</el-button>
            <el-button link type="danger" @click.stop="onRemove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
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
    const doc = await createDoc({ title: '无标题文档', content: '# 新文档\n\n开始编写…\n' })
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
.home { max-width: 960px; margin: 0 auto; padding: 24px; }
.bar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.bar h1 { margin: 0; font-size: 22px; }
.actions { display: flex; gap: 12px; align-items: center; }
.card-head { display: flex; align-items: center; justify-content: space-between; }
.card { border-radius: 10px; }
</style>
