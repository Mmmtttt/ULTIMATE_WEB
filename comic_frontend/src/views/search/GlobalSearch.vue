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
        <!-- Remote search often returns different structure, might need adaptation -->
        <MediaGrid 
          :items="normalizedResults" 
          :show-favorite="activeTab !== 'local'"
          :is-favorited="isFavorited"
          @click="onItemClick"
          @toggle-favorite="toggleFavorite"
        />
        
        <div v-if="hasMore && activeTab === 'remote'" class="load-more">
          <van-button block plain :loading="loadingMore" @click="loadMore">
            加载更多
          </van-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useModeStore, useComicStore, useVideoStore, useRecommendationStore, useVideoRecommendationStore, useListStore } from '@/stores'
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

const keyword = ref('')
const activeTab = ref('local')
const loading = ref(false)
const loadingMore = ref(false)
const results = ref([])
const hasMore = ref(false)
const currentPage = ref(0) // offset for some APIs

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
    
    return normalized
  })
})

async function handleSearch() {
  if (!keyword.value.trim()) return
  
  loading.value = true
  results.value = []
  currentPage.value = 0
  hasMore.value = false
  
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
    const res = await videoApi.thirdPartySearch(keyword.value)
    results.value = res.code === 200 ? res.data : (res || [])
    // Pagination handling for video remote search is complex, simplifying
  } else {
    const res = await comicStore.thirdPartySearch(keyword.value, 'all', 0)
    if (res.results) {
      results.value = res.results
      currentPage.value = res.offset + res.limit
      hasMore.value = res.has_more
    }
  }
}

async function loadMore() {
  if (!hasMore.value) return
  loadingMore.value = true
  
  try {
    if (isVideoMode.value) {
      // Implement pagination if API supports
    } else {
      const res = await comicStore.thirdPartySearch(keyword.value, 'all', currentPage.value)
      if (res.results) {
        results.value = [...results.value, ...res.results]
        currentPage.value = res.offset + res.limit
        hasMore.value = res.has_more
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
</style>
