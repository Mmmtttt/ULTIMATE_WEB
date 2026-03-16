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

  getJavdbCookieGuideUrl() {
    return '/api/v1/config/javdb-cookie-guide'
  }
}

export default configApi
