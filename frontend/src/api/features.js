import http from './http'

/** 默认全开：接口失败也不挡正常使用。 */
const DEFAULT_FLAGS = { oncursor: true, online: true }

let cache = null
let pending = null

/** 拉取 config.ini 的功能开关，模块级缓存一次；失败按全开处理。 */
export function fetchFeatureFlags() {
  if (cache) return Promise.resolve(cache)
  if (pending) return pending
  pending = http
    .get('/api/feature-flags')
    .then((r) => {
      cache = {
        oncursor: r.data?.oncursor !== false,
        online: r.data?.online !== false,
      }
      return cache
    })
    .catch(() => {
      cache = { ...DEFAULT_FLAGS }
      return cache
    })
    .finally(() => {
      pending = null
    })
  return pending
}
