<template>
  <div class="comic-reader-base" :style="{ background: background }">
    <!-- 顶部导航栏 -->
    <van-nav-bar
      v-show="showMenu"
      title=""
      left-text="返回"
      left-arrow
      @click-left="handleBack"
      :style="{ background: 'transparent' }"
    >
      <template #right>
        <span class="mode-switch" @click="togglePageMode">
          {{ pageMode === 'left_right' ? '左右' : '上下' }}
        </span>
      </template>
    </van-nav-bar>

    <!-- 加载中 -->
    <div v-if="loading" class="loading">
      <van-loading type="spinner" color="#fff" />
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error">
      <van-empty description="加载失败" />
      <van-button type="primary" @click="reloadImages">重试</van-button>
    </div>

    <!-- 阅读内容 -->
    <div v-else class="reader-content" ref="readerContent">
      <!-- 左右翻页模式 -->
      <div
        v-if="pageMode === 'left_right'"
        class="left-right-mode"
        ref="leftRightContainer"
        :style="getContainerStyle"
        @scroll="handleScroll"
        @wheel="handleWheel"
      >
        <div
          v-for="(image, index) in images"
          :key="index"
          class="page"
        >
          <img
            :src="getImageSrc(index)"
            class="comic-image"
            :class="{ 'loading': !loadedPages.has(index + 1) }"
            decoding="async"
            draggable="false"
            @click="handleImageClick"
            @mousedown="startDrag($event, index)"
            @touchstart="startTouchDrag($event, index)"
            @load="onImageLoad(index + 1)"
            @error="onImageError(index + 1)"
          />
        </div>
      </div>

      <!-- 上下翻页模式 -->
      <div
        v-else
        class="up-down-mode"
        ref="upDownContainer"
        :style="getContainerStyle"
        @scroll="handleScroll"
        @wheel="handleWheel"
      >
        <div
          v-for="(image, index) in images"
          :key="index"
          class="up-down-page"
        >
          <img
            :src="getImageSrc(index)"
            class="comic-image"
            :class="{ 'loading': !loadedPages.has(index + 1) }"
            decoding="async"
            draggable="false"
            @click="handleImageClick"
            @mousedown="startDrag($event, index)"
            @touchstart="startTouchDrag($event, index)"
            @load="onImageLoad(index + 1)"
            @error="onImageError(index + 1)"
          />
        </div>
      </div>

      <!-- 手机端缩放模式 -->
      <div
        v-if="isMobile && isZoomMode"
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

    <!-- 点击区域（用于显示/隐藏菜单） -->
    <div class="tap-zones" v-show="!isZoomMode">
      <div class="tap-zone tap-left" @click="handleTapLeft"></div>
      <div class="tap-zone tap-center" @click="handleTapCenter"></div>
      <div class="tap-zone tap-right" @click="handleTapRight"></div>
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
        <van-button v-if="isMobile" size="small" @click="enterZoomMode">缩放</van-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useConfigStore } from '@/stores'

const props = defineProps({
  // 漫画ID
  comicId: {
    type: String,
    required: true
  },
  // 总页数
  totalPages: {
    type: Number,
    required: true
  },
  // 当前页码（从外部传入的初始值）
  initialPage: {
    type: Number,
    default: 1
  },
  // 图片列表
  images: {
    type: Array,
    required: true
  },
  // 背景颜色
  background: {
    type: String,
    default: '#000'
  },
  // 是否正在加载
  loading: {
    type: Boolean,
    default: false
  },
  // 是否出错
  error: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits([
  'update:currentPage',
  'saveProgress',
  'reload',
  'back'
])

const router = useRouter()
const configStore = useConfigStore()

// ============ State ============
const currentPage = ref(props.initialPage)
const showMenu = ref(false)
const loadedPages = ref(new Set())
const loadingPages = ref(new Set())
const loadQueue = ref([])
let isProcessingQueue = false

// 翻页模式
const pageMode = computed(() => configStore.pageMode)

// 容器引用
const leftRightContainer = ref(null)
const upDownContainer = ref(null)
const readerContent = ref(null)

// 滑块页码
const sliderPage = ref(currentPage.value)

// 缩放相关
const isZoomMode = ref(false)
const zoomLevel = ref(1)
const panX = ref(0)
const panY = ref(0)
const isZoomDragging = ref(false)
const zoomDragStartX = ref(0)
const zoomDragStartY = ref(0)
const zoomDragStartPanX = ref(0)
const zoomDragStartPanY = ref(0)
const lastTouchDistance = ref(0)

// ============ Computed ============
const totalPage = computed(() => props.totalPages)

const isMobile = computed(() => {
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
})

const currentZoomImage = computed(() => {
  if (currentPage.value >= 1 && currentPage.value <= props.images.length) {
    return props.images[currentPage.value - 1]
  }
  return ''
})

const getContainerStyle = computed(() => {
  if (zoomLevel.value > 1) {
    return {
      transform: `scale(${zoomLevel.value})`,
      transformOrigin: 'center center'
    }
  }
  return {}
})

// ============ Methods ============

// 获取图片源（支持懒加载）
function getImageSrc(index) {
  return props.images[index] || ''
}

// 图片加载成功
function onImageLoad(page) {
  loadedPages.value.add(page)
}

// 图片加载失败
function onImageError(page) {
  console.error('[ComicReaderBase] 图片加载失败:', page)
}

// 计算需要加载的页面序列
function calculateLoadSequence(startPage, totalPages) {
  const sequence = []
  const added = new Set()

  if (totalPages <= 0) return sequence

  // 先加当前页
  if (startPage >= 1 && startPage <= totalPages) {
    sequence.push(startPage)
    added.add(startPage)
  }

  let forwardOffset = 1
  let backwardOffset = 1
  let iterations = 0
  const maxIterations = totalPages * 2 + 10

  while (added.size < totalPages && iterations < maxIterations) {
    iterations++

    // 向后加载
    const forwardPage = startPage + forwardOffset
    if (forwardPage <= totalPages && !added.has(forwardPage)) {
      sequence.push(forwardPage)
      added.add(forwardPage)
    }
    forwardOffset++

    // 向前加载（每向后4页插入1页向前）
    if (forwardOffset % 4 === 0) {
      const backwardPage = startPage - backwardOffset
      if (backwardPage >= 1 && !added.has(backwardPage)) {
        sequence.push(backwardPage)
        added.add(backwardPage)
      }
      backwardOffset++
    }
  }

  return sequence
}

// 处理加载队列
async function processLoadQueue() {
  if (isProcessingQueue || loadQueue.value.length === 0) return

  isProcessingQueue = true

  while (loadQueue.value.length > 0) {
    const page = loadQueue.value.shift()

    if (page >= 1 && page <= totalPage.value && !loadingPages.value.has(page)) {
      loadingPages.value.add(page)

      const img = new Image()
      img.decoding = 'async'

      await new Promise((resolve) => {
        img.onload = () => {
          loadedPages.value.add(page)
          loadingPages.value.delete(page)
          resolve()
        }
        img.onerror = () => {
          console.error('[ComicReaderBase] 加载失败:', page)
          loadingPages.value.delete(page)
          resolve()
        }

        if (page >= 1 && page <= props.images.length) {
          img.src = props.images[page - 1]
        } else {
          resolve()
        }
      })
    }
  }

  isProcessingQueue = false
}

// 预加载页面
function preloadPages(centerPage) {
  const sequence = calculateLoadSequence(centerPage, totalPage.value)
  loadQueue.value = sequence
  processLoadQueue()
}

// 滚动处理
function handleScroll() {
  if (pageMode.value === 'left_right') {
    const container = leftRightContainer.value
    if (!container) return

    const scrollLeft = container.scrollLeft
    const pageWidth = container.clientWidth
    const newPage = Math.round(scrollLeft / pageWidth) + 1

    if (newPage !== currentPage.value && newPage >= 1 && newPage <= totalPage.value) {
      currentPage.value = newPage
      preloadPages(newPage)
    }
  } else {
    const container = upDownContainer.value
    if (!container) return

    const scrollTop = container.scrollTop
    const pageHeight = container.clientHeight
    const newPage = Math.round(scrollTop / pageHeight) + 1

    if (newPage !== currentPage.value && newPage >= 1 && newPage <= totalPage.value) {
      currentPage.value = newPage
      preloadPages(newPage)
    }
  }
}

// 滚轮处理
function handleWheel(event) {
  if (!event.ctrlKey) return

  event.preventDefault()
  const delta = event.deltaY > 0 ? -0.1 : 0.1
  zoomLevel.value = Math.max(1, Math.min(5, zoomLevel.value + delta))
}

// 跳转到指定页
function goToPage(page) {
  const targetPage = Math.max(1, Math.min(page, totalPage.value))
  currentPage.value = targetPage

  nextTick(() => {
    if (pageMode.value === 'left_right') {
      const container = leftRightContainer.value
      if (container) {
        container.scrollTo({
          left: (targetPage - 1) * container.clientWidth,
          behavior: 'smooth'
        })
      }
    } else {
      const container = upDownContainer.value
      if (container) {
        container.scrollTo({
          top: (targetPage - 1) * container.clientHeight,
          behavior: 'smooth'
        })
      }
    }
  })

  preloadPages(targetPage)
}

// 上一页
function prevPage() {
  if (currentPage.value > 1) {
    goToPage(currentPage.value - 1)
  }
}

// 下一页
function nextPage() {
  if (currentPage.value < totalPage.value) {
    goToPage(currentPage.value + 1)
  }
}

// 切换翻页模式
function togglePageMode() {
  configStore.togglePageMode()
}

// 处理滑块变化
function handleSliderChange() {
  goToPage(parseInt(sliderPage.value))
}

// 点击左侧
function handleTapLeft() {
  if (pageMode.value === 'left_right') {
    nextPage()
  } else {
    prevPage()
  }
}

// 点击右侧
function handleTapRight() {
  if (pageMode.value === 'left_right') {
    prevPage()
  } else {
    nextPage()
  }
}

// 点击中间
function handleTapCenter() {
  showMenu.value = !showMenu.value
}

// 点击图片
function handleImageClick() {
  showMenu.value = !showMenu.value
}

// 拖拽开始
function startDrag(event, index) {
  if (zoomLevel.value > 1) {
    event.preventDefault()
    isZoomDragging.value = true
    zoomDragStartX.value = event.clientX
    zoomDragStartY.value = event.clientY
    zoomDragStartPanX.value = panX.value
    zoomDragStartPanY.value = panY.value

    document.addEventListener('mousemove', handleZoomDrag)
    document.addEventListener('mouseup', endZoomDrag)
  }
}

// 触摸拖拽开始
function startTouchDrag(event, index) {
  if (zoomLevel.value > 1 && event.touches.length === 1) {
    isZoomDragging.value = true
    zoomDragStartX.value = event.touches[0].clientX
    zoomDragStartY.value = event.touches[0].clientY
    zoomDragStartPanX.value = panX.value
    zoomDragStartPanY.value = panY.value
  }
}

// 处理拖拽
function handleZoomDrag(event) {
  if (!isZoomDragging.value) return

  const deltaX = event.clientX - zoomDragStartX.value
  const deltaY = event.clientY - zoomDragStartY.value

  panX.value = zoomDragStartPanX.value + deltaX
  panY.value = zoomDragStartPanY.value + deltaY
}

// 结束拖拽
function endZoomDrag() {
  isZoomDragging.value = false
  document.removeEventListener('mousemove', handleZoomDrag)
  document.removeEventListener('mouseup', endZoomDrag)
}

// 进入缩放模式
function enterZoomMode() {
  isZoomMode.value = true
  zoomLevel.value = 2
}

// 退出缩放模式
function exitZoomMode() {
  isZoomMode.value = false
  zoomLevel.value = 1
  panX.value = 0
  panY.value = 0
}

// 缩放滚轮
function handleZoomWheel(event) {
  if (!isMobile.value) return
  event.preventDefault()
  const delta = event.deltaY > 0 ? -0.2 : 0.2
  zoomLevel.value = Math.max(1, Math.min(5, zoomLevel.value + delta))
}

// 缩放触摸开始
function startZoomTouch(event) {
  if (!isMobile.value) return

  if (event.touches.length === 2) {
    const touch1 = event.touches[0]
    const touch2 = event.touches[1]
    lastTouchDistance.value = Math.hypot(
      touch2.clientX - touch1.clientX,
      touch2.clientY - touch1.clientY
    )
  } else if (event.touches.length === 1 && zoomLevel.value > 1) {
    isZoomDragging.value = true
    zoomDragStartX.value = event.touches[0].clientX
    zoomDragStartY.value = event.touches[0].clientY
    zoomDragStartPanX.value = panX.value
    zoomDragStartPanY.value = panY.value
  }
}

// 缩放触摸移动
function handleZoomTouchMove(event) {
  if (!isMobile.value) return

  if (event.touches.length === 2) {
    event.preventDefault()
    const touch1 = event.touches[0]
    const touch2 = event.touches[1]
    const distance = Math.hypot(
      touch2.clientX - touch1.clientX,
      touch2.clientY - touch1.clientY
    )

    if (lastTouchDistance.value > 0) {
      const scale = distance / lastTouchDistance.value
      zoomLevel.value = Math.max(1, Math.min(5, zoomLevel.value * scale))
    }

    lastTouchDistance.value = distance
  } else if (event.touches.length === 1 && isZoomDragging.value) {
    const deltaX = event.touches[0].clientX - zoomDragStartX.value
    const deltaY = event.touches[0].clientY - zoomDragStartY.value

    panX.value = zoomDragStartPanX.value + deltaX
    panY.value = zoomDragStartPanY.value + deltaY
  }
}

// 缩放触摸结束
function endZoomTouch() {
  lastTouchDistance.value = 0
  isZoomDragging.value = false
}

// 双击重置
function handleDoubleClick() {
  if (!isMobile.value && zoomLevel.value > 1) {
    zoomLevel.value = 1
    panX.value = 0
    panY.value = 0
  }
}

// 全屏切换
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(err => {
      console.error('[ComicReaderBase] 全屏失败:', err)
    })
  } else {
    document.exitFullscreen()
  }
}

// 返回
function handleBack() {
  emit('back')
}

// 重新加载
function reloadImages() {
  emit('reload')
}

// 保存进度
function saveProgress() {
  emit('saveProgress', currentPage.value)
}

// ============ Watchers ============
watch(currentPage, (newPage) => {
  sliderPage.value = Math.round(newPage)
  emit('update:currentPage', newPage)

  // 手机端切换页面时重置缩放
  if (isMobile.value) {
    zoomLevel.value = 1
    panX.value = 0
    panY.value = 0
  }
})

watch(() => props.initialPage, (newPage) => {
  if (newPage !== currentPage.value) {
    currentPage.value = newPage
    goToPage(newPage)
  }
})

// ============ Lifecycle ============
onMounted(() => {
  // 双击事件监听
  if (readerContent.value) {
    readerContent.value.addEventListener('dblclick', handleDoubleClick)
  }

  // 全屏变化监听
  document.addEventListener('fullscreenchange', () => {
    // 可以在这里添加全屏状态变化的处理
  })

  // 初始化预加载
  if (props.images.length > 0) {
    preloadPages(currentPage.value)
  }
})

onUnmounted(() => {
  document.removeEventListener('mousemove', handleZoomDrag)
  document.removeEventListener('mouseup', endZoomDrag)

  if (readerContent.value) {
    readerContent.value.removeEventListener('dblclick', handleDoubleClick)
  }
})
</script>

<style scoped>
.comic-reader-base {
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
  height: calc(100vh - 46px);
  overflow: hidden;
  position: relative;
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
  height: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
}

.left-right-mode .page {
  flex: 0 0 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  scroll-snap-align: start;
}

.up-down-mode {
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
  scroll-snap-type: y mandatory;
  scroll-behavior: smooth;
}

.up-down-mode .up-down-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  scroll-snap-align: start;
}

.comic-image {
  max-width: 100%;
  max-height: 100vh;
  object-fit: contain;
  transition: opacity 0.3s;
}

.comic-image.loading {
  opacity: 0.3;
}

.tap-zones {
  position: fixed;
  top: 46px;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  z-index: 100;
  pointer-events: none;
}

.tap-zone {
  pointer-events: auto;
}

.tap-left, .tap-right {
  width: 25%;
}

.tap-center {
  width: 50%;
}

.control-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(0, 0, 0, 0.9);
  padding: 10px 15px;
  z-index: 200;
}

.progress-section {
  margin-bottom: 10px;
}

.page-indicator {
  color: #fff;
  font-size: 14px;
  display: block;
  text-align: center;
  margin-bottom: 5px;
}

.progress-slider-container {
  margin: 5px 0;
}

.progress-slider {
  width: 100%;
  height: 4px;
  -webkit-appearance: none;
  appearance: none;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 2px;
  outline: none;
}

.progress-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  background: #fff;
  border-radius: 50%;
  cursor: pointer;
}

.progress-bar {
  height: 2px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 1px;
  margin-top: 5px;
}

.progress-fill {
  height: 100%;
  background: #fff;
  border-radius: 1px;
  transition: width 0.3s;
}

.actions {
  display: flex;
  justify-content: center;
  gap: 10px;
}

.mode-btn {
  min-width: 60px;
}

.zoom-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: #000;
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.zoom-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  transition: transform 0.1s;
}

.zoom-close {
  position: absolute;
  top: 20px;
  right: 20px;
  color: #fff;
  z-index: 301;
}

.zoom-info {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  color: #fff;
  background: rgba(0, 0, 0, 0.5);
  padding: 5px 10px;
  border-radius: 4px;
}

.desktop-zoom-info {
  position: fixed;
  top: 60px;
  left: 50%;
  transform: translateX(-50%);
  color: #fff;
  background: rgba(0, 0, 0, 0.7);
  padding: 5px 10px;
  border-radius: 4px;
  font-size: 12px;
  z-index: 150;
}
</style>