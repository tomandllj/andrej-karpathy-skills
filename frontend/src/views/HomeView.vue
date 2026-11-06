<template>
  <!-- 中文：登录后首页 — 顶栏、左筛选、右文档表 -->
  <div class="shell">
    <header class="topbar">
      <div class="brand">
        <span class="logo" aria-hidden="true">MD</span>
        <strong>文档协助</strong>
      </div>
      <el-input
        v-model="keyword"
        clearable
        placeholder="搜索全部文档"
        class="global-search"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
        <template #suffix>
          <span class="kbd" aria-hidden="true">/</span>
        </template>
      </el-input>
      <div class="top-actions">
        <button
          type="button"
          class="ghost"
          :title="theme === 'dark' ? '切换浅色' : '切换暗色'"
          @click="onToggleTheme"
        >
          <el-icon><Sunny v-if="theme === 'dark'" /><Moon v-else /></el-icon>
          <span>{{ theme === 'dark' ? '浅色' : '暗色' }}</span>
        </button>
        <div class="user-chip" :title="userName">
          <span class="user-avatar" aria-hidden="true">
            <el-icon><User /></el-icon>
          </span>
          <span class="user-name">{{ userName }}</span>
        </div>
        <button type="button" class="ghost" @click="onLogout">退出</button>
      </div>
    </header>

    <div class="body">
      <aside class="sidebar sidebar-nav">
        <!-- 中文：当前账号的文件夹 -->
        <div class="folder-head">
          <span>我的文件夹</span>
          <div class="folder-tools">
            <!-- 中文：小图标点开后选文件夹排序 -->
            <el-dropdown
              class="folder-sort"
              popper-class="folder-sort-popper"
              trigger="click"
              @command="onFolderSort"
            >
              <button
                type="button"
                class="icon-btn"
                :title="folderSort === 'name' ? '排序：名称' : '排序：最近修改'"
              >
                <el-icon><Sort /></el-icon>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    command="updated"
                    :class="{ 'is-chosen': folderSort === 'updated' }"
                  >
                    最近修改
                  </el-dropdown-item>
                  <el-dropdown-item
                    command="name"
                    :class="{ 'is-chosen': folderSort === 'name' }"
                  >
                    名称
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <button type="button" class="icon-btn" title="新建文件夹" @click="onAddFolder">
              <el-icon><Plus /></el-icon>
            </button>
          </div>
        </div>
        <button
          type="button"
          class="nav-item"
          :class="{ 'is-active': selectedFolderId === null }"
          @click="selectFolder(null)"
        >
          <span>未分类</span>
          <span class="count-wrap">
            <el-tag
              v-if="folderPendingCount(null)"
              size="small"
              effect="light"
              round
              type="warning"
              title="待解决"
            >
              {{ folderPendingCount(null) }}
            </el-tag>
            <span class="count">{{ folderCount(null) }}</span>
          </span>
        </button>
        <el-dropdown
          v-for="folder in sortedFolders"
          :key="folder.id"
          class="folder-menu"
          trigger="contextmenu"
          @command="(command) => onFolderCommand(command, folder)"
        >
          <button
            type="button"
            class="nav-item"
            :class="{ 'is-active': selectedFolderId === folder.id, 'is-pinned': folder.pinned }"
            @click="selectFolder(folder.id)"
          >
            <span class="folder-name">{{ folder.name }}</span>
            <span class="count-wrap">
              <el-tag
                v-if="folderPendingCount(folder.id)"
                size="small"
                effect="light"
                round
                type="warning"
                title="待解决"
              >
                {{ folderPendingCount(folder.id) }}
              </el-tag>
              <span class="count">{{ folderCount(folder.id) }}</span>
            </span>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="rename">重命名</el-dropdown-item>
              <el-dropdown-item command="pin">{{ folder.pinned ? '取消置顶' : '置顶' }}</el-dropdown-item>
              <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <!-- 中文：别人分享来的需求，按提交人分组；只是筛选，不是文件夹；可折叠，放在「最近打开」上面 -->
        <div
          v-if="hasInbox"
          class="inbox-block"
          :class="{ 'is-collapsed': inboxCollapsed }"
        >
          <button
            type="button"
            class="recent-label"
            :title="inboxCollapsed ? '展开收到的' : '折叠收到的'"
            :aria-expanded="!inboxCollapsed"
            @click="inboxCollapsed = !inboxCollapsed"
          >
            <el-icon class="recent-toggle" :class="{ 'is-collapsed': inboxCollapsed }">
              <ArrowDown />
            </el-icon>
            <span>收到的</span>
          </button>
          <template v-if="!inboxCollapsed">
            <button
              type="button"
              class="nav-item"
              :class="{ 'is-active': selectedInbox === 'all' }"
              @click="selectInbox('all')"
            >
              <span>全部</span>
              <span class="count">{{ inboxCount(null) }}</span>
            </button>
            <button
              v-for="person in inboxPeople"
              :key="person.name"
              type="button"
              class="nav-item"
              :class="{ 'is-active': selectedInbox === person.name }"
              @click="selectInbox(person.name)"
            >
              <span class="folder-name">{{ person.name }}</span>
              <span class="count">{{ inboxCount(person.name) }}</span>
            </button>
          </template>
        </div>
        <div
          v-if="recentDocs.length"
          class="recent-block"
          :class="{ 'is-collapsed': recentCollapsed }"
        >
          <!-- 中文：标题前箭头可折叠（类似 Cursor 侧栏）；折叠后只留标题并沉底 -->
          <button
            type="button"
            class="recent-label"
            :title="recentCollapsed ? '展开最近打开' : '折叠最近打开'"
            :aria-expanded="!recentCollapsed"
            @click="recentCollapsed = !recentCollapsed"
          >
            <el-icon class="recent-toggle" :class="{ 'is-collapsed': recentCollapsed }">
              <ArrowDown />
            </el-icon>
            <span>最近打开</span>
          </button>
          <template v-if="!recentCollapsed">
            <button
              v-for="item in recentDocs"
              :key="item.id"
              type="button"
              class="recent-item"
              @click="openDoc(item)"
            >
              <span class="recent-title">{{ item.title || '无标题文档' }}</span>
              <span class="recent-meta">
                <span class="recent-folder">{{ recentFolderName(item) }}</span>
                <span v-if="formatOpenedAt(item.opened_at)" class="recent-time">
                  {{ formatOpenedAt(item.opened_at) }}
                </span>
              </span>
            </button>
          </template>
        </div>
      </aside>

      <main class="main">
        <div class="main-head">
          <div class="head-filters">
            <el-select v-model="archiveFilter" class="archive-select">
              <el-option label="全部" value="all" />
              <el-option label="未归档" value="open" />
              <el-option label="已归档" value="archived" />
            </el-select>
            <el-select v-model="shareFilter" class="archive-select">
              <el-option label="全部" value="all" />
              <el-option label="已分享" value="shared" />
              <el-option label="未分享" value="unshared" />
            </el-select>
          </div>
          <div class="head-actions">
            <el-button @click="onCreateDemo">示例文档</el-button>
            <el-button type="primary" @click="onCreate">
              <el-icon class="el-icon--left"><Plus /></el-icon>
              新建文档
            </el-button>
          </div>
        </div>

        <div v-if="!filtered.length" class="empty">
          <h3>{{ keyword ? '没有匹配的文档' : '还没有文档' }}</h3>
          <p>{{ emptyHint }}</p>
        </div>

        <el-table
          v-else
          :data="filtered"
          class="doc-table"
          height="100%"
          scrollbar-always-on
          :default-sort="{ prop: 'updated_at', order: 'ascending' }"
          @row-click="openDoc"
        >
          <el-table-column
            label="标题"
            min-width="220"
            sortable
            :sort-method="compareDocTitle"
          >
            <template #default="{ row }">
              <button type="button" class="title-link" @click.stop="openDoc(row)">
                {{ row.title || '无标题文档' }}
              </button>
              <!-- 中文：收到别人分享的文档，标题旁标出是谁发来的 -->
              <span v-if="row.origin === 'received'" class="from-tag">
                来自 {{ row.from_name || '未知' }}
              </span>
              <div v-if="keyword.trim()" class="search-folder">{{ recentFolderName(row) }}</div>
              <div v-if="row.sub_lines" class="sub">{{ row.sub_lines }}</div>
            </template>
          </el-table-column>
          <!-- 中文：未解决根批注，一条一个标签 -->
          <el-table-column label="待解决" width="240" align="left" class-name="pending-col">
            <template #default="{ row }">
              <div v-if="row.pending_comments?.length" class="pending-tags">
                <el-tag
                  v-for="(text, index) in row.pending_comments"
                  :key="`${row.id}-${index}`"
                  size="small"
                  effect="light"
                  round
                  type="warning"
                  :title="text"
                >
                  {{ clipPending(text) }}
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <!-- 中文：作者最近一次保存，默认从早到晚，格子里不写「作者」 -->
          <el-table-column
            label="作者提交"
            prop="updated_at"
            min-width="140"
            class-name="submit-col"
            sortable
            :sort-orders="['ascending', 'descending', null]"
            :sort-method="compareDocTime"
          >
            <template #default="{ row }">
              <div class="row-meta">{{ formatRelativeTime(row.updated_at || row.saved_at) }}</div>
            </template>
          </el-table-column>
          <!-- 中文：最新一条批注的署名和相对时间 -->
          <el-table-column
            label="评论提交"
            prop="latest_comment_at"
            min-width="140"
            class-name="submit-col"
            sortable
            :sort-orders="['ascending', 'descending', null]"
            :sort-method="compareCommentTime"
          >
            <template #default="{ row }">
              <div v-if="row.latest_comment_at" class="row-meta">
                {{ row.latest_comment_anon_name || '匿名' }} {{ formatRelativeTime(row.latest_comment_at) }}
              </div>
            </template>
          </el-table-column>
          <!-- 中文：操作列用图标，分享、归档、移动、删除，悬停 title 显示汉字 -->
          <el-table-column label="操作" width="156" align="center" header-align="center">
            <template #default="{ row }">
              <div class="row-actions" @click.stop>
                <button
                  type="button"
                  class="icon-btn"
                  :class="{ 'is-shared': isShared(row) }"
                  :title="isShared(row) ? '已分享' : '分享'"
                  @click.stop="openShare(row)"
                >
                  <el-icon :size="16"><Share /></el-icon>
                </button>
                <button
                  type="button"
                  class="icon-btn"
                  :title="isArchived(row) ? '取消归档' : '归档'"
                  @click.stop="onArchive(row)"
                >
                  <el-icon :size="16"><Box /></el-icon>
                </button>
                <el-dropdown class="move-menu" trigger="click" @command="(target) => onMoveDoc(row, target)">
                  <button type="button" class="icon-btn" title="移动" @click.stop>
                    <el-icon :size="16"><FolderOpened /></el-icon>
                  </button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-if="!moveTargets(row).length" disabled>没有可移动的位置</el-dropdown-item>
                      <el-dropdown-item
                        v-for="target in moveTargets(row)"
                        :key="String(target.id)"
                        :command="target.id"
                      >
                        {{ target.name }}
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <button
                  type="button"
                  class="icon-btn is-danger"
                  :title="row.origin === 'received' ? '移除' : '删除'"
                  @click.stop="onRemove(row)"
                >
                  <el-icon :size="16"><Delete /></el-icon>
                </button>
              </div>
            </template>
          </el-table-column>
          <el-table-column
            class-name="time-col"
            label="创建时间"
            width="152"
            sortable
            :sort-orders="['descending', 'ascending', null]"
            :sort-method="compareDocCreated"
          >
            <template #default="{ row }">
              {{ formatTime(row.created_at || row.saved_at) }}
            </template>
          </el-table-column>
          <el-table-column
            class-name="time-col"
            label="修改时间"
            width="152"
            sortable
            :sort-orders="['descending', 'ascending', null]"
            :sort-method="compareDocTime"
          >
            <template #default="{ row }">
              {{ formatTime(row.updated_at || row.saved_at) }}
            </template>
          </el-table-column>
          <!-- 中文：文件大小放最后；批注数列已隐藏 -->
          <el-table-column
            label="文件大小"
            width="110"
            align="right"
            sortable
            :sort-orders="['descending', 'ascending', null]"
            :sort-method="compareDocSize"
          >
            <template #default="{ row }">
              {{ formatSize(row.content_size) }}
            </template>
          </el-table-column>
        </el-table>
      </main>
    </div>
    <ShareDialog v-if="shareDocId" v-model="shareVisible" :doc-id="shareDocId" />
  </div>
</template>

<script setup>
/** 登录后首页：本机文档的筛选与表格管理。离开后再回来由外层缓存保留选中文件夹。 */
import { computed, nextTick, onActivated, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, Box, Delete, FolderOpened, Moon, Plus, Search, Share, Sort, Sunny, User } from '@element-plus/icons-vue'
import ShareDialog from '@/components/ShareDialog.vue'
import {
  claimLegacyDocs,
  createDoc,
  deleteDoc,
  fetchMyDocs,
  moveDoc,
  searchDocs,
} from '@/api/doc'
import { createFolder, deleteFolder, listFolders, pinFolder, renameFolder } from '@/api/folder'
import { adminMe, clearAdminToken, getAdminToken, getLoginPath, rememberLoginPath } from '@/api/admin'
import { getEntry } from '@/api/auth'
import { fetchFeatureFlags } from '@/api/features'
import {
  forgetRecentDoc,
  listLocalDocs,
  listRecentDocs,
  removeLocalDoc,
  saveLocalDoc,
  setDocArchived,
} from '@/utils/localDocs'
import { getTheme, toggleTheme } from '@/utils/theme'
import { titleFromContent } from '@/utils/docTitle'
import demoMarkdown from '../../../demo.json?raw'

defineOptions({ name: 'HomeView' })

const router = useRouter()
const keyword = ref('')
/** 正文里命中当前关键字的文档编号。标题命中不必等这次结果。 */
const contentHitIds = ref(null)
let searchTimer = 0
let searchSerial = 0
const docs = ref([])
const theme = ref(getTheme())
/** 顶栏展示名，登录后由 /me 接口返回（管理员显示「管理员」，普通用户显示用户名）。 */
const userName = ref('用户')
/** 当前文件夹。null 表示未分类。 */
const selectedFolderId = ref(null)
/** 「收到的」筛选：null 不在看收到的，'all' 看全部未归类，其余为提交人用户名。 */
const selectedInbox = ref(null)
/** 当前账号的文件夹。 */
const folders = ref([])
/** 本机最近打开的文档，新的在前。 */
const recentDocs = ref([])
const ARCHIVE_FILTER_KEY = 'md_annotate_archive_filter'
const SHARE_FILTER_KEY = 'md_annotate_share_filter'

/** 读取上次的筛选；没有或不合法时用默认值。 */
function readStoredFilter(key, allowed, fallback) {
  const value = localStorage.getItem(key)
  return allowed.includes(value) ? value : fallback
}

/** 归档筛选：all 全部，open 未归档，archived 已归档。默认全部。 */
const archiveFilter = ref(readStoredFilter(ARCHIVE_FILTER_KEY, ['all', 'open', 'archived'], 'all'))
/** 分享筛选：all 全部，shared 已分享，unshared 未分享。默认全部。 */
const shareFilter = ref(readStoredFilter(SHARE_FILTER_KEY, ['all', 'shared', 'unshared'], 'all'))
/** 首页分享弹窗对应的文档。 */
const shareDocId = ref(null)
const shareVisible = ref(false)
const FOLDER_SORT_KEY = 'md_annotate_folder_sort'
/** 侧栏排序：updated 最近修改，name 名称。 */
const folderSort = ref(localStorage.getItem(FOLDER_SORT_KEY) === 'name' ? 'name' : 'updated')
const RECENT_COLLAPSED_KEY = 'md_annotate_recent_collapsed'
/** 最近打开是否折叠；折叠后列表隐藏并沉到侧栏底部。 */
const recentCollapsed = ref(localStorage.getItem(RECENT_COLLAPSED_KEY) === '1')
const INBOX_COLLAPSED_KEY = 'md_annotate_inbox_collapsed'
/** 「收到的」是否折叠；折叠后列表隐藏，只留标题条。 */
const inboxCollapsed = ref(localStorage.getItem(INBOX_COLLAPSED_KEY) === '1')

watch(folderSort, (value) => {
  localStorage.setItem(FOLDER_SORT_KEY, value)
})

watch(recentCollapsed, (value) => {
  localStorage.setItem(RECENT_COLLAPSED_KEY, value ? '1' : '0')
})

watch(inboxCollapsed, (value) => {
  localStorage.setItem(INBOX_COLLAPSED_KEY, value ? '1' : '0')
})

watch(archiveFilter, (value) => {
  localStorage.setItem(ARCHIVE_FILTER_KEY, value)
})

watch(shareFilter, (value) => {
  localStorage.setItem(SHARE_FILTER_KEY, value)
})

watch(keyword, (value) => {
  window.clearTimeout(searchTimer)
  contentHitIds.value = null
  const q = value.trim()
  if (!q) return
  searchTimer = window.setTimeout(() => {
    loadContentHits(q)
  }, 200)
})

watch(docs, () => {
  const q = keyword.value.trim()
  if (q) loadContentHits(q)
})

watch(shareVisible, (open) => {
  if (!open) refresh()
})

/** 记下侧栏文件夹的排序方式。 */
function onFolderSort(value) {
  if (value === 'name' || value === 'updated') folderSort.value = value
}

/** 文档是否已归档。 */
function isArchived(row) {
  return Number(row?.archived) === 1
}

/** 文档是否还有有效的分享链接。 */
function isShared(row) {
  return row?.is_shared === true
}

/** 文档是否命中当前归档和分享筛选。 */
function matchesStatusFilters(doc) {
  if (archiveFilter.value === 'open' && isArchived(doc)) return false
  if (archiveFilter.value === 'archived' && !isArchived(doc)) return false
  if (shareFilter.value === 'shared' && !isShared(doc)) return false
  if (shareFilter.value === 'unshared' && isShared(doc)) return false
  return true
}

/** 打开这篇文档的分享窗口。先挂上弹窗，再打开，好让弹窗去拉分享列表。 */
async function openShare(row) {
  shareDocId.value = Number(row.id)
  shareVisible.value = false
  await nextTick()
  shareVisible.value = true
}

/** 切换浅色 / 暗色主题。 */
function onToggleTheme() {
  theme.value = toggleTheme()
}

/** 某个文件夹里、符合当前归档、分享和关键字的文档数。没有命中时是 0。null 表示未分类（只算自己创建的）。 */
function folderCount(folderId) {
  const q = keyword.value.trim().toLowerCase()
  return docs.value.filter((d) => {
    if ((d.folder_id ?? null) !== folderId || !matchesStatusFilters(d)) return false
    if (folderId === null && d.origin === 'received') return false
    return !q || matchesKeyword(d, q)
  }).length
}

/** 某个文件夹里、符合当前筛选的待解决批注数。null 表示未分类（只算自己创建的）。 */
function folderPendingCount(folderId) {
  const q = keyword.value.trim().toLowerCase()
  return docs.value.reduce((sum, doc) => {
    if ((doc.folder_id ?? null) !== folderId || !matchesStatusFilters(doc)) return sum
    if (folderId === null && doc.origin === 'received') return sum
    if (q && !matchesKeyword(doc, q)) return sum
    const total = Number(doc.comment_count) || 0
    const resolved = Number(doc.resolved_count) || 0
    return sum + (total > resolved ? total - resolved : 0)
  }, 0)
}

/** 到服务器上按标题、正文和批注查找关键字。 */
async function loadContentHits(q) {
  const serial = ++searchSerial
  const ids = docs.value.map((d) => d.id)
  if (!ids.length) {
    if (serial === searchSerial) contentHitIds.value = new Set()
    return
  }
  try {
    const hit = await searchDocs(ids, q)
    if (serial !== searchSerial || keyword.value.trim() !== q) return
    contentHitIds.value = new Set(hit)
  } catch {
    if (serial === searchSerial) contentHitIds.value = null
  }
}

/** 关键字是否出现在标题、摘要、批注或正文里。 */
function matchesKeyword(doc, q) {
  const local = [doc.title || '', doc.sub_lines || '', ...(doc.pending_comments || [])]
    .join('\n')
    .toLowerCase()
  if (local.includes(q)) return true
  return contentHitIds.value?.has(doc.id) === true
}

/** 从本机记录刷新最近打开。 */
function loadRecent() {
  recentDocs.value = listRecentDocs()
}

/** 最近打开条目对应的文件夹名。收到的文档没归类时显示「收到的」。 */
function recentFolderName(item) {
  if (item?.origin === 'received' && item?.folder_id == null) return '收到的'
  if (item?.folder_id == null) return '未分类'
  const folder = folders.value.find((row) => row.id === item.folder_id)
  return folder?.name || '未分类'
}

/** 把打开时间写成侧栏短句：今天、昨天，或月-日。 */
function formatOpenedAt(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const now = new Date()
  const dayStart = (target) => new Date(target.getFullYear(), target.getMonth(), target.getDate()).getTime()
  const openedDay = dayStart(date)
  const today = dayStart(now)
  const yesterday = dayStart(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1))
  const pad = (n) => String(n).padStart(2, '0')
  const clock = `${pad(date.getHours())}:${pad(date.getMinutes())}`
  if (openedDay === today) return `今天 ${clock}`
  if (openedDay === yesterday) return `昨天 ${clock}`
  const monthDay = `${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
  if (date.getFullYear() === now.getFullYear()) return monthDay
  return `${date.getFullYear()}-${monthDay}`
}

/** 文件夹里文档最近一次修改时间；没有文档时用文件夹创建时间。 */
function folderActivity(folder) {
  let latest = ''
  for (const doc of docs.value) {
    if ((doc.folder_id ?? null) !== folder.id) continue
    const stamp = doc.updated_at || doc.saved_at || ''
    if (stamp > latest) latest = stamp
  }
  return latest || folder.created_at || ''
}

/** 自建文件夹：置顶在前，组内按所选方式排序。筛选只改后面的数字，文件夹仍全部显示。 */
const sortedFolders = computed(() => {
  const byName = (a, b) => (a.name || '').localeCompare(b.name || '', 'zh')
  const byTime = (a, b) => {
    const ta = folderActivity(a)
    const tb = folderActivity(b)
    if (ta !== tb) return ta < tb ? 1 : -1
    return byName(a, b)
  }
  const compare = folderSort.value === 'name' ? byName : byTime
  return [...folders.value].sort((a, b) => {
    const pinDelta = (a.pinned ? 0 : 1) - (b.pinned ? 0 : 1)
    if (pinDelta) return pinDelta
    return compare(a, b)
  })
})

/** 表格标题按中文升序比较。 */
function compareDocTitle(a, b) {
  return (a?.title || '无标题文档').localeCompare(b?.title || '无标题文档', 'zh')
}

/** 把时间转成毫秒，无法解析时当作 0。 */
function timeValue(value) {
  const ms = new Date(value || 0).getTime()
  return Number.isNaN(ms) ? 0 : ms
}

/** 表格修改时间按从旧到新比较，降序时最新在前。 */
function compareDocTime(a, b) {
  return timeValue(a?.updated_at || a?.saved_at) - timeValue(b?.updated_at || b?.saved_at)
}

/** 评论提交按从旧到新比较，没有评论的排在有评论的后面。 */
function compareCommentTime(a, b) {
  const ta = a?.latest_comment_at ? timeValue(a.latest_comment_at) : Number.POSITIVE_INFINITY
  const tb = b?.latest_comment_at ? timeValue(b.latest_comment_at) : Number.POSITIVE_INFINITY
  return ta - tb
}

/** 表格创建时间按从旧到新比较，降序时最新在前。 */
function compareDocCreated(a, b) {
  return timeValue(a?.created_at || a?.saved_at) - timeValue(b?.created_at || b?.saved_at)
}

/** 把字节数显示成 B、KB 或 MB。 */
function formatSize(n) {
  const size = Number(n) || 0
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

/** 表格按文件大小从小到大比较，降序时大的在前。 */
function compareDocSize(a, b) {
  return (Number(a?.content_size) || 0) - (Number(b?.content_size) || 0)
}

/** 空列表说明。 */
const emptyHint = computed(() => {
  if (keyword.value.trim()) return '试试其他关键词。'
  if (shareFilter.value === 'shared') return '还没有已分享的文档。'
  if (shareFilter.value === 'unshared') return '还没有未分享的文档。'
  if (archiveFilter.value === 'archived') return '归档的文档会显示在这里。'
  if (archiveFilter.value === 'open') return '还没有未归档的文档。'
  if (selectedInbox.value === 'all') return '还没有未归类的收到文档。'
  if (selectedInbox.value) return `${selectedInbox.value} 还没有未归类的文档。`
  if (selectedFolderId.value != null) return '这个文件夹里还没有文档。'
  return '还没有文档。'
})

/** 没关键字时只看当前文件夹或「收到的」；有关键字时在全部文档的标题、正文和批注里找。 */
const filtered = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return docs.value.filter((d) => {
    if (!matchesStatusFilters(d)) return false
    if (q) return matchesKeyword(d, q)
    if (selectedInbox.value != null) {
      if (d.origin !== 'received' || (d.folder_id ?? null) !== null) return false
      if (selectedInbox.value !== 'all' && (d.from_name || '未知') !== selectedInbox.value) {
        return false
      }
      return true
    }
    // 中文：未分类只放自己创建的文档；收到的未归类文档在「收到的」里
    if (selectedFolderId.value === null && d.origin === 'received') return false
    return (d.folder_id ?? null) === selectedFolderId.value
  })
})

/** 把时间显示成刚刚、N分钟前、N小时前、N天前，更早则显示月日。 */
function formatRelativeTime(v) {
  if (!v) return ''
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return ''
  const diffMs = Date.now() - d.getTime()
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour
  if (diffMs < minute) return '刚刚'
  if (diffMs < hour) return `${Math.floor(diffMs / minute)}分钟前`
  if (diffMs < day) return `${Math.floor(diffMs / hour)}小时前`
  if (diffMs < 30 * day) return `${Math.floor(diffMs / day)}天前`
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

/** 把时间格式化成 2026.11.05 16:21:03。 */
function formatTime(v) {
  if (!v) return ''
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}.${pad(d.getMonth() + 1)}.${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

/** 列表标签里的批注最多显示约 16 字，完整内容用悬停看。 */
function clipPending(text) {
  const compact = String(text || '').replace(/\s+/g, ' ').trim()
  return compact.length > 16 ? `${compact.slice(0, 16)}…` : compact
}

/** 把本机还持有密钥、服务器上还没有归属的旧文档，绑定到当前账号。 */
async function claimLegacy() {
  const local = listLocalDocs().filter((d) => d.owner_secret)
  if (!local.length) return
  try {
    await claimLegacyDocs(local.map((d) => ({ id: Number(d.id), owner_secret: d.owner_secret })))
  } catch {
    /* 绑定失败不阻塞列表展示 */
  }
}

/** 拉取当前账号的文档（自己创建的 + 收到的），并合并本机的归档标记。 */
async function refresh() {
  try {
    const rows = await fetchMyDocs()
    const localMap = new Map(listLocalDocs().map((d) => [Number(d.id), d]))
    docs.value = rows.map((r) => {
      const local = localMap.get(Number(r.id))
      return {
        ...r,
        archived: local?.archived ? 1 : 0,
        saved_at: local?.saved_at || '',
      }
    })
  } catch (e) {
    docs.value = []
    ElMessage.warning(e?.response?.data?.detail || '文档列表加载失败')
  }
}

/** 切换侧栏文件夹，并重新拉取文档列表。 */
async function selectFolder(folderId) {
  selectedInbox.value = null
  selectedFolderId.value = folderId
  await refresh()
}

/** 切到「收到的」视图；person 为 null 看全部，传用户名只看这个人发来的。 */
function selectInbox(person) {
  selectedFolderId.value = null
  selectedInbox.value = person
}

/** 是否存在未归类的收到文档。 */
const hasInbox = computed(() =>
  docs.value.some((d) => d.origin === 'received' && (d.folder_id ?? null) === null)
)

/** 未归类的收到文档按提交人分组，最近有动静的人排前面。 */
const inboxPeople = computed(() => {
  const map = new Map()
  for (const doc of docs.value) {
    if (doc.origin !== 'received' || (doc.folder_id ?? null) !== null) continue
    const name = doc.from_name || '未知'
    const stamp = doc.updated_at || ''
    if (!map.has(name) || stamp > map.get(name)) map.set(name, stamp)
  }
  return [...map.entries()]
    .map(([name, latest]) => ({ name, latest }))
    .sort((a, b) => {
      if (a.latest !== b.latest) return a.latest < b.latest ? 1 : -1
      return a.name.localeCompare(b.name, 'zh')
    })
})

/** 「收到的」里符合当前筛选的文档数；person 为 null 表示全部。 */
function inboxCount(person) {
  const q = keyword.value.trim().toLowerCase()
  return docs.value.filter((d) => {
    if (d.origin !== 'received' || (d.folder_id ?? null) !== null) return false
    if (!matchesStatusFilters(d)) return false
    if (person != null && (d.from_name || '未知') !== person) return false
    return !q || matchesKeyword(d, q)
  }).length
}

/** 新建文档时带上当前文件夹；未分类则不传。 */
function folderPayload() {
  if (selectedFolderId.value == null) return {}
  return { folder_id: selectedFolderId.value }
}

/** 拉取当前账号的文件夹。成功时返回 true，失败不改当前选中项。 */
async function loadFolders() {
  try {
    folders.value = await listFolders()
    return true
  } catch (e) {
    folders.value = []
    ElMessage.warning(e?.response?.data?.detail || '文件夹加载失败')
    return false
  }
}

/** 选中的文件夹已经不在列表里时，退回未分类。 */
function dropMissingFolder() {
  const id = selectedFolderId.value
  if (id == null) return
  if (!folders.value.some((folder) => folder.id === id)) selectedFolderId.value = null
}

/** 选中的提交人已经没有未归类文档时，「收到的」退回全部视图。 */
function dropMissingInboxPerson() {
  if (selectedInbox.value == null || selectedInbox.value === 'all') return
  if (!inboxPeople.value.some((person) => person.name === selectedInbox.value)) {
    selectedInbox.value = 'all'
  }
}

/** 刷新文件夹、最近打开和文档列表，不改当前选中的文件夹。 */
async function reloadHomeLists() {
  loadRecent()
  await claimLegacy()
  const [foldersOk] = await Promise.all([loadFolders(), refresh()])
  if (foldersOk) dropMissingFolder()
  dropMissingInboxPerson()
}

/** 当前文档可以移去的位置，不含它所在的文件夹。收到的文档移出后回到「收到的」。 */
function moveTargets(row) {
  const current = row?.folder_id ?? null
  const unfiledName = row?.origin === 'received' ? '收到的' : '未分类'
  const items = []
  if (current !== null) items.push({ id: 'none', name: unfiledName })
  for (const folder of folders.value) {
    if (folder.id !== current) items.push({ id: folder.id, name: folder.name })
  }
  return items
}

/** 把文档移到所选文件夹；选未分类则清空所属文件夹。 */
async function onMoveDoc(row, target) {
  const folderId = target === 'none' ? null : target
  try {
    await moveDoc(row.id, folderId)
    ElMessage.success('已移动')
    await refresh()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '移动失败')
  }
}

/** 按右键菜单处理自建文件夹。 */
function onFolderCommand(command, folder) {
  if (command === 'rename') return onRenameFolder(folder)
  if (command === 'pin') return onPinFolder(folder)
  if (command === 'delete') return onDeleteFolder(folder)
}

/** 输入新名称后重命名文件夹。 */
async function onRenameFolder(folder) {
  try {
    const { value } = await ElMessageBox.prompt('文件夹名称', '重命名', {
      inputValue: folder.name,
      inputPattern: /\S+/,
      inputErrorMessage: '请填写名称',
    })
    await renameFolder(folder.id, String(value).trim())
    await loadFolders()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e?.response?.data?.detail || '重命名失败')
  }
}

/** 置顶或取消置顶，并按服务端顺序刷新侧栏。 */
async function onPinFolder(folder) {
  try {
    await pinFolder(folder.id, !folder.pinned)
    await loadFolders()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '置顶失败')
  }
}

/** 确认后删除文件夹：自己的文档软删除，收到的文档退回「收到的」。 */
async function onDeleteFolder(folder) {
  try {
    await ElMessageBox.confirm(
      `确认删除文件夹「${folder.name}」？其中的文档会一并删除；收到的文档会退回「收到的」。`,
      '删除文件夹',
      { type: 'warning' }
    )
    const data = await deleteFolder(folder.id)
    for (const id of data.doc_ids || []) {
      removeLocalDoc(id)
      forgetRecentDoc(id)
    }
    if (selectedFolderId.value === folder.id) selectedFolderId.value = null
    loadRecent()
    await loadFolders()
    await refresh()
    ElMessage.success('已删除')
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

/** 输入名称后为当前账号新建文件夹。 */
async function onAddFolder() {
  try {
    const { value } = await ElMessageBox.prompt('文件夹名称', '新建文件夹', {
      inputPattern: /\S+/,
      inputErrorMessage: '请填写名称',
    })
    const row = await createFolder(String(value).trim())
    folders.value = [...folders.value, row]
    selectedFolderId.value = row.id
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e?.response?.data?.detail || '创建失败')
  }
}

/** 用 demo.json 创建示例文档并打开工作区。 */
async function onCreateDemo() {
  try {
    const content = String(demoMarkdown || '').replace(/^\uFEFF/, '')
    const doc = await createDoc({
      title: titleFromContent(content),
      content,
      ...folderPayload(),
    })
    saveLocalDoc({ id: doc.id, owner_secret: doc.owner_secret, title: doc.title })
    ElMessage.success('已创建示例')
    router.push(`/doc/${doc.id}`)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '创建失败')
  }
}

/** 创建带种子内容的文档并跳转编辑页。 */
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
    const doc = await createDoc({ title: titleFromContent(seed), content: seed, ...folderPayload() })
    saveLocalDoc({ id: doc.id, owner_secret: doc.owner_secret, title: doc.title })
    ElMessage.success('已创建')
    router.push(`/doc/${doc.id}`)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '创建失败')
  }
}

/** 打开指定文档工作区。 */
function openDoc(row) {
  router.push(`/doc/${row.id}`)
}

/** 在未归档与已归档之间移动文档。 */
function onArchive(row) {
  const next = !isArchived(row)
  setDocArchived(row.id, next)
  docs.value = docs.value.map((d) =>
    d.id === row.id ? { ...d, archived: next ? 1 : 0 } : d
  )
  ElMessage.success(next ? '已归档' : '已取消归档')
}

/** 删除：自己的文档软删除；收到的文档只从列表移除，原文留在创建者那里。 */
async function onRemove(row) {
  const isReceived = row.origin === 'received'
  try {
    if (isReceived) {
      await ElMessageBox.confirm(
        `从你的列表移除「${row.title}」？原文仍保留在创建者那里。`,
        '移除文档',
        { type: 'warning' }
      )
    } else {
      await ElMessageBox.confirm(`确认软删除「${row.title}」？`, '删除文档', { type: 'warning' })
    }
    await deleteDoc(row.id)
    if (!isReceived) removeLocalDoc(row.id)
    forgetRecentDoc(row.id)
    loadRecent()
    ElMessage.success(isReceived ? '已移除' : '已删除')
    await refresh()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || (isReceived ? '移除失败' : '删除失败'))
  }
}

/** 拉取当前登录者的展示名，并记住登录页路径。 */
async function loadCurrentUser() {
  try {
    const { data } = await adminMe()
    if (data?.name) userName.value = data.name
    if (data?.login_path) rememberLoginPath(data.login_path)
  } catch {
    /* 路由守卫已校验会话；失败时保留默认名 */
  }
}

/** 退出后统一回 ini 登录页（唯一登录/注册入口）。 */
async function onLogout() {
  let path = getLoginPath()
  if (!path) {
    try {
      const { data } = await adminMe()
      path = data?.login_path || ''
    } catch {
      path = ''
    }
  }
  if (!path) {
    try {
      // 中文：getEntry 已解包一层 data，这里直接拿 login_path
      const entry = await getEntry()
      path = entry?.login_path || ''
    } catch {
      path = ''
    }
  }
  clearAdminToken()
  if (path && path.startsWith('/') && path.length > 1) {
    router.replace(path)
    return
  }
  router.replace({ name: 'unavailable' })
}

/** 首次进入首页时 onActivated 也会触发，这次交给 onMounted，避免打两次请求。 */
let skipActivateRefresh = true

/** 从文档返回首页时刷新列表，保留选中的文件夹、搜索和归档筛选。 */
function onHomeActivated() {
  if (skipActivateRefresh) {
    skipActivateRefresh = false
    return
  }
  reloadHomeLists()
}

/** 浏览器页签重新可见时刷新文档列表。 */
function onHomeVisible() {
  if (document.visibilityState === 'visible') refresh()
}

let userWs = null
let userWsTimer = 0
let userRefreshTimer = 0
let userWsStopped = false

/** 连接按用户的通知通道，分享页批注变动时刷新列表；oncursor 关时不连。 */
function connectUserWs() {
  if (userWsStopped) return
  const token = getAdminToken()
  if (!token) return
  fetchFeatureFlags()
    .then((flags) => {
      if (userWsStopped || !flags.oncursor) return
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const url = `${proto}://${location.host}/ws/user?token=${encodeURIComponent(token)}`
      userWs = new WebSocket(url)
      userWs.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.event !== 'user.comment_activity') return
          window.clearTimeout(userRefreshTimer)
          userRefreshTimer = window.setTimeout(() => refresh(), 800)
        } catch {
          /* 忽略坏消息 */
        }
      }
      userWs.onclose = (ev) => {
        userWs = null
        if (userWsStopped || ev.code === 1008) return
        userWsTimer = window.setTimeout(connectUserWs, 3000)
      }
    })
    .catch(() => {
      /* 拉不到开关就不连，保留切页签刷新兜底 */
    })
}

/** 离开首页时断开通知通道。 */
function disconnectUserWs() {
  userWsStopped = true
  window.clearTimeout(userWsTimer)
  window.clearTimeout(userRefreshTimer)
  if (!userWs) return
  userWs.onclose = null
  userWs.close()
  userWs = null
}

onMounted(() => {
  loadCurrentUser()
  reloadHomeLists()
  connectUserWs()
  document.addEventListener('visibilitychange', onHomeVisible)
})

onBeforeUnmount(() => {
  disconnectUserWs()
  document.removeEventListener('visibilitychange', onHomeVisible)
})

onActivated(onHomeActivated)
</script>

<style scoped>
/* 中文：上左右控制台骨架 */
.shell {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-page);
  color: var(--text-body);
}
.topbar {
  height: 52px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 16px;
  /* 中文：顶栏底色与侧栏保持一致（同为页面底色） */
  background: var(--bg-page);
  border-bottom: 1px solid var(--border-subtle);
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 140px;
}
.logo {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  background: var(--accent);
}
.brand strong {
  font-size: 15px;
  color: var(--text-title);
}
.global-search {
  max-width: 360px;
  margin-left: auto;
}
.kbd {
  font-size: 12px;
  color: var(--text-muted);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 0 6px;
  line-height: 18px;
}
.top-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 160px;
  min-height: 32px;
  margin-left: 8px;
  padding: 0 10px 0 4px;
  border-radius: 999px;
  color: var(--text-title);
}
.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--accent);
  background: var(--accent-soft, #eef2ff);
}
.user-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
}
.ghost {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  padding: 0 10px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.ghost:hover {
  background: var(--bg-muted);
  color: var(--text-title);
}
.body {
  flex: 1;
  min-height: 0;
  display: flex;
}
.sidebar {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 16px 12px;
  overflow: auto;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--text-muted) 45%, transparent) transparent;
}
.sidebar::-webkit-scrollbar {
  width: 3px;
  height: 3px;
}
.sidebar::-webkit-scrollbar-track {
  background: transparent;
}
.sidebar::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--text-muted) 45%, transparent);
}
.sidebar::-webkit-scrollbar-thumb:hover {
  background: color-mix(in srgb, var(--text-muted) 70%, transparent);
}
.folder-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 32px;
  margin-bottom: 8px;
  padding: 0 4px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
}
/* 中文：「收到的」块放在文件夹和「最近打开」之间，与上方文件夹隔开 */
.inbox-block {
  margin-top: 24px;
}
.inbox-block.is-collapsed {
  /* 中文：折叠后整块沉到侧栏底部，紧贴「最近打开」标题条 */
  margin-top: auto;
}
.inbox-block.is-collapsed .recent-label {
  margin-bottom: 0;
}
/* 中文：紧跟在折叠「收到的」后面的「最近打开」不留间距和内衬，两条严丝合缝 */
.inbox-block.is-collapsed + .recent-block {
  margin-top: 0;
  padding-top: 0;
}
.from-tag {
  display: inline-block;
  margin-left: 8px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 20px;
  vertical-align: 1px;
  background: var(--accent-soft, #eef2ff);
  color: var(--accent);
}
/* 中文：最近打开与文件夹隔开，每条是固定高度的两行稿条；折叠时沉底 */
.recent-block {
  margin-top: 24px;
}
.recent-block.is-collapsed {
  margin-top: auto;
  /* 中文：抵消侧栏底部 padding，折叠条贴底无空隙 */
  margin-bottom: -16px;
  padding-top: 8px;
}
.recent-label {
  display: flex;
  align-items: center;
  gap: 4px;
  /* 中文：抵消侧栏左右 padding，标题条与侧栏同宽、直角 */
  width: calc(100% + 24px);
  min-height: 28px;
  margin-bottom: 8px;
  margin-left: -12px;
  padding: 4px 20px;
  border: 0;
  border-radius: 0;
  background: var(--bg-muted);
  color: var(--text-muted);
  font: inherit;
  font-size: 12px;
  font-weight: 500;
  line-height: 16px;
  text-align: left;
  cursor: pointer;
  transition: background-color 160ms cubic-bezier(0.22, 1, 0.36, 1);
}
.recent-label:hover {
  background: color-mix(in srgb, var(--bg-muted) 70%, var(--accent-soft));
}
.recent-label:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.recent-block.is-collapsed .recent-label {
  margin-bottom: 0;
}
.recent-toggle {
  flex: none;
  font-size: 12px;
  transition: transform 160ms cubic-bezier(0.22, 1, 0.36, 1);
}
.recent-toggle.is-collapsed {
  transform: rotate(-90deg);
}
.recent-item {
  width: 100%;
  min-height: 52px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  margin-bottom: 4px;
  padding: 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    background-color 160ms cubic-bezier(0.22, 1, 0.36, 1),
    color 160ms cubic-bezier(0.22, 1, 0.36, 1);
}
.recent-item:hover {
  background: var(--bg-muted);
}
.recent-item:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.recent-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 500;
  line-height: 16px;
  color: var(--text-title);
}
.recent-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.recent-folder {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 400;
  line-height: 16px;
  color: var(--text-muted);
}
.recent-time {
  flex: none;
  margin-left: auto;
  font-size: 12px;
  font-weight: 400;
  line-height: 16px;
  font-variant-numeric: tabular-nums;
  color: var(--text-muted);
}
.folder-tools {
  display: inline-flex;
  align-items: center;
}
.folder-sort {
  display: inline-flex;
}
.folder-sort :deep(.el-tooltip__trigger) {
  display: inline-flex;
}
/* 中文：下拉挂到页面外层，当前排序项用主题色标出 */
:global(.folder-sort-popper .el-dropdown-menu__item.is-chosen) {
  color: var(--el-color-primary);
  font-weight: 600;
}
.icon-btn {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}
.icon-btn:hover {
  background: var(--bg-muted);
  color: var(--text-title);
}
.folder-menu {
  display: block;
  width: 100%;
}
.folder-menu :deep(.el-tooltip__trigger) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  box-sizing: border-box;
}
.folder-name {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-actions {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-wrap: nowrap;
  gap: 4px;
}
.row-actions .icon-btn.is-danger:hover {
  color: var(--el-color-danger);
  background: color-mix(in srgb, var(--el-color-danger) 12%, transparent);
}
.row-actions .icon-btn.is-shared {
  color: var(--accent);
}
.move-menu {
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
}
.move-menu :deep(.el-tooltip__trigger) {
  display: inline-flex;
}
.archive-select {
  width: 120px;
}
.nav-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 36px;
  padding: 6px 10px;
  margin-bottom: 2px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-body);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.nav-item:hover {
  background: var(--bg-muted);
}
.nav-item.is-active {
  background: var(--accent-soft);
  color: var(--text-title);
  font-weight: 600;
}
.nav-item.is-pinned {
  padding-left: 16px;
}
.nav-item.is-pinned::before {
  content: '';
  width: 3px;
  height: 14px;
  flex: none;
  margin-left: -10px;
  margin-right: -1px;
  border-radius: 2px;
  background: var(--accent);
}
.count-wrap {
  flex: none;
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.count {
  flex: none;
  font-size: 12px;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}
.main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 20px 24px 32px;
  overflow: hidden;
  background: var(--bg-elevated);
}
.main-head {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.head-filters,
.head-actions,
.empty-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.empty-actions {
  justify-content: center;
}
/* 中文：表格占满剩余高度，行列超出时始终露出滚动条 */
.doc-table {
  flex: 1;
  min-height: 0;
  width: 100%;
  cursor: pointer;
}
.doc-table :deep(.el-scrollbar__bar) {
  opacity: 1;
}
/* 中文：时间列只留一行，避免被挤成两行 */
.doc-table :deep(.time-col .cell) {
  white-space: nowrap;
}
/* 中文：待解决标签换行排列，避免被单元格裁成一行 */
.doc-table :deep(.pending-col .cell) {
  white-space: normal;
  line-height: 1.4;
}
.pending-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 4px 0;
}
.title-link {
  border: 0;
  padding: 0;
  background: none;
  color: var(--text-title);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.title-link:hover {
  color: var(--text-link);
}
.search-folder {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-muted);
}
/* 中文：作者提交、评论提交列里的相对时间 */
.doc-table :deep(.submit-col .cell) {
  white-space: normal;
  line-height: 1.4;
}
.row-meta {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.45;
}
.sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-muted);
  white-space: pre-line;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.empty {
  padding: 64px 16px;
  text-align: center;
}
.empty h3 {
  margin: 0 0 6px;
  color: var(--text-title);
}
.empty p {
  margin: 0 0 16px;
  color: var(--text-muted);
  font-size: 13.5px;
}

@media (max-width: 860px) {
  .body {
    flex-direction: column;
  }
  .sidebar {
    width: 100%;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    padding: 12px;
    border-right: 0;
    border-bottom: 1px solid var(--sidebar-border);
  }
  .nav-item {
    width: auto;
    min-height: 36px;
  }
  .recent-block {
    flex: 1 0 100%;
    width: 100%;
  }
  .inbox-block {
    flex: 1 0 100%;
    width: 100%;
    margin-top: 12px;
  }
  .recent-block.is-collapsed {
    margin-top: 12px;
    padding-top: 0;
  }
  .recent-item {
    width: 100%;
  }
  .global-search {
    max-width: none;
    flex: 1;
  }
  .brand strong {
    display: none;
  }
  .main {
    padding: 16px;
  }
}
</style>
