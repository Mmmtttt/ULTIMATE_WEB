<template>
  <div class="preview-page">
    <!-- Filter & Sort Bar -->
    <div class="toolbar">
      <van-search
        v-model="searchKeyword"
        class="toolbar-search"
        type="text"
        shape="round"
        :placeholder="searchPlaceholder"
      >
        <template #right-icon>
          <button
            v-if="searchKeyword"
            type="button"
            class="toolbar-search-clear"
            aria-label="清空搜索"
            @click.stop="clearSearchKeyword"
          >
            <van-icon name="cross" />
          </button>
        </template>
      </van-search>
      
      <div class="actions">
        <van-button size="small" plain class="toolbar-action-btn" @click="showFilterPanel = true">
          <van-icon name="filter-o" />
        </van-button>
        <van-button size="small" plain class="toolbar-action-btn" @click="showSortPanel = true">
          <van-icon name="sort" />
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

    <div v-if="showCustomSortBanner" class="custom-sort-banner">
      <div class="custom-sort-banner__copy">当前按自定义顺序显示</div>
      <van-button size="small" plain type="primary" @click="openCustomOrderEditor">
        调整顺序
      </van-button>
    </div>

    <!-- Content Area -->
    <div class="content-area">
      <van-loading v-if="isLoading" class="loading-center" />
      
      <EmptyState 
        v-else-if="displayItems.length === 0" 
        :title="emptyTitle" 
        :description="emptyDescription"
      />

      <MediaGrid 
        v-else 
        :items="pagedItems" 
        :content-type="isVideoMode ? 'video' : 'comic'"
        :show-favorite="true"
        :is-favorited="isSaved"
        :selectable="isManageMode"
        :selected-ids="selectedIds"
        :show-progress="!isVideoMode"
        @click="onItemClick"
        @toggle-favorite="toggleSave"
        @select="toggleSelection"
        :class="{ 'video-mode': isVideoMode }"
      />
    </div>

    <AppPagination
      v-if="displayItems.length > 0"
      v-model="currentPage"
      class="content-pagination"
      :total-items="totalItems"
      :page-size="pageSize"
    />

    <!-- Management Bar -->
    <transition name="slide-up">
      <div v-if="isManageMode" class="manage-bar">
        <div class="selection-info">已选 {{ selectedIds.length }} 项</div>
        <div class="manage-btns">
          <van-button size="small" @click="isManageMode = false">取消</van-button>
          <van-button size="small" plain @click="toggleSelectAllItems">
            {{ isAllItemsSelected ? '取消全选' : '全选' }}
          </van-button>
          <van-button size="small" type="primary" :disabled="selectedIds.length === 0" @click="showBatchListPopup = true">
            加入清单
          </van-button>
          <van-button size="small" type="primary" :disabled="selectedIds.length === 0" @click="batchImportToLocal">
            导入本地库
          </van-button>
          <van-button size="small" type="danger" :disabled="selectedIds.length === 0" @click="batchTrash">
            移入回收站
          </van-button>
        </div>
      </div>
    </transition>

    <!-- Sort Panel -->
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
    
    <!-- 高级筛选面板 -->
    <van-popup 
      v-model:show="showFilterPanel" 
      :position="isDesktop ? 'center' : 'bottom'" 
      round 
      :style="isDesktop ? { width: '700px', height: '85vh' } : { height: '80%' }"
    >
      <div class="filter-panel">
        <van-nav-bar title="高级筛选" left-text="关闭" @click-left="showFilterPanel = false">
          <template #right>
            <van-button type="primary" size="small" @click="applyFilterAndClose">
              确定
            </van-button>
          </template>
        </van-nav-bar>
        
        <AdvancedFilter
          v-model:include-tags="tempIncludeTags"
          v-model:exclude-tags="tempExcludeTags"
          v-model:selected-authors="tempSelectedAuthors"
          v-model:selected-list-ids="tempSelectedListIds"
          v-model:min-score="tempMinScore"
          v-model:unread-only="tempUnreadOnly"
          :tags="availableTags"
          :authors="availableAuthors"
          :lists="availableLists"
          :is-video-mode="isVideoMode"
        />
      </div>
    </van-popup>

    <!-- Batch List Popup -->
    <van-popup
      v-model:show="showBatchListPopup"
      position="bottom"
      round
      :style="{ height: '60%' }"
    >
      <div class="batch-list-popup">
        <van-nav-bar title="批量加入清单">
          <template #right>
            <van-button type="primary" size="small" @click="batchAddToLists">保存</van-button>
          </template>
        </van-nav-bar>

        <van-checkbox-group v-model="batchSelectedListIds">
          <van-cell-group inset>
            <van-cell
              v-for="list in availableLists"
              :key="list.id"
              clickable
              @click="toggleBatchListItem(list.id)"
            >
              <template #title>
                <span>{{ list.name }}</span>
                <span class="list-count">({{ list.item_count || 0 }})</span>
              </template>
              <template #right-icon>
                <van-checkbox :name="list.id" />
              </template>
            </van-cell>
          </van-cell-group>
        </van-checkbox-group>

        <div class="list-action">
          <van-button type="primary" block @click="batchAddToLists">保存</van-button>
        </div>
      </div>
    </van-popup>

    <ContentOrderEditor
      v-model:show="showCustomOrderEditor"
      :items="orderEditorItems"
      @save="saveCustomOrder"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useModeStore, useRecommendationStore, useVideoRecommendationStore, useListStore, useTagStore, useImportTaskStore, useConfigStore } from '@/stores'
import { uiStateApi } from '@/api'
import MediaGrid from '@/components/common/MediaGrid.vue'
import AppPagination from '@/components/common/AppPagination.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AdvancedFilter from '@/components/filter/AdvancedFilter.vue'
import ContentOrderEditor from '@/components/common/ContentOrderEditor.vue'
import { showToast } from 'vant'
import { useDevice } from '@/composables/useDevice'
import { usePersistentPage } from '@/composables/useClientPagination'
import { toBackendUrl } from '@/utils/url'
import {
  buildSortOptions,
  clearBrowseState,
  buildUiStateScope,
  DEFAULT_CONFIG,
  debounce,
  decodeSortSelection,
  getOrCreateUiStateClientId,
  isAllSelected,
  isDefaultSortState,
  loadBrowseState,
  normalizeSortOrder,
  saveBrowseState,
  toggleSelectAll
} from '@/utils'

const router = useRouter()
const route = useRoute()
const modeStore = useModeStore()
const comicRecStore = useRecommendationStore()
const videoRecStore = useVideoRecommendationStore()
const listStore = useListStore()
const tagStore = useTagStore()
const importTaskStore = useImportTaskStore()
const configStore = useConfigStore()
const { isDesktop } = useDevice()

// State
const showSortPanel = ref(false)
const showMenu = ref(false)
const showViewModeSheet = ref(false)
const showBatchListPopup = ref(false)
const showCustomOrderEditor = ref(false)
const isManageMode = ref(false)
const selectedIds = ref([])
const batchSelectedListIds = ref([])
const showFilterPanel = ref(false)
const searchKeyword = ref('')
const tempIncludeTags = ref([])
const tempExcludeTags = ref([])
const tempSelectedAuthors = ref([])
const tempSelectedListIds = ref([])
const tempMinScore = ref(0)
const tempUnreadOnly = ref(false)
const currentSortField = ref('')
const currentSortOrder = ref('desc')
const suppressSearchStateWatch = ref(false)
const customOrderItems = ref([])
const pageWatchReady = ref(false)
const skipNextPageFetch = ref(false)
const selectionScopeItems = ref([])
const mediaViewMode = computed(() => modeStore.mediaViewMode)
const initVersion = ref(0)
const uiStateClientId = getOrCreateUiStateClientId()
const viewModeOptions = [
  { value: 'large', label: '大图' },
  { value: 'medium', label: '中图' },
  { value: 'small', label: '小图' },
  { value: 'list', label: '列表' }
]

function getUiStateScope() {
  return buildUiStateScope('preview_state', isVideoMode.value)
}

function isSortFieldSupported(sortField) {
  const normalized = String(sortField || '').trim()
  if (!normalized) {
    return true
  }
  if (normalized === 'name' || normalized === 'random' || normalized === 'custom') {
    return true
  }
  if (normalized === 'page_count') {
    return !isVideoMode.value
  }
  if (normalized === 'date') {
    return isVideoMode.value
  }
  return normalized === 'create_time' || normalized === 'score'
}

function buildPersistedStatePayload() {
  const payload = {
    searchKeyword: String(searchKeyword.value || '').trim(),
    includeTags: tempIncludeTags.value,
    excludeTags: tempExcludeTags.value,
    selectedAuthors: tempSelectedAuthors.value,
    selectedListIds: tempSelectedListIds.value,
    minScore: tempMinScore.value,
    unreadOnly: tempUnreadOnly.value
  }
  if (!isDefaultSortState(currentSortField.value, currentSortOrder.value)) {
    payload.sortField = currentSortField.value
    payload.sortOrder = currentSortOrder.value
  }
  if (
    payload.includeTags.length === 0 &&
    payload.excludeTags.length === 0 &&
    payload.selectedAuthors.length === 0 &&
    payload.selectedListIds.length === 0 &&
    Number(payload.minScore) <= 0 &&
    !payload.unreadOnly &&
    !payload.searchKeyword &&
    !payload.sortField
  ) {
    return null
  }
  return payload
}

function buildLocalBrowseStatePayload() {
  const payload = buildPersistedStatePayload() || {}
  if (currentPage.value > 1) {
    payload.currentPage = currentPage.value
  }
  return Object.keys(payload).length > 0 ? payload : null
}

function persistLocalBrowseState() {
  const payload = buildLocalBrowseStatePayload()
  if (!payload) {
    clearBrowseState(getUiStateScope())
    return
  }
  saveBrowseState(getUiStateScope(), payload)
}

async function persistViewState() {
  const payload = buildPersistedStatePayload()
  persistLocalBrowseState()
  if (!payload) {
    await uiStateApi.clear(getUiStateScope(), uiStateClientId)
    return
  }
  await uiStateApi.save(getUiStateScope(), payload, uiStateClientId)
}

async function restoreViewState() {
  suppressSearchStateWatch.value = true
  let parsed = loadBrowseState(getUiStateScope(), null)
  if (!parsed) {
    const response = await uiStateApi.get(getUiStateScope(), uiStateClientId)
    parsed = response?.data?.state
  }
  if (!parsed) {
    searchKeyword.value = ''
    tempIncludeTags.value = []
    tempExcludeTags.value = []
    tempSelectedAuthors.value = []
    tempSelectedListIds.value = []
    tempMinScore.value = 0
    tempUnreadOnly.value = false
    currentSortField.value = ''
    currentSortOrder.value = 'desc'
    currentStore.value.setSortType?.(null, currentSortOrder.value)
    suppressSearchStateWatch.value = false
    return false
  }
  searchKeyword.value = String(parsed.searchKeyword || '').trim()
  tempIncludeTags.value = parsed.includeTags || []
  tempExcludeTags.value = parsed.excludeTags || []
  tempSelectedAuthors.value = parsed.selectedAuthors || []
  tempSelectedListIds.value = parsed.selectedListIds || []
  tempMinScore.value = Number(parsed.minScore) > 0 ? Number(parsed.minScore) : 0
  tempUnreadOnly.value = Boolean(parsed.unreadOnly)
  currentSortField.value = isSortFieldSupported(parsed.sortField) ? String(parsed.sortField || '').trim() : ''
  currentSortOrder.value = normalizeSortOrder(parsed.sortOrder)
  if (Number(parsed.currentPage) >= 1) {
    currentPage.value = Math.max(1, Math.floor(Number(parsed.currentPage)))
  }
  currentStore.value.setSortType?.(currentSortField.value || null, currentSortOrder.value)
  suppressSearchStateWatch.value = false
  return true
}

function sanitizeFilterStateForCurrentMode() {
  const availableTagIds = new Set(availableTags.value.map((item) => item.id))
  tempIncludeTags.value = tempIncludeTags.value.filter((tagId) => availableTagIds.has(tagId))
  tempExcludeTags.value = tempExcludeTags.value.filter((tagId) => availableTagIds.has(tagId))
}

function buildListQueryParams() {
  const params = {
    paginate: 1,
    summary: 1,
    include_available_authors: 1,
    page: currentPage.value,
    page_size: pageSize.value,
  }

  if (currentSortField.value) {
    params.sort_type = currentSortField.value
    params.sort_order = currentSortOrder.value
  }
  if (String(searchKeyword.value || '').trim()) {
    params.keyword = String(searchKeyword.value || '').trim()
  }
  if (tempIncludeTags.value.length > 0) {
    params.include_tag_ids = [...tempIncludeTags.value]
  }
  if (tempExcludeTags.value.length > 0) {
    params.exclude_tag_ids = [...tempExcludeTags.value]
  }
  if (tempSelectedAuthors.value.length > 0) {
    params.authors = [...tempSelectedAuthors.value]
  }
  if (tempSelectedListIds.value.length > 0) {
    params.list_ids = [...tempSelectedListIds.value]
  }
  if (Number(tempMinScore.value) > 0) {
    params.min_score = Number(tempMinScore.value)
  }
  if (tempUnreadOnly.value && !isVideoMode.value) {
    params.unread_only = 1
  }
  return params
}

function buildCustomOrderQueryParams() {
  return {
    sort_type: 'custom',
    sort_order: currentSortOrder.value,
  }
}

function buildSelectionScopeQueryParams() {
  const params = buildListQueryParams()
  delete params.paginate
  delete params.page
  delete params.page_size
  delete params.include_available_authors
  return params
}

// Computed
const isVideoMode = computed(() => modeStore.isVideoMode)
const currentStore = computed(() => isVideoMode.value ? videoRecStore : comicRecStore)

const items = computed(() => {
  return isVideoMode.value ? videoRecStore.recommendationList : comicRecStore.recommendationList
})

const displayItems = computed(() => {
  return items.value
})

const showCustomSortBanner = computed(() => {
  return currentSortField.value === 'custom' && totalItems.value > 1
})

const orderEditorItems = computed(() => {
  return customOrderItems.value.map((item) => ({
    id: item.id,
    title: item.title || item.name || item.id,
    cover: resolveOrderCover(item),
    platformLabel: item.plugin_name || item.platform || item.plugin_id || '',
  }))
})

const paginationStorageKey = computed(() => `preview_${isVideoMode.value ? 'video' : 'comic'}`)
const pageSize = computed(() => {
  const size = Number(configStore.listPageSize)
  if (Number.isFinite(size) && size > 0) {
    return size
  }
  return DEFAULT_CONFIG.LIST_PAGE_SIZE
})
const {
  currentPage,
  goFirst,
  ensureWithinRange
} = usePersistentPage(paginationStorageKey)
const totalItems = computed(() => {
  const total = isVideoMode.value ? videoRecStore.queryTotalCount : comicRecStore.queryTotalCount
  return Number(total) || 0
})
const pagedItems = computed(() => items.value)

const isLoading = computed(() => currentStore.value.loading)

const searchPlaceholder = computed(() => 
  isVideoMode.value ? '实时搜索推荐视频...' : '实时搜索推荐漫画...'
)

const emptyTitle = computed(() => 
  isVideoMode.value ? '暂无推荐视频' : '暂无推荐漫画'
)

const emptyDescription = computed(() => {
  return String(searchKeyword.value || '').trim()
    ? '没有找到匹配的推荐内容'
    : '暂无推荐内容'
})

const availableTags = computed(() => isVideoMode.value ? tagStore.videoTags : tagStore.tags)

const availableAuthors = computed(() => {
  return isVideoMode.value ? videoRecStore.availableAuthors : comicRecStore.availableAuthors
})

const availableLists = computed(() => {
  return listStore.lists.map(list => ({
    ...list,
    item_count: list.item_ids?.length || 0
  }))
})

const activeFilters = computed(() => {
  const filters = []

  tempIncludeTags.value.forEach(tagId => {
    const tag = availableTags.value.find(item => item.id === tagId)
    filters.push({
      id: `include-${tagId}`,
      type: 'includeTag',
      value: tagId,
      label: `包含: ${tag?.name || tagId}`
    })
  })

  tempExcludeTags.value.forEach(tagId => {
    const tag = availableTags.value.find(item => item.id === tagId)
    filters.push({
      id: `exclude-${tagId}`,
      type: 'excludeTag',
      value: tagId,
      label: `排除: ${tag?.name || tagId}`
    })
  })

  tempSelectedAuthors.value.forEach(author => {
    filters.push({
      id: `author-${author}`,
      type: 'author',
      value: author,
      label: `作者: ${author}`
    })
  })

  tempSelectedListIds.value.forEach(listId => {
    const list = availableLists.value.find(item => item.id === listId)
    filters.push({
      id: `list-${listId}`,
      type: 'list',
      value: listId,
      label: `清单: ${list?.name || listId}`
    })
  })

  if (tempMinScore.value > 0) {
    filters.push({
      id: 'min-score',
      type: 'minScore',
      value: tempMinScore.value,
      label: `评分 >= ${tempMinScore.value}`
    })
  }

  if (!isVideoMode.value && tempUnreadOnly.value) {
    filters.push({
      id: 'unread-only',
      type: 'unreadOnly',
      value: true,
      label: '仅未读'
    })
  }

  return filters
})

const menuActions = [
  { text: '全网搜索', icon: 'search' },
  { text: '批量管理', icon: 'setting-o' },
  { text: '刷新列表', icon: 'replay' }
]

const sortOptions = computed(() => buildSortOptions(isVideoMode.value))

const isAllItemsSelected = computed(() => {
  const scopeItems = selectionScopeItems.value.length > 0 ? selectionScopeItems.value : displayItems.value
  return isAllSelected(selectedIds.value, scopeItems, (item) => item.id)
})

// Methods
function goToSearch() {
  router.push('/search')
}

async function onMenuSelect(action) {
  if (action.text === '全网搜索') {
    goToSearch()
    return
  }
  if (action.text === '批量管理') isManageMode.value = true
  if (action.text === '刷新列表') {
    await initializePage(true)
  }
}

function onItemClick(item) {
  if (isManageMode.value) {
    toggleSelection(item)
  } else {
    const routeName = isVideoMode.value ? 'VideoRecommendationDetail' : 'RecommendationDetail'
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

async function toggleSelectAllItems() {
  try {
    if (!isAllItemsSelected.value) {
      const scopeItems = await currentStore.value.fetchCustomOrderItems?.(buildSelectionScopeQueryParams())
      selectionScopeItems.value = Array.isArray(scopeItems) ? scopeItems : []
    }
    const scopeItems = selectionScopeItems.value.length > 0 ? selectionScopeItems.value : displayItems.value
    toggleSelectAll(selectedIds, scopeItems, (item) => item.id)
  } catch (error) {
    console.error('加载全选范围失败:', error)
    showToast('加载列表失败，请稍后重试')
  }
}

function setViewMode(mode) {
  modeStore.setMediaViewMode(mode)
  showViewModeSheet.value = false
}

function isSaved(item) {
  if (isVideoMode.value) {
    return listStore.isFavoritedVideo(item)
  } else {
    return listStore.isFavorited(item)
  }
}

async function toggleSave(item) {
  if (isVideoMode.value) {
    await listStore.toggleFavoriteVideo(item.id, item.source || 'preview')
  } else {
    await listStore.toggleFavorite(item.id, item.source || 'preview')
  }
}

async function batchImportToLocal() {
  if (selectedIds.value.length === 0) return

  let res
  if (isVideoMode.value) {
    res = await videoRecStore.migrateToLocal(selectedIds.value)
  } else {
    res = await comicRecStore.migrateToLocal(selectedIds.value)
  }

  if (!res || res.code !== 200) {
    showToast(res?.msg || '导入本地库失败')
    return
  }

  const taskId = String(res?.data?.task_id || '').trim()
  if (!taskId) {
    showToast('导入任务创建失败')
    return
  }

  await importTaskStore.fetchTasks()
  importTaskStore.startPolling()
  showToast('任务已创建，请到“我的-任务中心”查看进度')

  selectedIds.value = []
  isManageMode.value = false
}

async function batchTrash() {
  if (selectedIds.value.length === 0) return
  
  if (isVideoMode.value) {
    const success = await videoRecStore.batchMoveToTrash(selectedIds.value)
    if (!success) {
      showToast('移入回收站失败')
      return
    }
  } else {
    const res = await comicRecStore.batchMoveToTrash(selectedIds.value)
    if (res.code !== 200) {
      showToast(res.msg || '移入回收站失败')
      return
    }
  }
  
  showToast('已移入回收站')
  selectedIds.value = []
  isManageMode.value = false
  await loadData(true)
}

function toggleBatchListItem(listId) {
  const index = batchSelectedListIds.value.indexOf(listId)
  if (index > -1) {
    batchSelectedListIds.value.splice(index, 1)
  } else {
    batchSelectedListIds.value.push(listId)
  }
}

async function batchAddToLists() {
  if (batchSelectedListIds.value.length === 0) {
    showToast('请选择清单')
    return
  }

  try {
    const source = 'preview'
    let successCount = 0
    
    for (const listId of batchSelectedListIds.value) {
      let result = false
      if (isVideoMode.value) {
        result = await listStore.bindVideos(listId, selectedIds.value, source)
      } else {
        result = await listStore.bindComics(listId, selectedIds.value, source)
      }
      if (result) {
        successCount += 1
      }
    }

    showBatchListPopup.value = false
    batchSelectedListIds.value = []
    selectedIds.value = []
    selectionScopeItems.value = []
    isManageMode.value = false
    const contentType = isVideoMode.value ? 'video' : 'comic'
    await listStore.fetchLists(contentType)
    showToast(`已添加到 ${successCount} 个清单`)
  } catch (error) {
    console.error('批量加入清单失败:', error)
    showToast('操作失败')
  }
}

async function clearAllFilters() {
  tempIncludeTags.value = []
  tempExcludeTags.value = []
  tempSelectedAuthors.value = []
  tempSelectedListIds.value = []
  tempMinScore.value = 0
  tempUnreadOnly.value = false
  skipNextPageFetch.value = currentPage.value !== 1
  goFirst()
  await loadData()
  selectionScopeItems.value = []
  await persistViewState()
}

function clearSearchKeyword() {
  searchKeyword.value = ''
}

async function removeFilter(filter) {
  if (filter.type === 'includeTag') {
    tempIncludeTags.value = tempIncludeTags.value.filter(id => id !== filter.value)
  } else if (filter.type === 'excludeTag') {
    tempExcludeTags.value = tempExcludeTags.value.filter(id => id !== filter.value)
  } else if (filter.type === 'author') {
    tempSelectedAuthors.value = tempSelectedAuthors.value.filter(author => author !== filter.value)
  } else if (filter.type === 'list') {
    tempSelectedListIds.value = tempSelectedListIds.value.filter(id => id !== filter.value)
  } else if (filter.type === 'minScore') {
    tempMinScore.value = 0
  } else if (filter.type === 'unreadOnly') {
    tempUnreadOnly.value = false
  }

  await applyCurrentFilters()
}

async function onSortConfirm({ selectedOptions }) {
  const nextSort = decodeSortSelection(selectedOptions?.[0]?.value || 'default')
  currentSortField.value = isSortFieldSupported(nextSort.sortField) ? nextSort.sortField : ''
  currentSortOrder.value = nextSort.sortOrder
  currentStore.value.setSortType(currentSortField.value || null, currentSortOrder.value)
  skipNextPageFetch.value = currentPage.value !== 1
  goFirst()
  const customSortSelected = currentSortField.value === 'custom'
  if (customSortSelected) {
    await loadData(true)
  } else {
    await loadData(true)
  }
  await persistViewState()
  if (customSortSelected) {
    await openCustomOrderEditor()
  }
  showSortPanel.value = false
}

function resolveOrderCover(item) {
  const candidate = String(item?.cover_path_local || item?.cover_path || '').trim()
  return candidate ? toBackendUrl(candidate) : ''
}

async function openCustomOrderEditor() {
  if (!showCustomSortBanner.value) {
    return
  }
  try {
    const result = await currentStore.value.fetchCustomOrderItems?.(buildCustomOrderQueryParams())
    customOrderItems.value = Array.isArray(result) ? result : []
    showCustomOrderEditor.value = true
  } catch (error) {
    console.error('加载自定义顺序失败:', error)
    showToast('加载自定义顺序失败')
  }
}

async function saveCustomOrder(itemIds) {
  try {
    const response = await currentStore.value.saveCustomOrder?.(itemIds)
    if (!response || response.code !== 200) {
      showToast(response?.msg || response?.message || '保存自定义顺序失败')
      return
    }

    showCustomOrderEditor.value = false
    customOrderItems.value = []
    await loadData(true)
    goFirst()
    await persistViewState()
    showToast('自定义顺序已保存')
  } catch (error) {
    console.error('保存自定义顺序失败:', error)
    showToast('保存自定义顺序失败')
  }
}

async function applyFilterAndClose() {
  await applyCurrentFilters({ resetPage: true })
  showFilterPanel.value = false
}

async function loadSupportData(force = false) {
  if (force || listStore.lists.length === 0) {
    await listStore.fetchLists()
  }
  if (isVideoMode.value) {
    if (force || tagStore.videoTags.length === 0) {
      await tagStore.fetchTags('video', force)
    }
  } else if (force || tagStore.tags.length === 0) {
    await tagStore.fetchTags('comic', force)
  }
}

async function loadData(force = false) {
  await loadSupportData(force)
  await currentStore.value.fetchRecommendations(force, buildListQueryParams())
  ensureWithinRange(isVideoMode.value ? videoRecStore.queryTotalPages : comicRecStore.queryTotalPages)
}

async function applyCurrentFilters(options = {}) {
  const shouldResetPage = options.resetPage !== false
  const shouldPersistState = options.persist !== false
  if (shouldResetPage) {
    skipNextPageFetch.value = currentPage.value !== 1
    goFirst()
  }
  await loadData()
  if (shouldPersistState) {
    await persistViewState()
  }
}

async function initializePage(force = false) {
  const currentVersion = ++initVersion.value
  pageWatchReady.value = false
  await restoreViewState()
  if (route.query.author) {
    tempSelectedAuthors.value = [route.query.author]
  }
  if (route.query.tagId) {
    tempIncludeTags.value = [route.query.tagId]
  }

  await loadData(force)
  sanitizeFilterStateForCurrentMode()
  if (currentVersion !== initVersion.value) {
    return
  }
  pageWatchReady.value = true
}

// Lifecycle
watch(() => modeStore.currentMode, async () => {
  selectedIds.value = []
  isManageMode.value = false
  await initializePage(false)
})

watch(() => route.query.author, async (newAuthor) => {
  if (newAuthor) {
    tempSelectedAuthors.value = [newAuthor]
    await applyCurrentFilters({ resetPage: true })
  }
})

watch(() => route.query.tagId, async (newTagId) => {
  if (newTagId) {
    tempIncludeTags.value = [newTagId]
    await applyCurrentFilters({ resetPage: true })
  }
})

watch(
  () => pagedItems.value.map((item) => item.id),
  () => {
    selectedIds.value = []
    selectionScopeItems.value = []
  }
)

watch(currentPage, async (page, previousPage) => {
  persistLocalBrowseState()
  if (skipNextPageFetch.value) {
    skipNextPageFetch.value = false
    return
  }
  if (!pageWatchReady.value || page === previousPage) {
    return
  }
  await loadData()
})

const debouncedSearchRefresh = debounce(() => {
  loadData()
    .then(() => persistViewState())
    .catch(() => {})
}, 260)

watch(searchKeyword, () => {
  if (suppressSearchStateWatch.value) {
    return
  }
  skipNextPageFetch.value = currentPage.value !== 1
  goFirst()
  debouncedSearchRefresh()
})

onMounted(async () => {
  await initializePage(false)
})
</script>

<style scoped>
.preview-page {
  padding-bottom: 96px;
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

.custom-sort-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 2px 12px;
}

.custom-sort-banner__copy {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 13px;
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

.toolbar-search {
  flex: 1;
  min-width: 0;
  padding: 0;
  background: transparent;
  --van-search-background: transparent;
  --van-search-content-background: transparent;
  --van-field-input-text-color: var(--text-primary);
}

.toolbar-search :deep(.van-search__content) {
  height: 40px;
  border-radius: 999px;
  border: 1px solid var(--border-soft);
  background: transparent;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
}

.toolbar-search :deep(.van-cell),
.toolbar-search :deep(.van-field),
.toolbar-search :deep(.van-field__body) {
  background: transparent;
}

.toolbar-search :deep(.van-field__control) {
  color: var(--text-primary);
}

.toolbar-search :deep(.van-field__control::placeholder) {
  color: var(--text-tertiary);
}

.toolbar-search :deep(.van-field__left-icon),
.toolbar-search :deep(.van-field__right-icon) {
  color: var(--text-tertiary);
}

.toolbar-search-clear {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition:
    background-color var(--motion-fast) var(--ease-standard),
    color var(--motion-fast) var(--ease-standard);
}

.toolbar-search-clear:hover {
  background: rgba(89, 160, 255, 0.1);
  color: var(--text-secondary);
}

.actions {
  flex-shrink: 0;
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

.batch-list-popup {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.list-count {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-left: 4px;
}

.list-action {
  padding: 16px;
}

@media (max-width: 767px) {
  .preview-page {
    padding-bottom: 110px;
  }

  .toolbar {
    top: calc(var(--mobile-header-offset, 0px) + 8px);
    padding: 8px;
    gap: 8px;
  }

  .toolbar-search :deep(.van-search__content) {
    height: 34px;
  }

  .custom-sort-banner {
    flex-direction: column;
    align-items: stretch;
  }

  .manage-bar {
    bottom: 58px;
    padding: 10px 12px;
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
