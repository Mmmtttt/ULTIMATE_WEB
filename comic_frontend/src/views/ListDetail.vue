<template>
  <div class="list-detail">
    <van-nav-bar
      :title="listInfo?.name || '清单详情'"
      left-text="返回"
      left-arrow
      @click-left="$router.back()"
    >
      <template #right v-if="listInfo">
        <div class="nav-right">
          <van-button
            size="mini"
            plain
            type="primary"
            class="manage-btn"
            @click="toggleManageMode"
          >
            {{ manageMode ? '完成' : '管理' }}
          </van-button>
          <van-icon
            v-if="!listInfo?.is_default && !manageMode"
            name="delete-o"
            size="18"
            @click="confirmDelete"
          />
        </div>
      </template>
    </van-nav-bar>
    
    <van-loading v-if="loading" class="loading-center" />
    
    <template v-else-if="listInfo">
      <div class="list-header">
        <p class="list-desc">{{ listInfo.desc || '暂无描述' }}</p>
        <div class="list-stats">
          <span class="tab-count">
            {{ listInfo.content_type === 'comic' ? '漫画' : '视频' }}: ({{ (listInfo.content_type === 'comic' ? (listInfo.comics || []).length : (listInfo.videos || []).length) }})
          </span>
        </div>
      </div>
      
      <div class="action-bar">
        <van-button 
          size="small" 
          type="primary" 
          plain 
          @click="showSortPanel = true"
          class="action-btn"
        >
          排序
          <van-icon name="sort" />
        </van-button>
        <van-button 
          size="small" 
          type="primary" 
          plain 
          @click="showFilterPanel = true"
          class="action-btn"
        >
          筛选
          <van-icon name="filter-o" />
        </van-button>
        <van-button 
          v-if="listInfo.content_type === 'comic'"
          size="small" 
          type="primary" 
          plain 
          @click="handleBatchDownload"
          :loading="downloadLoading"
          :disabled="filteredComics.length === 0 || manageMode"
          class="action-btn"
        >
          批量下载
          <van-icon name="down" />
        </van-button>
      </div>

      <div v-if="manageMode" class="manage-action-bar">
        <div class="manage-summary">已选 {{ selectedCount }} 项</div>
        <div class="manage-actions">
          <van-button size="small" plain type="primary" @click="toggleSelectAllItems">
            {{ allCurrentSelected ? '取消全选' : '全选' }}
          </van-button>
          <van-button
            size="small"
            type="primary"
            plain
            :disabled="selectedCount === 0"
            :loading="downloadLoading"
            @click="handleManageBatchDownload"
          >
            下载
          </van-button>
          <van-button
            size="small"
            type="warning"
            plain
            :disabled="selectedCount === 0 || !canMoveToLocal"
            :loading="moveToLocalLoading"
            @click="handleBatchMoveToLocal"
          >
            移动到本地
          </van-button>
          <van-button
            size="small"
            type="danger"
            plain
            :disabled="selectedCount === 0"
            :loading="batchRemoveLoading"
            @click="handleBatchRemoveFromList"
          >
            删除
          </van-button>
        </div>
      </div>
      
      <div v-if="hasActiveFilter" class="active-filter-bar">
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
          v-if="minScore !== null && minScore > 0" 
          type="primary" 
          closeable 
          @close="clearScoreFilter"
          class="filter-tag"
        >
          评分 ≥ {{ minScore }}
        </van-tag>
        <van-tag 
          v-for="tag in selectedIncludeTags" 
          :key="tag.id" 
          type="success" 
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
        <van-tag
          v-for="author in selectedAuthorsDisplay"
          :key="`author-${author}`"
          type="success"
          closeable
          @close="removeAuthor(author)"
          class="filter-tag"
        >
          作者: {{ author }}
        </van-tag>
        <van-tag
          v-for="list in selectedLists"
          :key="`list-${list.id}`"
          type="warning"
          closeable
          @close="removeList(list.id)"
          class="filter-tag"
        >
          清单: {{ list.name }}
        </van-tag>
        <van-tag
          v-if="activeContentType === 'comic' && unreadOnly"
          type="danger"
          closeable
          @close="removeUnreadOnly"
          class="filter-tag"
        >
          仅未读
        </van-tag>
        <van-button size="mini" plain @click="clearAllFilters">清空</van-button>
      </div>
      
      <van-empty v-if="listInfo.content_type === 'comic' && filteredComics.length === 0" description="没有匹配的漫画" />
      <van-empty v-else-if="listInfo.content_type === 'video' && filteredVideos.length === 0" description="没有匹配的视频" />
      
      <div v-else-if="listInfo.content_type === 'comic'" class="comic-grid">
        <div
          v-for="comic in filteredComics"
          :key="comic.id"
          class="comic-card"
          :class="{ selected: isItemSelected(comic) }"
          @click="handleComicCardClick(comic)"
        >
          <van-checkbox
            v-if="manageMode"
            :model-value="isItemSelected(comic)"
            class="select-check"
            @click.stop="toggleItemSelection(comic)"
          />
          <img :src="getCoverUrl(comic.cover_path)" class="comic-cover" alt="" />
          <div class="comic-info">
            <p class="comic-title">{{ comic.title }}</p>
            <div class="comic-meta">
              <span v-if="comic.score" class="comic-score">{{ comic.score }}分</span>
              <span class="comic-pages">{{ comic.current_page }}/{{ comic.total_page }}</span>
            </div>
          </div>
          <van-tag
            v-if="comic.source === 'preview'"
            type="primary"
            size="small"
            class="source-tag"
          >预览</van-tag>
          <van-icon
            v-if="!listInfo.is_default && !manageMode"
            name="cross"
            class="remove-btn"
            @click.stop="removeComic(comic.id, comic.source)"
          />
        </div>
      </div>
      
      <div v-else class="video-grid">
        <div
          v-for="video in filteredVideos"
          :key="video.id"
          class="video-card"
          :class="{ selected: isItemSelected(video) }"
          @click="handleVideoCardClick(video)"
        >
          <van-checkbox
            v-if="manageMode"
            :model-value="isItemSelected(video)"
            class="select-check"
            @click.stop="toggleItemSelection(video)"
          />
          <img :src="getCoverUrl(video)" class="video-cover" alt="" />
          <div class="video-info">
            <p class="video-title">{{ video.title }}</p>
            <div class="video-meta">
              <span v-if="video.score" class="video-score">{{ video.score }}分</span>
              <span v-if="video.code" class="video-code">{{ video.code }}</span>
            </div>
          </div>
          <van-tag
            v-if="video.source === 'preview'"
            type="primary"
            size="small"
            class="source-tag"
          >预览</van-tag>
          <van-icon
            v-if="!listInfo.is_default && !manageMode"
            name="cross"
            class="remove-btn"
            @click.stop="removeVideo(video.id, video.source)"
          />
        </div>
      </div>
    </template>
    
    <van-popup 
      v-model:show="showSortPanel" 
      position="bottom" 
      round 
      :style="{ height: '40%' }"
    >
      <div class="sort-panel">
        <van-nav-bar title="排序方式" left-text="关闭" @click-left="showSortPanel = false" />
        <van-cell-group>
          <van-cell 
            title="按添加时间" 
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
    
    <van-popup 
      v-model:show="showFilterPanel" 
      position="bottom" 
      round 
      :style="{ height: '70%' }"
    >
      <div class="filter-panel">
        <van-nav-bar title="筛选" left-text="关闭" @click-left="showFilterPanel = false">
          <template #right>
            <van-button type="primary" size="small" @click="applyFilterAndClose">确定</van-button>
          </template>
        </van-nav-bar>

        <AdvancedFilter
          v-model:include-tags="tempIncludeTags"
          v-model:exclude-tags="tempExcludeTags"
          v-model:selected-authors="tempSelectedAuthors"
          v-model:selected-list-ids="tempSelectedListIds"
          v-model:min-score="tempMinScore"
          v-model:unread-only="tempUnreadOnly"
          :tags="allTags"
          :authors="availableAuthors"
          :lists="availableLists"
          :is-video-mode="activeContentType === 'video'"
        />
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useListStore, useTagStore } from '@/stores'
import { buildCoverUrl } from '@/api/image'
import { comicApi } from '@/api/comic'
import { recommendationApi, videoApi } from '@/api'
import { showConfirmDialog, showSuccessToast, showFailToast } from 'vant'
import AdvancedFilter from '@/components/filter/AdvancedFilter.vue'
import { StorageArea, getRawItem, setRawItem } from '@/runtime/storage'
import { extractAuthors, extractItemAuthors, isReadByProgress, isUnreadByProgress } from '@/utils'

const route = useRoute()
const router = useRouter()
const listStore = useListStore()
const tagStore = useTagStore()

const loading = ref(false)
const listInfo = ref(null)
const listId = computed(() => route.params.id)
const activeContentType = computed(() => listInfo.value?.content_type || 'comic')

const showSortPanel = ref(false)
const showFilterPanel = ref(false)
const currentSortType = ref('')
const minScore = ref(null)
const includeTags = ref([])
const excludeTags = ref([])
const selectedAuthors = ref([])
const selectedListIds = ref([])
const unreadOnly = ref(false)

const tempMinScore = ref(0)
const tempIncludeTags = ref([])
const tempExcludeTags = ref([])
const tempSelectedAuthors = ref([])
const tempSelectedListIds = ref([])
const tempUnreadOnly = ref(false)
const downloadLoading = ref(false)
const manageMode = ref(false)
const selectedItemKeys = ref([])
const batchRemoveLoading = ref(false)
const moveToLocalLoading = ref(false)

function getFilterStorageKey() {
  return `list_detail_filters_${listId.value}`
}

function saveFilterState() {
  const payload = {
    currentSortType: currentSortType.value,
    minScore: minScore.value,
    includeTags: includeTags.value,
    excludeTags: excludeTags.value,
    selectedAuthors: selectedAuthors.value,
    selectedListIds: selectedListIds.value,
    unreadOnly: unreadOnly.value
  }
  setRawItem(getFilterStorageKey(), JSON.stringify(payload), StorageArea.SESSION)
}

function restoreFilterState() {
  const raw = getRawItem(getFilterStorageKey(), StorageArea.SESSION)
  if (!raw) {
    return
  }
  try {
    const parsed = JSON.parse(raw)
    currentSortType.value = parsed.currentSortType || ''
    minScore.value = parsed.minScore ?? null
    includeTags.value = parsed.includeTags || []
    excludeTags.value = parsed.excludeTags || []
    selectedAuthors.value = parsed.selectedAuthors || []
    selectedListIds.value = parsed.selectedListIds || []
    unreadOnly.value = Boolean(parsed.unreadOnly)
    tempMinScore.value = minScore.value || 0
    tempIncludeTags.value = [...includeTags.value]
    tempExcludeTags.value = [...excludeTags.value]
    tempSelectedAuthors.value = [...selectedAuthors.value]
    tempSelectedListIds.value = [...selectedListIds.value]
    tempUnreadOnly.value = unreadOnly.value
  } catch {
  }
}

const comics = computed(() => listInfo.value?.comics || [])
const videos = computed(() => listInfo.value?.videos || [])
const allTags = computed(() => {
  if (activeContentType.value === 'video') {
    return tagStore.videoTags
  }
  return tagStore.tags
})
const currentItems = computed(() => activeContentType.value === 'video' ? videos.value : comics.value)
const availableAuthors = computed(() => extractAuthors(currentItems.value))
const availableLists = computed(() => {
  return listStore.lists
    .filter(list => list.content_type === activeContentType.value)
    .map(list => ({
      ...list,
      item_count: list.item_ids?.length || 0
    }))
})

function getItemSelectionKey(item) {
  if (!item?.id) {
    return ''
  }
  return `${item.source || 'local'}:${item.id}`
}

function normalizeSelectedItemKeys(keys) {
  const validKeys = new Set(currentItems.value.map(getItemSelectionKey))
  return [...new Set((keys || []).filter(key => key && validKeys.has(key)))]
}

const selectedItems = computed(() => {
  const keySet = new Set(selectedItemKeys.value)
  return currentItems.value.filter(item => keySet.has(getItemSelectionKey(item)))
})

const sortLabel = computed(() => {
  const labels = {
    'create_time': '按添加时间',
    'score': '按评分',
    'read_time': '按阅读时间',
    'read_status': '已读/未读'
  }
  return labels[currentSortType.value] || ''
})

const selectedIncludeTags = computed(() => {
  return includeTags.value
    .map(id => allTags.value.find(tag => tag.id === id))
    .filter(Boolean)
})

const selectedExcludeTags = computed(() => {
  return excludeTags.value
    .map(id => allTags.value.find(tag => tag.id === id))
    .filter(Boolean)
})

const selectedAuthorsDisplay = computed(() => selectedAuthors.value)

const selectedLists = computed(() => {
  return selectedListIds.value
    .map(id => availableLists.value.find(list => list.id === id))
    .filter(Boolean)
})

const hasActiveFilter = computed(() => {
  return currentSortType.value || 
         (minScore.value !== null && minScore.value > 0) || 
         includeTags.value.length > 0 || 
         excludeTags.value.length > 0 ||
         selectedAuthors.value.length > 0 ||
         selectedListIds.value.length > 0 ||
         (activeContentType.value === 'comic' && unreadOnly.value)
})

function hasAnySelectedAuthor(item) {
  if (selectedAuthors.value.length === 0) {
    return true
  }
  const itemAuthors = extractItemAuthors(item)
  return selectedAuthors.value.some(author => itemAuthors.includes(author))
}

function belongsToSelectedLists(item) {
  if (selectedListIds.value.length === 0) {
    return true
  }
  const listIds = Array.isArray(item?.list_ids) ? item.list_ids : []
  return selectedListIds.value.some(listId => listIds.includes(listId))
}

const filteredComics = computed(() => {
  let result = [...comics.value]
  
  if (minScore.value !== null && minScore.value > 0) {
    result = result.filter(c => {
      const score = c.score ?? 0
      return score >= minScore.value
    })
  }
  
  if (includeTags.value.length > 0) {
    result = result.filter(c => {
      const comicTags = c.tag_ids || []
      return includeTags.value.every(tagId => comicTags.includes(tagId))
    })
  }
  
  if (excludeTags.value.length > 0) {
    result = result.filter(c => {
      const comicTags = c.tag_ids || []
      return !excludeTags.value.some(tagId => comicTags.includes(tagId))
    })
  }

  if (unreadOnly.value) {
    result = result.filter(c => isUnreadByProgress(c.current_page))
  }

  result = result.filter(c => hasAnySelectedAuthor(c) && belongsToSelectedLists(c))
  
  if (currentSortType.value) {
    switch (currentSortType.value) {
      case 'create_time':
        result.sort((a, b) => (b.create_time || '').localeCompare(a.create_time || ''))
        break
      case 'score':
        result.sort((a, b) => (b.score || 0) - (a.score || 0))
        break
      case 'read_time':
        result.sort((a, b) => (b.last_read_time || '').localeCompare(a.last_read_time || ''))
        break
      case 'read_status':
        result.sort((a, b) => {
          const aRead = isReadByProgress(a.current_page)
          const bRead = isReadByProgress(b.current_page)
          if (aRead !== bRead) return aRead ? 1 : -1
          return (b.score || 0) - (a.score || 0)
        })
        break
    }
  }
  
  return result
})

const filteredVideos = computed(() => {
  let result = [...videos.value]
  
  if (minScore.value !== null && minScore.value > 0) {
    result = result.filter(v => {
      const score = v.score ?? 0
      return score >= minScore.value
    })
  }
  
  if (includeTags.value.length > 0) {
    result = result.filter(v => {
      const videoTags = v.tag_ids || []
      return includeTags.value.every(tagId => videoTags.includes(tagId))
    })
  }
  
  if (excludeTags.value.length > 0) {
    result = result.filter(v => {
      const videoTags = v.tag_ids || []
      return !excludeTags.value.some(tagId => videoTags.includes(tagId))
    })
  }

  result = result.filter(v => hasAnySelectedAuthor(v) && belongsToSelectedLists(v))
  
  if (currentSortType.value) {
    switch (currentSortType.value) {
      case 'create_time':
        result.sort((a, b) => (b.create_time || '').localeCompare(a.create_time || ''))
        break
      case 'score':
        result.sort((a, b) => (b.score || 0) - (a.score || 0))
        break
    }
  }
  
  return result
})

const currentFilteredItems = computed(() => activeContentType.value === 'video' ? filteredVideos.value : filteredComics.value)
const selectedCount = computed(() => selectedItems.value.length)
const allCurrentSelected = computed(() => {
  if (currentFilteredItems.value.length === 0) {
    return false
  }
  const keySet = new Set(selectedItemKeys.value)
  return currentFilteredItems.value.every(item => keySet.has(getItemSelectionKey(item)))
})
const canMoveToLocal = computed(() => selectedItems.value.some(item => item.source === 'preview'))

function getCoverUrl(coverSource) {
  return buildCoverUrl(coverSource)
}

async function loadDetail() {
  loading.value = true
  const result = await listStore.fetchListDetail(listId.value)
  listInfo.value = result
  selectedItemKeys.value = normalizeSelectedItemKeys(selectedItemKeys.value)
  loading.value = false
}

function goToComic(comic) {
  if (!comic?.id) return
  if (comic.source === 'preview') {
    router.push(`/recommendation/${comic.id}`)
    return
  }
  router.push(`/comic/${comic.id}`)
}

function goToVideo(video) {
  if (!video?.id) return
  if (video.source === 'preview') {
    router.push(`/video-recommendation/${video.id}`)
    return
  }
  router.push(`/video/${video.id}`)
}

async function removeComic(comicId, source = 'local') {
  showConfirmDialog({
    title: '移出漫画',
    message: '确定要将该漫画从清单中移出吗？',
  })
    .then(async () => {
      const result = await listStore.removeComics(listId.value, [comicId], source)
      if (result) {
        await loadDetail()
      }
    })
    .catch(() => {})
}

async function removeVideo(videoId, source = 'local') {
  showConfirmDialog({
    title: '移出视频',
    message: '确定要将该视频从清单中移出吗？',
  })
    .then(async () => {
      const result = await listStore.removeVideos(listId.value, [videoId], source)
      if (result) {
        await loadDetail()
      }
    })
    .catch(() => {})
}

async function confirmDelete() {
  showConfirmDialog({
    title: '删除清单',
    message: `确定要删除清单「${listInfo.value.name}」吗？`,
  })
    .then(async () => {
      const result = await listStore.deleteList(listId.value)
      if (result) {
        router.back()
      }
    })
    .catch(() => {})
}

function setSortType(sortType) {
  currentSortType.value = sortType
  saveFilterState()
  showSortPanel.value = false
}

function clearSort() {
  currentSortType.value = ''
  saveFilterState()
}

function removeIncludeTag(tagId) {
  includeTags.value = includeTags.value.filter(id => id !== tagId)
  saveFilterState()
}

function removeExcludeTag(tagId) {
  excludeTags.value = excludeTags.value.filter(id => id !== tagId)
  saveFilterState()
}

function removeAuthor(author) {
  selectedAuthors.value = selectedAuthors.value.filter(item => item !== author)
  saveFilterState()
}

function removeList(listId) {
  selectedListIds.value = selectedListIds.value.filter(id => id !== listId)
  saveFilterState()
}

function removeUnreadOnly() {
  unreadOnly.value = false
  tempUnreadOnly.value = false
  saveFilterState()
}

function clearScoreFilter() {
  minScore.value = null
  tempMinScore.value = 0
  saveFilterState()
}

function clearAllFilters() {
  currentSortType.value = ''
  minScore.value = null
  tempMinScore.value = 0
  includeTags.value = []
  excludeTags.value = []
  selectedAuthors.value = []
  selectedListIds.value = []
  unreadOnly.value = false
  tempIncludeTags.value = []
  tempExcludeTags.value = []
  tempSelectedAuthors.value = []
  tempSelectedListIds.value = []
  tempUnreadOnly.value = false
  saveFilterState()
}

function toggleManageMode() {
  manageMode.value = !manageMode.value
  if (!manageMode.value) {
    selectedItemKeys.value = []
  }
}

function isItemSelected(item) {
  const key = getItemSelectionKey(item)
  if (!key) {
    return false
  }
  return selectedItemKeys.value.includes(key)
}

function toggleItemSelection(item) {
  const key = getItemSelectionKey(item)
  if (!key) {
    return
  }
  if (selectedItemKeys.value.includes(key)) {
    selectedItemKeys.value = selectedItemKeys.value.filter(existingKey => existingKey !== key)
    return
  }
  selectedItemKeys.value = [...selectedItemKeys.value, key]
}

function toggleSelectAllItems() {
  const currentKeys = currentFilteredItems.value.map(getItemSelectionKey).filter(Boolean)
  if (currentKeys.length === 0) {
    return
  }

  if (allCurrentSelected.value) {
    const currentKeySet = new Set(currentKeys)
    selectedItemKeys.value = selectedItemKeys.value.filter(key => !currentKeySet.has(key))
    return
  }

  selectedItemKeys.value = [...new Set([...selectedItemKeys.value, ...currentKeys])]
}

function handleComicCardClick(comic) {
  if (manageMode.value) {
    toggleItemSelection(comic)
    return
  }
  goToComic(comic)
}

function handleVideoCardClick(video) {
  if (manageMode.value) {
    toggleItemSelection(video)
    return
  }
  goToVideo(video)
}

function buildSourceIdGroups(items) {
  return items.reduce((groups, item) => {
    if (!item?.id) {
      return groups
    }
    const source = item.source === 'preview' ? 'preview' : 'local'
    groups[source].push(item.id)
    return groups
  }, { local: [], preview: [] })
}

function getDownloadableComics(items) {
  const groups = buildSourceIdGroups(items)
  return {
    localIds: groups.local,
    skippedPreviewCount: groups.preview.length
  }
}

function applyFilterAndClose() {
  minScore.value = tempMinScore.value > 0 ? tempMinScore.value : null
  includeTags.value = [...tempIncludeTags.value]
  excludeTags.value = [...tempExcludeTags.value]
  selectedAuthors.value = [...tempSelectedAuthors.value]
  selectedListIds.value = [...tempSelectedListIds.value]
  unreadOnly.value = Boolean(tempUnreadOnly.value)
  saveFilterState()
  showFilterPanel.value = false
}

async function handleBatchDownload() {
  if (filteredComics.value.length === 0) {
    showFailToast('没有可下载的漫画')
    return
  }

  const { localIds, skippedPreviewCount } = getDownloadableComics(filteredComics.value)
  if (localIds.length === 0) {
    showFailToast('当前列表中没有可下载的本地漫画')
    return
  }
  
  downloadLoading.value = true
  try {
    await comicApi.batchDownload(localIds)
    if (skippedPreviewCount > 0) {
      showSuccessToast(`成功下载 ${localIds.length} 部，跳过预览项 ${skippedPreviewCount} 部`)
    } else {
      showSuccessToast(`成功下载 ${localIds.length} 部漫画`)
    }
  } catch (error) {
    console.error('批量下载失败:', error)
    showFailToast('批量下载失败')
  } finally {
    downloadLoading.value = false
  }
}

async function handleManageBatchDownload() {
  if (selectedItems.value.length === 0) {
    showFailToast('请先选择内容')
    return
  }
  if (activeContentType.value !== 'comic') {
    showFailToast('视频暂不支持批量下载')
    return
  }

  const { localIds, skippedPreviewCount } = getDownloadableComics(selectedItems.value)
  if (localIds.length === 0) {
    showFailToast('所选内容中没有可下载的本地漫画')
    return
  }

  downloadLoading.value = true
  try {
    await comicApi.batchDownload(localIds)
    if (skippedPreviewCount > 0) {
      showSuccessToast(`成功下载 ${localIds.length} 部，跳过预览项 ${skippedPreviewCount} 部`)
    } else {
      showSuccessToast(`成功下载 ${localIds.length} 部漫画`)
    }
  } catch (error) {
    console.error('批量下载失败:', error)
    showFailToast('批量下载失败')
  } finally {
    downloadLoading.value = false
  }
}

async function handleBatchRemoveFromList() {
  if (selectedItems.value.length === 0) {
    showFailToast('请先选择内容')
    return
  }

  try {
    await showConfirmDialog({
      title: '批量删除',
      message: `确定要从清单移除已选 ${selectedItems.value.length} 项内容吗？`
    })
  } catch {
    return
  }

  const groups = buildSourceIdGroups(selectedItems.value)
  batchRemoveLoading.value = true
  try {
    const operations = []
    if (activeContentType.value === 'video') {
      if (groups.local.length > 0) {
        operations.push(listStore.removeVideos(listId.value, groups.local, 'local'))
      }
      if (groups.preview.length > 0) {
        operations.push(listStore.removeVideos(listId.value, groups.preview, 'preview'))
      }
    } else {
      if (groups.local.length > 0) {
        operations.push(listStore.removeComics(listId.value, groups.local, 'local'))
      }
      if (groups.preview.length > 0) {
        operations.push(listStore.removeComics(listId.value, groups.preview, 'preview'))
      }
    }

    const results = await Promise.all(operations)
    if (!results.every(Boolean)) {
      showFailToast('批量删除失败，请重试')
      return
    }

    selectedItemKeys.value = []
    await loadDetail()
  } finally {
    batchRemoveLoading.value = false
  }
}

async function handleBatchMoveToLocal() {
  if (selectedItems.value.length === 0) {
    showFailToast('请先选择内容')
    return
  }

  const groups = buildSourceIdGroups(selectedItems.value)
  const localSkipped = groups.local.length
  const previewIds = groups.preview

  if (previewIds.length === 0) {
    showFailToast(localSkipped > 0 ? '所选内容已在本地库，无需移动' : '没有可移动的内容')
    return
  }

  moveToLocalLoading.value = true
  try {
    let response
    if (activeContentType.value === 'video') {
      response = await videoApi.migrateRecommendationToLocal(previewIds)
    } else {
      response = await recommendationApi.migrateToLocal(previewIds)
    }

    if (!response || response.code !== 200) {
      showFailToast(response?.msg || '移动到本地库失败')
      return
    }

    const stats = response.data || {}
    const importedCount = Number(stats.imported_count || 0)
    const skippedCount = Number(stats.skipped_count || 0) + localSkipped
    const failedCount = Number(stats.failed_count || 0)
    showSuccessToast(`移动完成：成功 ${importedCount}，跳过 ${skippedCount}，失败 ${failedCount}`)

    selectedItemKeys.value = []
    await loadDetail()
  } catch (error) {
    console.error('移动到本地库失败:', error)
    showFailToast('移动到本地库失败')
  } finally {
    moveToLocalLoading.value = false
  }
}

watch(showFilterPanel, (val) => {
  if (val) {
    tempMinScore.value = minScore.value || 0
    tempIncludeTags.value = [...includeTags.value]
    tempExcludeTags.value = [...excludeTags.value]
    tempSelectedAuthors.value = [...selectedAuthors.value]
    tempSelectedListIds.value = [...selectedListIds.value]
    tempUnreadOnly.value = unreadOnly.value
  }
})

watch(activeContentType, async (newContentType) => {
  selectedItemKeys.value = []
  manageMode.value = false
  if (newContentType === 'video' && tagStore.videoTags.length === 0) {
    await tagStore.fetchTags('video')
  }
})

watch(currentItems, () => {
  selectedItemKeys.value = normalizeSelectedItemKeys(selectedItemKeys.value)
})

onMounted(async () => {
  if (listStore.lists.length === 0) {
    await listStore.fetchLists()
  }
  if (tagStore.tags.length === 0) {
    await tagStore.fetchTags()
  }
  await loadDetail()
  if (activeContentType.value === 'video' && tagStore.videoTags.length === 0) {
    await tagStore.fetchTags('video')
  }
  restoreFilterState()
})
</script>

<style scoped>
.list-detail {
  min-height: 100vh;
  background: var(--surface-0);
  padding-bottom: 20px;
}

.loading-center {
  display: flex;
  justify-content: center;
  padding-top: 100px;
}

.list-header {
  padding: 16px;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  margin-bottom: 12px;
}

.list-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.list-count {
  font-size: 12px;
  color: var(--text-tertiary);
}

.list-stats {
  margin-top: 8px;
}

.tab-count {
  margin-left: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.action-bar {
  padding: 8px 16px;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.action-btn {
  flex: 1;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.manage-btn {
  min-width: 52px;
}

.manage-action-bar {
  padding: 10px 16px;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  margin-bottom: 8px;
}

.manage-summary {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.manage-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.active-filter-bar {
  padding: 8px 16px;
  background: var(--surface-2);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  border-bottom: 1px solid var(--border-soft);
  border-left: 1px solid var(--border-soft);
  border-right: 1px solid var(--border-soft);
  border-radius: 12px;
}

.filter-tag {
  margin-right: 4px;
}

.comic-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
  padding: 10px;
}

.video-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
  padding: 10px;
}

.comic-card {
  position: relative;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
}

.video-card {
  position: relative;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
}

.comic-card.selected,
.video-card.selected {
  border-color: #1989fa;
  box-shadow: 0 0 0 1px rgba(25, 137, 250, 0.25);
}

.comic-cover {
  width: 100%;
  aspect-ratio: 3/4;
  object-fit: cover;
}

.video-cover {
  width: 100%;
  aspect-ratio: 16/9;
  object-fit: cover;
}

.comic-info {
  padding: 8px;
}

.video-info {
  padding: 8px;
}

.comic-title {
  font-size: 12px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  margin-bottom: 4px;
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

.comic-meta {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: var(--text-tertiary);
}

.video-meta {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: var(--text-tertiary);
}

.comic-score {
  color: #ffd21e;
}

.video-score {
  color: #ffd21e;
}

.video-code {
  color: var(--text-secondary);
}

.remove-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  border-radius: 50%;
  padding: 4px;
  font-size: 12px;
}

.source-tag {
  position: absolute;
  top: 4px;
  left: 4px;
  z-index: 1;
}

.select-check {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 2;
  padding: 2px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.86);
}

.filter-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.filter-panel :deep(.advanced-filter) {
  flex: 1;
  overflow-y: auto;
  border-radius: 0;
  box-shadow: none;
}

@media (min-width: 768px) {
  .comic-grid {
    grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  }
  
  .video-grid {
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  }
}
</style>
