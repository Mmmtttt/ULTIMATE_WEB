<template>
  <div class="home">
    <van-nav-bar title="漫画库" />
    
    <!-- 搜索栏 -->
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
        @click="showFilterPanel = true"
        class="filter-btn"
      >
        筛选
        <van-icon name="filter-o" />
      </van-button>
    </div>
    
    <!-- 活跃筛选标签 -->
    <div v-if="isFiltering" class="active-filter-bar">
      <span class="filter-label">当前筛选:</span>
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

// 使用搜索组合
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

// 本地状态
const active = ref(0)
const showFilterPanel = ref(false)

// 计算属性
const isLoading = computed(() => loading.value || comicStore.loading)

// 方法
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
  // 筛选变化时自动应用
  if (includeTags.value.length > 0 || excludeTags.value.length > 0) {
    filterByTags()
  } else {
    comicStore.clearFilter()
  }
}

function applyFilterAndClose() {
  showFilterPanel.value = false
}

// 初始化
onMounted(async () => {
  await init()
  
  // 处理 URL 中的 tagId 参数
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
  gap: 10px;
}

.search-bar .van-search {
  flex: 1;
  padding: 0;
}

.filter-btn {
  flex-shrink: 0;
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
