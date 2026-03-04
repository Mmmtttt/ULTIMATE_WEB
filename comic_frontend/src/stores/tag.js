import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { tagApi, comicApi } from '@/api'
import { useCacheStore } from './cache'
import { validateTagName } from '@/utils'

/**
 * 标签管理 Store
 * 管理标签列表和标签相关操作
 */
export const useTagStore = defineStore('tag', () => {
  // ============ Dependencies ============
  const cacheStore = useCacheStore()
  
  // ============ State ============
  
  // 漫画标签列表
  const tags = ref([])
  
  // 视频标签列表
  const videoTags = ref([])
  
  // 当前选中的标签
  const selectedTags = ref([])
  
  // 加载状态
  const loading = ref(false)
  
  // 错误信息
  const error = ref(null)
  
  // ============ Getters ============
  
  /**
   * 标签列表（按名称排序）
   */
  const sortedTags = computed(() => {
    return [...tags.value].sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
  })
  
  /**
   * 标签数量
   */
  const tagCount = computed(() => tags.value.length)
  
  /**
   * 标签ID到名称的映射
   */
  const tagNameMap = computed(() => {
    const map = {}
    tags.value.forEach(tag => {
      map[tag.id] = tag.name
    })
    return map
  })
  
  /**
   * 根据ID获取标签（漫画标签）
   */
  const getTagById = computed(() => (id) => {
    return tags.value.find(tag => tag.id === id) || null
  })
  
  /**
   * 根据ID获取视频标签
   */
  const getVideoTagById = computed(() => (id) => {
    return videoTags.value.find(tag => tag.id === id) || null
  })
  
  /**
   * 选中的标签对象列表
   */
  const selectedTagObjects = computed(() => {
    return tags.value.filter(tag => selectedTags.value.includes(tag.id))
  })
  
  // ============ Actions ============
  
  /**
   * 获取标签列表
   * @param {string} contentType - 内容类型 'comic' 或 'video'
   * @param {boolean} forceRefresh - 是否强制刷新
   * @returns {Array} 标签列表
   */
  async function fetchTags(contentType = 'comic', forceRefresh = false) {
    // 检查缓存
    if (!forceRefresh) {
      const cached = contentType === 'video' 
        ? cacheStore.getVideoTagsCache() 
        : cacheStore.getTagsCache()
      if (cached) {
        if (contentType === 'video') {
          videoTags.value = cached
        } else {
          tags.value = cached
        }
        return cached
      }
    }
    
    loading.value = true
    error.value = null
    
    try {
      console.log('[Tag] 获取标签列表', { contentType })
      const response = await tagApi.list(contentType)
      const resultTags = response.data || []
      
      if (contentType === 'video') {
        videoTags.value = resultTags
        cacheStore.setVideoTagsCache(resultTags)
      } else {
        tags.value = resultTags
        cacheStore.setTagsCache(resultTags)
      }
      
      return resultTags
    } catch (err) {
      error.value = err.message
      console.error('[Tag] 获取标签列表失败:', err)
      return []
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 添加标签
   * @param {string} tagName - 标签名称
   * @param {string} contentType - 内容类型 'comic' 或 'video'
   * @returns {Object} 结果
   */
  async function addTag(tagName, contentType = 'comic') {
    // 校验
    const validation = validateTagName(tagName)
    if (!validation.valid) {
      return { success: false, message: validation.message }
    }
    
    // 检查是否已存在
    const currentTags = contentType === 'video' ? videoTags.value : tags.value
    const exists = currentTags.some(tag => tag.name === tagName.trim())
    if (exists) {
      return { success: false, message: '标签已存在' }
    }
    
    loading.value = true
    
    try {
      console.log('[Tag] 添加标签:', tagName, contentType)
      const response = await tagApi.add(tagName.trim(), contentType)
      
      // 刷新标签列表
      await fetchTags(contentType, true)
      
      // 清除标签缓存
      cacheStore.clearCache(contentType === 'video' ? 'video-tags' : 'tags')
      
      return { success: true, data: response.data }
    } catch (err) {
      console.error('[Tag] 添加标签失败:', err)
      return { success: false, message: err.message }
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 编辑标签
   * @param {string} tagId - 标签ID
   * @param {string} newName - 新名称
   * @returns {Object} 结果
   */
  async function editTag(tagId, newName) {
    // 校验
    const validation = validateTagName(newName)
    if (!validation.valid) {
      return { success: false, message: validation.message }
    }
    
    // 检查是否已存在
    const exists = tags.value.some(tag => tag.name === newName.trim() && tag.id !== tagId)
    if (exists) {
      return { success: false, message: '标签名称已存在' }
    }
    
    loading.value = true
    
    try {
      console.log('[Tag] 编辑标签:', tagId, newName)
      await tagApi.edit(tagId, newName.trim())
      
      // 刷新标签列表
      await fetchTags('comic', true)
      
      // 清除相关缓存
      cacheStore.clearCache('tags')
      cacheStore.clearCache('detail')
      
      return { success: true }
    } catch (err) {
      console.error('[Tag] 编辑标签失败:', err)
      return { success: false, message: err.message }
    } finally {
      loading.value = false
    }
  }

  /**
   * 编辑视频标签
   * @param {string} tagId - 标签ID
   * @param {string} newName - 新名称
   * @returns {Object} 结果
   */
  async function editVideoTag(tagId, newName) {
    // 校验
    const validation = validateTagName(newName)
    if (!validation.valid) {
      return { success: false, message: validation.message }
    }
    
    // 检查是否已存在
    const exists = videoTags.value.some(tag => tag.name === newName.trim() && tag.id !== tagId)
    if (exists) {
      return { success: false, message: '标签名称已存在' }
    }
    
    loading.value = true
    
    try {
      console.log('[Tag] 编辑视频标签:', tagId, newName)
      await tagApi.edit(tagId, newName.trim())
      
      // 刷新标签列表
      await fetchTags('video', true)
      
      // 清除相关缓存
      cacheStore.clearCache('video-tags')
      cacheStore.clearCache('video-detail')
      
      return { success: true }
    } catch (err) {
      console.error('[Tag] 编辑视频标签失败:', err)
      return { success: false, message: err.message }
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 删除标签
   * @param {string} tagId - 标签ID
   * @returns {Object} 结果
   */
  async function deleteTag(tagId) {
    loading.value = true
    
    try {
      console.log('[Tag] 删除标签:', tagId)
      await tagApi.delete(tagId)
      
      // 刷新标签列表
      await fetchTags(true)
      
      // 清除相关缓存
      cacheStore.clearCache('tags')
      cacheStore.clearCache('detail')
      
      // 从选中列表中移除
      selectedTags.value = selectedTags.value.filter(id => id !== tagId)
      
      return { success: true }
    } catch (err) {
      console.error('[Tag] 删除标签失败:', err)
      return { success: false, message: err.message }
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 选择标签
   * @param {string} tagId - 标签ID
   */
  function selectTag(tagId) {
    if (!selectedTags.value.includes(tagId)) {
      selectedTags.value.push(tagId)
    }
  }
  
  /**
   * 取消选择标签
   * @param {string} tagId - 标签ID
   */
  function deselectTag(tagId) {
    selectedTags.value = selectedTags.value.filter(id => id !== tagId)
  }
  
  /**
   * 切换标签选择
   * @param {string} tagId - 标签ID
   */
  function toggleTagSelection(tagId) {
    if (selectedTags.value.includes(tagId)) {
      deselectTag(tagId)
    } else {
      selectTag(tagId)
    }
  }
  
  /**
   * 清空选中标签
   */
  function clearSelectedTags() {
    selectedTags.value = []
  }
  
  /**
   * 全选标签
   */
  function selectAllTags() {
    selectedTags.value = tags.value.map(tag => tag.id)
  }
  
  /**
   * 绑定标签到漫画
   * @param {string} comicId - 漫画ID
   * @param {string[]} tagIds - 标签ID数组
   * @returns {Object} 结果
   */
  async function bindTagsToComic(comicId, tagIds) {
    try {
      console.log('[Tag] 绑定标签到漫画:', comicId, tagIds)
      await comicApi.bindTags(comicId, tagIds)
      
      // 清除详情缓存
      cacheStore.clearCache('detail', comicId)
      
      return { success: true }
    } catch (err) {
      console.error('[Tag] 绑定标签失败:', err)
      return { success: false, message: err.message }
    }
  }
  
  /**
   * 批量添加标签到漫画
   * @param {string[]} comicIds - 漫画ID数组
   * @param {string[]} tagIds - 标签ID数组
   * @returns {Object} 结果
   */
  async function batchAddTags(comicIds, tagIds) {
    try {
      console.log('[Tag] 批量添加标签:', comicIds, tagIds)
      await comicApi.batchAddTags(comicIds, tagIds)
      
      // 清除详情缓存
      comicIds.forEach(id => cacheStore.clearCache('detail', id))
      
      return { success: true }
    } catch (err) {
      console.error('[Tag] 批量添加标签失败:', err)
      return { success: false, message: err.message }
    }
  }
  
  /**
   * 批量移除标签
   * @param {string[]} comicIds - 漫画ID数组
   * @param {string[]} tagIds - 标签ID数组
   * @returns {Object} 结果
   */
  async function batchRemoveTags(comicIds, tagIds) {
    try {
      console.log('[Tag] 批量移除标签:', comicIds, tagIds)
      await comicApi.batchRemoveTags(comicIds, tagIds)
      
      // 清除详情缓存
      comicIds.forEach(id => cacheStore.clearCache('detail', id))
      
      return { success: true }
    } catch (err) {
      console.error('[Tag] 批量移除标签失败:', err)
      return { success: false, message: err.message }
    }
  }
  
  return {
    // State
    tags,
    videoTags,
    selectedTags,
    loading,
    error,
    
    // Getters
    sortedTags,
    tagCount,
    tagNameMap,
    getTagById,
    getVideoTagById,
    selectedTagObjects,
    
    // Actions
    fetchTags,
    addTag,
    editTag,
    editVideoTag,
    deleteTag,
    selectTag,
    deselectTag,
    toggleTagSelection,
    clearSelectedTags,
    selectAllTags,
    bindTagsToComic,
    batchAddTags,
    batchRemoveTags
  }
})
