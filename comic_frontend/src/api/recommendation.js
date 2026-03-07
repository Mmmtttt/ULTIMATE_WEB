/**
 * 推荐漫画相关 API
 * 与 comicApi 功能一致，但操作推荐页数据
 */
import request from './request'

export const recommendationApi = {
  /**
   * 获取推荐漫画列表
   * @param {object} params - 查询参数
   * @param {string} params.sort_type - 排序类型（create_time/score/read_time）
   * @param {number} params.min_score - 最低评分
   * @param {number} params.max_score - 最高评分
   * @returns {Promise}
   */
  getList: (params = {}) => {
    const queryParams = new URLSearchParams()
    if (params.sort_type) {
      queryParams.append('sort_type', params.sort_type)
    }
    if (params.min_score !== undefined) {
      queryParams.append('min_score', params.min_score)
    }
    if (params.max_score !== undefined) {
      queryParams.append('max_score', params.max_score)
    }
    const queryString = queryParams.toString()
    return request.get(`/v1/recommendation/list${queryString ? '?' + queryString : ''}`)
  },

  /**
   * 获取推荐漫画详情
   * @param {string} recommendationId - 推荐漫画ID
   * @returns {Promise}
   */
  getDetail: (recommendationId) => {
    return request.get('/v1/recommendation/detail', {
      params: { recommendation_id: recommendationId }
    })
  },

  /**
   * 获取推荐漫画图片列表
   * @param {string} recommendationId - 推荐漫画ID
   * @returns {Promise}
   */
  getImages: (recommendationId) => {
    return request.get('/v1/recommendation/images', {
      params: { recommendation_id: recommendationId }
    })
  },

  /**
   * 保存阅读进度
   * @param {string} recommendationId - 推荐漫画ID
   * @param {number} currentPage - 当前页码
   * @returns {Promise}
   */
  saveProgress: (recommendationId, currentPage) => {
    return request.put('/v1/recommendation/progress', {
      recommendation_id: recommendationId,
      current_page: currentPage
    })
  },

  /**
   * 更新评分
   * @param {string} recommendationId - 推荐漫画ID
   * @param {number} score - 评分
   * @returns {Promise}
   */
  updateScore: (recommendationId, score) => {
    return request.put('/v1/recommendation/score', {
      recommendation_id: recommendationId,
      score: score
    })
  },

  /**
   * 绑定标签
   * @param {string} recommendationId - 推荐漫画ID
   * @param {string[]} tagIdList - 标签ID列表
   * @returns {Promise}
   */
  bindTags: (recommendationId, tagIdList) => {
    return request.put('/v1/recommendation/tag/bind', {
      recommendation_id: recommendationId,
      tag_id_list: tagIdList
    })
  },

  /**
   * 搜索推荐漫画
   * @param {string} keyword - 搜索关键词
   * @returns {Promise}
   */
  search: (keyword) => {
    return request.get('/v1/recommendation/search', {
      params: { keyword }
    })
  },

  /**
   * 根据标签筛选
   * @param {string[]} includeTagIds - 包含的标签ID
   * @param {string[]} excludeTagIds - 排除的标签ID
   * @returns {Promise}
   */
  filter: (includeTagIds = [], excludeTagIds = [], authors = [], listIds = []) => {
    const params = new URLSearchParams()
    includeTagIds.forEach(id => params.append('include_tag_ids', id))
    excludeTagIds.forEach(id => params.append('exclude_tag_ids', id))
    authors.forEach(author => params.append('authors', author))
    listIds.forEach(id => params.append('list_ids', id))
    return request.get(`/v1/recommendation/filter?${params.toString()}`)
  },
  
  filterByTags: (includeTagIds = [], excludeTagIds = []) => {
    const params = new URLSearchParams()
    includeTagIds.forEach(id => params.append('include_tag_ids', id))
    excludeTagIds.forEach(id => params.append('exclude_tag_ids', id))
    return request.get(`/v1/recommendation/filter?${params.toString()}`)
  },

  /**
   * 批量添加标签
   * @param {string[]} recommendationIds - 推荐漫画ID列表
   * @param {string[]} tagIds - 标签ID列表
   * @returns {Promise}
   */
  batchAddTags: (recommendationIds, tagIds) => {
    return request.put('/v1/recommendation/tag/batch-add', {
      recommendation_ids: recommendationIds,
      tag_ids: tagIds
    })
  },

  /**
   * 批量移除标签
   * @param {string[]} recommendationIds - 推荐漫画ID列表
   * @param {string[]} tagIds - 标签ID列表
   * @returns {Promise}
   */
  batchRemoveTags: (recommendationIds, tagIds) => {
    return request.put('/v1/recommendation/tag/batch-remove', {
      recommendation_ids: recommendationIds,
      tag_ids: tagIds
    })
  },

  /**
   * 添加推荐漫画
   * @param {object} data - 漫画数据
   * @returns {Promise}
   */
  add: (data) => {
    return request.post('/v1/recommendation/add', data)
  },

  /**
   * 删除推荐漫画
   * @param {string} recommendationId - 推荐漫画ID
   * @returns {Promise}
   */
  delete: (recommendationId) => {
    return request.delete('/v1/recommendation/delete', {
      params: { recommendation_id: recommendationId }
    })
  },

  /**
   * 编辑推荐漫画元数据
   * @param {string} recommendationId - 推荐漫画ID
   * @param {object} data - 元数据
   * @returns {Promise}
   */
  edit: (recommendationId, data) => {
    return request.put('/v1/recommendation/edit', {
      recommendation_id: recommendationId,
      ...data
    })
  },
  
  // ==================== 回收站相关 ====================
  
  /**
   * 获取回收站漫画列表
   * @returns {Promise}
   */
  getTrashList: () => {
    return request.get('/v1/recommendation/trash/list')
  },
  
  /**
   * 移动漫画到回收站
   * @param {string} recommendationId - 漫画ID
   * @returns {Promise}
   */
  moveToTrash: (recommendationId) => {
    return request.put('/v1/recommendation/trash/move', { recommendation_id: recommendationId })
  },
  
  /**
   * 从回收站恢复漫画
   * @param {string} recommendationId - 漫画ID
   * @returns {Promise}
   */
  restoreFromTrash: (recommendationId) => {
    return request.put('/v1/recommendation/trash/restore', { recommendation_id: recommendationId })
  },
  
  /**
   * 批量移动漫画到回收站
   * @param {string[]} recommendationIds - 漫画ID数组
   * @returns {Promise}
   */
  batchMoveToTrash: (recommendationIds) => {
    return request.put('/v1/recommendation/trash/batch-move', { recommendation_ids: recommendationIds })
  },
  
  /**
   * 批量从回收站恢复漫画
   * @param {string[]} recommendationIds - 漫画ID数组
   * @returns {Promise}
   */
  batchRestoreFromTrash: (recommendationIds) => {
    return request.put('/v1/recommendation/trash/batch-restore', { recommendation_ids: recommendationIds })
  },
  
  /**
   * 永久删除漫画
   * @param {string} recommendationId - 漫画ID
   * @returns {Promise}
   */
  deletePermanently: (recommendationId) => {
    return request.delete('/v1/recommendation/trash/delete', { data: { recommendation_id: recommendationId } })
  },
  
  /**
   * 批量永久删除漫画
   * @param {string[]} recommendationIds - 漫画ID数组
   * @returns {Promise}
   */
  batchDeletePermanently: (recommendationIds) => {
    return request.delete('/v1/recommendation/trash/batch-delete', { data: { recommendation_ids: recommendationIds } })
  },
  
  // ==================== 缓存相关 ====================
  
  /**
   * 下载漫画到缓存
   * @param {string} recommendationId - 漫画ID
   * @returns {Promise}
   */
  downloadToCache: (recommendationId) => {
    return request.post('/v1/recommendation/cache/download', { recommendation_id: recommendationId })
  },
  
  /**
   * 获取缓存图片
   * @param {string} recommendationId - 漫画ID
   * @param {number} pageNum - 页码
   * @returns {string} 图片URL
   */
  getCachedImageUrl: (recommendationId, pageNum) => {
    return `/api/v1/recommendation/cache/image?recommendation_id=${recommendationId}&page_num=${pageNum}`
  },
  
  /**
   * 获取漫画缓存状态
   * @param {string} recommendationId - 漫画ID
   * @returns {Promise}
   */
  getCacheStatus: (recommendationId) => {
    return request.get('/v1/recommendation/cache/status', {
      params: { recommendation_id: recommendationId }
    })
  },
  
  /**
   * 获取缓存统计信息
   * @returns {Promise}
   */
  getCacheStats: () => {
    return request.get('/v1/recommendation/cache/stats')
  },
  
  /**
   * 清空缓存
   * @returns {Promise}
   */
  clearCache: () => {
    return request.delete('/v1/recommendation/cache/clear')
  },
  
  /**
   * 从缓存中移除指定漫画
   * @param {string} recommendationId - 漫画ID
   * @returns {Promise}
   */
  removeFromCache: (recommendationId) => {
    return request.delete('/v1/recommendation/cache/remove', {
      params: { recommendation_id: recommendationId }
    })
  }
}
