/**
 * 作者订阅相关 API
 */
import request from './request'

export const authorApi = {
  /**
   * 获取订阅作者列表
   * @returns {Promise}
   */
  getList: () => {
    return request.get('/v1/author/list')
  },

  /**
   * 订阅作者
   * @param {string} name - 作者名称
   * @returns {Promise}
   */
  subscribe: (name) => {
    return request.post('/v1/author/subscribe', { name })
  },

  /**
   * 取消订阅
   * @param {string} authorId - 作者ID
   * @returns {Promise}
   */
  unsubscribe: (authorId) => {
    return request.delete('/v1/author/unsubscribe', {
      data: { author_id: authorId }
    })
  },

  /**
   * 检查作者更新
   * @param {string} authorId - 作者ID（可选，不传则检查所有）
   * @returns {Promise}
   */
  checkUpdates: (authorId = null) => {
    return request.post('/v1/author/check-updates', 
      authorId ? { author_id: authorId } : {}
    )
  },

  /**
   * 获取作者新作品
   * @param {string} authorId - 作者ID
   * @returns {Promise}
   */
  getNewWorks: (authorId) => {
    return request.get(`/v1/author/new-works/${authorId}`)
  },

  /**
   * 清除新作品计数
   * @param {string} authorId - 作者ID
   * @returns {Promise}
   */
  clearNewCount: (authorId) => {
    return request.post(`/v1/author/clear-new-count/${authorId}`)
  },

  /**
   * 分页获取作者作品
   * @param {string} authorId - 作者ID
   * @param {number} offset - 偏移量
   * @param {number} limit - 每页数量
   * @returns {Promise}
   */
  getWorks: (authorId, offset = 0, limit = 5) => {
    return request.get(`/v1/author/works/${authorId}`, {
      params: { offset, limit }
    })
  },

  /**
   * 批量获取作品详情
   * @param {string[]} ids - 作品ID列表
   * @returns {Promise}
   */
  getWorksBatchDetail: (ids) => {
    return request.post('/v1/author/works/batch-detail', { ids })
  },

  /**
   * 清理作者封面缓存
   * @returns {Promise}
   */
  clearCoverCache: () => {
    return request.delete('/v1/author/cover-cache/clear')
  },

  /**
   * 清理作者作品数据缓存
   * @returns {Promise}
   */
  clearWorksCache: () => {
    return request.delete('/v1/author/works-cache/clear')
  },

  /**
   * 获取所有作者（主页+推荐页）
   * @returns {Promise}
   */
  getAllAuthors: () => {
    return request.get('/v1/author/all')
  },

  /**
   * 根据作者名搜索作品（不需要订阅）
   * @param {string} authorName - 作者名称
   * @param {number} offset - 偏移量
   * @param {number} limit - 每页数量
   * @returns {Promise}
   */
  searchWorksByName: (authorName, offset = 0, limit = 5) => {
    return request.get('/v1/author/search-works', {
      params: { author_name: authorName, offset, limit }
    })
  }
}
