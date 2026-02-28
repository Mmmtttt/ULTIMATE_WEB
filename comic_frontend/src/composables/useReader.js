import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useComicStore, useConfigStore } from '@/stores'
import { 
  PAGE_MODE, 
  validatePage, 
  formatProgress,
  PRELOAD_RANGE 
} from '@/utils'

/**
 * 阅读器组合式函数
 * 封装阅读器的核心逻辑
 */
export function useReader() {
  const route = useRoute()
  const router = useRouter()
  const comicStore = useComicStore()
  const configStore = useConfigStore()
  
  // ============ State ============
  
  // 当前漫画信息
  const comic = ref(null)
  
  // 图片列表
  const images = ref([])
  
  // 当前页码
  const currentPage = ref(1)
  
  // 总页数
  const totalPage = ref(0)
  
  // 缩放比例
  const scale = ref(1)
  
  // 图片位置（拖动用）
  const position = ref({ x: 0, y: 0 })
  
  // 加载状态
  const loading = ref(false)
  
  // 工具栏显示状态
  const toolbarVisible = ref(true)
  
  // 预加载的图片集合
  const preloadedImages = ref(new Set())
  
  // 触摸相关
  const touchStart = ref({ x: 0, y: 0 })
  const isDragging = ref(false)
  
  // ============ Getters ============
  
  /**
   * 当前进度信息
   */
  const progress = computed(() => ({
    current: currentPage.value,
    total: totalPage.value,
    percentage: totalPage.value > 0 
      ? Math.round((currentPage.value / totalPage.value) * 100) 
      : 0,
    text: formatProgress(currentPage.value, totalPage.value)
  }))
  
  /**
   * 当前图片URL
   */
  const currentImageUrl = computed(() => {
    if (!comic.value || !currentPage.value) return ''
    return `/api/v1/comic/image?comic_id=${comic.value.id}&page_num=${currentPage.value}`
  })
  
  /**
   * 是否可以前进
   */
  const canGoNext = computed(() => currentPage.value < totalPage.value)
  
  /**
   * 是否可以后退
   */
  const canGoPrev = computed(() => currentPage.value > 1)
  
  /**
   * 缩放百分比
   */
  const scalePercent = computed(() => Math.round(scale.value * 100))
  
  /**
   * 是否为左右翻页模式
   */
  const isLeftRightMode = computed(() => 
    configStore.defaultPageMode === PAGE_MODE.LEFT_RIGHT
  )
  
  /**
   * 预加载队列
   */
  const preloadQueue = computed(() => {
    const queue = []
    const preloadCount = configStore.preloadNum
    
    // 向后加载
    for (let i = 0; i <= preloadCount; i++) {
      const page = currentPage.value + i
      if (page <= totalPage.value) {
        queue.push(page)
      }
    }
    
    // 向前加载1页
    const prevPage = currentPage.value - 1
    if (prevPage >= 1) {
      queue.push(prevPage)
    }
    
    // 去重
    return [...new Set(queue)]
  })
  
  // ============ Actions ============
  
  /**
   * 初始化阅读器
   */
  async function initReader() {
    const comicId = route.query.id
    const initialPage = parseInt(route.query.page) || 1
    
    if (!comicId) {
      router.push('/')
      return
    }
    
    loading.value = true
    
    try {
      // 获取漫画详情
      const detail = await comicStore.fetchComicDetail(comicId)
      if (!detail) {
        throw new Error('漫画不存在')
      }
      
      comic.value = detail
      totalPage.value = detail.total_page || 0
      
      // 获取图片列表
      const imageList = await comicStore.fetchImages(comicId)
      if (imageList) {
        images.value = imageList
        totalPage.value = imageList.length
      }
      
      // 设置初始页码
      const validPage = Math.max(1, Math.min(initialPage, totalPage.value))
      currentPage.value = validPage
      
      // 开始预加载
      preloadImages()
      
      console.log('[useReader] 阅读器初始化完成', {
        comicId,
        totalPage: totalPage.value,
        currentPage: currentPage.value
      })
    } catch (error) {
      console.error('[useReader] 初始化失败:', error)
      // 可以在这里显示错误提示
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 跳转到指定页
   */
  function jumpToPage(page) {
    const validation = validatePage(page, totalPage.value)
    
    if (!validation.valid) {
      console.warn('[useReader] 页码无效:', validation.message)
      return false
    }
    
    currentPage.value = page
    
    // 更新URL
    router.replace({
      query: { ...route.query, page }
    })
    
    // 保存进度
    saveProgress()
    
    // 预加载
    preloadImages()
    
    return true
  }
  
  /**
   * 下一页
   */
  function nextPage() {
    if (canGoNext.value) {
      jumpToPage(currentPage.value + 1)
    }
  }
  
  /**
   * 上一页
   */
  function prevPage() {
    if (canGoPrev.value) {
      jumpToPage(currentPage.value - 1)
    }
  }
  
  /**
   * 放大
   */
  function zoomIn() {
    if (scale.value < 2.0) {
      scale.value = Math.min(2.0, scale.value + 0.1)
    }
  }
  
  /**
   * 缩小
   */
  function zoomOut() {
    if (scale.value > 0.5) {
      scale.value = Math.max(0.5, scale.value - 0.1)
    }
  }
  
  /**
   * 重置缩放
   */
  function resetZoom() {
    scale.value = 1
    position.value = { x: 0, y: 0 }
  }
  
  /**
   * 切换工具栏
   */
  function toggleToolbar() {
    toolbarVisible.value = !toolbarVisible.value
  }
  
  /**
   * 显示工具栏
   */
  function showToolbar() {
    toolbarVisible.value = true
  }
  
  /**
   * 隐藏工具栏
   */
  function hideToolbar() {
    if (configStore.autoHideToolbar) {
      toolbarVisible.value = false
    }
  }
  
  /**
   * 预加载图片
   */
  function preloadImages() {
    const pages = preloadQueue.value
    
    pages.forEach(page => {
      if (!preloadedImages.value.has(page)) {
        preloadImage(page)
      }
    })
  }
  
  /**
   * 预加载单张图片
   */
  function preloadImage(page) {
    if (preloadedImages.value.has(page) || !comic.value) return
    
    const url = `/api/v1/comic/image?comic_id=${comic.value.id}&page_num=${page}`
    
    const img = new Image()
    img.onload = () => {
      preloadedImages.value.add(page)
    }
    img.onerror = () => {
      console.warn('[useReader] 预加载失败:', page)
    }
    img.src = url
  }
  
  /**
   * 保存阅读进度
   */
  async function saveProgress() {
    if (!comic.value) return
    
    try {
      await comicStore.saveProgress(comic.value.id, currentPage.value)
    } catch (error) {
      console.error('[useReader] 保存进度失败:', error)
    }
  }
  
  /**
   * 返回上一页
   */
  function goBack() {
    router.back()
  }
  
  // ============ 键盘事件处理 ============
  
  function handleKeydown(event) {
    switch (event.key) {
      case 'ArrowRight':
      case 'ArrowDown':
      case ' ':
        event.preventDefault()
        nextPage()
        break
      case 'ArrowLeft':
      case 'ArrowUp':
        event.preventDefault()
        prevPage()
        break
      case 'Home':
        event.preventDefault()
        jumpToPage(1)
        break
      case 'End':
        event.preventDefault()
        jumpToPage(totalPage.value)
        break
      case '+':
      case '=':
        event.preventDefault()
        zoomIn()
        break
      case '-':
        event.preventDefault()
        zoomOut()
        break
      case '0':
        event.preventDefault()
        resetZoom()
        break
      case 'Escape':
        event.preventDefault()
        toggleToolbar()
        break
    }
  }
  
  // ============ 触摸事件处理 ============
  
  function handleTouchStart(event) {
    if (event.touches.length === 1) {
      touchStart.value = {
        x: event.touches[0].clientX,
        y: event.touches[0].clientY
      }
      isDragging.value = true
    }
  }
  
  function handleTouchMove(event) {
    if (!isDragging.value || event.touches.length !== 1) return
    
    event.preventDefault()
    
    const touch = event.touches[0]
    const deltaX = touch.clientX - touchStart.value.x
    const deltaY = touch.clientY - touchStart.value.y
    
    // 更新位置（拖动图片）
    if (scale.value > 1) {
      position.value.x += deltaX
      position.value.y += deltaY
    }
    
    touchStart.value = {
      x: touch.clientX,
      y: touch.clientY
    }
  }
  
  function handleTouchEnd(event) {
    if (!isDragging.value) return
    
    isDragging.value = false
    
    // 计算滑动距离
    const touch = event.changedTouches[0]
    const deltaX = touch.clientX - touchStart.value.x
    const deltaY = touch.clientY - touchStart.value.y
    const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY)
    
    // 短距离滑动视为翻页
    if (distance < 50) {
      const screenWidth = window.innerWidth
      const touchX = touch.clientX
      
      if (touchX < screenWidth * 0.3) {
        // 左侧点击 - 上一页
        prevPage()
      } else if (touchX > screenWidth * 0.7) {
        // 右侧点击 - 下一页
        nextPage()
      } else {
        // 中间点击 - 切换工具栏
        toggleToolbar()
      }
    }
  }
  
  // ============ 生命周期 ============
  
  onMounted(() => {
    window.addEventListener('keydown', handleKeydown)
    initReader()
  })
  
  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
    saveProgress()
  })
  
  return {
    // State
    comic,
    images,
    currentPage,
    totalPage,
    scale,
    position,
    loading,
    toolbarVisible,
    preloadedImages,
    
    // Getters
    progress,
    currentImageUrl,
    canGoNext,
    canGoPrev,
    scalePercent,
    isLeftRightMode,
    preloadQueue,
    
    // Actions
    initReader,
    jumpToPage,
    nextPage,
    prevPage,
    zoomIn,
    zoomOut,
    resetZoom,
    toggleToolbar,
    showToolbar,
    hideToolbar,
    preloadImages,
    saveProgress,
    goBack,
    
    // Event handlers
    handleTouchStart,
    handleTouchMove,
    handleTouchEnd
  }
}
