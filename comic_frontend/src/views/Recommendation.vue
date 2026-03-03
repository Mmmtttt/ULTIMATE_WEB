<template>
  <div class="recommendation">
    <van-nav-bar title="推荐漫画">
      <template #right>
        <van-dropdown-menu direction="down">
          <van-dropdown-item v-model="menuValue" :options="menuOptions" @change="handleMenuChange" />
        </van-dropdown-menu>
      </template>
    </van-nav-bar>

    <div class="search-bar">
      <van-search
        v-model="keyword"
        placeholder="搜索推荐漫画"
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
      icon="🌟"
      title="暂无推荐漫画"
      :description="isFiltering ? '没有找到匹配的推荐漫画' : '还没有添加任何推荐漫画'"
    >
      <template #action>
        <van-button v-if="isFiltering" type="primary" @click="clearAllFilters">
          清除筛选
        </van-button>
      </template>
    </EmptyState>

    <!-- 推荐漫画网格 - 管理模式 -->
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

    <!-- 推荐漫画网格 - 普通模式 -->
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
            <van-button type="primary" size="small" @click="applyFilter">确定</van-button>
          </template>
        </van-nav-bar>

        <TagFilter
          v-model:include-tags="tempIncludeTags"
          v-model:exclude-tags="tempExcludeTags"
          :tags="availableTags"
          show-count
        />
      </div>
    </van-popup>

    <!-- 排序面板 -->
    <van-popup
      v-model:show="showSortPanel"
      position="bottom"
      round
    >
      <van-picker
        :columns="sortColumns"
        @confirm="onSortConfirm"
        @cancel="showSortPanel = false"
        :default-index="currentSortIndex"
      />
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
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showConfirmDialog, showSuccessToast, showFailToast } from 'vant'
import { useRecommendationStore, useTagStore, useImportTaskStore } from '@/stores'
import { SORT_TYPE } from '@/utils'
import { recommendationApi } from '@/api'
import ComicGrid from '@/components/comic/ComicGrid.vue'
import TagFilter from '@/components/tag/TagFilter.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const router = useRouter()
const route = useRoute()
const recommendationStore = useRecommendationStore()
const tagStore = useTagStore()
const importTaskStore = useImportTaskStore()

// ============ State ============
const keyword = ref('')
const showFilterPanel = ref(false)
const showSortPanel = ref(false)
const tempIncludeTags = ref([])
const tempExcludeTags = ref([])
const selectedIncludeTags = ref([])
const selectedExcludeTags = ref([])
const active = ref(1)

// 管理模式相关
const isManageMode = ref(false)
const selectedComicIds = ref([])
const menuValue = ref(0)
const menuOptions = [
  { text: '更多操作', value: 0 },
  { text: '管理漫画', value: 1 }
]

// ============ Computed ============
const isLoading = computed(() => recommendationStore.loading)
const results = computed(() => recommendationStore.recommendationList)
const hasResults = computed(() => results.value.length > 0)
const isFiltering = computed(() => recommendationStore.isFiltering)
const currentSortType = computed(() => recommendationStore.currentSort)
const availableTags = computed(() => tagStore.tags)

const currentSortIndex = computed(() => {
  const index = sortColumns.findIndex(col => col.value === currentSortType.value)
  return index >= 0 ? index : 0
})

const sortLabel = computed(() => {
  const column = sortColumns.find(col => col.value === currentSortType.value)
  return column ? column.text : ''
})

// ============ Sort Options ============
const sortColumns = [
  { text: '最近导入', value: SORT_TYPE.CREATE_TIME },
  { text: '评分', value: SORT_TYPE.SCORE },
  { text: '阅读时间', value: SORT_TYPE.READ_TIME },
  { text: '阅读状态', value: SORT_TYPE.READ_STATUS }
]

// ============ Methods ============

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
    
    const res = await recommendationApi.batchMoveToTrash(selectedComicIds.value)
    if (res.code === 200) {
      showToast(res.msg || '已移入回收站')
      selectedComicIds.value = []
      isManageMode.value = false
      await recommendationStore.fetchRecommendations(true, currentSortType.value ? { sortType: currentSortType.value } : {})
    } else {
      showToast(res.msg || '操作失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      showToast('操作失败')
    }
  }
}

async function fetchRecommendations() {
  console.log('[Recommendation] 获取推荐列表')
  await recommendationStore.fetchRecommendations()
}

function goToDetail(comic) {
  console.log('[Recommendation] 跳转到详情页:', comic.id)
  router.push(`/recommendation/${comic.id}`)
}

async function handleAuthorClick(author) {
  console.log('[Recommendation] 点击作者:', author)
  keyword.value = author
  await recommendationStore.searchRecommendations(author)
}

async function handleSearch() {
  if (!keyword.value.trim()) {
    clearSearch()
    return
  }
  console.log('[Recommendation] 搜索:', keyword.value)
  await recommendationStore.searchRecommendations(keyword.value)
}

function clearSearch() {
  keyword.value = ''
  recommendationStore.clearFilter()
}

async function onSortConfirm({ selectedOptions }) {
  const sortType = selectedOptions[0]?.value
  console.log('[Recommendation] 排序:', sortType)
  recommendationStore.setSortType(sortType)
  showSortPanel.value = false
  await recommendationStore.fetchRecommendations(true, { sortType })
}

async function clearSort() {
  recommendationStore.clearSort()
  await recommendationStore.fetchRecommendations(true)
}

async function applyFilter() {
  console.log('[Recommendation] 应用筛选:', {
    include: tempIncludeTags.value,
    exclude: tempExcludeTags.value
  })

  const includeArray = Array.isArray(tempIncludeTags.value) ? tempIncludeTags.value : []
  const excludeArray = Array.isArray(tempExcludeTags.value) ? tempExcludeTags.value : []

  selectedIncludeTags.value = availableTags.value.filter(
    tag => includeArray.includes(tag.id)
  )
  selectedExcludeTags.value = availableTags.value.filter(
    tag => excludeArray.includes(tag.id)
  )

  await recommendationStore.filterByTags(
    includeArray,
    excludeArray
  )

  showFilterPanel.value = false
}

async function removeIncludeTag(tagId) {
  tempIncludeTags.value = tempIncludeTags.value.filter(id => id !== tagId)
  selectedIncludeTags.value = selectedIncludeTags.value.filter(tag => tag.id !== tagId)
  if (tempIncludeTags.value.length === 0 && tempExcludeTags.value.length === 0) {
    await clearAllFilters()
  } else {
    await recommendationStore.filterByTags(tempIncludeTags.value, tempExcludeTags.value)
  }
}

async function removeExcludeTag(tagId) {
  tempExcludeTags.value = tempExcludeTags.value.filter(id => id !== tagId)
  selectedExcludeTags.value = selectedExcludeTags.value.filter(tag => tag.id !== tagId)
  if (tempIncludeTags.value.length === 0 && tempExcludeTags.value.length === 0) {
    await clearAllFilters()
  } else {
    await recommendationStore.filterByTags(tempIncludeTags.value, tempExcludeTags.value)
  }
}

async function clearAllFilters() {
  keyword.value = ''
  tempIncludeTags.value = []
  tempExcludeTags.value = []
  selectedIncludeTags.value = []
  selectedExcludeTags.value = []
  recommendationStore.clearSort()
  recommendationStore.clearFilter()
  await recommendationStore.fetchRecommendations(true)
}

// ============ Lifecycle ============
onMounted(async () => {
  console.log('[Recommendation] 页面挂载')
  await tagStore.fetchTags()
  await fetchRecommendations()
  
  const importIds = route.query.importIds
  if (importIds) {
    const ids = importIds.split(',').filter(id => id.trim())
    if (ids.length > 0) {
      await createImportFromIds(ids, 'recommendation')
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

watch(currentSortType, async (newSort) => {
  if (newSort) {
    await recommendationStore.fetchRecommendations(true, { sortType: newSort })
  }
})
</script>

<style scoped>
.recommendation {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 50px;
}

.search-bar {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  background: #fff;
  gap: 8px;
}

.search-bar .van-search {
  flex: 1;
  padding: 0;
}

.sort-btn,
.filter-btn {
  flex-shrink: 0;
}

.active-filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 12px;
  background: #fff;
  border-bottom: 1px solid #eee;
}

.filter-tag {
  margin-right: 0;
}

.filter-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.van-loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
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
