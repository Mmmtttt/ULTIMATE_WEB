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
    const base = String(request.defaults.baseURL || '/api').replace(/\/$/, '')
    if (/^https?:\/\//i.test(base)) {
      return `${base}/v1/config/javdb-cookie-guide`
    }
    if (import.meta.env.DEV) {
      const protocol = window.location.protocol
      const hostname = window.location.hostname
      const backendPort = import.meta.env.VITE_BACKEND_PORT || 5000
      return `${protocol}//${hostname}:${backendPort}/api/v1/config/javdb-cookie-guide`
    }
    const normalized = base.startsWith('/') ? base : `/${base}`
    return `${normalized}/v1/config/javdb-cookie-guide`
  }
}

export default configApi
