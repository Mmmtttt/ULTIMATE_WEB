<template>
  <div class="preview-page">
    <!-- Filter & Sort Bar -->
    <div class="toolbar">
      <div class="search-trigger" @click="goToSearch">
        <van-icon name="search" />
        <span>{{ searchPlaceholder }}</span>
      </div>
      
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

    <!-- Content Area -->
    <div class="content-area">
      <van-loading v-if="isLoading" class="loading-center" />
      
      <EmptyState 
        v-else-if="items.length === 0" 
        :title="emptyTitle" 
        description="暂无推荐内容"
      />

      <MediaGrid 
        v-else 
        :items="items" 
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

    <!-- Management Bar -->
    <transition name="slide-up">
      <div v-if="isManageMode" class="manage-bar">
        <div class="selection-info">已选 {{ selectedIds.length }} 项</div>
        <div class="manage-btns">
          <van-button size="small" @click="isManageMode = false">取消</van-button>
          <van-button size="small" plain @click="toggleSelectAllItems">
            {{ isAllItemsSelected ? '取消全选' : '全选' }}
          </van-button>
          <van-button size="small" type="primary" :disabled="selectedIds.length === 0" @click="batchSave">
            批量保存
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
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useModeStore, useRecommendationStore, useVideoRecommendationStore, useListStore, useTagStore } from '@/stores'
import { recommendationApi } from '@/api'
import MediaGrid from '@/components/common/MediaGrid.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AdvancedFilter from '@/components/filter/AdvancedFilter.vue'
import { showToast } from 'vant'
import { useDevice } from '@/composables/useDevice'
import { extractAuthors, getFilterStorageKey as makeFilterStorageKey, isAllSelected, loadFromSession, saveToSession, toggleSelectAll } from '@/utils'

const router = useRouter()
const route = useRoute()
const modeStore = useModeStore()
const comicRecStore = useRecommendationStore()
const videoRecStore = useVideoRecommendationStore()
const listStore = useListStore()
const tagStore = useTagStore()
const { isDesktop, isMobile } = useDevice()

// State
const showSortPanel = ref(false)
const showMenu = ref(false)
const showViewModeSheet = ref(false)
const isManageMode = ref(false)
const selectedIds = ref([])
const showFilterPanel = ref(false)
const tempIncludeTags = ref([])
const tempExcludeTags = ref([])
const tempSelectedAuthors = ref([])
const tempSelectedListIds = ref([])
const tempMinScore = ref(0)
const tempUnreadOnly = ref(false)
const mediaViewMode = computed(() => modeStore.mediaViewMode)
const viewModeOptions = [
  { value: 'large', label: '大图标' },
  { value: 'medium', label: '中图标' },
  { value: 'small', label: '小图标' },
  { value: 'list', label: '列表' }
]

function getFilterStorageKey() {
  return makeFilterStorageKey('preview_filters', isVideoMode.value)
}

function saveFilterState() {
  const payload = {
    includeTags: tempIncludeTags.value,
    excludeTags: tempExcludeTags.value,
    selectedAuthors: tempSelectedAuthors.value,
    selectedListIds: tempSelectedListIds.value,
    minScore: tempMinScore.value,
    unreadOnly: tempUnreadOnly.value
  }
  saveToSession(getFilterStorageKey(), payload)
}

async function restoreFilterState() {
  const parsed = loadFromSession(getFilterStorageKey())
  if (!parsed) {
    return
  }
  tempIncludeTags.value = parsed.includeTags || []
  tempExcludeTags.value = parsed.excludeTags || []
  tempSelectedAuthors.value = parsed.selectedAuthors || []
  tempSelectedListIds.value = parsed.selectedListIds || []
  tempMinScore.value = Number(parsed.minScore) > 0 ? Number(parsed.minScore) : 0
  tempUnreadOnly.value = Boolean(parsed.unreadOnly)
  await currentStore.value.filterMulti(
    tempIncludeTags.value,
    tempExcludeTags.value,
    tempSelectedAuthors.value,
    tempSelectedListIds.value,
    tempMinScore.value,
    tempUnreadOnly.value
  )
}

// Computed
const isVideoMode = computed(() => modeStore.isVideoMode)
const currentStore = computed(() => isVideoMode.value ? videoRecStore : comicRecStore)

const items = computed(() => {
  return isVideoMode.value ? videoRecStore.recommendationList : comicRecStore.recommendationList
})

const isLoading = computed(() => currentStore.value.loading)

const searchPlaceholder = computed(() => 
  isVideoMode.value ? '搜索推荐视频...' : '搜索推荐漫画...'
)

const emptyTitle = computed(() => 
  isVideoMode.value ? '暂无推荐视频' : '暂无推荐漫画'
)

const availableTags = computed(() => isVideoMode.value ? tagStore.videoTags : tagStore.tags)

const availableAuthors = computed(() => {
  const items = isVideoMode.value ? videoRecStore.recommendations : comicRecStore.recommendations
  return extractAuthors(items)
})

const availableLists = computed(() => {
  return listStore.lists.map(list => ({
    ...list,
    item_count: list.item_ids?.length || 0
  }))
})

const menuActions = [
  { text: '批量管理', icon: 'setting-o' },
  { text: '刷新列表', icon: 'replay' }
]

const sortOptions = computed(() => [
  { text: '最近更新', value: 'create_time' },
  { text: '评分最高', value: 'score' },
  { text: '最新发布', value: 'date' }
])

const isAllItemsSelected = computed(() => {
  return isAllSelected(selectedIds.value, items.value, (item) => item.id)
})

// Methods
function goToSearch() {
  router.push('/search?source=preview')
}

function onMenuSelect(action) {
  if (action.text === '批量管理') isManageMode.value = true
  if (action.text === '刷新列表') loadData(true)
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

function toggleSelectAllItems() {
  toggleSelectAll(selectedIds, items.value, (item) => item.id)
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

async function batchSave() {
  showToast('Batch save')
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
    const res = await recommendationApi.batchMoveToTrash(selectedIds.value)
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

async function onSortConfirm({ selectedOptions }) {
  const sortType = selectedOptions?.[0]?.value
  currentStore.value.setSortType(sortType)
  await loadData(true)
  showSortPanel.value = false
}

async function applyFilterAndClose() {
  await currentStore.value.filterMulti(
    tempIncludeTags.value,
    tempExcludeTags.value,
    tempSelectedAuthors.value,
    tempSelectedListIds.value,
    tempMinScore.value,
    tempUnreadOnly.value
  )
  saveFilterState()
  showFilterPanel.value = false
}

async function loadData(force = false) {
  if (listStore.lists.length === 0) {
    await listStore.fetchLists()
  }
  await currentStore.value.fetchRecommendations(force)
}

// Lifecycle
watch(() => modeStore.currentMode, () => {
  loadData()
  selectedIds.value = []
  isManageMode.value = false
  restoreFilterState()
})

watch(() => route.query.author, (newAuthor) => {
  if (newAuthor) {
    tempSelectedAuthors.value = [newAuthor]
    applyFilterAndClose()
  }
})

watch(() => route.query.tagId, (newTagId) => {
  if (newTagId) {
    tempIncludeTags.value = [newTagId]
    applyFilterAndClose()
  }
})

onMounted(() => {
  loadData()
  restoreFilterState()
  if (route.query.author) {
    tempSelectedAuthors.value = [route.query.author]
    applyFilterAndClose()
  }
  if (route.query.tagId) {
    tempIncludeTags.value = [route.query.tagId]
    applyFilterAndClose()
  }
})
</script>

<style scoped>
.preview-page {
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

.content-area {
  min-height: 200px;
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
  background: rgba(255, 255, 255, 0.92);
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

.video-mode :deep(.media-cover) {
  aspect-ratio: 16 / 9;
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
  .preview-page {
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
}

@media (min-width: 1024px) {
  .manage-bar {
    left: calc(var(--sidebar-width) + 22px);
    right: 22px;
    bottom: 18px;
  }
}
</style>
