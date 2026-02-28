import { ref, computed } from 'vue'
import { useComicStore, useCacheStore } from '@/stores'
import { SORT_TYPE } from '@/utils'

/**
 * 漫画操作组合式函数
 * 封装漫画相关的操作逻辑
 */
export function useComic() {
  const comicStore = useComicStore()
  const cacheStore = useCacheStore()
  
  // ============ State ============
  
  // 加载状态
  const loading = ref(false)
  
  // 错误信息
  const error = ref(null)
  
  // 当前选中的漫画
  const selectedComics = ref([])
  
  // ============ Getters ============
  
  /**
   * 漫画列表
   */
  const comics = computed(() => comicStore.comicList)
  
  /**
   * 当前漫画详情
   */
  const currentComic = computed(() => comicStore.currentComic)
  
  /**
   * 是否正在加载
   */
  const isLoading = computed(() => loading.value || comicStore.loading)
  
  /**
   * 漫画总数
   */
  const totalCount = computed(() => comicStore.totalCount)
  
  /**
   * 显示数量
   */
  const displayCount = computed(() => comicStore.displayCount)
  
  /**
   * 是否有选中项
   */
  const hasSelection = computed(() => selectedComics.value.length > 0)
  
  /**
   * 选中数量
   */
  const selectedCount = computed(() => selectedComics.value.length)
  
  // ============ Actions ============
  
  /**
   * 获取漫画列表
   * @param {boolean} forceRefresh - 是否强制刷新
   */
  async function fetchComics(forceRefresh = false) {
    loading.value = true
    error.value = null
    
    try {
      const result = await comicStore.fetchComics(forceRefresh)
      return result
    } catch (err) {
      error.value = err.message
      return []
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 获取漫画详情
   * @param {string} id - 漫画ID
   * @param {boolean} forceRefresh - 是否强制刷新
   */
  async function fetchDetail(id, forceRefresh = false) {
    loading.value = true
    error.value = null
    
    try {
      const result = await comicStore.fetchComicDetail(id, forceRefresh)
      return result
    } catch (err) {
      error.value = err.message
      return null
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 获取图片列表
   * @param {string} id - 漫画ID
   * @param {boolean} forceRefresh - 是否强制刷新
   */
  async function fetchImages(id, forceRefresh = false) {
    try {
      const result = await comicStore.fetchImages(id, forceRefresh)
      return result
    } catch (err) {
      console.error('获取图片列表失败:', err)
      return null
    }
  }
  
  /**
   * 更新评分
   * @param {string} id - 漫画ID
   * @param {number} score - 评分
   */
  async function updateScore(id, score) {
    try {
      const result = await comicStore.updateScore(id, score)
      return result
    } catch (err) {
      console.error('更新评分失败:', err)
      return { success: false, message: err.message }
    }
  }
  
  /**
   * 保存阅读进度
   * @param {string} id - 漫画ID
   * @param {number} page - 页码
   */
  async function saveProgress(id, page) {
    try {
      const result = await comicStore.saveProgress(id, page)
      return result
    } catch (err) {
      console.error('保存进度失败:', err)
      return { success: false, message: err.message }
    }
  }
  
  /**
   * 选择漫画
   * @param {string} id - 漫画ID
   */
  function selectComic(id) {
    if (!selectedComics.value.includes(id)) {
      selectedComics.value.push(id)
    }
  }
  
  /**
   * 取消选择漫画
   * @param {string} id - 漫画ID
   */
  function deselectComic(id) {
    selectedComics.value = selectedComics.value.filter(comicId => comicId !== id)
  }
  
  /**
   * 切换选择状态
   * @param {string} id - 漫画ID
   */
  function toggleSelection(id) {
    if (selectedComics.value.includes(id)) {
      deselectComic(id)
    } else {
      selectComic(id)
    }
  }
  
  /**
   * 全选
   */
  function selectAll() {
    selectedComics.value = comics.value.map(comic => comic.id)
  }
  
  /**
   * 清空选择
   */
  function clearSelection() {
    selectedComics.value = []
  }
  
  /**
   * 按排序方式获取列表
   * @param {string} sortType - 排序类型
   */
  async function sortBy(sortType) {
    loading.value = true
    
    try {
      const result = await comicStore.sortComics(sortType)
      return result
    } catch (err) {
      error.value = err.message
      return []
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 清除筛选
   */
  function clearFilter() {
    comicStore.clearFilter()
  }
  
  /**
   * 获取阅读进度百分比
   * @param {Object} comic - 漫画对象
   */
  function getProgressPercent(comic) {
    if (!comic || !comic.total_page || comic.total_page === 0) return 0
    return Math.round((comic.current_page / comic.total_page) * 100)
  }
  
  /**
   * 格式化阅读进度
   * @param {Object} comic - 漫画对象
   */
  function formatProgress(comic) {
    if (!comic) return '0/0'
    const current = comic.current_page || 0
    const total = comic.total_page || 0
    return `${current}/${total}`
  }
  
  /**
   * 获取最后阅读时间
   * @param {Object} comic - 漫画对象
   */
  function getLastReadTime(comic) {
    if (!comic || !comic.last_read_time) return null
    
    const date = new Date(comic.last_read_time)
    const now = new Date()
    const diff = now - date
    
    // 小于1小时
    if (diff < 3600000) {
      const minutes = Math.floor(diff / 60000)
      return minutes <= 0 ? '刚刚' : `${minutes}分钟前`
    }
    
    // 小于24小时
    if (diff < 86400000) {
      const hours = Math.floor(diff / 3600000)
      return `${hours}小时前`
    }
    
    // 小于7天
    if (diff < 604800000) {
      const days = Math.floor(diff / 86400000)
      return `${days}天前`
    }
    
    // 其他情况显示日期
    return date.toLocaleDateString('zh-CN')
  }
  
  /**
   * 检查漫画是否已读
   * @param {Object} comic - 漫画对象
   */
  function isRead(comic) {
    return comic && comic.current_page > 0
  }
  
  /**
   * 检查漫画是否已读完
   * @param {Object} comic - 漫画对象
   */
  function isCompleted(comic) {
    return comic && comic.current_page >= comic.total_page
  }
  
  return {
    // State
    loading,
    error,
    selectedComics,
    
    // Getters
    comics,
    currentComic,
    isLoading,
    totalCount,
    displayCount,
    hasSelection,
    selectedCount,
    
    // Actions
    fetchComics,
    fetchDetail,
    fetchImages,
    updateScore,
    saveProgress,
    selectComic,
    deselectComic,
    toggleSelection,
    selectAll,
    clearSelection,
    sortBy,
    clearFilter,
    getProgressPercent,
    formatProgress,
    getLastReadTime,
    isRead,
    isCompleted
  }
}
