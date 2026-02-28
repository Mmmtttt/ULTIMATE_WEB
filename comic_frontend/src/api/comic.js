/**
 * 漫画相关 API
 */
import request from './request'

export const comicApi = {
  /**
   * 初始化漫画数据
   * @param {object} data - 初始化数据
   * @returns {Promise}
   */
  init: (data) => {
    return request.post('/v1/comic/init', data)
  },
  
  /**
   * 获取漫画列表
   * @returns {Promise}
   */
  getList: () => {
    return request.get('/v1/comic/list')
  },
  
  /**
   * 获取漫画详情
   * @param {string} comicId - 漫画ID
   * @returns {Promise}
   */
  getDetail: (comicId) => {
    return request.get('/v1/comic/detail', {
      params: { comic_id: comicId }
    })
  },
  
  /**
   * 获取漫画图片列表
   * @param {string} comicId - 漫画ID
   * @returns {Promise}
   */
  getImages: (comicId) => {
    return request.get('/v1/comic/images', {
      params: { comic_id: comicId }
    })
  },
  
  /**
   * 保存阅读进度
   * @param {string} comicId - 漫画ID
   * @param {number} currentPage - 当前页码
   * @returns {Promise}
   */
  saveProgress: (comicId, currentPage) => {
    return request.put('/v1/comic/progress', {
      comic_id: comicId,
      current_page: currentPage
    })
  },
  
  /**
   * 更新评分
   * @param {string} comicId - 漫画ID
   * @param {number} score - 评分
   * @returns {Promise}
   */
  updateScore: (comicId, score) => {
    return request.put('/v1/comic/score', {
      comic_id: comicId,
      score: score
    })
  },
  
  /**
   * 绑定标签
   * @param {string} comicId - 漫画ID
   * @param {string[]} tagIdList - 标签ID列表
   * @returns {Promise}
   */
  bindTags: (comicId, tagIdList) => {
    return request.put('/v1/comic/tag/bind', {
      comic_id: comicId,
      tag_id_list: tagIdList
    })
  },
  
  /**
   * 批量添加标签
   * @param {string[]} comicIds - 漫画ID数组
   * @param {string[]} tagIds - 标签ID数组
   * @returns {Promise}
   */
  batchAddTags: (comicIds, tagIds) => {
    return request.put('/v1/comic/tag/batch-add', {
      comic_ids: comicIds,
      tag_ids: tagIds
    })
  },
  
  /**
   * 批量移除标签
   * @param {string[]} comicIds - 漫画ID数组
   * @param {string[]} tagIds - 标签ID数组
   * @returns {Promise}
   */
  batchRemoveTags: (comicIds, tagIds) => {
    return request.put('/v1/comic/tag/batch-remove', {
      comic_ids: comicIds,
      tag_ids: tagIds
    })
  },
  
  /**
   * 编辑漫画信息
   * @param {string} comicId - 漫画ID
   * @param {object} data - 编辑数据
   * @returns {Promise}
   */
  editComic: (comicId, data) => {
    return request.put('/v1/comic/edit', {
      comic_id: comicId,
      ...data
    })
  },
  
  /**
   * 搜索漫画
   * @param {string} keyword - 搜索关键词
   * @returns {Promise}
   */
  search: (keyword) => {
    return request.get('/v1/comic/search', {
      params: { keyword }
    })
  },
  
  /**
   * 按标签筛选漫画
   * @param {string[]} includeTagIds - 包含标签ID数组
   * @param {string[]} excludeTagIds - 排除标签ID数组
   * @returns {Promise}
   */
  filter: (includeTagIds = [], excludeTagIds = []) => {
    const params = new URLSearchParams()
    includeTagIds.forEach(id => params.append('include_tag_ids', id))
    excludeTagIds.forEach(id => params.append('exclude_tag_ids', id))
    return request.get(`/v1/comic/filter?${params.toString()}`)
  },
  
  /**
   * 获取漫画标签列表
   * @returns {Promise}
   */
  getTags: () => {
    return request.get('/v1/comic/tags')
  },
  
  /**
   * 按排序方式获取列表
   * @param {string} sortType - 排序类型（create_time/score/read_time）
   * @returns {Promise}
   */
  getListBySort: (sortType) => {
    return request.get('/v1/comic/list', {
      params: { sort_type: sortType }
    })
  },
  
  /**
   * 按评分范围筛选
   * @param {number} minScore - 最低分
   * @param {number} maxScore - 最高分
   * @returns {Promise}
   */
  filterByScore: (minScore, maxScore) => {
    return request.get('/v1/comic/filter-by-score', {
      params: { min_score: minScore, max_score: maxScore }
    })
  }
}

/**
 * @deprecated 请使用 tagApi，保留此导出以保持向后兼容
 * 从 ./tag.js 导入 tagApi
 */
export { tagApi } from './tag'
