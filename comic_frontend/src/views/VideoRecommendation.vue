<template>
  <div class="video-recommendation" :class="{ 'video-recommendation-desktop': isDesktop, 'video-recommendation-mobile': isMobile }">
    <van-nav-bar title="推荐视频">
      <template #right>
        <van-dropdown-menu direction="down">
          <van-dropdown-item v-model="menuValue" :options="menuOptions" @change="handleMenuChange" />
        </van-dropdown-menu>
      </template>
    </van-nav-bar>

    <div class="search-bar">
      <van-search
        v-model="keyword"
        placeholder="搜索推荐视频"
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
        <van-icon v-if="isMobile" name="sort" />
        <template v-else>排序 <van-icon name="sort" /></template>
      </van-button>
    </div>

    <div v-if="currentSortType" class="active-filter-bar">
      <van-tag
        v-if="currentSortType"
        type="primary"
        closeable
        @close="clearSort"
        class="filter-tag"
      >
        {{ sortLabel }}
      </van-tag>
      <van-button size="mini" plain @click="clearAllFilters">清空</van-button>
    </div>

    <!-- 批量操作模式 -->
    <div v-if="isManageMode" class="manage-bar">
      <span class="selected-info">已选 {{ selectedVideoIds.length }} 个</span>
      <div class="manage-actions">
        <van-button size="small" type="primary" :disabled="selectedVideoIds.length === 0" @click="batchMoveToTrash">
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
      title="暂无推荐视频"
      :description="keyword ? '没有找到匹配的推荐视频' : '还没有添加任何推荐视频'"
    >
      <template #action>
        <van-button v-if="keyword" type="primary" @click="clearAllFilters">
          清除筛选
        </van-button>
      </template>
    </EmptyState>

    <!-- 推荐视频网格 - 管理模式 -->
    <div v-else-if="isManageMode" class="video-select-grid">
      <div 
        v-for="video in results" 
        :key="video.id" 
        class="video-select-item"
        :class="{ selected: selectedVideoIds.includes(video.id) }"
        @click="toggleVideoSelection(video.id)"
      >
        <van-image 
          :src="getCoverUrl(video.cover_path)" 
          fit="cover" 
          class="video-thumb"
        />
        <div class="video-title-line">{{ video.title }}</div>
        <div class="select-check" v-if="selectedVideoIds.includes(video.id)">
          <van-icon name="success" />
        </div>
      </div>
    </div>

    <!-- 推荐视频网格 - 普通模式 -->
    <div v-else class="video-grid">
      <div 
        v-for="video in results" 
        :key="video.id" 
        class="video-card"
        @click="goToDetail(video)"
      >
        <div class="video-cover">
          <van-image 
            :src="getCoverUrl(video.cover_path)" 
            fit="cover" 
            class="cover-image"
          />
          <div v-if="video.code" class="video-code">{{ video.code }}</div>
          <div v-if="video.score" class="video-score">{{ video.score }}</div>
        </div>
        <div class="video-info">
          <div class="video-title">{{ video.title }}</div>
          <div v-if="video.date" class="video-date">{{ video.date }}</div>
        </div>
      </div>
    </div>

    <!-- 排序面板 -->
    <van-popup
      v-model:show="showSortPanel"
      :position="isDesktop ? 'center' : 'bottom'"
      round
      :style="isDesktop ? { width: '400px' } : { height: '50%' }"
    >
      <div class="sort-panel">
        <van-nav-bar title="排序方式" left-text="关闭" @click-left="showSortPanel = false" />
        <van-cell-group>
          <van-cell 
            title="最近导入" 
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
            title="按发布日期" 
            clickable 
            @click="setSortType('date')"
          >
            <template #right-icon>
              <van-icon v-if="currentSortType === 'date'" name="success" color="#1989fa" />
            </template>
          </van-cell>
        </van-cell-group>
      </div>
    </van-popup>

    <!-- 底部导航 - 手机端显示 -->
    <van-tabbar v-if="isMobile" v-model="active" route>
      <van-tabbar-item icon="home-o" :to="homePath">主页</van-tabbar-item>
      <van-tabbar-item icon="star-o" to="/video-recommendation">推荐</van-tabbar-item>
      <van-tabbar-item icon="user-o" to="/mine">我的</van-tabbar-item>
    </van-tabbar>
    
    <!-- 顶部导航 - 电脑端显示 -->
    <div v-if="isDesktop" class="desktop-nav">
      <router-link :to="homePath" class="nav-item" :class="{ active: $route.path === '/' || $route.path === '/video-home' }">
        <van-icon name="home-o" />
        <span>主页</span>
      </router-link>
      <router-link to="/video-recommendation" class="nav-item" :class="{ active: $route.path === '/video-recommendation' }">
        <van-icon name="star-o" />
        <span>推荐</span>
      </router-link>
      <router-link to="/mine" class="nav-item" :class="{ active: $route.path === '/mine' }">
        <van-icon name="user-o" />
        <span>我的</span>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showConfirmDialog, showSuccessToast, showFailToast } from 'vant'
import { useVideoRecommendationStore, useTagStore, useImportTaskStore, useModeStore } from '@/stores'
import { useDevice } from '@/composables/useDevice'
import EmptyState from '@/components/common/EmptyState.vue'

const router = useRouter()
const route = useRoute()
const videoRecommendationStore = useVideoRecommendationStore()
const tagStore = useTagStore()
const importTaskStore = useImportTaskStore()
const modeStore = useModeStore()
const { isDesktop, isMobile } = useDevice()

const homePath = computed(() => modeStore.isVideoMode ? '/video-home' : '/')

// ============ State ============
const keyword = ref('')
const showSortPanel = ref(false)
const active = ref(1)

// 管理模式相关
const isManageMode = ref(false)
const selectedVideoIds = ref([])
const menuValue = ref(0)
const menuOptions = [
  { text: '更多操作', value: 0 },
  { text: '管理视频', value: 1 }
]

// ============ Computed ============
const isLoading = computed(() => videoRecommendationStore.loading)
const results = computed(() => videoRecommendationStore.recommendationList)
const hasResults = computed(() => results.value.length > 0)
const currentSortType = computed(() => videoRecommendationStore.currentSort)

const sortLabel = computed(() => {
  const labels = {
    'create_time': '最近导入',
    'score': '按评分',
    'date': '按发布日期'
  }
  return labels[currentSortType.value] || ''
})

// ============ Methods ============

function handleMenuChange(value) {
  if (value === 1) {
    isManageMode.value = true
    selectedVideoIds.value = []
    menuValue.value = 0
  }
}

function cancelManageMode() {
  isManageMode.value = false
  selectedVideoIds.value = []
}

function toggleVideoSelection(videoId) {
  const index = selectedVideoIds.value.indexOf(videoId)
  if (index > -1) {
    selectedVideoIds.value.splice(index, 1)
  } else {
    selectedVideoIds.value.push(videoId)
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
  if (selectedVideoIds.value.length === 0) {
    showToast('请先选择视频')
    return
  }
  
  try {
    await showConfirmDialog({
      title: '确认操作',
      message: `确定将 ${selectedVideoIds.value.length} 个视频移入回收站吗？`
    })
    
    const res = await videoRecommendationStore.batchMoveToTrash(selectedVideoIds.value)
    if (res) {
      showToast('已移入回收站')
      selectedVideoIds.value = []
      isManageMode.value = false
      await videoRecommendationStore.fetchRecommendations(true, currentSortType.value ? { sortType: currentSortType.value } : {})
    } else {
      showToast('操作失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      showToast('操作失败')
    }
  }
}

async function fetchRecommendations() {
  console.log('[VideoRecommendation] 获取推荐列表')
  await videoRecommendationStore.fetchRecommendations()
}

function goToDetail(video) {
  console.log('[VideoRecommendation] 跳转到详情页:', video.id)
  router.push(`/video-recommendation/${video.id}`)
}

async function handleSearch() {
  if (!keyword.value.trim()) {
    clearSearch()
    return
  }
  console.log('[VideoRecommendation] 搜索:', keyword.value)
  await videoRecommendationStore.searchRecommendations(keyword.value)
}

function clearSearch() {
  keyword.value = ''
  videoRecommendationStore.clearFilter()
}

function setSortType(type) {
  videoRecommendationStore.setSortType(type)
  showSortPanel.value = false
  videoRecommendationStore.fetchRecommendations(true, { sortType: type })
}

async function clearSort() {
  videoRecommendationStore.clearSort()
  await videoRecommendationStore.fetchRecommendations(true)
}

async function clearAllFilters() {
  keyword.value = ''
  videoRecommendationStore.clearSort()
  videoRecommendationStore.clearFilter()
  await videoRecommendationStore.fetchRecommendations(true)
}

// ============ Lifecycle ============
onMounted(async () => {
  console.log('[VideoRecommendation] 页面挂载')
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
      platform: 'JAVDB',
      comic_id: ids.length === 1 ? ids[0] : undefined, // API expects comic_id for by_id
      comic_ids: ids.length > 1 ? ids : undefined // API expects comic_ids for by_list
    }
    
    // 导入任务目前主要针对漫画设计，但后端 import_async 也支持。
    // 如果要支持视频导入任务，需要后端扩展。
    // 目前视频导入是同步的 videoApi.importVideo
    // 假设我们要复用 TaskManager，需要后端支持。
    // 暂时先用 importTaskStore.createImportTask，但后端需要区分 platform='JAVDB'
    
    const result = await importTaskStore.createImportTask(params)
    if (result) {
      showSuccessToast(`已创建导入任务，共 ${ids.length} 个视频`)
    }
  } catch (error) {
    console.error('创建导入任务失败:', error)
    showFailToast('创建导入任务失败')
  }
}

watch(currentSortType, async (newSort) => {
  if (newSort) {
    await videoRecommendationStore.fetchRecommendations(true, { sortType: newSort })
  }
})
</script>

<style scoped>
.video-recommendation {
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

.video-select-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  padding: 8px;
}

.video-select-item {
  position: relative;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid transparent;
  transition: border-color 0.2s;
}

.video-select-item.selected {
  border-color: #1989fa;
}

.video-thumb {
  width: 100%;
  aspect-ratio: 16/9;
}

.video-title-line {
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

.video-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  padding: 8px;
}

.video-card {
  position: relative;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}

.video-cover {
  position: relative;
  width: 100%;
  aspect-ratio: 16/9;
}

.cover-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.video-code {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
}

.video-score {
  position: absolute;
  top: 8px;
  right: 8px;
  background: #ffd21e;
  color: #000;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: bold;
}

.video-info {
  padding: 8px;
}

.video-title {
  font-size: 12px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  margin-bottom: 4px;
}

.video-actors {
  font-size: 10px;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 2px;
}

.video-date {
  font-size: 10px;
  color: #999;
}

.sort-panel {
  padding: 16px;
}

.desktop-nav {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  background: #fff;
  border-radius: 50px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  display: flex;
  padding: 8px 20px;
  gap: 30px;
  z-index: 1000;
}

.desktop-nav .nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  text-decoration: none;
  color: #666;
  font-size: 12px;
  transition: all 0.3s;
}

.desktop-nav .nav-item:hover {
  color: #1989fa;
}

.desktop-nav .nav-item.active {
  color: #1989fa;
}

.desktop-nav .nav-item .van-icon {
  font-size: 22px;
}

@media (min-width: 768px) {
  .video-select-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  
  .video-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
