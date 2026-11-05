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

export function saveLocalDoc({ id, owner_secret, title }) {
  const list = listLocalDocs().filter((d) => d.id !== id)
  list.unshift({
    id,
    owner_secret,
    title: title || '无标题文档',
    saved_at: new Date().toISOString(),
  })
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
