import request from './request'
import { toBackendApiUrl } from '@/utils/url'

export const teledriveApi = {
  getStatus() {
    return request.get('/v1/teledrive/status')
  },

  previewImport(payload = {}) {
    return request.post('/v1/teledrive/imports/preview', normalizeImportPayload(payload), {
      timeout: 0
    })
  },

  runImport(payload = {}) {
    return request.post('/v1/teledrive/imports', normalizeImportPayload(payload), {
      timeout: 0
    })
  },

  getCatalog(params = {}) {
    return request.get('/v1/teledrive/catalog', { params })
  },

  getTree(params = {}) {
    return request.get('/v1/teledrive/tree', { params })
  },

  previewLibrarySync(payload = {}) {
    return request.post('/v1/teledrive/library-sync/preview', normalizeLibrarySyncPayload(payload), {
      timeout: 0
    })
  },

  runLibrarySync(payload = {}) {
    return request.post('/v1/teledrive/library-sync', normalizeLibrarySyncPayload(payload), {
      timeout: 0
    })
  },

  buildFileContentUrl(fileId, params = {}) {
    if (!fileId) return ''
    const search = new URLSearchParams()
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        search.set(key, value)
      }
    })
    const suffix = search.toString() ? `?${search.toString()}` : ''
    return toBackendApiUrl(`/v1/teledrive/files/${encodeURIComponent(fileId)}/content${suffix}`)
  }
}

function normalizeImportPayload(payload) {
  const limit = Number(payload?.limit)
  return {
    limit: Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : undefined,
    convert_photos: payload?.convert_photos !== false
  }
}

function normalizeLibrarySyncPayload(payload) {
  const limit = Number(payload?.limit)
  return {
    limit: Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : undefined
  }
}
