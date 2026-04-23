import request from './request'

function encodeRequiredPlatform(platform) {
  const normalized = String(platform || '').trim().toLowerCase()
  if (!normalized) {
    throw new Error('platform is required')
  }
  return encodeURIComponent(normalized)
}

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
  
  batchMoveToTrash(videoIds) {
    return request.put('/v1/video/trash/batch-move', { video_ids: videoIds })
  },
  
  restoreFromTrash(videoId) {
    return request.put('/v1/video/trash/restore', { video_id: videoId })
  },
  
  deletePermanently(videoId) {
    return request.delete('/v1/video/trash/delete', { params: { video_id: videoId } })
  },
  
  batchRestoreFromTrash(videoIds) {
    return request.put('/v1/video/trash/batch-restore', { video_ids: videoIds })
  },
  
  batchDeletePermanently(videoIds) {
    return request.delete('/v1/video/trash/batch-delete', { data: { video_ids: videoIds } })
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

  localImportFromPath(sourcePath, options = {}) {
    const importMode = String(options?.importMode || 'hardlink_move').trim().toLowerCase() || 'hardlink_move'
    return request.post('/v1/video/local-import/from-path', {
      source_path: sourcePath,
      import_mode: importMode
    }, {
      timeout: 0
    })
  },
  
  getByTag(tagId) {
    return request.get(`/v1/video/tag/${tagId}`)
  },
  
  getByActor(actorName) {
    return request.get(`/v1/video/actor/${encodeURIComponent(actorName)}`)
  },
  
  thirdPartySearch(keyword, page = 1, platform = 'all') {
    return request.get('/v1/video/third-party/search', { params: { keyword, page, platform } })
  },

  thirdPartyPlatformHealthStatus(platform) {
    return request.get(`/v1/video/third-party/${encodeRequiredPlatform(platform)}/health-status`)
  },

  thirdPartyPlatformTags(platform, keyword = '', category = '') {
    return request.get(`/v1/video/third-party/${encodeRequiredPlatform(platform)}/tags`, {
      params: {
        keyword,
        category
      }
    })
  },

  thirdPartyPlatformSearchByTags(platform, tagIds = [], page = 1) {
    const normalizedPlatform = encodeRequiredPlatform(platform)
    const params = new URLSearchParams()
    tagIds.forEach(tagId => params.append('tag_ids', tagId))
    params.append('page', String(page))
    return request.get(`/v1/video/third-party/${normalizedPlatform}/search-by-tags?${params.toString()}`)
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
  
  thirdPartyImport(videoIdOrCode, target = 'home', platform) {
    return request.post('/v1/video/third-party/import', { video_id: videoIdOrCode, target, platform })
  },
  
  getPlayUrls(videoId) {
    return request.get(`/v1/video/${videoId}/play-urls`)
  },
  
  getRecommendationPlayUrls(videoId) {
    return request.get(`/v1/video/recommendation/${videoId}/play-urls`)
  },

  refreshPreviewVideo(videoId, source = 'local') {
    return request.post('/v1/video/preview-video/refresh', {
      video_id: videoId,
      source
    })
  },

  refreshLocalMetadata(videoId) {
    return request.post('/v1/video/local-metadata/refresh', {
      video_id: videoId
    })
  },
  
  getTags() {
    return request.get('/v1/video/tags')
  },
  
  bindTags(videoId, tagIdList) {
    return request.put('/v1/video/tag/bind', { video_id: videoId, tag_id_list: tagIdList })
  },

  editVideo(videoId, data) {
    return request.put('/v1/video/edit', {
      video_id: videoId,
      ...data
    })
  },
  
  filter(includeTags = [], excludeTags = [], authors = [], listIds = []) {
    const params = new URLSearchParams()
    includeTags.forEach(id => params.append('include_tag_ids', id))
    excludeTags.forEach(id => params.append('exclude_tag_ids', id))
    authors.forEach(author => params.append('authors', author))
    listIds.forEach(id => params.append('list_ids', id))
    return request.get(`/v1/video/filter?${params.toString()}`)
  },
  
  batchAddTags(videoIds, tagIds) {
    return request.put('/v1/video/tag/batch-add', { video_ids: videoIds, tag_ids: tagIds })
  },
  
  batchRemoveTags(videoIds, tagIds) {
    return request.put('/v1/video/tag/batch-remove', { video_ids: videoIds, tag_ids: tagIds })
  },
  
  getVideoRecommendationList(params = {}) {
    return request.get('/v1/video/recommendation/list', { params })
  },
  
  getVideoRecommendationDetail(videoId) {
    return request.get('/v1/video/recommendation/detail', { params: { video_id: videoId } })
  },
  
  updateVideoRecommendationScore(videoId, score) {
    return request.put('/v1/video/recommendation/score', { video_id: videoId, score })
  },
  
  moveVideoRecommendationToTrash(videoId) {
    return request.put('/v1/video/recommendation/trash/move', { video_id: videoId })
  },
  
  batchMoveVideoRecommendationToTrash(videoIds) {
    return request.put('/v1/video/recommendation/trash/batch-move', { video_ids: videoIds })
  },

  migrateRecommendationToLocal(videoIds) {
    return request.post('/v1/video/recommendation/migrate-to-local', { video_ids: videoIds })
  },
  
  getVideoRecommendationTrashList() {
    return request.get('/v1/video/recommendation/trash/list')
  },
  
  restoreVideoRecommendationFromTrash(videoId) {
    return request.put('/v1/video/recommendation/trash/restore', { video_id: videoId })
  },
  
  batchRestoreVideoRecommendationFromTrash(videoIds) {
    return request.put('/v1/video/recommendation/trash/batch-restore', { video_ids: videoIds })
  },
  
  deleteVideoRecommendationPermanently(videoId) {
    return request.delete('/v1/video/recommendation/trash/delete', { params: { video_id: videoId } })
  },
  
  batchDeleteVideoRecommendationPermanently(videoIds) {
    return request.delete('/v1/video/recommendation/trash/batch-delete', { data: { video_ids: videoIds } })
  },
  
  searchVideoRecommendations(keyword) {
    return request.get('/v1/video/recommendation/search', { params: { keyword } })
  },
  
  filterVideoRecommendations(includeTags = [], excludeTags = [], authors = [], listIds = []) {
    const params = new URLSearchParams()
    includeTags.forEach(id => params.append('include_tag_ids', id))
    excludeTags.forEach(id => params.append('exclude_tag_ids', id))
    authors.forEach(author => params.append('authors', author))
    listIds.forEach(id => params.append('list_ids', id))
    return request.get(`/v1/video/recommendation/filter?${params.toString()}`)
  },

  editVideoRecommendation(videoId, data) {
    return request.put('/v1/video/recommendation/edit', {
      video_id: videoId,
      ...data
    })
  },

  bindVideoRecommendationTags(videoId, tagIdList) {
    return request.put('/v1/video/recommendation/tag/bind', {
      video_id: videoId,
      tag_id_list: tagIdList
    })
  }
}

export const actorApi = {
  getList() {
    return request.get('/v1/actor/list')
  },
  
  getAll() {
    return request.get('/v1/actor/all')
  },
  
  subscribe(name) {
    return request.post('/v1/actor/subscribe', { name })
  },
  
  unsubscribe(actorId) {
    return request.delete('/v1/actor/unsubscribe', {
      data: { actor_id: actorId }
    })
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
  },

  /**
   * 检查演员订阅更新
   * @param {string|null} actorId 可选，传则检查单个
   */
  checkUpdates(actorId = null) {
    return request.post('/v1/actor/check-updates',
      actorId ? { actor_id: actorId } : {}
    )
  },

  /**
   * 获取演员新作品
   * @param {string} actorId - 演员ID
   * @returns {Promise}
   */
  getNewWorks: (actorId) => {
    return request.get(`/v1/actor/new-works/${actorId}`)
  },

  /**
   * 清除新作品计数
   * @param {string} actorId - 演员ID
   * @returns {Promise}
   */
  clearNewCount: (actorId) => {
    return request.post(`/v1/actor/clear-new-count/${actorId}`)
  },

  /**
   * 分页获取演员作品（已订阅演员使用，支持缓存）
   * @param {string} actorId - 演员ID
   * @param {number} offset - 偏移量
   * @param {number} limit - 每页数量
   * @returns {Promise}
   */
  getWorks(actorId, offset = 0, limit = 5, options = {}) {
    const cacheOnly = Boolean(options && options.cacheOnly)
    const forceRefresh = Boolean(options && options.forceRefresh)
    return request.get(`/v1/actor/works/${actorId}`, {
      params: { offset, limit, cache_only: cacheOnly, force_refresh: forceRefresh }
    })
  },

  /**
   * 清理演员封面缓存
   * @returns {Promise}
   */
  clearCoverCache: () => {
    return request.delete('/v1/actor/cover-cache/clear')
  },

  /**
   * 根据演员名搜索作品（不需要订阅，支持缓存）
   * @param {string} actorName - 演员名称
   * @param {number} offset - 偏移量
   * @param {number} limit - 每页数量
   * @returns {Promise}
   */
  searchWorksByName(actorName, offset = 0, limit = 5, options = {}) {
    const forceRefresh = Boolean(options && options.forceRefresh)
    return request.get('/v1/actor/search-works', {
      params: { actor_name: actorName, offset, limit, force_refresh: forceRefresh }
    })
  },

  /**
   * 清理演员作品缓存
   * @param {string} actorName - 演员名称（可选，不传则清理所有）
   * @returns {Promise}
   */
  clearWorksCache(actorName = null) {
    const params = actorName ? { actor_name: actorName } : {}
    return request.delete('/v1/actor/works-cache/clear', { params })
  }
}
