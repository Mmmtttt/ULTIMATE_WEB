<template>
  <div class="comic-reader" :style="{ background: background }" ref="readerRoot">
    <van-nav-bar 
      class="reader-nav"
      v-show="showMenu"
      title="" 
      left-text="返回" 
      left-arrow 
      @click-left="$router.back()"
      :style="{ background: 'transparent' }"
    >
      <template #right>
        <span class="mode-switch" @click="togglePageMode">
          {{ pageMode === 'left_right' ? '左右' : '上下' }}
        </span>
      </template>
    </van-nav-bar>
    
    <div v-if="loading" class="loading">
      <van-loading type="spinner" color="#fff" />
    </div>
    
    <div v-else-if="error" class="error">
      <van-empty description="加载失败" />
      <van-button type="primary" @click="loadImages">重试</van-button>
    </div>
    
    <div v-else class="reader-content" ref="readerContent" @click.self="toggleMenuVisibility">
      <!-- 左右翻页模式 -->
      <div 
        v-if="pageMode === 'left_right'" 
        class="left-right-mode" 
        :class="{ 'single-page-mode': isSinglePageBrowsing }"
        ref="leftRightContainer"
        :style="getContainerStyle"
        @scroll="handleScroll"
        @wheel="handleWheel"
        @touchstart="handleReaderTouchStart"
        @touchmove="handleReaderTouchMove"
        @touchend="handleReaderTouchEnd"
        @touchcancel="handleReaderTouchEnd"
      >
        <div class="page-track page-track-horizontal" :style="getContentStyle">
          <div 
            v-for="(pageNum, index) in displayedPageNumbers" 
            :key="`lr-${pageNum}-${index}`"
            class="page"
          >
            <img 
              :src="getImageSrc(pageNum)" 
              class="comic-image"
              decoding="async"
              :loading="getImageLoading(pageNum)"
              draggable="false"
              @load="handlePageImageLoad(pageNum)"
              @click="handleImageClick"
              @mousedown="startDrag($event, index)"
            />
          </div>
        </div>
      </div>
      
      <!-- 上下翻页模式 -->
      <div 
        v-else 
        class="up-down-mode" 
        :class="{ 'single-page-mode': isSinglePageBrowsing }"
        ref="upDownContainer" 
        :style="getContainerStyle"
        @scroll="handleScroll"
        @wheel="handleWheel"
        @touchstart="handleReaderTouchStart"
        @touchmove="handleReaderTouchMove"
        @touchend="handleReaderTouchEnd"
        @touchcancel="handleReaderTouchEnd"
      >
        <div class="page-track page-track-vertical" :style="getContentStyle">
          <div 
            v-for="(pageNum, index) in displayedPageNumbers" 
            :key="`ud-${pageNum}-${index}`" 
            class="up-down-page"
          >
            <img 
              :src="getImageSrc(pageNum)" 
              class="comic-image"
              decoding="async"
              :loading="getImageLoading(pageNum)"
              draggable="false"
              @load="handlePageImageLoad(pageNum)"
              @click="handleImageClick"
              @mousedown="startDrag($event, index)"
            />
          </div>
        </div>
      </div>
      
      <!-- 缩放覆盖层 -->
      <div 
        v-if="supportsTouch && isZoomMode" 
        class="zoom-overlay"
        @wheel="handleZoomWheel"
        @mousedown="startZoomDrag"
        @touchstart="startZoomTouch"
        @touchmove="handleZoomTouchMove"
        @touchend="endZoomTouch"
      >
        <img 
          :src="currentZoomImage" 
          class="zoom-image"
          :style="{ 
            transform: `translate(${panX}px, ${panY}px) scale(${zoomLevel})`,
            cursor: zoomLevel > 1 ? 'grab' : 'default'
          }"
          draggable="false"
        />
        <div class="zoom-close" @click="exitZoomMode">
          <van-icon name="cross" size="24" />
        </div>
        <div class="zoom-info">
          {{ Math.round(zoomLevel * 100) }}%
        </div>
      </div>
      
      <!-- 电脑端缩放提示 -->
      <div v-if="!isMobile && zoomLevel > 1" class="desktop-zoom-info">
        {{ Math.round(zoomLevel * 100) }}% | Ctrl+滚轮缩放 | 双击重置
      </div>
    </div>
    
    <!-- 底部控制栏 -->
    <div v-if="showMenu" class="control-bar">
      <div class="progress-section">
        <span class="page-indicator">{{ Math.round(currentPage) }} / {{ totalPage }}</span>
        <div class="progress-slider-container">
          <input 
            type="range" 
            min="1" 
            :max="totalPage" 
            v-model="sliderPage"
            @input="handleSliderChange"
            class="progress-slider"
          />
        </div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: (currentPage / totalPage) * 100 + '%' }"></div>
        </div>
      </div>
      <div class="actions">
        <van-button size="small" @click="prevPage">上一页</van-button>
        <van-button size="small" @click="togglePageMode" class="mode-btn">
          {{ pageMode === 'left_right' ? '上下' : '左右' }}
        </van-button>
        <van-button size="small" @click="nextPage">下一页</van-button>
        <van-button size="small" @click="toggleFullscreen">全屏</van-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useComicStore, useConfigStore } from '@/stores'
import { buildImageUrl } from '@/api/image'
import {
  calculateLoadSequence,
  clampPage,
  getAdaptiveMaxConcurrent,
  isLikelyLanHost,
  nextAnimationFrame,
  updateViewportHeightCssVar
} from '@/composables/readerShared'
import {
  addDocumentListener,
  addWindowListener,
  cancelFrame,
  exitFullscreen,
  getDocument,
  getDocumentElement,
  getFullscreenElement,
  getNavigator,
  getScrollX,
  getScrollY,
  getViewportWidth,
  getVisibilityState,
  getWindow,
  isOntouchstartSupported,
  matchMediaQuery,
  removeDocumentListener,
  removeWindowListener,
  requestFullscreen,
  requestNextFrame
} from '@/runtime/browser'

const route = useRoute()
const comicStore = useComicStore()
const configStore = useConfigStore()

const resolvePageMode = (mode) => (mode === 'left_right' || mode === 'up_down' ? mode : 'up_down')

const images = ref([])
const currentPage = ref(1)
const totalPage = ref(0)
const loading = ref(true)
const error = ref(false)
const showMenu = ref(false)
const pageMode = ref(resolvePageMode(configStore.defaultPageMode))
const background = ref('#000')
const readerRoot = ref(null)
const leftRightContainer = ref(null)
const upDownContainer = ref(null)
const readerContent = ref(null)
const sliderPage = ref(1)

const loadedPages = ref(new Set())
const loadingPages = ref(new Set())
const loadQueue = ref([])

const zoomLevel = ref(1)
const panX = ref(0)
const panY = ref(0)
const isZoomMode = ref(false)
const isZoomDragging = ref(false)
const zoomDragStartX = ref(0)
const zoomDragStartY = ref(0)
const zoomDragStartPanX = ref(0)
const zoomDragStartPanY = ref(0)
const lastTouchDistance = ref(0)
const touchPanActive = ref(false)
const touchPanStartX = ref(0)
const touchPanStartY = ref(0)
const touchPanStartPanX = ref(0)
const touchPanStartPanY = ref(0)
const touchPanLastX = ref(0)
const touchPanLastY = ref(0)
const touchPanLastTime = ref(0)
const touchPanVelocityX = ref(0)
const touchPanVelocityY = ref(0)
const touchPinchLastDistance = ref(0)
const touchPinchLastCenterX = ref(0)
const touchPinchLastCenterY = ref(0)

const isDragging = ref(false)
const dragStartX = ref(0)
const dragStartY = ref(0)
const dragStartScrollX = ref(0)
const dragStartScrollY = ref(0)

const detectMobileDevice = () => {
  if (!getWindow() || !getNavigator()) return false
  const ua = getNavigator()?.userAgent || ''
  const mobileUa = /Android|iPhone|iPad|iPod|Mobile|HarmonyOS/i.test(ua)
  const coarsePointer =
    matchMediaQuery('(pointer: coarse)')
  const narrowViewport = getViewportWidth() <= 1024
  return mobileUa || (coarsePointer && narrowViewport)
}

const detectTouchSupport = () => {
  if (!getWindow() || !getNavigator()) return false
  return (getNavigator()?.maxTouchPoints || 0) > 0 || isOntouchstartSupported()
}

const isProgrammaticScroll = ref(false)
const isMobile = ref(detectMobileDevice())
const supportsTouch = ref(detectTouchSupport())
const isSinglePageBrowsing = computed(() => Boolean(configStore.singlePageBrowsing))
const lastCommittedPage = ref(1)
const lastSavedPage = ref(0)
const pendingRestorePage = ref(null)
const isRestoreBootstrap = ref(false)
const singlePageSwipeActive = ref(false)
const singlePageSwipeStartX = ref(0)
const singlePageSwipeStartY = ref(0)
const singlePageSwipeStartAt = ref(0)

let saveProgressTimer = null
let scrollIdleTimer = null
let programmaticScrollTimer = null
let resizeAlignTimer = null
let scrollRafId = 0
let restoreRetryTimer = null
let restoreRetryCount = 0
let pageUpdateRafId = 0
let inertiaRafId = 0
let restoreBootstrapTimer = null
let scrollObservationToken = 0
let restoreSessionToken = 0

const comicId = computed(() => route.params.id)

const activeContainer = computed(() =>
  pageMode.value === 'left_right' ? leftRightContainer.value : upDownContainer.value
)

const currentZoomImage = computed(() => {
  const pageIndex = clampPage(currentPage.value, totalPage.value) - 1
  return images.value[pageIndex] || ''
})

const displayedPageNumbers = computed(() => {
  if (totalPage.value <= 0) return []
  return Array.from({ length: totalPage.value }, (_, index) => index + 1)
})

const getContainerStyle = computed(() => {
  if (zoomLevel.value <= 1 || isZoomMode.value) {
    return {}
  }

  return {
    touchAction: 'none'
  }
})

const getContentStyle = computed(() => {
  if (zoomLevel.value <= 1 || isZoomMode.value) {
    return {}
  }

  return {
    transform: `translate3d(${panX.value}px, ${panY.value}px, 0) scale(${zoomLevel.value})`,
    transformOrigin: 'left top'
  }
})

const getTouchDistance = (touch1, touch2) =>
  Math.hypot(touch2.clientX - touch1.clientX, touch2.clientY - touch1.clientY)

const getTouchCenterPoint = (touch1, touch2, container) => {
  const centerX = (touch1.clientX + touch2.clientX) / 2
  const centerY = (touch1.clientY + touch2.clientY) / 2
  if (!container || typeof container.getBoundingClientRect !== 'function') {
    return { x: centerX, y: centerY }
  }
  const rect = container.getBoundingClientRect()
  const scrollX =
    typeof container.scrollLeft === 'number'
      ? container.scrollLeft
      : Boolean(getWindow())
        ? getScrollX()
        : 0
  const scrollY =
    typeof container.scrollTop === 'number'
      ? container.scrollTop
      : Boolean(getWindow())
        ? getScrollY()
        : 0
  return {
    x: centerX - rect.left + scrollX,
    y: centerY - rect.top + scrollY
  }
}

const applyPinchAtPoint = (distance, centerX, centerY) => {
  if (distance <= 0) return
  if (touchPinchLastDistance.value <= 0) {
    touchPinchLastDistance.value = distance
    touchPinchLastCenterX.value = centerX
    touchPinchLastCenterY.value = centerY
    return
  }

  const prevZoom = zoomLevel.value
  if (!Number.isFinite(prevZoom) || prevZoom <= 0) return

  const scaleDelta = distance / touchPinchLastDistance.value
  const nextZoom = Math.max(1, Math.min(5, Number((prevZoom * scaleDelta).toFixed(3))))
  const appliedScale = nextZoom / prevZoom
  const centerDeltaX = centerX - touchPinchLastCenterX.value
  const centerDeltaY = centerY - touchPinchLastCenterY.value

  panX.value = centerX - (centerX - panX.value) * appliedScale + centerDeltaX
  panY.value = centerY - (centerY - panY.value) * appliedScale + centerDeltaY
  applyZoomLevel(nextZoom)

  touchPinchLastDistance.value = distance
  touchPinchLastCenterX.value = centerX
  touchPinchLastCenterY.value = centerY
}

const clearPanInertia = () => {
  if (inertiaRafId && Boolean(getWindow())) {
    cancelFrame(inertiaRafId)
  }
  inertiaRafId = 0
}

const syncScrollFromZoomState = () => {
  if (zoomLevel.value <= 1 || isZoomMode.value) return

  const container = activeContainer.value
  if (!container) return

  const currentZoom = zoomLevel.value
  if (!Number.isFinite(currentZoom) || currentZoom <= 0) return

  const currentLeft = typeof container.scrollLeft === 'number' ? container.scrollLeft : 0
  const currentTop = typeof container.scrollTop === 'number' ? container.scrollTop : 0
  const nextLeftRaw = (currentLeft - panX.value) / currentZoom
  const nextTopRaw = (currentTop - panY.value) / currentZoom

  const maxLeft = Math.max(0, (container.scrollWidth || 0) - (container.clientWidth || 0))
  const maxTop = Math.max(0, (container.scrollHeight || 0) - (container.clientHeight || 0))
  const nextLeft = Math.min(maxLeft, Math.max(0, nextLeftRaw))
  const nextTop = Math.min(maxTop, Math.max(0, nextTopRaw))

  invalidateScrollObservation()
  markProgrammaticScroll(120)
  container.scrollTo({
    left: nextLeft,
    top: nextTop,
    behavior: 'auto'
  })
}

const resetZoomState = () => {
  clearPanInertia()
  syncScrollFromZoomState()
  zoomLevel.value = 1
  panX.value = 0
  panY.value = 0
  isZoomDragging.value = false
  touchPanVelocityX.value = 0
  touchPanVelocityY.value = 0
  touchPanLastTime.value = 0
  if (activeContainer.value) {
    updatePageFromScroll()
  }
}

const applyZoomLevel = (nextLevel) => {
  const clamped = Math.max(1, Math.min(5, Number(nextLevel.toFixed(3))))

  if (clamped <= 1 && zoomLevel.value > 1) {
    clearPanInertia()
    syncScrollFromZoomState()
  }

  zoomLevel.value = clamped
  if (clamped <= 1) {
    panX.value = 0
    panY.value = 0
    isZoomDragging.value = false
    touchPanVelocityX.value = 0
    touchPanVelocityY.value = 0
    touchPanLastTime.value = 0
    if (activeContainer.value) {
      updatePageFromScroll()
    }
  }
}

const getZoomContainer = () => activeContainer.value || readerContent.value

const getContainerAnchorPoint = (container, clientX, clientY) => {
  if (!container || typeof container.getBoundingClientRect !== 'function') {
    return { x: 0, y: 0 }
  }

  const rect = container.getBoundingClientRect()
  const rawX = clientX - rect.left
  const rawY = clientY - rect.top
  return {
    x: Math.max(0, Math.min(container.clientWidth || 0, rawX)),
    y: Math.max(0, Math.min(container.clientHeight || 0, rawY))
  }
}

const zoomAtPoint = (nextLevel, anchorPoint, container) => {
  const prevZoom = zoomLevel.value
  const clamped = Math.max(1, Math.min(5, Number(nextLevel.toFixed(3))))

  if (!Number.isFinite(prevZoom) || prevZoom <= 0) {
    applyZoomLevel(clamped)
    return
  }

  if (Math.abs(clamped - prevZoom) < 0.0001) return

  if (!container || !anchorPoint || clamped <= 1) {
    applyZoomLevel(clamped)
    return
  }

  const scrollX = typeof container.scrollLeft === 'number' ? container.scrollLeft : 0
  const scrollY = typeof container.scrollTop === 'number' ? container.scrollTop : 0
  const scaleRatio = clamped / prevZoom

  panX.value =
    anchorPoint.x +
    scrollX -
    (anchorPoint.x + scrollX - panX.value) * scaleRatio
  panY.value =
    anchorPoint.y +
    scrollY -
    (anchorPoint.y + scrollY - panY.value) * scaleRatio

  applyZoomLevel(clamped)
  if (activeContainer.value) {
    updatePageFromScroll()
  }
}

const updateDeviceState = () => {
  if (!getWindow()) return
  isMobile.value = detectMobileDevice()
  supportsTouch.value = detectTouchSupport()
}

const updateReaderViewport = () => {
  updateViewportHeightCssVar('--reader-vh')
}

const markProgrammaticScroll = (duration = 220) => {
  isProgrammaticScroll.value = true
  if (programmaticScrollTimer) {
    clearTimeout(programmaticScrollTimer)
  }
  programmaticScrollTimer = setTimeout(() => {
    isProgrammaticScroll.value = false
  }, duration)
}

const clearScrollCommitTimer = () => {
  if (scrollIdleTimer) {
    clearTimeout(scrollIdleTimer)
    scrollIdleTimer = null
  }
}

const nextScrollObservation = () => {
  scrollObservationToken += 1
  return scrollObservationToken
}

const invalidateScrollObservation = () => {
  nextScrollObservation()
  clearScrollCommitTimer()
}

const nextRestoreSessionToken = () => {
  restoreSessionToken += 1
  return restoreSessionToken
}

const getPageElements = (container) => {
  if (!container) return []
  const selector = pageMode.value === 'left_right' ? '.page' : '.up-down-page'
  return Array.from(container.querySelectorAll(selector))
}

const getAxisStart = (element) => {
  if (!element) return 0
  return pageMode.value === 'left_right' ? element.offsetLeft : element.offsetTop
}

const getAxisExtent = (element) => {
  if (!element) return 0
  return pageMode.value === 'left_right' ? element.offsetWidth : element.offsetHeight
}

const getRectAxisStart = (rect) => {
  if (!rect) return 0
  return pageMode.value === 'left_right' ? rect.left : rect.top
}

const getRectAxisEnd = (rect) => {
  if (!rect) return 0
  return pageMode.value === 'left_right' ? rect.right : rect.bottom
}

const getRectAxisCenter = (rect) => {
  if (!rect) return 0
  return (getRectAxisStart(rect) + getRectAxisEnd(rect)) / 2
}

const getPageElementByNumber = (container, page) => {
  const pages = getPageElements(container)
  if (!pages.length) return null
  const index = clampPage(page, pages.length) - 1
  return pages[index] || null
}

const getViewportExtent = (container) => {
  if (!container) return 0
  return pageMode.value === 'left_right' ? container.clientWidth : container.clientHeight
}

const isPageExtentReady = (container, page) => {
  const element = getPageElementByNumber(container, page)
  return getAxisExtent(element) > 0
}

const isScrollAlignedWithPage = (container, page) => {
  if (!container) return false
  if (!isPageExtentReady(container, page)) return false

  const element = getPageElementByNumber(container, page)
  if (!element) return false

  const containerRect = container.getBoundingClientRect()
  const elementRect = element.getBoundingClientRect()
  const targetOffset = getRectAxisStart(elementRect)
  const currentOffset = getRectAxisStart(containerRect)
  const tolerance = Math.max(2, getViewportExtent(container) * 0.02)
  return Math.abs(currentOffset - targetOffset) <= tolerance
}

const scrollToPosition = (container, position, behavior) => {
  if (!container) return
  if (pageMode.value === 'left_right') {
    container.scrollTo({ left: position, behavior })
  } else {
    container.scrollTo({ top: position, behavior })
  }
}

const getPageScrollOffset = (container, page) => {
  const pages = getPageElements(container)
  if (!pages.length) return 0
  const targetIndex = clampPage(page, pages.length) - 1
  return getAxisStart(pages[targetIndex])
}

const estimatePageFromScroll = (container) => {
  const pages = getPageElements(container)
  if (!pages.length || totalPage.value <= 0) return 1

  const safeCurrentPage = clampPage(currentPage.value, totalPage.value)
  const containerRect = container.getBoundingClientRect()
  const viewportStart = getRectAxisStart(containerRect)
  const viewportEnd = getRectAxisEnd(containerRect)
  const viewportCenter = getRectAxisCenter(containerRect)
  const epsilon = 0.5

  if (isSinglePageBrowsing.value) {
    let bestPage = safeCurrentPage
    let bestDistance = Number.POSITIVE_INFINITY
    let bestVisible = -1

    for (let index = 0; index < pages.length; index += 1) {
      const rect = pages[index].getBoundingClientRect()
      const extent = pageMode.value === 'left_right' ? rect.width : rect.height
      if (extent <= 0) continue

      const pageStart = getRectAxisStart(rect)
      const pageEnd = getRectAxisEnd(rect)
      const visibleExtent = Math.max(0, Math.min(pageEnd, viewportEnd) - Math.max(pageStart, viewportStart))
      const centerDistance = Math.abs(getRectAxisCenter(rect) - viewportCenter)

      if (
        centerDistance < bestDistance - epsilon ||
        (Math.abs(centerDistance - bestDistance) <= epsilon && visibleExtent > bestVisible + epsilon)
      ) {
        bestPage = index + 1
        bestDistance = centerDistance
        bestVisible = visibleExtent
      }
    }

    return clampPage(bestPage, totalPage.value)
  }

  let bestPage = safeCurrentPage
  let bestVisible = -1
  let bestDistance = Number.POSITIVE_INFINITY

  for (let index = 0; index < pages.length; index += 1) {
    const rect = pages[index].getBoundingClientRect()
    const extent = pageMode.value === 'left_right' ? rect.width : rect.height
    if (extent <= 0) continue

    const pageStart = getRectAxisStart(rect)
    const pageEnd = getRectAxisEnd(rect)
    const visibleExtent = Math.max(0, Math.min(pageEnd, viewportEnd) - Math.max(pageStart, viewportStart))
    if (visibleExtent <= 0 && bestVisible >= 0) {
      continue
    }

    const centerDistance = Math.abs(getRectAxisCenter(rect) - viewportCenter)
    if (
      visibleExtent > bestVisible + epsilon ||
      (Math.abs(visibleExtent - bestVisible) <= epsilon && centerDistance < bestDistance - epsilon)
    ) {
      bestPage = index + 1
      bestVisible = visibleExtent
      bestDistance = centerDistance
    }
  }

  if (bestVisible > 0) {
    return clampPage(bestPage, totalPage.value)
  }

  for (let index = 0; index < pages.length; index += 1) {
    const rect = pages[index].getBoundingClientRect()
    const extent = pageMode.value === 'left_right' ? rect.width : rect.height
    if (extent <= 0) continue
    if (getRectAxisEnd(rect) > viewportStart + epsilon) {
      return clampPage(index + 1, totalPage.value)
    }
  }

  return safeCurrentPage
}

const flushProgressSave = async (page) => {
  if (!comicId.value || totalPage.value <= 0) return
  const safePage = clampPage(page, totalPage.value)
  if (safePage === lastSavedPage.value) return

  try {
    await comicStore.saveProgress(comicId.value, safePage)
    lastSavedPage.value = safePage
  } catch (err) {
    console.error('保存进度失败:', err)
  }
}

const scheduleProgressSave = (page, immediate = false) => {
  if (totalPage.value <= 0) return
  const safePage = clampPage(page, totalPage.value)

  if (saveProgressTimer) {
    clearTimeout(saveProgressTimer)
    saveProgressTimer = null
  }

  if (immediate) {
    void flushProgressSave(safePage)
    return
  }

  saveProgressTimer = setTimeout(() => {
    void flushProgressSave(safePage)
  }, 1600)
}

const writeDisplayedPage = (page) => {
  if (totalPage.value <= 0) return 1
  const safePage = clampPage(page, totalPage.value)
  currentPage.value = safePage
  sliderPage.value = safePage
  return safePage
}

const commitReadingPage = (page, immediateProgress = false) => {
  const safePage = writeDisplayedPage(page)

  if (safePage !== lastCommittedPage.value) {
    lastCommittedPage.value = safePage
    preloadImages(safePage)
  }

  scheduleProgressSave(safePage, immediateProgress)
  return safePage
}

const scheduleScrollCommit = (observationToken = scrollObservationToken) => {
  clearScrollCommitTimer()

  scrollIdleTimer = setTimeout(() => {
    if (observationToken !== scrollObservationToken) return
    if (isProgrammaticScroll.value || totalPage.value <= 0) return
    commitReadingPage(currentPage.value)
  }, 220)
}

const rebuildLoadQueue = (centerPage) => {
  if (totalPage.value <= 0) {
    loadQueue.value = []
    return
  }

  const focusPage =
    pendingRestorePage.value != null
      ? clampPage(pendingRestorePage.value, totalPage.value)
      : clampPage(centerPage, totalPage.value)
  const baseSequence = calculateLoadSequence(focusPage, totalPage.value)
  const sequence = isRestoreBootstrap.value
    ? baseSequence.filter((pageNum) => {
        const minPage = Math.max(1, focusPage - 1)
        const maxPage = Math.min(totalPage.value, focusPage + 24)
        return pageNum >= minPage && pageNum <= maxPage
      })
    : baseSequence

  const nextQueue = []
  for (const pageNum of sequence) {
    if (loadedPages.value.has(pageNum) || loadingPages.value.has(pageNum)) {
      continue
    }
    nextQueue.push(pageNum)
  }
  loadQueue.value = nextQueue
}

const queueProcessNextTick = () => {
  if (typeof queueMicrotask === 'function') {
    queueMicrotask(() => processLoadQueue())
  } else {
    setTimeout(() => processLoadQueue(), 0)
  }
}

const processLoadQueue = () => {
  const adaptiveMaxConcurrent = getAdaptiveMaxConcurrent({
    isMobileViewport: isMobile.value,
    lanHost: isLikelyLanHost()
  })
  const maxConcurrent = isRestoreBootstrap.value
    ? Math.max(2, Math.min(adaptiveMaxConcurrent, 4))
    : pendingRestorePage.value != null
      ? Math.max(3, Math.min(adaptiveMaxConcurrent, 6))
      : adaptiveMaxConcurrent

  while (loadQueue.value.length > 0 && loadingPages.value.size < maxConcurrent) {
    const pageNum = loadQueue.value.shift()
    if (loadedPages.value.has(pageNum) || loadingPages.value.has(pageNum)) {
      continue
    }

    loadingPages.value.add(pageNum)

    const img = new Image()
    const imageUrl = buildImageUrl(comicId.value, pageNum)

    img.onload = () => {
      loadedPages.value.add(pageNum)
      loadingPages.value.delete(pageNum)
      queueProcessNextTick()
    }

    img.onerror = () => {
      loadingPages.value.delete(pageNum)
      queueProcessNextTick()
    }

    img.src = imageUrl
  }
}

const preloadImages = (startPage) => {
  rebuildLoadQueue(startPage)
  processLoadQueue()
}

const getImageSrc = (pageNum) => {
  const safePage = clampPage(pageNum, totalPage.value)
  if (!loadedPages.value.has(safePage)) {
    return ''
  }
  return images.value[safePage - 1] || ''
}

const getLoadFocusPage = () => {
  if (totalPage.value <= 0) return 1
  const focus = pendingRestorePage.value != null ? pendingRestorePage.value : currentPage.value
  return clampPage(focus, totalPage.value)
}

const getImageLoading = (pageNum) => {
  const safePage = clampPage(pageNum, totalPage.value)
  const focusPage = getLoadFocusPage()
  const eagerStart = Math.max(1, focusPage - 1)
  const eagerEnd = Math.min(totalPage.value, focusPage + 4)
  return safePage >= eagerStart && safePage <= eagerEnd ? 'eager' : 'lazy'
}

const clearRestoreRetry = () => {
  if (restoreRetryTimer) {
    clearTimeout(restoreRetryTimer)
    restoreRetryTimer = null
  }
}

const clearRestoreBootstrap = () => {
  if (restoreBootstrapTimer) {
    clearTimeout(restoreBootstrapTimer)
    restoreBootstrapTimer = null
  }
  isRestoreBootstrap.value = false
}

const startRestoreBootstrap = (duration = 2200) => {
  clearRestoreBootstrap()
  isRestoreBootstrap.value = true
  restoreBootstrapTimer = setTimeout(() => {
    isRestoreBootstrap.value = false
    restoreBootstrapTimer = null
    if (totalPage.value > 0) {
      preloadImages(clampPage(currentPage.value, totalPage.value))
    }
  }, duration)
}

const scheduleRestoreRetry = (delay, restoreSession = restoreSessionToken) => {
  if (restoreSession !== restoreSessionToken) return
  if (pendingRestorePage.value == null) return

  restoreRetryCount += 1
  if (restoreRetryCount >= 90) {
    pendingRestorePage.value = null
    clearRestoreRetry()
    return
  }
  const nextDelay =
    typeof delay === 'number' && delay >= 0
      ? delay
      : Math.min(1200, 120 + restoreRetryCount * 45)

  clearRestoreRetry()
  restoreRetryTimer = setTimeout(() => {
    void tryRestorePendingPage(restoreSession)
  }, nextDelay)
}

const tryRestorePendingPage = async (restoreSession = restoreSessionToken) => {
  if (restoreSession !== restoreSessionToken) return
  if (pendingRestorePage.value == null || totalPage.value <= 0) return

  const targetPage = clampPage(pendingRestorePage.value, totalPage.value)
  await nextTick()
  await nextAnimationFrame()
  if (restoreSession !== restoreSessionToken) return

  const containerBeforeJump = activeContainer.value
  if (!containerBeforeJump) {
    scheduleRestoreRetry(120, restoreSession)
    return
  }

  await jumpToPage(targetPage, false, { reason: 'restore' })
  if (restoreSession !== restoreSessionToken) return

  const container = activeContainer.value
  if (container && isScrollAlignedWithPage(container, targetPage)) {
    pendingRestorePage.value = null
    restoreRetryCount = 0
    clearRestoreRetry()
    return
  }

  scheduleRestoreRetry(undefined, restoreSession)
}

const handlePageImageLoad = (pageNum) => {
  const pendingPage = pendingRestorePage.value
  if (pendingPage == null) return

  if (pageNum <= pendingPage + 1) {
    restoreRetryCount = 0
    clearRestoreRetry()
    void tryRestorePendingPage(restoreSessionToken)
  }
}

const loadImages = async () => {
  loading.value = true
  error.value = false
  resetZoomState()
  singlePageSwipeActive.value = false
  singlePageSwipeStartAt.value = 0
  invalidateScrollObservation()
  pendingRestorePage.value = null
  isRestoreBootstrap.value = false
  restoreRetryCount = 0
  clearRestoreRetry()
  clearRestoreBootstrap()
  const restoreSession = nextRestoreSessionToken()
  loadedPages.value = new Set()
  loadingPages.value = new Set()
  loadQueue.value = []

  try {
    const comic = await comicStore.fetchComicDetail(comicId.value)
    const imageData = await comicStore.fetchImages(comicId.value)

    if (!imageData || imageData.length === 0) {
      throw new Error('empty images')
    }

    images.value = imageData.map((_, index) => buildImageUrl(comicId.value, index + 1))
    totalPage.value = images.value.length

    const routePage = Number(route.query.page)
    const initialPage = clampPage(
      Number.isFinite(routePage) && routePage > 0 ? routePage : comic?.current_page || 1,
      totalPage.value
    )

    currentPage.value = initialPage
    sliderPage.value = initialPage
    lastCommittedPage.value = initialPage
    lastSavedPage.value = initialPage
    pendingRestorePage.value = initialPage
    restoreRetryCount = 0
    clearRestoreRetry()
    startRestoreBootstrap()

    preloadImages(initialPage)

    await nextTick()
    await nextAnimationFrame()
    void tryRestorePendingPage(restoreSession)
  } catch (err) {
    error.value = true
    console.error('加载图片失败:', err)
  } finally {
    loading.value = false
  }
}

const jumpToPage = async (page, smooth = true, options = {}) => {
  if (totalPage.value <= 0) return
  const reason = options.reason || 'navigation'
  const targetPage = clampPage(page, totalPage.value)
  const behavior = smooth ? 'smooth' : 'auto'

  if (reason !== 'restore' && pendingRestorePage.value != null) {
    pendingRestorePage.value = null
    restoreRetryCount = 0
    clearRestoreRetry()
    nextRestoreSessionToken()
  }
  invalidateScrollObservation()
  commitReadingPage(targetPage, !smooth)

  if (!activeContainer.value) {
    await nextTick()
    await nextAnimationFrame()
  }

  const container = activeContainer.value
  if (container) {
    const preferredOffset = getPageScrollOffset(container, targetPage)
    const fallbackOffset = (targetPage - 1) * getViewportExtent(container)
    const scrollPosition =
      preferredOffset > 0 || targetPage === 1 ? preferredOffset : fallbackOffset
    markProgrammaticScroll(smooth ? 260 : 120)
    scrollToPosition(container, scrollPosition, behavior)
  }
}

const prevPage = () => {
  const targetPage = Math.max(1, clampPage(currentPage.value, totalPage.value) - 1)
  void jumpToPage(targetPage, true, { reason: 'step' })
}

const nextPage = () => {
  const targetPage = Math.min(totalPage.value, clampPage(currentPage.value, totalPage.value) + 1)
  void jumpToPage(targetPage, true, { reason: 'step' })
}

const handleSliderChange = () => {
  const page = parseInt(sliderPage.value, 10)
  if (page >= 1 && page <= totalPage.value) {
    void jumpToPage(page, false, { reason: 'slider' })
  }
}

const updatePageFromScroll = () => {
  const container = activeContainer.value
  if (!container || totalPage.value <= 0) return
  const observationToken = nextScrollObservation()

  if (pendingRestorePage.value != null) {
    const lockedPage = clampPage(pendingRestorePage.value, totalPage.value)
    writeDisplayedPage(lockedPage)
    return
  }

  const estimatedPage = estimatePageFromScroll(container)
  writeDisplayedPage(estimatedPage)

  scheduleScrollCommit(observationToken)
}

const handleScroll = () => {
  if (!getWindow()) {
    updatePageFromScroll()
    return
  }

  if (scrollRafId) return
  scrollRafId = requestNextFrame(() => {
    scrollRafId = 0
    updatePageFromScroll()
  })
}

const flushProgressBeforeLeave = () => {
  if (saveProgressTimer) {
    clearTimeout(saveProgressTimer)
    saveProgressTimer = null
  }
  if (totalPage.value > 0) {
    void flushProgressSave(clampPage(currentPage.value, totalPage.value))
  }
}

const handleImageClick = () => {
  if (!isDragging.value) {
    toggleMenuVisibility()
  }
}

const toggleMenuVisibility = () => {
  showMenu.value = !showMenu.value
}

const togglePageMode = async () => {
  if (totalPage.value <= 0) return
  const anchorPage = clampPage(currentPage.value, totalPage.value)
  pageMode.value = pageMode.value === 'left_right' ? 'up_down' : 'left_right'
  configStore.setPageMode(pageMode.value)
  writeDisplayedPage(anchorPage)

  await nextTick()
  await nextAnimationFrame()
  await jumpToPage(anchorPage, false, { reason: 'mode-switch' })
}

const enterZoomMode = () => {
  if (!supportsTouch.value) return
  isZoomMode.value = true
  showMenu.value = false
  resetZoomState()
}

const exitZoomMode = () => {
  isZoomMode.value = false
  resetZoomState()
}

const zoomIn = () => {
  const container = getZoomContainer()
  if (!container) {
    applyZoomLevel(zoomLevel.value + 0.2)
    return
  }

  const anchorPoint = {
    x: (container.clientWidth || 0) / 2,
    y: (container.clientHeight || 0) / 2
  }
  zoomAtPoint(zoomLevel.value + 0.2, anchorPoint, container)
}

const zoomOut = () => {
  const container = getZoomContainer()
  if (!container) {
    applyZoomLevel(zoomLevel.value - 0.2)
    return
  }

  const anchorPoint = {
    x: (container.clientWidth || 0) / 2,
    y: (container.clientHeight || 0) / 2
  }
  zoomAtPoint(zoomLevel.value - 0.2, anchorPoint, container)
}

const queuePageUpdate = () => {
  if (!getWindow()) {
    updatePageFromScroll()
    return
  }

  if (pageUpdateRafId) return
  pageUpdateRafId = requestNextFrame(() => {
    pageUpdateRafId = 0
    updatePageFromScroll()
  })
}

const startPanInertia = () => {
  if (!getWindow() || zoomLevel.value <= 1 || isZoomMode.value) return

  let velocityX = touchPanVelocityX.value
  let velocityY = touchPanVelocityY.value
  if (Math.hypot(velocityX, velocityY) < 0.05) return

  clearPanInertia()

  const frictionPerFrame = 0.92
  const stopSpeed = 0.015
  const maxDuration = 1400
  let elapsed = 0
  let lastTime = performance.now()

  const step = (now) => {
    const dt = Math.max(1, now - lastTime)
    lastTime = now
    elapsed += dt

    panX.value += velocityX * dt
    panY.value += velocityY * dt

    const decay = Math.pow(frictionPerFrame, dt / 16.667)
    velocityX *= decay
    velocityY *= decay
    queuePageUpdate()

    if (elapsed >= maxDuration || Math.hypot(velocityX, velocityY) <= stopSpeed) {
      inertiaRafId = 0
      touchPanVelocityX.value = 0
      touchPanVelocityY.value = 0
      queuePageUpdate()
      return
    }

    inertiaRafId = requestNextFrame(step)
  }

  inertiaRafId = requestNextFrame(step)
}

const handleWheel = (event) => {
  if (isZoomMode.value) return

  if (event.ctrlKey) {
    event.preventDefault()
    const container = getZoomContainer()
    const anchorPoint = container
      ? getContainerAnchorPoint(container, event.clientX, event.clientY)
      : { x: 0, y: 0 }
    const nextZoom = event.deltaY > 0 ? zoomLevel.value - 0.2 : zoomLevel.value + 0.2
    zoomAtPoint(nextZoom, anchorPoint, container)
    return
  }

  if (zoomLevel.value > 1) {
    event.preventDefault()
    clearPanInertia()
    panX.value -= event.deltaX
    panY.value -= event.deltaY
    queuePageUpdate()
    return
  }

  if (isMobile.value) return

  if (pageMode.value === 'left_right' && leftRightContainer.value) {
    if (Math.abs(event.deltaY) > Math.abs(event.deltaX)) {
      event.preventDefault()
      leftRightContainer.value.scrollLeft += event.deltaY
    }
  }
}

const handleReaderTouchStart = (event) => {
  if (!supportsTouch.value || isZoomMode.value) return

  if (event.touches.length === 2) {
    event.preventDefault()
    clearPanInertia()
    touchPanActive.value = false
    touchPanVelocityX.value = 0
    touchPanVelocityY.value = 0
    touchPanLastTime.value = 0
    const container = activeContainer.value || readerContent.value
    const center = getTouchCenterPoint(event.touches[0], event.touches[1], container)
    touchPinchLastDistance.value = getTouchDistance(event.touches[0], event.touches[1])
    touchPinchLastCenterX.value = center.x
    touchPinchLastCenterY.value = center.y
    return
  }

  if (event.touches.length === 1 && zoomLevel.value > 1) {
    event.preventDefault()
    clearPanInertia()
    const touch = event.touches[0]
    touchPanActive.value = true
    touchPanStartX.value = touch.clientX
    touchPanStartY.value = touch.clientY
    touchPanStartPanX.value = panX.value
    touchPanStartPanY.value = panY.value
    touchPanLastX.value = touch.clientX
    touchPanLastY.value = touch.clientY
    touchPanLastTime.value =
      typeof performance !== 'undefined' ? performance.now() : Date.now()
    touchPanVelocityX.value = 0
    touchPanVelocityY.value = 0
  }
}

const handleReaderTouchMove = (event) => {
  if (!supportsTouch.value || isZoomMode.value) return

  if (event.touches.length === 2) {
    event.preventDefault()
    clearPanInertia()
    const container = activeContainer.value || readerContent.value
    const center = getTouchCenterPoint(event.touches[0], event.touches[1], container)
    const distance = getTouchDistance(event.touches[0], event.touches[1])
    applyPinchAtPoint(distance, center.x, center.y)
    queuePageUpdate()
    touchPanActive.value = false
    touchPanVelocityX.value = 0
    touchPanVelocityY.value = 0
    touchPanLastTime.value = 0
    return
  }

  if (event.touches.length === 1 && zoomLevel.value > 1) {
    event.preventDefault()
    const touch = event.touches[0]
    if (!touchPanActive.value) {
      touchPanActive.value = true
      touchPanStartX.value = touch.clientX
      touchPanStartY.value = touch.clientY
      touchPanStartPanX.value = panX.value
      touchPanStartPanY.value = panY.value
      touchPanLastX.value = touch.clientX
      touchPanLastY.value = touch.clientY
      touchPanLastTime.value =
        typeof performance !== 'undefined' ? performance.now() : Date.now()
      touchPanVelocityX.value = 0
      touchPanVelocityY.value = 0
      return
    }

    const now = typeof performance !== 'undefined' ? performance.now() : Date.now()
    const dt = Math.max(1, now - (touchPanLastTime.value || now))
    const instantVX = (touch.clientX - touchPanLastX.value) / dt
    const instantVY = (touch.clientY - touchPanLastY.value) / dt
    touchPanVelocityX.value = touchPanVelocityX.value * 0.72 + instantVX * 0.28
    touchPanVelocityY.value = touchPanVelocityY.value * 0.72 + instantVY * 0.28
    touchPanLastX.value = touch.clientX
    touchPanLastY.value = touch.clientY
    touchPanLastTime.value = now

    panX.value = touchPanStartPanX.value + (touch.clientX - touchPanStartX.value)
    panY.value = touchPanStartPanY.value + (touch.clientY - touchPanStartY.value)
    queuePageUpdate()
  }
}

const handleReaderTouchEnd = (event) => {
  if (!supportsTouch.value || isZoomMode.value) return

  if (event.touches.length === 1 && zoomLevel.value > 1) {
    clearPanInertia()
    const touch = event.touches[0]
    touchPanActive.value = true
    touchPanStartX.value = touch.clientX
    touchPanStartY.value = touch.clientY
    touchPanStartPanX.value = panX.value
    touchPanStartPanY.value = panY.value
    touchPanLastX.value = touch.clientX
    touchPanLastY.value = touch.clientY
    touchPanLastTime.value =
      typeof performance !== 'undefined' ? performance.now() : Date.now()
    touchPanVelocityX.value = 0
    touchPanVelocityY.value = 0
    touchPinchLastDistance.value = 0
    return
  }

  const canInertia =
    zoomLevel.value > 1 &&
    Math.hypot(touchPanVelocityX.value, touchPanVelocityY.value) >= 0.05

  touchPanActive.value = false
  touchPinchLastDistance.value = 0
  touchPinchLastCenterX.value = 0
  touchPinchLastCenterY.value = 0
  touchPanLastTime.value = 0
  if (canInertia) {
    startPanInertia()
    return
  }
  touchPanVelocityX.value = 0
  touchPanVelocityY.value = 0
  if (zoomLevel.value > 1) {
    queuePageUpdate()
  }
}

const startDrag = (event) => {
  if (event.button !== 0) return

  const container = activeContainer.value
  if (!container) return

  isDragging.value = false
  event.preventDefault()

  dragStartX.value = event.clientX
  dragStartY.value = event.clientY
  dragStartScrollX.value = container.scrollLeft
  dragStartScrollY.value = container.scrollTop
  const dragZoomedContent = zoomLevel.value > 1 && !isZoomMode.value

  if (dragZoomedContent) {
    zoomDragStartPanX.value = panX.value
    zoomDragStartPanY.value = panY.value
  }

  const handleDragMove = (moveEvent) => {
    const deltaX = Math.abs(moveEvent.clientX - dragStartX.value)
    const deltaY = Math.abs(moveEvent.clientY - dragStartY.value)

    if (deltaX > 5 || deltaY > 5) {
      isDragging.value = true
    }

    if (dragZoomedContent) {
      clearPanInertia()
      panX.value = zoomDragStartPanX.value + (moveEvent.clientX - dragStartX.value)
      panY.value = zoomDragStartPanY.value + (moveEvent.clientY - dragStartY.value)
      queuePageUpdate()
      return
    }

    const speed = zoomLevel.value > 1 ? zoomLevel.value : 1
    if (pageMode.value === 'left_right') {
      container.scrollLeft = dragStartScrollX.value - (moveEvent.clientX - dragStartX.value) * speed
    } else {
      container.scrollTop = dragStartScrollY.value - (moveEvent.clientY - dragStartY.value) * speed
    }
  }

  const handleDragEnd = () => {
    setTimeout(() => {
      isDragging.value = false
    }, 100)

    removeDocumentListener('mousemove', handleDragMove)
    removeDocumentListener('mouseup', handleDragEnd)
    if (!dragZoomedContent) {
      scheduleScrollCommit()
    }
  }

  addDocumentListener('mousemove', handleDragMove)
  addDocumentListener('mouseup', handleDragEnd)
}

const startZoomDrag = (event) => {
  if (zoomLevel.value <= 1) return
  isZoomDragging.value = true
  zoomDragStartX.value = event.clientX
  zoomDragStartY.value = event.clientY
  zoomDragStartPanX.value = panX.value
  zoomDragStartPanY.value = panY.value
  addDocumentListener('mousemove', handleZoomDrag)
  addDocumentListener('mouseup', endZoomDrag)
}

const handleZoomDrag = (event) => {
  if (!isZoomDragging.value) return

  const deltaX = event.clientX - zoomDragStartX.value
  const deltaY = event.clientY - zoomDragStartY.value
  panX.value = zoomDragStartPanX.value + deltaX
  panY.value = zoomDragStartPanY.value + deltaY
}

const endZoomDrag = () => {
  isZoomDragging.value = false
  removeDocumentListener('mousemove', handleZoomDrag)
  removeDocumentListener('mouseup', endZoomDrag)
}

const alignToCurrentPageAfterViewportChange = () => {
  if (resizeAlignTimer) {
    clearTimeout(resizeAlignTimer)
  }

  resizeAlignTimer = setTimeout(async () => {
    if (totalPage.value <= 0) return
    const anchorPage = clampPage(currentPage.value, totalPage.value)
    await jumpToPage(anchorPage, false, { reason: 'viewport-align' })
  }, 140)
}

const toggleFullscreen = async () => {
  if (!getDocument()) return

  const targetEl = readerRoot.value || getDocumentElement()
  try {
    if (!getFullscreenElement()) {
      if (targetEl.requestFullscreen) {
        await requestFullscreen(targetEl)
      }
    } else {
      await exitFullscreen()
    }
  } catch (err) {
    console.error('全屏失败:', err)
  }
}

const handleFullscreenChange = () => {
  updateReaderViewport()
  alignToCurrentPageAfterViewportChange()
}

const startTouchDrag = (event) => {
  if (!supportsTouch.value) return
  if (isZoomMode.value || event.touches.length !== 1 || zoomLevel.value <= 1) return

  event.preventDefault()
  isDragging.value = true
  const touch = event.touches[0]
  zoomDragStartX.value = touch.clientX
  zoomDragStartY.value = touch.clientY
  zoomDragStartPanX.value = panX.value
  zoomDragStartPanY.value = panY.value

  const handleTouchMove = (moveEvent) => {
    if (moveEvent.touches.length !== 1) return
    moveEvent.preventDefault()
    const moveTouch = moveEvent.touches[0]
    panX.value = zoomDragStartPanX.value + (moveTouch.clientX - zoomDragStartX.value)
    panY.value = zoomDragStartPanY.value + (moveTouch.clientY - zoomDragStartY.value)
  }

  const handleTouchEnd = () => {
    isDragging.value = false
    removeDocumentListener('touchmove', handleTouchMove)
    removeDocumentListener('touchend', handleTouchEnd)
    removeDocumentListener('touchcancel', handleTouchEnd)
  }

  addDocumentListener('touchmove', handleTouchMove, { passive: false })
  addDocumentListener('touchend', handleTouchEnd)
  addDocumentListener('touchcancel', handleTouchEnd)
}

const startZoomTouch = (event) => {
  if (!supportsTouch.value) return

  if (event.touches.length === 2) {
    event.preventDefault()
    const touch1 = event.touches[0]
    const touch2 = event.touches[1]
    const center = getTouchCenterPoint(touch1, touch2, event.currentTarget)
    const distance = getTouchDistance(touch1, touch2)
    touchPinchLastDistance.value = distance
    touchPinchLastCenterX.value = center.x
    touchPinchLastCenterY.value = center.y
    lastTouchDistance.value = distance
  } else if (event.touches.length === 1 && zoomLevel.value > 1) {
    isZoomDragging.value = true
    zoomDragStartX.value = event.touches[0].clientX
    zoomDragStartY.value = event.touches[0].clientY
    zoomDragStartPanX.value = panX.value
    zoomDragStartPanY.value = panY.value
  }
}

const handleZoomTouchMove = (event) => {
  if (!supportsTouch.value) return

  if (event.touches.length === 2) {
    event.preventDefault()
    const touch1 = event.touches[0]
    const touch2 = event.touches[1]
    const center = getTouchCenterPoint(touch1, touch2, event.currentTarget)
    const distance = getTouchDistance(touch1, touch2)
    applyPinchAtPoint(distance, center.x, center.y)
    lastTouchDistance.value = distance
  } else if (event.touches.length === 1 && zoomLevel.value > 1) {
    event.preventDefault()
    const touch = event.touches[0]
    if (!isZoomDragging.value) {
      isZoomDragging.value = true
      zoomDragStartX.value = touch.clientX
      zoomDragStartY.value = touch.clientY
      zoomDragStartPanX.value = panX.value
      zoomDragStartPanY.value = panY.value
      return
    }

    const deltaX = touch.clientX - zoomDragStartX.value
    const deltaY = touch.clientY - zoomDragStartY.value
    panX.value = zoomDragStartPanX.value + deltaX
    panY.value = zoomDragStartPanY.value + deltaY
  }
}

const endZoomTouch = () => {
  lastTouchDistance.value = 0
  isZoomDragging.value = false
  touchPinchLastDistance.value = 0
  touchPinchLastCenterX.value = 0
  touchPinchLastCenterY.value = 0
}

const handleZoomWheel = (event) => {
  if (!supportsTouch.value) return
  event.preventDefault()
  if (event.deltaY > 0) {
    zoomOut()
  } else {
    zoomIn()
  }
}

const handleDoubleClick = () => {
  if (!isMobile.value && zoomLevel.value > 1) {
    resetZoomState()
  }
}

const handleKeydown = (event) => {
  if (isMobile.value || totalPage.value <= 0 || loading.value || error.value) return

  const target = event.target
  const tagName = target?.tagName?.toLowerCase()
  const isEditable =
    tagName === 'input' ||
    tagName === 'textarea' ||
    target?.isContentEditable
  if (isEditable) return

  switch (event.key) {
    case 'ArrowLeft':
    case 'ArrowUp':
    case 'PageUp':
      event.preventDefault()
      prevPage()
      break
    case 'ArrowRight':
    case 'ArrowDown':
    case 'PageDown':
    case ' ':
      event.preventDefault()
      nextPage()
      break
    case 'Home':
      event.preventDefault()
      void jumpToPage(1, false, { reason: 'keyboard' })
      break
    case 'End':
      event.preventDefault()
      void jumpToPage(totalPage.value, false, { reason: 'keyboard' })
      break
    case 'm':
    case 'M':
      showMenu.value = !showMenu.value
      break
    case 'f':
    case 'F':
      event.preventDefault()
      void toggleFullscreen()
      break
    case '0':
      resetZoomState()
      break
    case '+':
    case '=':
      if (event.ctrlKey) {
        event.preventDefault()
        zoomIn()
      }
      break
    case '-':
      if (event.ctrlKey) {
        event.preventDefault()
        zoomOut()
      }
      break
    default:
      break
  }
}

const handleVisibilityChange = () => {
  if (getVisibilityState() === 'hidden') {
    flushProgressBeforeLeave()
  }
}

watch(() => route.params.id, async (newId, oldId) => {
  if (newId && newId !== oldId) {
    await loadImages()
  }
})

onMounted(() => {
  updateDeviceState()
  updateReaderViewport()
  void loadImages()

  if (readerContent.value) {
    readerContent.value.addEventListener('dblclick', handleDoubleClick)
  }

  addDocumentListener('fullscreenchange', handleFullscreenChange)
  addDocumentListener('visibilitychange', handleVisibilityChange)
  addWindowListener('resize', updateDeviceState)
  addWindowListener('resize', updateReaderViewport)
  addWindowListener('resize', alignToCurrentPageAfterViewportChange)
  addWindowListener('orientationchange', updateReaderViewport)
  addWindowListener('orientationchange', alignToCurrentPageAfterViewportChange)
  addWindowListener('keydown', handleKeydown)
  addWindowListener('pagehide', flushProgressBeforeLeave)
})

onUnmounted(() => {
  removeDocumentListener('mousemove', handleZoomDrag)
  removeDocumentListener('mouseup', endZoomDrag)
  removeDocumentListener('fullscreenchange', handleFullscreenChange)
  removeDocumentListener('visibilitychange', handleVisibilityChange)
  removeWindowListener('resize', updateDeviceState)
  removeWindowListener('resize', updateReaderViewport)
  removeWindowListener('resize', alignToCurrentPageAfterViewportChange)
  removeWindowListener('orientationchange', updateReaderViewport)
  removeWindowListener('orientationchange', alignToCurrentPageAfterViewportChange)
  removeWindowListener('keydown', handleKeydown)
  removeWindowListener('pagehide', flushProgressBeforeLeave)

  if (saveProgressTimer) {
    clearTimeout(saveProgressTimer)
  }
  if (scrollIdleTimer) {
    clearTimeout(scrollIdleTimer)
  }
  if (programmaticScrollTimer) {
    clearTimeout(programmaticScrollTimer)
  }
  if (resizeAlignTimer) {
    clearTimeout(resizeAlignTimer)
  }
  clearRestoreRetry()
  clearRestoreBootstrap()
  clearPanInertia()
  if (scrollRafId && Boolean(getWindow())) {
    cancelFrame(scrollRafId)
  }
  if (pageUpdateRafId && Boolean(getWindow())) {
    cancelFrame(pageUpdateRafId)
    pageUpdateRafId = 0
  }

  flushProgressBeforeLeave()

  if (readerContent.value) {
    readerContent.value.removeEventListener('dblclick', handleDoubleClick)
  }
})
</script>

<style scoped>
.comic-reader {
  min-height: 100vh;
  position: relative;
  background: #000;
  overflow: hidden;
}

.loading, .error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: #000;
}

.reader-content {
  height: var(--reader-vh, 100dvh);
  overflow: hidden;
  position: relative;
}

.reader-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1100;
}

.mode-switch {
  color: #fff;
  font-size: 14px;
  padding: 4px 12px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 16px;
  cursor: pointer;
  user-select: none;
}

.mode-switch:hover {
  background: rgba(255, 255, 255, 0.3);
}

.left-right-mode {
  display: flex;
  align-items: stretch;
  height: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
  will-change: scroll-position, transform;
}

.left-right-mode::-webkit-scrollbar {
  display: none;
}

.left-right-mode.single-page-mode {
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
}

.left-right-mode.single-page-mode .page-track-horizontal {
  width: max-content;
  min-width: 100%;
}

.left-right-mode.single-page-mode .page {
  flex: 0 0 100%;
  width: 100%;
  height: 100%;
}

.page-track {
  will-change: transform;
}

.page-track-horizontal {
  display: flex;
  align-items: center;
  min-height: 100%;
  width: max-content;
}

.page-track-vertical {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  min-height: 100%;
}

.page {
  flex: 0 0 auto;
  width: auto;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  margin: 0;
  padding: 0;
  flex-shrink: 0;
}

.page + .page {
  margin-left: -1px;
}

.comic-image {
  max-width: 100%;
  max-height: none;
  width: 100%;
  height: auto;
  object-fit: cover;
  display: block;
  user-select: none;
  -webkit-user-drag: none;
  cursor: grab;
  image-rendering: -webkit-optimize-quality;
  image-rendering: high-quality;
}

.left-right-mode .comic-image {
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.up-down-mode .comic-image {
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: var(--reader-vh, 100dvh);
  object-fit: contain;
  margin: 0 auto;
}

.comic-image:active {
  cursor: grabbing;
}

.up-down-mode {
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
  will-change: scroll-position, transform;
}

.up-down-mode::-webkit-scrollbar {
  display: none;
}

.up-down-mode.single-page-mode {
  scroll-snap-type: y mandatory;
  scroll-behavior: smooth;
}

.up-down-mode.single-page-mode .page-track-vertical {
  min-height: 100%;
}

.up-down-mode.single-page-mode .up-down-page {
  min-height: 100%;
  height: 100%;
  align-items: center;
  justify-content: center;
}

.up-down-page {
  width: 100%;
  height: auto;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  background: #000;
  margin: 0;
  padding: 0;
  line-height: 0;
  font-size: 0;
  border: none;
  outline: none;
}

.up-down-page + .up-down-page {
  margin-top: -1px;
}

.left-right-mode.single-page-mode .page,
.up-down-mode.single-page-mode .up-down-page {
  scroll-snap-align: center;
  scroll-snap-stop: always;
}

.left-right-mode.single-page-mode .page + .page,
.up-down-mode.single-page-mode .up-down-page + .up-down-page {
  margin: 0;
}

.left-right-mode.single-page-mode .comic-image,
.up-down-mode.single-page-mode .comic-image {
  margin: 0 auto;
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
}

/* 手机端缩放覆盖层 */
.zoom-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  overflow: hidden;
  touch-action: none;
}

.zoom-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  transition: transform 0.1s ease;
  user-select: none;
  -webkit-user-drag: none;
}

.zoom-close {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 40px;
  height: 40px;
  background: rgba(0, 0, 0, 0.6);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  cursor: pointer;
  z-index: 101;
}

.zoom-info {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  padding: 5px 15px;
  border-radius: 15px;
  font-size: 14px;
  z-index: 101;
}

/* 电脑端缩放提示 */
.desktop-zoom-info {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  padding: 8px 20px;
  border-radius: 20px;
  font-size: 14px;
  z-index: 100;
  pointer-events: none;
}

.control-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(0, 0, 0, 0.9);
  color: #fff;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 1000;
}

.progress-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.page-indicator {
  text-align: center;
  font-size: 14px;
  font-weight: 500;
}

.progress-slider-container {
  width: 100%;
  padding: 0 5px;
}

.progress-slider {
  width: 100%;
  height: 24px;
  -webkit-appearance: none;
  appearance: none;
  background: transparent;
  cursor: pointer;
}

.progress-slider::-webkit-slider-runnable-track {
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 2px;
}

.progress-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  background: #1989fa;
  border-radius: 50%;
  margin-top: -8px;
  cursor: pointer;
}

.progress-slider::-moz-range-track {
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 2px;
}

.progress-slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  background: #1989fa;
  border-radius: 50%;
  cursor: pointer;
  border: none;
}

.progress-bar {
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #1989fa;
  border-radius: 2px;
  transition: width 0.1s ease;
}

.actions {
  display: flex;
  justify-content: center;
  gap: 10px;
}

.mode-btn {
  min-width: 60px;
}

@media (max-width: 768px) {
  .actions {
    gap: 6px;
  }
  
  .actions .van-button {
    padding: 0 8px;
    font-size: 12px;
  }
}
</style>


