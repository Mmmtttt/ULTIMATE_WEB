import request from './request'
import { resolveBackendApiUrl } from '@/runtime/endpoint'


export const syncApi = {
  createSession(payload = {}) {
    return request.post('/v1/sync/session', payload)
  },

  getManifest(sessionId) {
    return request.get(`/v1/sync/manifest/${encodeURIComponent(sessionId)}`)
  },

  getSession(sessionId) {
    return request.get(`/v1/sync/session/${encodeURIComponent(sessionId)}`)
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
    })
  },

  downloadPackage(sessionId, packageName, options = {}) {
    const url = `/v1/sync/download/${encodeURIComponent(sessionId)}/${encodeURIComponent(packageName)}`
    return request.get(url, {
      responseType: 'blob',
      ...options
    })
  },

  getPackageDownloadUrl(sessionId, packageName) {
    const url = `/v1/sync/download/${encodeURIComponent(sessionId)}/${encodeURIComponent(packageName)}`
    return resolveBackendApiUrl(url)
  },

  createPairingInvite(payload = {}) {
    return request.post('/v1/sync/pairing/invite', payload)
  },

  claimPairingInvite(payload = {}) {
    return request.post('/v1/sync/pairing/claim', payload)
  },

  connectPairing(payload = {}) {
    return request.post('/v1/sync/pairing/connect', payload)
  },

  listPeers() {
    return request.get('/v1/sync/peers')
  },

  removePeer(peerId) {
    return request.delete(`/v1/sync/peers/${encodeURIComponent(peerId)}`)
  },

  pushDirectional(peerId) {
    return request.post('/v1/sync/directional/push', { peer_id: peerId })
  },

  pullDirectional(peerId) {
    return request.post('/v1/sync/directional/pull', { peer_id: peerId })
  }
}


export default syncApi
