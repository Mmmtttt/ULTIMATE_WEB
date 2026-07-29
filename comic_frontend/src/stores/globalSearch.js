/**
 * 全网搜索状态 Store
 *
 * 保持搜索结果在页面导航期间持久化。
 * 仅在以下情况清空：
 *  - 用户执行新的搜索（自动清空旧结果）
 *  - 页面刷新或关闭（Pinia 默认行为）
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useGlobalSearchStore = defineStore('globalSearch', () => {
  const keyword = ref('')
  const results = ref([])
  const hasMore = ref(false)
  const currentPage = ref(0)
  const selectedIds = ref([])
  const paginationInfo = ref(null)
  const searchExecuted = ref(false)
  const videoMode = ref(false)
  const selectedPlatforms = ref([])
  const platformOptions = ref([])

  function setSearchState({
    keyword: kw,
    results: res,
    hasMore: hm,
    currentPage: cp,
    paginationInfo: pi,
    videoMode: vm,
  }) {
    if (kw !== undefined) keyword.value = kw
    if (res !== undefined) results.value = res
    if (hm !== undefined) hasMore.value = hm
    if (cp !== undefined) currentPage.value = cp
    if (pi !== undefined) paginationInfo.value = pi
    if (vm !== undefined) videoMode.value = vm
  }

  function clearResults() {
    keyword.value = ''
    results.value = []
    hasMore.value = false
    currentPage.value = 0
    selectedIds.value = []
    paginationInfo.value = null
    searchExecuted.value = false
  }

  function clearSelection() {
    selectedIds.value = []
  }

  function appendResults(newResults, newPage, newHasMore, newPaginationInfo) {
    results.value = [...results.value, ...newResults]
    currentPage.value = newPage
    hasMore.value = newHasMore
    if (newPaginationInfo) {
      paginationInfo.value = newPaginationInfo
    }
  }

  return {
    keyword,
    results,
    hasMore,
    currentPage,
    selectedIds,
    paginationInfo,
    searchExecuted,
    videoMode,
    selectedPlatforms,
    platformOptions,
    setSearchState,
    clearResults,
    clearSelection,
    appendResults,
  }
})
