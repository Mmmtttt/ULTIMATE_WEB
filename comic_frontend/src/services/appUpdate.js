import { showConfirmDialog } from 'vant'
import { getLocation, openExternalUrl } from '@/runtime/browser'

export const RELEASES_PAGE_URL = 'https://github.com/Mmmtttt/ULTIMATE_WEB/releases'
export const LATEST_RELEASE_API_URL = 'https://api.github.com/repos/Mmmtttt/ULTIMATE_WEB/releases/latest'
const REQUEST_TIMEOUT_MS = 10000

function normalizeVersion(rawVersion) {
  const text = String(rawVersion || '').trim()
  if (!text) return ''
  const withoutPrefix = text.replace(/^refs\/tags\//i, '').replace(/^v/i, '')
  return withoutPrefix.trim()
}

function parseVersionParts(version) {
  const normalized = normalizeVersion(version)
  if (!normalized) return []
  const digits = normalized.match(/\d+/g) || []
  return digits.map((item) => Number.parseInt(item, 10)).filter((item) => Number.isFinite(item))
}

function compareVersion(a, b) {
  const left = parseVersionParts(a)
  const right = parseVersionParts(b)
  const maxLength = Math.max(left.length, right.length, 3)
  for (let i = 0; i < maxLength; i += 1) {
    const lv = left[i] ?? 0
    const rv = right[i] ?? 0
    if (lv > rv) return 1
    if (lv < rv) return -1
  }
  return 0
}

function isMeaningfulVersion(version) {
  const parts = parseVersionParts(version)
  if (!parts.length) return false
  return parts.some((item) => item > 0)
}

export function openReleasePage(url) {
  const target = String(url || '').trim() || RELEASES_PAGE_URL
  const opened = openExternalUrl(target, '_blank')
  if (opened) return
  const location = getLocation()
  if (location) {
    location.href = target
  }
}

async function fetchWithTimeout(url, timeoutMs) {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(url, {
      method: 'GET',
      cache: 'no-store',
      signal: controller.signal
    })
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    return await response.json()
  } finally {
    window.clearTimeout(timer)
  }
}

function getCurrentAppVersion() {
  return normalizeVersion(import.meta.env.VITE_APP_VERSION || '0.0.0')
}

function buildCheckResult(payload = {}) {
  return {
    checked: Boolean(payload.checked),
    hasUpdate: Boolean(payload.hasUpdate),
    source: String(payload.source || 'unknown'),
    currentVersion: normalizeVersion(payload.currentVersion || ''),
    latestVersion: normalizeVersion(payload.latestVersion || ''),
    releaseUrl: String(payload.releaseUrl || RELEASES_PAGE_URL).trim() || RELEASES_PAGE_URL,
    reason: String(payload.reason || ''),
    checkedAt: payload.checkedAt || new Date().toISOString(),
  }
}

export async function checkForAppUpdate(options = {}) {
  const source = String(options.source || 'manual')
  const showPrompt = options.showPrompt !== false
  const allowDevCheck = options.allowDevCheck === true || source === 'manual'

  if (import.meta.env.DEV && !allowDevCheck) {
    return buildCheckResult({ checked: false, source, reason: 'dev-mode' })
  }

  const currentVersion = getCurrentAppVersion()
  if (!parseVersionParts(currentVersion).length) {
    return buildCheckResult({
      checked: false,
      source,
      reason: 'unknown-current-version',
      currentVersion
    })
  }

  let latestRelease
  try {
    latestRelease = await fetchWithTimeout(LATEST_RELEASE_API_URL, REQUEST_TIMEOUT_MS)
  } catch (error) {
    console.warn('[Update] failed to fetch latest release:', error)
    return buildCheckResult({
      checked: false,
      source,
      reason: 'network-error',
      currentVersion
    })
  }

  const latestVersion = normalizeVersion(latestRelease?.tag_name || latestRelease?.name || '')
  const releaseUrl = String(latestRelease?.html_url || RELEASES_PAGE_URL).trim() || RELEASES_PAGE_URL

  if (!isMeaningfulVersion(latestVersion)) {
    return buildCheckResult({
      checked: false,
      source,
      reason: 'invalid-latest-version',
      currentVersion,
      latestVersion,
      releaseUrl
    })
  }

  const hasUpdate = compareVersion(latestVersion, currentVersion) > 0
  if (hasUpdate && showPrompt) {
    try {
      await showConfirmDialog({
        title: '发现新版本',
        message: `当前版本 ${currentVersion}，最新版本 ${latestVersion}。是否前往下载更新？`,
        confirmButtonText: '前往下载',
        cancelButtonText: '稍后'
      })
      openReleasePage(releaseUrl)
    } catch (_) {
      // 用户取消
    }
  }

  return buildCheckResult({
    checked: true,
    hasUpdate,
    source,
    currentVersion,
    latestVersion,
    releaseUrl,
    reason: hasUpdate ? 'has-update' : 'up-to-date'
  })
}

export async function checkForAppUpdateOnStartup() {
  return checkForAppUpdate({ source: 'startup', showPrompt: true })
}
