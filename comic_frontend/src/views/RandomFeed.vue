<template>
  <div class="random-feed-page">
    <section class="feed-toolbar">
      <div class="feed-title-group">
        <h1 class="feed-title">{{ isVideoMode ? '视频随机流' : '漫画随机流' }}</h1>
        <p class="feed-subtitle">本地库 + 已缓存预览库，随机序列可重复、可无限下滑</p>
        <p v-show="!controlsVisible" class="feed-toolbar-hint">点击当前图片显示操作按钮</p>
      </div>
      <div v-show="controlsVisible && !!currentItem" class="feed-toolbar-actions">
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
          :disabled="!currentItem"
          @click="goToDetail"
        >
          查看详情
        </van-button>
      </div>
    </section>

    <section class="feed-status">
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
          @dblclick.prevent="toggleZoom(index)"
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

const feedScroller = ref(null)
const activeIndex = ref(0)
const refreshing = ref(false)
const loadingTailPromise = ref(null)
const controlsVisible = ref(false)
const preloadCache = new Set()

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
    cursor: zoomState.scale > 1 ? 'grab' : 'default'
  }
}

function getCardHeight() {
  const scroller = feedScroller.value
  if (!scroller) return 0
  return Math.max(1, scroller.clientHeight)
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
  if (!item?.detail_route_name || !item?.detail_id) {
    return
  }
  router.push({
    name: item.detail_route_name,
    params: { id: item.detail_id }
  })
}

function handleScroll() {
  updateActiveIndexByScroll()
}

function handleImageTap(index) {
  if (index !== activeIndex.value) return
  controlsVisible.value = !controlsVisible.value
}

function isOverlayVisible(index) {
  return controlsVisible.value && index === activeIndex.value
}

function toggleZoom(index) {
  if (index !== activeIndex.value) return
  if (zoomState.scale <= 1) {
    zoomState.scale = 2
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
    const nextScale = clampZoom(zoomState.scale * factor)
    zoomState.scale = nextScale
    if (nextScale <= 1) {
      zoomState.x = 0
      zoomState.y = 0
    }
    return
  }

  if (zoomState.scale > 1) {
    zoomState.x -= event.deltaX
    zoomState.y -= event.deltaY
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
  zoomState.x = zoomState.startX + (event.clientX - zoomState.mouseStartX)
  zoomState.y = zoomState.startY + (event.clientY - zoomState.mouseStartY)
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
    const nextDistance = getTouchDistance(event.touches[0], event.touches[1])
    if (zoomState.pinchDistance > 0) {
      const ratio = nextDistance / zoomState.pinchDistance
      zoomState.scale = clampZoom(zoomState.scale * ratio)
    }
    zoomState.pinchDistance = nextDistance
    return
  }

  if (event.touches.length === 1 && zoomState.touchDragging && zoomState.scale > 1) {
    const touch = event.touches[0]
    zoomState.x = zoomState.startX + (touch.clientX - zoomState.mouseStartX)
    zoomState.y = zoomState.startY + (touch.clientY - zoomState.mouseStartY)
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
  updateViewportHeightCssVar('--reader-vh')
}

watch(modeKey, async () => {
  activeIndex.value = 0
  controlsVisible.value = false
  resetZoom()
  preloadCache.clear()
  await ensureRandomData()
  await nextTick()
  if (feedScroller.value) {
    feedScroller.value.scrollTop = 0
  }
})

watch(
  () => activeIndex.value,
  async (index, previous) => {
    if (index !== previous) {
      controlsVisible.value = false
      resetZoom()
    }
    preloadAround(index)
    if (index >= items.value.length - 4) {
      await loadMore()
    }
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
  await ensureRandomData()
})

onUnmounted(() => {
  removeWindowListener('resize', handleResize)
  removeDocumentListener('mousemove', onMouseMove)
  removeDocumentListener('mouseup', stopMouseDrag)
})
</script>

<style scoped>
.random-feed-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 6px;
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
  height: calc(var(--reader-vh, 100vh) - 132px);
  min-height: 500px;
  overflow-y: auto;
  scroll-snap-type: y mandatory;
  border-radius: 16px;
}

.feed-card {
  position: relative;
  height: calc(var(--reader-vh, 100vh) - 132px);
  min-height: 500px;
  scroll-snap-align: start;
  border-radius: 16px;
  overflow: hidden;
  background:
    radial-gradient(circle at 20% 20%, rgba(25, 137, 250, 0.2), transparent 50%),
    radial-gradient(circle at 80% 80%, rgba(255, 159, 0, 0.18), transparent 45%),
    var(--surface-1);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.25);
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

  .feed-scroller,
  .feed-card {
    height: calc(var(--reader-vh, 100vh) - 172px);
    min-height: 420px;
  }
}
</style>
