import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { videoApi } from '@/api/video'
import { showSuccessToast, showFailToast } from 'vant'

export const useVideoRecommendationStore = defineStore('videoRecommendation', () => {
  // State
  const recommendations = ref([])
  const currentRecommendation = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const currentSort = ref('create_time')
  const filters = ref({})

  // Getters
  const recommendationList = computed(() => recommendations.value)
  const totalCount = computed(() => recommendations.value.length)

  // Actions
  async function fetchRecommendations(force = false, params = {}) {
    if (!force && recommendations.value.length > 0 && Object.keys(params).length === 0) {
      return
    }

    loading.value = true
    error.value = null
    
    try {
      const queryParams = {
        sort_type: params.sortType || currentSort.value,
        ...filters.value,
        ...params
      }
      
      const res = await videoApi.getVideoRecommendationList(queryParams)
      if (res.code === 200) {
        recommendations.value = res.data || []
      }
    } catch (e) {
      error.value = e.message
      console.error('获取视频推荐列表失败:', e)
    } finally {
      loading.value = false
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

  async function updateScore(videoId, score) {
    try {
      const res = await videoApi.updateVideoRecommendationScore(videoId, score)
      if (res.code === 200) {
        // 更新列表中的数据
        const index = recommendations.value.findIndex(v => v.id === videoId)
        if (index !== -1) {
          recommendations.value[index].score = score
        }
        // 更新详情数据
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

  async function searchRecommendations(keyword) {
    loading.value = true
    try {
      const res = await videoApi.searchVideoRecommendations(keyword)
      if (res.code === 200) {
        recommendations.value = res.data || []
      }
    } catch (e) {
      console.error('搜索视频推荐失败:', e)
    } finally {
      loading.value = false
    }
  }

  function setSortType(type) {
    currentSort.value = type
  }

  function setFilter(key, value) {
    filters.value[key] = value
  }

  function clearFilter() {
    filters.value = {}
  }

  function clearSort() {
    currentSort.value = 'create_time'
  }

  return {
    recommendations,
    currentRecommendation,
    loading,
    error,
    currentSort,
    recommendationList,
    totalCount,
    fetchRecommendations,
    fetchDetail,
    updateScore,
    moveToTrash,
    batchMoveToTrash,
    searchRecommendations,
    setSortType,
    setFilter,
    clearFilter,
    clearSort
  }
})
