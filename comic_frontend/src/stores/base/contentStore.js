import { ref, computed } from 'vue'

export function createContentStore(options) {
  const {
    api,
    contentType,
    cacheStore = null,
    getCacheKey = (type) => `${contentType}_${type}`
  } = options

  return () => {
    const items = ref([])
    const currentItem = ref(null)
    const loading = ref(false)
    const error = ref(null)
    const currentSort = ref(null)
    const filteredItems = ref([])
    const isFiltering = ref(false)
    const trashList = ref([])

    const itemList = computed(() => isFiltering.value ? filteredItems.value : items.value)
    const totalCount = computed(() => items.value.length)
    const displayCount = computed(() => itemList.value.length)

    function getItemById(id) {
      return items.value.find(item => item.id === id) || null
    }

    async function fetchList(params = {}, forceRefresh = false) {
      if (!forceRefresh && items.value.length > 0 && Object.keys(params).length === 0) {
        return items.value
      }

      loading.value = true
      error.value = null

      try {
        const response = await api.getList(params)
        const data = response.data || response
        items.value = Array.isArray(data) ? data : (data.items || [])
        return items.value
      } catch (err) {
        error.value = err.message
        console.error(`[${contentType}] 获取列表失败:`, err)
        return []
      } finally {
        loading.value = false
      }
    }

    async function fetchDetail(id, forceRefresh = false) {
      loading.value = true
      error.value = null

      try {
        const response = await api.getDetail(id)
        currentItem.value = response.data || response
        return currentItem.value
      } catch (err) {
        error.value = err.message
        console.error(`[${contentType}] 获取详情失败:`, err)
        return null
      } finally {
        loading.value = false
      }
    }

    async function updateScore(id, score) {
      try {
        const response = await api.updateScore(id, score)
        const success = response.code === 200 || response.success

        if (success) {
          const item = items.value.find(i => i.id === id)
          if (item) item.score = score
          if (currentItem.value?.id === id) {
            currentItem.value.score = score
          }
        }
        return success
      } catch (err) {
        console.error(`[${contentType}] 更新评分失败:`, err)
        return false
      }
    }

    async function saveProgress(id, progress) {
      try {
        const response = await api.saveProgress(id, progress)
        const success = response.code === 200 || response.success

        if (success) {
          const item = items.value.find(i => i.id === id)
          if (item) {
            item.current_page = progress
            item.progress = progress
          }
          if (currentItem.value?.id === id) {
            currentItem.value.current_page = progress
            currentItem.value.progress = progress
          }
        }
        return success
      } catch (err) {
        console.error(`[${contentType}] 保存进度失败:`, err)
        return false
      }
    }

    async function moveToTrash(id) {
      try {
        const response = await api.moveToTrash(id)
        const success = response.code === 200 || response.success

        if (success) {
          items.value = items.value.filter(i => i.id !== id)
          if (currentItem.value?.id === id) {
            currentItem.value = null
          }
        }
        return success
      } catch (err) {
        console.error(`[${contentType}] 移入回收站失败:`, err)
        return false
      }
    }

    async function batchMoveToTrash(ids) {
      try {
        const response = await api.batchMoveToTrash(ids)
        const success = response.code === 200 || response.success

        if (success) {
          items.value = items.value.filter(i => !ids.includes(i.id))
        }
        return success
      } catch (err) {
        console.error(`[${contentType}] 批量移入回收站失败:`, err)
        return false
      }
    }

    async function restoreFromTrash(id) {
      try {
        const response = await api.restoreFromTrash(id)
        const success = response.code === 200 || response.success

        if (success) {
          trashList.value = trashList.value.filter(i => i.id !== id)
        }
        return success
      } catch (err) {
        console.error(`[${contentType}] 从回收站恢复失败:`, err)
        return false
      }
    }

    async function batchRestoreFromTrash(ids) {
      try {
        const response = await api.batchRestoreFromTrash ? await api.batchRestoreFromTrash(ids) : { success: false }
        const success = response.code === 200 || response.success

        if (success) {
          trashList.value = trashList.value.filter(i => !ids.includes(i.id))
        }
        return success
      } catch (err) {
        console.error(`[${contentType}] 批量恢复失败:`, err)
        return false
      }
    }

    async function deletePermanently(id) {
      try {
        const response = await api.deletePermanently(id)
        const success = response.code === 200 || response.success

        if (success) {
          trashList.value = trashList.value.filter(i => i.id !== id)
        }
        return success
      } catch (err) {
        console.error(`[${contentType}] 永久删除失败:`, err)
        return false
      }
    }

    async function batchDeletePermanently(ids) {
      try {
        const response = await api.batchDeletePermanently ? await api.batchDeletePermanently(ids) : { success: false }
        const success = response.code === 200 || response.success

        if (success) {
          trashList.value = trashList.value.filter(i => !ids.includes(i.id))
        }
        return success
      } catch (err) {
        console.error(`[${contentType}] 批量永久删除失败:`, err)
        return false
      }
    }

    async function fetchTrashList() {
      loading.value = true
      try {
        const response = await api.getTrashList()
        trashList.value = response.data || response || []
      } catch (err) {
        console.error(`[${contentType}] 获取回收站列表失败:`, err)
      } finally {
        loading.value = false
      }
    }

    async function search(keyword) {
      if (!keyword || keyword.trim() === '') {
        isFiltering.value = false
        return items.value
      }

      loading.value = true
      try {
        const response = await api.search(keyword.trim())
        filteredItems.value = response.data || response || []
        isFiltering.value = true
        return filteredItems.value
      } catch (err) {
        console.error(`[${contentType}] 搜索失败:`, err)
        return []
      } finally {
        loading.value = false
      }
    }

    async function filterByTags(includeTags = [], excludeTags = []) {
      if (includeTags.length === 0 && excludeTags.length === 0) {
        isFiltering.value = false
        return items.value
      }

      loading.value = true
      try {
        const response = await api.filter(includeTags, excludeTags)
        filteredItems.value = response.data || response || []
        isFiltering.value = true
        return filteredItems.value
      } catch (err) {
        console.error(`[${contentType}] 标签筛选失败:`, err)
        return []
      } finally {
        loading.value = false
      }
    }

    async function filterMulti(includeTags = [], excludeTags = [], authors = [], listIds = []) {
      if (includeTags.length === 0 && excludeTags.length === 0 && authors.length === 0 && listIds.length === 0) {
        isFiltering.value = false
        return items.value
      }

      loading.value = true
      try {
        const response = await api.filter(includeTags, excludeTags, authors, listIds)
        filteredItems.value = response.data || response || []
        isFiltering.value = true
        return filteredItems.value
      } catch (err) {
        console.error(`[${contentType}] 综合筛选失败:`, err)
        return []
      } finally {
        loading.value = false
      }
    }

    function clearFilter() {
      isFiltering.value = false
      filteredItems.value = []
    }

    function setSortType(sortType) {
      currentSort.value = sortType
    }

    function clearSort() {
      currentSort.value = null
    }

    function setCurrentItem(item) {
      currentItem.value = item
    }

    function clearCurrentItem() {
      currentItem.value = null
    }

    return {
      items,
      currentItem,
      loading,
      error,
      currentSort,
      filteredItems,
      isFiltering,
      trashList,

      itemList,
      totalCount,
      displayCount,

      getItemById,
      fetchList,
      fetchDetail,
      updateScore,
      saveProgress,
      moveToTrash,
      batchMoveToTrash,
      restoreFromTrash,
      batchRestoreFromTrash,
      deletePermanently,
      batchDeletePermanently,
      fetchTrashList,
      search,
      filterByTags,
      filterMulti,
      clearFilter,
      setSortType,
      clearSort,
      setCurrentItem,
      clearCurrentItem
    }
  }
}
