<template>
  <div class="import-tasks-page">
    <van-nav-bar
      title="导入任务"
      left-arrow
      @click-left="$router.back()"
    />

    <div class="tasks-container">
      <!-- 活跃任务区域 -->
      <div v-if="hasActiveTasks" class="section active-section">
        <div class="section-title">
          <van-icon name="clock-o" />
          <span>进行中 ({{ activeTaskCount }})</span>
        </div>
        
        <div class="task-list">
          <div
            v-for="task in activeTasks"
            :key="task.task_id"
            class="task-card active"
          >
            <div class="task-header">
              <span class="task-title">{{ task.title }}</span>
              <van-tag :color="getStatusColor(task.status)">
                {{ getStatusText(task.status) }}
              </van-tag>
            </div>
            
            <div class="task-info">
              <div class="info-row">
                <span class="label">平台:</span>
                <span class="value">{{ task.platform }}</span>
              </div>
              <div class="info-row">
                <span class="label">目标:</span>
                <span class="value">{{ task.target === 'home' ? '主页' : '推荐页' }}</span>
              </div>
              <div class="info-row">
                <span class="label">创建时间:</span>
                <span class="value">{{ formatTime(task.create_time) }}</span>
              </div>
            </div>
            
            <div v-if="task.status === 'processing'" class="progress-section">
              <div class="progress-header">
                <span class="progress-text">{{ task.message }}</span>
                <span class="progress-percent">{{ task.progress }}%</span>
              </div>
              <van-progress
                :percentage="task.progress"
                :stroke-width="8"
                :color="getStatusColor('processing')"
              />
              <div v-if="task.total_pages > 0" class="page-info">
                {{ task.downloaded_pages }} / {{ task.total_pages }} 页
              </div>
            </div>
            
            <div v-if="task.status === 'pending'" class="task-actions">
              <van-button
                size="small"
                type="danger"
                plain
                @click="handleCancel(task.task_id)"
              >
                取消
              </van-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 已完成任务区域 -->
      <div class="section completed-section">
        <div class="section-header">
          <div class="section-title">
            <van-icon name="completed" />
            <span>已完成</span>
          </div>
          <van-button
            v-if="completedTasks.length > 0"
            size="small"
            type="default"
            plain
            @click="handleClear"
          >
            清理旧任务
          </van-button>
        </div>
        
        <div v-if="completedTasks.length === 0" class="empty-state">
          <van-empty description="暂无已完成任务" />
        </div>
        
        <div v-else class="task-list">
          <div
            v-for="task in completedTasks"
            :key="task.task_id"
            class="task-card"
            :class="task.status"
          >
            <div class="task-header">
              <span class="task-title">{{ task.title }}</span>
              <van-tag :color="getStatusColor(task.status)">
                {{ getStatusText(task.status) }}
              </van-tag>
            </div>
            
            <div class="task-info">
              <div class="info-row">
                <span class="label">平台:</span>
                <span class="value">{{ task.platform }}</span>
              </div>
              <div class="info-row">
                <span class="label">目标:</span>
                <span class="value">{{ task.target === 'home' ? '主页' : '推荐页' }}</span>
              </div>
              <div class="info-row">
                <span class="label">创建时间:</span>
                <span class="value">{{ formatTime(task.create_time) }}</span>
              </div>
              <div v-if="task.complete_time" class="info-row">
                <span class="label">完成时间:</span>
                <span class="value">{{ formatTime(task.complete_time) }}</span>
              </div>
            </div>
            
            <div v-if="task.error_msg" class="error-message">
              <van-icon name="warning-o" />
              <span>{{ task.error_msg }}</span>
            </div>
            
            <div v-if="task.result?.imported_count" class="result-info">
              <van-icon name="success" color="#07c160" />
              <span>成功导入 {{ task.result.imported_count }} 部漫画</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部提示 -->
    <div class="footer-tip">
      <van-icon name="info-o" />
      <span>导入任务在后台执行，可关闭页面</span>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { showConfirmDialog } from 'vant'
import { useImportTaskStore } from '@/stores/importTask'

const taskStore = useImportTaskStore()

// Computed
const tasks = computed(() => taskStore.tasks)
const hasActiveTasks = computed(() => taskStore.hasActiveTasks)
const activeTaskCount = computed(() => taskStore.activeTaskCount)
const completedTasks = computed(() => taskStore.completedTasks)

const activeTasks = computed(() => {
  return tasks.value.filter(t => ['pending', 'processing'].includes(t.status))
})

// Methods
const getStatusText = (status) => taskStore.getStatusText(status)
const getStatusColor = (status) => taskStore.getStatusColor(status)

const formatTime = (timeStr) => {
  if (!timeStr) return '-'
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const handleCancel = async (taskId) => {
  showConfirmDialog({
    title: '确认取消',
    message: '确定要取消这个导入任务吗？',
  }).then(async () => {
    await taskStore.cancelTask(taskId)
  }).catch(() => {
    // 取消
  })
}

const handleClear = async () => {
  showConfirmDialog({
    title: '清理任务',
    message: '确定要清理已完成的任务吗？将保留最近10个任务。',
  }).then(async () => {
    await taskStore.clearCompletedTasks(10)
  }).catch(() => {
    // 取消
  })
}

// Lifecycle
onMounted(async () => {
  await taskStore.fetchTasks()
  // 如果有进行中的任务，开始轮询
  if (taskStore.hasActiveTasks) {
    taskStore.startPolling()
  }
})

onUnmounted(() => {
  taskStore.stopPolling()
})
</script>

<style scoped>
.import-tasks-page {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 60px;
}

.tasks-container {
  padding: 12px;
}

.section {
  margin-bottom: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 500;
  color: #323233;
  margin-bottom: 12px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.active-section .section-title {
  color: #1989fa;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.task-card.active {
  border-left: 3px solid #1989fa;
}

.task-card.completed {
  border-left: 3px solid #07c160;
}

.task-card.failed {
  border-left: 3px solid #ee0a24;
}

.task-card.cancelled {
  border-left: 3px solid #969799;
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.task-title {
  font-size: 15px;
  font-weight: 500;
  color: #323233;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-right: 12px;
}

.task-info {
  margin-bottom: 12px;
}

.info-row {
  display: flex;
  margin-bottom: 4px;
  font-size: 13px;
}

.info-row .label {
  color: #969799;
  width: 70px;
}

.info-row .value {
  color: #323233;
}

.progress-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f5f5f5;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.progress-text {
  font-size: 13px;
  color: #646566;
}

.progress-percent {
  font-size: 13px;
  color: #1989fa;
  font-weight: 500;
}

.page-info {
  margin-top: 8px;
  font-size: 12px;
  color: #969799;
  text-align: center;
}

.task-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.error-message {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 10px;
  background: #fff5f5;
  border-radius: 4px;
  font-size: 13px;
  color: #ee0a24;
}

.result-info {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 10px;
  background: #f0f9ff;
  border-radius: 4px;
  font-size: 13px;
  color: #07c160;
}

.empty-state {
  padding: 40px 0;
}

.footer-tip {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  background: #fff;
  border-top: 1px solid #ebedf0;
  font-size: 12px;
  color: #969799;
}
</style>
