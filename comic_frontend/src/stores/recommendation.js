import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { recommendationApi } from '@/api'
import { useCacheStore } from './cache'
import { SORT_TYPE } from '@/utils'

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

  // 当前选中的推荐漫画
  const currentRecommendation = ref(null)

  // 加载状态
  const loading = ref(false)

  // 错误信息
  const error = ref(null)

  // 当前排序方式
  const currentSort = ref(null)

  // 筛选结果
  const filteredRecommendations = ref([])

  // 是否正在筛选
  const isFiltering = ref(false)

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
    return recommendations.value.filter(rec => rec.current_page > 0).length
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

    loading.value = true
    error.value = null

    try {
      const params = {}
      if (options.sortType) {
        params.sort_type = options.sortType
      }
      if (options.minScore !== undefined) {
        params.min_score = options.minScore
      }
      if (options.maxScore !== undefined) {
        params.max_score = options.maxScore
      }

      console.log('[Recommendation] 调用 API 获取列表, params:', params)
      const response = await recommendationApi.getList(params)
      console.log('[Recommendation] API 返回数据:', response)

      if (response.code === 200) {
        recommendations.value = response.data || []
        // 缓存列表数据
        if (Object.keys(options).length === 0) {
          cacheStore.setRecommendationListCache(response.data)
        }
        return response.data
      } else {
        error.value = response.msg || '获取推荐列表失败'
        return []
      }
    } catch (err) {
      console.error('[Recommendation] 获取推荐列表失败:', err)
      error.value = '获取推荐列表失败'
      return []
    } finally {
      loading.value = false
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

    loading.value = true
    error.value = null

    try {
      const response = await recommendationApi.search(keyword)

      if (response.code === 200) {
        filteredRecommendations.value = response.data || []
        isFiltering.value = true
        return response.data
      } else {
        error.value = response.msg || '搜索失败'
        return []
      }
    } catch (err) {
      console.error('[Recommendation] 搜索失败:', err)
      error.value = '搜索失败'
      return []
    } finally {
      loading.value = false
    }
  }

  /**
   * 根据标签筛选
   * @param {string[]} includeTagIds - 包含的标签ID
   * @param {string[]} excludeTagIds - 排除的标签ID
   */
  async function filterByTags(includeTagIds = [], excludeTagIds = []) {
    console.log('[Recommendation] filterByTags called, include:', includeTagIds, 'exclude:', excludeTagIds)

    loading.value = true
    error.value = null

    try {
      const response = await recommendationApi.filterByTags(includeTagIds, excludeTagIds)

      if (response.code === 200) {
        filteredRecommendations.value = response.data || []
        isFiltering.value = true
        return response.data
      } else {
        error.value = response.msg || '筛选失败'
        return []
      }
    } catch (err) {
      console.error('[Recommendation] 筛选失败:', err)
      error.value = '筛选失败'
      return []
    } finally {
      loading.value = false
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

  /**
   * 设置排序方式
   * @param {string} sortType - 排序类型
   */
  function setSortType(sortType) {
    console.log('[Recommendation] setSortType called:', sortType)
    currentSort.value = sortType
  }

  /**
   * 清除排序
   */
  function clearSort() {
    console.log('[Recommendation] clearSort called')
    currentSort.value = null
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

  // ============ Return ============
  return {
    // State
    recommendations,
    currentRecommendation,
    loading,
    error,
    currentSort,
    filteredRecommendations,
    isFiltering,

    // Getters
    recommendationList,
    currentRecommendationInfo,
    totalCount,
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
    searchRecommendations,
    filterByTags,
    clearFilter,
    setSortType,
    clearSort,
    fetchImages,
    addRecommendation,
    deleteRecommendation
  }
})
