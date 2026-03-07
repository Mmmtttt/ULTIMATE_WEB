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
        :show-favorite="isVideoMode"
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

    <van-popup v-model:show="showFilterPanel" position="right" :style="{ width: '80%', height: '100%' }">
      <div class="filter-panel-content">
        <h3>高级筛选</h3>
        <AdvancedFilter
          v-model:include-tags="includeTags"
          v-model:exclude-tags="excludeTags"
          v-model:selected-authors="selectedAuthors"
          v-model:selected-list-ids="selectedListIds"
          :tags="availableTags"
          :authors="availableAuthors"
          :lists="availableLists"
          @change="onFilterChange"
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
import MediaGrid from '@/components/common/MediaGrid.vue'
import AdvancedFilter from '@/components/filter/AdvancedFilter.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { showToast, showConfirmDialog } from 'vant'

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
const isManageMode = ref(false)
const selectedIds = ref([])
const importInput = ref('')
const includeTags = ref([])
const excludeTags = ref([])
const selectedAuthors = ref([])
const selectedListIds = ref([])

// Computed
const isVideoMode = computed(() => modeStore.isVideoMode)
const currentStore = computed(() => isVideoMode.value ? videoStore : comicStore)

const items = computed(() => {
  return isVideoMode.value ? videoStore.videoList : comicStore.comicList
})

function onFilterChange(filterData) {
}

async function applyFilters() {
  if (isVideoMode.value) {
    await videoStore.filterMulti(
      includeTags.value,
      excludeTags.value,
      selectedAuthors.value,
      selectedListIds.value
    )
  } else {
    await comicStore.filterMulti(
      includeTags.value,
      excludeTags.value,
      selectedAuthors.value,
      selectedListIds.value
    )
  }
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

const availableTags = computed(() => {
  return isVideoMode.value ? tagStore.videoTags : tagStore.tags
})

const availableAuthors = computed(() => {
  const items = isVideoMode.value ? videoStore.videos : comicStore.comics
  const authors = new Set()
  items.forEach(item => {
    if (item.author) authors.add(item.author)
    if (item.creator) authors.add(item.creator)
  })
  return Array.from(authors).sort()
})

const availableLists = computed(() => {
  return listStore.lists.map(list => ({
    ...list,
    item_count: list.item_ids?.length || 0
  }))
})

const activeFilters = computed(() => {
  const filters = []
  if (currentStore.value.currentSort) {
    // simplified
  }
  return filters
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
    router.push({ name: routeName, params: { id: item.id } })
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
  return listStore.isFavoritedVideo(item) // Need to unify this API
}

async function toggleFavorite(item) {
  // Logic from VideoHome.vue
  if (isVideoMode.value) {
    await listStore.toggleFavoriteVideo(item.id)
  } else {
    // comic logic
  }
}

async function batchDelete() {
  // Implementation
  showToast('Delete logic here')
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
})

watch(() => route.query.author, (newAuthor) => {
  if (newAuthor) {
    selectedAuthors.value = [newAuthor]
    applyFilters()
  }
})

onMounted(() => {
  loadData()
  if (route.query.author) {
    selectedAuthors.value = [route.query.author]
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
</style>
