<template>
  <div class="creator-detail-page">
    <van-nav-bar :title="creatorName" left-text="返回" left-arrow @click-left="$router.back()">
      <template #right>
        <van-button size="small" type="primary" :disabled="selectedIds.length === 0" @click="handleImport">
          导入选中
        </van-button>
      </template>
    </van-nav-bar>

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

      <MediaGrid 
        v-else 
        :items="works" 
        :selectable="true"
        :selected-ids="selectedIds"
        @select="toggleSelection"
        @click="toggleSelection"
        :class="{ 'video-mode': isVideoMode }"
      />
      
      <div v-if="hasMore" class="load-more">
        <van-button block plain :loading="loadingMore" @click="loadMore">
          加载更多
        </van-button>
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
  const id = isVideoMode.value ? item.video_id : item.id
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
  const selectedItems = works.value.filter(item => 
    selectedIds.value.includes(isVideoMode.value ? item.video_id : item.id)
  )
  
  try {
    if (isVideoMode.value) {
      // Temporary loop for video
      let successCount = 0
      for (const item of selectedItems) {
        const id = item.video_id
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
        itemsByPlatform[platform].push(item.id)
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

.video-mode :deep(.media-cover) {
  aspect-ratio: 16/9;
}
</style>
