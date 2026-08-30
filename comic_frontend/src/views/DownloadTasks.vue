<template>
  <div class="download-tasks-page desktop-page-shell">
    <van-nav-bar
      title="下载任务"
      left-arrow
      @click-left="$router.back()"
    >
      <template #right>
        <van-icon
          name="replay"
          size="20"
          class="refresh-icon"
          :class="{ spinning: loading }"
          @click="refreshAll"
        />
      </template>
    </van-nav-bar>

    <div class="engine-bar" v-if="engines.length > 0">
      <van-tabs
        v-model:active="activeEngineIndex"
        animated
        swipeable
        @change="handleEngineChange"
      >
        <van-tab
          v-for="engine in engines"
          :key="engine.plugin_id"
          :title="engine.name"
        />
      </van-tabs>
    </div>

    <div class="tasks-container">
      <div v-if="!loading && engines.length === 0" class="empty-wrap">
        <van-empty description="未找到可用的下载引擎">
          <van-button type="primary" size="small" plain @click="goToConfig">
            前往第三方插件配置
          </van-button>
        </van-empty>
      </div>

      <template v-else>
        <section class="hero-card">
          <div class="hero-copy">
            <div class="hero-title">下载任务</div>
            <div class="hero-subtitle">
              {{ currentEngineName }}
              <template v-if="currentEngineStatus"> · {{ currentEngineStatus }}</template>
            </div>
          </div>
          <div class="hero-stats">
            <div class="hero-stat">
              <span class="hero-stat-value">{{ activeTasks.length }}</span>
              <span class="hero-stat-label">进行中</span>
            </div>
            <div class="hero-stat">
              <span class="hero-stat-value">{{ historyTasks.length }}</span>
              <span class="hero-stat-label">已结束</span>
            </div>
            <div class="hero-stat">
              <span class="hero-stat-value speed">{{ totalDownloadSpeedText }}</span>
              <span class="hero-stat-label">下载速度</span>
            </div>
          </div>
        </section>

        <div class="section active-section">
          <div class="section-title">
            <van-icon name="clock-o" />
            <span>进行中</span>
          </div>

          <div v-if="activeTasks.length === 0" class="empty-state">
            <van-empty description="当前没有进行中的下载任务" />
          </div>

          <div v-else class="task-list">
            <article
              v-for="task in activeTasks"
              :key="task.gid"
              class="task-card active"
            >
              <div class="task-header">
                <div class="task-heading">
                  <span class="task-title">{{ task.name || '未知任务' }}</span>
                  <span class="task-gid">{{ task.gid }}</span>
                </div>
                <van-tag :color="getStatusColor(task.status)">
                  {{ getStatusText(task.status) }}
                </van-tag>
              </div>

              <div class="progress-section">
                <div class="progress-header">
                  <span class="progress-text">{{ progressMetaText(task) }}</span>
                  <span class="progress-percent">{{ Math.round(task.progress * 100) }}%</span>
                </div>
                <van-progress
                  :percentage="Math.round(task.progress * 100)"
                  :stroke-width="8"
                  :color="getStatusColor(task.status)"
                />
                <div class="progress-speed">
                  <span v-if="task.download_speed > 0">↓ {{ formatSpeed(task.download_speed) }}</span>
                  <span v-if="task.upload_speed > 0">↑ {{ formatSpeed(task.upload_speed) }}</span>
                  <span>{{ formatBytes(task.completed_length) }} / {{ formatBytes(task.total_length) }}</span>
                </div>
              </div>

              <div class="task-actions">
                <van-button
                  size="small"
                  type="danger"
                  plain
                  @click="handleRemove(task)"
                >
                  删除任务
                </van-button>
              </div>
            </article>
          </div>
        </div>

        <div class="section history-section">
          <div class="section-title">
            <van-icon name="completed" />
            <span>已结束</span>
          </div>

          <div v-if="historyTasks.length === 0" class="empty-state">
            <van-empty description="暂无已结束的下载任务" />
          </div>

          <div v-else class="task-list">
            <article
              v-for="task in historyTasks"
              :key="task.gid"
              class="task-card"
              :class="task.status"
            >
              <div class="task-header">
                <div class="task-heading">
                  <span class="task-title">{{ task.name || '未知任务' }}</span>
                  <span class="task-gid">{{ task.gid }}</span>
                </div>
                <van-tag :color="getStatusColor(task.status)">
                  {{ getStatusText(task.status) }}
                </van-tag>
              </div>

              <div class="task-meta">
                <span>{{ formatBytes(task.total_length) }}</span>
                <span v-if="task.dir">{{ task.dir }}</span>
              </div>

              <div v-if="task.error_message" class="error-message">
                <van-icon name="warning-o" />
                <span>{{ task.error_message }}</span>
              </div>

              <div class="task-actions">
                <van-button
                  size="small"
                  type="default"
                  plain
                  @click="handleRemove(task)"
                >
                  删除记录
                </van-button>
              </div>
            </article>
          </div>
        </div>

        <div class="footer-tip">
          <van-icon name="info-o" />
          <span>任务由下载引擎（Aria2 等）在后台执行，此处每 3 秒自动刷新。</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showFailToast } from 'vant'
import { downloadApi } from '@/api/download'

const router = useRouter()

const engines = ref([])
const activeEngineIndex = ref(0)
const tasks = ref([])
const loading = ref(false)

const POLL_INTERVAL_MS = 3000
let pollTimer = null

const currentEngine = computed(() => engines.value[activeEngineIndex.value] || null)
const currentEngineName = computed(() => currentEngine.value?.name || '未选择引擎')
const currentEngineStatus = computed(() => {
  const status = currentEngine.value?.status || {}
  if (status.configured === false) {
    return '未配置'
  }
  return ''
})

const ACTIVE_STATUSES = new Set(['active', 'waiting', 'paused'])
const DONE_STATUSES = new Set(['complete', 'error', 'removed'])

const activeTasks = computed(() =>
  tasks.value.filter(task => ACTIVE_STATUSES.has(task.status))
)
const historyTasks = computed(() =>
  tasks.value.filter(task => DONE_STATUSES.has(task.status))
)

const totalDownloadSpeedText = computed(() => {
  const total = activeTasks.value.reduce((sum, task) => sum + Number(task.download_speed || 0), 0)
  return total > 0 ? formatSpeed(total) : '0 B/s'
})

function getStatusText(status) {
  const map = {
    active: '下载中',
    waiting: '等待中',
    paused: '已暂停',
    complete: '已完成',
    error: '下载出错',
    removed: '已删除'
  }
  return map[status] || status || '未知'
}

function getStatusColor(status) {
  const map = {
    active: '#2f74ff',
    waiting: '#969799',
    paused: '#ff976a',
    complete: '#07c160',
    error: '#ee0a24',
    removed: '#969799'
  }
  return map[status] || '#969799'
}

function progressMetaText(task) {
  if (task.status === 'active' && task.download_speed > 0) {
    return `正在下载 ${formatSpeed(task.download_speed)}`
  }
  if (task.status === 'waiting') {
    return '排队等待中'
  }
  if (task.status === 'paused') {
    return '已暂停'
  }
  return '获取元数据中...'
}

function formatBytes(bytes) {
  const value = Number(bytes || 0)
  if (!value || value <= 0) {
    return '0 B'
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let index = 0
  let size = value
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(size >= 100 ? 0 : 1)} ${units[index]}`
}

function formatSpeed(bytesPerSecond) {
  return `${formatBytes(bytesPerSecond)}/s`
}

async function refreshAll() {
  await Promise.all([loadEngines(), loadTasks()])
}

async function loadEngines() {
  try {
    const res = await downloadApi.listEngines()
    const list = res?.data?.engines || []
    engines.value = list
    if (list.length === 0) {
      tasks.value = []
      return
    }
    if (activeEngineIndex.value >= list.length) {
      activeEngineIndex.value = 0
    }
  } catch (error) {
    console.error('获取下载引擎失败:', error)
  }
}

async function loadTasks() {
  if (loading.value || !currentEngine.value) {
    return
  }
  loading.value = true
  try {
    const res = await downloadApi.listTasks({ engine: currentEngine.value.plugin_id })
    const list = res?.data?.tasks || []
    tasks.value = Array.isArray(list) ? list : []
  } catch (error) {
    console.error('获取下载任务失败:', error)
  } finally {
    loading.value = false
  }
}

function handleEngineChange() {
  tasks.value = []
  loadTasks()
}

async function handleRemove(task) {
  try {
    await showConfirmDialog({
      title: '删除任务',
      message: task.status === 'active'
        ? '删除后任务将停止下载，确定删除吗？'
        : '确定删除这条下载记录吗？'
    })
  } catch (_) {
    return
  }

  if (!currentEngine.value) {
    return
  }
  try {
    await downloadApi.removeTask(task.gid, currentEngine.value.plugin_id, true)
    loadTasks()
  } catch (error) {
    console.error('删除下载任务失败:', error)
    showFailToast(error?.message || '删除任务失败')
  }
}

function goToConfig() {
  router.push({ name: 'ThirdPartyConfig' })
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    loadTasks()
  }, POLL_INTERVAL_MS)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(async () => {
  await loadEngines()
  await loadTasks()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.download-tasks-page {
  min-height: 95vh;
  background: transparent;
  padding-bottom: 64px;
}

.refresh-icon {
  color: var(--text-secondary);
  cursor: pointer;
}

.refresh-icon.spinning {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.engine-bar {
  margin: 4px 12px 0;
  border-radius: 12px;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  overflow: hidden;
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
  grid-template-columns: repeat(3, minmax(72px, 1fr));
  gap: 10px;
  min-width: 250px;
}

.hero-stat {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 12px 8px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  text-align: center;
}

.hero-stat-value {
  font-size: 22px;
  font-weight: 700;
  color: #fff;
}

.hero-stat-value.speed {
  font-size: 16px;
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

.task-card.complete {
  border-color: rgba(7, 193, 96, 0.2);
}

.task-card.error {
  border-color: rgba(238, 10, 36, 0.18);
}

.task-card.removed {
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

.task-gid {
  font-size: 12px;
  color: var(--text-tertiary);
  font-family: monospace;
  word-break: break-all;
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

.progress-speed {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.task-actions {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
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
.empty-wrap {
  padding: 18px 0;
}

.footer-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin: 0 0 16px;
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
