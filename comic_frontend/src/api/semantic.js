import request from './request'

export const semanticApi = {
  // 语义检索状态：平台是否支持、索引是否建好、向量模型是否可用
  getStatus() {
    return request.get('/v1/semantic-search/status')
  },

  // 重建语义索引（桌面端可用；首次带向量构建可能需要下载模型）
  rebuild(buildEmbeddings = true) {
    return request.post('/v1/semantic-search/rebuild', { build_embeddings: Boolean(buildEmbeddings) })
  },

  // 直接查询语义索引（调试/命中来源用）
  search(params = {}) {
    return request.get('/v1/semantic-search/search', { params })
  },

  // ---------- 识图补全（VLM 生成 vibe / catalog / tags 草稿） ----------
  getVisionStatus() {
    return request.get('/v1/semantic-search/vision/status')
  },

  getVisionProviders() {
    return request.get('/v1/semantic-search/vision/providers')
  },

  // 用已保存（或刚填的）Key 拉取服务商模型列表
  fetchVisionModels(payload = {}) {
    return request.post('/v1/semantic-search/vision/models', payload)
  },

  // 批量补全：对缺梗概/速览的漫画排队跑识图
  listVisionMissing(onlyMissing = true) {
    return request.get('/v1/semantic-search/vision/missing', { params: { only_missing: onlyMissing ? 1 : 0 } })
  },

  startVisionBatch(payload = {}) {
    return request.post('/v1/semantic-search/vision/batch', payload)
  },

  getVisionBatch() {
    return request.get('/v1/semantic-search/vision/batch')
  },

  stopVisionBatch() {
    return request.post('/v1/semantic-search/vision/batch/stop')
  },

  listDrafts() {
    return request.get('/v1/semantic-search/vision/drafts')
  },

  getDraft(comicId) {
    return request.get('/v1/semantic-search/vision/drafts', { params: { comic_id: comicId } })
  },

  listVisionFailures() {
    return request.get('/v1/semantic-search/vision/failures')
  },

  clearVisionFailure(comicId) {
    return request.delete(`/v1/semantic-search/vision/failures/${comicId}`)
  },

  createDraft(comicId) {
    return request.post('/v1/semantic-search/vision/drafts', { comic_id: comicId })
  },

  applyDraft(comicId, accept = {}) {
    return request.post(`/v1/semantic-search/vision/drafts/${comicId}/apply`, accept)
  },

  deleteDraft(comicId) {
    return request.delete(`/v1/semantic-search/vision/drafts/${comicId}`)
  }
}

export default semanticApi
