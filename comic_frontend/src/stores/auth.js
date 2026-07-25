import { defineStore } from 'pinia'
import { login as loginApi, getAuthStatus, logout as logoutApi } from '@/api/auth'
import { resolveBackendOrigin } from '@/runtime/endpoint'

function getPrivateApiBase() {
  const privatePort = import.meta.env.VITE_PRIVATE_PORT || 5000
  const sslEnabled = import.meta.env.VITE_BACKEND_SSL_ENABLED !== false
  const protocol = sslEnabled ? 'https' : 'http'
  const hostname = window.location.hostname
  return `${protocol}://${hostname}:${privatePort}/api`
}

function getNormalApiBase() {
  const normalPort = import.meta.env.VITE_NORMAL_PORT || 5001
  const sslEnabled = import.meta.env.VITE_BACKEND_SSL_ENABLED !== false
  const protocol = sslEnabled ? 'https' : 'http'
  const hostname = window.location.hostname
  return `${protocol}://${hostname}:${normalPort}/api`
}

function setRuntimeApiBase(url) {
  try {
    if (url) {
      window.localStorage.setItem('ULTIMATE_API_BASE_URL', url)
      window.__ULTIMATE_API_BASE_URL = url
    } else {
      window.localStorage.removeItem('ULTIMATE_API_BASE_URL')
      delete window.__ULTIMATE_API_BASE_URL
    }
  } catch (e) {
    console.warn('[auth] failed to set runtime api base:', e)
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    enabled: false,
    authenticated: false,
    mode: 'private',
    loading: false,
    hasAttemptedLogin: false
  }),

  actions: {
    async checkStatus() {
      try {
        const res = await getAuthStatus()
        if (res.code === 200) {
          this.enabled = res.data.enabled
          this.authenticated = res.data.authenticated
          this.mode = res.data.mode
          // 如果已经认证了，说明之前登录过
          if (res.data.authenticated) {
            this.hasAttemptedLogin = true
          }
        }
        return res.data
      } catch (e) {
        console.error('[auth] check status failed:', e)
        throw e
      }
    },

    async login(password) {
      this.loading = true
      try {
        const res = await loginApi(password)
        if (res.code === 200) {
          this.authenticated = res.data.authenticated
          this.mode = res.data.mode
          this.hasAttemptedLogin = true

          // 密码错误（未认证）→ 切换到 private 端口，进入隐私模式
          if (!res.data.authenticated) {
            setRuntimeApiBase(getPrivateApiBase())
          } else {
            // 登录成功 → 确保使用 normal 端口
            // 开发环境走代理，不需要切换
            if (!import.meta.env.DEV) {
              setRuntimeApiBase(getNormalApiBase())
            }
          }
        }
        return res.data
      } finally {
        this.loading = false
      }
    },

    async logout() {
      try {
        await logoutApi()
      } catch (e) {
        console.error('[auth] logout failed:', e)
      }
      this.authenticated = false
      this.mode = 'private'
      this.hasAttemptedLogin = false

      // 退出登录后清除自定义 API 地址，让路由守卫把用户送到登录页
      try {
        window.localStorage.removeItem('ULTIMATE_API_BASE_URL')
        delete window.__ULTIMATE_API_BASE_URL
      } catch (e) {
        // ignore
      }
    },

    switchToPrivateMode() {
      setRuntimeApiBase(getPrivateApiBase())
      this.authenticated = false
      this.mode = 'private'
    },

    switchToNormalMode() {
      if (!import.meta.env.DEV) {
        setRuntimeApiBase(getNormalApiBase())
      }
      this.authenticated = true
      this.mode = 'normal'
    }
  }
})
