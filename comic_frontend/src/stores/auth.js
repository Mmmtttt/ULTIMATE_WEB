import { defineStore } from 'pinia'
import { login as loginApi, getAuthStatus, logout as logoutApi } from '@/api/auth'

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

          if (import.meta.env.DEV) {
            // 开发模式：通过切换端口来切换空间
            if (!res.data.authenticated) {
              setRuntimeApiBase(getPrivateApiBase())
            } else {
              // 开发环境走 Vite 代理（相对路径），不需要切换绝对 URL
              setRuntimeApiBase('')
            }
          }
          // 生产模式：始终走相对路径 /api，通过 X-Space-Mode header 由前端服务器路由
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

      try {
        window.localStorage.removeItem('ULTIMATE_API_BASE_URL')
        delete window.__ULTIMATE_API_BASE_URL
      } catch (e) {
        // ignore
      }

      if (import.meta.env.DEV) {
        // 开发模式：退出后切到 private 端口
        setRuntimeApiBase(getPrivateApiBase())
      }
    },

    switchToPrivateMode() {
      this.authenticated = false
      this.mode = 'private'
      if (import.meta.env.DEV) {
        setRuntimeApiBase(getPrivateApiBase())
      }
    },

    switchToNormalMode() {
      this.authenticated = true
      this.mode = 'normal'
      if (import.meta.env.DEV) {
        setRuntimeApiBase('')
      }
    }
  }
})
