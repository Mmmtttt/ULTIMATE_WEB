<template>
  <div class="video-recommendation-detail">
    <van-nav-bar title="推荐视频详情" left-text="返回" left-arrow @click-left="$router.back()">
      <template #right>
        <van-icon name="ellipsis" @click="showActionSheet = true" />
      </template>
    </van-nav-bar>

    <van-loading v-if="isLoading" type="spinner" color="#1989fa" />

    <div v-else-if="!recommendation" class="empty">
      <van-empty description="推荐视频不存在" />
    </div>

    <div v-else class="detail-content">
      <div class="cover-section">
        <van-image
          :src="getCoverUrl(recommendation.cover_path)"
          fit="cover"
          class="cover"
          lazy-load
        />
        <div class="info">
          <h1 class="title">{{ recommendation.title }}</h1>
          <p class="code" v-if="recommendation.code">{{ recommendation.code }}</p>

          <div class="stats">
            <span class="stat-item">ID: {{ recommendation.id }}</span>
            <span v-if="recommendation.date" class="stat-item">日期: {{ recommendation.date }}</span>
            <span v-if="recommendation.series" class="stat-item">系列: {{ recommendation.series }}</span>
          </div>

          <div class="score-section">
            <div class="score-display">
              <span class="score-label">评分:</span>
              <span class="score-value" v-if="recommendation.score">{{ recommendation.score }}</span>
              <span class="score-value no-score" v-else>未评分</span>
            </div>
            <van-slider
              v-model="scoreValue"
              :min="1"
              :max="10"
              :step="0.5"
              active-color="#ff9900"
              @change="handleScoreChange"
              class="score-slider"
            />
            <div class="score-labels">
              <span>1分</span>
              <span>10分</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="recommendation.actors && recommendation.actors.length > 0" class="actors-section">
        <h2 class="section-title">演员</h2>
        <div class="actors-container">
          <van-tag
            v-for="actor in recommendation.actors"
            :key="actor"
            size="medium"
            type="primary"
            plain
            class="actor"
            @click="filterByActor(actor)"
          >
            {{ actor }}
          </van-tag>
        </div>
      </div>

      <div class="tags-section">
        <h2 class="section-title">标签</h2>
        <div class="tags-container">
          <van-tag
            v-for="tag in recommendation.tags"
            :key="tag.id"
            size="medium"
            type="primary"
            plain
            class="tag"
          >
            {{ tag.name }}
          </van-tag>
          <van-tag
            v-if="!recommendation.tags || recommendation.tags.length === 0"
            size="medium"
            type="default"
          >
            暂无标签
          </van-tag>
        </div>
      </div>

      <div v-if="recommendation.thumbnail_images && recommendation.thumbnail_images.length > 0" class="preview-section">
        <h2 class="section-title">截图预览</h2>
        <div class="preview-grid">
          <div
            v-for="(url, index) in recommendation.thumbnail_images"
            :key="index"
            class="preview-item"
            @click="previewImage(index)"
          >
            <img
              :src="url"
              class="preview-image"
            />
          </div>
        </div>
      </div>

      <!-- 图片预览 -->
      <van-image-preview
        v-model:show="showPreview"
        :images="previewImages"
        :start-position="previewIndex"
        :closeable="true"
        close-icon="close"
      />

      <div class="action-section">
        <div class="action-buttons">
          <van-button
            :type="isFavoritedVideo ? 'warning' : 'default'"
            size="small"
            @click="handleToggleFavorite"
            :loading="favoriteLoading"
          >
            <van-icon :name="isFavoritedVideo ? 'star' : 'star-o'" />
            {{ isFavoritedVideo ? '已收藏' : '收藏' }}
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
            type="danger"
            size="small"
            @click="handleMoveToTrash"
          >
            <van-icon name="delete-o" />
            移入回收站
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
                <span class="list-count">({{ list.video_count || 0 }})</span>
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
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useVideoRecommendationStore, useTagStore, useListStore } from '@/stores'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'

const route = useRoute()
const router = useRouter()
const videoRecommendationStore = useVideoRecommendationStore()
const tagStore = useTagStore()
const listStore = useListStore()

// ============ State ============
const recommendation = ref(null)
const isLoading = ref(true)
const showActionSheet = ref(false)
const showListPopup = ref(false)
const showPreview = ref(false)
const previewIndex = ref(0)
const selectedListIds = ref([])
const scoreValue = ref(5)
const favoriteLoading = ref(false)

const actions = [
  { name: '移入回收站', value: 'trash', color: '#ee0a24' }
]

// ============ Computed ============
const recommendationId = computed(() => route.params.id)

const previewImages = computed(() => {
  if (!recommendation.value || !recommendation.value.thumbnail_images) return []
  return recommendation.value.thumbnail_images
})

const isFavoritedVideo = computed(() => {
  return listStore.isFavoritedVideo(recommendation.value)
})

const customLists = computed(() => listStore.lists || [])

// ============ Methods ============

function getCoverUrl(coverPath) {
  if (!coverPath) return ''
  if (coverPath.startsWith('http')) return coverPath
  if (coverPath.startsWith('/static/')) return coverPath
  if (coverPath.startsWith('/')) return coverPath
  return `/${coverPath}`
}

function filterByActor(actorName) {
  router.push({ name: 'Library', query: { author: actorName } })
}

async function fetchDetail() {
  const id = recommendationId.value
  isLoading.value = true
  
  try {
    const result = await videoRecommendationStore.fetchRecommendationDetail(id)
    if (result) {
      recommendation.value = result
      if (result.score) {
        scoreValue.value = result.score
      }
      const currentListIds = result.list_ids || []
      selectedListIds.value = customLists.value
        .filter(list => currentListIds.includes(list.id))
        .map(list => list.id)
    } else {
      showFailToast('获取详情失败')
    }
  } catch (e) {
    console.error('获取详情失败:', e)
    showFailToast('获取详情失败')
  } finally {
    isLoading.value = false
  }
}

function previewImage(index) {
  previewIndex.value = index
  showPreview.value = true
}

async function handleScoreChange(value) {
  try {
    const result = await videoRecommendationStore.updateScore(recommendationId.value, value)
    if (result) {
      recommendation.value.score = value
      showSuccessToast('评分更新成功')
    } else {
      showFailToast('评分更新失败')
    }
  } catch (e) {
    console.error('评分更新失败:', e)
    showFailToast('评分更新失败')
  }
}

async function handleToggleFavorite() {
  favoriteLoading.value = true
  try {
    const result = await listStore.toggleFavoriteVideo(recommendationId.value, 'preview')
    if (result !== null) {
      const FAVORITES_LIST_ID = 'list_favorites_video'
      if (result) {
        recommendation.value.list_ids = recommendation.value.list_ids || []
        if (!recommendation.value.list_ids.includes(FAVORITES_LIST_ID)) {
          recommendation.value.list_ids.push(FAVORITES_LIST_ID)
        }
      } else {
        recommendation.value.list_ids = (recommendation.value.list_ids || []).filter(id => id !== FAVORITES_LIST_ID)
      }
    }
  } catch (e) {
    console.error('收藏操作失败:', e)
    showFailToast('操作失败')
  } finally {
    favoriteLoading.value = false
  }
}

async function handleMoveToTrash() {
  try {
    await showConfirmDialog({
      title: '确认操作',
      message: '确定将该视频移入回收站吗？'
    })
    
    const result = await videoRecommendationStore.moveToTrash(recommendationId.value)
    if (result) {
      showSuccessToast('已移入回收站')
      router.back()
    } else {
      showFailToast('操作失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      console.error('移入回收站失败:', e)
      showFailToast('操作失败')
    }
  }
}

function onActionSelect(action) {
  showActionSheet.value = false
  if (action.value === 'trash') {
    handleMoveToTrash()
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
  const currentListIds = recommendation.value?.list_ids || []
  const toAdd = selectedListIds.value.filter(id => !currentListIds.includes(id))
  const toRemove = currentListIds.filter(id => !selectedListIds.value.includes(id))

  let addCount = 0
  let removeCount = 0

  try {
    for (const listId of toAdd) {
      const result = await listStore.bindVideos(listId, [recommendationId.value], 'preview')
      if (result) addCount++
    }

    for (const listId of toRemove) {
      const result = await listStore.removeVideos(listId, [recommendationId.value], 'preview')
      if (result) removeCount++
    }

    if (addCount > 0 || removeCount > 0) {
      recommendation.value.list_ids = selectedListIds.value
      showListPopup.value = false
      await listStore.fetchLists('video')

      let message = ''
      if (addCount > 0) message += `加入${addCount}个清单 `
      if (removeCount > 0) message += `移出${removeCount}个清单`
      showSuccessToast(message.trim())
    } else if (toAdd.length === 0 && toRemove.length === 0) {
      showSuccessToast('清单无变化')
      showListPopup.value = false
    }
  } catch (e) {
    console.error('保存失败:', e)
    showFailToast('操作失败')
  }
}

// ============ Lifecycle ============
onMounted(async () => {
  await listStore.fetchLists('video')
  await fetchDetail()
})

watch(recommendationId, () => {
  fetchDetail()
})

watch(showListPopup, async (val) => {
  if (val) {
    await listStore.fetchLists('video')
    if (recommendation.value) {
      const currentListIds = recommendation.value.list_ids || []
      selectedListIds.value = [...currentListIds]
    }
  }
})
</script>

<style scoped>
.video-recommendation-detail {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 20px;
}

.empty {
  padding: 40px 0;
}

.detail-content {
  background: #fff;
  padding-bottom: 20px;
}

.cover-section {
  display: flex;
  padding: 16px;
  gap: 16px;
  border-bottom: 8px solid #f5f5f5;
}

.cover {
  width: 120px;
  height: 180px;
  border-radius: 8px;
  flex-shrink: 0;
}

.info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 8px 0;
  line-height: 1.4;
}

.code {
  font-size: 14px;
  color: #666;
  margin: 0 0 8px 0;
}

.stats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
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
  font-weight: 600;
  color: #ff9900;
}

.score-value.no-score {
  color: #999;
  font-weight: 400;
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

.actors-section,
.tags-section,
.preview-section {
  padding: 16px;
  border-bottom: 8px solid #f5f5f5;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 12px 0;
}

.actors-container,
.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.actor,
.tag {
  margin: 0;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.preview-item {
  aspect-ratio: 16/9;
  border-radius: 4px;
  overflow: hidden;
}

.preview-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.action-section {
  padding: 16px;
}

.action-buttons {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.action-buttons .van-button {
  flex: 1;
}

.list-popup {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.tag-popup {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.tag-select-list {
  flex: 1;
  overflow-y: auto;
}

.tag-count {
  font-size: 12px;
  color: #999;
  margin-left: 8px;
}

.list-count {
  font-size: 12px;
  color: #999;
  margin-left: 8px;
}

.list-action {
  padding: 16px;
}
</style>
