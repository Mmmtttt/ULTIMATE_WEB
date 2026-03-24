import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authorApi } from '../api/author'

export const useAuthorStore = defineStore('author', () => {
  const actors = ref([])
  const allAuthors = ref([])
  const loading = ref(false)
  const error = ref(null)
  
  const subscribedCount = computed(() => actors.value.length)
  
  async function fetchList() {
    loading.value = true
    error.value = null
    try {
      const res = await authorApi.getList()
      if (res.code === 200) {
        actors.value = res.data || []
      }
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }
  
  async function fetchAll() {
    loading.value = true
    error.value = null
    try {
      const res = await authorApi.getAllAuthors()
      if (res.code === 200) {
        allAuthors.value = res.data || []
      }
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }
  
  async function subscribe(name) {
    try {
      const res = await authorApi.subscribe(name)
      if (res.code === 200) {
        await fetchList()
        return { success: true, data: res.data }
      }
      return { success: false, message: res.msg }
    } catch (e) {
      return { success: false, message: e.message }
    }
  }
  
  async function unsubscribe(authorSubscriptionId) {
    try {
      const res = await authorApi.unsubscribe(authorSubscriptionId)
      if (res.code === 200) {
        actors.value = actors.value.filter(a => a.id !== authorSubscriptionId)
        return true
      }
      return false
    } catch (e) {
      return false
    }
  }
  
  async function checkUpdates(authorId = null) {
    try {
      const res = await authorApi.checkUpdates(authorId)
      if (res.code === 200) {
        await fetchList()
        return res.data
      }
      return null
    } catch (e) {
      return null
    }
  }

  async function clearNewCount(authorId) {
    try {
      const res = await authorApi.clearNewCount(authorId)
      if (res.code === 200) {
        const index = actors.value.findIndex(a => a.id === authorId)
        if (index >= 0) {
          actors.value[index] = {
            ...actors.value[index],
            new_work_count: 0
          }
        }
        return true
      }
      return false
    } catch (e) {
      return false
    }
  }
  
  return {
    actors,
    allAuthors,
    loading,
    error,
    subscribedCount,
    fetchList,
    fetchAll,
    subscribe,
    unsubscribe,
    checkUpdates,
    clearNewCount
  }
})
