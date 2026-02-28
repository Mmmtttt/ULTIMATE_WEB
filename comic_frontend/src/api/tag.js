/**
 * 标签相关 API
 */
import request from './request'

export const tagApi = {
  /**
   * 添加标签
   * @param {string} tagName - 标签名称
   * @returns {Promise}
   */
  add: (tagName) => {
    return request.post('/v1/tag/add', { tag_name: tagName })
  },
  
  /**
   * 获取标签列表
   * @returns {Promise}
   */
  list: () => {
    return request.get('/v1/tag/list')
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
  }
}
