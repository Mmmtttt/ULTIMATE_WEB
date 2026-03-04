<template>
  <div class="video-home" :class="{ 'video-home-desktop': isDesktop, 'video-home-mobile': isMobile }">
    <van-nav-bar :title="isVideoMode ? '视频库' : '漫画库'">
      <template #left>
        <van-button 
          size="small" 
          :type="isVideoMode ? 'primary' : 'default'" 
          @click="toggleMode"
        >
          {{ isVideoMode ? '视频' : '漫画' }}
        </van-button>
      </template>
      <template #right>
        <van-dropdown-menu direction="down">
          <van-dropdown-item v-model="menuValue" :options="menuOptions" @change="handleMenuChange" />
        </van-dropdown-menu>
      </template>
    </van-nav-bar>
    
    <div class="search-bar">
      <van-search
        v-model="keyword"
        :placeholder="isVideoMode ? '搜索番号、标题、演员' : '搜索漫画ID、名称、作者、标签'"
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
      <van-button 
        size="small" 
        type="primary" 
        plain 
        @click="showFilterPanel = true"
        class="filter-btn"
      >
        <van-icon v-if="isMobile" name="filter-o" />
        <template v-else>筛选 <van-icon name="filter-o" /></template>
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
    
    <van-loading v-if="isLoading" type="spinner" color="#1989fa" />
    
    <EmptyState
      v-else-if="!hasResults"
      :icon="isVideoMode ? '🎬' : '📚'"
      :title="isVideoMode ? '暂无视频' : '暂无漫画'"
      :description="keyword ? '没有找到匹配的结果' : '还没有添加任何内容'"
    >
      <template #action>
        <van-button v-if="isVideoMode" type="primary" @click="showImportPanel = true">
          导入视频
        </van-button>
      </template>
    </EmptyState>
    
    <div v-else class="video-grid">
      <div 
        v-for="item in results" 
        :key="item.id" 
        class="video-card"
        @click="goToDetail(item)"
      >
        <div class="video-cover">
          <van-image 
            :src="getCoverUrl(item.cover_path)" 
            fit="cover" 
            class="cover-image"
          />
          <div v-if="item.code" class="video-code">{{ item.code }}</div>
          <div v-if="item.score" class="video-score">{{ item.score }}</div>
          <van-icon 
            v-if="isVideoMode"
            :name="isFavoritedVideo(item) ? 'star' : 'star-o'"
            :color="isFavoritedVideo(item) ? '#ff9500' : '#fff'"
            size="20"
            class="video-favorite"
            @click="toggleFavoriteVideo(item, $event)"
          />
        </div>
        <div class="video-info">
          <div class="video-title">{{ item.title }}</div>
          <div v-if="item.actors && item.actors.length > 0" class="video-actors">
            {{ item.actors.slice(0, 2).join(', ') }}
          </div>
          <div v-if="item.date" class="video-date">{{ item.date }}</div>
        </div>
      </div>
    </div>
    
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
    
    <van-popup 
      v-model:show="showFilterPanel" 
      :position="isDesktop ? 'center' : 'bottom'" 
      round 
      :style="isDesktop ? { width: '600px', height: '80vh' } : { height: '70%' }"
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
      v-model:show="showImportPanel" 
      :position="isDesktop ? 'center' : 'bottom'" 
      round 
      :style="isDesktop ? { width: '600px', height: '80vh' } : { height: '80%' }"
    >
      <div class="import-panel">
        <van-nav-bar title="导入视频" left-text="关闭" @click-left="showImportPanel = false" />
        
        <div class="import-target-select">
          <van-radio-group v-model="importTarget" direction="horizontal">
            <van-radio name="home">导入主页</van-radio>
            <van-radio name="recommendation">导入推荐页</van-radio>
          </van-radio-group>
        </div>
        
        <div class="import-search">
          <van-search
            v-model="importKeyword"
            placeholder="输入番号或关键词搜索"
            @search="handleImportSearch"
          />
        </div>
        
        <van-loading v-if="importLoading" type="spinner" color="#1989fa" class="import-loading" />
        
        <div v-else-if="importResults.length > 0" class="import-results">
          <div 
            v-for="item in importResults" 
            :key="item.video_id" 
            class="import-item"
          >
            <div class="import-item-info">
              <div class="import-item-code">{{ item.code }}</div>
              <div class="import-item-title">{{ item.title }}</div>
              <div class="import-item-date">{{ item.date }}</div>
            </div>
            <van-button 
              size="small" 
              type="primary" 
              :loading="item.importing"
              @click="importVideo(item)"
            >
              导入
            </van-button>
          </div>
        </div>
        
        <EmptyState
          v-else-if="importKeyword && !importLoading"
          icon="🔍"
          title="未找到结果"
          description="请尝试其他关键词"
        />
      </div>
    </van-popup>
    
    <!-- 底部导航 - 手机端显示 -->
    <van-tabbar v-if="isMobile" v-model="active" route>
      <van-tabbar-item icon="home-o" :to="homePath">主页</van-tabbar-item>
      <van-tabbar-item v-if="!isVideoMode" icon="star-o" to="/recommendation">推荐</van-tabbar-item>
      <van-tabbar-item v-if="isVideoMode" icon="user-o" to="/actors">演员</van-tabbar-item>
      <van-tabbar-item icon="user-o" to="/mine">我的</van-tabbar-item>
    </van-tabbar>
    
    <!-- 顶部导航 - 电脑端显示 -->
    <div v-if="isDesktop" class="desktop-nav">
      <router-link :to="homePath" class="nav-item" :class="{ active: $route.path === '/' || $route.path === '/video-home' }">
        <van-icon name="home-o" />
        <span>主页</span>
      </router-link>
      <router-link v-if="!isVideoMode" to="/recommendation" class="nav-item" :class="{ active: $route.path === '/recommendation' }">
        <van-icon name="star-o" />
        <span>推荐</span>
      </router-link>
      <router-link v-if="isVideoMode" to="/actors" class="nav-item" :class="{ active: $route.path === '/actors' }">
        <van-icon name="user-o" />
        <span>演员</span>
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
import { showToast, showSuccessToast, showFailToast } from 'vant'
import { useModeStore, useVideoStore, useComicStore, useTagStore, useListStore } from '@/stores'
import { useDevice } from '@/composables'
import { EmptyState, TagFilter } from '@/components'

const { isMobile, isDesktop } = useDevice()

const router = useRouter()
const route = useRoute()
const modeStore = useModeStore()
const videoStore = useVideoStore()
const comicStore = useComicStore()
const tagStore = useTagStore()
const listStore = useListStore()

const homePath = computed(() => modeStore.isVideoMode ? '/video-home' : '/')

const active = ref(0)
const keyword = ref('')
const includeTags = ref([])
const excludeTags = ref([])
const currentSortType = ref('')
const showSortPanel = ref(false)
const showFilterPanel = ref(false)
const showImportPanel = ref(false)
const importKeyword = ref('')
const importLoading = ref(false)
const importResults = ref([])
const importTarget = ref('home')
const menuValue = ref(0)
const menuOptions = [
  { text: '更多操作', value: 0 },
  { text: '导入视频', value: 1 }
]

const isVideoMode = computed(() => modeStore.isVideoMode)
const isLoading = computed(() => isVideoMode.value ? videoStore.loading : comicStore.loading)
const results = computed(() => isVideoMode.value ? videoStore.videoList : comicStore.comics)
const hasResults = computed(() => results.value.length > 0)
const isFiltering = computed(() => 
  keyword.value || 
  includeTags.value.length > 0 || 
  excludeTags.value.length > 0
)

const tags = computed(() => tagStore.videoTags)

const selectedIncludeTags = computed(() => {
  return includeTags.value.map(id => tagStore.getVideoTagById(id)).filter(Boolean)
})

const selectedExcludeTags = computed(() => {
  return excludeTags.value.map(id => tagStore.getVideoTagById(id)).filter(Boolean)
})

const sortLabel = computed(() => {
  const labels = {
    'create_time': '最近导入',
    'score': '按评分',
    'date': '按日期'
  }
  return labels[currentSortType.value] || ''
})

function isFavoritedVideo(video) {
  return listStore.isFavoritedVideo(video)
}

async function toggleFavoriteVideo(video, event) {
  event.stopPropagation()
  const result = await listStore.toggleFavoriteVideo(video.id)
  if (result !== null) {
    if (result) {
      video.list_ids = video.list_ids || []
      if (!video.list_ids.includes('favorites')) {
        video.list_ids.push('favorites')
      }
    } else {
      video.list_ids = (video.list_ids || []).filter(id => id !== 'favorites')
    }
  }
}

function toggleMode() {
  modeStore.toggleMode()
  keyword.value = ''
  currentSortType.value = ''
  loadData()
}

async function loadData() {
  if (isVideoMode.value) {
    await videoStore.fetchList()
  } else {
    await comicStore.fetchComics()
  }
}

function handleSearch() {
  if (!keyword.value.trim()) {
    loadData()
    return
  }
  
  if (isVideoMode.value) {
    videoStore.search(keyword.value)
  } else {
    comicStore.searchComics(keyword.value)
  }
}

function clearSearch() {
  keyword.value = ''
  loadData()
}

function getCoverUrl(coverPath) {
  if (!coverPath) return ''
  if (coverPath.startsWith('http')) return coverPath
  if (coverPath.startsWith('/static/')) return coverPath
  if (coverPath.startsWith('/')) return coverPath
  return `/${coverPath}`
}

function goToDetail(item) {
  if (isVideoMode.value) {
    router.push(`/video/${item.id}`)
  } else {
    router.push(`/comic/${item.id}`)
  }
}

async function setSortType(sortType) {
  currentSortType.value = sortType
  showSortPanel.value = false
  
  if (isVideoMode.value) {
    await videoStore.fetchList({ sort_type: sortType })
  } else {
    await comicStore.fetchComics(true, { sort_type: sortType })
  }
}

function clearSort() {
  currentSortType.value = ''
  loadData()
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
    videoStore.clearFilter()
  }
}

function applyFilterAndClose() {
  showFilterPanel.value = false
}

async function filterByTags() {
  if (isVideoMode.value) {
    await videoStore.filterByTags(includeTags.value, excludeTags.value)
  }
}

function clearAllFilters() {
  keyword.value = ''
  includeTags.value = []
  excludeTags.value = []
  currentSortType.value = ''
  videoStore.clearFilter()
  loadData()
}

function handleMenuChange(value) {
  if (value === 1 && isVideoMode.value) {
    showImportPanel.value = true
    menuValue.value = 0
  }
}

async function handleImportSearch() {
  if (!importKeyword.value.trim()) {
    return
  }
  
  importLoading.value = true
  try {
    const results = await videoStore.thirdPartySearch(importKeyword.value)
    importResults.value = results.map(r => ({ ...r, importing: false }))
  } catch (e) {
    showFailToast('搜索失败')
  } finally {
    importLoading.value = false
  }
}

async function importVideo(item) {
  item.importing = true
  try {
    const res = await videoStore.thirdPartyImport(item.video_id, importTarget.value)
    if (res.code === 200) {
      showSuccessToast('导入成功')
      if (importTarget.value === 'home') {
        await videoStore.fetchList()
      }
    } else {
      showFailToast(res.msg || '导入失败')
    }
  } catch (e) {
    showFailToast('导入失败')
  } finally {
    item.importing = false
  }
}

onMounted(async () => {
  modeStore.setMode('video')
  
  if (tagStore.videoTags.length === 0) {
    await tagStore.fetchTags('video')
  }
  
  loadData()
  
  const tagId = route.query.tagId
  if (tagId && !includeTags.value.includes(tagId)) {
    includeTags.value = [tagId]
    await filterByTags()
  }
})

watch(() => modeStore.currentMode, () => {
  loadData()
})
</script>

<style scoped>
.video-home {
  min-height: 100vh;
  background: #f5f5f5;
}

.video-home-mobile {
  padding-bottom: 50px;
}

.video-home-desktop {
  max-width: 1400px;
  margin: 0 auto;
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
}

.video-home-mobile .sort-btn,
.video-home-mobile .filter-btn {
  padding: 0 8px;
}

.video-home-desktop .sort-btn,
.video-home-desktop .filter-btn {
  padding: 0 12px;
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

.video-grid {
  display: grid;
  gap: 12px;
  padding: 12px;
}

.video-home-mobile .video-grid {
  grid-template-columns: repeat(2, 1fr);
}

.video-home-desktop .video-grid {
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  padding: 16px;
}

@media (min-width: 1200px) {
  .video-home-desktop .video-grid {
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  }
}

@media (min-width: 1600px) {
  .video-home-desktop .video-grid {
    grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
    gap: 20px;
    padding: 20px;
  }
}

.video-card {
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
  cursor: pointer;
}

.video-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.video-cover {
  position: relative;
  aspect-ratio: 16/9;
}

.cover-image {
  width: 100%;
  height: 100%;
}

.video-code {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.video-score {
  position: absolute;
  top: 8px;
  right: 8px;
  background: #ff9500;
  color: #fff;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.video-favorite {
  position: absolute;
  bottom: 8px;
  right: 8px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
  cursor: pointer;
}

.video-info {
  padding: 8px;
}

.video-home-desktop .video-info {
  padding: 12px;
}

.video-title {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-home-desktop .video-title {
  font-size: 15px;
}

.video-actors {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-date {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.import-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.import-target-select {
  padding: 12px;
  background: #fff;
  border-bottom: 1px solid #f5f5f5;
}

.import-search {
  padding: 10px;
  background: #fff;
}

.import-loading {
  padding: 40px;
  text-align: center;
}

.import-results {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.import-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  background: #fff;
  border-radius: 8px;
  margin-bottom: 10px;
}

.import-item-info {
  flex: 1;
  overflow: hidden;
}

.import-item-code {
  font-size: 14px;
  font-weight: 500;
  color: #1989fa;
}

.import-item-title {
  font-size: 13px;
  color: #333;
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.import-item-date {
  font-size: 12px;
  color: #999;
  margin-top: 2px;
}

@media (max-width: 767px) {
  .video-card:hover {
    transform: none;
  }
  
  .video-card:active {
    transform: scale(0.98);
  }
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
</style>
