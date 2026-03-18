import { getLocation } from './browser'

function trimTrailingSlash(value = '') {
  return String(value || '').replace(/\/+$/, '')
}

function ensureLeadingSlash(path) {
  if (!path) return ''
  return path.startsWith('/') ? path : `/${path}`
}

function isAbsoluteHttpUrl(value) {
  return /^https?:\/\//i.test(value)
}

function getEnvApiBase() {
  return String(import.meta.env.VITE_API_BASE_URL || '').trim()
}

function getDevBackendOrigin() {
  const location = getLocation()
  if (!location) return ''
  const backendPort = import.meta.env.VITE_BACKEND_PORT || 5000
  return `${location.protocol}//${location.hostname}:${backendPort}`
}

export function resolveApiBaseUrl() {
  const envBase = getEnvApiBase()
  if (envBase) {
    return trimTrailingSlash(envBase)
  }

  if (import.meta.env.DEV) {
    const origin = getDevBackendOrigin()
    return origin ? `${origin}/api` : '/api'
  }

  return '/api'
}

export function resolveBackendOrigin() {
  const envBase = getEnvApiBase()
  if (envBase) {
    if (!isAbsoluteHttpUrl(envBase)) {
      return ''
    }

    try {
      const parsed = new URL(envBase)
      return `${parsed.protocol}//${parsed.host}`
    } catch (_) {
      const matched = envBase.match(/^(https?:\/\/[^/]+)/i)
      return matched ? matched[1] : ''
    }
  }

  if (import.meta.env.DEV) {
    return getDevBackendOrigin()
  }

  return ''
}

export function resolveBackendUrl(path) {
  if (!path) return path

  const raw = String(path).trim()
  if (!raw) return raw

  if (/^(https?:)?\/\//i.test(raw) || raw.startsWith('data:') || raw.startsWith('blob:')) {
    return raw
  }

  const normalizedPath = ensureLeadingSlash(raw)
  const backendOrigin = resolveBackendOrigin()
  return backendOrigin ? `${backendOrigin}${normalizedPath}` : normalizedPath
}

export function resolveBackendApiUrl(path) {
  const normalized = ensureLeadingSlash(path || '')
  const apiPath = /^\/api(\/|$)/.test(normalized) ? normalized : `/api${normalized}`
  return resolveBackendUrl(apiPath)
}
