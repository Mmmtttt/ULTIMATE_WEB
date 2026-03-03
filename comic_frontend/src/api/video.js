import request from './request'

export const videoApi = {
  getList(params = {}) {
    return request.get('/v1/video/list', { params })
  },
  
  getDetail(videoId) {
    return request.get('/v1/video/detail', { params: { video_id: videoId } })
  },
  
  search(keyword) {
    return request.get('/v1/video/search', { params: { keyword } })
  },
  
  updateScore(videoId, score) {
    return request.put('/v1/video/score', { video_id: videoId, score })
  },
  
  updateProgress(videoId, unit) {
    return request.put('/v1/video/progress', { video_id: videoId, unit })
  },
  
  moveToTrash(videoId) {
    return request.put('/v1/video/trash/move', { video_id: videoId })
  },
  
  restoreFromTrash(videoId) {
    return request.put('/v1/video/trash/restore', { video_id: videoId })
  },
  
  deletePermanently(videoId) {
    return request.delete('/v1/video/trash/delete', { params: { video_id: videoId } })
  },
  
  getTrashList() {
    return request.get('/v1/video/trash/list')
  },
  
  importVideo(data) {
    return request.post('/v1/video/import', data)
  },
  
  batchImport(videos) {
    return request.post('/v1/video/import/batch', { videos })
  },
  
  getByTag(tagId) {
    return request.get(`/v1/video/tag/${tagId}`)
  },
  
  getByActor(actorName) {
    return request.get(`/v1/video/actor/${encodeURIComponent(actorName)}`)
  },
  
  thirdPartySearch(keyword) {
    return request.get('/v1/video/third-party/search', { params: { keyword } })
  },
  
  thirdPartyDetail(videoId) {
    return request.get('/v1/video/third-party/detail', { params: { video_id: videoId } })
  },
  
  thirdPartyActorSearch(actorName) {
    return request.get('/v1/video/third-party/actor/search', { params: { actor_name: actorName } })
  },
  
  thirdPartyActorWorks(actorId, page = 1) {
    return request.get('/v1/video/third-party/actor/works', { params: { actor_id: actorId, page } })
  },
  
  thirdPartyImport(videoId) {
    return request.post('/v1/video/third-party/import', { video_id: videoId })
  },
  
  getPlayUrls(videoId) {
    return request.get(`/v1/video/${videoId}/play-urls`)
  }
}

export const actorApi = {
  getList() {
    return request.get('/v1/actor/list')
  },
  
  getAll() {
    return request.get('/v1/actor/all')
  },
  
  subscribe(name, actorId = '') {
    return request.post('/v1/actor/subscribe', { name, actor_id: actorId })
  },
  
  unsubscribe(actorSubscriptionId) {
    return request.delete('/v1/actor/unsubscribe', { params: { actor_subscription_id: actorSubscriptionId } })
  },
  
  getVideos(actorName) {
    return request.get('/v1/actor/videos', { params: { actor_name: actorName } })
  },
  
  updateCheckTime(actorSubscriptionId) {
    return request.put('/v1/actor/update-check-time', { actor_subscription_id: actorSubscriptionId })
  },
  
  updateLastWork(actorSubscriptionId, workId, workTitle, newCount = 0) {
    return request.put('/v1/actor/update-last-work', {
      actor_subscription_id: actorSubscriptionId,
      work_id: workId,
      work_title: workTitle,
      new_count: newCount
    })
  }
}
