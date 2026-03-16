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
    return request.get(`/v1/comic/list${queryString ? '?' + queryString : ''}`)
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
   * 第三方平台搜索漫画
   * @param {string} keyword - 搜索关键词
   * @param {string} platform - 平台（JM/PK/all）
   * @param {number} page - 页码
   * @param {number} limit - 数量
   * @returns {Promise}
   */
  searchThirdParty: (keyword, platform = 'all', page = 1, limit = 20) => {
    return request.get('/v1/comic/search-third-party', {
      params: { keyword, platform, page, limit }
    })
  },
  
  /**
   * 综合筛选漫画
   * @param {string[]} includeTagIds - 包含标签ID数组
   * @param {string[]} excludeTagIds - 排除标签ID数组
   * @param {string[]} authors - 作者名称数组
   * @param {string[]} listIds - 清单ID数组
   * @returns {Promise}
   */
  filter: (includeTagIds = [], excludeTagIds = [], authors = [], listIds = []) => {
    const params = new URLSearchParams()
    includeTagIds.forEach(id => params.append('include_tag_ids', id))
    excludeTagIds.forEach(id => params.append('exclude_tag_ids', id))
    authors.forEach(author => params.append('authors', author))
    listIds.forEach(id => params.append('list_ids', id))
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
  },
  
  download: async (comicId, comicTitle) => {
    const safeTitle = comicTitle.replace(/[^a-zA-Z0-9一-龥\s\-_]/g, '').trim()
    const filename = `${comicId}-${safeTitle}.zip`
    
    const response = await fetch(`/api/v1/comic/download?comic_id=${comicId}`)
    if (!response.ok) {
      throw new Error('下载失败')
    }
    
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  },
  
  /**
   * 整理数据库
   * @returns {Promise}
   */
  organizeDatabase: () => {
    return request.post('/v1/comic/organize')
  },

  /**
   * 检查漫画是否有可下载更新
   * @param {string} comicId - 漫画ID
   * @returns {Promise}
   */
  checkUpdate: (comicId) => {
    return request.post('/v1/comic/update/check', {
      comic_id: comicId
    })
  },

  /**
   * 下载漫画更新并回写本地页数
   * @param {string} comicId - 漫画ID
   * @param {boolean} force - 是否强制下载
   * @returns {Promise}
   */
  downloadUpdate: (comicId, force = false) => {
    return request.post('/v1/comic/update/download', {
      comic_id: comicId,
      force
    })
  },
  
  batchDownload: async (comicIds) => {
    const response = await fetch('/api/v1/comic/batch-download', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ comic_ids: comicIds })
    })
    
    if (!response.ok) {
      throw new Error('批量下载失败')
    }
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
    const filename = `comics_batch_${timestamp}.zip`
    
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  },
  
  upload: async (file) => {
    const formData = new FormData()
    formData.append('file', file)
    
    const response = await fetch('/api/v1/comic/upload', {
      method: 'POST',
      body: formData
    })
    
    const result = await response.json()
    if (result.code !== 200) {
      throw new Error(result.msg || '上传失败')
    }
    return result.data
  },
  
  batchUpload: async (files) => {
    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })
    
    const response = await fetch('/api/v1/comic/batch-upload', {
      method: 'POST',
      body: formData
    })
    
    const result = await response.json()
    if (result.code !== 200) {
      throw new Error(result.msg || '批量上传失败')
    }
    return result.data
  },
  
  onlineImport: async (data) => {
    return request.post('/v1/comic/import/online', data)
  },
  
  /**
   * 获取第三方库配置
   * @returns {Promise}
   */
  getThirdPartyConfig: () => {
    return request.get('/v1/comic/third-party/config')
  },
  
  /**
   * 保存第三方库配置
   * @param {object} data - 配置数据
   * @param {string} data.adapter - 适配器名称
   * @param {string} data.username - 用户名
   * @param {string} data.password - 密码
   * @param {string} data.download_dir - 下载目录
   * @returns {Promise}
   */
  saveThirdPartyConfig: (data) => {
    return request.post('/v1/comic/third-party/config', data)
  },
  
  // ==================== 回收站相关 ====================
  
  /**
   * 获取回收站漫画列表
   * @returns {Promise}
   */
  getTrashList: () => {
    return request.get('/v1/comic/trash/list')
  },
  
  /**
   * 移动漫画到回收站
   * @param {string} comicId - 漫画ID
   * @returns {Promise}
   */
  moveToTrash: (comicId) => {
    return request.put('/v1/comic/trash/move', { comic_id: comicId })
  },
  
  /**
   * 从回收站恢复漫画
   * @param {string} comicId - 漫画ID
   * @returns {Promise}
   */
  restoreFromTrash: (comicId) => {
    return request.put('/v1/comic/trash/restore', { comic_id: comicId })
  },
  
  /**
   * 批量移动漫画到回收站
   * @param {string[]} comicIds - 漫画ID数组
   * @returns {Promise}
   */
  batchMoveToTrash: (comicIds) => {
    return request.put('/v1/comic/trash/batch-move', { comic_ids: comicIds })
  },
  
  /**
   * 批量从回收站恢复漫画
   * @param {string[]} comicIds - 漫画ID数组
   * @returns {Promise}
   */
  batchRestoreFromTrash: (comicIds) => {
    return request.put('/v1/comic/trash/batch-restore', { comic_ids: comicIds })
  },
  
  /**
   * 永久删除漫画
   * @param {string} comicId - 漫画ID
   * @returns {Promise}
   */
  deletePermanently: (comicId) => {
    return request.delete('/v1/comic/trash/delete', { data: { comic_id: comicId } })
  },
  
  /**
   * 批量永久删除漫画
   * @param {string[]} comicIds - 漫画ID数组
   * @returns {Promise}
   */
  batchDeletePermanently: (comicIds) => {
    return request.delete('/v1/comic/trash/batch-delete', { data: { comic_ids: comicIds } })
  }
}

/**
 * @deprecated 请使用 tagApi，保留此导出以保持向后兼容
 * 从 ./tag.js 导入 tagApi
 */
export { tagApi } from './tag'
