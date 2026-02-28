import request from './request'

export const configApi = {
  get() {
    return request.get('/v1/config')
  },
  
  update(data) {
    return request.put('/v1/config', data)
  },
  
  reset() {
    return request.post('/v1/config/reset')
  }
}

export default configApi
