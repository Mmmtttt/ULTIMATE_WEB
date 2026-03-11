import { ref, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'

export function useContentList(options) {
  const {
    store,
    contentType,
    listStore = null,
    tagStore = null,
    modeStore = null,
    isVideoMode = false,
    filterStorageKey = 'content_filters',
    detailRouteName = 'Detail',
    searchRoute = '/search'
  } = options

  const router = useRouter()
  const route = useRoute()

  const showSortPanel = ref(false)
  const showFilterPanel = ref(false)
  const showMenu = ref(false)
  const isManageMode = ref(false)
  const selectedIds = ref([])
  const includeTags = ref([])
  const excludeTags = ref([])
  const selectedAuthors = ref([])
  const selectedListIds = ref([])

  const items = computed(() => store.itemList || store.value?.itemList || [])
  const isLoading = computed(() => store.loading || store.value?.loading || false)

  const searchPlaceholder = computed(() =>
    isVideoMode ? '搜索视频...' : '搜索漫画...'
  )

  const emptyTitle = computed(() =>
    isVideoMode ? '暂无视频' : '暂无漫画'
  )

  const menuActions = [
    { text: '批量管理', icon: 'setting-o' },
    { text: '刷新列表', icon: 'replay' }
  ]

  const sortOptions = computed(() => [
    { text: '最近导入', value: 'create_time' },
    { text: '评分最高', value: 'score' },
    { text: '最新发布', value: 'date' }
  ])

  const availableTags = computed(() => {
    if (!tagStore) return []
    return isVideoMode ? (tagStore.videoTags || []) : (tagStore.tags || [])
  })

  const availableAuthors = computed(() => {
    const items = store.items || store.value?.items || []
    const authors = new Set()
    items.forEach(item => {
      if (item.author) authors.add(item.author)
      if (item.creator) authors.add(item.creator)
    })
    return Array.from(authors).sort()
  })

  const availableLists = computed(() => {
    if (!listStore) return []
    return (listStore.lists || []).map(list => ({
      ...list,
      item_count: list.item_ids?.length || 0
    }))
  })

  function getFilterStorageKey() {
    return `${filterStorageKey}_${isVideoMode ? 'video' : 'comic'}`
  }

  function saveFilterState() {
    const payload = {
      includeTags: includeTags.value,
      excludeTags: excludeTags.value,
      selectedAuthors: selectedAuthors.value,
      selectedListIds: selectedListIds.value
    }
    sessionStorage.setItem(getFilterStorageKey(), JSON.stringify(payload))
  }

  function restoreFilterState() {
    const raw = sessionStorage.getItem(getFilterStorageKey())
    if (!raw) return false

    try {
      const parsed = JSON.parse(raw)
      includeTags.value = parsed.includeTags || []
      excludeTags.value = parsed.excludeTags || []
      selectedAuthors.value = parsed.selectedAuthors || []
      selectedListIds.value = parsed.selectedListIds || []
      return includeTags.value.length > 0 || excludeTags.value.length > 0 ||
        selectedAuthors.value.length > 0 || selectedListIds.value.length > 0
    } catch {
      return false
    }
  }

  function goToSearch() {
    router.push(searchRoute)
  }

  function onMenuSelect(action) {
    if (action.text === '批量管理') isManageMode.value = true
    if (action.text === '刷新列表') loadData(true)
  }

  function onItemClick(item) {
    if (isManageMode.value) {
      toggleSelection(item)
    } else {
      router.push({
        name: detailRouteName,
        params: { id: item.id },
        query: route.query
      })
    }
  }

  function toggleSelection(item) {
    const id = item.id
    if (selectedIds.value.includes(id)) {
      selectedIds.value = selectedIds.value.filter(i => i !== id)
    } else {
      selectedIds.value.push(id)
    }
  }

  function isFavorited(item) {
    if (!listStore) return false
    return isVideoMode ? listStore.isFavoritedVideo(item) : listStore.isFavorited(item)
  }

  async function toggleFavorite(item) {
    if (!listStore) return
    if (isVideoMode) {
      await listStore.toggleFavoriteVideo(item.id, item.source)
    } else {
      await listStore.toggleFavorite(item.id, item.source)
    }
  }

  async function batchDelete() {
    if (selectedIds.value.length === 0) return

    try {
      await showConfirmDialog({
        title: '移入回收站',
        message: `确定将 ${selectedIds.value.length} 项内容移入回收站吗？`
      })

      const success = await store.batchMoveToTrash(selectedIds.value)
      if (!success) {
        showToast('移入回收站失败')
        return
      }

      showToast('已移入回收站')
      selectedIds.value = []
      isManageMode.value = false
      await loadData(true)
    } catch (e) {
      if (e !== 'cancel') {
        showToast('移入回收站失败')
      }
    }
  }

  async function applyFilters() {
    await store.filterMulti(
      includeTags.value,
      excludeTags.value,
      selectedAuthors.value,
      selectedListIds.value
    )
    saveFilterState()
    showFilterPanel.value = false
  }

  function clearAllFilters() {
    includeTags.value = []
    excludeTags.value = []
    selectedAuthors.value = []
    selectedListIds.value = []
    store.clearFilter()
    saveFilterState()
  }

  async function loadData(force = false) {
    if (listStore && listStore.lists?.length === 0) {
      await listStore.fetchLists()
    }
    if (tagStore && availableTags.value.length === 0) {
      await tagStore.fetchTags(isVideoMode ? 'video' : 'comic')
    }
    await store.fetchList({}, force)
  }

  async function onSortConfirm({ selectedOptions }) {
    const sortType = selectedOptions[0].value
    store.setSortType(sortType)
    await loadData(true)
    showSortPanel.value = false
  }

  function setupWatchers() {
    if (modeStore) {
      watch(() => modeStore.currentMode, () => {
        loadData()
        selectedIds.value = []
        isManageMode.value = false
        restoreFilterState()
        applyFilters()
      })
    }

    watch(() => route.query.author, (newAuthor) => {
      if (newAuthor) {
        selectedAuthors.value = [newAuthor]
        applyFilters()
      }
    })

    watch(() => route.query.tagId, (newTagId) => {
      if (newTagId) {
        includeTags.value = [newTagId]
        applyFilters()
      }
    })
  }

  function init() {
    loadData()
    const restored = restoreFilterState()
    if (restored) {
      applyFilters()
    }
    if (route.query.author) {
      selectedAuthors.value = [route.query.author]
      applyFilters()
    }
    if (route.query.tagId) {
      includeTags.value = [route.query.tagId]
      applyFilters()
    }
  }

  return {
    showSortPanel,
    showFilterPanel,
    showMenu,
    isManageMode,
    selectedIds,
    includeTags,
    excludeTags,
    selectedAuthors,
    selectedListIds,
    items,
    isLoading,
    searchPlaceholder,
    emptyTitle,
    menuActions,
    sortOptions,
    availableTags,
    availableAuthors,
    availableLists,
    goToSearch,
    onMenuSelect,
    onItemClick,
    toggleSelection,
    isFavorited,
    toggleFavorite,
    batchDelete,
    applyFilters,
    clearAllFilters,
    loadData,
    onSortConfirm,
    saveFilterState,
    restoreFilterState,
    setupWatchers,
    init
  }
}
