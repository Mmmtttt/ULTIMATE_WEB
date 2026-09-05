<template>
  <div class="comic-detail desktop-page-shell">
    <van-nav-bar title="漫画详情" left-text="返回" left-arrow @click-left="$router.back()">
      <template #right>
        <template v-if="isThirdPartyMode">
          <van-button size="small" type="primary" @click="handleThirdPartyImport" :loading="importing">
            导入
          </van-button>
        </template>
        <template v-else>
          <van-icon
            :name="isFavorited ? 'star' : 'star-o'"
            class="nav-icon"
            :class="{ active: isFavorited }"
            @click="handleToggleFavorite"
            :title="isFavorited ? '取消收藏' : '收藏'"
          />
          <van-icon
            name="ellipsis"
            class="nav-icon"
            @click="showActionSheet = true"
            title="更多操作"
          />
        </template>
      </template>
    </van-nav-bar>
    
    <van-loading v-if="isLoading" type="spinner" color="#1989fa" />
    
    <div v-else-if="!comic" class="empty">
      <van-empty :description="emptyDescription" />
    </div>
    
    <div v-else class="detail-content">
      <div class="cover-section">
        <div class="cover-main">
          <div class="cover-wrapper">
            <van-image 
              :src="coverUrl" 
              fit="cover" 
              class="cover" 
              lazy-load
              @click="startReading"
            >
              <template #loading>
                <van-loading class="loading" />
              </template>
            </van-image>
            <van-tag
              v-if="isThirdPartyMode"
              type="warning"
              size="small"
              class="source-tag"
            >{{ route.query.platform }}</van-tag>
            <van-tag
              v-else-if="comic.source === 'preview'"
              type="primary"
              size="small"
              class="source-tag"
            >预览库</van-tag>
            <van-tag
              v-else
              type="success"
              size="small"
              class="source-tag"
            >本地库</van-tag>
          </div>
          <div class="info">
            <van-icon v-if="!isThirdPartyMode" name="edit" class="info-edit-btn" @click="openEdit" title="编辑信息" />
            <h1 class="title">{{ comic.title }}</h1>
            <div class="author-row">
              <p class="author" v-if="comic.author">
                <span class="author-link" @click="filterByAuthor(comic.author)">{{ comic.author }}</span>
              </p>
              <p class="author" v-else>未知作者</p>
              <van-button 
                v-if="!isThirdPartyMode && comic.author && !isSubscribed" 
                size="mini" 
                type="primary" 
                plain
                @click="subscribeAuthor"
                :loading="subscribing"
              >
                订阅作者
              </van-button>
              <van-tag v-else-if="!isThirdPartyMode && comic.author && isSubscribed" type="success" size="medium">
                已订阅
              </van-tag>
            </div>
            
            <div v-if="!isThirdPartyMode" class="stats">
              <span class="stat-item">ID: {{ comic.id }}</span>
              <span class="stat-item">总页数: {{ comic.total_page }}</span>
              <span class="stat-item">进度: {{ comic.current_page }}/{{ comic.total_page }}</span>
              <span class="stat-item">{{ progressPercent }}%</span>
            </div>

            <div v-if="!isThirdPartyMode && comicStoragePath" class="storage-path-row" :title="comicStoragePath">
              <span class="storage-path-label">Path:</span>
              <span class="storage-path-value">{{ comicStoragePath }}</span>
            </div>

          </div>
        </div>

        <div v-if="!isThirdPartyMode" class="score-section">
          <div class="score-display">
            <div class="score-summary">
              <span class="score-label">评分</span>
            </div>
          </div>
          <div class="score-rate-wrap">
            <van-rate
              v-model="scoreValue"
              :count="12"
              allow-half
              @change="handleScoreChange"
              class="score-rate"
            />
          </div>
        </div>
      </div>
      
      <div v-if="!isThirdPartyMode" class="tags-section">
        <h2 class="section-title">标签</h2>
        <div class="tags-container">
          <van-tag 
            v-for="tag in comic.tags" 
            :key="tag.id" 
            size="medium" 
            type="primary" 
            plain 
            class="tag"
            :closeable="showTagRemove"
            @click="filterByTag(tag.id)"
            @close="handleRemoveTag(tag)"
          >
            {{ tag.name }}
          </van-tag>
          <van-tag 
            size="medium" 
            type="primary"
            class="tag tag-add"
            @click="openAddTagPopup"
          >
            <van-icon name="plus" size="12" />
          </van-tag>
          <van-tag
            v-if="comic.tags && comic.tags.length > 0"
            size="medium"
            type="danger"
            :plain="!showTagRemove"
            class="tag tag-remove"
            @click="showTagRemove = !showTagRemove"
          >
            <van-icon name="minus" size="12" />
          </van-tag>
          <van-tag 
            v-if="!comic.tags || comic.tags.length === 0" 
            size="medium" 
            type="default"
          >
            暂无标签
          </van-tag>
        </div>
      </div>
      
      <div class="desc-section" v-if="comic.desc">
        <h2 class="section-title">简介</h2>
        <p class="desc">{{ comic.desc }}</p>
      </div>

      <div v-if="hasChapters" class="chapter-section">
        <div class="section-heading">
          <h2 class="section-title">章节</h2>
          <span class="section-hint">共 {{ chapterCards.length }} 个章节</span>
        </div>
        <div class="chapter-list">
          <button
            v-for="chapter in chapterCards"
            :key="chapter.key"
            type="button"
            class="chapter-card"
            :class="{ 'is-current': chapter.isCurrent }"
            @click="openChapter(chapter)"
          >
            <span class="chapter-order">{{ chapter.displayIndex }}</span>
            <span class="chapter-main">
              <span class="chapter-title-row">
                <span class="chapter-name">{{ chapter.title }}</span>
                <van-tag
                  v-if="chapter.isCurrent"
                  size="medium"
                  type="primary"
                  plain
                  class="chapter-current-tag"
                >
                  当前
                </van-tag>
              </span>
              <span class="chapter-meta">{{ chapter.pageRangeLabel }} · 共 {{ chapter.pageCountLabel }}</span>
            </span>
            <span class="chapter-side">
              <span class="chapter-state">{{ chapter.statusText }}</span>
              <van-icon name="arrow" class="chapter-arrow" />
            </span>
          </button>
        </div>
      </div>
      
      <div class="preview-section" v-if="previewImages.length > 0">
        <h2 class="section-title">内容预览</h2>
        <div class="preview-grid">
          <div 
            v-for="(item, index) in displayedPreviewItems" 
            :key="index" 
            class="preview-item" 
            @click="previewImage(index)"
          >
            <img 
              :src="item.url" 
              class="preview-image"
            />
            <div class="preview-hover-overlay">
              <button class="preview-jump-btn" @click.stop="goToPreviewPage(item.pageNum)">
                跳转到此页
              </button>
            </div>
            <span class="preview-page">第{{ item.pageNum }}页</span>
          </div>
        </div>
        <div class="preview-actions">
          <button
            v-if="isPreviewLimited && hasMorePreviews"
            class="preview-action-btn"
            @click="expandPreview"
          >
            展开更多 ({{ previewImages.length - previewLimit }})
          </button>
          <button class="preview-action-btn preview-action-btn--primary" @click="showAllPreviews">
            显示全部 ({{ previewImages.length }})
          </button>
        </div>
      </div>
      
      <!-- 图片预览 -->
      <van-image-preview
        v-model:show="showPreview"
        :images="previewImages"
        :start-position="previewIndex"
        :closeable="true"
        close-icon="close"
        @change="onPreviewChange"
      />
      
      <div class="action-section">
        <template v-if="isThirdPartyMode">
          <van-button type="primary" size="large" @click="startThirdPartyReading" :disabled="!comic.image_urls || comic.image_urls.length === 0" class="read-button">
            在线阅读
          </van-button>
          <van-button plain size="large" @click="handleThirdPartyImport" :loading="importing">
            导入到本地
          </van-button>
        </template>
        <van-button v-else type="primary" size="large" @click="startReading" class="read-button">
          {{ comic.current_page > 1 ? '继续阅读' : '开始阅读' }}
        </van-button>
        <div v-if="!isThirdPartyMode" class="detail-action-strip">
          <van-button
            size="small"
            type="warning"
            :icon="isFavorited ? 'star' : 'star-o'"
            :loading="favoriteLoading"
            @click="handleToggleFavorite"
          >
            {{ isFavorited ? '已收藏' : '收藏' }}
          </van-button>
          <van-button size="small" type="primary" icon="records-o" @click="openListManager">
            加入清单
          </van-button>
          <van-button
            v-if="isLocalImportedComic"
            size="small"
            type="primary"
            plain
            icon="replay"
            :loading="refreshingLocalMetadata"
            @click="refreshLocalMetadata"
          >
            补全信息
          </van-button>
          <van-button size="small" type="danger" icon="delete-o" @click="handleMoveToTrash">
            删除
          </van-button>
        </div>
      </div>
    </div>
    
    <van-action-sheet 
      v-model:show="showActionSheet" 
      :actions="actions" 
      @select="onActionSelect"
    />
    <van-popup 
      v-model:show="showEditPopup" 
      position="bottom" 
      round 
      :style="{ height: '60%' }"
    >
      <div class="edit-popup">
        <van-nav-bar title="编辑漫画信息">
          <template #right>
            <van-button type="primary" size="small" @click="saveEdit">保存</van-button>
          </template>
        </van-nav-bar>
        
        <van-cell-group inset>
          <van-field v-model="editForm.title" label="标题" placeholder="请输入标题" />
          <van-field v-model="editForm.author" label="作者" placeholder="请输入作者" />
          <van-field 
            v-model="editForm.desc" 
            label="简介" 
            type="textarea" 
            rows="3"
            placeholder="请输入简介" 
          />
        </van-cell-group>
        <div v-if="comic.source !== 'preview'" style="padding: 0 16px 16px;">
          <van-button
            type="primary"
            plain
            block
            :loading="refreshingLocalMetadata"
            @click="refreshLocalMetadata"
          >
            更新详情信息
          </van-button>
        </div>
      </div>
    </van-popup>
    
    <van-popup 
      v-model:show="showTagPopup" 
      position="bottom" 
      round 
      :style="{ height: '60%' }"
    >
      <div class="tag-popup">
        <van-nav-bar title="绑定标签">
          <template #right>
            <van-button type="primary" size="small" @click="saveTags">保存</van-button>
          </template>
        </van-nav-bar>
        
        <div class="tag-select-list">
          <van-checkbox-group v-model="selectedTagIds">
            <van-cell-group inset>
              <van-cell 
                v-for="tag in allTags" 
                :key="tag.id"
                clickable
                @click="toggleTag(tag.id)"
              >
                <template #title>
                  <span>{{ tag.name }}</span>
                  <span class="tag-count">({{ tag.comic_count || 0 }})</span>
                </template>
                <template #right-icon>
                  <van-checkbox :name="tag.id" />
                </template>
              </van-cell>
            </van-cell-group>
          </van-checkbox-group>
        </div>
      </div>
    </van-popup>
    
    <van-popup 
      v-model:show="showListPopup" 
      position="bottom" 
      round 
      :style="{ height: '50%' }"
    >
      <div class="list-popup">
        <van-nav-bar title="管理清单" left-text="取消" @click-left="showListPopup = false" />
        
        <van-checkbox-group v-model="selectedListIds">
          <van-cell-group inset>
            <van-cell 
              v-for="list in customLists" 
              :key="list.id"
              clickable
              @click="toggleListItem(list.id)"
            >
              <template #title>
                <span>{{ list.name }}</span>
                <span class="list-count">({{ list.comic_count || 0 }})</span>
              </template>
              <template #right-icon>
                <van-checkbox :name="list.id" />
              </template>
            </van-cell>
          </van-cell-group>
        </van-checkbox-group>
        
        <div class="list-action">
          <van-button type="primary" block @click="addToLists">保存</van-button>
        </div>
      </div>
    </van-popup>

    <!-- 添加标签弹窗 -->
    <van-popup v-model:show="showAddTag" round position="bottom" :style="{ height: '50%' }">
      <div class="edit-popup">
        <van-nav-bar title="添加标签" left-text="取消" @click-left="showAddTag = false" />
        <div class="tag-add-content">
          <van-search
            v-model="newTagName"
            shape="round"
            placeholder="搜索已有标签，或输入新标签"
            clearable
            @search="handleAddTag"
          />
          <div v-if="filteredAddTagOptions.length > 0" class="tag-option-list">
            <button
              v-for="tag in filteredAddTagOptions"
              :key="tag.id"
              type="button"
              class="tag-option"
              @click="bindExistingTag(tag)"
            >
              <span class="tag-option-name">{{ tag.name }}</span>
              <span class="tag-option-count">{{ tag.comic_count || 0 }} 项</span>
            </button>
          </div>
          <div v-else class="tag-option-empty">
            {{ newTagName.trim() ? '没有匹配的已有标签，可直接新建。' : '输入关键词后会实时显示可选标签。' }}
          </div>
          <van-button type="primary" block :loading="tagAdding" @click="handleAddTag" style="margin-top:12px">
            添加
          </van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useComicStore, useTagStore, useListStore } from '@/stores'
import { buildCoverUrl, buildImageUrl } from '@/api/image'
import { authorApi, comicApi } from '@/api'
import { tagApi } from '@/api/tag'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { applyListMembershipChanges, buildListChangeMessage, isReadByProgress } from '@/utils'

const route = useRoute()
const router = useRouter()
const comicStore = useComicStore()
const tagStore = useTagStore()
const listStore = useListStore()

const comic = ref(null)
const isLoading = ref(true)
const showActionSheet = ref(false)
const showEditPopup = ref(false)
const showTagPopup = ref(false)
const showListPopup = ref(false)
const showAddTag = ref(false)
const newTagName = ref('')
const tagAdding = ref(false)
const showPreview = ref(false)
const previewIndex = ref(0)
const previewLimit = ref(0)
const previewColumns = ref(2)
const allTags = ref([])
const selectedTagIds = ref([])
const selectedListIds = ref([])
const scoreValue = ref(6)
const favoriteLoading = ref(false)
const downloadLoading = ref(false)
const subscribing = ref(false)
const isSubscribed = ref(false)
const refreshingLocalMetadata = ref(false)

const isThirdPartyMode = computed(() => {
  return Boolean(route.query.platform)
})
const isLocalImportedComic = computed(() => {
  const id = String(comic.value?.id || '').trim().toUpperCase()
  return !isThirdPartyMode.value && id.startsWith('LOCAL') && comic.value?.source !== 'preview'
})
const importing = ref(false)
const thirdPartyError = ref('')

const editForm = ref({
  title: '',
  author: '',
  desc: ''
})

const actions = computed(() => {
  const menuActions = [
    { name: '下载漫画', value: 'download' },
    { name: '检查更新', value: 'check_update' }
  ]
  menuActions.push({ name: '移入回收站', value: 'trash', color: '#ee0a24' })
  return menuActions
})
const coverUrl = computed(() => {
  return comic.value ? buildCoverUrl(comic.value.cover_path) : ''
})

const progressPercent = computed(() => {
  if (!comic.value || !comic.value.total_page || comic.value.total_page === 0) return 0
  return Math.round((comic.value.current_page / comic.value.total_page) * 100)
})

const previewImages = computed(() => {
  if (!comic.value) return []
  if (isThirdPartyMode.value) {
    if (comic.value.preview_urls && comic.value.preview_urls.length > 0) {
      return comic.value.preview_urls
    }
    if (!comic.value.preview_pages) return []
    return comic.value.preview_pages.map((page) => {
      return typeof page === 'string' && page.startsWith('http')
        ? page
        : buildImageUrl(comic.value.id, page)
    })
  }
  if (!comic.value.preview_pages) return []
  return comic.value.preview_pages.map(page => getImageUrl(comic.value.id, page))
})

function updatePreviewColumns() {
  const w = window.innerWidth
  if (w >= 1200) previewColumns.value = 5
  else if (w >= 768) previewColumns.value = 4
  else if (w >= 480) previewColumns.value = 3
  else previewColumns.value = 2
}

const displayedPreviews = computed(() => {
  if (previewLimit.value <= 0) return previewImages.value
  return previewImages.value.slice(0, previewLimit.value)
})

const previewItems = computed(() => {
  if (!comic.value) return []
  const urls = previewImages.value
  const pages = comic.value.preview_pages || []
  return urls.map((url, i) => ({
    url,
    pageNum: pages[i] || (i + 1)
  }))
})

const displayedPreviewItems = computed(() => {
  if (previewLimit.value <= 0) return previewItems.value
  return previewItems.value.slice(0, previewLimit.value)
})

const hasMorePreviews = computed(() => {
  return previewImages.value.length > previewColumns.value
})

const isPreviewLimited = computed(() => {
  return previewLimit.value > 0 && previewLimit.value < previewImages.value.length
})

function expandPreview() {
  previewLimit.value = Math.min(previewLimit.value + previewColumns.value, previewImages.value.length)
}

function showAllPreviews() {
  previewLimit.value = previewImages.value.length
}

const isFavorited = computed(() => {
  return listStore.isFavorited(comic.value)
})

const customLists = computed(() => listStore.lists || [])
const currentTagIdSet = computed(() => {
  const ids = [
    ...(comic.value?.tag_ids || []),
    ...((comic.value?.tags || []).map(tag => tag?.id))
  ]
  return new Set(ids.filter(Boolean).map(id => String(id)))
})

const filteredAddTagOptions = computed(() => {
  const keyword = newTagName.value.trim().toLowerCase()
  return allTags.value
    .filter(tag => tag?.id && !currentTagIdSet.value.has(String(tag.id)))
    .filter(tag => {
      if (!keyword) return true
      return String(tag.name || '').toLowerCase().includes(keyword)
    })
    .slice(0, 32)
})

const exactExistingAddTag = computed(() => {
  const keyword = newTagName.value.trim().toLowerCase()
  if (!keyword) return null
  return allTags.value.find(tag => {
    return tag?.id &&
      !currentTagIdSet.value.has(String(tag.id)) &&
      String(tag.name || '').trim().toLowerCase() === keyword
  }) || null
})

const isRead = computed(() => {
  if (!comic.value) return false
  return isReadByProgress(comic.value.current_page)
})

const comicStoragePath = computed(() => {
  const path = String(comic.value?.storage_path || comic.value?.import_source || '').trim()
  return path
})

const hasChapters = computed(() => {
  return Array.isArray(comic.value?.chapters) && comic.value.chapters.length > 1
})

const emptyDescription = computed(() => {
  if (isThirdPartyMode.value && route.query.platform) {
    if (thirdPartyError.value) {
      return thirdPartyError.value
    }
    return `无法从 ${route.query.platform} 加载漫画详情，请确认该平台插件已启用并配置正确`
  }
  return '漫画不存在'
})

const chapterCards = computed(() => {
  if (!hasChapters.value) return []
  const currentPage = Number(comic.value?.current_page || 1)
  return comic.value.chapters.map((chapter, index) => {
    const startPage = Number(chapter?.start_page || 1)
    const endPage = Number(chapter?.end_page || startPage)
    const pageCount = Number(chapter?.page_count || Math.max(1, endPage - startPage + 1))
    const isCurrent = currentPage >= startPage && currentPage <= endPage
    return {
      key: chapter?.key || `${startPage}-${index}`,
      title: chapter?.title || `第${index + 1}章`,
      displayIndex: String(index + 1).padStart(2, '0'),
      start_page: startPage,
      end_page: endPage,
      page_count: pageCount,
      pageRangeLabel: startPage === endPage ? `第 ${startPage} 页` : `第 ${startPage}-${endPage} 页`,
      pageCountLabel: `${pageCount} 页`,
      isCurrent,
      statusText: isCurrent ? `阅读至第 ${currentPage} 页` : `从第 ${startPage} 页开始`
    }
  })
})

// 方法
function getImageUrl(comicId, pageNum) {
  return buildImageUrl(comicId, pageNum)
}

async function fetchComicDetail() {
  const comicId = route.params.id
  isLoading.value = true

  if (isThirdPartyMode.value) {
    await fetchThirdPartyDetail(comicId)
    return
  }

  try {
    const detail = await comicStore.fetchComicDetail(comicId)
    if (detail) {
      comic.value = detail
      scoreValue.value = detail.score || 6
      selectedTagIds.value = detail.tag_ids || []
      editForm.value = {
        title: detail.title,
        author: detail.author || '',
        desc: detail.desc || ''
      }
      await checkSubscriptionStatus()
    }
  } catch (error) {
    console.error('获取漫画详情失败:', error)
  } finally {
    isLoading.value = false
  }
}

async function fetchThirdPartyDetail(comicId) {
  try {
    const response = await comicApi.thirdPartyDetail(comicId, route.query.platform)
    if (response.code === 200 && response.data) {
      const data = response.data
      comic.value = {
        id: data.id || data.album_id || comicId,
        title: data.title || data.name || '',
        author: data.author || data.artist || '',
        desc: data.description || data.desc || '',
        cover_path: data.cover_path || data.cover_url || '',
        total_page: data.total_page || data.page_count || data.pages || 0,
        preview_urls: data.preview_urls || [],
        image_urls: data.image_urls || [],
        preview_pages: data.preview_pages || data.preview_images || [],
        tags: data.tags || [],
        chapters: data.chapters || [],
        score: data.score || 0,
        source: route.query.platform,
      }
    } else {
      thirdPartyError.value = response?.msg || '获取漫画详情失败'
      console.warn('[ThirdParty] 响应异常:', response)
    }
  } catch (error) {
    thirdPartyError.value = error?.message || '获取第三方漫画详情失败'
    console.error('[ThirdParty] 获取第三方漫画详情失败:', error)
  } finally {
    isLoading.value = false
  }
}

async function handleThirdPartyImport() {
  if (!comic.value) return
  importing.value = true
  try {
    const response = await comicApi.onlineImport({
      import_type: 'by_id',
      target: 'home',
      platform: route.query.platform,
      comic_id: route.params.id,
    })
    if (response.code === 200) {
      showSuccessToast('导入成功')
      router.replace({ query: {} })
    } else {
      showFailToast(response.msg || '导入失败')
    }
  } catch {
    showFailToast('导入失败')
  } finally {
    importing.value = false
  }
}

async function checkSubscriptionStatus() {
  if (!comic.value?.author) return
  
  try {
    const response = await authorApi.getList()
    if (response.code === 200) {
      isSubscribed.value = response.data.some(
        author => author.name.toLowerCase() === comic.value.author.toLowerCase()
      )
    }
  } catch (error) {
    console.error('检查订阅状态失败:', error)
  }
}

async function subscribeAuthor() {
  if (!comic.value?.author || subscribing.value) return
  
  subscribing.value = true
  try {
    const response = await authorApi.subscribe(comic.value.author)
    if (response.code === 200) {
      isSubscribed.value = true
      showSuccessToast('订阅成功')
    } else {
      showFailToast(response.msg || '订阅失败')
    }
  } catch (error) {
    console.error('订阅作者失败:', error)
    showFailToast('订阅失败')
  } finally {
    subscribing.value = false
  }
}

async function fetchAllTags() {
  try {
    const tags = await tagStore.fetchTags()
    if (tags) {
      allTags.value = tags
    }
  } catch (error) {
    console.error('获取标签列表失败:', error)
  }
}

function startReading() {
  router.push(`/reader/${comic.value.id}`)
}

function startThirdPartyReading() {
  if (!comic.value.image_urls || comic.value.image_urls.length === 0) return
  router.push({
    name: 'ComicReader',
    params: { id: route.params.id },
    query: { mode: 'third_party', platform: route.query.platform, title: comic.value.title }
  })
}

function goToPage(page) {
  router.push(`/reader/${comic.value.id}?page=${page}`)
}

function goToPreviewPage(page) {
  if (isThirdPartyMode.value) {
    router.push({
      name: 'ComicReader',
      params: { id: route.params.id },
      query: { mode: 'third_party', platform: route.query.platform, title: comic.value.title, page: String(page) }
    })
  } else {
    router.push(`/reader/${comic.value.id}?page=${page}`)
  }
}

function openChapter(chapter) {
  const startPage = Number(chapter?.start_page || 0)
  if (!Number.isFinite(startPage) || startPage < 1) return
  goToPage(startPage)
}

function previewImage(index) {
  previewIndex.value = index
  showPreview.value = true
}

function onPreviewChange(index) {
  previewIndex.value = index
}

function filterByTag(tagId) {
  if (comic.value.source === 'preview') {
    router.push({ name: 'Preview', query: { tagId: tagId } })
  } else {
    router.push({ name: 'Library', query: { tagId: tagId } })
  }
}

function filterByAuthor(author) {
  if (comic.value.source === 'preview') {
    router.push({ name: 'Preview', query: { author: author } })
  } else {
    router.push({ name: 'Library', query: { author: author } })
  }
}

async function handleScoreChange(value) {
  try {
    await comicStore.updateScore(comic.value.id, value)
    comic.value.score = value
    showSuccessToast('评分保存成功')
  } catch (error) {
    console.error('保存评分失败:', error)
    showFailToast('评分保存失败')
  }
}

function openEdit() {
  editForm.value = {
    title: comic.value.title || '',
    author: comic.value.author || '',
    desc: comic.value.desc || ''
  }
  showEditPopup.value = true
}

function onActionSelect(action) {
  showActionSheet.value = false
  if (action.value === 'download') {
    handleDownload()
  } else if (action.value === 'check_update') {
    handleCheckAndDownloadUpdate()
  } else if (action.value === 'tags') {
    showTagPopup.value = true
  } else if (action.value === 'trash') {
    handleMoveToTrash()
  }
}

function openListManager() {
  selectedListIds.value = [...(comic.value?.list_ids || [])]
  showListPopup.value = true
}

async function openAddTagPopup() {
  newTagName.value = ''
  if (allTags.value.length === 0) {
    await fetchAllTags()
  }
  showAddTag.value = true
}

async function refreshLocalMetadata() {
  if (!comic.value?.id || comic.value?.source === 'preview' || refreshingLocalMetadata.value) return

  refreshingLocalMetadata.value = true
  try {
    const response = await comicStore.refreshLocalMetadata(comic.value.id)
    if (response?.code !== 200 || !response?.data) {
      showFailToast(response?.msg || '更新详情信息失败')
      return
    }

    comicStore.clearCache('detail', comic.value.id)
    comicStore.clearCache('list')
    comic.value = response.data
    selectedTagIds.value = [...(response.data?.tag_ids || [])]
    editForm.value = {
      title: response.data?.title || '',
      author: response.data?.author || '',
      desc: response.data?.desc || ''
    }
    await fetchAllTags()
    await checkSubscriptionStatus()
    showSuccessToast(response?.msg || '详情信息已更新')
  } catch (error) {
    console.error('更新详情信息失败:', error)
    showFailToast(error?.message || '更新详情信息失败')
  } finally {
    refreshingLocalMetadata.value = false
  }
}

async function handleDownload() {
  if (!comic.value) return
  
  downloadLoading.value = true
  try {
    await comicStore.download(comic.value.id, comic.value.title)
    showSuccessToast('下载成功')
  } catch (error) {
    console.error('下载失败:', error)
    showFailToast('下载失败')
  } finally {
    downloadLoading.value = false
  }
}

async function handleCheckAndDownloadUpdate() {
  if (!comic.value) return

  try {
    const checkResponse = await comicStore.checkUpdate(comic.value.id)
    const checkData = checkResponse?.data || {}

    if (!checkData.can_update) {
      showFailToast('当前平台暂不支持在线更新')
      return
    }

    if (!checkData.has_update) {
      const localPages = checkData.local_page_count ?? comic.value.total_page ?? 0
      const remotePages = checkData.remote_total_page ?? localPages
      showSuccessToast(`暂无更新（本地 ${localPages} 页 / 远程 ${remotePages} 页）`)
      return
    }

    const localPages = checkData.local_page_count ?? 0
    const remotePages = checkData.remote_total_page ?? 0

    const { showConfirmDialog } = await import('vant')
    await showConfirmDialog({
      title: '发现更新',
      message: `检测到远程页数 ${remotePages} 大于本地页数 ${localPages}，是否立即下载更新？`
    })

    const downloadResponse = await comicStore.downloadUpdate(comic.value.id)
    if (downloadResponse.code !== 200) {
      showFailToast(downloadResponse.msg || '下载更新失败')
      return
    }

    comicStore.clearCache('detail', comic.value.id)
    comicStore.clearCache('images', comic.value.id)
    comicStore.clearCache('list')
    await fetchComicDetail()

    const latestPages = downloadResponse?.data?.local_page_count ?? comic.value?.total_page ?? 0
    showSuccessToast(`更新完成，当前本地 ${latestPages} 页`)
  } catch (error) {
    if (error === 'cancel') return
    console.error('检查更新失败:', error)
    showFailToast(error?.message || '检查更新失败')
  }
}
async function handleMoveToTrash() {
  if (!comic.value) return
  
  try {
    const { showConfirmDialog } = await import('vant')
    await showConfirmDialog({
      title: '确认操作',
      message: '确定将此漫画移入回收站吗？'
    })
    
    const res = await comicStore.moveToTrash(comic.value.id)
    if (res.code === 200) {
      showSuccessToast('已移入回收站')
      router.back()
    } else {
      showFailToast(res.msg || '操作失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      showFailToast('操作失败')
    }
  }
}

async function saveEdit() {
  try {
    const response = await comicStore.editComic(comic.value.id, editForm.value)
    if (response.code === 200) {
      comic.value.title = editForm.value.title
      comic.value.author = editForm.value.author
      comic.value.desc = editForm.value.desc
      showEditPopup.value = false
      showSuccessToast('保存成功')
    } else {
      showFailToast(response.msg || '保存失败')
    }
  } catch (error) {
    console.error('保存失败:', error)
    showFailToast('保存失败')
  }
}

function toggleTag(tagId) {
  const index = selectedTagIds.value.indexOf(tagId)
  if (index > -1) {
    selectedTagIds.value.splice(index, 1)
  } else {
    selectedTagIds.value.push(tagId)
  }
}

async function saveTags() {
  try {
    const response = await comicStore.bindTags(comic.value.id, selectedTagIds.value)
    if (response.code === 200) {
      comicStore.clearCache('detail', comic.value.id)
      await fetchComicDetail()
      showTagPopup.value = false
      showSuccessToast('标签绑定成功')
    } else {
      showFailToast(response.msg || '标签绑定失败')
    }
  } catch (error) {
    console.error('标签绑定失败:', error)
    showFailToast('标签绑定失败')
  }
}

async function handleToggleFavorite() {
  favoriteLoading.value = true
  try {
    const result = await listStore.toggleFavorite(comic.value.id, comic.value.source || 'local')
    if (result !== null) {
      const FAVORITES_LIST_ID = 'list_favorites_comic'
      if (result) {
        if (!comic.value.list_ids) {
          comic.value.list_ids = []
        }
        if (!comic.value.list_ids.includes(FAVORITES_LIST_ID)) {
          comic.value.list_ids.push(FAVORITES_LIST_ID)
        }
      } else {
        if (comic.value.list_ids) {
          comic.value.list_ids = comic.value.list_ids.filter(id => id !== FAVORITES_LIST_ID)
        }
      }
      comicStore.clearCache('detail', comic.value.id)
    }
  } finally {
    favoriteLoading.value = false
  }
}

function toggleListItem(listId) {
  const index = selectedListIds.value.indexOf(listId)
  if (index > -1) {
    selectedListIds.value.splice(index, 1)
  } else {
    selectedListIds.value.push(listId)
  }
}

async function addToLists() {
  if (selectedListIds.value.length === 0 && (!comic.value.list_ids || comic.value.list_ids.length === 0)) {
    showFailToast('请选择清单')
    return
  }
  
  try {
    const { addCount, removeCount, unchanged } = await applyListMembershipChanges({
      listStore,
      contentType: 'comic',
      selectedListIds: selectedListIds.value,
      currentListIds: comic.value.list_ids || [],
      itemId: comic.value.id,
      source: comic.value.source || 'local'
    })

    if (addCount > 0 || removeCount > 0) {
      showListPopup.value = false
      selectedListIds.value = []
      comicStore.clearCache('detail', comic.value.id)
      await fetchComicDetail()
      await listStore.fetchLists('comic')

      showSuccessToast(buildListChangeMessage(addCount, removeCount))
    } else if (unchanged) {
      showSuccessToast('清单无变化')
      showListPopup.value = false
    }
  } catch (error) {
    console.error('addToLists error:', error)
    showFailToast('操作失败')
  }
}

async function markAsRead() {
  try {
    if (isRead.value) {
      await comicStore.saveProgress(comic.value.id, 1)
      comic.value.current_page = 1
      showSuccessToast('已标记为未读')
    } else {
      await comicStore.saveProgress(comic.value.id, comic.value.total_page)
      comic.value.current_page = comic.value.total_page
      showSuccessToast('已标记为已读')
    }
  } catch (error) {
    showFailToast('标记失败')
  }
}

async function handleAddTag() {
  const name = newTagName.value.trim()
  if (!name) { showFailToast('请输入标签名称'); return }
  if ((comic.value?.tags || []).some(tag => String(tag.name || '').trim().toLowerCase() === name.toLowerCase())) {
    showFailToast('标签已存在')
    return
  }
  const existing = exactExistingAddTag.value
  if (existing) {
    await bindExistingTag(existing)
    return
  }
  tagAdding.value = true
  try {
    const res = await tagApi.add(name, 'comic')
    const tagId = res.data?.tag_id || res.data?.id
    if (res.code === 200 && tagId) {
      await tagApi.batchAddTags([{ id: comic.value.id, source: comic.value.source || 'local' }], [tagId])
      await fetchComicDetail()
      await fetchAllTags()
      newTagName.value = ''
      showAddTag.value = false
      showSuccessToast('标签已添加')
    } else {
      showFailToast('添加失败')
    }
  } catch (e) {
    showFailToast('添加失败')
  } finally {
    tagAdding.value = false
  }
}

async function bindExistingTag(tag) {
  if (!tag?.id || currentTagIdSet.value.has(String(tag.id))) return
  tagAdding.value = true
  try {
    await tagApi.batchAddTags([{ id: comic.value.id, source: comic.value.source || 'local' }], [tag.id])
    await fetchComicDetail()
    newTagName.value = ''
    showAddTag.value = false
    showSuccessToast('标签已添加')
  } catch (e) {
    showFailToast('添加失败')
  } finally {
    tagAdding.value = false
  }
}

async function handleRemoveTag(tag) {
  try {
    await showConfirmDialog({ title: '移除标签', message: `确定移除「${tag.name}」吗？` })
  } catch { return }
  try {
    const comicData = [{ id: comic.value.id, source: comic.value.source || 'local' }]
    await tagApi.batchRemoveTags(comicData, [tag.id])
    await fetchComicDetail()
    showSuccessToast('标签已移除')
  } catch (e) {
    showFailToast('移除失败')
  }
}

onMounted(async () => {
  console.log('[Detail] onMounted, id:', route.params.id)
  await fetchComicDetail()
  if (route.query.autoread === '1' && comic.value) {
    // 先 await 清除 autoread 参数（此时没有其他导航竞争），再跳转阅读器
    await router.replace({ query: { ...route.query, autoread: undefined } })
    startReading()
    return
  }
  await fetchAllTags()
  await listStore.fetchLists('comic')
  updatePreviewColumns()
  previewLimit.value = previewColumns.value
  window.addEventListener('resize', onWindowResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onWindowResize)
})

function onWindowResize() {
  updatePreviewColumns()
}

watch(() => route.params.id, async (newId) => {
  console.log('[Detail] watch id:', newId)
  await fetchComicDetail()
})

watch(showListPopup, async (val) => {
  console.log('[Detail] showListPopup changed:', val)
  if (val) {
    await listStore.fetchLists('comic')
    console.log('[Detail] listStore.lists:', listStore.lists)
    console.log('[Detail] customLists:', customLists.value)
    if (comic.value) {
      selectedListIds.value = [...(comic.value.list_ids || [])]
      console.log('[Detail] selectedListIds initialized:', selectedListIds.value)
    }
  }
})
</script>

<style scoped>
.comic-detail {
  padding-bottom: 20px;
  background: transparent;
  border-radius: 12px;
  overflow: hidden;
}

.nav-icon {
  font-size: 20px;
  margin-left: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}

.nav-icon.active {
  color: #f5a21e;
}

.tag-add {
  cursor: pointer;
  opacity: 0.7;
}

.tag-add:hover {
  opacity: 1;
}

.tag-add-content {
  padding: 16px;
}

.tag-add-content :deep(.van-search) {
  padding: 0;
  background: transparent;
}

.tag-add-content :deep(.van-search__content) {
  background: var(--surface-1);
  border: 1px solid var(--border-soft);
}

.tag-option-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
  max-height: 260px;
  overflow-y: auto;
}

.tag-option {
  appearance: none;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  background: var(--surface-1);
  color: var(--text-primary);
  padding: 10px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  font: inherit;
  cursor: pointer;
  text-align: left;
}

.tag-option-name {
  font-weight: 700;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-option-count,
.tag-option-empty {
  color: var(--text-tertiary);
  font-size: 12px;
}

.tag-option-empty {
  padding: 16px 2px 4px;
  text-align: center;
}

.detail-content {
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  box-shadow: 0 16px 30px rgba(2, 8, 18, 0.38);
}

.cover-section {
  display: flex;
  flex-direction: column;
  padding: 16px;
  gap: 16px;
  background: linear-gradient(125deg, #2f74ff 0%, #1c49ad 65%, #12316f 100%);
  color: #fff;
}

.cover-main {
  display: flex;
  gap: 16px;
}

.cover {
  width: 120px;
  height: 160px;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  flex-shrink: 0;
  cursor: pointer;
  position: relative;
}

.cover-wrapper {
  position: relative;
  width: 120px;
  flex-shrink: 0;
}

.source-tag {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 2;
}

.info {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
}

.info-edit-btn {
  position: absolute;
  top: 0;
  right: 0;
  font-size: 18px;
  color: rgba(255, 255, 255, 0.75);
  cursor: pointer;
  padding: 4px;
  z-index: 1;
  transition: color var(--motion-fast) var(--ease-standard);
}

.info-edit-btn:hover {
  color: #fff;
}

.title {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 8px 0;
  line-height: 1.3;
  padding-right: 34px;
}

.author {
  font-size: 14px;
  margin: 0 0 12px 0;
  opacity: 0.9;
}

.author-link {
  color: #d7e8ff;
  cursor: pointer;
  transition: opacity var(--motion-fast) var(--ease-standard);
}

.author-link:hover {
  opacity: 0.86;
}

.author-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.author-row .author {
  margin: 0;
}

.stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.stat-item {
  font-size: 12px;
  background: rgba(255, 255, 255, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.24);
  padding: 4px 8px;
  border-radius: 999px;
}

.storage-path-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 12px;
  line-height: 1.4;
  color: rgba(255, 255, 255, 0.95);
}

.storage-path-label {
  flex-shrink: 0;
  font-weight: 600;
  opacity: 0.92;
}

.storage-path-value {
  min-width: 0;
  word-break: break-all;
  opacity: 0.9;
}

.detail-action-strip {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
  margin: 14px auto 0;
}

.detail-action-strip :deep(.van-button) {
  min-width: 112px;
  border: 0;
  border-radius: 999px;
  box-shadow: 0 10px 20px rgba(17, 27, 45, 0.12);
}

.score-section {
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  padding: 8px 14px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.score-display {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.score-summary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.score-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.9);
}

.score-star {
  color: #ffd36a;
  font-size: 15px;
}

.score-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 58px;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #ffc657 0%, #f78a1d 70%);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  box-shadow: 0 6px 12px rgba(245, 154, 34, 0.34);
}

.score-chip.is-empty {
  background: rgba(255, 255, 255, 0.24);
  color: rgba(255, 255, 255, 0.88);
  box-shadow: none;
}

.score-rate-wrap {
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: 2px;
  flex: 1;
  min-width: 0;
}

.score-rate {
  --van-rate-icon-size: 20px;
  margin: 0;
  width: max-content;
  white-space: nowrap;
}

.tags-section,
.desc-section,
.chapter-section,
.preview-section {
  padding: 16px;
  border-bottom: 1px solid rgba(73, 98, 146, 0.15);
}

.section-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: var(--text-strong);
}

.tags-section > .section-title,
.desc-section > .section-title,
.preview-section > .section-title {
  margin-bottom: 12px;
}

.section-hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag {
  cursor: pointer;
}

.desc {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
  margin: 0;
  white-space: pre-wrap;
}

.chapter-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 10px;
}

.chapter-card {
  appearance: none;
  -webkit-appearance: none;
  border: 1px solid var(--border-soft);
  border-radius: 16px;
  background: linear-gradient(180deg, var(--surface-1) 0%, var(--surface-2) 100%);
  color: var(--text-primary);
  width: 100%;
  font: inherit;
  padding: 14px 16px;
  text-align: left;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  transition:
    transform var(--motion-fast) var(--ease-standard),
    border-color var(--motion-fast) var(--ease-standard),
    box-shadow var(--motion-fast) var(--ease-standard),
    background-color var(--motion-fast) var(--ease-standard);
  box-shadow: 0 10px 22px rgba(17, 27, 45, 0.06);
  position: relative;
  overflow: hidden;
}

.chapter-card:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  box-shadow: 0 14px 28px rgba(17, 27, 45, 0.1);
}

.chapter-card.is-current {
  border-color: rgba(56, 118, 255, 0.32);
  background:
    linear-gradient(180deg, rgba(71, 124, 255, 0.08) 0%, var(--surface-2) 100%);
  box-shadow: 0 14px 30px rgba(38, 86, 189, 0.12);
}

.chapter-card.is-current::before {
  content: '';
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 4px;
  border-radius: 999px;
  background: linear-gradient(180deg, #5f9bff 0%, #2f74ff 100%);
}

.chapter-order {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: rgba(47, 116, 255, 0.09);
  border: 1px solid rgba(47, 116, 255, 0.12);
  color: #2f74ff;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  flex-shrink: 0;
}

.chapter-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chapter-title-row {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 10px;
}

.chapter-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-strong);
}

.chapter-current-tag {
  flex-shrink: 0;
}

.chapter-meta {
  font-size: 12px;
  color: var(--text-secondary);
}

.chapter-side {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  justify-self: end;
  min-width: 0;
}

.chapter-state {
  font-size: 12px;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.chapter-arrow {
  color: var(--text-tertiary);
  font-size: 15px;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

@media (min-width: 480px) {
  .preview-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (min-width: 768px) {
  .preview-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

@media (min-width: 1200px) {
  .preview-grid {
    grid-template-columns: repeat(5, 1fr);
  }
}

.preview-item {
  position: relative;
  cursor: pointer;
  border-radius: 10px;
  overflow: hidden;
  background: linear-gradient(145deg, #15243f 0%, #203659 100%);
}

.preview-image {
  width: 100%;
  height: auto;
  display: block;
}

.preview-page {
  position: absolute;
  bottom: 8px;
  left: 8px;
  background: rgba(16, 29, 57, 0.76);
  border: 1px solid rgba(255, 255, 255, 0.22);
  color: #fff;
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 999px;
}

.preview-hover-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
  opacity: 0;
  transition: opacity 0.2s;
}

.preview-item:hover .preview-hover-overlay {
  opacity: 1;
}

.preview-jump-btn {
  padding: 6px 14px;
  border: none;
  border-radius: 8px;
  background: var(--brand-500);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.preview-jump-btn:hover {
  background: var(--brand-600);
}

.preview-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}

.preview-action-btn {
  flex: 1;
  height: 38px;
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.preview-action-btn:hover {
  background: var(--surface-2);
  color: var(--text-primary);
}

.preview-action-btn--primary {
  background: var(--brand-500);
  border-color: transparent;
  color: #fff;
}

.preview-action-btn--primary:hover {
  opacity: 0.9;
}

.action-section {
  padding: 16px;
  text-align: center;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.action-buttons .van-button {
  min-width: 80px;
}

.read-button {
  width: 100%;
}

.edit-popup,
.tag-popup,
.list-popup {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.tag-select-list {
  flex: 1;
  overflow-y: auto;
}

.tag-count,
.list-count {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-left: 4px;
}

.list-action {
  padding: 16px;
}

@media (max-width: 767px) {
  .comic-detail {
    padding-bottom: 70px;
  }

  .detail-content {
    border-radius: 16px;
  }

  .cover-section {
    padding: 14px;
    gap: 12px;
  }

  .cover-main {
    gap: 12px;
  }

  .cover {
    width: 110px;
    height: 148px;
  }

  .cover-wrapper {
    width: 110px;
  }

  .score-section {
    padding: 10px 12px;
  }

  .score-display {
    flex-wrap: wrap;
    align-items: center;
  }

  .score-rate {
    --van-rate-icon-size: 17px;
  }

  .detail-action-strip {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    width: 100%;
    gap: 8px;
  }

  .detail-action-strip :deep(.van-button) {
    width: 100%;
    min-width: 0;
    padding-inline: 6px;
  }

  .action-buttons {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .action-buttons .van-button {
    width: 100%;
    min-width: 0;
  }

  .section-heading {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }

  .chapter-list {
    grid-template-columns: 1fr;
  }

  .chapter-card {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .chapter-side {
    grid-column: 2;
    justify-self: start;
    padding-left: 0;
  }
}

@media (min-width: 1024px) {
  .detail-content {
    margin: 0 auto;
  }
}
</style>
