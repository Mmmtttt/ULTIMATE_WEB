import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { comicApi } from '@/api'
import { useCacheStore } from './cache'
import { SORT_TYPE } from '@/utils'

/**
 * 漫画管理 Store
 * 管理漫画列表、详情和相关操作
 */
export const useComicStore = defineStore('comic', () => {
  // ============ Dependencies ============
  const cacheStore = useCacheStore()
  
  // ============ State ============
  
  // 漫画列表
  const comics = ref([])
  
  // 当前选中的漫画
  const currentComic = ref(null)
  
  // 加载状态
  const loading = ref(false)
  
  // 错误信息
  const error = ref(null)
  
  // 当前排序方式
  const currentSort = ref(SORT_TYPE.CREATE_TIME)
  
  // 筛选结果
  const filteredComics = ref([])
  
  // 是否正在筛选
  const isFiltering = ref(false)
  
  // ============ Getters ============
  
  /**
   * 漫画列表（根据状态返回筛选结果或全部）
   */
  const comicList = computed(() => {
    return isFiltering.value ? filteredComics.value : comics.value
  })
  
  /**
   * 当前漫画信息
   */
  const currentComicInfo = computed(() => currentComic.value)
  
  /**
   * 漫画总数
   */
  const totalCount = computed(() => comics.value.length)
  
  /**
   * 当前显示数量
   */
  const displayCount = computed(() => comicList.value.length)
  
  /**
   * 根据ID获取漫画
   */
  const getComicById = computed(() => (id) => {
    return comics.value.find(comic => comic.id === id) || null
  })
  
  /**
   * 已读漫画数量
   */
  const readCount = computed(() => {
    return comics.value.filter(comic => comic.current_page > 0).length
  })
  
  /**
   * 已评分漫画数量
   */
  const scoredCount = computed(() => {
    return comics.value.filter(comic => comic.score > 0).length
  })
  
  // ============ Actions ============
  
  /**
   * 获取漫画列表
   * @param {boolean} forceRefresh - 是否强制刷新
   * @param {object} options - 可选参数
   * @param {string} options.sortType - 排序类型
   * @param {number} options.minScore - 最低评分
   * @param {number} options.maxScore - 最高评分
   * @returns {Array} 漫画列表
   */
  async function fetchComics(forceRefresh = false, options = {}) {
    if (!forceRefresh && Object.keys(options).length === 0) {
      const cached = cacheStore.getListCache()
      if (cached) {
        comics.value = cached
        return cached
      }
    }
    
    loading.value = true
    error.value = null
    
    try {
      console.log('[Comic] 获取漫画列表', options)
      const response = await comicApi.getList(options)
      comics.value = response.data || []
      
      if (Object.keys(options).length === 0) {
        cacheStore.setListCache(comics.value)
      }
      
      return comics.value
    } catch (err) {
      error.value = err.message
      console.error('[Comic] 获取漫画列表失败:', err)
      return []
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 获取漫画详情
   * @param {string} id - 漫画ID
   * @param {boolean} forceRefresh - 是否强制刷新
   * @returns {Object} 漫画详情
   */
  async function fetchComicDetail(id, forceRefresh = false) {
    // 检查缓存
    if (!forceRefresh) {
      const cached = cacheStore.getDetailCache(id)
      if (cached) {
        currentComic.value = cached
        return cached
      }
    }
    
    loading.value = true
    error.value = null
    
    try {
      console.log('[Comic] 获取漫画详情:', id)
      const response = await comicApi.getDetail(id)
      currentComic.value = response.data
      
      // 更新缓存
      cacheStore.setDetailCache(id, response.data)
      
      return response.data
    } catch (err) {
      error.value = err.message
      console.error('[Comic] 获取漫画详情失败:', err)
      return null
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 获取图片列表
   * @param {string} id - 漫画ID
   * @param {boolean} forceRefresh - 是否强制刷新
   * @returns {Array} 图片列表
   */
  async function fetchImages(id, forceRefresh = false) {
    // 检查缓存
    if (!forceRefresh) {
      const cached = cacheStore.getImagesCache(id)
      if (cached) {
        return cached
      }
    }
    
    try {
      console.log('[Comic] 获取图片列表:', id)
      const response = await comicApi.getImages(id)
      
      // 更新缓存
      cacheStore.setImagesCache(id, response.data)
      
      return response.data
    } catch (err) {
      console.error('[Comic] 获取图片列表失败:', err)
      return null
    }
  }
  
  /**
   * 更新评分
   * @param {string} id - 漫画ID
   * @param {number} score - 评分
   * @returns {Object} 结果
   */
  async function updateScore(id, score) {
    try {
      console.log('[Comic] 更新评分:', id, score)
      const response = await comicApi.updateScore(id, score)
      
      // 更新本地数据
      const comic = comics.value.find(c => c.id === id)
      if (comic) {
        comic.score = score
      }
      
      if (currentComic.value && currentComic.value.id === id) {
        currentComic.value.score = score
      }
      
      // 更新缓存
      cacheStore.setDetailCache(id, currentComic.value)
      
      return { success: true, data: response.data }
    } catch (err) {
      console.error('[Comic] 更新评分失败:', err)
      return { success: false, message: err.message }
    }
  }
  
  /**
   * 保存阅读进度
   * @param {string} id - 漫画ID
   * @param {number} page - 当前页码
   * @returns {Object} 结果
   */
  async function saveProgress(id, page) {
    try {
      console.log('[Comic] 保存阅读进度:', id, page)
      const response = await comicApi.saveProgress(id, page)
      
      // 更新本地数据
      const comic = comics.value.find(c => c.id === id)
      if (comic) {
        comic.current_page = page
        comic.last_read_time = response.data.last_read_time
      }
      
      if (currentComic.value && currentComic.value.id === id) {
        currentComic.value.current_page = page
        currentComic.value.last_read_time = response.data.last_read_time
      }
      
      // 更新缓存
      if (currentComic.value) {
        cacheStore.setDetailCache(id, currentComic.value)
      }
      
      return { success: true, data: response.data }
    } catch (err) {
      console.error('[Comic] 保存阅读进度失败:', err)
      return { success: false, message: err.message }
    }
  }
  
  /**
   * 搜索漫画
   * @param {string} keyword - 搜索关键词
   * @returns {Array} 搜索结果
   */
  async function searchComics(keyword) {
    if (!keyword || keyword.trim() === '') {
      isFiltering.value = false
      return comics.value
    }
    
    loading.value = true
    
    try {
      console.log('[Comic] 搜索漫画:', keyword)
      const response = await comicApi.search(keyword.trim())
      filteredComics.value = response.data || []
      isFiltering.value = true
      return filteredComics.value
    } catch (err) {
      console.error('[Comic] 搜索漫画失败:', err)
      return []
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 按标签筛选
   * @param {string[]} includeTags - 包含的标签ID
   * @param {string[]} excludeTags - 排除的标签ID
   * @returns {Array} 筛选结果
   */
  async function filterByTags(includeTags = [], excludeTags = []) {
    if (includeTags.length === 0 && excludeTags.length === 0) {
      isFiltering.value = false
      return comics.value
    }
    
    loading.value = true
    
    try {
      console.log('[Comic] 按标签筛选:', { includeTags, excludeTags })
      const response = await comicApi.filter(includeTags, excludeTags)
      filteredComics.value = response.data || []
      isFiltering.value = true
      return filteredComics.value
    } catch (err) {
      console.error('[Comic] 筛选漫画失败:', err)
      return []
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 按排序方式获取列表
   * @param {string} sortType - 排序类型
   * @returns {Array} 排序后的列表
   */
  async function sortComics(sortType) {
    currentSort.value = sortType
    
    loading.value = true
    
    try {
      console.log('[Comic] 按排序获取列表:', sortType)
      const response = await comicApi.getListBySort(sortType)
      comics.value = response.data || []
      
      // 更新缓存
      cacheStore.setListCache(comics.value)
      
      return comics.value
    } catch (err) {
      console.error('[Comic] 排序失败:', err)
      return []
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 清除筛选
   */
  function clearFilter() {
    isFiltering.value = false
    filteredComics.value = []
  }
  
  /**
   * 设置当前漫画
   * @param {Object} comic - 漫画对象
   */
  function setCurrentComic(comic) {
    currentComic.value = comic
  }
  
  /**
   * 清除当前漫画
   */
  function clearCurrentComic() {
    currentComic.value = null
  }
  
  return {
    // State
    comics,
    currentComic,
    loading,
    error,
    currentSort,
    filteredComics,
    isFiltering,
    
    // Getters
    comicList,
    currentComicInfo,
    totalCount,
    displayCount,
    getComicById,
    readCount,
    scoredCount,
    
    // Actions
    fetchComics,
    fetchComicDetail,
    fetchImages,
    updateScore,
    saveProgress,
    searchComics,
    filterByTags,
    sortComics,
    clearFilter,
    setCurrentComic,
    clearCurrentComic
  }
})
