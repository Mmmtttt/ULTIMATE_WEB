import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { showSuccessToast, showFailToast } from 'vant'
import request from '@/utils/request'

export const useImportTaskStore = defineStore('importTask', () => {
  // State
  const tasks = ref([])
  const loading = ref(false)
  const currentTaskId = ref(null)
  const pollingInterval = ref(null)

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
      const response = await request.get('/api/v1/comic/import/tasks')
      if (response && response.code === 200) {
        tasks.value = response.data.tasks || []
        return tasks.value
      }
    } catch (error) {
      console.error('获取导入任务失败:', error)
    }
    return []
  }

  // 获取单个任务详情
  const fetchTaskDetail = async (taskId) => {
    try {
      const response = await request.get(`/api/v1/comic/import/task/${taskId}`)
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
      const response = await request.post('/api/v1/comic/import/async', params)
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
      const response = await request.post(`/api/v1/comic/import/task/${taskId}/cancel`)
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
      const response = await request.post('/api/v1/comic/import/tasks/clear', { keep_count: keepCount })
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
    
    pollingInterval.value = setInterval(async () => {
      await fetchTasks()
      
      // 如果没有进行中的任务，停止轮询
      if (!hasActiveTasks.value) {
        stopPolling()
      }
    }, 2000) // 每2秒轮询一次
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
