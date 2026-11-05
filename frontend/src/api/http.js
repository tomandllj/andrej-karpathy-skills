import axios from 'axios'
import { getClientKey, getOwnerSecret } from '@/utils/localDocs'

const http = axios.create({
  baseURL: '',
  timeout: 30000,
})

http.interceptors.request.use((config) => {
  const docId = config.headers?.['X-Doc-Id'] || config.params?._docId
  const secret =
    config.headers?.['X-Owner-Secret'] ||
    (docId != null ? getOwnerSecret(docId) : null)
  if (secret && !config.headers['X-Owner-Secret']) {
    config.headers['X-Owner-Secret'] = secret
  }
  if (!config.headers['X-Client-Key']) {
    config.headers['X-Client-Key'] = getClientKey()
  }
  if (config.params?._docId) {
    const { _docId, ...rest } = config.params
    config.params = rest
  }
  return config
})

export default http
