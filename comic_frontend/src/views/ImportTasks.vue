<template>
  <div class="import-tasks-page desktop-page-shell">
    <van-nav-bar
      title="任务中心"
      left-arrow
      @click-left="$router.back()"
    />

    <div class="tasks-container">
      <section class="hero-card">
        <div class="hero-copy">
          <div class="hero-title">后台任务</div>
          <div class="hero-subtitle">导入、本地补全、缩略图生成都会在这里持续更新进度。</div>
        </div>
        <div class="hero-stats">
          <div class="hero-stat">
            <span class="hero-stat-value">{{ activeTaskCount }}</span>
            <span class="hero-stat-label">进行中</span>
          </div>
          <div class="hero-stat">
            <span class="hero-stat-value">{{ completedTasks.length }}</span>
            <span class="hero-stat-label">历史任务</span>
          </div>
        </div>
      </section>

      <div v-if="activeTasks.length > 0" class="section active-section">
        <div class="section-title">
          <van-icon name="clock-o" />
          <span>进行中</span>
        </div>

        <div class="task-list">
          <article
            v-for="task in activeTasks"
            :key="task.task_id"
            class="task-card active"
          >
            <div class="task-header">
              <div class="task-heading">
                <span class="task-title">{{ task.title }}</span>
                <span class="task-type">{{ getTaskTypeText(task) }}</span>
              </div>
              <van-tag :color="getStatusColor(task.status)">
                {{ getStatusText(task.status) }}
              </van-tag>
            </div>

            <div class="task-meta">
              <span>{{ getTaskMetaText(task) }}</span>
              <span>{{ formatTime(task.create_time) }}</span>
            </div>

            <div class="progress-section">
              <div class="progress-header">
                <span class="progress-text">{{ task.message || '等待处理...' }}</span>
                <span class="progress-percent">{{ task.progress }}%</span>
              </div>
              <van-progress
                :percentage="task.progress"
                :stroke-width="8"
                :color="getStatusColor(task.status)"
              />
              <div class="progress-count">{{ getProgressCountText(task) }}</div>
            </div>

            <div class="task-actions">
              <van-button
                size="small"
                type="danger"
                plain
                @click="handleCancel(task.task_id)"
              >
                取消任务
              </van-button>
            </div>
          </article>
        </div>
      </div>

      <div v-else class="section empty-active">
        <van-empty description="当前没有进行中的任务" />
      </div>

      <div class="section completed-section">
        <div class="section-header">
          <div class="section-title">
            <van-icon name="completed" />
            <span>任务历史</span>
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
          <van-empty description="暂无历史任务" />
        </div>

        <div v-else class="task-list">
          <article
            v-for="task in completedTasks"
            :key="task.task_id"
            class="task-card"
            :class="task.status"
          >
            <div class="task-header">
              <div class="task-heading">
                <span class="task-title">{{ task.title }}</span>
                <span class="task-type">{{ getTaskTypeText(task) }}</span>
              </div>
              <van-tag :color="getStatusColor(task.status)">
                {{ getStatusText(task.status) }}
              </van-tag>
            </div>

            <div class="task-meta">
              <span>{{ getTaskMetaText(task) }}</span>
              <span v-if="task.complete_time">完成于 {{ formatTime(task.complete_time) }}</span>
              <span v-else>{{ formatTime(task.create_time) }}</span>
            </div>

            <div class="result-info" :class="{ danger: task.status === 'failed' }">
              <van-icon :name="task.status === 'failed' ? 'warning-o' : 'success'" />
              <span>{{ getTaskResultText(task) }}</span>
            </div>

            <div v-if="task.error_msg" class="error-message">
              <van-icon name="warning-o" />
              <span>{{ task.error_msg }}</span>
            </div>
          </article>
        </div>
      </div>
    </div>

    <div class="footer-tip">
      <van-icon name="info-o" />
      <span>任务会在后台持续执行，离开当前页面也不会中断。</span>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { showConfirmDialog } from 'vant'
import { useImportTaskStore } from '@/stores/importTask'

const taskStore = useImportTaskStore()

const activeTasks = computed(() => taskStore.activeTasks)
const activeTaskCount = computed(() => taskStore.activeTaskCount)
const completedTasks = computed(() => taskStore.completedTasks)

const batchTaskTypes = new Set([
  'comic_local_metadata_refresh',
  'video_local_metadata_refresh',
  'video_local_thumbnail_generate'
])

function isBatchTask(task) {
  return batchTaskTypes.has(String(task?.import_type || '').trim())
}

function getStatusText(status) {
  return taskStore.getStatusText(status)
}

function getStatusColor(status) {
  return taskStore.getStatusColor(status)
}

function getTaskTypeText(task) {
  const importType = String(task?.import_type || '').trim()
  const contentType = String(task?.content_type || '').trim()
  const typeMap = {
    by_id: '单项导入',
    by_search: '搜索导入',
    by_list: '批量导入',
    by_platform_list: '平台清单导入',
    migrate_to_local: contentType === 'video' ? '迁移到本地视频库' : '迁移到本地漫画库',
    comic_local_metadata_refresh: '本地漫画补全',
    video_local_metadata_refresh: '本地视频补全',
    video_local_thumbnail_generate: '本地视频缩略图',
  }
  return typeMap[importType] || '后台任务'
}

function getTaskMetaText(task) {
  if (isBatchTask(task)) {
    const count = Number(task?.total_pages || 0)
    const unit = String(task?.content_type || '').trim() === 'video' ? '个视频' : '部漫画'
    return `处理范围 ${count} ${unit}`
  }

  const platform = String(task?.platform || '').trim() || '-'
  const targetMap = {
    home: '本地库',
    recommendation: '预览库',
    local: '本地',
  }
  return `${platform} · ${targetMap[String(task?.target || '').trim()] || '后台任务'}`
}

function getProgressCountText(task) {
  const total = Number(task?.total_pages || 0)
  const done = Number(task?.downloaded_pages || 0)
  if (total <= 0) {
    return '等待统计总量'
  }
  const unit = isBatchTask(task) ? '项' : '项'
  return `已完成 ${done} / ${total} ${unit}`
}

function getTaskResultText(task) {
  const result = task?.result || {}
  if (isBatchTask(task)) {
    const processed = Number(result.processed_count || task?.downloaded_pages || 0)
    const success = Number(result.success_count || 0)
    const failed = Number(result.failed_count || 0)
    const skipped = Number(result.skipped_count || 0)
    if (task?.status === 'cancelled') {
      return `已取消，已完成 ${processed} 项`
    }
    if (task?.status === 'failed') {
      return task?.error_msg || '任务执行失败'
    }
    return `已完成 ${processed} 项，成功 ${success}，失败 ${failed}，跳过 ${skipped}`
  }

  const importedCount = Number(result.imported_count || 0)
  const skippedCount = Number(result.skipped_count || 0)
  const failedCount = Number(result.failed_count || 0)
  if (importedCount > 0 || skippedCount > 0 || failedCount > 0) {
    return `成功 ${importedCount}，跳过 ${skippedCount}，失败 ${failedCount}`
  }
  if (task?.status === 'cancelled') {
    return '任务已取消'
  }
  if (task?.status === 'failed') {
    return task?.error_msg || '任务执行失败'
  }
  return task?.message || '任务已完成'
}

function formatTime(timeStr) {
  if (!timeStr) return '-'
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

async function handleCancel(taskId) {
  showConfirmDialog({
    title: '确认取消',
    message: '确定要取消这个后台任务吗？',
  }).then(async () => {
    await taskStore.cancelTask(taskId)
  }).catch(() => {})
}

async function handleClear() {
  showConfirmDialog({
    title: '清理任务',
    message: '确定要清理已完成的任务吗？将保留最近 10 个任务。',
  }).then(async () => {
    await taskStore.clearCompletedTasks(10)
  }).catch(() => {})
}

onMounted(async () => {
  await taskStore.fetchTasks()
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
  min-height: 95vh;
  background: transparent;
  padding-bottom: 64px;
}

.tasks-container {
  padding: 14px 12px 0;
}

.hero-card {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 18px;
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(14, 25, 45, 0.94), rgba(25, 50, 95, 0.88));
  border: 1px solid rgba(120, 161, 255, 0.18);
  box-shadow: 0 20px 40px rgba(9, 18, 33, 0.22);
}

.hero-title {
  font-size: 20px;
  font-weight: 700;
  color: #f3f7ff;
}

.hero-subtitle {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.5;
  color: rgba(235, 242, 255, 0.76);
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(74px, 1fr));
  gap: 10px;
  min-width: 176px;
}

.hero-stat {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 12px 10px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  text-align: center;
}

.hero-stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #fff;
}

.hero-stat-label {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(235, 242, 255, 0.72);
}

.section {
  margin-bottom: 18px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-strong);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card {
  padding: 16px;
  border-radius: 16px;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  box-shadow: 0 10px 22px rgba(12, 22, 37, 0.1);
}

.task-card.active {
  border-color: rgba(47, 116, 255, 0.24);
}

.task-card.completed {
  border-color: rgba(7, 193, 96, 0.2);
}

.task-card.failed {
  border-color: rgba(238, 10, 36, 0.18);
}

.task-card.cancelled {
  border-color: rgba(150, 151, 153, 0.2);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.task-heading {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.task-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-strong);
  word-break: break-word;
}

.task-type {
  font-size: 12px;
  color: var(--text-tertiary);
}

.task-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-secondary);
}

.progress-section {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border-soft);
}

.progress-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.progress-text {
  font-size: 13px;
  color: var(--text-secondary);
}

.progress-percent {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
  color: #2f74ff;
}

.progress-count {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.task-actions {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}

.result-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(7, 193, 96, 0.1);
  color: #07c160;
  font-size: 13px;
}

.result-info.danger {
  background: rgba(238, 10, 36, 0.1);
  color: #ee0a24;
}

.error-message {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(238, 10, 36, 0.1);
  color: #ee0a24;
  font-size: 13px;
}

.empty-state,
.empty-active {
  padding: 18px 0;
}

.footer-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin: 0 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  font-size: 12px;
  color: var(--text-tertiary);
}

@media (max-width: 767px) {
  .hero-card {
    flex-direction: column;
  }

  .hero-stats {
    width: 100%;
    min-width: 0;
  }
}
</style>
