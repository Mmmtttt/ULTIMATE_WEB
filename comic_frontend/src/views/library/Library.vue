<template>
  <div class="library-page" :class="{ 'is-manage-mode': isManageMode }">
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
        :is-favorited="isFavorited"
        :selectable="isManageMode"
        :selected-ids="selectedIds"
        :show-progress="!isVideoMode"
        @click="onItemClick"
        @play="onItemPlay"
        @toggle-favorite="toggleFavorite"
        @select="toggleSelection"
        @direct-read="onDirectRead"
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

    <!-- Management Bar (Bottom) -->
    <transition name="slide-up">
      <div v-if="isManageMode" class="manage-bar">
        <div class="selection-info">已选 {{ selectedIds.length }} 项</div>
        <div class="manage-btns">
          <van-button size="small" @click="exitManageMode">取消</van-button>
          <van-button size="small" plain @click="toggleSelectAllItems">
            {{ isAllItemsSelected ? '取消全选' : '全选全部' }}
          </van-button>
          <van-button size="small" type="primary" plain :disabled="selectedIds.length === 0" @click="openBatchTaskSheet">
            批量处理
          </van-button>
          <van-button size="small" type="primary" :disabled="selectedIds.length === 0" @click="showBatchListPopup = true">
            加入清单
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

    <van-action-sheet
      v-model:show="showBatchTaskSheet"
      title="批量处理"
      :actions="batchTaskActions"
      close-on-click-action
      @select="handleBatchTaskAction"
    />

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
import { useModeStore, useComicStore, useVideoStore, useTagStore, useListStore, useImportTaskStore, useRuntimeStore, useConfigStore } from '@/stores'
import { uiStateApi } from '@/api'
import MediaGrid from '@/components/common/MediaGrid.vue'
import AppPagination from '@/components/common/AppPagination.vue'
import AdvancedFilter from '@/components/filter/AdvancedFilter.vue'
import ContentOrderEditor from '@/components/common/ContentOrderEditor.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { showToast, showConfirmDialog } from 'vant'
import { useDevice } from '@/composables/useDevice'
import { usePersistentPage } from '@/composables/useClientPagination'
import { toBackendUrl } from '@/utils/url'
import {
  buildBatchTaskActions,
  clearBrowseState,
  buildSortOptions,
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
  toggleSelectAll,
} from '@/utils'

const router = useRouter()
const route = useRoute()
const modeStore = useModeStore()
const comicStore = useComicStore()
const videoStore = useVideoStore()
const tagStore = useTagStore()
const listStore = useListStore()
const importTaskStore = useImportTaskStore()
const runtimeStore = useRuntimeStore()
const configStore = useConfigStore()
const { isDesktop } = useDevice()

// State
const showSortPanel = ref(false)
const showFilterPanel = ref(false)
const showMenu = ref(false)
const showViewModeSheet = ref(false)
const showBatchTaskSheet = ref(false)
const showBatchListPopup = ref(false)
const showCustomOrderEditor = ref(false)
const isManageMode = ref(false)
const selectedIds = ref([])
const selectedItemMap = ref({})
const batchSelectedListIds = ref([])
const searchKeyword = ref('')
const includeTags = ref([])
const excludeTags = ref([])
const selectedAuthors = ref([])
const selectedListIds = ref([])
const minScore = ref(0)
const unreadOnly = ref(false)
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
  return buildUiStateScope('library_state', isVideoMode.value)
}

function isSortFieldSupported(sortField) {
  const normalized = String(sortField || '').trim()
  if (!normalized) {
    return true
  }
  if (normalized === 'name' || normalized === 'random' || normalized === 'custom') {
    return true
  }
  if (normalized === 'date') {
    return isVideoMode.value
  }
  return normalized === 'create_time' || normalized === 'score'
}

function buildPersistedStatePayload() {
  const payload = {
    searchKeyword: String(searchKeyword.value || '').trim(),
    includeTags: includeTags.value,
    excludeTags: excludeTags.value,
    selectedAuthors: selectedAuthors.value,
    selectedListIds: selectedListIds.value,
    minScore: minScore.value,
    unreadOnly: unreadOnly.value
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
    includeTags.value = []
    excludeTags.value = []
    selectedAuthors.value = []
    selectedListIds.value = []
    minScore.value = 0
    unreadOnly.value = false
    currentSortField.value = ''
    currentSortOrder.value = 'desc'
    currentStore.value.setSortState?.(null, currentSortOrder.value)
    suppressSearchStateWatch.value = false
    return false
  }
  searchKeyword.value = String(parsed.searchKeyword || '').trim()
  includeTags.value = parsed.includeTags || []
  excludeTags.value = parsed.excludeTags || []
  selectedAuthors.value = parsed.selectedAuthors || []
  selectedListIds.value = parsed.selectedListIds || []
  minScore.value = Number(parsed.minScore) > 0 ? Number(parsed.minScore) : 0
  unreadOnly.value = Boolean(parsed.unreadOnly)
  currentSortField.value = isSortFieldSupported(parsed.sortField) ? String(parsed.sortField || '').trim() : ''
  currentSortOrder.value = normalizeSortOrder(parsed.sortOrder)
  if (Number(parsed.currentPage) >= 1) {
    currentPage.value = Math.max(1, Math.floor(Number(parsed.currentPage)))
  }
  currentStore.value.setSortState?.(currentSortField.value || null, currentSortOrder.value)
  suppressSearchStateWatch.value = false
  return true
}

function sanitizeFilterStateForCurrentMode() {
  const availableTagIds = new Set(availableTags.value.map((item) => item.id))
  includeTags.value = includeTags.value.filter((tagId) => availableTagIds.has(tagId))
  excludeTags.value = excludeTags.value.filter((tagId) => availableTagIds.has(tagId))
}

function buildListQueryParams(options = {}) {
  const params = {
    paginate: 1,
    summary: 1,
    page: currentPage.value,
    page_size: pageSize.value,
  }
  if (options.includeAvailableAuthors) {
    params.include_available_authors = 1
  }

  if (currentSortField.value) {
    params.sort_type = currentSortField.value
    params.sort_order = currentSortOrder.value
  }
  if (String(searchKeyword.value || '').trim()) {
    params.keyword = String(searchKeyword.value || '').trim()
  }
  if (includeTags.value.length > 0) {
    params.include_tag_ids = [...includeTags.value]
  }
  if (excludeTags.value.length > 0) {
    params.exclude_tag_ids = [...excludeTags.value]
  }
  if (selectedAuthors.value.length > 0) {
    params.authors = [...selectedAuthors.value]
  }
  if (selectedListIds.value.length > 0) {
    params.list_ids = [...selectedListIds.value]
  }
  if (Number(minScore.value) > 0) {
    params.min_score = Number(minScore.value)
  }
  if (unreadOnly.value && !isVideoMode.value) {
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
const currentStore = computed(() => isVideoMode.value ? videoStore : comicStore)

const items = computed(() => {
  return isVideoMode.value ? videoStore.videoList : comicStore.comicList
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

const paginationStorageKey = computed(() => `library_${isVideoMode.value ? 'video' : 'comic'}`)
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
  ensureWithinRange,
} = usePersistentPage(paginationStorageKey)
const totalItems = computed(() => {
  const total = isVideoMode.value ? videoStore.queryTotalCount : comicStore.queryTotalCount
  return Number(total) || 0
})
const pagedItems = computed(() => items.value)

async function applyFilters(options = {}) {
  const shouldResetPage = options.resetPage !== false
  const shouldClosePanel = options.closePanel !== false
  const shouldPersistState = options.persist !== false
  if (shouldResetPage) {
    clearSelection()
    skipNextPageFetch.value = currentPage.value !== 1
    goFirst()
  }
  await loadData()
  if (shouldPersistState) {
    await persistViewState()
  }
  if (shouldClosePanel) {
    showFilterPanel.value = false
  }
}

const isLoading = computed(() => currentStore.value.loading)

const searchPlaceholder = computed(() => 
  isVideoMode.value ? '实时搜索视频...' : '实时搜索漫画...'
)

const emptyTitle = computed(() => 
  isVideoMode.value ? '暂无视频' : '暂无漫画'
)

const emptyDescription = computed(() => {
  return String(searchKeyword.value || '').trim()
    ? '没有找到匹配的内容'
    : '快去导入一些内容吧'
})

const menuActions = [
  { text: '全网搜索', icon: 'search' },
  { text: '批量管理', icon: 'setting-o' },
  { text: '刷新列表', icon: 'replay' }
]

const selectedItems = computed(() => {
  const selectedIdSet = new Set(selectedIds.value)
  const byId = {}
  const rememberItem = (item) => {
    const id = String(item?.id || '').trim()
    if (id && selectedIdSet.has(id) && !byId[id]) {
      byId[id] = item
    }
  }
  selectionScopeItems.value.forEach(rememberItem)
  Object.values(selectedItemMap.value).forEach(rememberItem)
  displayItems.value.forEach(rememberItem)
  return selectedIds.value.map((id) => byId[id]).filter(Boolean)
})

const batchTaskActions = computed(() => {
  return buildBatchTaskActions({
    contentType: isVideoMode.value ? 'video' : 'comic',
    selectedItems: selectedItems.value,
    thirdPartyEnabled: runtimeStore.thirdPartyEnabled,
    supportsVideoThumbnailBatch: runtimeStore.supportsLocalVideoThumbnailBatch,
  }).map((action) => ({
    ...action,
    subname: action.reason || '',
  }))
})

const sortOptions = computed(() => buildSortOptions(isVideoMode.value))

async function onSortConfirm({ selectedOptions }) {
  showSortPanel.value = false
  try {
    const selectedValue = selectedOptions?.[0]?.value || 'default'
    const nextSort = decodeSortSelection(selectedValue)
    currentSortField.value = isSortFieldSupported(nextSort.sortField) ? nextSort.sortField : ''
    currentSortOrder.value = nextSort.sortOrder
    currentStore.value.setSortState?.(currentSortField.value || null, currentSortOrder.value)
    clearSelection()
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
  } catch (e) {
    console.error('排序失败:', e)
    showToast('排序失败')
  }
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

const availableTags = computed(() => {
  return isVideoMode.value ? tagStore.videoTags : tagStore.tags
})

const availableAuthors = computed(() => {
  return isVideoMode.value ? videoStore.availableAuthors : comicStore.availableAuthors
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
  if (selectionScopeItems.value.length === 0) {
    return false
  }
  return isAllSelected(selectedIds.value, selectionScopeItems.value, (item) => item.id)
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
    const routeName = isVideoMode.value ? 'VideoDetail' : 'ComicDetail'
    router.push({ name: routeName, params: { id: item.id }, query: route.query })
  }
}

function onItemPlay(item) {
  if (isManageMode.value) return
  router.push({ name: 'VideoDetail', params: { id: item.id }, query: { ...route.query, autoplay: '1' } })
}

function onDirectRead(item) {
  if (isManageMode.value) return
  router.push({ name: 'ComicDetail', params: { id: item.id }, query: { autoread: '1' } })
}

function toggleSelection(item) {
  const id = item.id
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter(i => i !== id)
    const nextMap = { ...selectedItemMap.value }
    delete nextMap[id]
    selectedItemMap.value = nextMap
  } else {
    selectedIds.value.push(id)
    selectedItemMap.value = { ...selectedItemMap.value, [id]: item }
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
    rememberSelectedItems(scopeItems)
  } catch (error) {
    console.error('加载全选范围失败:', error)
    showToast('加载列表失败，请稍后重试')
  }
}

function rememberSelectedItems(items = []) {
  const selectedIdSet = new Set(selectedIds.value)
  const nextMap = { ...selectedItemMap.value }
  for (const item of Array.isArray(items) ? items : []) {
    const id = String(item?.id || '').trim()
    if (id && selectedIdSet.has(id)) {
      nextMap[id] = item
    }
  }
  selectedItemMap.value = nextMap
}

function clearSelection() {
  selectedIds.value = []
  selectedItemMap.value = {}
  selectionScopeItems.value = []
}

function exitManageMode() {
  clearSelection()
  isManageMode.value = false
}

async function openBatchTaskSheet() {
  if (selectedIds.value.length === 0) {
    return
  }
  await runtimeStore.fetchRuntime()
  showBatchTaskSheet.value = true
}

async function handleBatchTaskAction(action) {
  if (!action || action.disabled) {
    if (action?.reason) {
      showToast(action.reason)
    }
    return
  }

  const eligibleIds = Array.isArray(action.eligibleIds) ? action.eligibleIds : []
  if (eligibleIds.length === 0) {
    showToast('当前没有可执行的内容')
    return
  }

  try {
    await showConfirmDialog({
      title: action.name,
      message: `确定对 ${eligibleIds.length} 项内容执行“${action.name}”吗？`
    })
  } catch {
    return
  }

  const created = await importTaskStore.createContentTask({
    taskType: action.taskType,
    itemIds: eligibleIds
  })
  if (created) {
    showBatchTaskSheet.value = false
    clearSelection()
    isManageMode.value = false
  }
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
      const res = await comicStore.batchMoveToTrash(selectedIds.value)
      success = res.code === 200
    }
    
    if (!success) {
      showToast('移入回收站失败')
      return
    }
    
    showToast('已移入回收站')
    clearSelection()
    isManageMode.value = false
    await loadData(true)
  } catch (e) {
    if (e !== 'cancel') {
      showToast('移入回收站失败')
    }
  }
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
    const source = 'local'
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
  clearSelection()
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
  includeTags.value = []
  excludeTags.value = []
  selectedAuthors.value = []
  selectedListIds.value = []
  minScore.value = 0
  unreadOnly.value = false
  clearSelection()
  skipNextPageFetch.value = currentPage.value !== 1
  goFirst()
  await loadData()
  await persistViewState()
}

function clearSearchKeyword() {
  searchKeyword.value = ''
}

async function removeFilter(filter) {
  clearSelection()
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

async function loadSupportData(force = false) {
  if (force || listStore.lists.length === 0) {
    await listStore.fetchLists()
  }
  if (isVideoMode.value) {
    if (force || tagStore.videoTags.length === 0) {
      await tagStore.fetchTags('video', force)
    }
  } else {
    if (force || tagStore.tags.length === 0) {
      await tagStore.fetchTags('comic', force)
    }
  }
}

async function loadData(force = false, options = {}) {
  await loadSupportData(force)
  const params = buildListQueryParams({
    includeAvailableAuthors: options.includeAvailableAuthors === true || shouldRequestAvailableAuthors(),
  })
  if (isVideoMode.value) {
    await videoStore.fetchList(params)
  } else {
    await comicStore.fetchComics(force, params)
  }
  ensureWithinRange(isVideoMode.value ? videoStore.queryTotalPages : comicStore.queryTotalPages)
}

function shouldRequestAvailableAuthors() {
  return (isVideoMode.value ? videoStore.availableAuthors : comicStore.availableAuthors).length === 0
}

async function initializePage(force = false) {
  const currentVersion = ++initVersion.value
  pageWatchReady.value = false
  await restoreViewState()
  if (route.query.author) {
    selectedAuthors.value = [route.query.author]
  }
  if (route.query.tagId) {
    includeTags.value = [route.query.tagId]
  }

  await loadData(force, { includeAvailableAuthors: true })
  sanitizeFilterStateForCurrentMode()
  if (currentVersion !== initVersion.value) {
    return
  }
  pageWatchReady.value = true
}

// Lifecycle
watch(() => modeStore.currentMode, async () => {
  clearSelection()
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

watch(
  () => pagedItems.value.map((item) => item.id),
  () => {
    rememberSelectedItems(pagedItems.value)
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
  clearSelection()
  skipNextPageFetch.value = currentPage.value !== 1
  goFirst()
  debouncedSearchRefresh()
})

onMounted(async () => {
  await initializePage(false)
})
</script>

<style scoped>
.library-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  --manage-bar-reserved-space: 0px;
  padding-bottom: var(--manage-bar-reserved-space);
  transition: padding-bottom 180ms var(--ease-standard);
}

.library-page.is-manage-mode {
  --manage-bar-reserved-space: 112px;
}

.library-page.is-manage-mode .content-pagination {
  margin-bottom: 92px;
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
  --van-search-content-background: var(--surface-1);
  --van-field-input-text-color: var(--text-primary);
}

.toolbar-search :deep(.van-search__content) {
  height: 40px;
  border-radius: 999px;
  border: 1px solid var(--border-soft);
  background: var(--surface-1);
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

.content-area {
  flex: 1;
  min-height: 200px;
}

.content-pagination {
  margin-top: auto;
  padding: 8px 8px 12px;
  background: var(--surface-1);
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
    align-items: stretch;
    flex-direction: column;
  }

  .manage-btns :deep(.van-button) {
    flex: 1 1 calc(33.333% - 8px);
    min-width: 74px;
  }

  .library-page.is-manage-mode {
    --manage-bar-reserved-space: 156px;
  }

  .library-page.is-manage-mode .content-pagination {
    margin-bottom: 136px;
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
