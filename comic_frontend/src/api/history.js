import request from './request'

export const historyApi = {
  list(contentType = 'comic') {
    return request.get('/v1/history/list', { params: { content_type: contentType } })
  },

  recordVisit({ contentType, contentId, id, source = 'local' }) {
    return request.post('/v1/history/visit', {
      content_type: contentType,
      content_id: contentId || id,
      source
    })
  }
}

export default historyApi
