import http from './http'
import { getOwnerSecret } from '@/utils/localDocs'

export function createDoc(payload = {}) {
  return http.post('/api/doc', payload).then((r) => r.data)
}

export function fetchDocList(ids) {
  return http.post('/api/doc/list', { ids }).then((r) => r.data)
}

/** 在这些文档的标题、正文和批注里查找关键字，返回命中的文档编号。 */
export function searchDocs(ids, q) {
  return http.post('/api/doc/search', { ids, q }).then((r) => r.data)
}

export function getDoc(docId, { shareToken, ownerSecret } = {}) {
  const headers = {}
  const secret = ownerSecret || getOwnerSecret(docId)
  if (secret) headers['X-Owner-Secret'] = secret
  return http
    .get(`/api/doc/${docId}`, {
      headers,
      params: shareToken ? { share_token: shareToken } : {},
    })
    .then((r) => r.data)
}

export function updateDoc(docId, body, { shareToken, ownerSecret } = {}) {
  const headers = {}
  const secret = ownerSecret || getOwnerSecret(docId)
  if (secret) headers['X-Owner-Secret'] = secret
  return http
    .put(`/api/doc/${docId}`, body, {
      headers,
      params: shareToken ? { share_token: shareToken } : {},
    })
    .then((r) => r.data)
}

/** 把文档移到指定文件夹；folderId 为空则回到未分类。 */
export function moveDoc(docId, folderId) {
  const headers = {}
  const secret = getOwnerSecret(docId)
  if (secret) headers['X-Owner-Secret'] = secret
  return http.put(`/api/doc/${docId}/folder`, { folder_id: folderId }, { headers }).then((r) => r.data)
}

export function deleteDoc(docId) {
  const headers = {}
  const secret = getOwnerSecret(docId)
  if (secret) headers['X-Owner-Secret'] = secret
  return http.delete(`/api/doc/${docId}`, { headers }).then((r) => r.data)
}

export function listVersions(docId) {
  return http.get(`/api/doc/${docId}/version`).then((r) => r.data)
}

export function getVersion(docId, vid) {
  return http.get(`/api/doc/${docId}/version/${vid}`).then((r) => r.data)
}

export function rollback(docId, vid) {
  const headers = {}
  const secret = getOwnerSecret(docId)
  if (secret) headers['X-Owner-Secret'] = secret
  return http.post(`/api/doc/${docId}/rollback/${vid}`, null, { headers }).then((r) => r.data)
}

export function exportUrl(docId) {
  return `/api/doc/${docId}/export`
}

export function createShare(docId, permission, recipientIds = []) {
  const headers = {}
  const secret = getOwnerSecret(docId)
  if (secret) headers['X-Owner-Secret'] = secret
  return http
    .post(`/api/doc/${docId}/share`, { permission, recipient_ids: recipientIds }, { headers })
    .then((r) => r.data)
}

export function listShares(docId) {
  const headers = {}
  const secret = getOwnerSecret(docId)
  if (secret) headers['X-Owner-Secret'] = secret
  return http.get(`/api/doc/${docId}/share`, { headers }).then((r) => r.data)
}

export function updateShare(shareId, body, docId) {
  const headers = {}
  const secret = getOwnerSecret(docId)
  if (secret) headers['X-Owner-Secret'] = secret
  return http.put(`/api/share/${shareId}`, body, { headers }).then((r) => r.data)
}

export function getByShareToken(token) {
  return http.get(`/api/share/${token}`).then((r) => r.data)
}

/** 登录后打开分享链接，把这篇记进「收到的」。 */
export function claimShare(token) {
  return http.post(`/api/share/${token}/save`).then((r) => r.data)
}

/** 登录后可用的账号名单（排除管理员和自己），给分享对话框选接收人用。 */
export function listUsers() {
  return http.get('/api/auth/user/list').then((r) => r.data)
}

/** 当前账号的文档：自己创建的 + 收到的分享。 */
export function fetchMyDocs() {
  return http.get('/api/doc/mine').then((r) => r.data)
}

/** 把本机持有密钥的旧文档绑定到当前账号。 */
export function claimLegacyDocs(items) {
  return http.post('/api/doc/claim-legacy', { items }).then((r) => r.data)
}

export function listComments(docId) {
  return http.get(`/api/doc/${docId}/comment`).then((r) => r.data)
}

export function createComment(docId, body, { shareToken } = {}) {
  const headers = {}
  const secret = getOwnerSecret(docId)
  if (secret) headers['X-Owner-Secret'] = secret
  return http
    .post(`/api/doc/${docId}/comment`, body, {
      headers,
      params: shareToken ? { share_token: shareToken } : {},
    })
    .then((r) => r.data)
}

export function updateComment(docId, cid, body, { shareToken } = {}) {
  const headers = {}
  const secret = getOwnerSecret(docId)
  if (secret) headers['X-Owner-Secret'] = secret
  return http
    .put(`/api/doc/${docId}/comment/${cid}`, body, {
      headers,
      params: shareToken ? { share_token: shareToken } : {},
    })
    .then((r) => r.data)
}

/** 正文保存后批量写回批注锚点。 */
export function batchUpdateCommentAnchors(docId, items, { shareToken } = {}) {
  const headers = {}
  const secret = getOwnerSecret(docId)
  if (secret) headers['X-Owner-Secret'] = secret
  return http
    .put(
      `/api/doc/${docId}/comment-anchors`,
      { items },
      {
        headers,
        params: shareToken ? { share_token: shareToken } : {},
      }
    )
    .then((r) => r.data)
}

export function deleteComment(docId, cid, { shareToken } = {}) {
  const headers = {}
  const secret = getOwnerSecret(docId)
  if (secret) headers['X-Owner-Secret'] = secret
  return http
    .delete(`/api/doc/${docId}/comment/${cid}`, {
      headers,
      params: shareToken ? { share_token: shareToken } : {},
    })
    .then((r) => r.data)
}
