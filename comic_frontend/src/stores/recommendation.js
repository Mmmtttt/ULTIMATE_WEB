import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { recommendationApi } from '@/api'
import { useCacheStore } from './cache'
import { extractAuthors, filterItemsByMinScore, filterItemsByUnread, isReadByProgress, normalizeMinScore, sortContentItems } from '@/utils'

/**
 * 推荐漫画管理 Store
 * 管理推荐漫画列表、详情和相关操作
 * 与 useComicStore 功能一致，但操作推荐页数据
 */
export const useRecommendationStore = defineStore('recommendation', () => {
  // ============ Dependencies ============
  const cacheStore = useCacheStore()

  // ============ State ============

  // 推荐漫画列表
  const recommendations = ref([])
  const totalCountState = ref(0)
  const currentPageState = ref(1)
  const pageSizeState = ref(0)
  const totalPagesState = ref(1)
  const availableAuthors = ref([])

  // 当前选中的推荐漫画
  const currentRecommendation = ref(null)

  // 加载状态
  const loading = ref(false)

  // 错误信息
  const error = ref(null)

  // 当前排序方式
  const currentSort = ref(null)
  const currentSortOrder = ref('desc')

  // 筛选结果
  const filteredRecommendations = ref([])

  // 是否正在筛选
  const isFiltering = ref(false)
  let listFetchSeq = 0

  // ============ Getters ============

  /**
   * 推荐漫画列表（根据状态返回筛选结果或全部）
   */
  const recommendationList = computed(() => {
    return isFiltering.value ? filteredRecommendations.value : recommendations.value
  })

  /**
   * 当前推荐漫画信息
   */
  const currentRecommendationInfo = computed(() => currentRecommendation.value)

  /**
   * 推荐漫画总数
   */
  const totalCount = computed(() => recommendations.value.length)
  const queryTotalCount = computed(() => totalCountState.value || recommendations.value.length)
  const queryCurrentPage = computed(() => currentPageState.value || 1)
  const queryPageSize = computed(() => pageSizeState.value || recommendations.value.length || 0)
  const queryTotalPages = computed(() => totalPagesState.value || 1)

  /**
   * 当前显示数量
   */
  const displayCount = computed(() => recommendationList.value.length)

  /**
   * 根据ID获取推荐漫画
   */
  const getRecommendationById = computed(() => (id) => {
    return recommendations.value.find(rec => rec.id === id) || null
  })

  /**
   * 已读推荐漫画数量
   */
  const readCount = computed(() => {
    return recommendations.value.filter(rec => isReadByProgress(rec.current_page)).length
  })

  /**
   * 已评分推荐漫画数量
   */
  const scoredCount = computed(() => {
    return recommendations.value.filter(rec => rec.score > 0).length
  })

  // ============ Actions ============

  /**
   * 获取推荐漫画列表
   * @param {boolean} forceRefresh - 是否强制刷新
   * @param {object} options - 可选参数
   * @param {string} options.sortType - 排序类型
   * @param {number} options.minScore - 最低评分
   * @param {number} options.maxScore - 最高评分
   * @returns {Array} 推荐漫画列表
   */
  async function fetchRecommendations(forceRefresh = false, options = {}) {
    console.log('[Recommendation] fetchRecommendations called, forceRefresh:', forceRefresh, 'options:', options)

    if (!forceRefresh && Object.keys(options).length === 0) {
      const cached = cacheStore.getRecommendationListCache()
      if (cached) {
        console.log('[Recommendation] 使用缓存数据')
        recommendations.value = cached
        return cached
      }
    }

    const requestSeq = ++listFetchSeq
    loading.value = true
    error.value = null

    try {
      const params = { ...options }
      const sortTypeToUse = options.sortType || currentSort.value
      if (sortTypeToUse) {
        params.sort_type = sortTypeToUse
      }
      const sortOrderToUse = options.sortOrder || currentSortOrder.value
      if (sortTypeToUse && sortOrderToUse) {
        params.sort_order = sortOrderToUse
      }
      if (options.minScore !== undefined) {
        params.min_score = options.minScore
      }
      if (options.maxScore !== undefined) {
        params.max_score = options.maxScore
      }

      console.log('[Recommendation] 调用 API 获取列表, params:', params)
      const response = await recommendationApi.getList(params)
      if (requestSeq !== listFetchSeq) {
        return recommendations.value
      }
      console.log('[Recommendation] API 返回数据:', response)

      if (response.code === 200) {
        const payload = response.data
        if (payload && typeof payload === 'object' && Array.isArray(payload.items)) {
          recommendations.value = payload.items || []
          totalCountState.value = Number(payload.total) || recommendations.value.length
          currentPageState.value = Number(payload.page) || 1
          pageSizeState.value = Number(payload.page_size) || recommendations.value.length || 0
          totalPagesState.value = Number(payload.total_pages) || 1
          if (Array.isArray(payload.available_authors)) {
            availableAuthors.value = payload.available_authors
          } else if (availableAuthors.value.length === 0) {
            availableAuthors.value = extractAuthors(recommendations.value)
          }
        } else {
          recommendations.value = Array.isArray(payload) ? payload : []
          totalCountState.value = recommendations.value.length
          currentPageState.value = 1
          pageSizeState.value = recommendations.value.length
          totalPagesState.value = 1
          availableAuthors.value = extractAuthors(recommendations.value)
        }
        isFiltering.value = false
        filteredRecommendations.value = []
        // 缓存列表数据
        if (Object.keys(options).length === 0) {
          cacheStore.setRecommendationListCache(recommendations.value)
        }
        return recommendations.value
      } else {
        error.value = response.msg || '获取推荐列表失败'
        return []
      }
    } catch (err) {
      console.error('[Recommendation] 获取推荐列表失败:', err)
      if (requestSeq === listFetchSeq) {
        error.value = '获取推荐列表失败'
      }
      return []
    } finally {
      if (requestSeq === listFetchSeq) {
        loading.value = false
      }
    }
  }

  /**
   * 获取推荐漫画详情
   * @param {string} recommendationId - 推荐漫画ID
   * @param {boolean} forceRefresh - 是否强制刷新
   * @returns {object} 推荐漫画详情
   */
  async function fetchRecommendationDetail(recommendationId, forceRefresh = false) {
    console.log('[Recommendation] fetchRecommendationDetail called, id:', recommendationId)

    if (!forceRefresh) {
      const cached = cacheStore.getRecommendationDetailCache(recommendationId)
      if (cached) {
        console.log('[Recommendation] 使用详情缓存')
        currentRecommendation.value = cached
        return cached
      }
    }

    loading.value = true
    error.value = null

    try {
      const response = await recommendationApi.getDetail(recommendationId)
      console.log('[Recommendation] 详情 API 返回:', response)

      if (response.code === 200) {
        currentRecommendation.value = response.data
        cacheStore.setRecommendationDetailCache(recommendationId, response.data)
        return response.data
      } else {
        error.value = response.msg || '获取详情失败'
        return null
      }
    } catch (err) {
      console.error('[Recommendation] 获取详情失败:', err)
      error.value = '获取详情失败'
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * 保存阅读进度
   * @param {string} recommendationId - 推荐漫画ID
   * @param {number} currentPage - 当前页码
   */
  async function saveProgress(recommendationId, currentPage) {
    console.log('[Recommendation] saveProgress called, id:', recommendationId, 'page:', currentPage)

    try {
      const response = await recommendationApi.saveProgress(recommendationId, currentPage)

      if (response.code === 200) {
        // 更新本地数据
        const rec = recommendations.value.find(r => r.id === recommendationId)
        if (rec) {
          rec.current_page = currentPage
        }
        if (currentRecommendation.value?.id === recommendationId) {
          currentRecommendation.value.current_page = currentPage
        }
        // 清除缓存
        cacheStore.clearRecommendationDetailCache(recommendationId)
        return true
      }
      return false
    } catch (err) {
      console.error('[Recommendation] 保存进度失败:', err)
      return false
    }
  }

  /**
   * 更新评分
   * @param {string} recommendationId - 推荐漫画ID
   * @param {number} score - 评分
   */
  async function updateScore(recommendationId, score) {
    console.log('[Recommendation] updateScore called, id:', recommendationId, 'score:', score)

    try {
      const response = await recommendationApi.updateScore(recommendationId, score)

      if (response.code === 200) {
        // 更新本地数据
        const rec = recommendations.value.find(r => r.id === recommendationId)
        if (rec) {
          rec.score = score
        }
        if (currentRecommendation.value?.id === recommendationId) {
          currentRecommendation.value.score = score
        }
        // 清除缓存
        cacheStore.clearRecommendationDetailCache(recommendationId)
        return true
      }
      return false
    } catch (err) {
      console.error('[Recommendation] 更新评分失败:', err)
      return false
    }
  }

  /**
   * 绑定标签
   * @param {string} recommendationId - 推荐漫画ID
   * @param {string[]} tagIdList - 标签ID列表
   */
  async function bindTags(recommendationId, tagIdList) {
    console.log('[Recommendation] bindTags called, id:', recommendationId, 'tags:', tagIdList)

    try {
      const response = await recommendationApi.bindTags(recommendationId, tagIdList)

      if (response.code === 200) {
        // 更新本地数据
        const rec = recommendations.value.find(r => r.id === recommendationId)
        if (rec) {
          rec.tag_ids = tagIdList
        }
        if (currentRecommendation.value?.id === recommendationId) {
          currentRecommendation.value.tag_ids = tagIdList
        }
        // 清除缓存
        cacheStore.clearRecommendationDetailCache(recommendationId)
        return true
      }
      return false
    } catch (err) {
      console.error('[Recommendation] 绑定标签失败:', err)
      return false
    }
  }

  /**
   * 搜索推荐漫画
   * @param {string} keyword - 搜索关键词
   */
  async function searchRecommendations(keyword) {
    console.log('[Recommendation] searchRecommendations called, keyword:', keyword)

    try {
      const normalizedKeyword = String(keyword || '').trim()
      if (!normalizedKeyword) {
        isFiltering.value = false
        return recommendations.value
      }
      return await fetchRecommendations(true, {
        paginate: 1,
        summary: 1,
        page: 1,
        page_size: 120,
        keyword: normalizedKeyword
      })
    } catch (err) {
      console.error('[Recommendation] 搜索失败:', err)
      error.value = '搜索失败'
      return []
    }
  }

  /**
   * 根据标签筛选
   * @param {string[]} includeTagIds - 包含的标签ID
   * @param {string[]} excludeTagIds - 排除的标签ID
   */
  async function filterByTags(includeTagIds = [], excludeTagIds = []) {
    console.log('[Recommendation] filterByTags called, include:', includeTagIds, 'exclude:', excludeTagIds)

    try {
      if (includeTagIds.length === 0 && excludeTagIds.length === 0) {
        isFiltering.value = false
        return recommendations.value
      }
      return await fetchRecommendations(true, {
        paginate: 1,
        summary: 1,
        page: 1,
        page_size: 120,
        include_tag_ids: [...includeTagIds],
        exclude_tag_ids: [...excludeTagIds]
      })
    } catch (err) {
      console.error('[Recommendation] 筛选失败:', err)
      error.value = '筛选失败'
      return []
    }
  }
  
  /**
   * 综合筛选（标签、作者、清单）
   * @param {string[]} includeTags - 包含的标签ID
   * @param {string[]} excludeTags - 排除的标签ID
   * @param {string[]} authors - 作者名称
   * @param {string[]} listIds - 清单ID
   * @param {number} minScore - 最低评分
   * @param {boolean} unreadOnly - 仅未读
   * @returns {Array} 筛选结果
   */
  async function filterMulti(includeTags = [], excludeTags = [], authors = [], listIds = [], minScore = 0, unreadOnly = false, sortType = currentSort.value, sortOrder = currentSortOrder.value) {
    const scoreThreshold = normalizeMinScore(minScore)
    const hasMultiFilter = includeTags.length > 0 || excludeTags.length > 0 || authors.length > 0 || listIds.length > 0
    const hasScoreFilter = scoreThreshold > 0
    const hasUnreadFilter = Boolean(unreadOnly)

    console.log('[Recommendation] 综合筛选:', { includeTags, excludeTags, authors, listIds, minScore: scoreThreshold, unreadOnly: hasUnreadFilter })
    
    if (!hasMultiFilter && !hasScoreFilter && !hasUnreadFilter) {
      isFiltering.value = false
      return recommendations.value
    }
    
    try {
      const params = {
        paginate: 1,
        summary: 1,
        page: 1,
        page_size: 120
      }
      if (includeTags.length > 0) {
        params.include_tag_ids = [...includeTags]
      }
      if (excludeTags.length > 0) {
        params.exclude_tag_ids = [...excludeTags]
      }
      if (authors.length > 0) {
        params.authors = [...authors]
      }
      if (listIds.length > 0) {
        params.list_ids = [...listIds]
      }
      if (scoreThreshold > 0) {
        params.min_score = scoreThreshold
      }
      if (hasUnreadFilter) {
        params.unread_only = 1
      }
      if (sortType) {
        params.sort_type = sortType
        params.sort_order = sortOrder
      }
      return await fetchRecommendations(true, params)
    } catch (err) {
      console.error('[Recommendation] 综合筛选失败:', err)
      error.value = '筛选失败'
      return []
    }
  }

  /**
   * 清空筛选
   */
  function clearFilter() {
    console.log('[Recommendation] clearFilter called')
    filteredRecommendations.value = []
    isFiltering.value = false
  }

  async function saveCustomOrder(recommendationIds = []) {
    return recommendationApi.updateCustomOrder(recommendationIds)
  }

  async function fetchCustomOrderItems(options = {}) {
    const response = await recommendationApi.getList({
      ...options,
      summary: 1
    })
    if (response.data && typeof response.data === 'object' && Array.isArray(response.data.items)) {
      return response.data.items
    }
    return Array.isArray(response.data) ? response.data : []
  }

  /**
   * 设置排序方式
   * @param {string} sortType - 排序类型
   */
  function setSortType(sortType, sortOrder = 'desc') {
    console.log('[Recommendation] setSortType called:', sortType, sortOrder)
    currentSort.value = sortType
    currentSortOrder.value = sortOrder
  }

  async function editRecommendation(recommendationId, data) {
    try {
      const response = await recommendationApi.edit(recommendationId, data)
      if (response.code === 200) {
        recommendations.value = recommendations.value.map((item) =>
          item.id === recommendationId ? { ...item, ...data } : item
        )
        if (currentRecommendation.value?.id === recommendationId) {
          currentRecommendation.value = {
            ...currentRecommendation.value,
            ...data,
          }
        }
        cacheStore.clearRecommendationDetailCache(recommendationId)
      }
      return response
    } catch (err) {
      console.error('[Recommendation] 编辑失败:', err)
      throw err
    }
  }

  async function moveToTrash(recommendationId) {
    const response = await recommendationApi.moveToTrash(recommendationId)
    if (response.code === 200) {
      recommendations.value = recommendations.value.filter((item) => item.id !== recommendationId)
      if (currentRecommendation.value?.id === recommendationId) {
        currentRecommendation.value = null
      }
      cacheStore.clearRecommendationDetailCache(recommendationId)
    }
    return response
  }

  async function batchMoveToTrash(recommendationIds) {
    const response = await recommendationApi.batchMoveToTrash(recommendationIds)
    if (response.code === 200) {
      const idSet = new Set(recommendationIds)
      recommendations.value = recommendations.value.filter((item) => !idSet.has(item.id))
    }
    return response
  }

  async function migrateToLocal(recommendationIds) {
    return recommendationApi.migrateToLocal(recommendationIds)
  }

  /**
   * 清除排序
   */
  function clearSort() {
    console.log('[Recommendation] clearSort called')
    currentSort.value = null
    currentSortOrder.value = 'desc'
  }

  /**
   * 获取图片列表
   * @param {string} recommendationId - 推荐漫画ID
   * @returns {Array} 图片列表
   */
  async function fetchImages(recommendationId) {
    console.log('[Recommendation] fetchImages called, id:', recommendationId)

    try {
      const response = await recommendationApi.getImages(recommendationId)

      if (response.code === 200) {
        return response.data || []
      }
      return []
    } catch (err) {
      console.error('[Recommendation] 获取图片列表失败:', err)
      return []
    }
  }

  /**
   * 添加推荐漫画
   * @param {object} data - 漫画数据
   */
  async function addRecommendation(data) {
    console.log('[Recommendation] addRecommendation called:', data)

    try {
      const response = await recommendationApi.add(data)

      if (response.code === 200) {
        // 刷新列表
        await fetchRecommendations(true)
        return true
      }
      return false
    } catch (err) {
      console.error('[Recommendation] 添加推荐漫画失败:', err)
      return false
    }
  }

  /**
   * 删除推荐漫画
   * @param {string} recommendationId - 推荐漫画ID
   */
  async function deleteRecommendation(recommendationId) {
    console.log('[Recommendation] deleteRecommendation called, id:', recommendationId)

    try {
      const response = await recommendationApi.delete(recommendationId)

      if (response.code === 200) {
        // 从本地列表中移除
        recommendations.value = recommendations.value.filter(r => r.id !== recommendationId)
        // 清除缓存
        cacheStore.clearRecommendationDetailCache(recommendationId)
        return true
      }
      return false
    } catch (err) {
      console.error('[Recommendation] 删除推荐漫画失败:', err)
      return false
    }
  }

  function clearCache(type = 'all', id = null) {
    cacheStore.clearCache(type, id)
  }

  // ============ Return ============
  return {
    // State
    recommendations,
    currentRecommendation,
    loading,
    error,
    currentSort,
    currentSortOrder,
    filteredRecommendations,
    isFiltering,

    // Getters
    recommendationList,
    currentRecommendationInfo,
    totalCount,
    queryTotalCount,
    queryCurrentPage,
    queryPageSize,
    queryTotalPages,
    availableAuthors,
    displayCount,
    getRecommendationById,
    readCount,
    scoredCount,

    // Actions
    fetchRecommendations,
    fetchRecommendationDetail,
    saveProgress,
    updateScore,
    bindTags,
    editRecommendation,
    moveToTrash,
    batchMoveToTrash,
    migrateToLocal,
    searchRecommendations,
    filterByTags,
    filterMulti,
    saveCustomOrder,
    fetchCustomOrderItems,
    clearFilter,
    setSortType,
    clearSort,
    fetchImages,
    addRecommendation,
    deleteRecommendation,
    clearCache
  }
})
