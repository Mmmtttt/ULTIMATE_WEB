import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { videoApi } from '../api/video'

export const useVideoStore = defineStore('video', () => {
  const videos = ref([])
  const currentVideo = ref(null)
  const trashList = ref([])
  const loading = ref(false)
  const error = ref(null)
  
  const videoCount = computed(() => videos.value.length)
  const trashCount = computed(() => trashList.value.length)
  
  async function fetchList(params = {}) {
    loading.value = true
    error.value = null
    try {
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
  
  async function thirdPartySearch(keyword) {
    loading.value = true
    try {
      const res = await videoApi.thirdPartySearch(keyword)
      if (res.code === 200) {
        return res.data || []
      }
      return []
    } catch (e) {
      return []
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
  
  async function thirdPartyImport(videoId) {
    try {
      const res = await videoApi.thirdPartyImport(videoId)
      return res
    } catch (e) {
      return { code: 500, message: e.message }
    }
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
    videoCount,
    trashCount,
    fetchList,
    fetchDetail,
    search,
    updateScore,
    updateProgress,
    moveToTrash,
    restoreFromTrash,
    deletePermanently,
    fetchTrashList,
    importVideo,
    thirdPartySearch,
    thirdPartyDetail,
    thirdPartyImport,
    clearCurrentVideo
  }
})
