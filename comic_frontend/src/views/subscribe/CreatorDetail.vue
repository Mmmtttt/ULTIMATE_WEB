<template>
  <div class="creator-detail-page">
    <van-nav-bar :title="creatorName" left-text="返回" left-arrow @click-left="$router.back()" />

    <div class="creator-header">
      <div class="avatar-placeholder">
        <van-icon name="user-circle-o" size="64" color="#ddd" />
      </div>
      <div class="info">
        <h1>{{ creatorName }}</h1>
        <p>共 {{ totalWorks }} 部作品</p>
      </div>
      <div class="actions">
        <van-button 
          :type="isSubscribed ? 'default' : 'primary'" 
          size="small" 
          round
          @click="toggleSubscribe"
        >
          {{ isSubscribed ? '已订阅' : '订阅' }}
        </van-button>
      </div>
    </div>

    <div class="works-area">
      <van-loading v-if="loading" class="loading-center" />
      
      <EmptyState 
        v-else-if="works.length === 0" 
        title="暂无作品" 
      />

      <div v-else class="remote-results-grid" :class="{ 'video-mode': isVideoMode }">
        <div
          v-for="item in works"
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
      
      <div v-if="hasMore" class="load-more">
        <van-button block plain :loading="loadingMore" @click="loadMore">
          加载更多
        </van-button>
      </div>
    </div>

    <!-- 浮动导入栏 -->
    <div class="floating-import-bar" v-if="selectedIds.length > 0">
      <span class="floating-selection-info">已选 {{ selectedIds.length }} 项</span>
      <van-button type="primary" @click="handleImport">导入选中</van-button>
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
import { useRoute, useRouter } from 'vue-router'
import { useModeStore, useActorStore, useImportTaskStore } from '@/stores'
import { videoApi, authorApi } from '@/api' // Ensure authorApi is exported
import MediaGrid from '@/components/common/MediaGrid.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { showToast } from 'vant'

const route = useRoute()
const router = useRouter()
const modeStore = useModeStore()
const actorStore = useActorStore()
const importTaskStore = useImportTaskStore()

const creatorName = computed(() => decodeURIComponent(route.params.name))
const isVideoMode = computed(() => modeStore.isVideoMode)

const loading = ref(false)
const loadingMore = ref(false)
const works = ref([])
const totalWorks = ref(0)
const hasMore = ref(false)
const currentPage = ref(1)
const selectedIds = ref([])
const showImportSheet = ref(false)
const isSubscribed = ref(false)
const actorId = ref(null) // For video mode

async function loadData(page = 1) {
  if (page === 1) loading.value = true
  else loadingMore.value = true
  
  try {
    if (isVideoMode.value) {
      // First, find actor ID if not known
      if (!actorId.value) {
        const searchRes = await videoApi.thirdPartyActorSearch(creatorName.value)
        if (searchRes.code === 200 && searchRes.data.length > 0) {
          // Exact match preferred
          const match = searchRes.data.find(a => a.actor_name === creatorName.value) || searchRes.data[0]
          actorId.value = match.actor_id
        }
      }
      
      if (actorId.value) {
        const res = await videoApi.thirdPartyActorWorks(actorId.value, page)
        if (res.code === 200) {
          const newWorks = res.data.works || []
          if (page === 1) works.value = newWorks
          else works.value = [...works.value, ...newWorks]
          
          hasMore.value = res.data.has_next
        }
      }
    } else {
      // Comic mode
      const res = await authorApi.searchWorksByName(creatorName.value, (page - 1) * 20, 20) // Assuming pagination
      if (res.code === 200) {
        const newWorks = res.data.works || []
        if (page === 1) works.value = newWorks
        else works.value = [...works.value, ...newWorks]
        
        hasMore.value = res.data.has_more
      }
    }
  } catch (e) {
    showToast('加载失败')
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

async function loadMore() {
  currentPage.value++
  await loadData(currentPage.value)
}

function toggleSelection(item) {
  const id = getItemId(item)
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter(i => i !== id)
  } else {
    selectedIds.value.push(id)
  }
}

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

function handleImport() {
  showImportSheet.value = true
}

async function confirmImport(target) {
  showImportSheet.value = false
  const selectedItems = works.value.filter(item => 
    selectedIds.value.includes(getItemId(item))
  )
  
  try {
    if (isVideoMode.value) {
      // Temporary loop for video
      let successCount = 0
      for (const item of selectedItems) {
        const id = getItemId(item)
        await videoApi.thirdPartyImport(id, target)
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

async function toggleSubscribe() {
  // Toggle logic similar to SubscriptionList
  showToast('Toggle subscribe')
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.creator-detail-page {
  background: #fff;
  min-height: 100vh;
}

.creator-header {
  padding: 24px;
  display: flex;
  align-items: center;
  gap: 20px;
  border-bottom: 1px solid #f5f5f5;
}

.info h1 {
  font-size: 20px;
  margin: 0 0 8px 0;
}

.info p {
  color: #999;
  font-size: 14px;
}

.actions {
  margin-left: auto;
}

.works-area {
  padding: 16px;
}

.loading-center {
  padding: 40px;
  text-align: center;
}

.load-more {
  margin-top: 20px;
}

.sheet-content {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
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

@media (min-width: 768px) {
  .remote-results-grid {
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    padding: 20px;
  }
}
</style>
