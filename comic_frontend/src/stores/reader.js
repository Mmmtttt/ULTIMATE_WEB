import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useConfigStore } from './config'
import { comicApi } from '@/api'
import { validatePage, formatProgress } from '@/utils'

/**
 * 阅读器 Store
 * 管理阅读器状态和阅读进度
 */
export const useReaderStore = defineStore('reader', () => {
  // ============ Dependencies ============
  const configStore = useConfigStore()
  
  // ============ State ============
  
  // 当前漫画ID
  const currentComicId = ref(null)
  
  // 当前页码
  const currentPage = ref(1)
  
  // 总页数
  const totalPage = ref(0)
  
  // 缩放比例
  const scale = ref(1)
  
  // 图片位置（用于拖动）
  const position = ref({ x: 0, y: 0 })
  
  // 阅读器状态
  const readerState = ref('IDLE') // IDLE, LOADING, READING, ZOOMING, MENU
  
  // 工具栏显示状态
  const toolbarVisible = ref(true)
  
  // 预加载的图片集合
  const preloadedImages = ref(new Set())
  
  // 图片缓存
  const imageCache = ref(new Map())
  
  // 阅读进度（本地存储）
  const readProgress = ref({})
  
  // ============ Getters ============
  
  /**
   * 当前进度信息
   */
  const progress = computed(() => ({
    current: currentPage.value,
    total: totalPage.value,
    percentage: totalPage.value > 0 ? Math.round((currentPage.value / totalPage.value) * 100) : 0,
    text: formatProgress(currentPage.value, totalPage.value)
  }))
  
  /**
   * 是否可以前进
   */
  const canGoNext = computed(() => currentPage.value < totalPage.value)
  
  /**
   * 是否可以后退
   */
  const canGoPrev = computed(() => currentPage.value > 1)
  
  /**
   * 当前图片URL
   */
  const currentImageUrl = computed(() => {
    if (!currentComicId.value) return ''
    return `/api/v1/comic/image?comic_id=${currentComicId.value}&page_num=${currentPage.value}`
  })
  
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
  
  /**
   * 缩放百分比
   */
  const scalePercent = computed(() => Math.round(scale.value * 100))
  
  // ============ Actions ============
  
  /**
   * 初始化阅读器
   * @param {string} comicId - 漫画ID
   * @param {number} total - 总页数
   * @param {number} initialPage - 初始页码
   */
  function initReader(comicId, total, initialPage = 1) {
    currentComicId.value = comicId
    totalPage.value = total
    currentPage.value = initialPage
    scale.value = 1
    position.value = { x: 0, y: 0 }
    readerState.value = 'READING'
    preloadedImages.value.clear()
    
    console.log('[Reader] 初始化阅读器', { comicId, total, initialPage })
    
    // 开始预加载
    preloadImages()
  }
  
  /**
   * 跳转到指定页
   * @param {number} page - 目标页码
   * @returns {boolean} 是否成功
   */
  function jumpToPage(page) {
    const validation = validatePage(page, totalPage.value)
    
    if (!validation.valid) {
      console.warn('[Reader] 页码无效:', validation.message)
      return false
    }
    
    currentPage.value = page
    console.log('[Reader] 跳转到页码:', page)
    
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
      readerState.value = 'ZOOMING'
      console.log('[Reader] 放大:', scale.value)
    }
  }
  
  /**
   * 缩小
   */
  function zoomOut() {
    if (scale.value > 0.5) {
      scale.value = Math.max(0.5, scale.value - 0.1)
      readerState.value = 'ZOOMING'
      console.log('[Reader] 缩小:', scale.value)
    }
  }
  
  /**
   * 重置缩放
   */
  function resetZoom() {
    scale.value = 1
    position.value = { x: 0, y: 0 }
    readerState.value = 'READING'
    console.log('[Reader] 重置缩放')
  }
  
  /**
   * 设置图片位置
   * @param {number} x - X坐标
   * @param {number} y - Y坐标
   */
  function setPosition(x, y) {
    position.value = { x, y }
  }
  
  /**
   * 切换工具栏显示
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
   * @param {number} page - 页码
   */
  function preloadImage(page) {
    if (preloadedImages.value.has(page)) return
    
    const url = `/api/v1/comic/image?comic_id=${currentComicId.value}&page_num=${page}`
    
    const img = new Image()
    img.onload = () => {
      preloadedImages.value.add(page)
      imageCache.value.set(page, img)
      console.log('[Reader] 预加载完成:', page)
    }
    img.onerror = () => {
      console.warn('[Reader] 预加载失败:', page)
    }
    img.src = url
    
    console.log('[Reader] 开始预加载:', page)
  }
  
  /**
   * 保存阅读进度
   */
  async function saveProgress() {
    if (!currentComicId.value) return
    
    const progress = {
      page: currentPage.value,
      scale: scale.value,
      mode: configStore.defaultPageMode,
      background: configStore.defaultBackground,
      timestamp: Date.now()
    }
    
    // 保存到本地
    readProgress.value[currentComicId.value] = progress
    
    // 保存到服务器
    try {
      await comicApi.saveProgress(currentComicId.value, currentPage.value)
      console.log('[Reader] 保存阅读进度:', currentComicId.value, currentPage.value)
    } catch (error) {
      console.error('[Reader] 保存进度失败:', error)
    }
  }
  
  /**
   * 加载阅读进度
   * @param {string} comicId - 漫画ID
   * @returns {Object|null} 进度信息
   */
  function loadProgress(comicId) {
    return readProgress.value[comicId] || null
  }
  
  /**
   * 恢复阅读状态
   * @param {string} comicId - 漫画ID
   */
  function restoreProgress(comicId) {
    const progress = loadProgress(comicId)
    
    if (progress) {
      currentPage.value = progress.page || 1
      scale.value = progress.scale || 1
      
      // 恢复配置
      if (progress.mode) {
        configStore.setPageMode(progress.mode)
      }
      if (progress.background) {
        configStore.setBackground(progress.background)
      }
      
      console.log('[Reader] 恢复阅读状态:', progress)
      return true
    }
    
    return false
  }
  
  /**
   * 清理阅读器状态
   */
  function cleanup() {
    currentComicId.value = null
    currentPage.value = 1
    totalPage.value = 0
    scale.value = 1
    position.value = { x: 0, y: 0 }
    readerState.value = 'IDLE'
    toolbarVisible.value = true
    preloadedImages.value.clear()
    imageCache.value.clear()
    console.log('[Reader] 清理阅读器状态')
  }
  
  return {
    // State
    currentComicId,
    currentPage,
    totalPage,
    scale,
    position,
    readerState,
    toolbarVisible,
    preloadedImages,
    imageCache,
    readProgress,
    
    // Getters
    progress,
    canGoNext,
    canGoPrev,
    currentImageUrl,
    preloadQueue,
    scalePercent,
    
    // Actions
    initReader,
    jumpToPage,
    nextPage,
    prevPage,
    zoomIn,
    zoomOut,
    resetZoom,
    setPosition,
    toggleToolbar,
    showToolbar,
    hideToolbar,
    preloadImages,
    preloadImage,
    saveProgress,
    loadProgress,
    restoreProgress,
    cleanup
  }
})
