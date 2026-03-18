/**
 * 婕敾鐩稿叧 API
 */
import request from './request'
import { triggerBlobDownload } from '@/runtime/browser'

export const comicApi = {
  /**
   * 鍒濆鍖栨极鐢绘暟鎹?
   * @param {object} data - 鍒濆鍖栨暟鎹?
   * @returns {Promise}
   */
  init: (data) => {
    return request.post('/v1/comic/init', data)
  },
  
  /**
   * 鑾峰彇婕敾鍒楄〃
   * @param {object} params - 鏌ヨ鍙傛暟
   * @param {string} params.sort_type - 鎺掑簭绫诲瀷锛坈reate_time/score/read_time锛?
   * @param {number} params.min_score - 鏈€浣庤瘎鍒?
   * @param {number} params.max_score - 鏈€楂樿瘎鍒?
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
   * 鑾峰彇婕敾璇︽儏
   * @param {string} comicId - 婕敾ID
   * @returns {Promise}
   */
  getDetail: (comicId) => {
    return request.get('/v1/comic/detail', {
      params: { comic_id: comicId }
    })
  },
  
  /**
   * 鑾峰彇婕敾鍥剧墖鍒楄〃
   * @param {string} comicId - 婕敾ID
   * @returns {Promise}
   */
  getImages: (comicId) => {
    return request.get('/v1/comic/images', {
      params: { comic_id: comicId }
    })
  },
  
  /**
   * 淇濆瓨闃呰杩涘害
   * @param {string} comicId - 婕敾ID
   * @param {number} currentPage - 褰撳墠椤电爜
   * @returns {Promise}
   */
  saveProgress: (comicId, currentPage) => {
    return request.put('/v1/comic/progress', {
      comic_id: comicId,
      current_page: currentPage
    })
  },
  
  /**
   * 鏇存柊璇勫垎
   * @param {string} comicId - 婕敾ID
   * @param {number} score - 璇勫垎
   * @returns {Promise}
   */
  updateScore: (comicId, score) => {
    return request.put('/v1/comic/score', {
      comic_id: comicId,
      score: score
    })
  },
  
  /**
   * 缁戝畾鏍囩
   * @param {string} comicId - 婕敾ID
   * @param {string[]} tagIdList - 鏍囩ID鍒楄〃
   * @returns {Promise}
   */
  bindTags: (comicId, tagIdList) => {
    return request.put('/v1/comic/tag/bind', {
      comic_id: comicId,
      tag_id_list: tagIdList
    })
  },
  
  /**
   * 鎵归噺娣诲姞鏍囩
   * @param {string[]} comicIds - 婕敾ID鏁扮粍
   * @param {string[]} tagIds - 鏍囩ID鏁扮粍
   * @returns {Promise}
   */
  batchAddTags: (comicIds, tagIds) => {
    return request.put('/v1/comic/tag/batch-add', {
      comic_ids: comicIds,
      tag_ids: tagIds
    })
  },
  
  /**
   * 鎵归噺绉婚櫎鏍囩
   * @param {string[]} comicIds - 婕敾ID鏁扮粍
   * @param {string[]} tagIds - 鏍囩ID鏁扮粍
   * @returns {Promise}
   */
  batchRemoveTags: (comicIds, tagIds) => {
    return request.put('/v1/comic/tag/batch-remove', {
      comic_ids: comicIds,
      tag_ids: tagIds
    })
  },
  
  /**
   * 缂栬緫婕敾淇℃伅
   * @param {string} comicId - 婕敾ID
   * @param {object} data - 缂栬緫鏁版嵁
   * @returns {Promise}
   */
  editComic: (comicId, data) => {
    return request.put('/v1/comic/edit', {
      comic_id: comicId,
      ...data
    })
  },
  
  /**
   * 鎼滅储婕敾
   * @param {string} keyword - 鎼滅储鍏抽敭璇?
   * @returns {Promise}
   */
  search: (keyword) => {
    return request.get('/v1/comic/search', {
      params: { keyword }
    })
  },
  
  /**
   * 绗笁鏂瑰钩鍙版悳绱㈡极鐢?
   * @param {string} keyword - 鎼滅储鍏抽敭璇?
   * @param {string} platform - 骞冲彴锛圝M/PK/all锛?
   * @param {number} page - 椤电爜
   * @param {number} limit - 鏁伴噺
   * @returns {Promise}
   */
  searchThirdParty: (keyword, platform = 'all', page = 1, limit = 20) => {
    return request.get('/v1/comic/search-third-party', {
      params: { keyword, platform, page, limit }
    })
  },
  
  /**
   * 缁煎悎绛涢€夋极鐢?
   * @param {string[]} includeTagIds - 鍖呭惈鏍囩ID鏁扮粍
   * @param {string[]} excludeTagIds - 鎺掗櫎鏍囩ID鏁扮粍
   * @param {string[]} authors - 浣滆€呭悕绉版暟缁?
   * @param {string[]} listIds - 娓呭崟ID鏁扮粍
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
   * 鑾峰彇婕敾鏍囩鍒楄〃
   * @returns {Promise}
   */
  getTags: () => {
    return request.get('/v1/comic/tags')
  },
  
  /**
   * 鎸夋帓搴忔柟寮忚幏鍙栧垪琛?
   * @param {string} sortType - 鎺掑簭绫诲瀷锛坈reate_time/score/read_time锛?
   * @returns {Promise}
   */
  getListBySort: (sortType) => {
    return request.get('/v1/comic/list', {
      params: { sort_type: sortType }
    })
  },
  
  /**
   * 鎸夎瘎鍒嗚寖鍥寸瓫閫?
   * @param {number} minScore - 鏈€浣庡垎
   * @param {number} maxScore - 鏈€楂樺垎
   * @returns {Promise}
   */
  filterByScore: (minScore, maxScore) => {
    return request.get('/v1/comic/filter-by-score', {
      params: { min_score: minScore, max_score: maxScore }
    })
  },
  
  download: async (comicId, comicTitle) => {
    const safeTitle = comicTitle.replace(/[^a-zA-Z0-9\u4e00-\u9fa5\s\-_]/g, '').trim()
    const filename = `${comicId}-${safeTitle}.zip`

    const response = await request.get('/v1/comic/download', {
      params: { comic_id: comicId },
      responseType: 'blob'
    })
    triggerBlobDownload(response.data, filename)
  },
  
  /**
   * 鏁寸悊鏁版嵁搴?
   * @returns {Promise}
   */
  organizeDatabase: () => {
    return request.post('/v1/comic/organize')
  },

  /**
   * 妫€鏌ユ极鐢绘槸鍚︽湁鍙笅杞芥洿鏂?   * @param {string} comicId - 婕敾ID
   * @returns {Promise}
   */
  checkUpdate: (comicId) => {
    return request.post('/v1/comic/update/check', {
      comic_id: comicId
    })
  },

  /**
   * 涓嬭浇婕敾鏇存柊骞跺洖鍐欐湰鍦伴〉鏁?   * @param {string} comicId - 婕敾ID
   * @param {boolean} force - 鏄惁寮哄埗涓嬭浇
   * @returns {Promise}
   */
  downloadUpdate: (comicId, force = false) => {
    return request.post('/v1/comic/update/download', {
      comic_id: comicId,
      force
    })
  },
  
  batchDownload: async (comicIds) => {
    const response = await request.post('/v1/comic/batch-download', {
      comic_ids: comicIds
    }, {
      responseType: 'blob'
    })

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
    const filename = `comics_batch_${timestamp}.zip`

    triggerBlobDownload(response.data, filename)
  },
  
  upload: async (file) => {
    const formData = new FormData()
    formData.append('file', file)

    const result = await request.post('/v1/comic/upload', formData)
    return result.data
  },
  
  batchUpload: async (files) => {
    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })

    const result = await request.post('/v1/comic/batch-upload', formData)
    return result.data
  },
  
  onlineImport: async (data) => {
    return request.post('/v1/comic/import/online', data)
  },
  
  /**
   * 鑾峰彇绗笁鏂瑰簱閰嶇疆
   * @returns {Promise}
   */
  getThirdPartyConfig: () => {
    return request.get('/v1/comic/third-party/config')
  },
  
  /**
   * 淇濆瓨绗笁鏂瑰簱閰嶇疆
   * @param {object} data - 閰嶇疆鏁版嵁
   * @param {string} data.adapter - 閫傞厤鍣ㄥ悕绉?
   * @param {string} data.username - 鐢ㄦ埛鍚?
   * @param {string} data.password - 瀵嗙爜
   * @param {string} data.download_dir - 涓嬭浇鐩綍
   * @returns {Promise}
   */
  saveThirdPartyConfig: (data) => {
    return request.post('/v1/comic/third-party/config', data)
  },
  
  // ==================== 鍥炴敹绔欑浉鍏?====================
  
  /**
   * 鑾峰彇鍥炴敹绔欐极鐢诲垪琛?
   * @returns {Promise}
   */
  getTrashList: () => {
    return request.get('/v1/comic/trash/list')
  },
  
  /**
   * 绉诲姩婕敾鍒板洖鏀剁珯
   * @param {string} comicId - 婕敾ID
   * @returns {Promise}
   */
  moveToTrash: (comicId) => {
    return request.put('/v1/comic/trash/move', { comic_id: comicId })
  },
  
  /**
   * 浠庡洖鏀剁珯鎭㈠婕敾
   * @param {string} comicId - 婕敾ID
   * @returns {Promise}
   */
  restoreFromTrash: (comicId) => {
    return request.put('/v1/comic/trash/restore', { comic_id: comicId })
  },
  
  /**
   * 鎵归噺绉诲姩婕敾鍒板洖鏀剁珯
   * @param {string[]} comicIds - 婕敾ID鏁扮粍
   * @returns {Promise}
   */
  batchMoveToTrash: (comicIds) => {
    return request.put('/v1/comic/trash/batch-move', { comic_ids: comicIds })
  },
  
  /**
   * 鎵归噺浠庡洖鏀剁珯鎭㈠婕敾
   * @param {string[]} comicIds - 婕敾ID鏁扮粍
   * @returns {Promise}
   */
  batchRestoreFromTrash: (comicIds) => {
    return request.put('/v1/comic/trash/batch-restore', { comic_ids: comicIds })
  },
  
  /**
   * 姘镐箙鍒犻櫎婕敾
   * @param {string} comicId - 婕敾ID
   * @returns {Promise}
   */
  deletePermanently: (comicId) => {
    return request.delete('/v1/comic/trash/delete', { data: { comic_id: comicId } })
  },
  
  /**
   * 鎵归噺姘镐箙鍒犻櫎婕敾
   * @param {string[]} comicIds - 婕敾ID鏁扮粍
   * @returns {Promise}
   */
  batchDeletePermanently: (comicIds) => {
    return request.delete('/v1/comic/trash/batch-delete', { data: { comic_ids: comicIds } })
  }
}

/**
 * @deprecated 璇蜂娇鐢?tagApi锛屼繚鐣欐瀵煎嚭浠ヤ繚鎸佸悜鍚庡吋瀹?
 * 浠?./tag.js 瀵煎叆 tagApi
 */
export { tagApi } from './tag'

