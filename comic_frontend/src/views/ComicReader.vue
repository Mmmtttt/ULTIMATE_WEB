<template>
  <div class="comic-reader" :style="{ background: background }">
    <van-nav-bar 
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
          />
        </div>
      </div>
      
      <!-- 上下翻页模式 -->
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
import { ref, onMounted, computed, watch, nextTick, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useComicStore, useConfigStore } from '@/stores'
import { buildImageUrl } from '@/api/image'

const route = useRoute()
const comicStore = useComicStore()
const configStore = useConfigStore()

const resolvePageMode = (mode) => (mode === 'left_right' || mode === 'up_down' ? mode : 'up_down')

// 状态
const images = ref([])
const currentPage = ref(1)
const totalPage = ref(0)
const loading = ref(true)
const error = ref(false)
const showMenu = ref(false)
const pageMode = ref(resolvePageMode(configStore.defaultPageMode))
const background = ref('#000')
const leftRightContainer = ref(null)
const upDownContainer = ref(null)
const readerContent = ref(null)
const sliderPage = ref(1)

// 图片加载队列控制
const loadedPages = ref(new Set())
const loadingPages = ref(new Set())
const loadQueue = ref([])
let isProcessingQueue = false

// 计算需要加载的页面（向后优先，每向后4页插入1页向前）
const calculateLoadSequence = (startPage, totalPages) => {
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
  let backwardCount = 0
  let iterations = 0
  const maxIterations = totalPages * 2 + 10  // 安全限制
  
  while (added.size < totalPages && iterations < maxIterations) {
    iterations++
    let addedThisRound = false
    
    // 向后加载
    const forwardPage = startPage + forwardOffset
    if (forwardPage <= totalPages && !added.has(forwardPage)) {
      sequence.push(forwardPage)
      added.add(forwardPage)
      backwardCount++
      addedThisRound = true
    }
    forwardOffset++
    
    // 每向后4页，向前加载1页
    if (backwardCount >= 4) {
      const backwardPage = startPage - backwardOffset
      if (backwardPage >= 1 && !added.has(backwardPage)) {
        sequence.push(backwardPage)
        added.add(backwardPage)
        addedThisRound = true
      }
      backwardOffset++
      backwardCount = 0
    }
    
    // 如果向后已遍历完，继续向前加载剩余页面
    if (forwardOffset > totalPages) {
      while (startPage - backwardOffset >= 1 && added.size < totalPages) {
        const backwardPage = startPage - backwardOffset
        if (!added.has(backwardPage)) {
          sequence.push(backwardPage)
          added.add(backwardPage)
        }
        backwardOffset++
      }
      break
    }
  }
  
  return sequence
}

// 处理队列（非递归版本）
const processLoadQueue = () => {
  const MAX_CONCURRENT = 20
  
  while (loadQueue.value.length > 0 && loadingPages.value.size < MAX_CONCURRENT) {
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
      // 用 setTimeout 避免递归栈溢出
      setTimeout(() => processLoadQueue(), 0)
    }
    img.onerror = () => {
      loadingPages.value.delete(pageNum)
      setTimeout(() => processLoadQueue(), 0)
    }
    img.src = imageUrl
  }
  
  isProcessingQueue = loadingPages.value.size > 0
}

// 触发预加载（清空旧队列，开始新序列）
const preloadImages = (startPage) => {
  loadQueue.value = []
  
  const sequence = calculateLoadSequence(startPage, totalPage.value)
  
  for (const pageNum of sequence) {
    if (!loadedPages.value.has(pageNum) && !loadingPages.value.has(pageNum)) {
      loadQueue.value.push(pageNum)
    }
  }
  
  processLoadQueue()
}

// 获取图片URL（只返回已加载或在加载队列中的图片URL）
const getImageSrc = (index) => {
  const pageNum = index + 1
  // 只返回已加载或正在加载的图片URL
  if (loadedPages.value.has(pageNum) || loadingPages.value.has(pageNum)) {
    return images.value[index] || ''
  }
  return ''
}

// 缩放状态
const zoomLevel = ref(1)
const panX = ref(0)
const panY = ref(0)
const isZoomMode = ref(false)
const isZoomDragging = ref(false)
const zoomDragStartX = ref(0)
const zoomDragStartY = ref(0)
const zoomDragStartPanX = ref(0)
const zoomDragStartPanY = ref(0)

// 触摸缩放
const lastTouchDistance = ref(0)

// 拖拽翻页状态
const isDragging = ref(false)
const dragStartX = ref(0)
const dragStartY = ref(0)
const dragStartScrollX = ref(0)
const dragStartScrollY = ref(0)

// 计算属性
const comicId = computed(() => route.params.id)
const currentZoomImage = computed(() => {
  const pageIndex = Math.round(currentPage.value) - 1
  return images.value[pageIndex] || ''
})
const isMobile = computed(() => {
  if (typeof window !== 'undefined') {
    return window.innerWidth <= 768
  }
  return false
})

// 获取容器样式（电脑端缩放时应用到整个容器）
const getContainerStyle = computed(() => {
  if (isMobile.value || zoomLevel.value === 1) {
    return {}
  }
  
  return {
    transform: `scale(${zoomLevel.value})`,
    transformOrigin: 'center center'
  }
})

// 方法
const loadImages = async () => {
  loading.value = true
  error.value = false
  try {
    // 先获取详情，确定当前页
    const comic = await comicStore.fetchComicDetail(comicId.value)
    if (comic && comic.current_page > 1) {
      currentPage.value = comic.current_page
      sliderPage.value = comic.current_page
    }
    
    // 再获取图片列表
    const imageData = await comicStore.fetchImages(comicId.value)
    if (imageData) {
      images.value = imageData.map((path, index) => buildImageUrl(comicId.value, index + 1))
      totalPage.value = images.value.length
      
      // 立即开始预加载，按正确顺序加载图片
      preloadImages(currentPage.value)
    }
    
    await nextTick()
    setTimeout(() => {
      jumpToPage(currentPage.value, false)
    }, 100)
  } catch (err) {
    error.value = true
    console.error('加载图片失败:', err)
  } finally {
    loading.value = false
  }
}

const handleImageClick = (event) => {
  if (!isDragging.value) {
    showMenu.value = !showMenu.value
  }
}

const togglePageMode = () => {
  pageMode.value = pageMode.value === 'left_right' ? 'up_down' : 'left_right'
  setTimeout(() => {
    jumpToPage(currentPage.value, false)
  }, 100)
}

const prevPage = () => {
  const targetPage = Math.max(1, Math.floor(currentPage.value) - 1)
  jumpToPage(targetPage)
  saveProgress()
  preloadImages(targetPage)
}

const nextPage = () => {
  const targetPage = Math.min(totalPage.value, Math.ceil(currentPage.value) + 1)
  jumpToPage(targetPage)
  saveProgress()
  preloadImages(targetPage)
}

const jumpToPage = (page, smooth = true) => {
  const behavior = smooth ? 'smooth' : 'auto'
  
  if (pageMode.value === 'left_right' && leftRightContainer.value) {
    const scrollPosition = (page - 1) * leftRightContainer.value.clientWidth
    leftRightContainer.value.scrollTo({
      left: scrollPosition,
      behavior
    })
  } else if (pageMode.value === 'up_down' && upDownContainer.value) {
    // 获取实际页面高度（单个页面元素的高度）
    const pageElement = upDownContainer.value.querySelector('.up-down-page')
    const pageHeight = pageElement ? pageElement.offsetHeight : upDownContainer.value.clientHeight
    const scrollPosition = (page - 1) * pageHeight
    upDownContainer.value.scrollTo({
      top: scrollPosition,
      behavior
    })
  }
}

const handleSliderChange = () => {
  const page = parseInt(sliderPage.value)
  if (page >= 1 && page <= totalPage.value) {
    jumpToPage(page, false)
    saveProgress()
    preloadImages(page)
  }
}

const saveProgress = async () => {
  try {
    const pageToSave = Math.round(currentPage.value)
    await comicStore.saveProgress(comicId.value, pageToSave)
  } catch (err) {
    console.error('保存进度失败:', err)
  }
}

const handleScroll = () => {
  const container = pageMode.value === 'left_right' ? leftRightContainer.value : upDownContainer.value
  if (!container) return
  
  let newPage
  if (pageMode.value === 'left_right') {
    const scrollLeft = container.scrollLeft
    const pageWidth = container.clientWidth
    newPage = scrollLeft / pageWidth + 1
  } else {
    const scrollTop = container.scrollTop
    // 获取实际页面高度（单个页面元素的高度）
    const pageElement = container.querySelector('.up-down-page')
    const pageHeight = pageElement ? pageElement.offsetHeight : container.clientHeight
    newPage = scrollTop / pageHeight + 1
  }
  
  currentPage.value = Math.max(1, Math.min(totalPage.value, newPage))
  
  if (Math.abs(newPage - Math.round(newPage)) < 0.1) {
    const page = Math.round(newPage)
    saveProgress()
    preloadImages(page)
  }
}

// 手机端缩放模式
const enterZoomMode = () => {
  isZoomMode.value = true
  showMenu.value = false
  zoomLevel.value = 1
  panX.value = 0
  panY.value = 0
}

const exitZoomMode = () => {
  isZoomMode.value = false
  zoomLevel.value = 1
  panX.value = 0
  panY.value = 0
}

// 电脑端滚轮处理
const handleWheel = (event) => {
  if (isMobile.value) return
  
  // Ctrl + 滚轮 = 缩放
  if (event.ctrlKey) {
    event.preventDefault()
    const delta = event.deltaY > 0 ? -0.2 : 0.2
    const newZoom = Math.max(1, Math.min(5, zoomLevel.value + delta))
    
    if (newZoom !== zoomLevel.value) {
      zoomLevel.value = newZoom
    }
  }
  // 单纯滚轮 = 翻页（不重置缩放）
}

// 电脑端拖拽
const startDrag = (event, index) => {
  if (isMobile.value) return
  
  isDragging.value = false
  
  const container = pageMode.value === 'left_right' ? leftRightContainer.value : upDownContainer.value
  if (!container) return
  
  dragStartX.value = event.clientX
  dragStartY.value = event.clientY
  dragStartScrollX.value = container.scrollLeft
  dragStartScrollY.value = container.scrollTop
  
  const handleDragMove = (e) => {
    const deltaX = Math.abs(e.clientX - dragStartX.value)
    const deltaY = Math.abs(e.clientY - dragStartY.value)
    
    if (deltaX > 5 || deltaY > 5) {
      isDragging.value = true
    }
    
    // 缩放状态下，拖动速度加快
    const speed = zoomLevel.value > 1 ? zoomLevel.value : 1
    
    if (pageMode.value === 'left_right') {
      container.scrollLeft = dragStartScrollX.value - (e.clientX - dragStartX.value) * speed
    } else {
      container.scrollTop = dragStartScrollY.value - (e.clientY - dragStartY.value) * speed
    }
  }
  
  const handleDragEnd = () => {
    setTimeout(() => {
      isDragging.value = false
    }, 100)
    document.removeEventListener('mousemove', handleDragMove)
    document.removeEventListener('mouseup', handleDragEnd)
    saveProgress()
  }
  
  document.addEventListener('mousemove', handleDragMove)
  document.addEventListener('mouseup', handleDragEnd)
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
  document.removeEventListener('mousemove', handleZoomDrag)
  document.removeEventListener('mouseup', endZoomDrag)
}

// 全屏切换
const toggleFullscreen = () => {
  // 保存当前进度
  const savedPage = currentPage.value
  
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(err => {
      console.error('全屏失败:', err)
    })
  } else {
    document.exitFullscreen()
  }
  
  // 全屏切换后恢复进度
  setTimeout(() => {
    jumpToPage(savedPage, false)
  }, 100)
}

// 全屏变化处理
const handleFullscreenChange = () => {
  // 全屏变化后恢复进度
  setTimeout(() => {
    jumpToPage(currentPage.value, false)
  }, 100)
}

// 手机端触摸拖拽
const startTouchDrag = (event, index) => {
  if (!isMobile.value) return
  if (isZoomMode.value || event.touches.length !== 1) return
  
  const touch = event.touches[0]
  const container = pageMode.value === 'left_right' ? leftRightContainer.value : upDownContainer.value
  if (!container) return
  
  dragStartX.value = touch.clientX
  dragStartY.value = touch.clientY
  dragStartScrollX.value = container.scrollLeft
  dragStartScrollY.value = container.scrollTop
}

// 手机端缩放触摸
const startZoomTouch = (event) => {
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

const handleZoomTouchMove = (event) => {
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

const endZoomTouch = () => {
  lastTouchDistance.value = 0
  isZoomDragging.value = false
}

// 手机端缩放滚轮
const handleZoomWheel = (event) => {
  if (!isMobile.value) return
  
  event.preventDefault()
  const delta = event.deltaY > 0 ? -0.2 : 0.2
  const newZoom = Math.max(1, Math.min(5, zoomLevel.value + delta))
  
  if (newZoom !== zoomLevel.value) {
    zoomLevel.value = newZoom
  }
}

// 双击重置缩放
const handleDoubleClick = () => {
  if (!isMobile.value && zoomLevel.value > 1) {
    zoomLevel.value = 1
    panX.value = 0
    panY.value = 0
  }
}

watch(currentPage, (newPage) => {
  sliderPage.value = Math.round(newPage)
  // 手机端切换页面时重置缩放
  if (isMobile.value) {
    zoomLevel.value = 1
    panX.value = 0
    panY.value = 0
  }
})

onMounted(() => {
  console.log('[Reader] onMounted, id:', comicId.value, 'cache status:', comicStore.cacheStatus)
  loadImages()
  // 双击事件监听
  if (readerContent.value) {
    readerContent.value.addEventListener('dblclick', handleDoubleClick)
  }
  // 全屏变化监听
  document.addEventListener('fullscreenchange', handleFullscreenChange)
})

onUnmounted(() => {
  document.removeEventListener('mousemove', handleZoomDrag)
  document.removeEventListener('mouseup', endZoomDrag)
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
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
  will-change: scroll-position, transform;
}

.left-right-mode::-webkit-scrollbar {
  display: none;
}

.page {
  flex: 0 0 100%;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  margin: 0;
  padding: 0;
  flex-shrink: 0;
}

.comic-image {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
  display: block;
  user-select: none;
  -webkit-user-drag: none;
  cursor: grab;
  image-rendering: -webkit-optimize-quality;
  image-rendering: high-quality;
}

.comic-image:active {
  cursor: grabbing;
}

.up-down-mode {
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
  will-change: scroll-position, transform;
}

.up-down-mode::-webkit-scrollbar {
  display: none;
}

.up-down-page {
  width: 100%;
  height: calc(100vh - 46px);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  margin: 0;
  padding: 0;
  line-height: 0;
  font-size: 0;
  border: none;
  outline: none;
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
  .up-down-page {
    height: calc(72vh - 46px);
  }
  
  .actions {
    gap: 6px;
  }
  
  .actions .van-button {
    padding: 0 8px;
    font-size: 12px;
  }
}
</style>
