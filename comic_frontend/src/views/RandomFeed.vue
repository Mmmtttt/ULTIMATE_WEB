<template>
  <div class="random-feed-page" :style="pageStyle">
    <section v-show="controlsVisible" class="feed-toolbar">
      <div class="feed-title-group">
        <h1 class="feed-title">{{ isVideoMode ? '视频随机流' : '漫画随机流' }}</h1>
        <p class="feed-subtitle">本地库 + 已缓存预览库，随机序列可重复、可无限下滑</p>
        <p class="feed-toolbar-hint">点击当前图片显示操作按钮</p>
      </div>
      <div class="feed-toolbar-actions">
        <van-button
          size="small"
          plain
          data-testid="random-feed-refresh"
          :loading="refreshing"
          @click="handleRefresh"
        >
          刷新序列
        </van-button>
        <van-button
          size="small"
          type="primary"
          data-testid="random-feed-detail"
          :disabled="!controlItem"
          @click.stop="goToDetail(controlItem)"
        >
          查看详情
        </van-button>
      </div>
    </section>

    <section v-show="controlsVisible" class="feed-status">
      <span v-if="currentItem">第 {{ activeIndex + 1 }} 项 / 无限序列</span>
      <span v-else>等待加载随机内容…</span>
      <span class="mode-chip">{{ isVideoMode ? '视频模式' : '漫画模式' }}</span>
    </section>

    <section
      ref="feedScroller"
      class="feed-scroller"
      data-testid="random-feed-scroller"
      @scroll.passive="handleScroll"
    >
      <article
        v-for="(item, index) in items"
        :key="`${item.content_id}-${item.source}-${index}`"
        class="feed-card"
        data-testid="random-feed-card"
      >
        <div
          class="feed-image-shell"
          @click="handleImageTap(index)"
          @wheel="handleWheel($event, index)"
          @touchstart="handleTouchStart($event, index)"
          @touchmove="handleTouchMove($event, index)"
          @touchend="handleTouchEnd($event, index)"
          @touchcancel="handleTouchEnd($event, index)"
          @mousedown.prevent="startMouseDrag($event, index)"
        >
          <img
            class="feed-image"
            draggable="false"
            :src="toDisplayUrl(item.image_url)"
            :alt="item.title || item.content_id"
            :style="getImageStyle(index)"
            loading="lazy"
          />
          <div v-if="index === activeIndex && !controlsVisible" class="feed-image-tap-hint">
            点击图片显示操作
          </div>
        </div>

        <div v-show="isOverlayVisible(index)" class="feed-overlay">
          <div class="feed-meta-row">
            <span class="feed-source">{{ item.source === 'preview' ? '预览缓存' : '本地库' }}</span>
            <span v-if="item.page_num" class="feed-page">页码 {{ item.page_num }}</span>
          </div>
          <h2 class="feed-item-title">{{ item.title || item.content_id }}</h2>
          <p class="feed-item-author">{{ item.author || '未知作者' }}</p>
          <p class="feed-gesture-hint">
            双击或 Ctrl+滚轮缩放；缩放后可拖拽。
          </p>
          <van-button
            size="small"
            type="primary"
            block
            class="detail-button"
            data-testid="random-feed-card-detail"
            @click.stop="goToDetail(item)"
          >
            查看详情
          </van-button>
        </div>
      </article>

      <div v-if="loadingMore" class="tail-loading">
        <van-loading size="20px" />
        <span>继续加载随机内容…</span>
      </div>
      <div v-else-if="!items.length && loading" class="tail-loading">
        <van-loading size="20px" />
        <span>初始化随机序列…</span>
      </div>
      <div v-else-if="errorText" class="tail-error">{{ errorText }}</div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showFailToast } from 'vant'
import { imageApi } from '@/api'
import { useModeStore, useRandomFeedStore } from '@/stores'
import { updateViewportHeightCssVar } from '@/composables/readerShared'
import { addDocumentListener, addWindowListener, removeDocumentListener, removeWindowListener } from '@/runtime/browser'
import { toBackendUrl } from '@/utils/url'

const router = useRouter()
const modeStore = useModeStore()
const randomFeedStore = useRandomFeedStore()
const VIEW_STATE_KEY = 'random_feed_view_state_v1'

const feedScroller = ref(null)
const activeIndex = ref(0)
const refreshing = ref(false)
const loadingTailPromise = ref(null)
const controlsVisible = ref(false)
const controlIndex = ref(0)
const scrollerHeight = ref(0)
const restoringViewState = ref(false)
const suppressScrollSync = ref(false)
const layoutAnchorIndex = ref(null)
const preloadCache = new Set()
let releaseScrollSyncRaf = 0

const zoomState = reactive({
  scale: 1,
  x: 0,
  y: 0,
  mouseDragging: false,
  mouseStartX: 0,
  mouseStartY: 0,
  startX: 0,
  startY: 0,
  touchDragging: false,
  pinchDistance: 0
})

const isVideoMode = computed(() => modeStore.isVideoMode)
const modeKey = computed(() => (isVideoMode.value ? 'video' : 'comic'))
const modeState = computed(() => randomFeedStore.getState(modeKey.value))
const items = computed(() => modeState.value.items || [])
const loading = computed(() => modeState.value.loading)
const loadingMore = computed(() => modeState.value.loadingMore)
const errorText = computed(() => modeState.value.error || '')
const currentItem = computed(() => items.value[activeIndex.value] || null)
const controlItem = computed(() => items.value[controlIndex.value] || currentItem.value || null)
const pageStyle = computed(() => {
  if (!scrollerHeight.value) return {}
  return {
    '--feed-card-height': `${scrollerHeight.value}px`
  }
})

function resetZoom() {
  zoomState.scale = 1
  zoomState.x = 0
  zoomState.y = 0
  zoomState.mouseDragging = false
  zoomState.touchDragging = false
  zoomState.pinchDistance = 0
}

function clampZoom(scale) {
  return Math.max(1, Math.min(5, Number(scale || 1)))
}

function clampIndex(index) {
  if (!items.value.length) return 0
  return Math.max(0, Math.min(items.value.length - 1, Number(index) || 0))
}

function getZoomViewportRect() {
  const scroller = feedScroller.value
  if (!scroller || typeof scroller.getBoundingClientRect !== 'function') return null
  const rect = scroller.getBoundingClientRect()
  const width = Math.max(1, Number(scroller.clientWidth) || Math.round(rect.width) || 1)
  const height = Math.max(1, getCardHeight() || Math.round(rect.height) || 1)
  return {
    left: rect.left,
    top: rect.top,
    width,
    height
  }
}

function clampPan(nextX, nextY, scale = zoomState.scale) {
  if (!Number.isFinite(scale) || scale <= 1) {
    return { x: 0, y: 0 }
  }
  const viewport = getZoomViewportRect()
  if (!viewport) {
    return {
      x: Number.isFinite(nextX) ? nextX : 0,
      y: Number.isFinite(nextY) ? nextY : 0
    }
  }
  const maxX = Math.max(0, (viewport.width * (scale - 1)) / 2)
  const maxY = Math.max(0, (viewport.height * (scale - 1)) / 2)
  const safeX = Number.isFinite(nextX) ? nextX : 0
  const safeY = Number.isFinite(nextY) ? nextY : 0
  return {
    x: Math.max(-maxX, Math.min(maxX, safeX)),
    y: Math.max(-maxY, Math.min(maxY, safeY))
  }
}

function applyPan(nextX, nextY, scale = zoomState.scale) {
  const clamped = clampPan(nextX, nextY, scale)
  zoomState.x = clamped.x
  zoomState.y = clamped.y
}

function zoomAtClientPoint(nextScaleRaw, clientX, clientY) {
  const prevScale = Number(zoomState.scale) || 1
  const nextScale = clampZoom(nextScaleRaw)

  if (!Number.isFinite(prevScale) || prevScale <= 0) {
    zoomState.scale = nextScale
    if (nextScale <= 1) {
      applyPan(0, 0, 1)
    } else {
      applyPan(zoomState.x, zoomState.y, nextScale)
    }
    return
  }

  if (Math.abs(nextScale - prevScale) < 0.0001) return

  if (nextScale <= 1) {
    zoomState.scale = 1
    applyPan(0, 0, 1)
    return
  }

  const viewport = getZoomViewportRect()
  if (!viewport) {
    zoomState.scale = nextScale
    applyPan(zoomState.x, zoomState.y, nextScale)
    return
  }

  const originX = viewport.width / 2
  const originY = viewport.height / 2
  const fallbackClientX = viewport.left + originX
  const fallbackClientY = viewport.top + originY
  const safeClientX = Number.isFinite(clientX) ? clientX : fallbackClientX
  const safeClientY = Number.isFinite(clientY) ? clientY : fallbackClientY
  const localX = Math.max(0, Math.min(viewport.width, safeClientX - viewport.left))
  const localY = Math.max(0, Math.min(viewport.height, safeClientY - viewport.top))
  const anchorX = localX - originX
  const anchorY = localY - originY
  const ratio = nextScale / prevScale
  const nextX = anchorX - (anchorX - zoomState.x) * ratio
  const nextY = anchorY - (anchorY - zoomState.y) * ratio

  zoomState.scale = nextScale
  applyPan(nextX, nextY, nextScale)
}

function readViewState() {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.sessionStorage.getItem(VIEW_STATE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    return parsed
  } catch (_error) {
    return null
  }
}

function hasStoredViewStateForMode(targetMode = modeKey.value) {
  const state = readViewState()
  if (!state) return false
  return String(state.mode || '') === String(targetMode || '')
}

function saveViewState() {
  if (typeof window === 'undefined') return
  const scroller = feedScroller.value
  if (!scroller) return
  if (restoringViewState.value) return
  try {
    const payload = {
      mode: modeKey.value,
      activeIndex: activeIndex.value,
      controlIndex: controlIndex.value,
      controlsVisible: controlsVisible.value,
      updatedAt: Date.now()
    }
    window.sessionStorage.setItem(VIEW_STATE_KEY, JSON.stringify(payload))
  } catch (_error) {
    // ignore storage failure
  }
}

async function applyStoredViewState() {
  const state = readViewState()
  if (!state || String(state.mode || '') !== modeKey.value) {
    return false
  }
  if (!items.value.length) {
    return false
  }

  const nextActive = Math.max(0, Math.min(items.value.length - 1, Number(state.activeIndex) || 0))
  const nextControl = Math.max(0, Math.min(items.value.length - 1, Number(state.controlIndex) || nextActive))

  activeIndex.value = nextActive
  controlIndex.value = nextControl
  controlsVisible.value = Boolean(state.controlsVisible)

  await nextTick()
  updateScrollerHeight()
  await nextTick()

  const scroller = feedScroller.value
  if (!scroller) return true
  const targetTop = nextActive * getCardHeight()
  const maxTop = Math.max(0, scroller.scrollHeight - scroller.clientHeight)
  scroller.scrollTop = Math.min(maxTop, Math.max(0, targetTop))
  updateActiveIndexByScroll()
  return true
}

function toDisplayUrl(rawUrl) {
  const text = String(rawUrl || '').trim()
  if (!text) return ''
  if (
    text.startsWith('http://') ||
    text.startsWith('https://') ||
    text.startsWith('data:') ||
    text.startsWith('blob:')
  ) {
    return text
  }
  if (text.startsWith('/')) {
    return toBackendUrl(text)
  }
  return toBackendUrl(`/${text}`)
}

function getImageStyle(index) {
  if (index !== activeIndex.value) {
    return {
      transform: 'translate3d(0, 0, 0) scale(1)'
    }
  }
  return {
    transform: `translate3d(${zoomState.x}px, ${zoomState.y}px, 0) scale(${zoomState.scale})`,
    cursor: zoomState.scale > 1 && (zoomState.mouseDragging || zoomState.touchDragging) ? 'grabbing' : zoomState.scale > 1 ? 'grab' : 'default'
  }
}

function getCardHeight() {
  const scroller = feedScroller.value
  if (!scroller) return 0
  return Math.max(1, scroller.clientHeight)
}

function alignScrollerToIndex(index) {
  const scroller = feedScroller.value
  if (!scroller || !items.value.length) return
  const cardHeight = getCardHeight()
  if (!Number.isFinite(cardHeight) || cardHeight <= 0) return
  const targetTop = clampIndex(index) * cardHeight
  const maxTop = Math.max(0, scroller.scrollHeight - scroller.clientHeight)
  const nextTop = Math.min(maxTop, Math.max(0, targetTop))
  if (Math.abs(scroller.scrollTop - nextTop) > 1) {
    scroller.scrollTop = nextTop
  }
}

function scheduleReleaseScrollSync() {
  if (releaseScrollSyncRaf && typeof window !== 'undefined') {
    window.cancelAnimationFrame(releaseScrollSyncRaf)
  }
  if (typeof window === 'undefined') {
    suppressScrollSync.value = false
    return
  }
  releaseScrollSyncRaf = window.requestAnimationFrame(() => {
    suppressScrollSync.value = false
    releaseScrollSyncRaf = 0
  })
}

function updateActiveIndexByScroll() {
  const scroller = feedScroller.value
  if (!scroller || !items.value.length) return
  const cardHeight = getCardHeight()
  const next = Math.round(scroller.scrollTop / cardHeight)
  const clamped = Math.max(0, Math.min(items.value.length - 1, next))
  if (clamped !== activeIndex.value) {
    activeIndex.value = clamped
  }
}

async function ensureRandomData() {
  try {
    await randomFeedStore.ensureSession(modeKey.value)
    if (!items.value.length) {
      await loadMore()
    }
  } catch (error) {
    showFailToast(error?.message || '初始化随机流失败')
  }
}

async function loadMore() {
  if (loadingTailPromise.value) {
    return loadingTailPromise.value
  }
  loadingTailPromise.value = randomFeedStore
    .loadMore(modeKey.value, 18)
    .catch((error) => {
      showFailToast(error?.message || '加载随机流失败')
      return []
    })
    .finally(() => {
      loadingTailPromise.value = null
    })
  return loadingTailPromise.value
}

function preloadAround(index) {
  if (!items.value.length) return
  const upper = Math.min(items.value.length - 1, index + 4)
  const lower = Math.max(0, index)
  for (let cursor = lower; cursor <= upper; cursor += 1) {
    const item = items.value[cursor]
    if (!item?.image_url) continue
    const resolved = toDisplayUrl(item.image_url)
    if (!resolved || preloadCache.has(resolved)) continue
    preloadCache.add(resolved)
    imageApi.preload(resolved).catch(() => {})
  }
}

async function handleRefresh() {
  refreshing.value = true
  try {
    await randomFeedStore.refreshSequence(modeKey.value)
    await loadMore()
    activeIndex.value = 0
    controlsVisible.value = false
    resetZoom()
    await nextTick()
    if (feedScroller.value) {
      feedScroller.value.scrollTop = 0
    }
  } catch (error) {
    showFailToast(error?.message || '刷新序列失败')
  } finally {
    refreshing.value = false
  }
}

function goToDetail(item = currentItem.value) {
  const target = item || currentItem.value
  if (!target?.detail_route_name || !target?.detail_id) {
    showFailToast('当前推荐项暂不支持跳转详情')
    return
  }
  saveViewState()
  router.push({
    name: target.detail_route_name,
    params: { id: target.detail_id }
  })
}

function handleScroll() {
  if (suppressScrollSync.value) return
  updateActiveIndexByScroll()
  saveViewState()
}

function handleImageTap(index) {
  if (index !== activeIndex.value) {
    const shouldToggleControls = controlsVisible.value !== true
    if (shouldToggleControls) {
      suppressScrollSync.value = true
      layoutAnchorIndex.value = index
    }
    activeIndex.value = index
    controlIndex.value = index
    controlsVisible.value = true
    return
  }
  controlIndex.value = index
  layoutAnchorIndex.value = index
  suppressScrollSync.value = true
  controlsVisible.value = !controlsVisible.value
}

function isOverlayVisible(index) {
  return controlsVisible.value && index === activeIndex.value
}

function toggleZoom(event, index) {
  if (index !== activeIndex.value) return
  if (zoomState.scale <= 1) {
    zoomAtClientPoint(2, event?.clientX, event?.clientY)
  } else {
    resetZoom()
  }
}

function handleWheel(event, index) {
  if (index !== activeIndex.value) return

  if (!event.ctrlKey && zoomState.scale <= 1) {
    return
  }
  event.preventDefault()

  if (event.ctrlKey) {
    const factor = event.deltaY > 0 ? 0.9 : 1.1
    zoomAtClientPoint(zoomState.scale * factor, event.clientX, event.clientY)
    return
  }

  if (zoomState.scale > 1) {
    applyPan(zoomState.x - event.deltaX, zoomState.y - event.deltaY)
  }
}

function startMouseDrag(event, index) {
  if (index !== activeIndex.value || zoomState.scale <= 1) return
  zoomState.mouseDragging = true
  zoomState.mouseStartX = event.clientX
  zoomState.mouseStartY = event.clientY
  zoomState.startX = zoomState.x
  zoomState.startY = zoomState.y
}

function onMouseMove(event) {
  if (!zoomState.mouseDragging) return
  applyPan(
    zoomState.startX + (event.clientX - zoomState.mouseStartX),
    zoomState.startY + (event.clientY - zoomState.mouseStartY)
  )
}

function stopMouseDrag() {
  zoomState.mouseDragging = false
}

function getTouchDistance(touchA, touchB) {
  return Math.hypot(touchB.clientX - touchA.clientX, touchB.clientY - touchA.clientY)
}

function handleTouchStart(event, index) {
  if (index !== activeIndex.value) return
  if (event.touches.length === 2) {
    zoomState.pinchDistance = getTouchDistance(event.touches[0], event.touches[1])
    zoomState.touchDragging = false
    return
  }
  if (event.touches.length === 1 && zoomState.scale > 1) {
    zoomState.touchDragging = true
    zoomState.mouseStartX = event.touches[0].clientX
    zoomState.mouseStartY = event.touches[0].clientY
    zoomState.startX = zoomState.x
    zoomState.startY = zoomState.y
  }
}

function handleTouchMove(event, index) {
  if (index !== activeIndex.value) return

  if (event.touches.length === 2) {
    event.preventDefault()
    const nextDistance = getTouchDistance(event.touches[0], event.touches[1])
    if (zoomState.pinchDistance > 0) {
      const ratio = nextDistance / zoomState.pinchDistance
      const centerX = (event.touches[0].clientX + event.touches[1].clientX) / 2
      const centerY = (event.touches[0].clientY + event.touches[1].clientY) / 2
      zoomAtClientPoint(zoomState.scale * ratio, centerX, centerY)
    }
    zoomState.pinchDistance = nextDistance
    return
  }

  if (event.touches.length === 1 && zoomState.touchDragging && zoomState.scale > 1) {
    event.preventDefault()
    const touch = event.touches[0]
    applyPan(
      zoomState.startX + (touch.clientX - zoomState.mouseStartX),
      zoomState.startY + (touch.clientY - zoomState.mouseStartY)
    )
  }
}

function handleTouchEnd() {
  if (zoomState.scale <= 1) {
    resetZoom()
    return
  }
  zoomState.touchDragging = false
  zoomState.pinchDistance = 0
}

function handleResize() {
  const anchorIndex = clampIndex(activeIndex.value)
  suppressScrollSync.value = true
  updateViewportHeightCssVar('--reader-vh')
  updateScrollerHeight()
  activeIndex.value = anchorIndex
  controlIndex.value = anchorIndex
  alignScrollerToIndex(anchorIndex)
  scheduleReleaseScrollSync()
}

function updateScrollerHeight() {
  const scroller = feedScroller.value
  if (!scroller || typeof window === 'undefined') return

  const rect = scroller.getBoundingClientRect()
  const nextHeight = Math.max(1, rect.height)
  if (!Number.isFinite(nextHeight)) return
  if (Math.abs(nextHeight - scrollerHeight.value) < 0.5) return
  scrollerHeight.value = nextHeight
  if (zoomState.scale > 1) {
    applyPan(zoomState.x, zoomState.y, zoomState.scale)
  }
}

watch(modeKey, async () => {
  const shouldRestore = hasStoredViewStateForMode(modeKey.value)
  restoringViewState.value = true
  activeIndex.value = 0
  controlIndex.value = 0
  controlsVisible.value = false
  resetZoom()
  preloadCache.clear()
  await ensureRandomData()
  await nextTick()
  if (feedScroller.value && !shouldRestore) {
    feedScroller.value.scrollTop = 0
  }
  updateScrollerHeight()
  if (shouldRestore) {
    await applyStoredViewState()
  }
  restoringViewState.value = false
})

watch(
  () => activeIndex.value,
  async (index, previous) => {
    if (index !== previous && !restoringViewState.value) {
      controlIndex.value = index
      controlsVisible.value = false
      resetZoom()
    }
    preloadAround(index)
    if (index >= items.value.length - 4) {
      await loadMore()
    }
    saveViewState()
  }
)

watch(
  () => items.value.length,
  (length) => {
    if (!length) return
    if (activeIndex.value >= length) {
      activeIndex.value = length - 1
    }
    preloadAround(activeIndex.value)
  }
)

onMounted(async () => {
  updateViewportHeightCssVar('--reader-vh')
  addWindowListener('resize', handleResize)
  addDocumentListener('mousemove', onMouseMove)
  addDocumentListener('mouseup', stopMouseDrag)
  restoringViewState.value = true
  await ensureRandomData()
  await nextTick()
  updateScrollerHeight()
  if (hasStoredViewStateForMode(modeKey.value)) {
    await applyStoredViewState()
  }
  restoringViewState.value = false
})

onUnmounted(() => {
  saveViewState()
  if (releaseScrollSyncRaf && typeof window !== 'undefined') {
    window.cancelAnimationFrame(releaseScrollSyncRaf)
    releaseScrollSyncRaf = 0
  }
  removeWindowListener('resize', handleResize)
  removeDocumentListener('mousemove', onMouseMove)
  removeDocumentListener('mouseup', stopMouseDrag)
})

watch(
  () => controlsVisible.value,
  async () => {
    await nextTick()
    updateScrollerHeight()
    if (restoringViewState.value) return
    const anchorIndex = clampIndex(layoutAnchorIndex.value ?? activeIndex.value)
    suppressScrollSync.value = true
    activeIndex.value = anchorIndex
    controlIndex.value = anchorIndex
    alignScrollerToIndex(anchorIndex)
    layoutAnchorIndex.value = null
    scheduleReleaseScrollSync()
    saveViewState()
  }
)
</script>

<style scoped>
.random-feed-page {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
  overflow: hidden;
}

.feed-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 8px 0;
}

.feed-title-group {
  min-width: 0;
}

.feed-title {
  margin: 0;
  font-size: 21px;
  line-height: 1.2;
  color: var(--text-strong);
  letter-spacing: 0.01em;
}

.feed-subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-tertiary);
}

.feed-toolbar-hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.feed-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.feed-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 0 8px;
  font-size: 11px;
  color: var(--text-secondary);
}

.mode-chip {
  border: 1px solid var(--border-soft);
  border-radius: 999px;
  padding: 2px 10px;
  color: var(--text-secondary);
  background: var(--surface-2);
}

.feed-scroller {
  flex: 1;
  min-height: 0;
  height: var(--feed-card-height, 100%);
  overflow-y: auto;
  overflow-anchor: none;
  scroll-snap-type: y mandatory;
  border-radius: 0;
}

.feed-card {
  position: relative;
  height: var(--feed-card-height, 100%);
  min-height: 0;
  scroll-snap-align: start;
  border-radius: 0;
  overflow: hidden;
  background:
    radial-gradient(circle at 20% 20%, rgba(25, 137, 250, 0.2), transparent 50%),
    radial-gradient(circle at 80% 80%, rgba(255, 159, 0, 0.18), transparent 45%),
    var(--surface-1);
  box-shadow: none;
}

.feed-image-shell {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  cursor: pointer;
}

.feed-image-tap-hint {
  position: absolute;
  right: 14px;
  bottom: 14px;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 11px;
  color: #f5f7fa;
  background: rgba(12, 24, 42, 0.68);
  border: 1px solid rgba(255, 255, 255, 0.28);
  pointer-events: none;
}

.feed-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  transform-origin: center center;
  transition: transform 0.16s ease;
  will-change: transform;
  user-select: none;
}

.feed-overlay {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 14px;
  background: linear-gradient(180deg, rgba(2, 8, 18, 0) 0%, rgba(2, 8, 18, 0.86) 46%, rgba(2, 8, 18, 0.96) 100%);
  color: #f3f5f8;
}

.feed-meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  opacity: 0.95;
}

.feed-source,
.feed-page {
  border: 1px solid rgba(255, 255, 255, 0.28);
  border-radius: 999px;
  padding: 2px 8px;
}

.feed-item-title {
  margin: 10px 0 4px;
  font-size: 17px;
  line-height: 1.3;
  color: #fff;
  word-break: break-word;
}

.feed-item-author {
  margin: 0;
  font-size: 13px;
  opacity: 0.9;
}

.feed-gesture-hint {
  margin: 8px 0 10px;
  font-size: 12px;
  opacity: 0.8;
}

.detail-button {
  --van-button-primary-background: #1f6bff;
  --van-button-primary-border-color: #1f6bff;
}

.tail-loading,
.tail-error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  color: var(--text-secondary);
  font-size: 12px;
}

.tail-error {
  color: var(--danger-500, #f56c6c);
}

@media (max-width: 1023px) {
  .feed-toolbar {
    padding: 8px 10px 0;
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .feed-toolbar-actions {
    width: 100%;
    justify-content: space-between;
  }

  .feed-overlay {
    padding-bottom: calc(14px + env(safe-area-inset-bottom, 0px) + 64px);
  }
}
</style>
