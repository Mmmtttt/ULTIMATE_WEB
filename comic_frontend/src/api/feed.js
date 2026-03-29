import request from './request'

export const feedApi = {
  createSession(mode = 'comic', strategyName = '') {
    const payload = { mode }
    if (strategyName) {
      payload.strategy_name = strategyName
    }
    return request.post('/v1/feed/session', payload)
  },

  refreshSession(sessionId = '', mode = 'comic', strategyName = '') {
    const payload = {}
    if (sessionId) {
      payload.session_id = sessionId
    } else {
      payload.mode = mode
    }
    if (strategyName) {
      payload.strategy_name = strategyName
    }
    return request.post('/v1/feed/session/refresh', payload)
  },

  getItems(sessionId, limit = 16) {
    return request.get('/v1/feed/items', {
      params: {
        session_id: sessionId,
        limit
      }
    })
  },

  getStrategies() {
    return request.get('/v1/feed/strategies')
  }
}

