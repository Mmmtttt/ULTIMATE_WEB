<template>
  <div class="home">
    <van-nav-bar title="漫画库">
      <template #right>
        <van-dropdown-menu direction="down">
          <van-dropdown-item v-model="menuValue" :options="menuOptions" @change="handleMenuChange" />
        </van-dropdown-menu>
      </template>
    </van-nav-bar>
    
    <div class="search-bar">
      <van-search
        v-model="keyword"
        placeholder="搜索漫画ID、名称、作者、标签"
        @search="handleSearch"
        @clear="clearSearch"
        shape="round"
      />
      <van-button 
        size="small" 
        type="primary" 
        plain 
        @click="showSortPanel = true"
        class="sort-btn"
      >
        排序
        <van-icon name="sort" />
      </van-button>
      <van-button 
        size="small" 
        type="primary" 
        plain 
        @click="showFilterPanel = true"
        class="filter-btn"
      >
        筛选
        <van-icon name="filter-o" />
      </van-button>
    </div>
    
    <div v-if="isFiltering || currentSortType" class="active-filter-bar">
      <van-tag 
        v-if="currentSortType" 
        type="primary" 
        closeable 
        @close="clearSort"
        class="filter-tag"
      >
        {{ sortLabel }}
      </van-tag>
      <van-tag 
        v-for="tag in selectedIncludeTags" 
        :key="tag.id" 
        type="primary" 
        closeable 
        @close="removeIncludeTag(tag.id)"
        class="filter-tag"
      >
        包含: {{ tag.name }}
      </van-tag>
      <van-tag 
        v-for="tag in selectedExcludeTags" 
        :key="tag.id" 
        type="danger" 
        closeable 
        @close="removeExcludeTag(tag.id)"
        class="filter-tag"
      >
        排除: {{ tag.name }}
      </van-tag>
      <van-button size="mini" plain @click="clearAllFilters">清空</van-button>
    </div>
    
    <!-- 批量操作模式 -->
    <div v-if="isManageMode" class="manage-bar">
      <span class="selected-info">已选 {{ selectedComicIds.length }} 个</span>
      <div class="manage-actions">
        <van-button size="small" type="primary" :disabled="selectedComicIds.length === 0" @click="batchMoveToTrash">
          移入回收站
        </van-button>
        <van-button size="small" plain @click="cancelManageMode">取消</van-button>
      </div>
    </div>
    
    <!-- 加载状态 -->
    <van-loading v-if="isLoading" type="spinner" color="#1989fa" />
    
    <!-- 空状态 -->
    <EmptyState
      v-else-if="!hasResults"
      icon="📚"
      title="暂无漫画"
      :description="isFiltering ? '没有找到匹配的漫画' : '还没有添加任何漫画'"
    >
      <template #action>
        <van-button v-if="isFiltering" type="primary" @click="clearAllFilters">
          清除筛选
        </van-button>
      </template>
    </EmptyState>
    
    <!-- 漫画网格 - 管理模式 -->
    <div v-else-if="isManageMode" class="comic-select-grid">
      <div 
        v-for="comic in results" 
        :key="comic.id" 
        class="comic-select-item"
        :class="{ selected: selectedComicIds.includes(comic.id) }"
        @click="toggleComicSelection(comic.id)"
      >
        <van-image 
          :src="getCoverUrl(comic.cover_path)" 
          fit="contain" 
          class="comic-thumb"
        />
        <div class="comic-title-line">{{ comic.title }}</div>
        <div class="select-check" v-if="selectedComicIds.includes(comic.id)">
          <van-icon name="success" />
        </div>
      </div>
    </div>
    
    <!-- 漫画网格 - 普通模式 -->
    <ComicGrid
      v-else
      :comics="results"
      @card-click="goToDetail"
      @author-click="handleAuthorClick"
    />
    
    <!-- 标签筛选面板 -->
    <van-popup 
      v-model:show="showFilterPanel" 
      position="bottom" 
      round 
      :style="{ height: '70%' }"
    >
      <div class="filter-panel">
        <van-nav-bar title="标签筛选" left-text="关闭" @click-left="showFilterPanel = false">
          <template #right>
            <van-button type="primary" size="small" @click="applyFilterAndClose">
              确定
            </van-button>
          </template>
        </van-nav-bar>
        
        <TagFilter
          v-model:include-tags="includeTags"
          v-model:exclude-tags="excludeTags"
          :tags="tags"
          show-count
          @change="handleFilterChange"
        />
      </div>
    </van-popup>
    
    <van-popup 
      v-model:show="showSortPanel" 
      position="bottom" 
      round 
      :style="{ height: '50%' }"
    >
      <div class="sort-panel">
        <van-nav-bar title="排序方式" left-text="关闭" @click-left="showSortPanel = false" />
        <van-cell-group>
          <van-cell 
            title="最近导入" 
            label="按导入时间倒序排列"
            clickable 
            @click="setSortType('create_time')"
          >
            <template #right-icon>
              <van-icon v-if="currentSortType === 'create_time'" name="success" color="#1989fa" />
            </template>
          </van-cell>
          <van-cell 
            title="按评分从高到低" 
            clickable 
            @click="setSortType('score')"
          >
            <template #right-icon>
              <van-icon v-if="currentSortType === 'score'" name="success" color="#1989fa" />
            </template>
          </van-cell>
          <van-cell 
            title="按最后阅读时间" 
            clickable 
            @click="setSortType('read_time')"
          >
            <template #right-icon>
              <van-icon v-if="currentSortType === 'read_time'" name="success" color="#1989fa" />
            </template>
          </van-cell>
          <van-cell 
            title="已读/未读（未读优先）" 
            clickable 
            @click="setSortType('read_status')"
          >
            <template #right-icon>
              <van-icon v-if="currentSortType === 'read_status'" name="success" color="#1989fa" />
            </template>
          </van-cell>
        </van-cell-group>
      </div>
    </van-popup>
    
    <!-- 底部导航 -->
    <van-tabbar v-model="active" route>
      <van-tabbar-item icon="home-o" to="/">主页</van-tabbar-item>
      <van-tabbar-item icon="star-o" to="/recommendation">推荐</van-tabbar-item>
      <van-tabbar-item icon="user-o" to="/mine">我的</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showConfirmDialog, showSuccessToast, showFailToast } from 'vant'
import { useComicStore, useTagStore, useImportTaskStore } from '@/stores'
import { useSearch } from '@/composables'
import { ComicGrid, EmptyState, TagFilter } from '@/components'
import { comicApi } from '@/api'
import request from '@/api/request'

const router = useRouter()
const route = useRoute()
const comicStore = useComicStore()
const tagStore = useTagStore()
const importTaskStore = useImportTaskStore()

const {
  keyword,
  includeTags,
  excludeTags,
  loading,
  results,
  hasResults,
  isFiltering,
  tags,
  selectedIncludeTags,
  selectedExcludeTags,
  tagNameMap,
  search,
  clearSearch,
  filterByTags,
  clearAllFilters,
  init
} = useSearch()

const active = ref(0)
const showFilterPanel = ref(false)
const showSortPanel = ref(false)
const currentSortType = ref('')

// 管理模式相关
const isManageMode = ref(false)
const selectedComicIds = ref([])
const menuValue = ref(0)
const menuOptions = [
  { text: '更多操作', value: 0 },
  { text: '管理漫画', value: 1 }
]

const isLoading = computed(() => loading.value || comicStore.loading)

const sortLabel = computed(() => {
  const labels = {
    'create_time': '最近导入',
    'score': '按评分',
    'read_time': '按阅读时间',
    'read_status': '已读/未读'
  }
  return labels[currentSortType.value] || ''
})

function handleMenuChange(value) {
  if (value === 1) {
    isManageMode.value = true
    selectedComicIds.value = []
    menuValue.value = 0
  }
}

function cancelManageMode() {
  isManageMode.value = false
  selectedComicIds.value = []
}

function toggleComicSelection(comicId) {
  const index = selectedComicIds.value.indexOf(comicId)
  if (index > -1) {
    selectedComicIds.value.splice(index, 1)
  } else {
    selectedComicIds.value.push(comicId)
  }
}

function getCoverUrl(coverPath) {
  if (!coverPath) return ''
  if (coverPath.startsWith('http')) return coverPath
  if (coverPath.startsWith('/static/')) return coverPath
  if (coverPath.startsWith('/')) return coverPath
  return `/${coverPath}`
}

async function batchMoveToTrash() {
  if (selectedComicIds.value.length === 0) {
    showToast('请先选择漫画')
    return
  }
  
  try {
    await showConfirmDialog({
      title: '确认操作',
      message: `确定将 ${selectedComicIds.value.length} 个漫画移入回收站吗？`
    })
    
    const res = await comicApi.batchMoveToTrash(selectedComicIds.value)
    if (res.code === 200) {
      showToast(res.msg || '已移入回收站')
      selectedComicIds.value = []
      isManageMode.value = false
      await comicStore.fetchComics(true, currentSortType.value ? { sort_type: currentSortType.value } : {})
    } else {
      showToast(res.msg || '操作失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      showToast('操作失败')
    }
  }
}

function handleSearch() {
  search()
}

function goToDetail(comic) {
  router.push(`/comic/${comic.id}`)
}

function handleAuthorClick(author) {
  keyword.value = author
  search()
}

function removeIncludeTag(tagId) {
  const index = includeTags.value.indexOf(tagId)
  if (index > -1) {
    includeTags.value.splice(index, 1)
  }
}

function removeExcludeTag(tagId) {
  const index = excludeTags.value.indexOf(tagId)
  if (index > -1) {
    excludeTags.value.splice(index, 1)
  }
}

function handleFilterChange() {
  if (includeTags.value.length > 0 || excludeTags.value.length > 0) {
    filterByTags()
  } else {
    comicStore.clearFilter()
  }
}

function applyFilterAndClose() {
  showFilterPanel.value = false
}

async function setSortType(sortType) {
  currentSortType.value = sortType
  showSortPanel.value = false
  comicStore.clearFilter()
  await comicStore.fetchComics(true, { sort_type: sortType })
}

function clearSort() {
  currentSortType.value = ''
  comicStore.clearFilter()
  comicStore.fetchComics(true)
}

onMounted(async () => {
  await init()
  
  const tagId = route.query.tagId
  if (tagId && !includeTags.value.includes(tagId)) {
    includeTags.value = [tagId]
    await filterByTags()
  }
  
  const importIds = route.query.importIds
  if (importIds) {
    const ids = importIds.split(',').filter(id => id.trim())
    if (ids.length > 0) {
      await createImportFromIds(ids, 'home')
      router.replace({ query: {} })
    }
  }
})

async function createImportFromIds(ids, target) {
  try {
    const params = {
      import_type: ids.length === 1 ? 'by_id' : 'by_list',
      target: target,
      platform: 'JM',
      comic_id: ids.length === 1 ? ids[0] : undefined,
      comic_ids: ids.length > 1 ? ids : undefined
    }
    
    const result = await importTaskStore.createImportTask(params)
    if (result) {
      showSuccessToast(`已创建导入任务，共 ${ids.length} 个漫画`)
    }
  } catch (error) {
    console.error('创建导入任务失败:', error)
    showFailToast('创建导入任务失败')
  }
}
</script>

<style scoped>
.home {
  padding-bottom: 50px;
  min-height: 100vh;
  background: #f5f5f5;
}

.search-bar {
  padding: 10px 16px;
  background: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
}

.search-bar .van-search {
  flex: 1;
  padding: 0;
}

.sort-btn,
.filter-btn {
  flex-shrink: 0;
  padding: 0 8px;
}

.active-filter-bar {
  padding: 8px 16px;
  background: #fff;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  border-bottom: 1px solid #eee;
}

.filter-label {
  font-size: 12px;
  color: #666;
}

.filter-tag {
  margin-right: 4px;
}

.filter-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.filter-panel :deep(.tag-filter) {
  flex: 1;
  overflow-y: auto;
}

.manage-bar {
  padding: 10px 16px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #eee;
}

.selected-info {
  font-size: 14px;
  color: #333;
}

.manage-actions {
  display: flex;
  gap: 8px;
}

.comic-select-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 8px;
}

.comic-select-item {
  position: relative;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid transparent;
  transition: border-color 0.2s;
}

.comic-select-item.selected {
  border-color: #1989fa;
}

.comic-thumb {
  width: 100%;
  aspect-ratio: 3/4;
}

.comic-title-line {
  padding: 4px 6px;
  font-size: 12px;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.select-check {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  background: #1989fa;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 12px;
}
</style>
