import request from './request'
import { resolveBackendApiUrl } from '@/runtime/endpoint'

export const configApi = {
  get() {
    return request.get('/v1/config')
  },

  update(data) {
    return request.put('/v1/config', data)
  },

  reset() {
    return request.post('/v1/config/reset')
  },

  getSystemConfig() {
    return request.get('/v1/config/system')
  },

  updateSystemConfig(data) {
    return request.put('/v1/config/system', data)
  },

  getConfigDirInfo() {
    return request.get('/v1/config/system/config-dir')
  },

  updateConfigDir(data) {
    return request.put('/v1/config/system/config-dir', data)
  },

  getJavdbCookieGuideUrl() {
    return resolveBackendApiUrl('/v1/config/javdb-cookie-guide')
  },

  getCacheInfo() {
    return request.get('/v1/config/cache/info')
  },

  clearSpecificCache(cacheType) {
    return request.delete('/v1/config/cache/clear-specific', { data: { cache_type: cacheType } })
  }
}

export default configApi
