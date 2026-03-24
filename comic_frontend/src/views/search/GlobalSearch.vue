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

      <div v-if="isVideoMode && activeTab === 'remote'" class="tag-search-entry">
        <van-button size="small" plain type="primary" icon="filter-o" @click="goToVideoTagSearch">
          标签搜索
        </van-button>
      </div>
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
          <div v-if="normalizedResults.length > 0" class="remote-select-bar">
            <span class="selected-count">已选 {{ selectedIds.length }} 项</span>
            <van-button size="small" plain type="primary" @click="toggleSelectAllRemote">
              {{ isAllRemoteSelected ? '取消全选' : '全选' }}
            </van-button>
          </div>

          <div class="remote-results-grid" :class="{ 'video-mode': isVideoMode }">
            <div
              v-for="item in normalizedResults"
              :key="getItemId(item)"
              class="remote-result-card"
              :class="{ selected: isSelected(item) }"
              @click="toggleSelection(item)"
            >
              <div
                class="card-cover"
                :class="{
                  'video-cover-landscape': isVideoMode && !isJavbusPlatform(item),
                  'video-cover-portrait': isVideoMode && isJavbusPlatform(item)
                }"
              >
                <van-image 
                  :src="getCoverUrl(item)" 
                  :fit="getCoverFit(item)"
                  class="cover-image"
                  lazy-load
                />
                <div v-if="item.platform" class="platform-badge">{{ item.platform }}</div>
                <div v-if="item.score" class="card-score score-badge">{{ formatScore(item.score) }}</div>
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
            :show-favorite="true"
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
import { showConfirmDialog, showToast } from 'vant'
import { getCoverUrl, isAllSelected, toggleSelectAll } from '@/utils'

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
    const normalized = { ...item }
    
    if (normalized.cover_url && !normalized.cover_path) {
      normalized.cover_path = normalized.cover_url
    }
    
    if (!normalized.id) {
      normalized.id = normalized.video_id || normalized.album_id || normalized.comic_id
    }
    
    if (activeTab.value === 'remote') {
      if (isVideoMode.value) {
        normalized.platform = normalized.platform || 'JAVDB'
      } else {
        normalized.platform = normalized.platform || 'JM'
      }
    }
    
    return normalized
  })
})

const isAllRemoteSelected = computed(() => {
  return isAllSelected(selectedIds.value, normalizedResults.value, (item) => getItemId(item))
})

function getItemId(item) {
  return item.id || item.video_id || item.album_id || item.comic_id
}

function isJavbusPlatform(item) {
  const platform = String(item?.platform || '').trim().toLowerCase()
  return platform === 'javbus'
}

function getCoverFit(item) {
  if (isVideoMode.value && isJavbusPlatform(item)) {
    return 'contain'
  }
  return 'cover'
}

function formatScore(score) {
  const value = Number(score)
  if (!Number.isFinite(value)) {
    return score
  }
  return value % 1 === 0 ? value.toFixed(0) : value.toFixed(1)
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

function toggleSelectAllRemote() {
  toggleSelectAll(selectedIds, normalizedResults.value, (item) => getItemId(item))
}

async function goToVideoTagSearch() {
  try {
    const res = await videoApi.thirdPartyJavdbCookieStatus()
    const configured = Boolean(res?.code === 200 && res?.data?.configured)
    if (configured) {
      router.push('/video-tag-search')
      return
    }

    await showConfirmDialog({
      title: '提示',
      message: '未配置cookie，请先在系统配置中填写JAVDB cookie',
      showCancelButton: false,
      confirmButtonText: '知道了'
    })
  } catch (e) {
    await showConfirmDialog({
      title: '提示',
      message: e?.message || '未配置cookie，请先在系统配置中填写JAVDB cookie',
      showCancelButton: false,
      confirmButtonText: '知道了'
    })
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
        await videoApi.thirdPartyImport(getItemId(item), target, item.platform)
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
  if (isVideoMode.value) {
    return listStore.isFavoritedVideo(item)
  } else {
    return listStore.isFavorited(item)
  }
}

async function toggleFavorite(item) {
  const source = activeTab.value === 'local' ? 'local' : 'preview'
  if (isVideoMode.value) {
    await listStore.toggleFavoriteVideo(item.id, source)
  } else {
    await listStore.toggleFavorite(item.id, source)
  }
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
  background: transparent;
  display: flex;
  flex-direction: column;
  color: var(--text-primary);
}

.search-header {
  margin: 10px 10px 0;
  border: 1px solid var(--border-soft);
  border-radius: 16px;
  background: var(--surface-2);
  backdrop-filter: blur(12px);
  padding-top: 8px;
  position: sticky;
  top: 10px;
  z-index: 14;
  box-shadow: 0 10px 24px rgba(17, 27, 45, 0.08);
}

.search-input-wrapper {
  display: flex;
  align-items: center;
  padding: 0 10px 8px;
}

.back-icon {
  font-size: 20px;
  padding: 10px;
  color: var(--text-primary);
}

.search-input-wrapper .van-search {
  flex: 1;
  padding: 0;
}

.tag-search-entry {
  display: flex;
  justify-content: flex-end;
  padding: 0 12px 10px;
}

.search-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0 20px;
}

.loading-center {
  padding: 40px;
  text-align: center;
}

.load-more {
  padding: 20px;
}

.remote-select-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px 0;
}

.remote-select-bar .selected-count {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 600;
}

.pagination-info {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 10px 16px;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  box-shadow: 0 8px 20px rgba(17, 27, 45, 0.08);
  flex-wrap: wrap;
}

.platform-item {
  display: flex;
  gap: 8px;
  padding: 5px 10px;
  background: rgba(89, 160, 255, 0.16);
  border-radius: 999px;
}

.platform-info,
.page-info,
.total-pages {
  font-size: 14px;
  color: var(--text-secondary);
}

.platform-info {
  font-weight: 600;
  color: var(--brand-600);
}

.page-info {
  font-weight: 500;
  color: var(--text-strong);
}

.floating-import-bar {
  position: fixed;
  bottom: 18px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  padding: 12px 20px;
  border-radius: 999px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  box-shadow: 0 14px 28px rgba(17, 27, 45, 0.16);
  max-width: 90%;
  width: auto;
  backdrop-filter: blur(12px);
}

.floating-selection-info {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 600;
  white-space: nowrap;
}

.remote-results-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  padding: 12px;
}

.remote-result-card {
  background: var(--surface-2);
  border: 1px solid rgba(78, 104, 155, 0.14);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 8px 18px rgba(17, 27, 45, 0.08);
  cursor: pointer;
  transition:
    transform var(--motion-base) var(--ease-standard),
    border-color var(--motion-base) var(--ease-standard),
    box-shadow var(--motion-base) var(--ease-standard);
  position: relative;
}

.remote-result-card:hover {
  transform: translateY(-3px);
  border-color: rgba(47, 116, 255, 0.32);
  box-shadow: 0 18px 34px rgba(22, 44, 84, 0.16);
}

.remote-result-card.selected {
  box-shadow: 0 0 0 2px rgba(47, 116, 255, 0.6);
}

.card-cover {
  position: relative;
  aspect-ratio: 2 / 3;
  background: linear-gradient(145deg, rgba(70, 108, 171, 0.24) 0%, rgba(102, 138, 198, 0.2) 100%);
}

.remote-results-grid.video-mode .card-cover.video-cover-landscape {
  aspect-ratio: 16 / 9;
}

.remote-results-grid.video-mode .card-cover.video-cover-portrait {
  aspect-ratio: 2 / 3;
}

.cover-image {
  width: 100%;
  height: 100%;
}

.platform-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  background: var(--surface-3);
  border: 1px solid var(--border-soft);
  color: var(--text-primary);
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
  backdrop-filter: blur(4px);
}

.card-score {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 2;
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
  background: var(--brand-500);
  border-radius: 50%;
  padding: 8px;
}

.card-info {
  padding: 10px 10px 11px;
}

.card-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-strong);
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
  color: var(--text-secondary);
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
  .search-header {
    margin-inline: 14px;
  }

  .remote-results-grid {
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    padding: 14px;
  }
}

@media (max-width: 767px) {
  .search-header {
    top: 8px;
    margin: 8px 8px 0;
    border-radius: 14px;
  }

  .remote-results-grid {
    gap: 10px;
    padding: 10px;
  }

  .remote-results-grid.video-mode .card-cover.video-cover-landscape {
    aspect-ratio: 3 / 2;
  }

  .remote-results-grid.video-mode .card-title {
    font-size: 12px;
    line-height: 1.35;
  }

  .remote-results-grid.video-mode .card-author {
    font-size: 11px;
  }

  .floating-import-bar {
    bottom: 64px;
  }

  .pagination-info {
    margin-inline: 10px;
  }
}
</style>
