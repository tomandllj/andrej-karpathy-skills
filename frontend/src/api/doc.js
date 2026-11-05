import http from './http'
import { getOwnerSecret } from '@/utils/localDocs'

export function createDoc(payload = {}) {
  return http.post('/api/doc', payload).then((r) => r.data)
}

export function fetchDocList(ids) {
  return http.post('/api/doc/list', { ids }).then((r) => r.data)
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

export function createShare(docId, permission) {
  const headers = {}
  const secret = getOwnerSecret(docId)
  if (secret) headers['X-Owner-Secret'] = secret
  return http.post(`/api/doc/${docId}/share`, { permission }, { headers }).then((r) => r.data)
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
