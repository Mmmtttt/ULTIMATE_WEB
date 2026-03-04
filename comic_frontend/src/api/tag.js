/**
 * 标签相关 API
 */
import request from './request'

export const tagApi = {
  /**
   * 添加标签
   * @param {string} tagName - 标签名称
   * @param {string} contentType - 内容类型 'comic' 或 'video'
   * @returns {Promise}
   */
  add: (tagName, contentType = 'comic') => {
    return request.post('/v1/tag/add', { tag_name: tagName, content_type: contentType })
  },
  
  /**
   * 获取标签列表
   * @param {string} contentType - 内容类型 'comic' 或 'video'
   * @returns {Promise}
   */
  list: (contentType = 'comic') => {
    return request.get('/v1/tag/list', {
      params: { content_type: contentType }
    })
  },
  
  /**
   * 编辑标签
   * @param {string} tagId - 标签ID
   * @param {string} tagName - 新标签名称
   * @returns {Promise}
   */
  edit: (tagId, tagName) => {
    return request.put('/v1/tag/edit', { 
      tag_id: tagId, 
      tag_name: tagName 
    })
  },
  
  /**
   * 删除标签
   * @param {string} tagId - 标签ID
   * @returns {Promise}
   */
  delete: (tagId) => {
    return request.delete('/v1/tag/delete', { 
      data: { tag_id: tagId } 
    })
  },
  
  /**
   * 获取标签下的漫画
   * @param {string} tagId - 标签ID
   * @returns {Promise}
   */
  getComics: (tagId) => {
    return request.get('/v1/tag/comics', {
      params: { tag_id: tagId }
    })
  },

  /**
   * 获取标签下的视频
   * @param {string} tagId - 标签ID
   * @returns {Promise}
   */
  getVideos: (tagId) => {
    return request.get('/v1/tag/videos', {
      params: { tag_id: tagId }
    })
  },

  /**
   * 获取所有漫画（主页+推荐页）
   * @returns {Promise}
   */
  getAllComics: () => {
    return request.get('/v1/tag/all-comics')
  },

  /**
   * 批量添加标签（支持主页和推荐页）
   * @param {Array} comicData - 漫画数据数组，包含id和source
   * @param {Array} tagIds - 标签ID数组
   * @returns {Promise}
   */
  batchAddTags: (comicData, tagIds) => {
    return request.post('/v1/tag/batch-add-tags', {
      comic_data: comicData,
      tag_ids: tagIds
    })
  },

  /**
   * 批量移除标签（支持主页和推荐页）
   * @param {Array} comicData - 漫画数据数组，包含id和source
   * @param {Array} tagIds - 标签ID数组
   * @returns {Promise}
   */
  batchRemoveTags: (comicData, tagIds) => {
    return request.post('/v1/tag/batch-remove-tags', {
      comic_data: comicData,
      tag_ids: tagIds
    })
  },

  /**
   * 获取所有视频
   * @returns {Promise}
   */
  getAllVideos: () => {
    return request.get('/v1/tag/all-videos')
  },

  /**
   * 批量添加标签到视频
   * @param {Array} videoData - 视频数据数组，包含id
   * @param {Array} tagIds - 标签ID数组
   * @returns {Promise}
   */
  batchAddTagsToVideos: (videoData, tagIds) => {
    return request.post('/v1/tag/batch-add-tags-to-videos', {
      video_data: videoData,
      tag_ids: tagIds
    })
  },

  /**
   * 批量从视频移除标签
   * @param {Array} videoData - 视频数据数组，包含id
   * @param {Array} tagIds - 标签ID数组
   * @returns {Promise}
   */
  batchRemoveTagsFromVideos: (videoData, tagIds) => {
    return request.post('/v1/tag/batch-remove-tags-from-videos', {
      video_data: videoData,
      tag_ids: tagIds
    })
  }
}
