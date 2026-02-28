<template>
  <div class="home">
    <van-nav-bar title="漫画库" />
    
    <div class="search-bar">
      <van-search
        v-model="searchQuery"
        placeholder="搜索漫画ID、名称、作者、标签"
        @search="handleSearch"
        @clear="handleClearSearch"
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
    
    <div v-if="hasActiveFilter" class="active-filter-bar">
      <span class="filter-label">当前筛选:</span>
      <van-tag 
        v-for="tag in includeTags" 
        :key="tag.id" 
        type="primary" 
        closeable 
        @close="removeIncludeTag(tag.id)"
        class="filter-tag"
      >
        包含: {{ tag.name }}
      </van-tag>
      <van-tag 
        v-for="tag in excludeTags" 
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
    
    <van-loading v-if="isLoading" type="spinner" color="#1989fa" />
    
    <div v-else-if="displayList.length === 0" class="empty">
      <van-empty description="暂无匹配漫画" />
      <van-button type="primary" @click="handleClearSearch">清空搜索</van-button>
    </div>
    
    <div v-else class="comic-grid">
      <div 
        v-for="comic in displayList" 
        :key="comic.id" 
        class="comic-card" 
        @click="goToDetail(comic.id)"
        @mouseenter="showTooltip(comic, $event)"
        @mouseleave="hideTooltip"
      >
        <div class="comic-cover-container">
          <van-image 
            :src="getCoverUrl(comic.cover_path)" 
            fit="cover" 
            class="comic-cover"
            lazy-load
          />
          <div class="comic-badge" v-if="comic.current_page > 1">
            {{ Math.round((comic.current_page / comic.total_page) * 100) }}%
          </div>
          <div class="score-badge" v-if="comic.score">
            {{ comic.score }}分
          </div>
        </div>
        <div class="comic-info">
          <h3 class="comic-title">{{ comic.title }}</h3>
          <div class="comic-tags" v-if="comic.tags && comic.tags.length > 0">
            <van-tag 
              v-for="(tag, index) in comic.tags.slice(0, 2)" 
              :key="tag.id" 
              size="mini" 
              type="primary" 
              plain
              class="comic-tag"
            >
              {{ tag.name }}
            </van-tag>
            <span v-if="comic.tags.length > 2" class="more-tags">+{{ comic.tags.length - 2 }}</span>
          </div>
          <div class="comic-meta">
            <span class="page-info">{{ comic.current_page }}/{{ comic.total_page }}</span>
            <span class="author">{{ comic.author || '未知' }}</span>
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="tooltipVisible" class="tags-tooltip" :style="tooltipStyle">
      <div class="tooltip-content">
        <h4>{{ tooltipComic.title }}</h4>
        <div class="tooltip-score" v-if="tooltipComic.score">
          评分: {{ tooltipComic.score }}分
        </div>
        <div class="tooltip-tags">
          <van-tag 
            v-for="tag in tooltipTags" 
            :key="tag.id" 
            size="small" 
            type="primary"
            class="tooltip-tag"
          >
            {{ tag.name }}
          </van-tag>
          <span v-if="tooltipTags.length === 0" class="no-tags">暂无标签</span>
        </div>
      </div>
    </div>
    
    <van-popup 
      v-model:show="showFilterPanel" 
      position="bottom" 
      round 
      :style="{ height: '70%' }"
    >
      <div class="filter-panel">
        <van-nav-bar title="高级筛选" left-text="重置" @click-left="resetFilters">
          <template #right>
            <van-button type="primary" size="small" @click="applyFilters">确定</van-button>
          </template>
        </van-nav-bar>
        
        <div class="filter-section">
          <h4 class="section-title">包含标签（同时包含所有选中标签）</h4>
          <div class="tag-grid">
            <van-tag 
              v-for="tag in allTags" 
              :key="tag.id" 
              :type="tempIncludeIds.includes(tag.id) ? 'primary' : 'default'"
              size="large"
              class="filter-tag-item"
              @click="toggleIncludeTag(tag.id)"
            >
              {{ tag.name }} ({{ tag.comic_count || 0 }})
            </van-tag>
          </div>
        </div>
        
        <div class="filter-section">
          <h4 class="section-title">排除标签（不包含任意选中标签）</h4>
          <div class="tag-grid">
            <van-tag 
              v-for="tag in allTags" 
              :key="tag.id" 
              :type="tempExcludeIds.includes(tag.id) ? 'danger' : 'default'"
              size="large"
              class="filter-tag-item"
              @click="toggleExcludeTag(tag.id)"
            >
              {{ tag.name }} ({{ tag.comic_count || 0 }})
            </van-tag>
          </div>
        </div>
      </div>
    </van-popup>
    
    <van-tabbar v-model="active" route>
      <van-tabbar-item icon="home-o" to="/">主页</van-tabbar-item>
      <van-tabbar-item icon="user-o" to="/mine">我的</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useComicStore } from '../store/modules/comic'
import { comicApi, tagApi } from '../api/comic'
import apiConfig from '../config/api'

const router = useRouter()
const route = useRoute()
const comicStore = useComicStore()
const active = ref(0)
const searchQuery = ref('')
const isLoading = ref(false)

const showFilterPanel = ref(false)
const allTags = ref([])
const includeTagIds = ref([])
const excludeTagIds = ref([])
const tempIncludeIds = ref([])
const tempExcludeIds = ref([])

const searchResults = ref([])
const isSearchMode = ref(false)
const filteredResults = ref([])

const includeTags = computed(() => {
  return allTags.value.filter(t => includeTagIds.value.includes(t.id))
})

const excludeTags = computed(() => {
  return allTags.value.filter(t => excludeTagIds.value.includes(t.id))
})

const hasActiveFilter = computed(() => {
  return includeTagIds.value.length > 0 || excludeTagIds.value.length > 0
})

const displayList = computed(() => {
  if (isSearchMode.value) {
    return searchResults.value
  }
  if (hasActiveFilter.value) {
    return filteredResults.value
  }
  return comicStore.comicList
})

const getCoverUrl = (coverPath) => {
  return apiConfig.getCoverUrl(coverPath)
}

const goToDetail = (id) => {
  router.push(`/comic/${id}`)
}

const handleSearch = async () => {
  const keyword = searchQuery.value.trim()
  if (!keyword) {
    isSearchMode.value = false
    searchResults.value = []
    return
  }
  
  isLoading.value = true
  isSearchMode.value = true
  
  try {
    console.log('搜索关键词:', keyword)
    const response = await comicApi.search(keyword)
    console.log('搜索响应:', response)
    if (response.code === 200) {
      searchResults.value = response.data
      console.log('搜索结果数量:', response.data.length)
    }
  } catch (error) {
    console.error('搜索失败:', error)
  } finally {
    isLoading.value = false
  }
}

const handleClearSearch = async () => {
  searchQuery.value = ''
  isSearchMode.value = false
  searchResults.value = []
  
  if (hasActiveFilter.value) {
    await applyFilters()
  } else {
    await comicStore.fetchComics()
  }
}

const toggleIncludeTag = (tagId) => {
  const index = tempIncludeIds.value.indexOf(tagId)
  if (index > -1) {
    tempIncludeIds.value.splice(index, 1)
  } else {
    tempIncludeIds.value.push(tagId)
  }
  const excludeIndex = tempExcludeIds.value.indexOf(tagId)
  if (excludeIndex > -1) {
    tempExcludeIds.value.splice(excludeIndex, 1)
  }
}

const toggleExcludeTag = (tagId) => {
  const index = tempExcludeIds.value.indexOf(tagId)
  if (index > -1) {
    tempExcludeIds.value.splice(index, 1)
  } else {
    tempExcludeIds.value.push(tagId)
  }
  const includeIndex = tempIncludeIds.value.indexOf(tagId)
  if (includeIndex > -1) {
    tempIncludeIds.value.splice(includeIndex, 1)
  }
}

const applyFilters = async () => {
  console.log('[Home] applyFilters called')
  includeTagIds.value = [...tempIncludeIds.value]
  excludeTagIds.value = [...tempExcludeIds.value]
  showFilterPanel.value = false
  
  if (includeTagIds.value.length === 0 && excludeTagIds.value.length === 0) {
    console.log('[Home] No filters, fetching comics')
    filteredResults.value = []
    await comicStore.fetchComics()
    return
  }
  
  isLoading.value = true
  try {
    const response = await comicApi.filter(includeTagIds.value, excludeTagIds.value)
    if (response.code === 200) {
      filteredResults.value = response.data
    }
  } catch (error) {
    console.error('筛选失败:', error)
  } finally {
    isLoading.value = false
  }
}

const resetFilters = () => {
  tempIncludeIds.value = []
  tempExcludeIds.value = []
}

const removeIncludeTag = async (tagId) => {
  includeTagIds.value = includeTagIds.value.filter(id => id !== tagId)
  tempIncludeIds.value = [...includeTagIds.value]
  await applyFilters()
}

const removeExcludeTag = async (tagId) => {
  excludeTagIds.value = excludeTagIds.value.filter(id => id !== tagId)
  tempExcludeIds.value = [...excludeTagIds.value]
  await applyFilters()
}

const clearAllFilters = async () => {
  includeTagIds.value = []
  excludeTagIds.value = []
  tempIncludeIds.value = []
  tempExcludeIds.value = []
  await comicStore.fetchComics()
}

const tooltipVisible = ref(false)
const tooltipComic = ref({})
const tooltipTags = ref([])
const tooltipStyle = ref({})

const showTooltip = (comic, event) => {
  tooltipComic.value = comic
  tooltipTags.value = comic.tags || []
  
  const rect = event.target.getBoundingClientRect()
  tooltipStyle.value = {
    left: `${rect.left + rect.width / 2}px`,
    top: `${rect.top - 10}px`,
    transform: 'translate(-50%, -100%)'
  }
  
  tooltipVisible.value = true
}

const hideTooltip = () => {
  tooltipVisible.value = false
}

const fetchAllTags = async () => {
  try {
    const tags = await comicStore.fetchTags()
    if (tags) {
      allTags.value = tags
    }
  } catch (error) {
    console.error('获取标签列表失败:', error)
  }
}

watch(() => route.query.tagId, async (tagId) => {
  console.log('[Home] watch tagId:', tagId, 'current filter:', includeTagIds.value)
  if (tagId) {
    includeTagIds.value = [tagId]
    tempIncludeIds.value = [tagId]
    await applyFilters()
  } else if (includeTagIds.value.length > 0) {
    // 清除筛选状态
    includeTagIds.value = []
    tempIncludeIds.value = []
    await applyFilters()
  }
}, { immediate: true })

// 监听路由变化，处理返回等情况
watch(() => route.path, async (newPath, oldPath) => {
  console.log('[Home] route changed:', oldPath, '->', newPath)
  if (newPath === '/' && oldPath !== '/') {
    // 从其他页面返回主页
    console.log('[Home] Returned to home, query:', route.query)
    
    // 如果没有 tagId 参数，清除筛选状态
    if (!route.query.tagId) {
      includeTagIds.value = []
      tempIncludeIds.value = []
      excludeTagIds.value = []
      tempExcludeIds.value = []
      filteredResults.value = []
    }
    
    // 只有在没有筛选条件时才获取列表
    if (includeTagIds.value.length === 0 && !isSearchMode.value) {
      await comicStore.fetchComics()
    }
    await fetchAllTags()
  }
}, { immediate: true })
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

.comic-grid {
  padding: 10px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}

.comic-card {
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
  cursor: pointer;
}

.comic-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.comic-cover-container {
  position: relative;
  width: 100%;
  padding-top: 140%;
  overflow: hidden;
}

.comic-cover {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: #f0f0f0;
}

.comic-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
}

.score-badge {
  position: absolute;
  bottom: 8px;
  left: 8px;
  background: rgba(255, 153, 0, 0.9);
  color: #fff;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
  font-weight: bold;
}

.comic-info {
  padding: 8px;
}

.comic-title {
  font-size: 12px;
  font-weight: 500;
  margin: 0 0 4px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: 1.3;
}

.comic-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 4px;
}

.comic-tag {
  font-size: 10px;
}

.more-tags {
  font-size: 10px;
  color: #999;
}

.comic-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10px;
  color: #999;
}

.page-info {
  flex: 1;
}

.author {
  flex: 1;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty {
  padding: 40px 0;
  text-align: center;
}

.empty .van-button {
  margin-top: 20px;
}

.tags-tooltip {
  position: fixed;
  z-index: 9999;
  pointer-events: none;
}

.tooltip-content {
  background: rgba(0, 0, 0, 0.9);
  color: #fff;
  padding: 12px 16px;
  border-radius: 8px;
  max-width: 250px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.tooltip-content h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tooltip-score {
  font-size: 12px;
  color: #ff9900;
  margin-bottom: 6px;
}

.tooltip-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tooltip-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 12px;
}

.no-tags {
  font-size: 11px;
  color: #999;
  font-style: italic;
}

.tags-tooltip::after {
  content: '';
  position: absolute;
  bottom: -8px;
  left: 50%;
  transform: translateX(-50%);
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
  border-top: 8px solid rgba(0, 0, 0, 0.9);
}

.filter-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.filter-section {
  padding: 16px;
  border-bottom: 1px solid #eee;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 12px 0;
  color: #333;
}

.tag-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-tag-item {
  cursor: pointer;
  transition: all 0.2s;
}

.filter-tag-item:hover {
  opacity: 0.8;
}
</style>
