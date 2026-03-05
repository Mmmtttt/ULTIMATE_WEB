<template>
  <div class="home" :class="{ 'home-desktop': isDesktop, 'home-mobile': isMobile }">
    <van-nav-bar title="漫画库">
      <template #left>
        <van-button 
          size="small" 
          type="default" 
          @click="goToVideoMode"
        >
          视频
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
    
    <!-- 漫画网格 - 管理模式 -->
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
    
    <!-- 漫画网格 - 普通模式 -->
    <ComicGrid
      v-else
      :comics="results"
      @card-click="goToDetail"
      @author-click="handleAuthorClick"
    />
    
    <!-- 标签筛选面板 -->
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
            label="按导入时间倒序排列"
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
    
    <!-- 导入漫画面板 -->
    <van-popup 
      v-model:show="showImportPanel" 
      :position="isDesktop ? 'center' : 'bottom'" 
      round 
      :style="isDesktop ? { width: '600px', height: '80vh' } : { height: '80%' }"
    >
      <div class="import-panel">
        <van-nav-bar title="导入漫画" left-text="关闭" @click-left="showImportPanel = false" />
        
        <div class="import-target-select">
          <van-radio-group v-model="importTarget" direction="horizontal">
            <van-radio name="home">导入主页</van-radio>
            <van-radio name="recommendation">导入推荐页</van-radio>
          </van-radio-group>
        </div>
        
        <div class="import-platform-select">
          <van-radio-group v-model="importPlatform" direction="horizontal">
            <van-radio name="all">全部平台</van-radio>
            <van-radio name="JM">JM平台</van-radio>
            <van-radio name="PK">PK平台</van-radio>
          </van-radio-group>
        </div>
        
        <div class="import-search">
          <van-search
            v-model="importKeyword"
            placeholder="输入关键词搜索漫画"
            @search="handleImportSearch"
          />
        </div>
        
        <van-loading v-if="importLoading" type="spinner" color="#1989fa" class="import-loading" />
        
        <div v-else-if="importResults.length > 0" class="import-results">
          <div 
            v-for="item in importResults" 
            :key="item.album_id || item.id" 
            class="import-item"
          >
            <div v-if="item.cover_url" class="import-item-cover">
              <img :src="item.cover_url" :alt="item.title" @error="handleImportCoverError(item)" />
            </div>
            <div class="import-item-info">
              <div class="import-item-platform">{{ item.platform }}平台</div>
              <div class="import-item-title">{{ item.title }}</div>
              <div class="import-item-author">{{ item.author || '' }}</div>
            </div>
            <van-button 
              size="small" 
              type="primary" 
              :loading="item.importing"
              @click="importComic(item)"
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
      <van-tabbar-item icon="star-o" to="/recommendation">推荐</van-tabbar-item>
      <van-tabbar-item icon="user-o" to="/mine">我的</van-tabbar-item>
    </van-tabbar>
    
    <!-- 顶部导航 - 电脑端显示 -->
    <div v-if="isDesktop" class="desktop-nav">
      <router-link :to="homePath" class="nav-item" :class="{ active: $route.path === '/' || $route.path === '/video-home' }">
        <van-icon name="home-o" />
        <span>主页</span>
      </router-link>
      <router-link to="/recommendation" class="nav-item" :class="{ active: $route.path === '/recommendation' }">
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
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showConfirmDialog, showSuccessToast, showFailToast } from 'vant'
import { useComicStore, useTagStore, useImportTaskStore, useModeStore } from '@/stores'
import { useSearch, useDevice } from '@/composables'
import { ComicGrid, EmptyState, TagFilter } from '@/components'
import { comicApi } from '@/api'
import request from '@/api/request'

const { isMobile, isDesktop } = useDevice()

const router = useRouter()
const route = useRoute()
const comicStore = useComicStore()
const tagStore = useTagStore()
const importTaskStore = useImportTaskStore()
const modeStore = useModeStore()

const homePath = computed(() => modeStore.isVideoMode ? '/video-home' : '/')

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

const isManageMode = ref(false)
const selectedComicIds = ref([])
const menuValue = ref(0)
const menuOptions = [
  { text: '更多操作', value: 0 },
  { text: '导入漫画', value: 1 },
  { text: '管理漫画', value: 2 }
]

const isLoading = computed(() => loading.value || comicStore.loading)

const sortLabel = computed(() => {
  const labels = {
    'create_time': '最近导入',
    'score': '按评分',
    'read_time': '按阅读时间',
    'read_status': '已读/未读'
  }
  return labels[currentSortType.value] || ''
})

function goToVideoMode() {
  modeStore.setMode('video')
  router.push('/video-home')
}

const showImportPanel = ref(false)
const importKeyword = ref('')
const importLoading = ref(false)
const importResults = ref([])
const importPlatform = ref('all')
const importTarget = ref('home')

function handleMenuChange(value) {
  if (value === 1) {
    showImportPanel.value = true
    menuValue.value = 0
  } else if (value === 2) {
    isManageMode.value = true
    selectedComicIds.value = []
    menuValue.value = 0
  }
}

async function handleImportSearch() {
  if (!importKeyword.value.trim()) {
    return
  }
  
  importLoading.value = true
  try {
    const results = await comicStore.thirdPartySearch(importKeyword.value, importPlatform.value)
    importResults.value = results.map(r => ({ ...r, importing: false }))
  } catch (e) {
    showFailToast('搜索失败')
  } finally {
    importLoading.value = false
  }
}

async function importComic(item) {
  item.importing = true
  try {
    const res = await comicStore.thirdPartyImport(item.album_id || item.id, importTarget.value, item.platform)
    if (res.code === 200) {
      showSuccessToast('导入成功')
      if (importTarget.value === 'home') {
        await comicStore.fetchComics(true)
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

function cancelManageMode() {
  isManageMode.value = false
  selectedComicIds.value = []
}

function handleImportCoverError(item) {
  item.cover_url = null
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
    
    const res = await comicApi.batchMoveToTrash(selectedComicIds.value)
    if (res.code === 200) {
      showToast(res.msg || '已移入回收站')
      selectedComicIds.value = []
      isManageMode.value = false
      await comicStore.fetchComics(true, currentSortType.value ? { sort_type: currentSortType.value } : {})
    } else {
      showToast(res.msg || '操作失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      showToast('操作失败')
    }
  }
}

function handleSearch() {
  search()
}

function goToDetail(comic) {
  router.push(`/comic/${comic.id}`)
}

function handleAuthorClick(author) {
  keyword.value = author
  search()
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
  modeStore.setMode('comic')
  await init()
  
  const tagId = route.query.tagId
  if (tagId && !includeTags.value.includes(tagId)) {
    includeTags.value = [tagId]
    await filterByTags()
  }
  
  const importIds = route.query.importIds
  if (importIds) {
    const ids = importIds.split(',').filter(id => id.trim())
    if (ids.length > 0) {
      await createImportFromIds(ids, 'home')
      router.replace({ query: {} })
    }
  }
  
  const authorName = route.query.author
  if (authorName) {
    keyword.value = authorName
    await handleSearch()
    router.replace({ query: {} })
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
</script>

<style scoped>
.home {
  min-height: 100vh;
  background: #f5f5f5;
}

.home-mobile {
  padding-bottom: 50px;
}

.home-desktop {
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

.home-mobile .sort-btn,
.home-mobile .filter-btn {
  padding: 0 8px;
}

.home-desktop .sort-btn,
.home-desktop .filter-btn {
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
  gap: 8px;
  padding: 8px;
}

.home-mobile .comic-select-grid {
  grid-template-columns: repeat(3, 1fr);
}

.home-desktop .comic-select-grid {
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
  padding: 12px;
}

@media (min-width: 1200px) {
  .home-desktop .comic-select-grid {
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  }
}

@media (min-width: 1600px) {
  .home-desktop .comic-select-grid {
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  }
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

.home-desktop .comic-title-line {
  padding: 6px 8px;
  font-size: 13px;
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

.import-platform-select {
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

.import-item-cover {
  width: 60px;
  height: 80px;
  flex-shrink: 0;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f5f5;
  margin-right: 12px;
}

.import-item-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.import-item-info {
  flex: 1;
  overflow: hidden;
  min-width: 0;
}

.import-item-platform {
  font-size: 12px;
  color: #1989fa;
}

.import-item-title {
  font-size: 14px;
  color: #333;
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.import-item-author {
  font-size: 12px;
  color: #666;
  margin-top: 2px;
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

.home-desktop .select-check {
  width: 24px;
  height: 24px;
  font-size: 14px;
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
