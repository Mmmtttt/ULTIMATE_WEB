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
          show-action
          @search="handleSearch"
        >
          <template #action>
            <button class="search-action-btn" type="button" @click="handleSearch">搜索</button>
          </template>
        </van-search>
      </div>

      <div class="search-subtitle">仅搜索全网内容，输入关键词后点击搜索或按回车触发。</div>

      <!-- 平台选择器（多选） -->
      <div v-if="platformOptions.length > 0" class="platform-selector">
        <div
          class="platform-chip"
          :class="{ active: selectedPlatforms.length === 0 }"
          @click="handlePlatformChange('all')"
        >
          全部
        </div>
        <div
          v-for="opt in platformOptions"
          :key="opt.platform"
          class="platform-chip"
          :class="{ active: selectedPlatforms.includes(opt.platform) }"
          @click="handlePlatformChange(opt.platform)"
        >
          {{ opt.label }}
        </div>
      </div>

      <div v-if="isVideoMode" class="tag-search-entry">
        <van-button size="small" plain type="primary" icon="filter-o" @click="goToTagSearch">
          标签搜索
        </van-button>
      </div>
    </div>

    <div class="search-content">
      <van-loading v-if="loading" class="loading-center" />

      <EmptyState
        v-else-if="results.length === 0"
        :title="emptyTitle"
        :description="emptyDescription"
      />

      <div v-else class="results-container">
        <div class="remote-select-bar">
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
            <div class="card-cover" :style="getRemoteCoverStyle(item)">
              <van-image
                :src="getCoverUrl(item)"
                :fit="getCoverFit(item)"
                class="cover-image"
                lazy-load
              />
              <div v-if="shouldRenderPlatformBadge(item)" class="platform-badge">{{ getPlatformBadgeLabel(item) }}</div>
              <div v-if="item.score" class="card-score score-badge">{{ formatScore(item.score) }}</div>
              <div v-if="isSelected(item)" class="select-overlay">
                <van-icon name="success" class="select-icon" />
              </div>
              <div class="card-hover-actions">
                <div class="hover-action-btn" title="查看详情" @click.stop="goToDetail(item)">
                  <van-icon name="eye-o" />
                </div>
                <div class="hover-action-btn" title="选中" @click.stop="toggleSelection(item)">
                  <van-icon name="success" />
                </div>
              </div>
            </div>
            <div class="card-info">
              <div class="card-title">{{ item.title }}</div>
              <div v-if="item.author" class="card-author">{{ item.author }}</div>
            </div>
          </div>
        </div>

        <div v-if="selectedIds.length > 0" class="floating-import-bar">
          <span class="floating-selection-info">已选 {{ selectedIds.length }} 项</span>
          <van-button type="primary" @click="handleImport">导入选中</van-button>
        </div>

        <div v-if="hasMore" class="load-more">
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

    <van-action-sheet v-model:show="showImportSheet" title="导入位置">
      <div class="sheet-content">
        <van-button block type="primary" @click="confirmImport('home')">导入到主页</van-button>
        <van-button block type="success" @click="confirmImport('recommendation')">导入到推荐页</van-button>
      </div>
    </van-action-sheet>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useModeStore, useComicStore, useImportTaskStore, useVideoStore, useGlobalSearchStore } from '@/stores'
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

const router = useRouter()
const modeStore = useModeStore()
const comicStore = useComicStore()
const videoStore = useVideoStore()
const importTaskStore = useImportTaskStore()
const searchStore = useGlobalSearchStore()

// 持久化状态 — 来自 store，页面导航间保持
const {
  keyword,
  results,
  hasMore,
  currentPage,
  selectedIds,
  paginationInfo,
  searchExecuted,
  selectedPlatforms,
  platformOptions,
} = storeToRefs(searchStore)

// 临时 UI 状态 — 组件销毁即消失
const loading = ref(false)
const loadingMore = ref(false)
const showImportSheet = ref(false)

const isVideoMode = computed(() => modeStore.isVideoMode)

const searchPlaceholder = computed(() =>
  isVideoMode.value ? '搜索全网视频...' : '搜索全网漫画...'
)

const emptyTitle = computed(() => {
  return searchExecuted.value ? '未找到结果' : '开始全网搜索'
})

const emptyDescription = computed(() => {
  if (!searchExecuted.value) {
    return '输入关键词后点击搜索或按回车'
  }
  if (!String(keyword.value || '').trim()) {
    return '请输入关键词开始搜索'
  }
  return '尝试调整关键词后重新搜索'
})

const normalizedResults = computed(() => {
  return results.value.map((item) => {
    const normalized = { ...item }

    if (normalized.cover_url && !normalized.cover_path) {
      normalized.cover_path = normalized.cover_url
    }

    if (!normalized.id) {
      normalized.id = normalized.video_id || normalized.album_id || normalized.comic_id
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

function getCoverFit(item) {
  return resolveDisplayCoverFit(item) || 'cover'
}

function getRemoteCoverStyle(item) {
  return buildDisplayCoverStyle(item)
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

function isSelected(item) {
  const id = getItemId(item)
  return selectedIds.value.includes(id)
}

function toggleSelection(item) {
  const id = getItemId(item)
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter((itemId) => itemId !== id)
  } else {
    selectedIds.value.push(id)
  }
}

function goToDetail(item) {
  const id = getItemId(item)
  if (id) {
    const platform = resolveImportPlatform(item) || item?.platform || item?.plugin_name || ''
    if (!platform) {
      console.warn('[goToDetail] 无法解析平台信息:', item)
      return
    }
    const routeName = isVideoMode.value ? 'VideoDetail' : 'ComicDetail'
    router.push({ name: routeName, params: { id }, query: { platform } })
  }
}

function toggleSelectAllRemote() {
  toggleSelectAll(selectedIds, normalizedResults.value, (item) => getItemId(item))
}

async function goToTagSearch() {
  try {
    const platformOptions = await fetchProtocolPlatformOptions({
      mediaType: 'video',
      capability: 'taxonomy.tag_search'
    })
    const targetPlatform = platformOptions[0] || null
    if (!targetPlatform) {
      throw new Error('当前没有声明标签搜索能力的视频平台')
    }

    router.push({
      name: 'VideoTagSearch',
      query: { platform: targetPlatform.platform }
    })
  } catch (e) {
    await showConfirmDialog({
      title: '提示',
      message: e?.message || '当前没有可用的视频标签搜索平台',
      showCancelButton: false,
      confirmButtonText: '知道了'
    })
  }
}

function handleImport() {
  showImportSheet.value = true
}

function handlePlatformChange(platform) {
  if (platform === 'all') {
    // 点击"全部" → 清空选择 → 搜全部平台
    selectedPlatforms.value = []
  } else {
    // 切换单个平台选/不选
    const idx = selectedPlatforms.value.indexOf(platform)
    if (idx >= 0) {
      selectedPlatforms.value.splice(idx, 1)
    } else {
      selectedPlatforms.value.push(platform)
    }
  }
  // 若有关键词则自动重新搜索
  if (String(keyword.value || '').trim()) {
    handleSearch()
  }
}

async function confirmImport(target) {
  showImportSheet.value = false
  const selectedItems = normalizedResults.value.filter((item) =>
    selectedIds.value.includes(getItemId(item))
  )

  try {
    const itemsByPlatform = {}
    selectedItems.forEach((item) => {
      const platform = resolveImportPlatform(item)
      if (!platform) {
        return
      }
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
      throw new Error('未找到可导入的平台标识')
    }
    showToast(`已创建 ${taskCount} 个导入任务`)
    searchStore.clearSelection()
  } catch {
    showToast('导入失败')
  }
}

async function handleSearch() {
  const normalizedKeyword = String(keyword.value || '').trim()
  searchExecuted.value = true
  results.value = []
  currentPage.value = 0
  hasMore.value = false
  selectedIds.value = []
  paginationInfo.value = null

  if (!normalizedKeyword) {
    return
  }

  loading.value = true
  try {
    await searchRemote(normalizedKeyword)
  } catch {
    showToast('搜索失败')
  } finally {
    loading.value = false
  }
}

async function searchRemote(searchKeyword) {
  const platform = selectedPlatforms.value.length > 0 ? selectedPlatforms.value.join(',') : 'all'
  if (isVideoMode.value) {
    const res = await videoStore.thirdPartySearch(searchKeyword, platform, 1, 40)
    if (res.results) {
      searchStore.setSearchState({
        keyword: searchKeyword,
        results: res.results,
        currentPage: res.page,
        hasMore: res.has_more,
        paginationInfo: {
          platform: res.platform || 'all',
          page: res.page || 1,
          total_pages: res.total_pages || 1,
        },
        videoMode: true,
      })
    }
    return
  }

  const res = await comicStore.thirdPartySearch(searchKeyword, platform, 1, 40)
  if (res.results) {
    searchStore.setSearchState({
      keyword: searchKeyword,
      results: res.results,
      currentPage: res.page,
      hasMore: res.has_more,
      paginationInfo: res.platform_info || {},
      videoMode: false,
    })
  }
}

async function loadMore() {
  if (!hasMore.value) return
  loadingMore.value = true

  try {
    const normalizedKeyword = String(keyword.value || '').trim()
    if (!normalizedKeyword) {
      return
    }

    const platform = selectedPlatforms.value.length > 0 ? selectedPlatforms.value.join(',') : 'all'

    if (isVideoMode.value) {
      const nextPage = currentPage.value + 1
      const res = await videoStore.thirdPartySearch(normalizedKeyword, platform, nextPage, 40)
      if (res.results) {
        searchStore.appendResults(res.results, res.page, res.has_more, res.platform_info)
      }
      return
    }

    const nextPage = currentPage.value + 1
    const res = await comicStore.thirdPartySearch(normalizedKeyword, platform, nextPage, 40)
    if (res.results) {
      searchStore.appendResults(res.results, res.page, res.has_more, res.platform_info || {})
    }
  } finally {
    loadingMore.value = false
  }
}

/** 加载当前模式下的平台选项 */
async function loadPlatformOptions(mediaType) {
  try {
    const options = await fetchProtocolPlatformOptions({
      mediaType,
      capability: 'catalog.search',
    })
    platformOptions.value = options.map((item) => ({
      platform: item.platform,
      label: item.label,
    }))
  } catch (e) {
    console.warn('[GlobalSearch] 加载平台选项失败:', e)
  }
}

// 监听视频/漫画模式切换：模式变化时清空数据、刷新平台列表
watch(isVideoMode, async (newMode, oldMode) => {
  const modeChanged = oldMode !== undefined && newMode !== oldMode
  if (modeChanged) {
    // 模式真正切换了 → 清空结果和平台选择
    searchStore.clearResults()
    selectedPlatforms.value = []
    platformOptions.value = []
    await loadPlatformOptions(newMode ? 'video' : 'comic')
  } else if (platformOptions.value.length === 0) {
    // 首次挂载或选项已丢失时加载
    await loadPlatformOptions(newMode ? 'video' : 'comic')
  }
}, { immediate: true })

onMounted(() => {
  // onMounted 不再处理 —— watch 的 immediate: true 已覆盖
})
</script>

<style scoped>
.search-page {
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

.search-input-wrapper :deep(.van-search) {
  flex: 1;
  padding: 0;
  background: transparent;
}

.search-action-btn {
  border: 0;
  background: transparent;
  color: var(--brand-600);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.search-subtitle {
  padding: 0 14px 10px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.platform-selector {
  display: flex;
  gap: 8px;
  padding: 0 14px 10px;
  overflow-x: auto;
  flex-shrink: 0;
  scrollbar-width: none;
}

.platform-selector::-webkit-scrollbar {
  display: none;
}

.platform-chip {
  flex-shrink: 0;
  padding: 4px 14px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  background: var(--surface-3);
  border: 1px solid var(--border-soft);
  color: var(--text-secondary);
  transition: all 0.2s ease;
  white-space: nowrap;
  user-select: none;
}

.platform-chip:hover {
  border-color: var(--brand-400);
  color: var(--brand-500);
}

.platform-chip.active {
  background: var(--brand-500);
  border-color: var(--brand-500);
  color: #fff;
}

.tag-search-entry {
  display: flex;
  justify-content: flex-start;
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

.remote-results-grid.video-mode {
  align-items: start;
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

.remote-results-grid.video-mode .remote-result-card {
  align-self: start;
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
  aspect-ratio: var(--media-cover-aspect-ratio, 2 / 3);
  background: linear-gradient(145deg, rgba(70, 108, 171, 0.24) 0%, rgba(102, 138, 198, 0.2) 100%);
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

.card-hover-actions {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  gap: 16px;
  z-index: 3;
  opacity: 0;
  transition: opacity var(--motion-base) var(--ease-standard);
  pointer-events: none;
}

.remote-result-card:hover .card-hover-actions {
  opacity: 1;
  pointer-events: auto;
}

.hover-action-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition:
    transform var(--motion-fast) var(--ease-standard),
    background var(--motion-fast) var(--ease-standard);
}

.hover-action-btn:hover {
  transform: scale(1.12);
  background: rgba(0, 0, 0, 0.75);
}

.hover-action-btn .van-icon {
  font-size: 20px;
  color: #fff;
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

  .card-cover {
    aspect-ratio: var(--media-cover-aspect-ratio-mobile, var(--media-cover-aspect-ratio, 2 / 3));
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
