import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { CACHE_EXPIRY } from '@/utils'

/**
 * 缓存管理 Store
 * 统一管理应用中的各类缓存数据
 */
export const useCacheStore = defineStore('cache', () => {
  // ============ State ============

  // 漫画列表缓存
  const listCache = ref(null)
  const listCacheTime = ref(0)

  // 漫画详情缓存（按ID存储）
  const detailCache = ref({})
  const detailCacheTime = ref({})

  // 图片列表缓存（按漫画ID存储）
  const imagesCache = ref({})
  const imagesCacheTime = ref({})

  // 标签列表缓存
  const tagsCache = ref(null)
  const tagsCacheTime = ref(0)

  // 推荐漫画列表缓存
  const recommendationListCache = ref(null)
  const recommendationListCacheTime = ref(0)

  // 推荐漫画详情缓存（按ID存储）
  const recommendationDetailCache = ref({})
  const recommendationDetailCacheTime = ref({})

  // 作者列表缓存
  const authorsCache = ref(null)
  const authorsCacheTime = ref(0)
  
  // ============ Getters ============
  
  /**
   * 缓存状态统计
   */
  const cacheStats = computed(() => ({
    list: listCache.value ? 'cached' : 'empty',
    detailCount: Object.keys(detailCache.value).length,
    imagesCount: Object.keys(imagesCache.value).length,
    tags: tagsCache.value ? 'cached' : 'empty'
  }))
  
  /**
   * 检查列表缓存是否有效
   */
  const isListCacheValid = computed(() => {
    if (!listCache.value) return false
    return Date.now() - listCacheTime.value < CACHE_EXPIRY.COMIC_LIST
  })
  
  /**
   * 检查标签缓存是否有效
   */
  const isTagsCacheValid = computed(() => {
    if (!tagsCache.value) return false
    return Date.now() - tagsCacheTime.value < CACHE_EXPIRY.TAGS
  })

  /**
   * 检查推荐列表缓存是否有效
   */
  const isRecommendationListCacheValid = computed(() => {
    if (!recommendationListCache.value) return false
    return Date.now() - recommendationListCacheTime.value < CACHE_EXPIRY.COMIC_LIST
  })

  /**
   * 检查作者列表缓存是否有效
   */
  const isAuthorsCacheValid = computed(() => {
    if (!authorsCache.value) return false
    return Date.now() - authorsCacheTime.value < CACHE_EXPIRY.AUTHORS
  })
  
  // ============ Actions ============
  
  /**
   * 获取列表缓存
   * @returns {Array|null} 缓存数据或null
   */
  function getListCache() {
    if (isListCacheValid.value) {
      console.log('[Cache] 使用缓存的漫画列表', { 
        age: Math.round((Date.now() - listCacheTime.value) / 1000) + 's' 
      })
      return listCache.value
    }
    return null
  }
  
  /**
   * 设置列表缓存
   * @param {Array} data - 漫画列表数据
   */
  function setListCache(data) {
    listCache.value = data
    listCacheTime.value = Date.now()
    console.log('[Cache] 缓存漫画列表')
  }
  
  /**
   * 获取详情缓存
   * @param {string} id - 漫画ID
   * @returns {Object|null} 缓存数据或null
   */
  function getDetailCache(id) {
    const cache = detailCache.value[id]
    const cacheTime = detailCacheTime.value[id]
    
    if (cache && cacheTime) {
      const age = Date.now() - cacheTime
      if (age < CACHE_EXPIRY.COMIC_DETAIL) {
        console.log('[Cache] 使用缓存的漫画详情', { 
          id, 
          age: Math.round(age / 1000) + 's' 
        })
        return cache
      }
    }
    return null
  }
  
  /**
   * 设置详情缓存
   * @param {string} id - 漫画ID
   * @param {Object} data - 漫画详情数据
   */
  function setDetailCache(id, data) {
    detailCache.value[id] = data
    detailCacheTime.value[id] = Date.now()
    console.log('[Cache] 缓存漫画详情', { id })
  }
  
  /**
   * 获取图片列表缓存
   * @param {string} id - 漫画ID
   * @returns {Array|null} 缓存数据或null
   */
  function getImagesCache(id) {
    const cache = imagesCache.value[id]
    const cacheTime = imagesCacheTime.value[id]
    
    if (cache && cacheTime) {
      const age = Date.now() - cacheTime
      if (age < CACHE_EXPIRY.IMAGES) {
        console.log('[Cache] 使用缓存的图片列表', { 
          id, 
          age: Math.round(age / 1000) + 's' 
        })
        return cache
      }
    }
    return null
  }
  
  /**
   * 设置图片列表缓存
   * @param {string} id - 漫画ID
   * @param {Array} data - 图片列表数据
   */
  function setImagesCache(id, data) {
    imagesCache.value[id] = data
    imagesCacheTime.value[id] = Date.now()
    console.log('[Cache] 缓存图片列表', { id })
  }
  
  /**
   * 获取标签缓存
   * @returns {Array|null} 缓存数据或null
   */
  function getTagsCache() {
    if (isTagsCacheValid.value) {
      console.log('[Cache] 使用缓存的标签列表', { 
        age: Math.round((Date.now() - tagsCacheTime.value) / 1000) + 's' 
      })
      return tagsCache.value
    }
    return null
  }
  
  /**
   * 设置标签缓存
   * @param {Array} data - 标签列表数据
   */
  function setTagsCache(data) {
    tagsCache.value = data
    tagsCacheTime.value = Date.now()
    console.log('[Cache] 缓存标签列表')
  }

  // ============ 作者列表缓存操作 ============

  /**
   * 获取作者列表缓存
   * @returns {Array|null} 缓存数据或null
   */
  function getAuthorsCache() {
    if (isAuthorsCacheValid.value) {
      console.log('[Cache] 使用缓存的作者列表', {
        age: Math.round((Date.now() - authorsCacheTime.value) / 1000) + 's'
      })
      return authorsCache.value
    }
    return null
  }

  /**
   * 设置作者列表缓存
   * @param {Array} data - 作者列表数据
   */
  function setAuthorsCache(data) {
    authorsCache.value = data
    authorsCacheTime.value = Date.now()
    console.log('[Cache] 缓存作者列表')
  }

  /**
   * 清除作者列表缓存
   */
  function clearAuthorsCache() {
    authorsCache.value = null
    authorsCacheTime.value = 0
    console.log('[Cache] 清除作者列表缓存')
  }

  // ============ 推荐漫画缓存操作 ============

  /**
   * 获取推荐列表缓存
   * @returns {Array|null} 缓存数据或null
   */
  function getRecommendationListCache() {
    if (isRecommendationListCacheValid.value) {
      console.log('[Cache] 使用缓存的推荐列表', {
        age: Math.round((Date.now() - recommendationListCacheTime.value) / 1000) + 's'
      })
      return recommendationListCache.value
    }
    return null
  }

  /**
   * 设置推荐列表缓存
   * @param {Array} data - 推荐漫画列表数据
   */
  function setRecommendationListCache(data) {
    recommendationListCache.value = data
    recommendationListCacheTime.value = Date.now()
    console.log('[Cache] 缓存推荐列表')
  }

  /**
   * 获取推荐详情缓存
   * @param {string} id - 推荐漫画ID
   * @returns {Object|null} 缓存数据或null
   */
  function getRecommendationDetailCache(id) {
    const cache = recommendationDetailCache.value[id]
    const cacheTime = recommendationDetailCacheTime.value[id]

    if (cache && cacheTime) {
      const age = Date.now() - cacheTime
      if (age < CACHE_EXPIRY.COMIC_DETAIL) {
        console.log('[Cache] 使用缓存的推荐详情', {
          id,
          age: Math.round(age / 1000) + 's'
        })
        return cache
      }
    }
    return null
  }

  /**
   * 设置推荐详情缓存
   * @param {string} id - 推荐漫画ID
   * @param {Object} data - 推荐漫画详情数据
   */
  function setRecommendationDetailCache(id, data) {
    recommendationDetailCache.value[id] = data
    recommendationDetailCacheTime.value[id] = Date.now()
    console.log('[Cache] 缓存推荐详情', { id })
  }

  /**
   * 清除推荐详情缓存
   * @param {string} id - 推荐漫画ID
   */
  function clearRecommendationDetailCache(id) {
    delete recommendationDetailCache.value[id]
    delete recommendationDetailCacheTime.value[id]
    console.log('[Cache] 清除推荐详情缓存', { id })
  }
  
  /**
   * 清除缓存
   * @param {string} type - 缓存类型（all/list/detail/images/tags）
   * @param {string} id - 特定ID（用于detail/images）
   */
  function clearCache(type = 'all', id = null) {
    console.log('[Cache] 清除缓存', { type, id })
    
    if (type === 'all' || type === 'list') {
      listCache.value = null
      listCacheTime.value = 0
    }
    
    if (type === 'all' || type === 'detail') {
      if (id) {
        delete detailCache.value[id]
        delete detailCacheTime.value[id]
      } else {
        detailCache.value = {}
        detailCacheTime.value = {}
      }
    }
    
    if (type === 'all' || type === 'images') {
      if (id) {
        delete imagesCache.value[id]
        delete imagesCacheTime.value[id]
      } else {
        imagesCache.value = {}
        imagesCacheTime.value = {}
      }
    }
    
    if (type === 'all' || type === 'tags') {
      tagsCache.value = null
      tagsCacheTime.value = 0
    }
  }
  
  /**
   * 清除过期缓存
   */
  function clearExpiredCache() {
    const now = Date.now()
    
    // 检查列表缓存
    if (listCache.value && now - listCacheTime.value >= CACHE_EXPIRY.COMIC_LIST) {
      listCache.value = null
      listCacheTime.value = 0
    }
    
    // 检查详情缓存
    Object.keys(detailCacheTime.value).forEach(id => {
      if (now - detailCacheTime.value[id] >= CACHE_EXPIRY.COMIC_DETAIL) {
        delete detailCache.value[id]
        delete detailCacheTime.value[id]
      }
    })
    
    // 检查图片缓存
    Object.keys(imagesCacheTime.value).forEach(id => {
      if (now - imagesCacheTime.value[id] >= CACHE_EXPIRY.IMAGES) {
        delete imagesCache.value[id]
        delete imagesCacheTime.value[id]
      }
    })
    
    // 检查标签缓存
    if (tagsCache.value && now - tagsCacheTime.value >= CACHE_EXPIRY.TAGS) {
      tagsCache.value = null
      tagsCacheTime.value = 0
    }
  }
  
  return {
    // State (只读)
    listCache: computed(() => listCache.value),
    detailCache: computed(() => detailCache.value),
    imagesCache: computed(() => imagesCache.value),
    tagsCache: computed(() => tagsCache.value),
    recommendationListCache: computed(() => recommendationListCache.value),
    recommendationDetailCache: computed(() => recommendationDetailCache.value),
    authorsCache: computed(() => authorsCache.value),

    // Getters
    cacheStats,
    isListCacheValid,
    isTagsCacheValid,
    isRecommendationListCacheValid,
    isAuthorsCacheValid,

    // Actions
    getListCache,
    setListCache,
    getDetailCache,
    setDetailCache,
    getImagesCache,
    setImagesCache,
    getTagsCache,
    setTagsCache,
    getAuthorsCache,
    setAuthorsCache,
    clearAuthorsCache,
    getRecommendationListCache,
    setRecommendationListCache,
    getRecommendationDetailCache,
    setRecommendationDetailCache,
    clearRecommendationDetailCache,
    clearCache,
    clearExpiredCache
  }
})
