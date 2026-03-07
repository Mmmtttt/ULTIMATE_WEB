<template>
  <div class="search-page">
    <div class="search-header">
      <div class="search-input-wrapper">
        <van-icon name="arrow-left" class="back-icon" @click="$router.back()" />
        <van-search 
          v-model="keyword" 
          :placeholder="searchPlaceholder" 
          shape="round"
          autofocus
          @search="handleSearch"
        />
      </div>
      
      <van-tabs v-model:active="activeTab" @change="handleSearch">
        <van-tab title="本地库" name="local" />
        <van-tab title="预览库" name="preview" />
        <van-tab title="全网搜" name="remote" />
      </van-tabs>
    </div>

    <div class="search-content">
      <van-loading v-if="loading" class="loading-center" />
      
      <EmptyState 
        v-else-if="results.length === 0 && !loading" 
        title="未找到结果" 
        :description="emptyDescription"
      />

      <div v-else class="results-container">
        <template v-if="activeTab === 'remote'">
          <div class="remote-results-grid" :class="{ 'video-mode': isVideoMode }">
            <div
              v-for="item in normalizedResults"
              :key="getItemId(item)"
              class="remote-result-card"
              :class="{ selected: isSelected(item) }"
              @click="toggleSelection(item)"
            >
              <div class="card-cover">
                <van-image 
                  :src="getCoverUrl(item)" 
                  fit="cover" 
                  class="cover-image"
                  lazy-load
                />
                <div v-if="item.platform" class="platform-badge">{{ item.platform }}</div>
                <div v-if="item.score" class="card-score">{{ item.score }}</div>
                <div v-if="isSelected(item)" class="select-overlay">
                  <van-icon name="success" class="select-icon" />
                </div>
              </div>
              <div class="card-info">
                <div class="card-title">{{ item.title }}</div>
                <div v-if="item.author" class="card-author">{{ item.author }}</div>
              </div>
            </div>
          </div>
          
          <div class="floating-import-bar" v-if="selectedIds.length > 0">
            <span class="floating-selection-info">已选 {{ selectedIds.length }} 项</span>
            <van-button type="primary" @click="handleImport">导入选中</van-button>
          </div>
        </template>
        
        <template v-else>
          <MediaGrid 
            :items="normalizedResults" 
            :show-favorite="activeTab !== 'local'"
            :is-favorited="isFavorited"
            :show-progress="!isVideoMode"
            @click="onItemClick"
            @toggle-favorite="toggleFavorite"
          />
        </template>
        
        <div v-if="hasMore && activeTab === 'remote'" class="load-more">
          <div v-if="paginationInfo" class="pagination-info">
            <template v-if="isVideoMode">
              <span class="platform-info">平台: {{ paginationInfo.platform.toUpperCase() }}</span>
              <span class="page-info">第 {{ paginationInfo.page }} 页</span>
              <span v-if="paginationInfo.total_pages" class="total-pages">/ {{ paginationInfo.total_pages }} 页</span>
            </template>
            <template v-else>
              <div v-for="(info, plat) in paginationInfo" :key="plat" class="platform-item">
                <span class="platform-info">平台: {{ plat }}</span>
                <span class="page-info">第 {{ info.page }} 页</span>
                <span v-if="info.total_pages" class="total-pages">/ {{ info.total_pages }} 页</span>
              </div>
            </template>
          </div>
          <van-button block plain :loading="loadingMore" @click="loadMore">
            加载更多
          </van-button>
        </div>
      </div>
    </div>

    <!-- Import Options -->
    <van-action-sheet v-model:show="showImportSheet" title="导入位置">
      <div class="sheet-content">
        <van-button block type="primary" @click="confirmImport('home')">导入到主页</van-button>
        <van-button block type="success" @click="confirmImport('recommendation')">导入到推荐页</van-button>
      </div>
    </van-action-sheet>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useModeStore, useComicStore, useVideoStore, useRecommendationStore, useVideoRecommendationStore, useListStore, useImportTaskStore } from '@/stores'
import { videoApi } from '@/api'
import MediaGrid from '@/components/common/MediaGrid.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { showToast } from 'vant'

const router = useRouter()
const route = useRoute()
const modeStore = useModeStore()
const comicStore = useComicStore()
const videoStore = useVideoStore()
const comicRecStore = useRecommendationStore()
const videoRecStore = useVideoRecommendationStore()
const listStore = useListStore()
const importTaskStore = useImportTaskStore()

const keyword = ref('')
const activeTab = ref('local')
const loading = ref(false)
const loadingMore = ref(false)
const results = ref([])
const hasMore = ref(false)
const currentPage = ref(0) // offset for some APIs
const selectedIds = ref([])
const showImportSheet = ref(false)
const paginationInfo = ref(null) // 分页信息：{ platform, page, total_pages, has_next }

const isVideoMode = computed(() => modeStore.isVideoMode)

const searchPlaceholder = computed(() => 
  isVideoMode.value ? '搜索视频...' : '搜索漫画...'
)

const emptyDescription = computed(() => {
  if (!keyword.value) return '请输入关键词开始搜索'
  return '尝试切换其他来源看看？'
})

const normalizedResults = computed(() => {
  return results.value.map(item => {
    // Normalize data structure for MediaGrid
    const normalized = { ...item }
    
    // Handle video data
    if (normalized.cover_url && !normalized.cover_path) {
      normalized.cover_path = normalized.cover_url
    }
    
    // Handle comic data
    if (normalized.cover_url && !normalized.cover_path) {
      normalized.cover_path = normalized.cover_url
    }
    
    // Ensure id exists
    if (!normalized.id) {
      normalized.id = normalized.video_id || normalized.album_id || normalized.comic_id
    }
    
    // Add platform information
    if (activeTab.value === 'remote') {
      if (isVideoMode.value) {
        normalized.platform = 'JAVDB'
      } else {
        normalized.platform = normalized.platform || 'JM'
      }
    }
    
    return normalized
  })
})

function getItemId(item) {
  return item.id || item.video_id || item.album_id || item.comic_id
}

function getCoverUrl(item) {
  const coverPath = item.cover_path || item.cover_url
  if (!coverPath) return ''
  if (coverPath.startsWith('http')) return coverPath
  if (coverPath.startsWith('/static/')) return coverPath
  if (coverPath.startsWith('/')) return coverPath
  return `/${coverPath}`
}

function isSelected(item) {
  const id = getItemId(item)
  return selectedIds.value.includes(id)
}

function toggleSelection(item) {
  const id = getItemId(item)
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter(i => i !== id)
  } else {
    selectedIds.value.push(id)
  }
}

function handleImport() {
  showImportSheet.value = true
}

async function confirmImport(target) {
  showImportSheet.value = false
  const selectedItems = normalizedResults.value.filter(item => 
    selectedIds.value.includes(getItemId(item))
  )
  
  try {
    if (isVideoMode.value) {
      let successCount = 0
      for (const item of selectedItems) {
        await videoApi.thirdPartyImport(getItemId(item), target)
        successCount++
      }
      showToast(`已导入 ${successCount} 个视频`)
    } else {
      const itemsByPlatform = {}
      selectedItems.forEach(item => {
        const platform = item.platform || 'JM'
        if (!itemsByPlatform[platform]) {
          itemsByPlatform[platform] = []
        }
        itemsByPlatform[platform].push(getItemId(item))
      })
      
      for (const [platform, comicIds] of Object.entries(itemsByPlatform)) {
        const params = {
          import_type: 'by_list',
          target: target,
          platform: platform,
          comic_ids: comicIds
        }
        await importTaskStore.createImportTask(params)
      }
      showToast('已创建导入任务')
    }
    selectedIds.value = []
  } catch (e) {
    showToast('导入失败')
  }
}

async function handleSearch() {
  if (!keyword.value.trim()) return
  
  loading.value = true
  results.value = []
  currentPage.value = 0
  hasMore.value = false
  selectedIds.value = []
  paginationInfo.value = null
  
  try {
    if (activeTab.value === 'local') {
      await searchLocal()
    } else if (activeTab.value === 'preview') {
      await searchPreview()
    } else {
      await searchRemote()
    }
  } catch (e) {
    showToast('搜索失败')
  } finally {
    loading.value = false
  }
}

async function searchLocal() {
  if (isVideoMode.value) {
    const res = await videoStore.search(keyword.value)
    results.value = res || []
  } else {
    // comicStore.searchComics modifies store state, doesn't return
    await comicStore.searchComics(keyword.value)
    results.value = comicStore.comicList
  }
}

async function searchPreview() {
  if (isVideoMode.value) {
    await videoRecStore.searchRecommendations(keyword.value)
    results.value = videoRecStore.recommendations
  } else {
    await comicRecStore.searchRecommendations(keyword.value)
    results.value = comicRecStore.recommendations
  }
}

async function searchRemote() {
  if (isVideoMode.value) {
    const res = await videoApi.thirdPartySearch(keyword.value, 1)
    if (res.code === 200 && res.data) {
      results.value = res.data.videos || []
      paginationInfo.value = {
        platform: res.data.platform,
        page: res.data.page,
        total_pages: res.data.total_pages,
        has_next: res.data.has_next
      }
      hasMore.value = res.data.has_next
    } else {
      results.value = []
      paginationInfo.value = null
      hasMore.value = false
    }
  } else {
    const res = await comicStore.thirdPartySearch(keyword.value, 'all', 1, 40)
    if (res.results) {
      results.value = res.results
      currentPage.value = res.page
      hasMore.value = res.has_more
      paginationInfo.value = res.platform_info || {}
    }
  }
}

async function loadMore() {
  if (!hasMore.value) return
  loadingMore.value = true
  
  try {
    if (isVideoMode.value) {
      const nextPage = paginationInfo.value ? paginationInfo.value.page + 1 : 2
      const res = await videoApi.thirdPartySearch(keyword.value, nextPage)
      if (res.code === 200 && res.data) {
        results.value = [...results.value, ...(res.data.videos || [])]
        paginationInfo.value = {
          platform: res.data.platform,
          page: res.data.page,
          total_pages: res.data.total_pages,
          has_next: res.data.has_next
        }
        hasMore.value = res.data.has_next
      }
    } else {
      const nextPage = currentPage.value + 1
      const res = await comicStore.thirdPartySearch(keyword.value, 'all', nextPage, 40)
      if (res.results) {
        results.value = [...results.value, ...res.results]
        currentPage.value = res.page
        hasMore.value = res.has_more
        paginationInfo.value = res.platform_info || {}
      }
    }
  } finally {
    loadingMore.value = false
  }
}

function onItemClick(item) {
  // Navigation logic
  if (activeTab.value === 'local') {
    const routeName = isVideoMode.value ? 'VideoDetail' : 'ComicDetail'
    router.push({ name: routeName, params: { id: item.id } })
  } else if (activeTab.value === 'preview') {
    const routeName = isVideoMode.value ? 'VideoRecommendationDetail' : 'RecommendationDetail'
    router.push({ name: routeName, params: { id: item.id } })
  } else {
    // Remote item click - maybe show import dialog or detail
    // For now, assume import logic
    // Or navigate to a temp detail page
    showToast('第三方内容需先导入')
  }
}

function isFavorited(item) {
  return listStore.isFavoritedVideo(item)
}

function toggleFavorite(item) {
  // Logic
}

onMounted(() => {
  if (route.query.keyword) {
    keyword.value = route.query.keyword
    handleSearch()
  }
  if (route.query.source === 'preview') {
    activeTab.value = 'preview'
  }
})
</script>

<style scoped>
.search-page {
  min-height: 100vh;
  background: #f5f5f5;
  display: flex;
  flex-direction: column;
}

.search-header {
  background: #fff;
  padding-top: 10px;
  position: sticky;
  top: 0;
  z-index: 10;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}

.search-input-wrapper {
  display: flex;
  align-items: center;
  padding: 0 10px;
}

.back-icon {
  font-size: 20px;
  padding: 10px;
  color: #333;
}

.search-input-wrapper .van-search {
  flex: 1;
  padding: 0;
}

.search-content {
  flex: 1;
  overflow-y: auto;
}

.loading-center {
  padding: 40px;
  text-align: center;
}

.load-more {
  padding: 20px;
}

.pagination-info {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 8px 16px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  flex-wrap: wrap;
}

.platform-item {
  display: flex;
  gap: 8px;
  padding: 4px 8px;
  background: #f5f5f5;
  border-radius: 4px;
}

.platform-info,
.page-info,
.total-pages {
  font-size: 14px;
  color: #666;
}

.platform-info {
  font-weight: 600;
  color: #1989fa;
}

.page-info {
  font-weight: 500;
  color: #333;
}

.floating-import-bar {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
  background: #fff;
  padding: 12px 20px;
  border-radius: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
  max-width: 90%;
  width: auto;
}

.floating-selection-info {
  font-size: 14px;
  color: #333;
  white-space: nowrap;
}

.remote-results-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  padding: 12px;
}

.remote-result-card {
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  cursor: pointer;
  transition: transform 0.2s;
  position: relative;
}

.remote-result-card:hover {
  transform: translateY(-2px);
}

.remote-result-card.selected {
  box-shadow: 0 0 0 2px #1989fa;
}

.card-cover {
  position: relative;
  aspect-ratio: 2/3;
  background: #f0f2f5;
}

.remote-results-grid.video-mode .card-cover {
  aspect-ratio: 16/9;
}

.cover-image {
  width: 100%;
  height: 100%;
}

.platform-badge {
  position: absolute;
  top: 6px;
  left: 6px;
  background: rgba(0,0,0,0.7);
  color: #fff;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
}

.card-score {
  position: absolute;
  top: 6px;
  right: 6px;
  background: #ff9500;
  color: #fff;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
}

.select-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(25, 137, 250, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
}

.select-icon {
  font-size: 32px;
  color: #fff;
  background: #1989fa;
  border-radius: 50%;
  padding: 8px;
}

.card-info {
  padding: 10px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: 1.4;
}

.card-author {
  font-size: 12px;
  color: #666;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sheet-content {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

@media (min-width: 768px) {
  .remote-results-grid {
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    padding: 20px;
  }
}
</style>
