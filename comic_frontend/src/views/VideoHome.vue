<template>
  <div class="video-home">
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
        排序
        <van-icon name="sort" />
      </van-button>
    </div>
    
    <div v-if="currentSortType" class="active-filter-bar">
      <van-tag 
        type="primary" 
        closeable 
        @close="clearSort"
        class="filter-tag"
      >
        {{ sortLabel }}
      </van-tag>
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
      position="bottom" 
      round 
      :style="{ height: '50%' }"
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
      v-model:show="showImportPanel" 
      position="bottom" 
      round 
      :style="{ height: '80%' }"
    >
      <div class="import-panel">
        <van-nav-bar title="导入视频" left-text="关闭" @click-left="showImportPanel = false" />
        
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
    
    <van-tabbar v-model="active" route>
      <van-tabbar-item icon="home-o" to="/">主页</van-tabbar-item>
      <van-tabbar-item v-if="!isVideoMode" icon="star-o" to="/recommendation">推荐</van-tabbar-item>
      <van-tabbar-item v-if="isVideoMode" icon="user-o" to="/actors">演员</van-tabbar-item>
      <van-tabbar-item icon="user-o" to="/mine">我的</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import { useModeStore, useVideoStore, useComicStore } from '@/stores'
import { EmptyState } from '@/components'

const router = useRouter()
const modeStore = useModeStore()
const videoStore = useVideoStore()
const comicStore = useComicStore()

const active = ref(0)
const keyword = ref('')
const currentSortType = ref('')
const showSortPanel = ref(false)
const showImportPanel = ref(false)
const importKeyword = ref('')
const importLoading = ref(false)
const importResults = ref([])
const menuValue = ref(0)
const menuOptions = [
  { text: '更多操作', value: 0 },
  { text: '导入视频', value: 1 }
]

const isVideoMode = computed(() => modeStore.isVideoMode)
const isLoading = computed(() => isVideoMode.value ? videoStore.loading : comicStore.loading)
const results = computed(() => isVideoMode.value ? videoStore.videos : comicStore.comics)
const hasResults = computed(() => results.value.length > 0)

const sortLabel = computed(() => {
  const labels = {
    'create_time': '最近导入',
    'score': '按评分',
    'date': '按日期'
  }
  return labels[currentSortType.value] || ''
})

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
    const res = await videoStore.thirdPartyImport(item.video_id)
    if (res.code === 200) {
      showSuccessToast('导入成功')
      await videoStore.fetchList()
    } else {
      showFailToast(res.msg || '导入失败')
    }
  } catch (e) {
    showFailToast('导入失败')
  } finally {
    item.importing = false
  }
}

onMounted(() => {
  loadData()
})

watch(() => modeStore.currentMode, () => {
  loadData()
})
</script>

<style scoped>
.video-home {
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

.sort-btn {
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

.video-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  padding: 12px;
}

.video-card {
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
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

.video-info {
  padding: 8px;
}

.video-title {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
</style>
