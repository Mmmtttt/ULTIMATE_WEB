<template>
  <div class="recommendation-reader" :style="{ background: background }">
    <van-nav-bar
      v-show="showMenu"
      title=""
      left-text="返回"
      left-arrow
      @click-left="$router.back()"
      :style="{ background: 'transparent' }"
    >
      <template #right>
        <span class="page-indicator">{{ currentPage }}/{{ totalPages }}</span>
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
        @scroll="handleScroll"
      >
        <div
          v-for="(image, index) in images"
          :key="index"
          class="page"
        >
          <img
            :src="image"
            class="comic-image"
            :class="{ 'loading': !loadedPages.has(index + 1) }"
            decoding="async"
            draggable="false"
            @click="handleImageClick"
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
        @scroll="handleScroll"
      >
        <div
          v-for="(image, index) in images"
          :key="index"
          class="up-down-page"
        >
          <img
            :src="image"
            class="comic-image"
            :class="{ 'loading': !loadedPages.has(index + 1) }"
            decoding="async"
            draggable="false"
            @click="handleImageClick"
            @load="onImageLoad(index + 1)"
            @error="onImageError(index + 1)"
          />
        </div>
      </div>
    </div>

    <!-- 底部控制栏 -->
    <div v-show="showMenu" class="bottom-controls">
      <div class="progress-bar">
        <van-slider
          v-model="sliderPage"
          :min="1"
          :max="totalPages"
          @change="onSliderChange"
        />
      </div>
      <div class="control-buttons">
        <van-button size="small" @click="prevPage">上一页</van-button>
        <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
        <van-button size="small" @click="nextPage">下一页</van-button>
      </div>
    </div>

    <!-- 点击区域（用于显示/隐藏菜单） -->
    <div class="tap-zones">
      <div class="tap-zone tap-left" @click="handleTapLeft"></div>
      <div class="tap-zone tap-center" @click="handleTapCenter"></div>
      <div class="tap-zone tap-right" @click="handleTapRight"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRecommendationStore, useConfigStore } from '@/stores'

const route = useRoute()
const router = useRouter()
const recommendationStore = useRecommendationStore()
const configStore = useConfigStore()

// ============ State ============
const loading = ref(true)
const error = ref(false)
const images = ref([])
const currentPage = ref(1)
const totalPages = ref(0)
const showMenu = ref(true)
const loadedPages = ref(new Set())
const sliderPage = ref(1)

// ============ Computed ============
const recommendationId = computed(() => route.params.id)
const recommendation = computed(() => recommendationStore.currentRecommendationInfo)

const pageMode = computed(() => configStore.pageMode)
const background = computed(() => configStore.background)

// ============ Methods ============

/**
 * 加载图片列表
 */
async function loadImages() {
  console.log('[RecommendationReader] 加载图片列表:', recommendationId.value)
  loading.value = true
  error.value = false

  try {
    // 获取推荐漫画详情
    await recommendationStore.fetchRecommendationDetail(recommendationId.value)

    if (!recommendation.value) {
      error.value = true
      loading.value = false
      return
    }

    totalPages.value = recommendation.value.total_page

    // 获取图片列表
    const imageList = await recommendationStore.fetchImages(recommendationId.value)
    images.value = imageList

    // 设置当前页
    const startPage = parseInt(route.query.page) || recommendation.value.current_page || 1
    currentPage.value = Math.max(1, Math.min(startPage, totalPages.value))
    sliderPage.value = currentPage.value

    // 预加载当前页及附近页面
    preloadPages(currentPage.value)

    loading.value = false
  } catch (err) {
    console.error('[RecommendationReader] 加载失败:', err)
    error.value = true
    loading.value = false
  }
}

/**
 * 预加载页面
 */
function preloadPages(centerPage) {
  const preloadRange = 3
  for (let i = centerPage - preloadRange; i <= centerPage + preloadRange; i++) {
    if (i >= 1 && i <= totalPages.value) {
      const img = new Image()
      img.src = images.value[i - 1]
    }
  }
}

/**
 * 图片加载成功
 */
function onImageLoad(page) {
  loadedPages.value.add(page)
}

/**
 * 图片加载失败
 */
function onImageError(page) {
  console.error('[RecommendationReader] 图片加载失败:', page)
}

/**
 * 处理滚动事件
 */
function handleScroll() {
  // 根据滚动位置计算当前页
  const container = pageMode.value === 'left_right'
    ? document.querySelector('.left-right-mode')
    : document.querySelector('.up-down-mode')

  if (!container) return

  if (pageMode.value === 'left_right') {
    const scrollLeft = container.scrollLeft
    const pageWidth = container.clientWidth
    const newPage = Math.round(scrollLeft / pageWidth) + 1
    if (newPage !== currentPage.value && newPage >= 1 && newPage <= totalPages.value) {
      currentPage.value = newPage
      sliderPage.value = newPage
      saveProgress()
      preloadPages(newPage)
    }
  } else {
    const scrollTop = container.scrollTop
    const pageHeight = container.querySelector('.up-down-page')?.clientHeight || 0
    const newPage = Math.round(scrollTop / pageHeight) + 1
    if (newPage !== currentPage.value && newPage >= 1 && newPage <= totalPages.value) {
      currentPage.value = newPage
      sliderPage.value = newPage
      saveProgress()
      preloadPages(newPage)
    }
  }
}

/**
 * 保存阅读进度
 */
async function saveProgress() {
  await recommendationStore.saveProgress(recommendationId.value, currentPage.value)
}

/**
 * 上一页
 */
function prevPage() {
  if (currentPage.value > 1) {
    goToPage(currentPage.value - 1)
  }
}

/**
 * 下一页
 */
function nextPage() {
  if (currentPage.value < totalPages.value) {
    goToPage(currentPage.value + 1)
  }
}

/**
 * 跳转到指定页
 */
function goToPage(page) {
  if (page < 1 || page > totalPages.value) return

  currentPage.value = page
  sliderPage.value = page

  const container = pageMode.value === 'left_right'
    ? document.querySelector('.left-right-mode')
    : document.querySelector('.up-down-mode')

  if (container) {
    if (pageMode.value === 'left_right') {
      container.scrollTo({
        left: (page - 1) * container.clientWidth,
        behavior: 'smooth'
      })
    } else {
      const pageElement = container.children[page - 1]
      if (pageElement) {
        pageElement.scrollIntoView({ behavior: 'smooth' })
      }
    }
  }

  saveProgress()
  preloadPages(page)
}

/**
 * 滑块变化
 */
function onSliderChange(value) {
  goToPage(value)
}

/**
 * 处理图片点击
 */
function handleImageClick() {
  toggleMenu()
}

/**
 * 处理左侧点击
 */
function handleTapLeft() {
  if (showMenu.value) {
    toggleMenu()
  } else {
    prevPage()
  }
}

/**
 * 处理中间点击
 */
function handleTapCenter() {
  toggleMenu()
}

/**
 * 处理右侧点击
 */
function handleTapRight() {
  if (showMenu.value) {
    toggleMenu()
  } else {
    nextPage()
  }
}

/**
 * 切换菜单显示
 */
function toggleMenu() {
  showMenu.value = !showMenu.value
}

// ============ Keyboard Navigation ============
function handleKeydown(e) {
  switch (e.key) {
    case 'ArrowLeft':
    case 'PageUp':
      prevPage()
      break
    case 'ArrowRight':
    case ' ': // 空格键
    case 'PageDown':
      nextPage()
      break
    case 'Home':
      goToPage(1)
      break
    case 'End':
      goToPage(totalPages.value)
      break
    case 'Escape':
      toggleMenu()
      break
  }
}

// ============ Lifecycle ============
onMounted(() => {
  console.log('[RecommendationReader] 页面挂载')
  loadImages()
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

// 监听路由参数变化
watch(() => route.query.page, (newPage) => {
  if (newPage) {
    goToPage(parseInt(newPage))
  }
})
</script>

<style scoped>
.recommendation-reader {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
}

.loading,
.error {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.reader-content {
  width: 100%;
  height: 100%;
}

/* 左右翻页模式 */
.left-right-mode {
  width: 100%;
  height: 100%;
  display: flex;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
}

.left-right-mode .page {
  flex-shrink: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  scroll-snap-align: start;
}

/* 上下翻页模式 */
.up-down-mode {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
}

.up-down-page {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
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

/* 底部控制栏 */
.bottom-controls {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 16px;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(10px);
}

.progress-bar {
  margin-bottom: 12px;
}

.control-buttons {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-info {
  color: #fff;
  font-size: 14px;
}

.page-indicator {
  color: #fff;
  font-size: 14px;
}

/* 点击区域 */
.tap-zones {
  position: fixed;
  top: 50px;
  left: 0;
  right: 0;
  bottom: 100px;
  display: flex;
  pointer-events: none;
}

.tap-zone {
  pointer-events: auto;
}

.tap-left {
  width: 25%;
}

.tap-center {
  width: 50%;
}

.tap-right {
  width: 25%;
}

/* 导航栏样式 */
:deep(.van-nav-bar) {
  background: rgba(0, 0, 0, 0.5);
}

:deep(.van-nav-bar__text),
:deep(.van-nav-bar__title) {
  color: #fff;
}

:deep(.van-nav-bar .van-icon) {
  color: #fff;
}
</style>
