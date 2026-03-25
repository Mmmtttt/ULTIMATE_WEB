import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { showSuccessToast, showFailToast } from 'vant'
import request from '@/api/request'
import { useTagStore } from './tag'
import { useCacheStore } from './cache'

export const useImportTaskStore = defineStore('importTask', () => {
  const tagStore = useTagStore()
  const cacheStore = useCacheStore()
  // State
  const tasks = ref([])
  const loading = ref(false)
  const currentTaskId = ref(null)
  const pollingInterval = ref(null)
  const lastFetchSuccess = ref(true)
  const consecutiveFailures = ref(0)

  // Getters
  const pendingTasks = computed(() => 
    tasks.value.filter(t => t.status === 'pending')
  )
  
  const processingTasks = computed(() => 
    tasks.value.filter(t => t.status === 'processing')
  )
  
  const completedTasks = computed(() => 
    tasks.value.filter(t => ['completed', 'failed', 'cancelled'].includes(t.status))
  )
  
  const hasActiveTasks = computed(() => 
    pendingTasks.value.length > 0 || processingTasks.value.length > 0
  )
  
  const activeTaskCount = computed(() => 
    pendingTasks.value.length + processingTasks.value.length
  )

  // Actions
  // 获取任务列表
  const fetchTasks = async () => {
    try {
      const response = await request.get('/v1/comic/import/tasks')
      if (response && response.code === 200) {
        tasks.value = response.data.tasks || []
        lastFetchSuccess.value = true
        consecutiveFailures.value = 0
        return tasks.value
      } else {
        // 后端返回错误，可能是服务重启
        consecutiveFailures.value++
        if (consecutiveFailures.value >= 3) {
          lastFetchSuccess.value = false
          // 如果连续失败3次，停止轮询
          stopPolling()
          showFailToast('后端服务异常，已停止轮询')
        }
      }
    } catch (error) {
      console.error('获取导入任务失败:', error)
      // 网络错误或后端不可用
      consecutiveFailures.value++
      if (consecutiveFailures.value >= 3) {
        lastFetchSuccess.value = false
        // 如果连续失败3次，停止轮询
        stopPolling()
        showFailToast('后端服务不可用，已停止轮询')
      }
    }
    return []
  }

  // 获取单个任务详情
  const fetchTaskDetail = async (taskId) => {
    try {
      const response = await request.get(`/v1/comic/import/task/${taskId}`)
      if (response && response.code === 200) {
        return response.data
      }
    } catch (error) {
      console.error('获取任务详情失败:', error)
    }
    return null
  }

  // 创建异步导入任务
  const createImportTask = async (params) => {
    try {
      const payload = { ...(params || {}) }
      if (!payload.content_type) {
        const platform = String(payload.platform || '').trim().toUpperCase()
        payload.content_type = ['JAVDB', 'JAVBUS'].includes(platform) ? 'video' : 'comic'
      }

      const response = await request.post('/v1/comic/import/async', payload)
      if (response && response.code === 200) {
        showSuccessToast('导入任务已创建')
        // 立即刷新任务列表
        await fetchTasks()
        // 开始轮询
        startPolling()
        return response.data
      } else {
        showFailToast(response?.msg || '创建任务失败')
        return null
      }
    } catch (error) {
      console.error('创建导入任务失败:', error)
      showFailToast('创建任务失败')
      return null
    }
  }

  // 取消任务
  const cancelTask = async (taskId) => {
    try {
      const response = await request.post(`/v1/comic/import/task/${taskId}/cancel`)
      if (response && response.code === 200) {
        showSuccessToast('任务已取消')
        await fetchTasks()
        return true
      } else {
        showFailToast(response?.msg || '取消失败')
        return false
      }
    } catch (error) {
      console.error('取消任务失败:', error)
      showFailToast('取消失败')
      return false
    }
  }

  // 清理已完成任务
  const clearCompletedTasks = async (keepCount = 20) => {
    try {
      const response = await request.post('/v1/comic/import/tasks/clear', { keep_count: keepCount })
      if (response && response.code === 200) {
        showSuccessToast(`已清理 ${response.data.deleted_count} 个任务`)
        await fetchTasks()
        return true
      }
    } catch (error) {
      console.error('清理任务失败:', error)
      showFailToast('清理失败')
    }
    return false
  }

  // 开始轮询任务状态
  const startPolling = () => {
    if (pollingInterval.value) return
    
    let hadActiveTasks = hasActiveTasks.value
    
    pollingInterval.value = setInterval(async () => {
      const prevActiveCount = activeTaskCount.value
      await fetchTasks()
      
      if (!hasActiveTasks.value && prevActiveCount > 0) {
        await refreshTagsAfterImport()
      }
      
      if (!hasActiveTasks.value) {
        stopPolling()
      }
    }, 2000)
  }

  const refreshTagsAfterImport = async () => {
    try {
      cacheStore.clearCache('tags')
      cacheStore.clearCache('video-tags')
      cacheStore.clearCache('list')
      await tagStore.fetchTags('comic', true)
      await tagStore.fetchTags('video', true)
      console.log('[ImportTask] 标签列表已刷新')
    } catch (error) {
      console.error('[ImportTask] 刷新标签列表失败:', error)
    }
  }

  // 停止轮询
  const stopPolling = () => {
    if (pollingInterval.value) {
      clearInterval(pollingInterval.value)
      pollingInterval.value = null
    }
  }

  // 获取状态文本
  const getStatusText = (status) => {
    const statusMap = {
      'pending': '等待中',
      'processing': '处理中',
      'completed': '已完成',
      'failed': '失败',
      'cancelled': '已取消'
    }
    return statusMap[status] || status
  }

  // 获取状态颜色
  const getStatusColor = (status) => {
    const colorMap = {
      'pending': '#ff976a',
      'processing': '#1989fa',
      'completed': '#07c160',
      'failed': '#ee0a24',
      'cancelled': '#969799'
    }
    return colorMap[status] || '#969799'
  }

  return {
    tasks,
    loading,
    currentTaskId,
    lastFetchSuccess,
    consecutiveFailures,
    pendingTasks,
    processingTasks,
    completedTasks,
    hasActiveTasks,
    activeTaskCount,
    fetchTasks,
    fetchTaskDetail,
    createImportTask,
    cancelTask,
    clearCompletedTasks,
    startPolling,
    stopPolling,
    getStatusText,
    getStatusColor
  }
})
