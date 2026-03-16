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

      <template v-else>
        <div class="remote-select-bar">
          <span class="selected-count">已选 {{ selectedIds.length }} 项</span>
          <van-button size="small" plain type="primary" @click="toggleSelectAllWorks">
            {{ isAllWorksSelected ? '取消全选' : '全选' }}
          </van-button>
        </div>

        <div class="remote-results-grid" :class="{ 'video-mode': isVideoMode }">
          <div
            v-for="item in works"
            :key="getItemId(item)"
            class="remote-result-card"
            :class="{ selected: isSelected(item) }"
            @click="toggleSelection(item)"
          >
            <div class="card-cover">
              <van-image 
                :src="getCoverUrl(item.cover_path || item.cover_url)" 
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
      </template>
      
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
import { videoApi, actorApi, authorApi } from '@/api' // Ensure authorApi is exported
import EmptyState from '@/components/common/EmptyState.vue'
import { showToast } from 'vant'
import { getCoverUrl, isAllSelected, toggleSelectAll } from '@/utils'

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
const authorSubscriptionId = ref(null)
const actorId = ref(null) // For video mode

const isAllWorksSelected = computed(() => {
  return isAllSelected(selectedIds.value, works.value, (item) => getItemId(item))
})

async function loadData(page = 1) {
  if (page === 1) loading.value = true
  else loadingMore.value = true
  
  try {
    console.log('=== CreatorDetail loadData start ===')
    console.log('isVideoMode:', isVideoMode.value)
    console.log('creatorName:', creatorName.value)
    console.log('page:', page)
    
    if (isVideoMode.value) {
      console.log('=== Video mode ===')
      
      // Video mode：如果是已订阅演员，则优先走订阅演员作品接口，支持持久化缓存
      if (page === 1) {
        console.log('=== Page 1, checking all actors ===')
        // 尝试根据名称匹配订阅记录
        const allActorsRes = await actorApi.getAll()
        console.log('allActorsRes:', allActorsRes)
        
        if (allActorsRes.code === 200 && Array.isArray(allActorsRes.data)) {
          console.log('All actors data:', allActorsRes.data)
          const match = allActorsRes.data.find(a => a.name === creatorName.value && a.is_subscribed && a.subscription)
          console.log('Match found:', match)
          
          if (match) {
            isSubscribed.value = true
            actorId.value = match.subscription.id
            console.log('Set isSubscribed=true, actorId:', actorId.value)
          } else {
            isSubscribed.value = false
            actorId.value = null
            console.log('Set isSubscribed=false, actorId=null')
          }
        }
      }

      if (isSubscribed.value && actorId.value) {
        console.log('=== Loading subscribed actor works ===')
        console.log('actorId:', actorId.value)
        // 已订阅演员：优先从后端 actor_works 持久化缓存中读取，第一页给 20 条
        const offset = (page - 1) * 20
        const res = await actorApi.getWorks(actorId.value, offset, 20)
        console.log('getWorks response:', res)
        
        if (res.code === 200) {
          const newWorks = res.data.works || []
          console.log('New works:', newWorks)
          if (page === 1) works.value = newWorks
          else works.value = [...works.value, ...newWorks]
          
          hasMore.value = !!res.data.has_more
          totalWorks.value = res.data.total || works.value.length
          console.log('Set hasMore:', hasMore.value, 'totalWorks:', totalWorks.value)
        }
      } else {
        console.log('=== Loading unsubscribed actor works by search ===')
        console.log('Searching for:', creatorName.value)
        // 非订阅演员：保持原有按名称搜索逻辑，支持缓存
        const res = await actorApi.searchWorksByName(creatorName.value, (page - 1) * 20, 20)
        console.log('searchWorksByName response:', res)
        
        if (res.code === 200) {
          const newWorks = res.data.works || []
          console.log('New works:', newWorks)
          if (page === 1) works.value = newWorks
          else works.value = [...works.value, ...newWorks]
          
          hasMore.value = res.data.has_more
          totalWorks.value = res.data.total || works.value.length
          console.log('Set hasMore:', hasMore.value, 'totalWorks:', totalWorks.value)
        }
      }
    } else {
      console.log('=== Comic mode ===')
      // Comic mode：如果是已订阅作者，则优先走订阅作者作品接口，支持持久化缓存
      if (page === 1) {
        console.log('=== Page 1, checking all authors ===')
        // 尝试根据名称匹配订阅记录
        const allAuthorsRes = await authorApi.getAllAuthors()
        console.log('allAuthorsRes:', allAuthorsRes)
        
        if (allAuthorsRes.code === 200 && Array.isArray(allAuthorsRes.data)) {
          console.log('All authors data:', allAuthorsRes.data)
          const match = allAuthorsRes.data.find(a => a.name === creatorName.value && a.is_subscribed && a.subscription)
          console.log('Match found:', match)
          
          if (match) {
            isSubscribed.value = true
            authorSubscriptionId.value = match.subscription.id
            console.log('Set isSubscribed=true, authorSubscriptionId:', authorSubscriptionId.value)
          } else {
            isSubscribed.value = false
            authorSubscriptionId.value = null
            console.log('Set isSubscribed=false, authorSubscriptionId=null')
          }
        }
      }

      if (isSubscribed.value && authorSubscriptionId.value) {
        console.log('=== Loading subscribed author works ===')
        console.log('authorSubscriptionId:', authorSubscriptionId.value)
        // 已订阅作者：优先从后端 author_works 持久化缓存中读取，第一页给 20 条
        const offset = (page - 1) * 20
        const res = await authorApi.getWorks(authorSubscriptionId.value, offset, 20)
        console.log('getWorks response:', res)
        
        if (res.code === 200) {
          const newWorks = res.data.works || []
          console.log('New works:', newWorks)
          if (page === 1) works.value = newWorks
          else works.value = [...works.value, ...newWorks]
          
          hasMore.value = !!res.data.has_more
          totalWorks.value = res.data.total || works.value.length
          console.log('Set hasMore:', hasMore.value, 'totalWorks:', totalWorks.value)
        }
      } else {
        console.log('=== Loading unsubscribed author works by search ===')
        console.log('Searching for:', creatorName.value)
        // 非订阅作者：保持原有按名称搜索逻辑
        const res = await authorApi.searchWorksByName(creatorName.value, (page - 1) * 20, 20)
        console.log('searchWorksByName response:', res)
        
        if (res.code === 200) {
          const newWorks = res.data.works || []
          console.log('New works:', newWorks)
          if (page === 1) works.value = newWorks
          else works.value = [...works.value, ...newWorks]
          
          hasMore.value = res.data.has_more
          totalWorks.value = res.data.total || works.value.length
          console.log('Set hasMore:', hasMore.value, 'totalWorks:', totalWorks.value)
        }
      }
    }
  } catch (e) {
    console.error('=== Error in loadData ===', e)
    console.error('Error stack:', e.stack)
    showToast('加载失败')
  } finally {
    console.log('=== CreatorDetail loadData end ===')
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

function toggleSelectAllWorks() {
  toggleSelectAll(selectedIds, works.value, (item) => getItemId(item))
}

function getItemId(item) {
  return item.id || item.video_id || item.album_id || item.comic_id
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
        const platform = (item.platform || 'javdb').toLowerCase()
        await videoApi.thirdPartyImport(id, target, platform)
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
  // 订阅/取消订阅逻辑，可根据当前是否已订阅调用对应接口
  showToast('订阅功能稍后完善')
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.creator-detail-page {
  background: transparent;
  min-height: 100vh;
}

.creator-header {
  padding: 24px;
  display: flex;
  align-items: center;
  gap: 20px;
  border-bottom: 1px solid var(--border-soft);
  background: var(--surface-2);
  border-radius: 16px;
  margin: 10px 10px 0;
}

.info h1 {
  font-size: 20px;
  margin: 0 0 8px 0;
}

.info p {
  color: var(--text-tertiary);
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

.remote-select-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 12px 8px;
}

.remote-select-bar .selected-count {
  font-size: 13px;
  color: var(--text-secondary);
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
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
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
  color: var(--text-primary);
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
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 10px 22px rgba(2, 8, 18, 0.34);
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
  background: linear-gradient(145deg, rgba(70, 108, 171, 0.24) 0%, rgba(102, 138, 198, 0.2) 100%);
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
  background: var(--surface-3);
  color: var(--text-primary);
  border: 1px solid var(--border-soft);
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
  background: var(--brand-500);
  border-radius: 50%;
  padding: 8px;
}

.card-info {
  padding: 10px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
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

@media (min-width: 768px) {
  .remote-results-grid {
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    padding: 20px;
  }
}
</style>
