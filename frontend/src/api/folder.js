import http from './http'

/** 列出当前登录账号的文件夹。 */
export function listFolders() {
  return http.get('/api/folder').then((r) => r.data)
}

/** 为当前账号新建文件夹。 */
export function createFolder(name) {
  return http.post('/api/folder', { name }).then((r) => r.data)
}

/** 重命名当前账号的文件夹。 */
export function renameFolder(id, name) {
  return http.put(`/api/folder/${id}`, { name }).then((r) => r.data)
}

/** 置顶或取消置顶当前账号的文件夹。 */
export function pinFolder(id, pinned) {
  return http.post(`/api/folder/${id}/pin`, { pinned }).then((r) => r.data)
}

/** 删除文件夹，并软删除其中的文档。 */
export function deleteFolder(id) {
  return http.delete(`/api/folder/${id}`).then((r) => r.data)
}
