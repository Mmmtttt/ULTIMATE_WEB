<template>
  <div class="tag-search-page">
    <div class="page-header">
      <van-icon name="arrow-left" class="back-icon" @click="$router.back()" />
      <div class="header-copy">
        <div class="header-title">{{ currentPlatformLabel }} 标签搜索</div>
        <div class="header-subtitle">多选平台内置标签后搜索并导入</div>
      </div>
    </div>

    <div v-if="!isVideoMode" class="mode-empty">
      <EmptyState title="仅视频模式可用" description="请先切换到视频模式" />
      <van-button type="primary" class="mode-switch-btn" @click="switchToVideoMode">
        切换到视频模式
      </van-button>
    </div>

    <template v-else>
      <van-loading v-if="!platformsLoaded || !platformStatusChecked" class="loading-center" />

      <div v-else-if="availablePlatforms.length === 0" class="mode-empty">
        <EmptyState
          title="暂无可用平台"
          description="当前没有声明标签搜索能力的视频插件"
        />
      </div>

      <div v-else-if="!platformConfigured" class="mode-empty">
        <EmptyState
          title="未完成平台配置"
          :description="platformConfigMessage"
        />
      </div>

      <template v-else>
        <div v-if="availablePlatforms.length > 1" class="platform-switch">
          <button
            v-for="platform in availablePlatforms"
            :key="platform.platform"
            type="button"
            class="platform-pill"
            :class="{ active: selectedPlatform === platform.platform }"
            @click="selectPlatform(platform.platform)"
          >
            {{ platform.label }}
          </button>
        </div>

        <div class="filters-card">
        <div class="filter-actions">
          <span class="selected-summary">已选 {{ selectedTagIds.length }} 个标签</span>
          <div class="filter-action-btns">
            <van-button
              size="small"
              plain
              :disabled="selectedTagIds.length === 0"
              @click="clearSelectedTags"
            >
              清空
            </van-button>
            <van-button
              size="small"
              type="primary"
              :disabled="selectedTagIds.length === 0 || loadingTags"
              :loading="loading"
              @click="handleSearch"
            >
              搜索
            </van-button>
          </div>
        </div>

        <div v-if="selectedTags.length > 0" class="selected-tags">
          <van-tag
            v-for="tag in selectedTags"
            :key="tag.id"
            closeable
            type="primary"
            @close="removeSelectedTag(tag.id)"
          >
            {{ tag.name }}
          </van-tag>
        </div>

        <van-loading v-if="loadingTags" class="loading-center" />

        <template v-else>
          <van-tabs v-model:active="activeCategory" shrink>
            <van-tab
              v-for="category in categoryTabs"
              :key="category.key"
              :title="`${category.name} (${category.count})`"
              :name="category.key"
            />
          </van-tabs>

          <div class="tag-grid">
            <button
              v-for="tag in filteredTags"
              :key="tag.id"
              type="button"
              class="tag-pill"
              :class="{ selected: selectedTagIds.includes(tag.id) }"
              @click="toggleTag(tag.id)"
            >
              {{ tag.name }}
            </button>
          </div>
        </template>
      </div>

        <div class="results-card">
        <div class="results-header">
          <span class="results-title">搜索结果</span>
          <span v-if="searchExecuted" class="results-count">{{ normalizedResults.length }} 项</span>
        </div>

        <van-loading v-if="loading" class="loading-center" />

        <EmptyState
          v-else-if="searchExecuted && normalizedResults.length === 0"
          title="未找到结果"
          description="尝试调整标签组合后重新搜索"
        />

        <EmptyState
          v-else-if="!searchExecuted"
          title="先选标签再搜索"
          :description="`标签来源于 ${currentPlatformLabel} 内置标签能力`"
        />

        <div v-else class="results-container">
          <div class="remote-select-bar">
            <span class="selected-count">已选 {{ selectedResultIds.length }} 项</span>
            <van-button size="small" plain type="primary" @click="toggleSelectAllResults">
              {{ isAllResultsSelected ? '取消全选' : '全选' }}
            </van-button>
          </div>

          <div class="remote-results-grid video-mode">
            <div
              v-for="item in normalizedResults"
              :key="getItemId(item)"
              class="remote-result-card"
              :class="{ selected: isResultSelected(item) }"
              @click="toggleResultSelection(item)"
            >
              <div
                class="card-cover"
                :style="getCardCoverStyle(item)"
              >
                <van-image
                  :src="getCoverUrl(item)"
                  :fit="getCardCoverFit(item)"
                  class="cover-image"
                  lazy-load
                />
                <div v-if="shouldRenderPlatformBadge(item)" class="platform-badge">{{ getPlatformBadgeLabel(item) }}</div>
                <div v-if="item.score" class="card-score score-badge">{{ formatScore(item.score) }}</div>
                <div v-if="isResultSelected(item)" class="select-overlay">
                  <van-icon name="success" class="select-icon" />
                </div>
              </div>
              <div class="card-info">
                <div class="card-title">{{ item.title }}</div>
                <div v-if="item.code" class="card-code">{{ item.code }}</div>
              </div>
            </div>
          </div>

          <div v-if="hasMore" class="load-more">
            <div v-if="paginationInfo" class="pagination-info">
              <span class="page-info">第 {{ paginationInfo.page }} 页</span>
            </div>
            <van-button block plain :loading="loadingMore" @click="loadMore">
              加载更多
            </van-button>
          </div>
        </div>
        </div>
      </template>
    </template>

    <div v-if="selectedResultIds.length > 0 && isVideoMode" class="floating-import-bar">
      <span class="floating-selection-info">已选 {{ selectedResultIds.length }} 项</span>
      <van-button type="primary" @click="showImportSheet = true">导入选中</van-button>
    </div>

    <van-action-sheet v-model:show="showImportSheet" title="导入位置">
      <div class="sheet-content">
        <van-button block type="primary" @click="confirmImport('home')">导入到本地库</van-button>
        <van-button block type="success" @click="confirmImport('recommendation')">导入到预览库</van-button>
      </div>
    </van-action-sheet>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useModeStore, useImportTaskStore } from '@/stores'
import { videoApi } from '@/api'
import EmptyState from '@/components/common/EmptyState.vue'
import { showConfirmDialog, showToast } from 'vant'
import {
  buildDisplayCoverStyle,
  fetchProtocolPlatformOptions,
  getCoverUrl,
  isAllSelected,
  resolveDisplayCoverFit,
  resolveImportPlatform,
  resolvePlatformBadgeLabel,
  shouldShowPlatformBadge,
  toggleSelectAll,
} from '@/utils'

const route = useRoute()
const router = useRouter()
const modeStore = useModeStore()
const importTaskStore = useImportTaskStore()

const isVideoMode = computed(() => modeStore.isVideoMode)

const loadingTags = ref(false)
const loading = ref(false)
const loadingMore = ref(false)
const searchExecuted = ref(false)
const platformsLoaded = ref(false)
const platformConfigured = ref(false)
const platformStatusChecked = ref(false)
const platformStatusMessage = ref('')
const availablePlatforms = ref([])
const selectedPlatform = ref('')

const allTags = ref([])
const categories = ref([])
const activeCategory = ref('all')
const selectedTagIds = ref([])

const results = ref([])
const selectedResultIds = ref([])
const hasMore = ref(false)
const paginationInfo = ref(null)

const showImportSheet = ref(false)

const currentPlatformOption = computed(() => {
  return availablePlatforms.value.find(item => item.platform === selectedPlatform.value) || availablePlatforms.value[0] || null
})

const currentPlatformLabel = computed(() => currentPlatformOption.value?.label || '平台')
const platformConfigMessage = computed(() => {
  return platformStatusMessage.value || `请先在系统配置中完成 ${currentPlatformLabel.value} 所需配置后再使用标签搜索`
})

const categoryTabs = computed(() => {
  return [
    { key: 'all', name: '全部', count: allTags.value.length },
    ...categories.value
  ]
})

const filteredTags = computed(() => {
  if (activeCategory.value === 'all') {
    return allTags.value
  }
  return allTags.value.filter(tag => tag.category === activeCategory.value)
})

const selectedTags = computed(() => {
  return selectedTagIds.value
    .map(tagId => allTags.value.find(tag => tag.id === tagId))
    .filter(Boolean)
})

const normalizedResults = computed(() => {
  return results.value.map(item => {
    return {
      ...item,
      id: item.id || item.video_id,
      cover_path: item.cover_path || item.cover_url,
      platform: item.platform || selectedPlatform.value || ''
    }
  })
})

const isAllResultsSelected = computed(() => {
  return isAllSelected(selectedResultIds.value, normalizedResults.value, item => getItemId(item))
})

function resetPlatformData() {
  allTags.value = []
  categories.value = []
  activeCategory.value = 'all'
  selectedTagIds.value = []
  results.value = []
  selectedResultIds.value = []
  hasMore.value = false
  paginationInfo.value = null
  searchExecuted.value = false
}

async function syncSelectedPlatformToRoute() {
  const nextPlatform = String(selectedPlatform.value || '').trim().toLowerCase()
  const currentPlatform = String(route.query.platform || '').trim().toLowerCase()
  if (!nextPlatform || nextPlatform === currentPlatform) {
    return
  }
  await router.replace({
    path: route.path,
    query: {
      ...route.query,
      platform: nextPlatform
    }
  })
}

async function ensurePlatformConfigured(showDialog = false) {
  const platform = String(selectedPlatform.value || '').trim().toLowerCase()
  if (!platform) {
    platformConfigured.value = false
    platformStatusChecked.value = true
    platformStatusMessage.value = '当前没有可用的平台'
    resetPlatformData()
    return false
  }

  try {
    const res = await videoApi.thirdPartyPlatformHealthStatus(platform)
    const configured = Boolean(res?.code === 200 && res?.data?.configured)
    platformConfigured.value = configured
    platformStatusChecked.value = true
    platformStatusMessage.value = String(res?.data?.message || '').trim()

    if (!configured) {
      resetPlatformData()
      if (showDialog) {
        await showConfirmDialog({
          title: '提示',
          message: platformConfigMessage.value,
          showCancelButton: false,
          confirmButtonText: '知道了'
        })
      }
    }

    return configured
  } catch (e) {
    platformConfigured.value = false
    platformStatusChecked.value = true
    platformStatusMessage.value = String(e?.message || '').trim()
    resetPlatformData()

    if (showDialog) {
      await showConfirmDialog({
        title: '提示',
        message: platformConfigMessage.value,
        showCancelButton: false,
        confirmButtonText: '知道了'
      })
    }
    return false
  }
}

async function switchToVideoMode() {
  modeStore.setMode('video')
  await loadAvailablePlatforms()
}

function toggleTag(tagId) {
  if (selectedTagIds.value.includes(tagId)) {
    selectedTagIds.value = selectedTagIds.value.filter(id => id !== tagId)
  } else {
    selectedTagIds.value.push(tagId)
  }
}

function clearSelectedTags() {
  selectedTagIds.value = []
}

function removeSelectedTag(tagId) {
  selectedTagIds.value = selectedTagIds.value.filter(id => id !== tagId)
}

function getItemId(item) {
  return item.id || item.video_id
}

function getCardCoverFit(item) {
  return resolveDisplayCoverFit(item) || 'cover'
}

function getCardCoverStyle(item) {
  return buildDisplayCoverStyle(item, '16 / 9', '3 / 2')
}

function shouldRenderPlatformBadge(item) {
  return shouldShowPlatformBadge(item)
}

function getPlatformBadgeLabel(item) {
  return resolvePlatformBadgeLabel(item)
}

function formatScore(score) {
  const value = Number(score)
  if (!Number.isFinite(value)) {
    return score
  }
  return value % 1 === 0 ? value.toFixed(0) : value.toFixed(1)
}

function isResultSelected(item) {
  return selectedResultIds.value.includes(getItemId(item))
}

function toggleResultSelection(item) {
  const id = getItemId(item)
  if (!id) return

  if (selectedResultIds.value.includes(id)) {
    selectedResultIds.value = selectedResultIds.value.filter(itemId => itemId !== id)
  } else {
    selectedResultIds.value.push(id)
  }
}

function toggleSelectAllResults() {
  toggleSelectAll(selectedResultIds, normalizedResults.value, item => getItemId(item))
}

async function activateSelectedPlatform() {
  platformStatusChecked.value = false
  platformConfigured.value = false
  platformStatusMessage.value = ''
  resetPlatformData()
  await syncSelectedPlatformToRoute()
  const configured = await ensurePlatformConfigured()
  if (!configured) return
  await loadTags()
}

async function loadAvailablePlatforms() {
  platformsLoaded.value = false
  try {
    const options = await fetchProtocolPlatformOptions({
      mediaType: 'video',
      capability: 'taxonomy.tag_search'
    })
    availablePlatforms.value = options

    const requestedPlatform = String(route.query.platform || '').trim().toLowerCase()
    const resolvedPlatform = options.some(item => item.platform === requestedPlatform)
      ? requestedPlatform
      : (options[0]?.platform || '')

    selectedPlatform.value = resolvedPlatform
    platformsLoaded.value = true
    await activateSelectedPlatform()
  } catch (error) {
    availablePlatforms.value = []
    selectedPlatform.value = ''
    platformConfigured.value = false
    platformStatusChecked.value = true
    platformStatusMessage.value = String(error?.message || '加载平台失败').trim()
    resetPlatformData()
    platformsLoaded.value = true
  }
}

async function selectPlatform(platform) {
  const normalizedPlatform = String(platform || '').trim().toLowerCase()
  if (!normalizedPlatform || normalizedPlatform === selectedPlatform.value) {
    return
  }
  selectedPlatform.value = normalizedPlatform
  await activateSelectedPlatform()
}

async function loadTags() {
  if (!isVideoMode.value || !platformConfigured.value || !platformStatusChecked.value) return

  loadingTags.value = true
  try {
    const res = await videoApi.thirdPartyPlatformTags(selectedPlatform.value)
    if (res.code === 200 && res.data) {
      if (res.data.cookie_configured === false) {
        platformConfigured.value = false
        platformStatusMessage.value = String(res.data.message || '').trim()
        resetPlatformData()
        return
      }

      if (res.data.source_ready === false) {
        showToast(res.data.message || `${currentPlatformLabel.value} 内置标签库未初始化`)
      }
      if (res.data.tag_search_available === false) {
        showToast(`${currentPlatformLabel.value} 标签搜索暂不可用，请检查平台配置`)
      }

      allTags.value = res.data.tags || []
      categories.value = res.data.categories || []

      if (categories.value.length > 0) {
        activeCategory.value = categories.value[0].key
      } else {
        activeCategory.value = 'all'
      }
    } else {
      allTags.value = []
      categories.value = []
      activeCategory.value = 'all'
    }
  } catch (e) {
    allTags.value = []
    categories.value = []
    activeCategory.value = 'all'
    showToast(e?.message || '获取标签失败')
  } finally {
    loadingTags.value = false
  }
}

async function handleSearch() {
  if (!platformConfigured.value) {
    await ensurePlatformConfigured(true)
    return
  }

  if (selectedTagIds.value.length === 0) {
    showToast('请先选择至少一个标签')
    return
  }

  loading.value = true
  searchExecuted.value = true
  results.value = []
  selectedResultIds.value = []
  hasMore.value = false
  paginationInfo.value = null

  try {
    const res = await videoApi.thirdPartyPlatformSearchByTags(selectedPlatform.value, selectedTagIds.value, 1)
    if (res.code === 200 && res.data) {
      results.value = res.data.videos || []
      paginationInfo.value = {
        page: res.data.page || 1
      }
      hasMore.value = Boolean(res.data.has_next)
    } else {
      results.value = []
      hasMore.value = false
      paginationInfo.value = null
    }
  } catch (e) {
    results.value = []
    hasMore.value = false
    paginationInfo.value = null
    showToast(e?.message || '标签搜索失败')
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (!hasMore.value || loadingMore.value) return

  loadingMore.value = true
  try {
    const nextPage = (paginationInfo.value?.page || 1) + 1
    const res = await videoApi.thirdPartyPlatformSearchByTags(selectedPlatform.value, selectedTagIds.value, nextPage)
    if (res.code === 200 && res.data) {
      results.value = [...results.value, ...(res.data.videos || [])]
      paginationInfo.value = {
        page: res.data.page || nextPage
      }
      hasMore.value = Boolean(res.data.has_next)
    }
  } catch (e) {
    showToast(e?.message || '加载更多失败')
  } finally {
    loadingMore.value = false
  }
}

async function confirmImport(target) {
  showImportSheet.value = false

  const selectedItems = normalizedResults.value.filter(item => {
    return selectedResultIds.value.includes(getItemId(item))
  })

  if (selectedItems.length === 0) {
    showToast('请先选择要导入的内容')
    return
  }

  const itemsByPlatform = {}
  selectedItems.forEach(item => {
    const platform = String(resolveImportPlatform(item) || selectedPlatform.value || '').trim().toUpperCase()
    const videoId = getItemId(item)
    if (!videoId) return
    if (!itemsByPlatform[platform]) {
      itemsByPlatform[platform] = []
    }
    itemsByPlatform[platform].push(videoId)
  })

  let taskCount = 0
  for (const [platform, videoIds] of Object.entries(itemsByPlatform)) {
    const created = await importTaskStore.createImportTask({
      import_type: 'by_list',
      target,
      platform,
      comic_ids: videoIds,
      content_type: 'video'
    })
    if (created) {
      taskCount += 1
    }
  }

  if (taskCount === 0) {
    showToast('导入失败')
    return
  }

  showToast(`已创建 ${taskCount} 个导入任务`)
  selectedResultIds.value = []
}

onMounted(async () => {
  await loadAvailablePlatforms()
})
</script>

<style scoped>
.tag-search-page {
  min-height: 100vh;
  padding: 12px 10px 90px;
  color: var(--text-primary);
}

.page-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  padding: 6px 4px;
}

.back-icon {
  font-size: 20px;
  padding: 8px;
  color: var(--text-primary);
}

.header-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.header-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-strong);
}

.header-subtitle {
  font-size: 12px;
  color: var(--text-secondary);
}

.mode-empty {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mode-switch-btn {
  width: 100%;
}

.platform-switch {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.platform-pill {
  border: 1px solid var(--border-soft);
  border-radius: 999px;
  background: var(--surface-2);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.3;
  padding: 8px 12px;
  cursor: pointer;
  transition: all 0.16s ease;
}

.platform-pill.active {
  border-color: rgba(47, 116, 255, 0.5);
  background: rgba(89, 160, 255, 0.18);
  color: var(--brand-700);
  font-weight: 600;
}

.filters-card,
.results-card {
  border: 1px solid var(--border-soft);
  border-radius: 16px;
  background: var(--surface-2);
  backdrop-filter: blur(10px);
  box-shadow: 0 10px 22px rgba(17, 27, 45, 0.08);
}

.filters-card {
  padding: 10px 10px 12px;
  margin-bottom: 12px;
}

.filter-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.selected-summary {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.filter-action-btns {
  display: flex;
  align-items: center;
  gap: 8px;
}

.selected-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.tag-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 8px;
  max-height: 44vh;
  overflow-y: auto;
  padding-top: 10px;
}

.tag-pill {
  border: 1px solid var(--border-soft);
  border-radius: 999px;
  background: var(--surface-3);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.3;
  padding: 8px 10px;
  text-align: center;
  cursor: pointer;
  transition: all 0.16s ease;
}

.tag-pill.selected {
  border-color: rgba(47, 116, 255, 0.5);
  background: rgba(89, 160, 255, 0.18);
  color: var(--brand-700);
  font-weight: 600;
}

.results-card {
  padding: 10px 10px 14px;
}

.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.results-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-strong);
}

.results-count {
  font-size: 12px;
  color: var(--text-secondary);
}

.loading-center {
  text-align: center;
  padding: 26px 0;
}

.remote-select-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 2px 8px;
}

.selected-count {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 600;
}

.remote-results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
}

.remote-results-grid.video-mode {
  align-items: start;
}

.remote-result-card {
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  overflow: hidden;
  background: var(--surface-2);
  transition: all 0.16s ease;
}

.remote-results-grid.video-mode .remote-result-card {
  align-self: start;
}

.remote-result-card.selected {
  border-color: rgba(47, 116, 255, 0.52);
  box-shadow: 0 10px 24px rgba(47, 116, 255, 0.2);
}

.card-cover {
  position: relative;
  aspect-ratio: var(--media-cover-aspect-ratio, 2 / 3);
}

.cover-image {
  width: 100%;
  height: 100%;
  display: block;
}

.platform-badge {
  position: absolute;
  left: 8px;
  top: 8px;
  background: var(--surface-3);
  color: var(--text-primary);
  border: 1px solid var(--border-soft);
  border-radius: 999px;
  font-size: 11px;
  padding: 2px 8px;
}

.score-badge {
  position: absolute;
  right: 8px;
  top: 8px;
  background: var(--surface-3);
  color: var(--text-primary);
  border: 1px solid var(--border-soft);
  border-radius: 999px;
  font-size: 11px;
  padding: 2px 7px;
}

.select-overlay {
  position: absolute;
  inset: 0;
  background: rgba(47, 116, 255, 0.22);
  display: flex;
  justify-content: center;
  align-items: center;
}

.select-icon {
  color: #fff;
  font-size: 24px;
}

.card-info {
  padding: 8px 8px 9px;
}

.card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-strong);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 36px;
}

.card-code {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.load-more {
  padding-top: 12px;
}

.pagination-info {
  display: flex;
  justify-content: center;
  margin-bottom: 8px;
}

.page-info {
  font-size: 12px;
  color: var(--text-secondary);
}

.floating-import-bar {
  position: fixed;
  left: 12px;
  right: 12px;
  bottom: 14px;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  background: var(--surface-2);
  backdrop-filter: blur(10px);
  box-shadow: 0 12px 24px rgba(17, 27, 45, 0.16);
  padding: 10px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 120;
}

.floating-selection-info {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 600;
}

.sheet-content {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

@media (max-width: 767px) {
  .tag-search-page {
    padding: 10px 8px 102px;
  }

  .tag-grid {
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    max-height: 46vh;
  }

  .remote-results-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .card-cover {
    aspect-ratio: var(--media-cover-aspect-ratio-mobile, var(--media-cover-aspect-ratio, 2 / 3));
  }

  .remote-results-grid.video-mode .card-title {
    font-size: 12px;
    min-height: 32px;
  }

  .remote-results-grid.video-mode .card-code {
    font-size: 11px;
  }
}

@media (min-width: 1024px) {
  .tag-search-page {
    max-width: 1120px;
    margin: 0 auto;
    padding-bottom: 88px;
  }

  .floating-import-bar {
    left: calc(var(--sidebar-width) + 20px);
    right: 20px;
    bottom: 18px;
  }
}
</style>
