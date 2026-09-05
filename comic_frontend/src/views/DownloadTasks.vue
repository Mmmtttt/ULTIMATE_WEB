<template>
  <div class="download-tasks-page desktop-page-shell">
    <van-nav-bar
      title="下载任务"
      left-arrow
      @click-left="$router.back()"
    >
      <template #right>
        <span class="nav-actions">
          <van-icon
            name="plus"
            size="20"
            class="nav-action-icon"
            @click="openAddPopup"
          />
          <van-icon
            name="replay"
            size="20"
            class="refresh-icon"
            :class="{ spinning: loading }"
            @click="refreshAll"
          />
        </span>
      </template>
    </van-nav-bar>

    <van-popup
      v-model:show="showAddPopup"
      round
      position="bottom"
      class="add-popup"
    >
      <div class="add-popup-content">
        <div class="add-popup-header">
          <span class="add-popup-title">手动添加下载链接</span>
          <van-icon name="cross" class="add-popup-close" @click="showAddPopup = false" />
        </div>
        <div class="add-popup-hint">
          支持磁力链接、HTTP/FTP 直链、BT 种子文件链接，每行一个。
        </div>
        <van-field
          :model-value="selectedEngine ? selectedEngine.name : '请选择下载引擎'"
          readonly
          is-link
          label="下载平台"
          placeholder="请选择下载引擎"
          @click="openEnginePicker"
        />
        <van-field
          v-model="manualSubfolder"
          label="保存到子文件夹"
          placeholder="可选，如 ABC-123 或剧名，留空用下载目录根路径"
          clearable
        />
        <van-field
          v-model="manualLinks"
          type="textarea"
          rows="6"
          autosize
          maxlength="8000"
          placeholder="每行一个链接&#10;magnet:?xt=urn:btih:...&#10;https://example.com/file.torrent"
        />
        <div class="add-popup-actions">
          <van-button
            block
            type="primary"
            :loading="addingLinks"
            :disabled="!canAddLinks"
            @click="submitManualLinks"
          >
            创建任务
          </van-button>
        </div>
      </div>
      <van-action-sheet
        v-model:show="showEnginePicker"
        :actions="enginePickerActions"
        cancel-text="取消"
        @select="onEngineSelect"
      />
    </van-popup>

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
              共 {{ engines.length }} 个下载引擎
              <template v-if="engineSummary"> · {{ engineSummary }}</template>
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
                  <div class="task-subtitle">
                    <span class="engine-tag">{{ task.engine_name || '下载引擎' }}</span>
                    <span class="task-status-text">{{ progressMetaText(task) }}</span>
                  </div>
                </div>
                <div class="task-header-right">
                  <van-tag :color="getStatusColor(task.status)">
                    {{ getStatusText(task.status) }}
                  </van-tag>
                  <div class="task-actions">
                    <button
                      v-if="task.status === 'paused'"
                      class="icon-btn"
                      :disabled="taskActionGid === task.gid"
                      title="继续下载"
                      @click="handleResume(task)"
                    >
                      <van-icon name="play-circle-o" size="20" />
                    </button>
                    <button
                      v-else
                      class="icon-btn"
                      :disabled="taskActionGid === task.gid"
                      title="暂停下载"
                      @click="handlePause(task)"
                    >
                      <van-icon name="pause-circle-o" size="20" />
                    </button>
                    <button
                      class="icon-btn danger"
                      :disabled="taskActionGid === task.gid"
                      title="删除任务"
                      @click="handleRemove(task)"
                    >
                      <van-icon name="delete-o" size="20" />
                    </button>
                  </div>
                </div>
              </div>

              <div class="progress-section">
                <van-progress
                  :percentage="Math.round(task.progress * 100)"
                  :stroke-width="8"
                  :color="getStatusColor(task.status)"
                />
                <div class="progress-speed">
                  <span v-if="task.upload_speed > 0">↑ {{ formatSpeed(task.upload_speed) }}</span>
                  <span>{{ formatBytes(task.completed_length) }} / {{ formatBytes(task.total_length) }}</span>
                </div>
              </div>
            </article>
          </div>
        </div>

        <div class="section history-section">
          <div class="section-title collapsible" @click="showHistory = !showHistory">
            <van-icon name="completed" />
            <span>已结束</span>
            <span v-if="historyTasks.length > 0" class="section-count">
              {{ historyTasks.length }}
            </span>
            <van-icon
              :name="showHistory ? 'arrow-up' : 'arrow-down'"
              class="section-toggle"
            />
          </div>

          <template v-if="showHistory">
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
                  <div class="task-subtitle">
                    <span class="engine-tag">{{ task.engine_name || '下载引擎' }}</span>
                    <span class="task-gid">{{ task.gid }}</span>
                  </div>
                </div>
                <div class="task-header-right">
                  <van-tag :color="getStatusColor(task.status)">
                    {{ getStatusText(task.status) }}
                  </van-tag>
                  <div class="task-actions">
                    <button
                      class="icon-btn danger"
                      :disabled="taskActionGid === task.gid"
                      title="删除记录"
                      @click="handleRemove(task)"
                    >
                      <van-icon name="delete-o" size="20" />
                    </button>
                  </div>
                </div>
              </div>

              <div class="task-meta">
                <span>{{ formatBytes(task.total_length) }}</span>
                <span v-if="task.dir">{{ task.dir }}</span>
              </div>

              <div v-if="task.error_message" class="error-message">
                <van-icon name="warning-o" />
                <span>{{ task.error_message }}</span>
              </div>
            </article>
            </div>
          </template>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'
import { downloadApi } from '@/api/download'

const router = useRouter()

const engines = ref([])
const tasks = ref([])
const loading = ref(false)
const showAddPopup = ref(false)
const manualLinks = ref('')
const manualSubfolder = ref('')
const addingLinks = ref(false)
const taskActionGid = ref('')
const showHistory = ref(false)
const selectedEngineIndex = ref(0)
const showEnginePicker = ref(false)
const organizingPrompting = ref(false)

const POLL_INTERVAL_MS = 3000
let pollTimer = null

const engineSummary = computed(() => {
  const names = engines.value
    .filter(engine => engine?.status?.configured !== false)
    .map(engine => engine.name)
  return names.length > 0 ? names.join('、') : ''
})

const selectedEngine = computed(() =>
  engines.value[selectedEngineIndex.value] || engines.value[0] || null
)

const enginePickerActions = computed(() =>
  engines.value.map(engine => ({
    name: engine.name,
    plugin_id: engine.plugin_id
  }))
)

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
  if (task.status === 'active') {
    if (task.download_speed > 0) {
      return `正在下载 ${formatSpeed(task.download_speed)}`
    }
    return '正在下载中...'
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
  await loadEngines()
  await loadTasks(true)
}

async function loadEngines() {
  try {
    const res = await downloadApi.listEngines()
    const list = res?.data?.engines || []
    engines.value = list
    if (selectedEngineIndex.value >= list.length) {
      selectedEngineIndex.value = 0
    }
    if (list.length === 0) {
      tasks.value = []
    }
  } catch (error) {
    console.error('获取下载引擎失败:', error)
  }
}

async function loadTasks(force = false) {
  const engineList = engines.value
  if ((loading.value && !force) || engineList.length === 0) {
    return
  }
  loading.value = true
  try {
    // 并行拉取所有引擎的任务并合并，任务附带所属引擎信息
    const results = await Promise.all(
      engineList.map(engine =>
        downloadApi.listTasks({ engine: engine.plugin_id })
          .then(res => {
            const list = res?.data?.tasks || []
            const items = Array.isArray(list) ? list : []
            return items.map(task => ({
              ...task,
              engine: engine.plugin_id,
              engine_name: engine.name
            }))
          })
          .catch(error => {
            console.error(`获取 ${engine.name} 任务失败:`, error)
            return []
          })
      )
    )
    tasks.value = results.flat()
  } finally {
    loading.value = false
  }
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

  if (!task.engine) {
    return
  }
  taskActionGid.value = task.gid
  try {
    await downloadApi.removeTask(task.gid, task.engine, true)
    loadTasks()
  } catch (error) {
    console.error('删除下载任务失败:', error)
    showFailToast(error?.message || '删除任务失败')
  } finally {
    taskActionGid.value = ''
  }
}

async function handlePause(task) {
  await runTaskAction(task, 'pause')
}

async function handleResume(task) {
  await runTaskAction(task, 'resume')
}

async function runTaskAction(task, action) {
  if (!task.engine || taskActionGid.value) {
    return
  }
  taskActionGid.value = task.gid
  try {
    if (action === 'pause') {
      await downloadApi.pauseTask(task.gid, task.engine)
    } else {
      await downloadApi.resumeTask(task.gid, task.engine)
    }
    loadTasks()
  } catch (error) {
    console.error(`任务${action}失败:`, error)
    showFailToast(error?.message || (action === 'pause' ? '暂停任务失败' : '继续任务失败'))
  } finally {
    taskActionGid.value = ''
  }
}

function goToConfig() {
  router.push({ name: 'ThirdPartyConfig' })
}

const canAddLinks = computed(() => {
  return manualLinks.value.trim().length > 0 && engines.value.length > 0
})

function openAddPopup() {
  if (engines.value.length === 0) {
    showFailToast('未配置下载引擎，请先到第三方插件配置启用下载引擎')
    return
  }
  showAddPopup.value = true
}

function openEnginePicker() {
  if (engines.value.length > 1) {
    showEnginePicker.value = true
  }
}

function onEngineSelect(action) {
  const index = engines.value.findIndex(
    engine => engine.plugin_id === action.plugin_id
  )
  if (index >= 0) {
    selectedEngineIndex.value = index
  }
}

function parseManualLinks() {
  return manualLinks.value
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(line => line.length > 0)
}

async function submitManualLinks() {
  const engine = selectedEngine.value
  if (!engine) {
    return
  }
  const uris = parseManualLinks()
  if (uris.length === 0) {
    showFailToast('请输入下载链接')
    return
  }
  addingLinks.value = true
  let created = 0
  let failed = 0
  try {
    // 逐条投递：aria2.addUri 的多 URI 会被视为同一任务的备用源，
    // 因此每条链接单独创建任务，确保互不干扰。
    const subfolder = manualSubfolder.value.trim()
    for (const uri of uris) {
      try {
        const res = await downloadApi.addMagnet({
          magnet: uri,
          engine: engine.plugin_id,
          dir_subfolder: subfolder || undefined
        })
        if (res?.data?.added) {
          created += 1
        } else {
          failed += 1
        }
      } catch (error) {
        console.error(`创建任务失败: ${uri}`, error)
        failed += 1
      }
    }
  } finally {
    addingLinks.value = false
  }

  if (created > 0) {
    showSuccessToast(`已创建 ${created} 个任务${failed > 0 ? `，${failed} 个失败` : ''}`)
    showAddPopup.value = false
    manualLinks.value = ''
    manualSubfolder.value = ''
    loadTasks()
  } else {
    showFailToast('创建任务失败，请检查链接格式')
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    loadTasks()
    checkOrganizePending()
  }, POLL_INTERVAL_MS)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function checkOrganizePending() {
  if (organizingPrompting.value) {
    return
  }
  let pending
  try {
    const res = await downloadApi.listOrganizePending()
    pending = res?.data?.pending || []
  } catch (error) {
    console.error('获取待确认归集列表失败:', error)
    return
  }
  const item = pending[0]
  if (!item) {
    return
  }
  organizingPrompting.value = true
  try {
    await showConfirmDialog({
      title: '检测到相同内容',
      message:
        `下载目录中已存在内容 ${item.code}。\n` +
        `是否创建文件夹 ${item.target_dir}，并将 ${item.files?.length || 0} 个新文件移入？`,
      confirmButtonText: '创建并移入',
      cancelButtonText: '忽略'
    })
    try {
      const res = await downloadApi.confirmOrganize(item.id)
      showSuccessToast(res?.msg || '已创建文件夹并移入文件')
      loadTasks()
    } catch (error) {
      showFailToast(error?.message || '归集失败')
    }
  } catch (_) {
    try {
      await downloadApi.dismissOrganize(item.id)
    } catch (error) {
      console.error('忽略归集失败:', error)
    }
  } finally {
    organizingPrompting.value = false
  }
}

onMounted(async () => {
  await loadEngines()
  await loadTasks()
  checkOrganizePending()
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

.nav-actions {
  display: flex;
  align-items: center;
  gap: 18px;
}

.nav-action-icon {
  color: var(--text-secondary);
  cursor: pointer;
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

.add-popup-content {
  padding: 16px 16px 20px;
}

.add-popup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.add-popup-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-strong);
}

.add-popup-close {
  color: var(--text-3);
  cursor: pointer;
}

.add-popup-hint {
  margin-bottom: 10px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-tertiary);
}

.add-popup-actions {
  margin-top: 14px;
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

.section-title.collapsible {
  cursor: pointer;
  user-select: none;
}

.section-count {
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--surface-3, rgba(127, 143, 166, 0.18));
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
}

.section-toggle {
  margin-left: auto;
  color: var(--text-3);
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
  align-items: center;
  gap: 12px;
}

.task-header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.task-heading {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.task-subtitle {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.engine-tag {
  flex-shrink: 0;
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(47, 116, 255, 0.12);
  color: #2f74ff;
  font-size: 11px;
  font-weight: 500;
}

.task-status-text {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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

.progress-speed {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.task-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border-radius: 50%;
  border: 1px solid var(--border-soft);
  background: var(--surface-3, var(--surface-2));
  color: var(--text-secondary);
  cursor: pointer;
}

.icon-btn.danger {
  color: #ee0a24;
}

.icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
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
