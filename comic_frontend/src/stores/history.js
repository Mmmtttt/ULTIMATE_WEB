import { defineStore } from 'pinia'
import { ref } from 'vue'
import { historyApi } from '@/api/history'

export const useHistoryStore = defineStore('history', () => {
  const comicItems = ref([])
  const videoItems = ref([])
  const loading = ref(false)

  async function fetchHistory(contentType = 'comic') {
    loading.value = true
    try {
      const res = await historyApi.list(contentType)
      if (res.code === 200) {
        const items = res.data?.items || []
        if (contentType === 'video') {
          videoItems.value = items
        } else {
          comicItems.value = items
        }
        return items
      }
      return []
    } catch (error) {
      console.error('获取阅读记录失败:', error)
      return []
    } finally {
      loading.value = false
    }
  }

  async function recordVisit(payload) {
    try {
      const res = await historyApi.recordVisit(payload)
      return res.code === 200
    } catch (error) {
      console.warn('写入阅读记录失败:', error)
      return false
    }
  }

  return {
    comicItems,
    videoItems,
    loading,
    fetchHistory,
    recordVisit
  }
})
