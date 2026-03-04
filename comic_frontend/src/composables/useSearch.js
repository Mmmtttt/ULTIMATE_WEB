import { ref, computed, watch } from 'vue'
import { useComicStore, useTagStore } from '@/stores'
import { debounce } from '@/utils'

/**
 * 搜索筛选组合式函数
 * 封装搜索、筛选、排序逻辑
 */
export function useSearch() {
  const comicStore = useComicStore()
  const tagStore = useTagStore()
  
  // ============ State ============
  
  // 搜索关键词
  const keyword = ref('')
  
  // 包含标签
  const includeTags = ref([])
  
  // 排除标签
  const excludeTags = ref([])
  
  // 排序方式
  const sortType = ref('create_time')
  
  // 加载状态
  const loading = ref(false)
  
  // 是否显示筛选面板
  const showFilterPanel = ref(false)
  
  // ============ Getters ============
  
  /**
   * 搜索结果
   */
  const results = computed(() => comicStore.comicList)
  
  /**
   * 结果数量
   */
  const resultCount = computed(() => results.value.length)
  
  /**
   * 是否有搜索结果
   */
  const hasResults = computed(() => resultCount.value > 0)
  
  /**
   * 是否正在筛选
   */
  const isFiltering = computed(() => 
    keyword.value || 
    includeTags.value.length > 0 || 
    excludeTags.value.length > 0
  )
  
  /**
   * 标签列表
   */
  const tags = computed(() => tagStore.tags)
  
  /**
   * 已选标签对象
   */
  const selectedIncludeTags = computed(() => {
    return includeTags.value.map(id => tagStore.getTagById(id)).filter(Boolean)
  })
  
  const selectedExcludeTags = computed(() => {
    return excludeTags.value.map(id => tagStore.getTagById(id)).filter(Boolean)
  })
  
  // ============ Actions ============
  
  /**
   * 执行搜索
   */
  async function search() {
    if (!keyword.value.trim()) {
      comicStore.clearFilter()
      return
    }
    
    loading.value = true
    
    try {
      await comicStore.searchComics(keyword.value)
    } catch (error) {
      console.error('搜索失败:', error)
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 防抖搜索
   */
  const debouncedSearch = debounce(search, 300)
  
  /**
   * 按标签筛选
   */
  async function filterByTags() {
    loading.value = true
    
    try {
      await comicStore.filterByTags(includeTags.value, excludeTags.value)
    } catch (error) {
      console.error('筛选失败:', error)
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 排序
   */
  async function sort(type) {
    sortType.value = type
    loading.value = true
    
    try {
      await comicStore.sortComics(type)
    } catch (error) {
      console.error('排序失败:', error)
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 添加包含标签
   * @param {string} tagId - 标签ID
   */
  function addIncludeTag(tagId) {
    if (!includeTags.value.includes(tagId)) {
      includeTags.value.push(tagId)
      // 从排除标签中移除
      excludeTags.value = excludeTags.value.filter(id => id !== tagId)
    }
  }
  
  /**
   * 添加排除标签
   * @param {string} tagId - 标签ID
   */
  function addExcludeTag(tagId) {
    if (!excludeTags.value.includes(tagId)) {
      excludeTags.value.push(tagId)
      // 从包含标签中移除
      includeTags.value = includeTags.value.filter(id => id !== tagId)
    }
  }
  
  /**
   * 移除包含标签
   * @param {string} tagId - 标签ID
   */
  function removeIncludeTag(tagId) {
    includeTags.value = includeTags.value.filter(id => id !== tagId)
  }
  
  /**
   * 移除排除标签
   * @param {string} tagId - 标签ID
   */
  function removeExcludeTag(tagId) {
    excludeTags.value = excludeTags.value.filter(id => id !== tagId)
  }
  
  /**
   * 切换标签选择状态
   * @param {string} tagId - 标签ID
   */
  function toggleTag(tagId) {
    if (includeTags.value.includes(tagId)) {
      removeIncludeTag(tagId)
    } else if (excludeTags.value.includes(tagId)) {
      removeExcludeTag(tagId)
    } else {
      addIncludeTag(tagId)
    }
  }
  
  /**
   * 清除搜索
   */
  function clearSearch() {
    keyword.value = ''
    comicStore.clearFilter()
  }
  
  /**
   * 清除所有筛选条件
   */
  function clearAllFilters() {
    keyword.value = ''
    includeTags.value = []
    excludeTags.value = []
    comicStore.clearFilter()
  }
  
  /**
   * 显示筛选面板
   */
  function showFilter() {
    showFilterPanel.value = true
  }
  
  /**
   * 隐藏筛选面板
   */
  function hideFilter() {
    showFilterPanel.value = false
  }
  
  /**
   * 切换筛选面板
   */
  function toggleFilter() {
    showFilterPanel.value = !showFilterPanel.value
  }
  
  /**
   * 应用筛选
   */
  async function applyFilter() {
    if (keyword.value) {
      await search()
    } else if (includeTags.value.length > 0 || excludeTags.value.length > 0) {
      await filterByTags()
    } else {
      comicStore.clearFilter()
    }
    hideFilter()
  }
  
  /**
   * 获取筛选描述
   */
  const filterDescription = computed(() => {
    const parts = []
    
    if (keyword.value) {
      parts.push(`关键词: "${keyword.value}"`)
    }
    
    if (includeTags.value.length > 0) {
      const tagNames = selectedIncludeTags.value.map(tag => tag.name).join(', ')
      parts.push(`包含标签: ${tagNames}`)
    }
    
    if (excludeTags.value.length > 0) {
      const tagNames = selectedExcludeTags.value.map(tag => tag.name).join(', ')
      parts.push(`排除标签: ${tagNames}`)
    }
    
    return parts.join(' | ')
  })
  
  /**
   * 初始化
   */
  async function init() {
    // 获取标签列表
    if (tagStore.tags.length === 0) {
      await tagStore.fetchTags('comic')
    }
    
    // 获取漫画列表
    if (comicStore.comics.length === 0) {
      await comicStore.fetchComics()
    }
  }
  
  // 监听标签变化，自动应用筛选
  watch([includeTags, excludeTags], async () => {
    if (includeTags.value.length > 0 || excludeTags.value.length > 0) {
      await filterByTags()
    } else if (!keyword.value) {
      comicStore.clearFilter()
    }
  }, { deep: true })
  
  return {
    // State
    keyword,
    includeTags,
    excludeTags,
    sortType,
    loading,
    showFilterPanel,
    
    // Getters
    results,
    resultCount,
    hasResults,
    isFiltering,
    tags,
    selectedIncludeTags,
    selectedExcludeTags,
    filterDescription,
    
    // Actions
    search,
    debouncedSearch,
    filterByTags,
    sort,
    addIncludeTag,
    addExcludeTag,
    removeIncludeTag,
    removeExcludeTag,
    toggleTag,
    clearSearch,
    clearAllFilters,
    showFilter,
    hideFilter,
    toggleFilter,
    applyFilter,
    init
  }
}
