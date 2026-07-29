import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { videoApi } from '../api/video'
import { extractAuthors, filterItemsByMinScore, normalizeMinScore, sortContentItems } from '@/utils'

export const useVideoStore = defineStore('video', () => {
  const videos = ref([])
  const totalCountState = ref(0)
  const currentPageState = ref(1)
  const pageSizeState = ref(0)
  const totalPagesState = ref(1)
  const availableAuthors = ref([])
  const currentVideo = ref(null)
  const trashList = ref([])
  const loading = ref(false)
  const error = ref(null)
  const filteredVideos = ref([])
  const isFiltering = ref(false)
  const currentSort = ref(null)
  const currentSortOrder = ref('desc')
  
  const videoCount = computed(() => videos.value.length)
  const queryTotalCount = computed(() => totalCountState.value || videos.value.length)
  const queryCurrentPage = computed(() => currentPageState.value || 1)
  const queryPageSize = computed(() => pageSizeState.value || videos.value.length || 0)
  const queryTotalPages = computed(() => totalPagesState.value || 1)
  const trashCount = computed(() => trashList.value.length)
  const videoList = computed(() => isFiltering.value ? filteredVideos.value : videos.value)
  
  async function fetchList(params = {}) {
    loading.value = true
    error.value = null
    try {
      const queryParams = { ...params }
      const sortTypeToUse = params.sort_type || currentSort.value
      if (sortTypeToUse) {
        queryParams.sort_type = sortTypeToUse
      }
      const sortOrderToUse = params.sort_order || currentSortOrder.value
      if (sortTypeToUse && sortOrderToUse) {
        queryParams.sort_order = sortOrderToUse
      }
      const res = await videoApi.getList(queryParams)
      if (res.code === 200) {
        const payload = res.data
        if (payload && typeof payload === 'object' && Array.isArray(payload.items)) {
          videos.value = payload.items || []
          totalCountState.value = Number(payload.total) || videos.value.length
          currentPageState.value = Number(payload.page) || 1
          pageSizeState.value = Number(payload.page_size) || videos.value.length || 0
          totalPagesState.value = Number(payload.total_pages) || 1
          availableAuthors.value = Array.isArray(payload.available_authors) ? payload.available_authors : extractAuthors(videos.value)
        } else {
          videos.value = Array.isArray(payload) ? payload : []
          totalCountState.value = videos.value.length
          currentPageState.value = 1
          pageSizeState.value = videos.value.length
          totalPagesState.value = 1
          availableAuthors.value = extractAuthors(videos.value)
        }
        isFiltering.value = false
        filteredVideos.value = []
      }
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }
  
  async function fetchDetail(videoId) {
    loading.value = true
    error.value = null
    try {
      const res = await videoApi.getDetail(videoId)
      if (res.code === 200) {
        currentVideo.value = res.data
        return res.data
      }
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }
  
  async function search(keyword) {
    loading.value = true
    error.value = null
    try {
      const res = await videoApi.search(keyword)
      if (res.code === 200) {
        return res.data || []
      }
      return []
    } catch (e) {
      error.value = e.message
      return []
    } finally {
      loading.value = false
    }
  }
  
  async function updateScore(videoId, score) {
    try {
      const res = await videoApi.updateScore(videoId, score)
      return res.code === 200
    } catch (e) {
      return false
    }
  }
  
  async function updateProgress(videoId, unit) {
    try {
      const res = await videoApi.updateProgress(videoId, unit)
      return res.code === 200
    } catch (e) {
      return false
    }
  }

  async function fetchDetailSnapshot(videoId) {
    const res = await videoApi.getDetail(videoId)
    if (res.code === 200) {
      return res.data || null
    }
    return null
  }

  async function bindTags(videoId, tagIdList) {
    try {
      const response = await videoApi.bindTags(videoId, tagIdList)
      return response
    } catch (e) {
      throw e
    }
  }

  async function editVideo(videoId, data) {
    try {
      const response = await videoApi.editVideo(videoId, data)
      return response
    } catch (e) {
      throw e
    }
  }
  
  async function moveToTrash(videoId) {
    try {
      const res = await videoApi.moveToTrash(videoId)
      if (res.code === 200) {
        videos.value = videos.value.filter(v => v.id !== videoId)
        return true
      }
      return false
    } catch (e) {
      return false
    }
  }
  
  async function batchMoveToTrash(videoIds) {
    try {
      const res = await videoApi.batchMoveToTrash(videoIds)
      if (res.code === 200) {
        videos.value = videos.value.filter(v => !videoIds.includes(v.id))
        return true
      }
      return false
    } catch (e) {
      return false
    }
  }
  
  async function restoreFromTrash(videoId) {
    try {
      const res = await videoApi.restoreFromTrash(videoId)
      return res.code === 200
    } catch (e) {
      return false
    }
  }
  
  async function deletePermanently(videoId) {
    try {
      const res = await videoApi.deletePermanently(videoId)
      if (res.code === 200) {
        trashList.value = trashList.value.filter(v => v.id !== videoId)
        return true
      }
      return false
    } catch (e) {
      return false
    }
  }
  
  async function fetchTrashList() {
    loading.value = true
    try {
      const res = await videoApi.getTrashList()
      if (res.code === 200) {
        trashList.value = res.data || []
      }
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }
  
  async function importVideo(data) {
    try {
      const res = await videoApi.importVideo(data)
      return res
    } catch (e) {
      return { code: 500, message: e.message }
    }
  }
  
  async function thirdPartySearch(keyword, platform = 'all', page = 1, limit = 20) {
    if (!keyword || keyword.trim() === '') {
      return { results: [], platform_info: {}, page: 1, limit: 20, has_more: false }
    }
    loading.value = true
    try {
      const res = await videoApi.thirdPartySearch(keyword, page, platform)
      if (res.code === 200 && res.data) {
        return {
          results: Array.isArray(res.data.videos) ? res.data.videos : [],
          platform: res.data.platform || 'all',
          platform_info: res.data.platform_info || {},
          page: res.data.page || 1,
          total_pages: res.data.total_pages || 1,
          has_more: Boolean(res.data.has_next),
          total: res.data.total || 0,
        }
      }
      return { results: [], platform: 'all', platform_info: {}, page: 1, limit: 20, has_more: false }
    } catch (e) {
      console.error('[Video] 第三方搜索失败:', e)
      return { results: [], platform: 'all', platform_info: {}, page: 1, limit: 20, has_more: false }
    } finally {
      loading.value = false
    }
  }
  
  async function thirdPartyDetail(videoId) {
    loading.value = true
    try {
      const res = await videoApi.thirdPartyDetail(videoId)
      if (res.code === 200) {
        return res.data
      }
      return null
    } catch (e) {
      return null
    } finally {
      loading.value = false
    }
  }
  
  async function thirdPartyImport(videoId, target = 'home', platform = '') {
    try {
      const res = await videoApi.thirdPartyImport(videoId, target, platform)
      return res
    } catch (e) {
      return { code: 500, message: e.message }
    }
  }

  async function refreshPreviewVideo(videoId, source = 'local') {
    const response = await videoApi.refreshPreviewVideo(videoId, source)
    if (response.code === 200 && response.data) {
      currentVideo.value = response.data
      videos.value = videos.value.map((video) => (video.id === videoId ? response.data : video))
    }
    return response
  }

  async function refreshLocalMetadata(videoId) {
    const response = await videoApi.refreshLocalMetadata(videoId)
    if (response.code === 200 && response.data) {
      currentVideo.value = response.data
      videos.value = videos.value.map((video) => (video.id === videoId ? response.data : video))
    }
    return response
  }

  async function generateLocalThumbnails(videoId) {
    const response = await videoApi.generateLocalThumbnails(videoId)
    if (response.code === 200 && response.data) {
      currentVideo.value = response.data
      videos.value = videos.value.map((video) => (video.id === videoId ? response.data : video))
    }
    return response
  }

  async function selectLocalThumbnailCover(videoId, coverIndex) {
    const response = await videoApi.selectLocalThumbnailCover(videoId, coverIndex)
    if (response.code === 200 && response.data) {
      currentVideo.value = response.data
      videos.value = videos.value.map((video) => (video.id === videoId ? response.data : video))
    }
    return response
  }

  async function getPlayUrls(videoId, params = {}) {
    return videoApi.getPlayUrls(videoId, params)
  }
  
  async function filterByTags(includeTags = [], excludeTags = []) {
    if (includeTags.length === 0 && excludeTags.length === 0) {
      isFiltering.value = false
      return videos.value
    }
    
    loading.value = true
    
    try {
      const response = await videoApi.filter(includeTags, excludeTags)
      if (response.code === 200) {
        filteredVideos.value = response.data || []
        isFiltering.value = true
        return filteredVideos.value
      }
      return []
    } catch (err) {
      console.error('[Video] 筛选视频失败:', err)
      return []
    } finally {
      loading.value = false
    }
  }
  
  async function filterMulti(includeTags = [], excludeTags = [], authors = [], listIds = [], minScore = 0, sortType = currentSort.value, sortOrder = currentSortOrder.value) {
    const scoreThreshold = normalizeMinScore(minScore)
    const hasMultiFilter = includeTags.length > 0 || excludeTags.length > 0 || authors.length > 0 || listIds.length > 0
    const hasScoreFilter = scoreThreshold > 0

    if (!hasMultiFilter && !hasScoreFilter) {
      isFiltering.value = false
      return videos.value
    }
    
    loading.value = true
    
    try {
      console.log('[Video] 综合筛选:', { includeTags, excludeTags, authors, listIds, minScore: scoreThreshold })
      let result = []

      if (hasMultiFilter) {
        const response = await videoApi.filter(includeTags, excludeTags, authors, listIds)
        if (response.code !== 200) {
          return []
        }
        result = response.data || []
      } else {
        result = videos.value
      }

      filteredVideos.value = sortContentItems(
        filterItemsByMinScore(result, scoreThreshold),
        sortType,
        sortOrder
      )
      isFiltering.value = true
      return filteredVideos.value
    } catch (err) {
      console.error('[Video] 综合筛选视频失败:', err)
      return []
    } finally {
      loading.value = false
    }
  }
  
  async function sortVideos(sortType, sortOrder = 'desc') {
    loading.value = true
    currentSort.value = sortType || null
    currentSortOrder.value = sortOrder || 'desc'
    try {
      const params = {}
      if (sortType) {
        params.sort_type = sortType
        params.sort_order = sortOrder
      }
      const res = await videoApi.getList(params)
      if (res.code === 200) {
        videos.value = res.data || []
      }
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }
  
  function clearFilter() {
    isFiltering.value = false
    filteredVideos.value = []
  }

  async function saveCustomOrder(videoIds = []) {
    return videoApi.updateCustomOrder(videoIds)
  }

  async function fetchCustomOrderItems(params = {}) {
    const response = await videoApi.getList({
      ...params,
      summary: 1
    })
    return Array.isArray(response.data) ? response.data : []
  }

  function setSortState(sortType = null, sortOrder = 'desc') {
    currentSort.value = sortType || null
    currentSortOrder.value = sortOrder || 'desc'
  }
  
  function clearCurrentVideo() {
    currentVideo.value = null
  }
  
  return {
    videos,
    currentVideo,
    trashList,
    loading,
    error,
    currentSort,
    currentSortOrder,
    filteredVideos,
    isFiltering,
    videoCount,
    queryTotalCount,
    queryCurrentPage,
    queryPageSize,
    queryTotalPages,
    availableAuthors,
    trashCount,
    videoList,
    fetchList,
    fetchDetail,
    fetchDetailSnapshot,
    search,
    updateScore,
    updateProgress,
    bindTags,
    editVideo,
    moveToTrash,
    batchMoveToTrash,
    restoreFromTrash,
    deletePermanently,
    fetchTrashList,
    importVideo,
    refreshPreviewVideo,
    refreshLocalMetadata,
    generateLocalThumbnails,
    selectLocalThumbnailCover,
    getPlayUrls,
    thirdPartySearch,
    thirdPartyDetail,
    thirdPartyImport,
    filterByTags,
    filterMulti,
    sortVideos,
    saveCustomOrder,
    fetchCustomOrderItems,
    setSortState,
    clearFilter,
    clearCurrentVideo
  }
})
