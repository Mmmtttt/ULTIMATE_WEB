import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { listApi } from '@/api'
import { showSuccessToast, showFailToast } from 'vant'

const FAVORITES_LIST_ID = 'list_favorites'

export const useListStore = defineStore('list', () => {
  const lists = ref([])
  const currentList = ref(null)
  const loading = ref(false)
  
  const favoritesList = computed(() => 
    lists.value.find(l => l.id === FAVORITES_LIST_ID)
  )
  
  const customLists = computed(() => 
    lists.value.filter(l => l.id !== FAVORITES_LIST_ID)
  )
  
  const totalLists = computed(() => lists.value.length)
  
  async function fetchLists() {
    loading.value = true
    try {
      const res = await listApi.getListAll()
      if (res.code === 200) {
        lists.value = res.data || []
        return true
      }
      return false
    } catch (e) {
      console.error('获取清单列表失败:', e)
      return false
    } finally {
      loading.value = false
    }
  }
  
  async function fetchListDetail(listId) {
    loading.value = true
    try {
      const res = await listApi.getDetail(listId)
      if (res.code === 200) {
        currentList.value = res.data
        return res.data
      }
      return null
    } catch (e) {
      console.error('获取清单详情失败:', e)
      return null
    } finally {
      loading.value = false
    }
  }
  
  async function createList(name, desc = '') {
    try {
      const res = await listApi.create(name, desc)
      if (res.code === 200) {
        showSuccessToast('创建成功')
        await fetchLists()
        return res.data
      } else {
        showFailToast(res.msg || '创建失败')
        return null
      }
    } catch (e) {
      showFailToast('创建失败')
      return null
    }
  }
  
  async function updateList(listId, name, desc) {
    try {
      const res = await listApi.update(listId, name, desc)
      if (res.code === 200) {
        showSuccessToast('更新成功')
        await fetchLists()
        return true
      } else {
        showFailToast(res.msg || '更新失败')
        return false
      }
    } catch (e) {
      showFailToast('更新失败')
      return false
    }
  }
  
  async function deleteList(listId) {
    try {
      const res = await listApi.delete(listId)
      if (res.code === 200) {
        showSuccessToast('删除成功')
        await fetchLists()
        return true
      } else {
        showFailToast(res.msg || '删除失败')
        return false
      }
    } catch (e) {
      showFailToast('删除失败')
      return false
    }
  }
  
  async function bindComics(listId, comicIds) {
    try {
      const res = await listApi.bindComics(listId, comicIds)
      if (res.code === 200) {
        showSuccessToast(`成功加入${res.data.updated_count}个漫画`)
        return true
      } else {
        showFailToast(res.msg || '加入失败')
        return false
      }
    } catch (e) {
      showFailToast('加入失败')
      return false
    }
  }
  
  async function removeComics(listId, comicIds) {
    try {
      const res = await listApi.removeComics(listId, comicIds)
      if (res.code === 200) {
        showSuccessToast(`成功移出${res.data.updated_count}个漫画`)
        return true
      } else {
        showFailToast(res.msg || '移出失败')
        return false
      }
    } catch (e) {
      showFailToast('移出失败')
      return false
    }
  }
  
  async function toggleFavorite(comicId) {
    try {
      const res = await listApi.toggleFavorite(comicId)
      if (res.code === 200) {
        const action = res.data.is_favorited ? '收藏成功' : '取消收藏'
        showSuccessToast(action)
        return res.data.is_favorited
      } else {
        showFailToast(res.msg || '操作失败')
        return null
      }
    } catch (e) {
      showFailToast('操作失败')
      return null
    }
  }
  
  function isFavorited(comic) {
    return comic?.list_ids?.includes(FAVORITES_LIST_ID) || false
  }
  
  function clearCurrentList() {
    currentList.value = null
  }
  
  return {
    lists,
    currentList,
    loading,
    favoritesList,
    customLists,
    totalLists,
    fetchLists,
    fetchListDetail,
    createList,
    updateList,
    deleteList,
    bindComics,
    removeComics,
    toggleFavorite,
    isFavorited,
    clearCurrentList
  }
})
