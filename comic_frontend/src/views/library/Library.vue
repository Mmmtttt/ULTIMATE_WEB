<template>
  <div class="library-page">
    <!-- Filter & Sort Bar -->
    <div class="toolbar">
      <div class="search-trigger" @click="goToSearch">
        <van-icon name="search" />
        <span>{{ searchPlaceholder }}</span>
      </div>
      
      <div class="actions">
        <van-button size="small" plain class="toolbar-action-btn" @click="showSortPanel = true">
          <van-icon name="sort" />
        </van-button>
        <van-button size="small" plain class="toolbar-action-btn" @click="showFilterPanel = true">
          <van-icon name="filter-o" />
        </van-button>
        <van-button size="small" plain class="toolbar-action-btn" @click="showViewModeSheet = true">
          <van-icon name="apps-o" />
        </van-button>
        <van-popover
          v-model:show="showMenu"
          :actions="menuActions"
          placement="bottom-end"
          @select="onMenuSelect"
        >
          <template #reference>
            <van-button size="small" plain class="toolbar-action-btn">
              <van-icon name="ellipsis" />
            </van-button>
          </template>
        </van-popover>
      </div>
    </div>

    <!-- Active Filters -->
    <div v-if="activeFilters.length > 0" class="active-filters">
      <van-tag 
        v-for="filter in activeFilters" 
        :key="filter.id" 
        closeable 
        type="primary" 
        @close="removeFilter(filter)"
      >
        {{ filter.label }}
      </van-tag>
      <van-button size="mini" plain @click="clearAllFilters">清空</van-button>
    </div>

    <!-- Content Area -->
    <div class="content-area">
      <van-loading v-if="isLoading" class="loading-center" />
      
      <EmptyState 
        v-else-if="items.length === 0" 
        :title="emptyTitle" 
        description="快去导入一些内容吧"
      />

      <MediaGrid 
        v-else 
        :items="pagedItems" 
        :show-favorite="true"
        :is-favorited="isFavorited"
        :selectable="isManageMode"
        :selected-ids="selectedIds"
        :show-progress="!isVideoMode"
        @click="onItemClick"
        @toggle-favorite="toggleFavorite"
        @select="toggleSelection"
        :class="{ 'video-mode': isVideoMode }"
      />
    </div>

    <AppPagination
      v-if="items.length > 0"
      v-model="currentPage"
      class="content-pagination"
      :total-items="totalItems"
      :page-size="pageSize"
    />

    <!-- Management Bar (Bottom) -->
    <transition name="slide-up">
      <div v-if="isManageMode" class="manage-bar">
        <div class="selection-info">已选 {{ selectedIds.length }} 项</div>
        <div class="manage-btns">
          <van-button size="small" @click="isManageMode = false">取消</van-button>
          <van-button size="small" plain @click="toggleSelectAllItems">
            {{ isAllItemsSelected ? '取消全选' : '全选' }}
          </van-button>
          <van-button size="small" type="danger" :disabled="selectedIds.length === 0" @click="batchDelete">
            删除
          </van-button>
        </div>
      </div>
    </transition>

    <!-- Panels -->
    <van-popup v-model:show="showSortPanel" position="bottom" round>
      <van-picker
        :columns="sortOptions"
        @confirm="onSortConfirm"
        @cancel="showSortPanel = false"
        show-toolbar
        title="排序方式"
      />
    </van-popup>

    <van-action-sheet v-model:show="showViewModeSheet" title="显示模式">
      <div class="view-mode-sheet">
        <van-cell
          v-for="option in viewModeOptions"
          :key="option.value"
          :title="option.label"
          clickable
          @click="setViewMode(option.value)"
        >
          <template #right-icon>
            <van-icon v-if="mediaViewMode === option.value" name="success" color="#1989fa" />
          </template>
        </van-cell>
      </div>
    </van-action-sheet>

    <van-popup
      v-model:show="showFilterPanel"
      :position="isDesktop ? 'center' : 'bottom'"
      round
      :style="isDesktop ? { width: '700px', height: '85vh' } : { height: '80%' }"
    >
      <div class="filter-panel">
        <van-nav-bar title="高级筛选" left-text="关闭" @click-left="showFilterPanel = false">
          <template #right>
            <van-button type="primary" size="small" @click="applyFilters">
              确定
            </van-button>
          </template>
        </van-nav-bar>

        <AdvancedFilter
          v-model:include-tags="includeTags"
          v-model:exclude-tags="excludeTags"
          v-model:selected-authors="selectedAuthors"
          v-model:selected-list-ids="selectedListIds"
          v-model:min-score="minScore"
          v-model:unread-only="unreadOnly"
          :tags="availableTags"
          :authors="availableAuthors"
          :lists="availableLists"
          :is-video-mode="isVideoMode"
        />
      </div>
    </van-popup>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useModeStore, useComicStore, useVideoStore, useTagStore, useListStore } from '@/stores'
import { comicApi } from '@/api'
import MediaGrid from '@/components/common/MediaGrid.vue'
import AppPagination from '@/components/common/AppPagination.vue'
import AdvancedFilter from '@/components/filter/AdvancedFilter.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { showToast, showConfirmDialog } from 'vant'
import { useDevice } from '@/composables/useDevice'
import { useClientPagination } from '@/composables/useClientPagination'
import { extractAuthors, getFilterStorageKey as makeFilterStorageKey, isAllSelected, loadFromSession, saveToSession, toggleSelectAll } from '@/utils'

const router = useRouter()
const route = useRoute()
const modeStore = useModeStore()
const comicStore = useComicStore()
const videoStore = useVideoStore()
const tagStore = useTagStore()
const listStore = useListStore()
const { isDesktop } = useDevice()

// State
const showSortPanel = ref(false)
const showFilterPanel = ref(false)
const showMenu = ref(false)
const showViewModeSheet = ref(false)
const isManageMode = ref(false)
const selectedIds = ref([])
const includeTags = ref([])
const excludeTags = ref([])
const selectedAuthors = ref([])
const selectedListIds = ref([])
const minScore = ref(0)
const unreadOnly = ref(false)
const mediaViewMode = computed(() => modeStore.mediaViewMode)
const initVersion = ref(0)
const viewModeOptions = [
  { value: 'large', label: '大图' },
  { value: 'medium', label: '中图' },
  { value: 'small', label: '小图' },
  { value: 'list', label: '列表' }
]

function getFilterStorageKey() {
  return makeFilterStorageKey('library_filters', isVideoMode.value)
}

function saveFilterState() {
  const payload = {
    includeTags: includeTags.value,
    excludeTags: excludeTags.value,
    selectedAuthors: selectedAuthors.value,
    selectedListIds: selectedListIds.value,
    minScore: minScore.value,
    unreadOnly: unreadOnly.value
  }
  saveToSession(getFilterStorageKey(), payload)
}

function restoreFilterState() {
  const parsed = loadFromSession(getFilterStorageKey())
  if (!parsed) {
    return false
  }
  includeTags.value = parsed.includeTags || []
  excludeTags.value = parsed.excludeTags || []
  selectedAuthors.value = parsed.selectedAuthors || []
  selectedListIds.value = parsed.selectedListIds || []
  minScore.value = Number(parsed.minScore) > 0 ? Number(parsed.minScore) : 0
  unreadOnly.value = Boolean(parsed.unreadOnly)
  return includeTags.value.length > 0 || excludeTags.value.length > 0 || selectedAuthors.value.length > 0 || selectedListIds.value.length > 0 || minScore.value > 0 || unreadOnly.value
}

// Computed
const isVideoMode = computed(() => modeStore.isVideoMode)
const currentStore = computed(() => isVideoMode.value ? videoStore : comicStore)

const items = computed(() => {
  return isVideoMode.value ? videoStore.videoList : comicStore.comicList
})

const paginationStorageKey = computed(() => `library_${isVideoMode.value ? 'video' : 'comic'}`)
const {
  pageSize,
  currentPage,
  totalItems,
  pagedItems,
  goFirst
} = useClientPagination(items, paginationStorageKey)

async function applyFilters(options = {}) {
  const shouldResetPage = options.resetPage !== false
  const shouldClosePanel = options.closePanel !== false
  if (isVideoMode.value) {
    await videoStore.filterMulti(
      includeTags.value,
      excludeTags.value,
      selectedAuthors.value,
      selectedListIds.value,
      minScore.value
    )
  } else {
    await comicStore.filterMulti(
      includeTags.value,
      excludeTags.value,
      selectedAuthors.value,
      selectedListIds.value,
      minScore.value,
      unreadOnly.value
    )
  }
  if (shouldResetPage) {
    goFirst()
  }
  saveFilterState()
  if (shouldClosePanel) {
    showFilterPanel.value = false
  }
}

const isLoading = computed(() => currentStore.value.loading)

const searchPlaceholder = computed(() => 
  isVideoMode.value ? '搜索视频...' : '搜索漫画...'
)

const emptyTitle = computed(() => 
  isVideoMode.value ? '暂无视频' : '暂无漫画'
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

async function onSortConfirm({ selectedOptions }) {
  showSortPanel.value = false
  try {
    const selectedValue = selectedOptions?.[0]?.value
    if (!selectedValue) return
    
    if (isVideoMode.value) {
      await videoStore.sortVideos(selectedValue)
    } else {
      await comicStore.sortComics(selectedValue)
    }
    goFirst()
  } catch (e) {
    console.error('排序失败:', e)
    showToast('排序失败')
  }
}

const availableTags = computed(() => {
  return isVideoMode.value ? tagStore.videoTags : tagStore.tags
})

const availableAuthors = computed(() => {
  const items = isVideoMode.value ? videoStore.videos : comicStore.comics
  return extractAuthors(items)
})

const availableLists = computed(() => {
  return listStore.lists.map(list => ({
    ...list,
    item_count: list.item_ids?.length || 0
  }))
})

const activeFilters = computed(() => {
  const filters = []

  includeTags.value.forEach(tagId => {
    const tag = availableTags.value.find(item => item.id === tagId)
    filters.push({
      id: `include-${tagId}`,
      type: 'includeTag',
      value: tagId,
      label: `包含: ${tag?.name || tagId}`
    })
  })

  excludeTags.value.forEach(tagId => {
    const tag = availableTags.value.find(item => item.id === tagId)
    filters.push({
      id: `exclude-${tagId}`,
      type: 'excludeTag',
      value: tagId,
      label: `排除: ${tag?.name || tagId}`
    })
  })

  selectedAuthors.value.forEach(author => {
    filters.push({
      id: `author-${author}`,
      type: 'author',
      value: author,
      label: `作者: ${author}`
    })
  })

  selectedListIds.value.forEach(listId => {
    const list = availableLists.value.find(item => item.id === listId)
    filters.push({
      id: `list-${listId}`,
      type: 'list',
      value: listId,
      label: `清单: ${list?.name || listId}`
    })
  })

  if (minScore.value > 0) {
    filters.push({
      id: 'min-score',
      type: 'minScore',
      value: minScore.value,
      label: `评分 >= ${minScore.value}`
    })
  }

  if (!isVideoMode.value && unreadOnly.value) {
    filters.push({
      id: 'unread-only',
      type: 'unreadOnly',
      value: true,
      label: '仅未读'
    })
  }

  return filters
})

const isAllItemsSelected = computed(() => {
  return isAllSelected(selectedIds.value, pagedItems.value, (item) => item.id)
})

// Methods
function goToSearch() {
  router.push('/search')
}

async function onMenuSelect(action) {
  if (action.text === '批量管理') isManageMode.value = true
  if (action.text === '刷新列表') {
    await initializePage(true)
  }
}

function onItemClick(item) {
  if (isManageMode.value) {
    toggleSelection(item)
  } else {
    const routeName = isVideoMode.value ? 'VideoDetail' : 'ComicDetail'
    router.push({ name: routeName, params: { id: item.id }, query: route.query })
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

function toggleSelectAllItems() {
  toggleSelectAll(selectedIds, pagedItems.value, (item) => item.id)
}

function setViewMode(mode) {
  modeStore.setMediaViewMode(mode)
  showViewModeSheet.value = false
}

function isFavorited(item) {
  if (isVideoMode.value) {
    return listStore.isFavoritedVideo(item)
  } else {
    return listStore.isFavorited(item)
  }
}

async function toggleFavorite(item) {
  if (isVideoMode.value) {
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
    
    let success = false
    if (isVideoMode.value) {
      success = await videoStore.batchMoveToTrash(selectedIds.value)
    } else {
      const res = await comicApi.batchMoveToTrash(selectedIds.value)
      success = res.code === 200
    }
    
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

function clearAllFilters() {
  includeTags.value = []
  excludeTags.value = []
  selectedAuthors.value = []
  selectedListIds.value = []
  minScore.value = 0
  unreadOnly.value = false
  currentStore.value.clearFilter()
  goFirst()
  saveFilterState()
}

async function removeFilter(filter) {
  if (filter.type === 'includeTag') {
    includeTags.value = includeTags.value.filter(id => id !== filter.value)
  } else if (filter.type === 'excludeTag') {
    excludeTags.value = excludeTags.value.filter(id => id !== filter.value)
  } else if (filter.type === 'author') {
    selectedAuthors.value = selectedAuthors.value.filter(author => author !== filter.value)
  } else if (filter.type === 'list') {
    selectedListIds.value = selectedListIds.value.filter(id => id !== filter.value)
  } else if (filter.type === 'minScore') {
    minScore.value = 0
  } else if (filter.type === 'unreadOnly') {
    unreadOnly.value = false
  }

  await applyFilters()
}

async function loadData(force = false) {
  if (force || listStore.lists.length === 0) {
    await listStore.fetchLists()
  }
  if (isVideoMode.value) {
    if (force || tagStore.videoTags.length === 0) await tagStore.fetchTags('video', force)
    await videoStore.fetchList()
  } else {
    if (force || tagStore.tags.length === 0) await tagStore.fetchTags('comic', force)
    await comicStore.fetchComics(force)
  }
}

function hasActiveFilterState() {
  return includeTags.value.length > 0 ||
    excludeTags.value.length > 0 ||
    selectedAuthors.value.length > 0 ||
    selectedListIds.value.length > 0 ||
    minScore.value > 0 ||
    unreadOnly.value
}

async function initializePage(force = false) {
  const currentVersion = ++initVersion.value
  await loadData(force)
  if (currentVersion !== initVersion.value) {
    return
  }

  const restored = restoreFilterState()
  if (route.query.author) {
    selectedAuthors.value = [route.query.author]
  }
  if (route.query.tagId) {
    includeTags.value = [route.query.tagId]
  }

  if (restored || hasActiveFilterState()) {
    await applyFilters({ resetPage: false, closePanel: false })
  } else {
    currentStore.value.clearFilter()
  }
}

// Lifecycle
watch(() => modeStore.currentMode, async () => {
  selectedIds.value = []
  isManageMode.value = false
  await initializePage(false)
})

watch(() => route.query.author, async (newAuthor) => {
  if (newAuthor) {
    selectedAuthors.value = [newAuthor]
    await applyFilters({ closePanel: false })
  }
})

watch(() => route.query.tagId, async (newTagId) => {
  if (newTagId) {
    includeTags.value = [newTagId]
    await applyFilters({ closePanel: false })
  }
})

onMounted(async () => {
  await initializePage(false)
})
</script>

<style scoped>
.library-page {
  padding-bottom: 96px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  margin-bottom: 12px;
  position: sticky;
  top: 10px;
  z-index: 12;
}

.search-trigger {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  font-size: 14px;
}

.search-trigger .van-icon {
  color: var(--text-tertiary);
}

.actions {
  flex-shrink: 0;
}

.active-filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 2px 2px 10px;
}

.active-filters :deep(.van-tag) {
  border-radius: 999px;
  border: 1px solid rgba(47, 116, 255, 0.24);
  background: rgba(47, 116, 255, 0.08);
  color: var(--brand-700);
}

.content-area {
  min-height: 200px;
}

.content-pagination {
  padding: 0 8px;
}

.loading-center {
  padding: 54px 0;
  text-align: center;
}

.manage-bar {
  position: fixed;
  left: 12px;
  right: 12px;
  bottom: 62px;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  padding: 10px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  box-shadow: 0 14px 26px rgba(17, 27, 45, 0.14);
  backdrop-filter: blur(12px);
  z-index: 101;
}

.selection-info {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.manage-btns {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.filter-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.filter-panel :deep(.advanced-filter) {
  flex: 1;
  overflow-y: auto;
}

.filter-panel :deep(.van-nav-bar) {
  border-radius: 14px 14px 0 0;
}

.view-mode-sheet {
  padding-bottom: 10px;
}

@media (max-width: 767px) {
  .library-page {
    padding-bottom: 110px;
  }

  .toolbar {
    top: 8px;
    padding: 8px;
    gap: 8px;
  }

  .search-trigger {
    height: 34px;
    padding: 0 12px;
    font-size: 13px;
  }

  .manage-bar {
    bottom: 58px;
    padding: 10px 12px;
  }

  .manage-btns :deep(.van-button) {
    min-width: 64px;
  }
}

@media (min-width: 1024px) {
  .manage-bar {
    left: calc(var(--sidebar-width) + 22px);
    right: 22px;
    bottom: 18px;
  }
}
</style>
