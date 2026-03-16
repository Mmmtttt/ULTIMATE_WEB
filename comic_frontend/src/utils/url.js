function normalizeRelativePath(path) {
  if (!path) return ''
  return path.startsWith('/') ? path : `/${path}`
}

export function getBackendOrigin() {
  const envBase = import.meta.env.VITE_API_BASE_URL
  if (envBase) {
    const base = String(envBase).trim()
    if (/^https?:\/\//i.test(base)) {
      try {
        const parsed = new URL(base)
        return `${parsed.protocol}//${parsed.host}`
      } catch (_) {
        return base.replace(/\/+$/, '')
      }
    }
    return ''
  }

  if (import.meta.env.DEV && typeof window !== 'undefined') {
    const protocol = window.location.protocol
    const hostname = window.location.hostname
    const backendPort = import.meta.env.VITE_BACKEND_PORT || 5000
    return `${protocol}//${hostname}:${backendPort}`
  }

  return ''
}

export function toBackendUrl(path) {
  if (!path) return path

  const raw = String(path).trim()
  if (!raw) return raw

  if (/^(https?:)?\/\//i.test(raw) || raw.startsWith('data:') || raw.startsWith('blob:')) {
    return raw
  }

  const normalizedPath = normalizeRelativePath(raw)
  const backendOrigin = getBackendOrigin()
  return backendOrigin ? `${backendOrigin}${normalizedPath}` : normalizedPath
}

export function toBackendApiUrl(path) {
  const normalized = normalizeRelativePath(path || '')
  const apiPath = normalized.startsWith('/api/') ? normalized : `/api${normalized}`
  return toBackendUrl(apiPath)
}

