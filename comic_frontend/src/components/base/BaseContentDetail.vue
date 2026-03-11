<template>
  <div class="base-content-detail">
    <van-nav-bar :title="pageTitle" left-text="返回" left-arrow @click-left="$router.back()">
      <template #right>
        <van-icon name="ellipsis" @click="showActionSheet = true" />
      </template>
    </van-nav-bar>
    
    <van-loading v-if="loading" type="spinner" color="#1989fa" />
    
    <div v-else-if="!item" class="empty">
      <van-empty :description="`${contentTypeLabel}不存在`" />
    </div>
    
    <div v-else class="detail-content">
      <div class="cover-section">
        <van-image 
          :src="coverUrl" 
          fit="cover" 
          class="cover" 
          lazy-load
          @click="onCoverClick"
        >
          <template #loading>
            <van-loading class="loading" />
          </template>
        </van-image>
        <van-tag
          v-if="item.source === 'preview'"
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
        <div class="info">
          <h1 class="title">{{ item.title }}</h1>
          <div class="author-row">
            <p class="author" v-if="authorField">
              <span class="author-link" @click="filterByAuthor(authorField)">{{ authorField }}</span>
            </p>
            <p class="author" v-else>未知</p>
            <van-button 
              v-if="authorField && !isSubscribed" 
              size="mini" 
              type="primary" 
              plain
              @click="subscribeAuthor"
              :loading="subscribing"
            >
              订阅
            </van-button>
            <van-tag v-else-if="authorField && isSubscribed" type="success" size="medium">
              已订阅
            </van-tag>
          </div>
          
          <div class="stats">
            <span class="stat-item">ID: {{ item.id }}</span>
            <span v-if="item.total_page" class="stat-item">总页数: {{ item.total_page }}</span>
            <span v-if="item.current_page !== undefined" class="stat-item">进度: {{ item.current_page }}/{{ item.total_page || '-' }}</span>
            <span v-if="progressPercent > 0" class="stat-item">{{ progressPercent }}%</span>
          </div>
          
          <div class="score-section">
            <div class="score-display">
              <span class="score-label">评分:</span>
              <span class="score-value" v-if="item.score">{{ item.score }}</span>
              <span class="score-value no-score" v-else>未评分</span>
            </div>
            <van-slider 
              v-model="scoreValue" 
              :min="1" 
              :max="maxScore" 
              :step="0.5"
              active-color="#ff9900"
              @change="handleScoreChange"
              class="score-slider"
            />
            <div class="score-labels">
              <span>1分</span>
              <span>{{ maxScore }}分</span>
            </div>
          </div>
        </div>
      </div>
      
      <div v-if="item.tags && item.tags.length > 0" class="tags-section">
        <h2 class="section-title">标签</h2>
        <div class="tags-container">
          <van-tag 
            v-for="tag in item.tags" 
            :key="tag.id" 
            size="medium" 
            type="primary" 
            plain 
            class="tag"
            @click="filterByTag(tag.id)"
          >
            {{ tag.name }}
          </van-tag>
        </div>
      </div>
      
      <div class="desc-section" v-if="item.desc">
        <h2 class="section-title">简介</h2>
        <p class="desc">{{ item.desc }}</p>
      </div>
      
      <slot name="extra-content" :item="item"></slot>
      
      <div class="action-section">
        <div class="action-buttons">
          <van-button 
            :type="isFavorited ? 'warning' : 'default'" 
            size="small"
            @click="handleToggleFavorite"
            :loading="favoriteLoading"
          >
            <van-icon :name="isFavorited ? 'star' : 'star-o'" />
            {{ isFavorited ? '已收藏' : '收藏' }}
          </van-button>
          <van-button 
            type="default" 
            size="small"
            @click="showListPopup = true"
          >
            <van-icon name="add-o" />
            加入清单
          </van-button>
          <van-button 
            v-if="showMarkRead"
            :type="isRead ? 'success' : 'default'" 
            size="small"
            @click="markAsRead"
          >
            <van-icon :name="isRead ? 'passed' : 'circle'" />
            {{ isRead ? '已读' : '标记已读' }}
          </van-button>
          <van-button 
            type="danger" 
            size="small"
            @click="handleMoveToTrash"
          >
            <van-icon name="delete-o" />
            移入回收站
          </van-button>
        </div>
        <van-button 
          v-if="showReadButton" 
          type="primary" 
          size="large" 
          @click="startReading" 
          class="read-button"
        >
          {{ item.current_page > 1 ? '继续阅读' : '开始阅读' }}
        </van-button>
      </div>
    </div>
    
    <van-action-sheet 
      v-model:show="showActionSheet" 
      :actions="actions" 
      @select="onActionSelect"
    />
    
    <slot name="extra-popups" :item="item"></slot>
    
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
                <span class="list-count">({{ getListCount(list) }})</span>
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { getCoverUrl, FAVORITES_COMIC_LIST_ID, FAVORITES_VIDEO_LIST_ID } from '@/utils/helpers'

const props = defineProps({
  contentType: {
    type: String,
    required: true,
    validator: (v) => ['comic', 'video'].includes(v)
  },
  store: {
    type: Object,
    required: true
  },
  listStore: {
    type: Object,
    required: true
  },
  authorStore: {
    type: Object,
    default: null
  },
  tagStore: {
    type: Object,
    default: null
  },
  api: {
    type: Object,
    required: true
  },
  buildCoverUrl: {
    type: Function,
    default: null
  },
  maxScore: {
    type: Number,
    default: 12
  },
  showReadButton: {
    type: Boolean,
    default: true
  },
  showMarkRead: {
    type: Boolean,
    default: true
  },
  libraryRoute: {
    type: String,
    default: 'Library'
  },
  previewRoute: {
    type: String,
    default: 'Preview'
  },
  readerRoute: {
    type: String,
    default: 'Reader'
  }
})

const emit = defineEmits(['item-loaded', 'score-changed', 'favorite-changed', 'action'])

const route = useRoute()
const router = useRouter()

const item = ref(null)
const loading = ref(true)
const showActionSheet = ref(false)
const showListPopup = ref(false)
const selectedListIds = ref([])
const scoreValue = ref(6)
const favoriteLoading = ref(false)
const subscribing = ref(false)
const isSubscribed = ref(false)

const isVideo = computed(() => props.contentType === 'video')

const contentTypeLabel = computed(() => isVideo.value ? '视频' : '漫画')

const pageTitle = computed(() => `${contentTypeLabel.value}详情`)

const authorField = computed(() => item.value?.author || item.value?.creator)

const coverUrl = computed(() => {
  if (!item.value) return ''
  if (props.buildCoverUrl) {
    return props.buildCoverUrl(item.value.cover_path)
  }
  return getCoverUrl(item.value.cover_path)
})

const progressPercent = computed(() => {
  if (!item.value || !item.value.total_page || item.value.total_page === 0) return 0
  return Math.round((item.value.current_page / item.value.total_page) * 100)
})

const isFavorited = computed(() => {
  if (!item.value) return false
  return isVideo.value 
    ? props.listStore.isFavoritedVideo(item.value)
    : props.listStore.isFavorited(item.value)
})

const customLists = computed(() => props.listStore.lists || [])

const isRead = computed(() => {
  if (!item.value) return false
  return item.value.current_page >= item.value.total_page
})

const favoritesListId = computed(() => 
  isVideo.value ? FAVORITES_VIDEO_LIST_ID : FAVORITES_COMIC_LIST_ID
)

const actions = computed(() => [
  { name: '编辑信息', value: 'edit' },
  { name: '绑定标签', value: 'tags' },
  { name: '移入回收站', value: 'trash', color: '#ee0a24' }
])

function getListCount(list) {
  return isVideo.value ? (list.video_count || 0) : (list.comic_count || 0)
}

async function fetchDetail() {
  const id = route.params.id
  loading.value = true
  
  try {
    const detail = await props.store.fetchDetail(id)
    if (detail) {
      item.value = detail
      scoreValue.value = detail.score || 6
      selectedListIds.value = detail.list_ids || []
      await checkSubscriptionStatus()
      emit('item-loaded', detail)
    }
  } catch (error) {
    console.error('获取详情失败:', error)
  } finally {
    loading.value = false
  }
}

async function checkSubscriptionStatus() {
  if (!props.authorStore || !authorField.value) return
  
  try {
    const authors = props.authorStore.actors || props.authorStore.authors || []
    isSubscribed.value = authors.some(
      author => author.name.toLowerCase() === authorField.value.toLowerCase()
    )
  } catch (error) {
    console.error('检查订阅状态失败:', error)
  }
}

async function subscribeAuthor() {
  if (!authorField.value || subscribing.value || !props.authorStore) return
  
  subscribing.value = true
  try {
    const result = await props.authorStore.subscribe(authorField.value)
    if (result.success) {
      isSubscribed.value = true
      showSuccessToast('订阅成功')
    } else {
      showFailToast(result.message || '订阅失败')
    }
  } catch (error) {
    console.error('订阅失败:', error)
    showFailToast('订阅失败')
  } finally {
    subscribing.value = false
  }
}

function filterByAuthor(author) {
  const routeName = item.value.source === 'preview' ? props.previewRoute : props.libraryRoute
  router.push({ name: routeName, query: { author } })
}

function filterByTag(tagId) {
  const routeName = item.value.source === 'preview' ? props.previewRoute : props.libraryRoute
  router.push({ name: routeName, query: { tagId } })
}

async function handleScoreChange(value) {
  try {
    const success = await props.store.updateScore(item.value.id, value)
    if (success) {
      item.value.score = value
      showSuccessToast('评分保存成功')
      emit('score-changed', value)
    } else {
      showFailToast('评分保存失败')
    }
  } catch (error) {
    console.error('保存评分失败:', error)
    showFailToast('评分保存失败')
  }
}

function onActionSelect(action) {
  showActionSheet.value = false
  emit('action', action.value, item.value)
  
  if (action.value === 'trash') {
    handleMoveToTrash()
  }
}

async function handleMoveToTrash() {
  if (!item.value) return
  
  try {
    await showConfirmDialog({
      title: '确认操作',
      message: `确定将此${contentTypeLabel.value}移入回收站吗？`
    })
    
    const success = await props.store.moveToTrash(item.value.id)
    if (success) {
      showSuccessToast('已移入回收站')
      router.back()
    } else {
      showFailToast('操作失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      showFailToast('操作失败')
    }
  }
}

async function handleToggleFavorite() {
  favoriteLoading.value = true
  try {
    const result = isVideo.value
      ? await props.listStore.toggleFavoriteVideo(item.value.id, item.value.source || 'local')
      : await props.listStore.toggleFavorite(item.value.id, item.value.source || 'local')
    
    if (result !== null) {
      if (result) {
        item.value.list_ids = item.value.list_ids || []
        if (!item.value.list_ids.includes(favoritesListId.value)) {
          item.value.list_ids.push(favoritesListId.value)
        }
      } else {
        item.value.list_ids = (item.value.list_ids || []).filter(id => id !== favoritesListId.value)
      }
      emit('favorite-changed', result)
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
  if (selectedListIds.value.length === 0 && (!item.value.list_ids || item.value.list_ids.length === 0)) {
    showFailToast('请选择清单')
    return
  }
  
  try {
    const currentListIds = item.value.list_ids || []
    const toAdd = selectedListIds.value.filter(id => !currentListIds.includes(id))
    const toRemove = currentListIds.filter(id => !selectedListIds.value.includes(id))
    
    let addCount = 0
    let removeCount = 0
    const source = item.value.source || 'local'
    
    for (const listId of toAdd) {
      const result = isVideo.value
        ? await props.listStore.bindVideos(listId, [item.value.id], source)
        : await props.listStore.bindComics(listId, [item.value.id], source)
      if (result) addCount++
    }
    
    for (const listId of toRemove) {
      const result = isVideo.value
        ? await props.listStore.removeVideos(listId, [item.value.id], source)
        : await props.listStore.removeComics(listId, [item.value.id], source)
      if (result) removeCount++
    }
    
    if (addCount > 0 || removeCount > 0) {
      showListPopup.value = false
      selectedListIds.value = []
      await fetchDetail()
      await props.listStore.fetchLists(isVideo.value ? 'video' : 'comic')
      
      let message = ''
      if (addCount > 0) message += `加入${addCount}个清单 `
      if (removeCount > 0) message += `移出${removeCount}个清单`
      showSuccessToast(message.trim())
    } else if (toAdd.length === 0 && toRemove.length === 0) {
      showSuccessToast('清单无变化')
      showListPopup.value = false
    }
  } catch (error) {
    console.error('操作清单失败:', error)
    showFailToast('操作失败')
  }
}

async function markAsRead() {
  try {
    if (isRead.value) {
      await props.store.saveProgress(item.value.id, 1)
      item.value.current_page = 1
      showSuccessToast('已标记为未读')
    } else {
      await props.store.saveProgress(item.value.id, item.value.total_page)
      item.value.current_page = item.value.total_page
      showSuccessToast('已标记为已读')
    }
  } catch (error) {
    showFailToast('标记失败')
  }
}

function startReading() {
  router.push({ name: props.readerRoute, params: { id: item.value.id } })
}

function onCoverClick() {
  emit('action', 'cover-click', item.value)
}

onMounted(async () => {
  await props.listStore.fetchLists(isVideo.value ? 'video' : 'comic')
  if (props.authorStore) {
    await props.authorStore.fetchList()
  }
  await fetchDetail()
})

watch(showListPopup, async (val) => {
  if (val && item.value) {
    selectedListIds.value = [...(item.value.list_ids || [])]
  }
})
</script>

<style scoped>
.base-content-detail {
  min-height: 100vh;
  background: #f5f5f5;
}

.cover-section {
  display: flex;
  padding: 16px;
  background: #fff;
}

.cover {
  width: 120px;
  height: 160px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
}

.source-tag {
  position: absolute;
  top: 8px;
  left: 8px;
}

.info {
  flex: 1;
  margin-left: 16px;
  display: flex;
  flex-direction: column;
}

.title {
  font-size: 16px;
  font-weight: bold;
  margin: 0 0 8px 0;
  line-height: 1.4;
}

.author-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.author {
  margin: 0;
  font-size: 14px;
  color: #666;
}

.author-link {
  color: #1989fa;
  cursor: pointer;
}

.stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.stat-item {
  font-size: 12px;
  color: #999;
}

.score-section {
  margin-top: auto;
}

.score-display {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.score-label {
  font-size: 14px;
  color: #666;
}

.score-value {
  font-size: 18px;
  font-weight: bold;
  color: #ff9900;
}

.score-value.no-score {
  color: #999;
  font-size: 14px;
  font-weight: normal;
}

.score-slider {
  margin: 8px 0;
}

.score-labels {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #999;
}

.tags-section,
.desc-section {
  padding: 16px;
  background: #fff;
  margin-top: 10px;
}

.section-title {
  font-size: 14px;
  font-weight: bold;
  margin: 0 0 12px 0;
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
  color: #666;
  margin: 0;
}

.action-section {
  padding: 16px;
  background: #fff;
  margin-top: 10px;
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.action-buttons .van-button {
  flex: 1;
  min-width: 80px;
}

.read-button {
  margin-top: 8px;
}

.list-popup {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.list-count {
  font-size: 12px;
  color: #999;
  margin-left: 4px;
}

.list-action {
  padding: 16px;
}
</style>
