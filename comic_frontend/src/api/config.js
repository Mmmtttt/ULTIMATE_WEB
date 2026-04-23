import request from './request'

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

  getCacheInfo() {
    return request.get('/v1/config/cache/info')
  },

  clearSpecificCache(cacheType) {
    return request.delete('/v1/config/cache/clear-specific', { data: { cache_type: cacheType } })
  }
}

export default configApi
