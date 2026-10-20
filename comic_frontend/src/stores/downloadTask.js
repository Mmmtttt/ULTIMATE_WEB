import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'

import { downloadApi } from '@/api/download'

const POLL_INTERVAL_MS = 3000
const ACTIVE_STATUSES = new Set(['active', 'waiting', 'paused'])
const DONE_STATUSES = new Set(['complete', 'error', 'removed'])

// 功能标签：只用于向用户解释「为什么这里没有这个按钮」，属于展示层语义。
const FEATURE_LABELS = {
  task_list: '任务列表',
  task_status: '任务详情',
  pause: '暂停',
  resume: '继续',
  remove: '删除任务',
  migrate: '任务迁移',
  auto_import: '自动导入',
  auto_organize: '自动归集'
}
const TASK_CONTROL_FEATURES = ['pause', 'resume', 'remove']

export const useDownloadTaskStore = defineStore('downloadTask', () => {
  const engines = ref([])
  const tasks = ref([])
  const loading = ref(false)
  const showAddPopup = ref(false)
  const manualLinks = ref('')
  const manualSubfolder = ref('')
  const addingLinks = ref(false)
  const taskActionGid = ref('')
  const selectedEngineIndex = ref(0)
  const showEnginePicker = ref(false)
  const organizingPrompting = ref(false)

  let pollTimer = null

  const engineSummary = computed(() => {
    const names = engines.value
      .filter((engine) => engine?.status?.configured !== false)
      .map((engine) => engine.name)
    return names.length > 0 ? names.join('、') : ''
  })

  // 引擎 plugin_id -> features。features 由后端按插件 manifest 计算，
  // 描述引擎「能做什么」（静态），与 status「现在能不能用」（运行时）是两件事。
  const engineFeatures = computed(() => {
    const map = {}
    engines.value.forEach((engine) => {
      if (engine?.plugin_id && engine.features) {
        map[engine.plugin_id] = engine.features
      }
    })
    return map
  })

  function engineSupports(engine, feature) {
    // 后端未返回 features 时不做裁剪，保持旧行为
    if (!engine?.features) return true
    return engine.features[feature] === true
  }

  function featuresOfTask(task) {
    return task?.engine ? engineFeatures.value[task.engine] || null : null
  }

  function taskSupports(task, feature) {
    const features = featuresOfTask(task)
    if (!features) return true
    return features[feature] === true
  }

  function taskCapabilityNote(task) {
    const features = featuresOfTask(task)
    if (!features) return ''
    const missing = TASK_CONTROL_FEATURES.filter((name) => features[name] !== true)
    if (missing.length === 0) return ''
    const names = missing.map((name) => FEATURE_LABELS[name] || name)
    return `${task.engine_name || '该引擎'} 未提供能力：${names.join('、')}`
  }

  // 只有声明了 download.magnet.add 的引擎才能投递
  const submittableEngines = computed(() =>
    engines.value.filter((engine) => engineSupports(engine, 'submit_magnet'))
  )

  // 只有声明了 download.task.list 的引擎才能拉任务列表
  const taskListEngines = computed(() =>
    engines.value.filter((engine) => engineSupports(engine, 'task_list'))
  )

  const selectedEngine = computed(
    () => submittableEngines.value[selectedEngineIndex.value] || submittableEngines.value[0] || null
  )

  const enginePickerActions = computed(() =>
    submittableEngines.value.map((engine) => ({
      name: engine.name,
      plugin_id: engine.plugin_id
    }))
  )

  const activeTasks = computed(() => tasks.value.filter((task) => ACTIVE_STATUSES.has(task.status)))
  const historyTasks = computed(() => tasks.value.filter((task) => DONE_STATUSES.has(task.status)))

  const totalDownloadSpeedText = computed(() => {
    const total = activeTasks.value.reduce((sum, task) => sum + Number(task.download_speed || 0), 0)
    return total > 0 ? formatSpeed(total) : '0 B/s'
  })

  const canAddLinks = computed(
    () => manualLinks.value.trim().length > 0 && submittableEngines.value.length > 0
  )

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
      if (task.download_speed > 0) return `正在下载 ${formatSpeed(task.download_speed)}`
      return '正在下载中...'
    }
    if (task.status === 'waiting') return '排队等待中'
    if (task.status === 'paused') return '已暂停'
    return '获取元数据中...'
  }

  function formatBytes(bytes) {
    const value = Number(bytes || 0)
    if (!value || value <= 0) return '0 B'
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

  async function loadEngines() {
    try {
      const res = await downloadApi.listEngines()
      engines.value = res?.data?.engines || []
      if (selectedEngineIndex.value >= submittableEngines.value.length) {
        selectedEngineIndex.value = 0
      }
      if (taskListEngines.value.length === 0) {
        tasks.value = []
      }
    } catch (error) {
      console.error('获取下载引擎失败:', error)
    }
  }

  async function loadTasks(force = false) {
    const engineList = taskListEngines.value
    if ((loading.value && !force) || engineList.length === 0) return
    loading.value = true
    try {
      const results = await Promise.all(
        engineList.map((engine) =>
          downloadApi
            .listTasks({ engine: engine.plugin_id })
            .then((res) => {
              const list = res?.data?.tasks || []
              const items = Array.isArray(list) ? list : []
              return items.map((task) => ({
                ...task,
                engine: engine.plugin_id,
                engine_name: engine.name
              }))
            })
            .catch((error) => {
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

  async function refreshAll() {
    await loadEngines()
    await loadTasks(true)
  }

  async function handleRemove(task) {
    try {
      await showConfirmDialog({
        title: '删除任务',
        message:
          task.status === 'active'
            ? '删除后任务将停止下载，确定删除吗？'
            : '确定删除这条下载记录吗？'
      })
    } catch (_) {
      return
    }
    if (!task.engine) return
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

  function handlePause(task) {
    return runTaskAction(task, 'pause')
  }

  function handleResume(task) {
    return runTaskAction(task, 'resume')
  }

  async function runTaskAction(task, action) {
    if (!task.engine || taskActionGid.value) return
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

  function openAddPopup() {
    if (engines.value.length === 0) {
      showFailToast('未配置下载引擎，请先到第三方插件配置启用下载引擎')
      return
    }
    if (submittableEngines.value.length === 0) {
      showFailToast('当前下载引擎均未声明投递能力（download.magnet.add），无法创建任务')
      return
    }
    showAddPopup.value = true
  }

  function openEnginePicker() {
    if (submittableEngines.value.length > 1) {
      showEnginePicker.value = true
    }
  }

  function onEngineSelect(action) {
    const index = submittableEngines.value.findIndex((engine) => engine.plugin_id === action.plugin_id)
    if (index >= 0) selectedEngineIndex.value = index
  }

  function parseManualLinks() {
    return manualLinks.value
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
  }

  async function submitManualLinks() {
    const engine = selectedEngine.value
    if (!engine) return
    const uris = parseManualLinks()
    if (uris.length === 0) {
      showFailToast('请输入下载链接')
      return
    }
    addingLinks.value = true
    let created = 0
    let failed = 0
    try {
      // 逐条投递：aria2.addUri 的多 URI 会被视为同一任务的备用源
      const subfolder = manualSubfolder.value.trim()
      for (const uri of uris) {
        try {
          const res = await downloadApi.addMagnet({
            magnet: uri,
            engine: engine.plugin_id,
            dir_subfolder: subfolder || undefined
          })
          if (res?.data?.added) created += 1
          else failed += 1
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
    if (organizingPrompting.value) return
    let pending
    try {
      const res = await downloadApi.listOrganizePending()
      pending = res?.data?.pending || []
    } catch (error) {
      console.error('获取待确认归集列表失败:', error)
      return
    }
    const item = pending[0]
    if (!item) return
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

  async function init() {
    await loadEngines()
    await loadTasks()
    checkOrganizePending()
    startPolling()
  }

  return {
    engines,
    tasks,
    loading,
    showAddPopup,
    manualLinks,
    manualSubfolder,
    addingLinks,
    taskActionGid,
    selectedEngineIndex,
    showEnginePicker,
    engineSummary,
    submittableEngines,
    taskListEngines,
    selectedEngine,
    enginePickerActions,
    activeTasks,
    historyTasks,
    totalDownloadSpeedText,
    canAddLinks,
    getStatusText,
    getStatusColor,
    progressMetaText,
    formatBytes,
    formatSpeed,
    taskSupports,
    taskCapabilityNote,
    loadEngines,
    loadTasks,
    refreshAll,
    handleRemove,
    handlePause,
    handleResume,
    openAddPopup,
    openEnginePicker,
    onEngineSelect,
    submitManualLinks,
    startPolling,
    stopPolling,
    checkOrganizePending,
    init
  }
})
