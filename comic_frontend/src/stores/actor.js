import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { actorApi } from '../api/video'

export const useActorStore = defineStore('actor', () => {
  const actors = ref([])
  const allActors = ref([])
  const loading = ref(false)
  const error = ref(null)
  
  const subscribedCount = computed(() => actors.value.length)
  
  async function fetchList() {
    loading.value = true
    error.value = null
    try {
      const res = await actorApi.getList()
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
      const res = await actorApi.getAll()
      if (res.code === 200) {
        allActors.value = res.data || []
      }
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }
  
  async function subscribe(name) {
    try {
      const res = await actorApi.subscribe(name)
      if (res.code === 200) {
        await fetchList()
        return { success: true, data: res.data }
      }
      return { success: false, message: res.msg }
    } catch (e) {
      return { success: false, message: e.message }
    }
  }
  
  async function unsubscribe(actorSubscriptionId) {
    try {
      const res = await actorApi.unsubscribe(actorSubscriptionId)
      if (res.code === 200) {
        actors.value = actors.value.filter(a => a.id !== actorSubscriptionId)
        return true
      }
      return false
    } catch (e) {
      return false
    }
  }
  
  async function getVideos(actorName) {
    try {
      const res = await actorApi.getVideos(actorName)
      if (res.code === 200) {
        return res.data || []
      }
      return []
    } catch (e) {
      return []
    }
  }
  
  async function updateCheckTime(actorSubscriptionId) {
    try {
      const res = await actorApi.updateCheckTime(actorSubscriptionId)
      return res.code === 200
    } catch (e) {
      return false
    }
  }
  
  async function updateLastWork(actorSubscriptionId, workId, workTitle, newCount = 0) {
    try {
      const res = await actorApi.updateLastWork(actorSubscriptionId, workId, workTitle, newCount)
      if (res.code === 200) {
        const index = actors.value.findIndex(a => a.id === actorSubscriptionId)
        if (index >= 0) {
          actors.value[index] = res.data
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
    allActors,
    loading,
    error,
    subscribedCount,
    fetchList,
    fetchAll,
    subscribe,
    unsubscribe,
    getVideos,
    updateCheckTime,
    updateLastWork
  }
})
