import request from './request'

export const organizeApi = {
  getOptions: (mode = 'comic') => {
    return request.get('/v1/organize/options', {
      params: { mode }
    })
  },

  run: (mode, action) => {
    return request.post('/v1/organize/run', {
      mode,
      action
    }, {
      timeout: 0
    })
  }
}
