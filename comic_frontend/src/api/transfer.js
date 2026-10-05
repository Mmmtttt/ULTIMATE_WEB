import request from './request'
import { resolveBackendApiUrl } from '@/runtime/endpoint'

export const transferApi = {
  listItems() {
    return request.get('/v1/transfer/items')
  },

  publishText(text, name = '') {
    return request.post('/v1/transfer/text', { text, name })
  },

  registerServerFile(path, name = '') {
    return request.post('/v1/transfer/server-file', { path, name })
  },

  uploadFile(file) {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/v1/transfer/upload', formData, {
      timeout: 0,
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  deleteItem(itemId) {
    return request.delete(`/v1/transfer/items/${encodeURIComponent(itemId)}`)
  },

  getDownloadUrl(itemId, spaceMode = '') {
    const params = new URLSearchParams()
    if (spaceMode) {
      params.set('space_mode', spaceMode)
    }
    const query = params.toString()
    return resolveBackendApiUrl(`/v1/transfer/download/${encodeURIComponent(itemId)}${query ? `?${query}` : ''}`)
  }
}

export default transferApi
