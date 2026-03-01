<template>
  <div class="recommendation">
    <van-nav-bar title="推荐漫画" />

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

    <!-- 推荐漫画网格 -->
    <ComicGrid
      v-else
      :comics="results"
      @card-click="goToDetail"
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

        <div class="filter-content">
          <div class="filter-section">
            <h3>包含标签</h3>
            <TagFilter
              :tags="availableTags"
              :selected-ids="tempIncludeTags"
              @change="tempIncludeTags = $event"
            />
          </div>

          <div class="filter-section">
            <h3>排除标签</h3>
            <TagFilter
              :tags="availableTags"
              :selected-ids="tempExcludeTags"
              @change="tempExcludeTags = $event"
            />
          </div>
        </div>
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
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useRecommendationStore, useTagStore } from '@/stores'
import { SORT_TYPE } from '@/utils'
import ComicGrid from '@/components/comic/ComicGrid.vue'
import TagFilter from '@/components/tag/TagFilter.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const router = useRouter()
const recommendationStore = useRecommendationStore()
const tagStore = useTagStore()

// ============ State ============
const keyword = ref('')
const showFilterPanel = ref(false)
const showSortPanel = ref(false)
const tempIncludeTags = ref([])
const tempExcludeTags = ref([])
const selectedIncludeTags = ref([])
const selectedExcludeTags = ref([])
const active = ref(1) // 底部导航当前选中项，推荐页是第2个（索引1）

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
  { text: '添加时间', value: SORT_TYPE.CREATE_TIME },
  { text: '评分', value: SORT_TYPE.SCORE },
  { text: '阅读时间', value: SORT_TYPE.READ_TIME },
  { text: '阅读状态', value: SORT_TYPE.READ_STATUS }
]

// ============ Methods ============

/**
 * 获取推荐漫画列表
 */
async function fetchRecommendations() {
  console.log('[Recommendation] 获取推荐列表')
  await recommendationStore.fetchRecommendations()
}

/**
 * 跳转到详情页
 */
function goToDetail(comic) {
  console.log('[Recommendation] 跳转到详情页:', comic.id)
  router.push(`/recommendation/${comic.id}`)
}

/**
 * 搜索
 */
async function handleSearch() {
  if (!keyword.value.trim()) {
    clearSearch()
    return
  }
  console.log('[Recommendation] 搜索:', keyword.value)
  await recommendationStore.searchRecommendations(keyword.value)
}

/**
 * 清除搜索
 */
function clearSearch() {
  keyword.value = ''
  recommendationStore.clearFilter()
}

/**
 * 排序确认
 */
async function onSortConfirm({ selectedOptions }) {
  const sortType = selectedOptions[0]?.value
  console.log('[Recommendation] 排序:', sortType)
  recommendationStore.setSortType(sortType)
  showSortPanel.value = false
  await recommendationStore.fetchRecommendations(true, { sortType })
}

/**
 * 清除排序
 */
async function clearSort() {
  recommendationStore.clearSort()
  await recommendationStore.fetchRecommendations(true)
}

/**
 * 应用筛选
 */
async function applyFilter() {
  console.log('[Recommendation] 应用筛选:', {
    include: tempIncludeTags.value,
    exclude: tempExcludeTags.value
  })

  selectedIncludeTags.value = availableTags.value.filter(
    tag => tempIncludeTags.value.includes(tag.id)
  )
  selectedExcludeTags.value = availableTags.value.filter(
    tag => tempExcludeTags.value.includes(tag.id)
  )

  await recommendationStore.filterByTags(
    tempIncludeTags.value,
    tempExcludeTags.value
  )

  showFilterPanel.value = false
}

/**
 * 移除包含标签
 */
async function removeIncludeTag(tagId) {
  tempIncludeTags.value = tempIncludeTags.value.filter(id => id !== tagId)
  selectedIncludeTags.value = selectedIncludeTags.value.filter(tag => tag.id !== tagId)
  await applyFilter()
}

/**
 * 移除排除标签
 */
async function removeExcludeTag(tagId) {
  tempExcludeTags.value = tempExcludeTags.value.filter(id => id !== tagId)
  selectedExcludeTags.value = selectedExcludeTags.value.filter(tag => tag.id !== tagId)
  await applyFilter()
}

/**
 * 清除所有筛选
 */
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
  // 获取标签列表
  await tagStore.fetchTags()
  // 获取推荐漫画列表
  await fetchRecommendations()
})

// 监听排序变化
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
  padding-bottom: 50px; /* 为底部导航栏留出空间 */
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

.filter-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.filter-section {
  margin-bottom: 24px;
}

.filter-section h3 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #666;
}

.van-loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
</style>
