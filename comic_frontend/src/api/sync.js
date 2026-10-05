import request from './request'
import { resolveBackendApiUrl } from '@/runtime/endpoint'

const syncRequestOptions = {
  timeout: 0
}


export const syncApi = {
  createSession(payload = {}) {
    return request.post('/v1/sync/session', payload, syncRequestOptions)
  },

  getManifest(sessionId) {
    return request.get(`/v1/sync/manifest/${encodeURIComponent(sessionId)}`, syncRequestOptions)
  },

  getSession(sessionId) {
    return request.get(`/v1/sync/session/${encodeURIComponent(sessionId)}`, syncRequestOptions)
  },

  finishSession({
    sessionId,
    status = 'completed',
    failedPackages = [],
    error = ''
  }) {
    return request.post('/v1/sync/session/finish', {
      session_id: sessionId,
      status,
      failed_packages: Array.isArray(failedPackages) ? failedPackages : [],
      error
    }, syncRequestOptions)
  },

  downloadPackage(sessionId, packageName, options = {}) {
    const url = `/v1/sync/download/${encodeURIComponent(sessionId)}/${encodeURIComponent(packageName)}`
    return request.get(url, {
      ...syncRequestOptions,
      responseType: 'blob',
      ...options
    })
  },

  getPackageDownloadUrl(sessionId, packageName) {
    const url = `/v1/sync/download/${encodeURIComponent(sessionId)}/${encodeURIComponent(packageName)}`
    return resolveBackendApiUrl(url)
  },

  createPairingInvite(payload = {}) {
    return request.post('/v1/sync/pairing/invite', payload, syncRequestOptions)
  },

  claimPairingInvite(payload = {}) {
    return request.post('/v1/sync/pairing/claim', payload, syncRequestOptions)
  },

  connectPairing(payload = {}) {
    return request.post('/v1/sync/pairing/connect', payload, syncRequestOptions)
  },

  listPeers() {
    return request.get('/v1/sync/peers', syncRequestOptions)
  },

  removePeer(peerId) {
    return request.delete(`/v1/sync/peers/${encodeURIComponent(peerId)}`, syncRequestOptions)
  },

  pushDirectional(peerId) {
    return request.post('/v1/sync/directional/push', { peer_id: peerId }, syncRequestOptions)
  },

  previewDirectional(peerId, direction) {
    return request.post('/v1/sync/directional/preview', {
      peer_id: peerId,
      direction
    }, syncRequestOptions)
  },

  previewListScope(peerId, listId) {
    return request.post('/v1/sync/list-scope/preview', {
      peer_id: peerId,
      list_id: listId,
      direction: 'push',
    }, syncRequestOptions)
  },

  previewListScopeWithDirection(peerId, listId, direction) {
    return request.post('/v1/sync/list-scope/preview', {
      peer_id: peerId,
      list_id: listId,
      direction,
    }, syncRequestOptions)
  },

  pullDirectional(peerId) {
    return request.post('/v1/sync/directional/pull', { peer_id: peerId }, syncRequestOptions)
  },

  startDirectionalTask(peerId, direction) {
    return request.post('/v1/sync/directional/task/start', {
      peer_id: peerId,
      direction
    }, syncRequestOptions)
  },

  getDirectionalTask(taskId) {
    return request.get(`/v1/sync/directional/task/${encodeURIComponent(taskId)}`, syncRequestOptions)
  },

  pushListScope(peerId, listId) {
    return request.post('/v1/sync/list-scope/push', {
      peer_id: peerId,
      list_id: listId
    }, syncRequestOptions)
  },

  pullListScope(peerId, listId) {
    return request.post('/v1/sync/list-scope/pull', {
      peer_id: peerId,
      list_id: listId
    }, syncRequestOptions)
  },

  startListScopeTask(peerId, listId, direction = 'push') {
    return request.post('/v1/sync/list-scope/task/start', {
      peer_id: peerId,
      list_id: listId,
      direction,
    }, syncRequestOptions)
  },

  getListScopeTask(taskId) {
    return request.get(`/v1/sync/list-scope/task/${encodeURIComponent(taskId)}`, syncRequestOptions)
  },

  getListScopeOptions(peerId = '') {
    return request.get('/v1/sync/list-scope/options', {
      ...syncRequestOptions,
      params: peerId ? { peer_id: peerId } : undefined,
    })
  }
}


export default syncApi
