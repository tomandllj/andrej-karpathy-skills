const KEY = 'md_annotate_docs_v1'
const CLIENT_KEY = 'md_annotate_client_key'
const ANON_NAME = 'md_annotate_anon_name'

export function getClientKey() {
  let k = localStorage.getItem(CLIENT_KEY)
  if (!k) {
    k = crypto.randomUUID()
    localStorage.setItem(CLIENT_KEY, k)
  }
  return k
}

export function getAnonName() {
  return localStorage.getItem(ANON_NAME) || ''
}

export function setAnonName(name) {
  localStorage.setItem(ANON_NAME, name || '')
}

export function listLocalDocs() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]')
  } catch {
    return []
  }
}

/** 写入本机文档缓存，并保留已有归档标记。 */
export function saveLocalDoc({ id, owner_secret, title }) {
  const prev = listLocalDocs().find((d) => d.id === id)
  const list = listLocalDocs().filter((d) => d.id !== id)
  list.unshift({
    id,
    owner_secret,
    title: title || '无标题文档',
    saved_at: new Date().toISOString(),
    archived: prev?.archived ? 1 : 0,
  })
  localStorage.setItem(KEY, JSON.stringify(list))
}

/** 标记本机文档是否已归档。 */
export function setDocArchived(id, archived) {
  const list = listLocalDocs().map((d) =>
    d.id === id || d.id === Number(id) ? { ...d, archived: archived ? 1 : 0 } : d
  )
  localStorage.setItem(KEY, JSON.stringify(list))
}

export function updateLocalTitle(id, title) {
  const list = listLocalDocs().map((d) => (d.id === id ? { ...d, title } : d))
  localStorage.setItem(KEY, JSON.stringify(list))
}

export function removeLocalDoc(id) {
  const list = listLocalDocs().filter((d) => d.id !== id)
  localStorage.setItem(KEY, JSON.stringify(list))
}

export function getOwnerSecret(id) {
  const item = listLocalDocs().find((d) => d.id === Number(id) || d.id === id)
  return item?.owner_secret || null
}

const RECENT_KEY = 'md_annotate_recent_docs'
const RECENT_LIMIT = 10

/** 读取最近打开的文档，新的在前。 */
export function listRecentDocs() {
  try {
    const rows = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]')
    return Array.isArray(rows) ? rows.slice(0, RECENT_LIMIT) : []
  } catch {
    return []
  }
}

/** 记下一次打开。同一篇只留最新一条，最多 10 条；origin 标记是自己创建还是收到的。 */
export function rememberRecentDoc({ id, title, folder_id, origin }) {
  const docId = Number(id)
  if (!docId) return []
  const rest = listRecentDocs().filter((item) => Number(item.id) !== docId)
  const next = [
    {
      id: docId,
      title: title || '无标题文档',
      folder_id: folder_id ?? null,
      origin: origin || null,
      opened_at: new Date().toISOString(),
    },
    ...rest,
  ].slice(0, RECENT_LIMIT)
  localStorage.setItem(RECENT_KEY, JSON.stringify(next))
  return next
}

/** 只改最近打开里某篇的标题，不改变顺序。 */
export function renameRecentDoc(id, title) {
  const docId = Number(id)
  const rows = listRecentDocs()
  if (!rows.some((item) => Number(item.id) === docId)) return
  const next = rows.map((item) =>
    Number(item.id) === docId ? { ...item, title: title || '无标题文档' } : item
  )
  localStorage.setItem(RECENT_KEY, JSON.stringify(next))
}

/** 从最近打开里去掉一篇文档。 */
export function forgetRecentDoc(id) {
  const next = listRecentDocs().filter((item) => Number(item.id) !== Number(id))
  localStorage.setItem(RECENT_KEY, JSON.stringify(next))
}
