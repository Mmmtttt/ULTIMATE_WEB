import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getItem, setItem } from '@/utils/storage'
import { checkForAppUpdate, RELEASES_PAGE_URL } from '@/services/appUpdate'

const UPDATE_STATE_STORAGE_KEY = 'app_update_last_state'

function defaultState() {
  return {
    checked: false,
    hasUpdate: false,
    source: '',
    currentVersion: String(import.meta.env.VITE_APP_VERSION || '').trim(),
    latestVersion: '',
    releaseUrl: RELEASES_PAGE_URL,
    reason: '',
    checkedAt: ''
  }
}

function normalizeState(raw) {
  const base = defaultState()
  if (!raw || typeof raw !== 'object') return base
  return {
    checked: Boolean(raw.checked),
    hasUpdate: Boolean(raw.hasUpdate),
    source: String(raw.source || ''),
    currentVersion: String(raw.currentVersion || base.currentVersion).trim(),
    latestVersion: String(raw.latestVersion || '').trim(),
    releaseUrl: String(raw.releaseUrl || RELEASES_PAGE_URL).trim() || RELEASES_PAGE_URL,
    reason: String(raw.reason || ''),
    checkedAt: String(raw.checkedAt || '')
  }
}

function formatCheckedAtText(isoText) {
  const value = String(isoText || '').trim()
  if (!value) return '尚未检查'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '尚未检查'
  }
  return date.toLocaleString()
}

export const useAppUpdateStore = defineStore('appUpdate', () => {
  const checking = ref(false)
  const lastResult = ref(normalizeState(getItem(UPDATE_STATE_STORAGE_KEY, null)))

  const currentVersion = computed(() => (
    String(lastResult.value.currentVersion || import.meta.env.VITE_APP_VERSION || '').trim() || '0.0.0'
  ))
  const latestVersion = computed(() => String(lastResult.value.latestVersion || '').trim())
  const hasUpdate = computed(() => Boolean(lastResult.value.hasUpdate))
  const releaseUrl = computed(() => String(lastResult.value.releaseUrl || RELEASES_PAGE_URL).trim() || RELEASES_PAGE_URL)
  const checkedAtText = computed(() => formatCheckedAtText(lastResult.value.checkedAt))

  const statusText = computed(() => {
    if (checking.value) return '正在检查更新...'
    if (!lastResult.value.checkedAt) return '尚未检查更新'
    if (lastResult.value.reason === 'up-to-date') return `已是最新版本（${currentVersion.value}）`
    if (lastResult.value.reason === 'has-update') {
      return `发现新版本 ${latestVersion.value || '-'}（当前 ${currentVersion.value}）`
    }
    if (lastResult.value.reason === 'network-error') return '检查失败：网络异常或 GitHub 不可达'
    if (lastResult.value.reason === 'unknown-current-version') return '检查失败：当前版本号无效'
    if (lastResult.value.reason === 'invalid-latest-version') return '检查失败：最新版本信息异常'
    if (lastResult.value.reason === 'dev-mode') return '开发模式下不执行自动检查'
    return '更新状态未知'
  })

  function persistState() {
    setItem(UPDATE_STATE_STORAGE_KEY, lastResult.value)
  }

  function applyResult(result) {
    lastResult.value = normalizeState(result)
    persistState()
    return lastResult.value
  }

  async function checkForUpdates(options = {}) {
    const source = String(options.source || 'manual')
    const showPrompt = options.showPrompt !== false
    checking.value = true
    try {
      const result = await checkForAppUpdate({ source, showPrompt })
      return applyResult(result)
    } finally {
      checking.value = false
    }
  }

  return {
    checking,
    lastResult,
    currentVersion,
    latestVersion,
    hasUpdate,
    releaseUrl,
    checkedAtText,
    statusText,
    checkForUpdates,
    applyResult
  }
})

