import {
  getDocument,
  getLocation,
  getNavigator,
  getViewportHeight,
  requestNextFrame
} from '@/runtime/browser'
import {
  calculateLoadSequence,
  clampPage,
  READER_LOAD_WINDOW,
  estimateReaderPageExtent,
  estimateReaderRangeExtent
} from './readerLoadWindow'

export {
  calculateLoadSequence,
  clampPage,
  READER_LOAD_WINDOW,
  estimateReaderPageExtent,
  estimateReaderRangeExtent
}

const READER_IMAGE_METRICS_STORAGE_KEY = 'reader_image_metrics_v1'
const MAX_READER_IMAGE_METRICS = 5000

function getReaderMetricsStorage(storage) {
  if (storage) return storage
  try {
    return getWindow()?.localStorage || null
  } catch (error) {
    return null
  }
}

function readReaderMetrics(storage) {
  const targetStorage = getReaderMetricsStorage(storage)
  if (!targetStorage) return {}

  try {
    const parsed = JSON.parse(targetStorage.getItem(READER_IMAGE_METRICS_STORAGE_KEY) || '{}')
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
  } catch (error) {
    return {}
  }
}

export function loadReaderImageMetrics(cacheKey, storage) {
  const allMetrics = readReaderMetrics(storage)
  const metrics = allMetrics[String(cacheKey || '')]
  return metrics && typeof metrics === 'object' && !Array.isArray(metrics)
    ? metrics
    : {}
}

export function saveReaderImageMetric(cacheKey, page, width, height, storage) {
  const safeKey = String(cacheKey || '').trim()
  const safePage = Number(page)
  const safeWidth = Number(width)
  const safeHeight = Number(height)
  if (!safeKey || !Number.isInteger(safePage) || safePage < 1) return
  if (!Number.isFinite(safeWidth) || safeWidth <= 0 || !Number.isFinite(safeHeight) || safeHeight <= 0) return

  const targetStorage = getReaderMetricsStorage(storage)
  if (!targetStorage) return

  try {
    const allMetrics = readReaderMetrics(targetStorage)
    const metrics = allMetrics[safeKey] && typeof allMetrics[safeKey] === 'object'
      ? allMetrics[safeKey]
      : {}
    metrics[safePage] = {
      width: Math.round(safeWidth),
      height: Math.round(safeHeight),
      updatedAt: Date.now()
    }
    allMetrics[safeKey] = metrics

    const entries = []
    for (const [key, keyMetrics] of Object.entries(allMetrics)) {
      for (const [metricPage, metric] of Object.entries(keyMetrics || {})) {
        entries.push({ key, page: metricPage, updatedAt: Number(metric?.updatedAt) || 0 })
      }
    }
    entries.sort((left, right) => right.updatedAt - left.updatedAt)
    const keep = new Set(entries.slice(0, MAX_READER_IMAGE_METRICS).map((item) => `${item.key}:${item.page}`))
    for (const [key, keyMetrics] of Object.entries(allMetrics)) {
      for (const pageKey of Object.keys(keyMetrics || {})) {
        if (!keep.has(`${key}:${pageKey}`)) delete keyMetrics[pageKey]
      }
      if (Object.keys(keyMetrics || {}).length === 0) delete allMetrics[key]
    }

    targetStorage.setItem(READER_IMAGE_METRICS_STORAGE_KEY, JSON.stringify(allMetrics))
  } catch (error) {
    // Browser storage can be unavailable or full; dimensions remain an in-memory optimization.
  }
}

export function createReaderLoadController({
  getTotalPages,
  getFocusPage,
  getImageUrl,
  getIsPageLoadable = () => true,
  getIsMobileViewport = () => false,
  getLanHost = isLikelyLanHost,
  loadedPages,
  loadingPages,
  loadQueue,
  getRestoreMode = () => false,
  getLoadWindow = null,
  onPageLoaded = () => {},
  onPageLoadFailed = () => {}
}) {
  let sessionToken = 0
  const activePreloads = new Map()
  let activeBounds = { minPage: 1, maxPage: 0 }

  const getBounds = () => {
    const totalPages = Math.max(0, Math.floor(Number(getTotalPages()) || 0))
    if (totalPages <= 0) return { minPage: 1, maxPage: 0 }

    const focusPage = clampPage(getFocusPage(), totalPages)
    const restoreMode = Boolean(getRestoreMode())
    const customWindow = typeof getLoadWindow === 'function'
      ? getLoadWindow({ restoreMode, totalPages, focusPage })
      : null
    const before = Number.isFinite(customWindow?.before)
      ? Math.max(0, Math.floor(customWindow.before))
      : restoreMode
        ? READER_LOAD_WINDOW.restoreBefore
        : READER_LOAD_WINDOW.normalBefore
    const after = Number.isFinite(customWindow?.after)
      ? Math.max(0, Math.floor(customWindow.after))
      : restoreMode
        ? READER_LOAD_WINDOW.restoreAfter
        : READER_LOAD_WINDOW.normalAfter

    return {
      minPage: Math.max(1, focusPage - before),
      maxPage: Math.min(totalPages, focusPage + after)
    }
  }

  const isPageInWindow = (page) => {
    const safePage = Number(page)
    return Number.isInteger(safePage) &&
      safePage >= activeBounds.minPage &&
      safePage <= activeBounds.maxPage
  }

  const cancelPreload = (page) => {
    const active = activePreloads.get(page)
    if (!active) return
    activePreloads.delete(page)
    try {
      active.image.onload = null
      active.image.onerror = null
      active.image.src = ''
    } catch (error) {
      // Browsers may reject clearing an already completed image request.
    }
    loadingPages.value.delete(page)
  }

  const cancelOutsideWindow = () => {
    for (const page of activePreloads.keys()) {
      if (!isPageInWindow(page)) cancelPreload(page)
    }
    loadQueue.value = loadQueue.value.filter((page) => isPageInWindow(page))
  }

  const rebuildQueue = () => {
    activeBounds = getBounds()
    cancelOutsideWindow()
    if (activeBounds.maxPage < activeBounds.minPage) {
      loadQueue.value = []
      return
    }

    const sequence = calculateLoadSequence(
      getFocusPage(),
      getTotalPages(),
      activeBounds
    )
    const nextQueue = []
    for (const page of sequence) {
      if (!getIsPageLoadable(page)) continue
      if (loadedPages.value.has(page) || loadingPages.value.has(page)) continue
      nextQueue.push(page)
    }
    loadQueue.value = nextQueue
  }

  const processQueue = (token = sessionToken) => {
    if (token !== sessionToken) return
    const adaptiveMaxConcurrent = getAdaptiveMaxConcurrent({
      isMobileViewport: Boolean(getIsMobileViewport()),
      lanHost: Boolean(getLanHost())
    })
    const maxConcurrent = Boolean(getRestoreMode())
      ? Math.max(2, Math.min(adaptiveMaxConcurrent, 4))
      : Math.max(3, Math.min(adaptiveMaxConcurrent, 6))

    while (loadQueue.value.length > 0 && activePreloads.size < maxConcurrent) {
      const page = loadQueue.value.shift()
      if (!isPageInWindow(page) || !getIsPageLoadable(page)) continue
      if (loadedPages.value.has(page) || activePreloads.has(page)) continue

      const image = new Image()
      const request = { image, token }
      activePreloads.set(page, request)
      loadingPages.value.add(page)
      const finish = (loaded) => {
        if (activePreloads.get(page) !== request) return
        activePreloads.delete(page)
        loadingPages.value.delete(page)
        if (token !== sessionToken) return
        if (loaded) {
          loadedPages.value.add(page)
          onPageLoaded(page, image)
        } else {
          onPageLoadFailed(page)
        }
        if (loadQueue.value.length > 0) {
          const schedule = typeof queueMicrotask === 'function'
            ? queueMicrotask
            : (callback) => Promise.resolve().then(callback)
          schedule(() => processQueue(token))
        }
      }

      image.onload = () => finish(true)
      image.onerror = () => finish(false)
      image.src = getImageUrl(page) || ''
    }
  }

  const preload = () => {
    rebuildQueue()
    processQueue()
  }

  const retry = (page) => {
    const safePage = Number(page)
    if (!isPageInWindow(safePage) || !getIsPageLoadable(safePage)) return
    loadedPages.value.delete(safePage)
    loadQueue.value = [safePage, ...loadQueue.value.filter((queuedPage) => queuedPage !== safePage)]
    processQueue()
  }

  const cancelAll = () => {
    sessionToken += 1
    for (const page of Array.from(activePreloads.keys())) cancelPreload(page)
    loadQueue.value = []
    activeBounds = { minPage: 1, maxPage: 0 }
  }

  return {
    preload,
    retry,
    cancelAll,
    isPageInWindow,
    getBounds,
    getActiveRequestCount: () => activePreloads.size
  }
}

export function isLikelyLanHost(hostname) {
  const location = getLocation()
  const host = hostname || location?.hostname || ''

  if (!host) return false

  return (
    host === 'localhost' ||
    host === '127.0.0.1' ||
    host === '::1' ||
    /^10\./.test(host) ||
    /^192\.168\./.test(host) ||
    /^172\.(1[6-9]|2\d|3[0-1])\./.test(host)
  )
}

export function getAdaptiveMaxConcurrent({
  isMobileViewport = false,
  lanHost = false,
  hardwareConcurrency
} = {}) {
  const runtimeNavigator = getNavigator()
  const cores =
    Number.isFinite(hardwareConcurrency) && hardwareConcurrency > 0
      ? hardwareConcurrency
      : runtimeNavigator && runtimeNavigator.hardwareConcurrency
        ? runtimeNavigator.hardwareConcurrency
        : 8

  const lanBoost = lanHost ? 4 : 0

  if (isMobileViewport) {
    return Math.min(10, Math.max(3, Math.floor(cores / 2) + Math.floor(lanBoost / 2)))
  }

  return Math.min(28, Math.max(8, cores + 4 + lanBoost))
}

export function nextAnimationFrame() {
  return new Promise((resolve) => {
    const frameId = requestNextFrame(() => resolve())
    if (!frameId) {
      resolve()
    }
  })
}

export function updateViewportHeightCssVar(varName = '--reader-vh') {
  const documentRef = getDocument()
  if (!documentRef) return
  const height = getViewportHeight()
  documentRef.documentElement.style.setProperty(varName, `${height}px`)
}
