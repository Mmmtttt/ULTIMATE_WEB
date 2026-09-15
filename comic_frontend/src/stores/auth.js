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
  const hasRuntimeSpaceEndpoints = typeof window !== 'undefined'
    && window.__ULTIMATE_SPACE_API_BASES
    && typeof window.__ULTIMATE_SPACE_API_BASES === 'object'
  if (!hasRuntimeSpaceEndpoints && !import.meta.env.DEV) return

  const configured = mode === 'normal' ? getNormalApiBase() : getPrivateApiBase()
  if (configured) {
    setRuntimeApiBase(configured)
  } else if (import.meta.env.DEV) {
    setRuntimeApiBase(mode === 'normal' ? '' : getPrivateApiBase())
  }
}

function prepareAuthStatusProbe() {
  // A restarted dual-space client must always probe the private listener first.
  const hasRuntimeSpaceEndpoints = typeof window !== 'undefined'
    && window.__ULTIMATE_SPACE_API_BASES
    && typeof window.__ULTIMATE_SPACE_API_BASES === 'object'
  if (hasRuntimeSpaceEndpoints) applySpaceApiBase('private')
}

const AUTH_STATUS_RETRY_DELAYS_MS = [0, 250, 500, 750, 1000, 1500]

function waitForAuthStatusRetry(delayMs) {
  if (!delayMs) return Promise.resolve()
  return new Promise(resolve => setTimeout(resolve, delayMs))
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    enabled: false,
    authenticated: false,
    mode: 'private',
    loading: false,
    hasAttemptedLogin: false,
    authStatusError: null,
    authStatusProbePrepared: false
  }),

  actions: {
    async checkStatus() {
      if (!this.authStatusProbePrepared) {
        prepareAuthStatusProbe()
        this.authStatusProbePrepared = true
      }
      let lastError = null
      for (const delayMs of AUTH_STATUS_RETRY_DELAYS_MS) {
        await waitForAuthStatusRetry(delayMs)
        try {
          const res = await getAuthStatus()
          if (res.code === 200) {
            this.enabled = res.data.enabled
            this.authenticated = res.data.authenticated
            this.mode = res.data.mode
            this.authStatusError = null
            if (this.enabled) {
              applySpaceApiBase(this.authenticated ? 'normal' : 'private')
            }
            if (res.data.authenticated) {
              this.hasAttemptedLogin = true
            }
            return res.data
          }
          lastError = new Error(res.msg || '认证状态响应无效')
        } catch (e) {
          lastError = e
        }
      }

      console.error('[auth] check status failed after retries:', lastError)
      this.authStatusError = lastError || new Error('认证状态检查失败')
      throw lastError || new Error('认证状态检查失败')
    },

    async login(password) {
      this.loading = true
      try {
        const res = await loginApi(password)
        if (res.code === 200) {
          if (typeof res.data.enabled === 'boolean') {
            this.enabled = res.data.enabled
          }
          this.authenticated = res.data.authenticated
          this.mode = res.data.mode
          this.hasAttemptedLogin = true
          this.authStatusError = null

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
