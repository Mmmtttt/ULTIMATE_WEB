<template>
  <div class="home">
    <van-nav-bar title="漫画库" />
    
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
    
    <!-- 漫画网格 -->
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
      :style="{ height: '40%' }"
    >
      <div class="sort-panel">
        <van-nav-bar title="排序方式" left-text="关闭" @click-left="showSortPanel = false" />
        <van-cell-group>
          <van-cell 
            title="按添加时间" 
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
      <van-tabbar-item icon="user-o" to="/mine">我的</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useComicStore, useTagStore } from '@/stores'
import { useSearch } from '@/composables'
import { ComicGrid, EmptyState, TagFilter } from '@/components'

const router = useRouter()
const route = useRoute()
const comicStore = useComicStore()
const tagStore = useTagStore()

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

const isLoading = computed(() => loading.value || comicStore.loading)

const sortLabel = computed(() => {
  const labels = {
    'create_time': '按添加时间',
    'score': '按评分',
    'read_time': '按阅读时间',
    'read_status': '已读/未读'
  }
  return labels[currentSortType.value] || ''
})

function handleSearch() {
  search()
}

function goToDetail(comic) {
  router.push(`/comic/${comic.id}`)
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
})
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
</style>
