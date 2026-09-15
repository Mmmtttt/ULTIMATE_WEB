import axios from 'axios'
import { resolveApiBaseUrl } from '@/runtime/endpoint'
import { showFailToast } from 'vant'

let _authStore = null
function _getAuthStore() {
  if (!_authStore) {
    try {
      const { useAuthStore } = require('@/stores/auth')
      _authStore = useAuthStore()
    } catch (_) {
      // ignore
    }
  }
  return _authStore
}

const request = axios.create({
  baseURL: resolveApiBaseUrl(),
  timeout: 30000,
  withCredentials: true
})

request.interceptors.request.use(
  config => {
    // Runtime space switching changes the endpoint after this module loads.
    config.baseURL = resolveApiBaseUrl()

    console.log('[request]', config.method?.toUpperCase(), {
      baseURL: config.baseURL,
      url: config.url
    })

    const authStore = _getAuthStore()
    if (authStore?.mode) {
      config.headers['X-Space-Mode'] = authStore.mode
    }

    return config
  },
  error => Promise.reject(error)
)

request.interceptors.response.use(
  response => {
    console.log('[response]', response.config.url, response.status)

    if (response.config.responseType === 'blob' || response.config.responseType === 'arraybuffer') {
      return response
    }

    const res = response.data
    if (res.code === 200) {
      return res
    }
    return Promise.reject(new Error(res.msg || 'Request failed'))
  },
  error => {
    const status = error.response?.status
    const url = error.config?.url || ''
    const diagnostics = {
      at: new Date().toISOString(),
      method: error.config?.method?.toUpperCase() || '',
      baseURL: error.config?.baseURL || '',
      url,
      status: status ?? null,
      code: error.code || '',
      message: error.message || ''
    }
    console.error('[request error]', diagnostics)
    try {
      window.localStorage.setItem('ULTIMATE_LAST_NETWORK_ERROR', JSON.stringify(diagnostics))
    } catch (_) {
      // Diagnostics must never replace the original request error.
    }

    if (status === 401) {
      console.warn('[request] 401 Unauthorized - 未认证或 session 已过期')
      // 不自动跳转，让页面自己处理
    } else if (status >= 500) {
      showFailToast(`服务器错误 (${status})`)
    } else if (error.message === 'Network Error') {
      showFailToast('网络连接失败，请检查服务是否启动')
    }

    return Promise.reject(error)
  }
)

export default request
