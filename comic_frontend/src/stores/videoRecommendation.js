import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { videoApi } from '@/api/video'
import { showSuccessToast, showFailToast } from 'vant'
import { extractAuthors, filterItemsByMinScore, normalizeMinScore, sortContentItems } from '@/utils'

export const useVideoRecommendationStore = defineStore('videoRecommendation', () => {
  // State
  const recommendations = ref([])
  const totalCountState = ref(0)
  const currentPageState = ref(1)
  const pageSizeState = ref(0)
  const totalPagesState = ref(1)
  const availableAuthors = ref([])
  const currentRecommendation = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const currentSort = ref(null)
  const currentSortOrder = ref('desc')
  const filters = ref({})
  const filteredRecommendations = ref([])
  const isFiltering = ref(false)
  const trashList = ref([])
  let listFetchSeq = 0

  // Getters
  const recommendationList = computed(() => isFiltering.value ? filteredRecommendations.value : recommendations.value)
  const totalCount = computed(() => recommendations.value.length)
  const queryTotalCount = computed(() => totalCountState.value || recommendations.value.length)
  const queryCurrentPage = computed(() => currentPageState.value || 1)
  const queryPageSize = computed(() => pageSizeState.value || recommendations.value.length || 0)
  const queryTotalPages = computed(() => totalPagesState.value || 1)

  // Actions
  async function fetchRecommendations(force = false, params = {}) {
    if (!force && recommendations.value.length > 0 && Object.keys(params).length === 0) {
      return
    }

    const requestSeq = ++listFetchSeq
    loading.value = true
    error.value = null
    
    try {
      const queryParams = {
        ...filters.value,
        ...params
      }
      const sortTypeToUse = params.sortType || currentSort.value
      if (sortTypeToUse) {
        queryParams.sort_type = sortTypeToUse
      }
      const sortOrderToUse = params.sortOrder || currentSortOrder.value
      if (sortTypeToUse && sortOrderToUse) {
        queryParams.sort_order = sortOrderToUse
      }
      
      const res = await videoApi.getVideoRecommendationList(queryParams)
      if (requestSeq !== listFetchSeq) {
        return recommendations.value
      }
      if (res.code === 200) {
        const payload = res.data
        if (payload && typeof payload === 'object' && Array.isArray(payload.items)) {
          recommendations.value = payload.items || []
          totalCountState.value = Number(payload.total) || recommendations.value.length
          currentPageState.value = Number(payload.page) || 1
          pageSizeState.value = Number(payload.page_size) || recommendations.value.length || 0
          totalPagesState.value = Number(payload.total_pages) || 1
          availableAuthors.value = Array.isArray(payload.available_authors) ? payload.available_authors : extractAuthors(recommendations.value)
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
      }
    } catch (e) {
      if (requestSeq === listFetchSeq) {
        error.value = e.message
      }
      console.error('获取视频推荐列表失败:', e)
    } finally {
      if (requestSeq === listFetchSeq) {
        loading.value = false
      }
    }
  }

  async function fetchDetail(videoId) {
    loading.value = true
    error.value = null
    
    try {
      const res = await videoApi.getVideoRecommendationDetail(videoId)
      if (res.code === 200) {
        currentRecommendation.value = res.data
        return res.data
      }
      return null
    } catch (e) {
      error.value = e.message
      console.error('获取视频推荐详情失败:', e)
      return null
    } finally {
      loading.value = false
    }
  }

  async function fetchRecommendationDetail(videoId) {
    return fetchDetail(videoId)
  }

  async function fetchDetailSnapshot(videoId) {
    const res = await videoApi.getVideoRecommendationDetail(videoId)
    if (res.code === 200) {
      return res.data || null
    }
    return null
  }

  async function updateScore(videoId, score) {
    try {
      const res = await videoApi.updateVideoRecommendationScore(videoId, score)
      if (res.code === 200) {
        const index = recommendations.value.findIndex(v => v.id === videoId)
        if (index !== -1) {
          recommendations.value[index].score = score
        }
        if (currentRecommendation.value && currentRecommendation.value.id === videoId) {
          currentRecommendation.value.score = score
        }
        return true
      }
      return false
    } catch (e) {
      console.error('更新评分失败:', e)
      return false
    }
  }

  async function moveToTrash(videoId) {
    try {
      const res = await videoApi.moveVideoRecommendationToTrash(videoId)
      if (res.code === 200) {
        recommendations.value = recommendations.value.filter(v => v.id !== videoId)
        if (currentRecommendation.value && currentRecommendation.value.id === videoId) {
          currentRecommendation.value = null
        }
        return true
      }
      return false
    } catch (e) {
      console.error('移入回收站失败:', e)
      return false
    }
  }

  async function batchMoveToTrash(videoIds) {
    try {
      const res = await videoApi.batchMoveVideoRecommendationToTrash(videoIds)
      if (res.code === 200) {
        recommendations.value = recommendations.value.filter(v => !videoIds.includes(v.id))
        return true
      }
      return false
    } catch (e) {
      console.error('批量移入回收站失败:', e)
      return false
    }
  }

  async function fetchTrashList() {
    loading.value = true
    try {
      const res = await videoApi.getVideoRecommendationTrashList()
      if (res.code === 200) {
        trashList.value = res.data || []
      }
    } catch (e) {
      console.error('获取推荐视频回收站列表失败:', e)
    } finally {
      loading.value = false
    }
  }

  async function restoreFromTrash(videoId) {
    try {
      const res = await videoApi.restoreVideoRecommendationFromTrash(videoId)
      if (res.code === 200) {
        trashList.value = trashList.value.filter(v => v.id !== videoId)
        return true
      }
      return false
    } catch (e) {
      console.error('从回收站恢复失败:', e)
      return false
    }
  }
  
  async function batchRestoreFromTrash(videoIds) {
    try {
      const res = await videoApi.batchRestoreVideoRecommendationFromTrash(videoIds)
      if (res.code === 200) {
        trashList.value = trashList.value.filter(v => !videoIds.includes(v.id))
        return true
      }
      return false
    } catch (e) {
      console.error('批量从回收站恢复失败:', e)
      return false
    }
  }

  async function deletePermanently(videoId) {
    try {
      const res = await videoApi.deleteVideoRecommendationPermanently(videoId)
      if (res.code === 200) {
        trashList.value = trashList.value.filter(v => v.id !== videoId)
        return true
      }
      return false
    } catch (e) {
      console.error('永久删除失败:', e)
      return false
    }
  }
  
  async function batchDeletePermanently(videoIds) {
    try {
      const res = await videoApi.batchDeleteVideoRecommendationPermanently(videoIds)
      if (res.code === 200) {
        trashList.value = trashList.value.filter(v => !videoIds.includes(v.id))
        return true
      }
      return false
    } catch (e) {
      console.error('批量永久删除失败:', e)
      return false
    }
  }

  async function searchRecommendations(keyword) {
    loading.value = true
    try {
      const res = await videoApi.searchVideoRecommendations(keyword)
      if (res.code === 200) {
        filteredRecommendations.value = res.data || []
        isFiltering.value = true
        return filteredRecommendations.value
      }
      return []
    } catch (e) {
      console.error('搜索视频推荐失败:', e)
      return []
    } finally {
      loading.value = false
    }
  }

  async function migrateToLocal(videoIds) {
    return videoApi.migrateRecommendationToLocal(videoIds)
  }

  async function refreshPreviewVideo(videoId, source = 'preview') {
    const response = await videoApi.refreshPreviewVideo(videoId, source)
    if (response.code === 200 && response.data) {
      currentRecommendation.value = response.data
      recommendations.value = recommendations.value.map((item) => (item.id === videoId ? response.data : item))
    }
    return response
  }

  async function fetchTags() {
    return videoApi.getTags()
  }

  async function editRecommendation(videoId, data) {
    const response = await videoApi.editVideoRecommendation(videoId, data)
    if (response.code === 200) {
      recommendations.value = recommendations.value.map((item) =>
        item.id === videoId
          ? {
              ...item,
              ...data,
              actors: Array.isArray(data.actors)
                ? data.actors
                : String(data.actors || '')
                    .split(',')
                    .map((actor) => actor.trim())
                    .filter(Boolean),
            }
          : item
      )
      if (currentRecommendation.value?.id === videoId) {
        currentRecommendation.value = {
          ...currentRecommendation.value,
          ...data,
          actors: Array.isArray(data.actors)
            ? data.actors
            : String(data.actors || '')
                .split(',')
                .map((actor) => actor.trim())
                .filter(Boolean),
        }
      }
    }
    return response
  }

  async function bindTags(videoId, tagIds) {
    const response = await videoApi.bindVideoRecommendationTags(videoId, tagIds)
    if (response.code === 200) {
      if (currentRecommendation.value?.id === videoId) {
        currentRecommendation.value = {
          ...currentRecommendation.value,
          tag_ids: [...tagIds],
        }
      }
      recommendations.value = recommendations.value.map((item) =>
        item.id === videoId ? { ...item, tag_ids: [...tagIds] } : item
      )
    }
    return response
  }

  async function getPlayUrls(videoId, params = {}) {
    return videoApi.getRecommendationPlayUrls(videoId, params)
  }

  async function filterByTags(includeTagIds = [], excludeTagIds = []) {
    console.log('[Video Recommendation] filterByTags called, include:', includeTagIds, 'exclude:', excludeTagIds)
    
    loading.value = true
    error.value = null
    
    try {
      const response = await videoApi.filterVideoRecommendations(includeTagIds, excludeTagIds)
      
      if (response.code === 200) {
        filteredRecommendations.value = response.data || []
        isFiltering.value = true
        return response.data
      } else {
        error.value = response.msg || '筛选失败'
        return []
      }
    } catch (err) {
      console.error('[Video Recommendation] 筛选失败:', err)
      error.value = '筛选失败'
      return []
    } finally {
      loading.value = false
    }
  }

  async function filterMulti(includeTags = [], excludeTags = [], authors = [], listIds = [], minScore = 0, sortType = currentSort.value, sortOrder = currentSortOrder.value) {
    const scoreThreshold = normalizeMinScore(minScore)
    const hasMultiFilter = includeTags.length > 0 || excludeTags.length > 0 || authors.length > 0 || listIds.length > 0
    const hasScoreFilter = scoreThreshold > 0

    console.log('[Video Recommendation] 综合筛选:', { includeTags, excludeTags, authors, listIds, minScore: scoreThreshold })
    
    if (!hasMultiFilter && !hasScoreFilter) {
      isFiltering.value = false
      return recommendations.value
    }
    
    loading.value = true
    error.value = null
    
    try {
      let result = []

      if (hasMultiFilter) {
        const response = await videoApi.filterVideoRecommendations(includeTags, excludeTags, authors, listIds)
        if (response.code !== 200) {
          error.value = response.msg || '筛选失败'
          return []
        }
        result = response.data || []
      } else {
        result = recommendations.value
      }
      
      filteredRecommendations.value = sortContentItems(
        filterItemsByMinScore(result, scoreThreshold),
        sortType,
        sortOrder
      )
      isFiltering.value = true
      return filteredRecommendations.value
    } catch (err) {
      console.error('[Video Recommendation] 综合筛选失败:', err)
      error.value = '筛选失败'
      return []
    } finally {
      loading.value = false
    }
  }

  function clearFilter() {
    console.log('[Video Recommendation] clearFilter called')
    filteredRecommendations.value = []
    isFiltering.value = false
    filters.value = {}
  }

  async function saveCustomOrder(videoIds = []) {
    return videoApi.updateVideoRecommendationCustomOrder(videoIds)
  }

  async function fetchCustomOrderItems(params = {}) {
    const response = await videoApi.getVideoRecommendationList({
      ...params,
      summary: 1
    })
    return Array.isArray(response.data) ? response.data : []
  }

  function setSortType(type, order = 'desc') {
    currentSort.value = type || null
    currentSortOrder.value = order || 'desc'
  }

  function setFilter(key, value) {
    filters.value[key] = value
  }

  function clearSort() {
    currentSort.value = null
    currentSortOrder.value = 'desc'
  }

  return {
    recommendations,
    currentRecommendation,
    loading,
    error,
    currentSort,
    currentSortOrder,
    filters,
    filteredRecommendations,
    isFiltering,
    trashList,
    recommendationList,
    totalCount,
    queryTotalCount,
    queryCurrentPage,
    queryPageSize,
    queryTotalPages,
    availableAuthors,
    fetchRecommendations,
    fetchDetail,
    fetchRecommendationDetail,
    fetchDetailSnapshot,
    updateScore,
    moveToTrash,
    batchMoveToTrash,
    migrateToLocal,
    refreshPreviewVideo,
    fetchTags,
    editRecommendation,
    bindTags,
    getPlayUrls,
    fetchTrashList,
    restoreFromTrash,
    batchRestoreFromTrash,
    deletePermanently,
    batchDeletePermanently,
    searchRecommendations,
    filterByTags,
    filterMulti,
    saveCustomOrder,
    fetchCustomOrderItems,
    clearFilter,
    setSortType,
    setFilter,
    clearSort
  }
})
