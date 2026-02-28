import { ref, computed } from 'vue'
import { useCacheStore } from '@/stores'

/**
 * 缓存操作组合式函数
 * 封装缓存相关的操作逻辑
 */
export function useCache() {
  const cacheStore = useCacheStore()
  
  // ============ State ============
  
  // 缓存状态
  const isClearing = ref(false)
  
  // ============ Getters ============
  
  /**
   * 缓存统计信息
   */
  const stats = computed(() => cacheStore.cacheStats)
  
  /**
   * 列表缓存是否有效
   */
  const isListCacheValid = computed(() => cacheStore.isListCacheValid)
  
  /**
   * 标签缓存是否有效
   */
  const isTagsCacheValid = computed(() => cacheStore.isTagsCacheValid)
  
  /**
   * 缓存的漫画列表
   */
  const cachedList = computed(() => cacheStore.listCache)
  
  /**
   * 缓存的标签列表
   */
  const cachedTags = computed(() => cacheStore.tagsCache)
  
  // ============ Actions ============
  
  /**
   * 获取列表缓存
   * @returns {Array|null}
   */
  function getListCache() {
    return cacheStore.getListCache()
  }
  
  /**
   * 设置列表缓存
   * @param {Array} data
   */
  function setListCache(data) {
    cacheStore.setListCache(data)
  }
  
  /**
   * 获取详情缓存
   * @param {string} id
   * @returns {Object|null}
   */
  function getDetailCache(id) {
    return cacheStore.getDetailCache(id)
  }
  
  /**
   * 设置详情缓存
   * @param {string} id
   * @param {Object} data
   */
  function setDetailCache(id, data) {
    cacheStore.setDetailCache(id, data)
  }
  
  /**
   * 获取图片列表缓存
   * @param {string} id
   * @returns {Array|null}
   */
  function getImagesCache(id) {
    return cacheStore.getImagesCache(id)
  }
  
  /**
   * 设置图片列表缓存
   * @param {string} id
   * @param {Array} data
   */
  function setImagesCache(id, data) {
    cacheStore.setImagesCache(id, data)
  }
  
  /**
   * 获取标签缓存
   * @returns {Array|null}
   */
  function getTagsCache() {
    return cacheStore.getTagsCache()
  }
  
  /**
   * 设置标签缓存
   * @param {Array} data
   */
  function setTagsCache(data) {
    cacheStore.setTagsCache(data)
  }
  
  /**
   * 清除所有缓存
   */
  function clearAllCache() {
    isClearing.value = true
    
    try {
      cacheStore.clearCache('all')
      console.log('[useCache] 清除所有缓存')
    } finally {
      isClearing.value = false
    }
  }
  
  /**
   * 清除列表缓存
   */
  function clearListCache() {
    cacheStore.clearCache('list')
    console.log('[useCache] 清除列表缓存')
  }
  
  /**
   * 清除详情缓存
   * @param {string} id - 特定漫画ID，不传则清除所有
   */
  function clearDetailCache(id = null) {
    cacheStore.clearCache('detail', id)
    console.log('[useCache] 清除详情缓存', id || '全部')
  }
  
  /**
   * 清除图片缓存
   * @param {string} id - 特定漫画ID，不传则清除所有
   */
  function clearImagesCache(id = null) {
    cacheStore.clearCache('images', id)
    console.log('[useCache] 清除图片缓存', id || '全部')
  }
  
  /**
   * 清除标签缓存
   */
  function clearTagsCache() {
    cacheStore.clearCache('tags')
    console.log('[useCache] 清除标签缓存')
  }
  
  /**
   * 清除过期缓存
   */
  function clearExpiredCache() {
    cacheStore.clearExpiredCache()
    console.log('[useCache] 清除过期缓存')
  }
  
  /**
   * 清除漫画相关缓存（详情+图片）
   * @param {string} id - 漫画ID
   */
  function clearComicCache(id) {
    clearDetailCache(id)
    clearImagesCache(id)
    console.log('[useCache] 清除漫画缓存', id)
  }
  
  /**
   * 刷新缓存
   * 清除所有缓存并重新获取
   */
  async function refreshCache() {
    isClearing.value = true
    
    try {
      clearAllCache()
      console.log('[useCache] 刷新缓存完成')
    } finally {
      isClearing.value = false
    }
  }
  
  /**
   * 获取缓存大小估算
   */
  function getCacheSize() {
    const stats = cacheStore.cacheStats
    let size = 0
    
    // 估算列表缓存大小
    if (stats.list === 'cached') {
      size += 100 // KB
    }
    
    // 估算详情缓存大小
    size += stats.detailCount * 10 // 每个详情约10KB
    
    // 估算图片缓存大小
    size += stats.imagesCount * 5 // 每个图片列表约5KB
    
    // 估算标签缓存大小
    if (stats.tags === 'cached') {
      size += 50 // KB
    }
    
    return {
      size,
      unit: 'KB',
      formatted: size < 1024 ? `${size} KB` : `${(size / 1024).toFixed(2)} MB`
    }
  }
  
  return {
    // State
    isClearing,
    
    // Getters
    stats,
    isListCacheValid,
    isTagsCacheValid,
    cachedList,
    cachedTags,
    
    // Actions
    getListCache,
    setListCache,
    getDetailCache,
    setDetailCache,
    getImagesCache,
    setImagesCache,
    getTagsCache,
    setTagsCache,
    clearAllCache,
    clearListCache,
    clearDetailCache,
    clearImagesCache,
    clearTagsCache,
    clearExpiredCache,
    clearComicCache,
    refreshCache,
    getCacheSize
  }
}
