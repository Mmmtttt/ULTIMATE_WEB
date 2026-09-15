import { defineStore } from 'pinia'
import { login as loginApi, getAuthStatus, logout as logoutApi, updateProjectPassword } from '@/api/auth'
import { getConfiguredSpaceApiBaseUrl } from '@/runtime/endpoint'

function getPrivateApiBase() {
  const runtimeBase = getConfiguredSpaceApiBaseUrl('private')
  if (runtimeBase) return runtimeBase
  const privatePort = import.meta.env.VITE_PRIVATE_PORT || 5000
  const sslEnabled = import.meta.env.VITE_BACKEND_SSL_ENABLED !== false
  const protocol = sslEnabled ? 'https' : 'http'
  const hostname = window.location.hostname
  return `${protocol}://${hostname}:${privatePort}/api`
}

function getNormalApiBase() {
  const runtimeBase = getConfiguredSpaceApiBaseUrl('normal')
  if (runtimeBase) return runtimeBase
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

function applySpaceApiBase(mode) {
  const configured = mode === 'normal' ? getNormalApiBase() : getPrivateApiBase()
  if (configured) {
    setRuntimeApiBase(configured)
  } else if (import.meta.env.DEV) {
    setRuntimeApiBase(mode === 'normal' ? '' : getPrivateApiBase())
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
          if (this.enabled) {
            applySpaceApiBase(this.authenticated ? 'normal' : 'private')
          }
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

          if (this.enabled) {
            applySpaceApiBase(res.data.authenticated ? 'normal' : 'private')
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

      try {
        window.localStorage.removeItem('ULTIMATE_API_BASE_URL')
        delete window.__ULTIMATE_API_BASE_URL
      } catch (e) {
        // ignore
      }

      if (this.enabled) applySpaceApiBase('private')
    },

    switchToPrivateMode() {
      this.authenticated = false
      this.mode = 'private'
      if (this.enabled) applySpaceApiBase('private')
    },

    switchToNormalMode() {
      this.authenticated = true
      this.mode = 'normal'
      if (this.enabled) applySpaceApiBase('normal')
    },

    async changePassword(password) {
      const res = await updateProjectPassword(password)
      if (res.code === 200) {
        this.enabled = true
        this.authenticated = true
        this.mode = 'normal'
        this.hasAttemptedLogin = true
      }
      return res
    }
  }
})
