<template>
  <div class="library-page">
    <!-- Filter & Sort Bar -->
    <div class="toolbar">
      <div class="search-trigger" @click="goToSearch">
        <van-icon name="search" />
        <span>{{ searchPlaceholder }}</span>
      </div>
      
      <div class="actions">
        <van-button size="small" plain @click="showSortPanel = true">
          <van-icon name="sort" />
        </van-button>
        <van-button size="small" plain @click="showFilterPanel = true">
          <van-icon name="filter-o" />
        </van-button>
        <van-button size="small" plain @click="showViewModeSheet = true">
          <van-icon name="apps-o" />
        </van-button>
        <van-popover
          v-model:show="showMenu"
          :actions="menuActions"
          placement="bottom-end"
          @select="onMenuSelect"
        >
          <template #reference>
            <van-button size="small" plain>
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
        :items="items" 
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

    <van-popup v-model:show="showFilterPanel" position="right" :style="{ width: '80%', height: '100%' }">
      <div class="filter-panel-content">
        <h3>高级筛选</h3>
        <AdvancedFilter
          v-model:include-tags="includeTags"
          v-model:exclude-tags="excludeTags"
          v-model:selected-authors="selectedAuthors"
          v-model:selected-list-ids="selectedListIds"
          v-model:min-score="minScore"
          :tags="availableTags"
          :authors="availableAuthors"
          :lists="availableLists"
          :is-video-mode="isVideoMode"
        />
        <div class="filter-actions">
          <van-button block type="primary" @click="applyFilters">应用</van-button>
        </div>
      </div>
    </van-popup>

    <!-- Import Modal -->
    <van-dialog 
      v-model:show="showImportDialog" 
      title="快速导入" 
      show-cancel-button
      @confirm="handleQuickImport"
    >
      <van-field v-model="importInput" label="ID/链接" placeholder="输入内容ID" />
    </van-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useModeStore, useComicStore, useVideoStore, useTagStore, useListStore } from '@/stores'
import { comicApi } from '@/api'
import MediaGrid from '@/components/common/MediaGrid.vue'
import AdvancedFilter from '@/components/filter/AdvancedFilter.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { showToast, showConfirmDialog } from 'vant'
import { extractAuthors, getFilterStorageKey as makeFilterStorageKey, isAllSelected, loadFromSession, saveToSession, toggleSelectAll } from '@/utils'

const router = useRouter()
const route = useRoute()
const modeStore = useModeStore()
const comicStore = useComicStore()
const videoStore = useVideoStore()
const tagStore = useTagStore()
const listStore = useListStore()

// State
const showSortPanel = ref(false)
const showFilterPanel = ref(false)
const showMenu = ref(false)
const showImportDialog = ref(false)
const showViewModeSheet = ref(false)
const isManageMode = ref(false)
const selectedIds = ref([])
const importInput = ref('')
const includeTags = ref([])
const excludeTags = ref([])
const selectedAuthors = ref([])
const selectedListIds = ref([])
const minScore = ref(0)
const mediaViewMode = computed(() => modeStore.mediaViewMode)
const viewModeOptions = [
  { value: 'large', label: '大图标' },
  { value: 'medium', label: '中图标' },
  { value: 'small', label: '小图标' },
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
    minScore: minScore.value
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
  return includeTags.value.length > 0 || excludeTags.value.length > 0 || selectedAuthors.value.length > 0 || selectedListIds.value.length > 0 || minScore.value > 0
}

// Computed
const isVideoMode = computed(() => modeStore.isVideoMode)
const currentStore = computed(() => isVideoMode.value ? videoStore : comicStore)

const items = computed(() => {
  return isVideoMode.value ? videoStore.videoList : comicStore.comicList
})

async function applyFilters() {
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
      minScore.value
    )
  }
  saveFilterState()
  showFilterPanel.value = false
}

const isLoading = computed(() => currentStore.value.loading)

const searchPlaceholder = computed(() => 
  isVideoMode.value ? '搜索视频...' : '搜索漫画...'
)

const emptyTitle = computed(() => 
  isVideoMode.value ? '暂无视频' : '暂无漫画'
)

const menuActions = [
  { text: '导入内容', icon: 'plus' },
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
      label: `评分 ≥ ${minScore.value}`
    })
  }

  return filters
})

const isAllItemsSelected = computed(() => {
  return isAllSelected(selectedIds.value, items.value, (item) => item.id)
})

// Methods
function goToSearch() {
  router.push('/search')
}

function onMenuSelect(action) {
  if (action.text === '导入内容') showImportDialog.value = true
  if (action.text === '批量管理') isManageMode.value = true
  if (action.text === '刷新列表') loadData(true)
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
  toggleSelectAll(selectedIds, items.value, (item) => item.id)
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
  currentStore.value.clearFilter()
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
  }

  await applyFilters()
}

async function loadData(force = false) {
  if (listStore.lists.length === 0) {
    await listStore.fetchLists()
  }
  if (isVideoMode.value) {
    if (tagStore.videoTags.length === 0) await tagStore.fetchTags('video')
    await videoStore.fetchList()
  } else {
    if (tagStore.tags.length === 0) await tagStore.fetchTags('comic')
    await comicStore.fetchComics()
  }
}

function handleQuickImport() {
  // Logic
}

// Lifecycle
watch(() => modeStore.currentMode, () => {
  loadData()
  selectedIds.value = []
  isManageMode.value = false
  restoreFilterState()
  applyFilters()
})

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

onMounted(() => {
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
})
</script>

<style scoped>
.library-page {
  padding-bottom: 80px; /* Space for manage bar or tabbar */
}

.toolbar {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: #fff;
  position: sticky;
  top: 0;
  z-index: 10;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}

.search-trigger {
  flex: 1;
  background: #f7f8fa;
  height: 36px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  color: #969799;
  font-size: 14px;
  gap: 8px;
  margin-right: 12px;
  cursor: pointer;
}

.actions {
  display: flex;
  gap: 8px;
}

.loading-center {
  padding: 40px;
  text-align: center;
}

.manage-bar {
  position: fixed;
  bottom: 0; /* Adjust if tabbar exists */
  left: 0;
  right: 0;
  background: #fff;
  padding: 12px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 -2px 10px rgba(0,0,0,0.05);
  z-index: 100;
}

/* Video Mode Adjustments */
.video-mode :deep(.media-cover) {
  aspect-ratio: 16/9;
}

.filter-panel-content {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.filter-actions {
  margin-top: auto;
}

.view-mode-sheet {
  padding-bottom: 8px;
}
</style>
