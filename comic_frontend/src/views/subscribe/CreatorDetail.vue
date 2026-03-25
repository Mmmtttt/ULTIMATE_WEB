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
        <van-button
          v-if="!isVideoMode"
          type="primary"
          plain
          size="small"
          round
          @click="queryWorks"
        >
          查询作品
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

    <div class="floating-import-bar" v-if="selectedIds.length > 0">
      <span class="floating-selection-info">已选 {{ selectedIds.length }} 项</span>
      <van-button type="primary" @click="handleImport">导入选中</van-button>
    </div>

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
import { useRoute } from 'vue-router'
import { useModeStore, useImportTaskStore } from '@/stores'
import { actorApi, authorApi } from '@/api'
import EmptyState from '@/components/common/EmptyState.vue'
import { showToast } from 'vant'
import { getCoverUrl, isAllSelected, toggleSelectAll } from '@/utils'

const route = useRoute()
const modeStore = useModeStore()
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
const actorId = ref(null)
const hasRemoteQueried = ref(false)

const isAllWorksSelected = computed(() => {
  return isAllSelected(selectedIds.value, works.value, (item) => getItemId(item))
})

async function resolveSubscription() {
  if (isVideoMode.value) {
    const actorListRes = await actorApi.getList()
    const actorList = Array.isArray(actorListRes?.data) ? actorListRes.data : []
    const actor = actorList.find(item => item?.name === creatorName.value)
    isSubscribed.value = Boolean(actor)
    actorId.value = actor?.id || null
    return
  }

  const authorListRes = await authorApi.getList()
  const authorList = Array.isArray(authorListRes?.data) ? authorListRes.data : []
  const author = authorList.find(item => item?.name === creatorName.value)
  isSubscribed.value = Boolean(author)
  authorSubscriptionId.value = author?.id || null
}

function applyWorksPage(res, page) {
  const newWorks = res?.data?.works || []
  if (page === 1) works.value = newWorks
  else works.value = [...works.value, ...newWorks]

  hasMore.value = Boolean(res?.data?.has_more)
  totalWorks.value = res?.data?.total || works.value.length
}

async function loadData(page = 1, options = {}) {
  if (page === 1) loading.value = true
  else loadingMore.value = true

  const forceQuery = Boolean(options?.forceQuery)

  try {
    if (page === 1) {
      await resolveSubscription()
      if (!isVideoMode.value && !forceQuery) {
        hasRemoteQueried.value = false
      }
    }

    if (isVideoMode.value) {
      if (isSubscribed.value && actorId.value) {
        const offset = (page - 1) * 20
        const res = await actorApi.getWorks(actorId.value, offset, 20)
        if (res.code === 200) {
          applyWorksPage(res, page)
        }
      } else {
        const res = await actorApi.searchWorksByName(creatorName.value, (page - 1) * 20, 20)
        if (res.code === 200) {
          applyWorksPage(res, page)
        }
      }
      return
    }

    if (isSubscribed.value && authorSubscriptionId.value) {
      const offset = (page - 1) * 20
      const cacheOnly = !forceQuery && !hasRemoteQueried.value
      const forceRefresh = Boolean(forceQuery && page === 1)
      const res = await authorApi.getWorks(authorSubscriptionId.value, offset, 20, { cacheOnly, forceRefresh })
      if (res.code === 200) {
        applyWorksPage(res, page)
        if (forceQuery) {
          hasRemoteQueried.value = true
        }
      }
      return
    }

    if (!forceQuery) {
      if (page === 1) {
        works.value = []
        hasMore.value = false
        totalWorks.value = 0
      }
      return
    }

    const res = await authorApi.searchWorksByName(creatorName.value, (page - 1) * 20, 20)
    if (res.code === 200) {
      applyWorksPage(res, page)
      hasRemoteQueried.value = true
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
  await loadData(currentPage.value, {
    forceQuery: isVideoMode.value ? false : hasRemoteQueried.value
  })
}

async function queryWorks() {
  currentPage.value = 1
  selectedIds.value = []
  await loadData(1, { forceQuery: true })
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
    const itemsByPlatform = {}
    selectedItems.forEach(item => {
      const platform = item.platform || (isVideoMode.value ? 'JAVDB' : 'JM')
      if (!itemsByPlatform[platform]) {
        itemsByPlatform[platform] = []
      }
      itemsByPlatform[platform].push(getItemId(item))
    })

    let taskCount = 0
    for (const [platform, comicIds] of Object.entries(itemsByPlatform)) {
      const params = {
        import_type: 'by_list',
        target,
        platform: isVideoMode.value ? String(platform).toUpperCase() : platform,
        comic_ids: comicIds,
        content_type: isVideoMode.value ? 'video' : 'comic'
      }
      const created = await importTaskStore.createImportTask(params)
      if (created) {
        taskCount += 1
      }
    }

    if (taskCount === 0) {
      throw new Error('创建导入任务失败')
    }
    showToast(`已创建 ${taskCount} 个导入任务`)
    selectedIds.value = []
  } catch (e) {
    showToast('导入失败')
  }
}

async function toggleSubscribe() {
  showToast('订阅功能稍后完善')
}

onMounted(() => {
  loadData(1, { forceQuery: false })
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
  display: flex;
  align-items: center;
  gap: 8px;
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

.remote-results-grid.video-mode {
  align-items: start;
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

.remote-results-grid.video-mode .remote-result-card {
  align-self: start;
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

@media (max-width: 767px) {
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
}
</style>
