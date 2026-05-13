import request from './request'

export const uiStateApi = {
  get(scope, clientId) {
    return request.get('/v1/ui-state', {
      params: {
        scope,
        client_id: clientId,
      }
    })
  },

  save(scope, state, clientId) {
    return request.put('/v1/ui-state', {
      scope,
      client_id: clientId,
      state,
    })
  },

  clear(scope, clientId) {
    return request.delete('/v1/ui-state', {
      data: {
        scope,
        client_id: clientId,
      }
    })
  }
}
