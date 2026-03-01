<template>
  <div class="recommendation-detail">
    <van-nav-bar title="推荐漫画详情" left-text="返回" left-arrow @click-left="$router.back()">
      <template #right>
        <van-icon name="ellipsis" @click="showActionSheet = true" />
      </template>
    </van-nav-bar>

    <van-loading v-if="isLoading" type="spinner" color="#1989fa" />

    <div v-else-if="!recommendation" class="empty">
      <van-empty description="推荐漫画不存在" />
    </div>

    <div v-else class="detail-content">
      <div class="cover-section">
        <van-image
          :src="recommendation.cover_path"
          fit="cover"
          class="cover"
          lazy-load
          @click="startReading"
        />
        <div class="info">
          <h1 class="title">{{ recommendation.title }}</h1>
          <p class="author" v-if="recommendation.author">{{ recommendation.author }}</p>
          <p class="author" v-else>未知作者</p>

          <div class="stats">
            <span class="stat-item">总页数: {{ recommendation.total_page }}</span>
            <span class="stat-item">进度: {{ recommendation.current_page }}/{{ recommendation.total_page }}</span>
            <span class="stat-item">{{ progressPercent }}%</span>
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
              :max="12"
              :step="0.5"
              active-color="#ff9900"
              @change="handleScoreChange"
              class="score-slider"
            />
            <div class="score-labels">
              <span>1分</span>
              <span>12分</span>
            </div>
          </div>
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
            @click="filterByTag(tag.id)"
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

      <div class="desc-section" v-if="recommendation.desc">
        <h2 class="section-title">简介</h2>
        <p class="desc">{{ recommendation.desc }}</p>
      </div>

      <div class="preview-section">
        <h2 class="section-title">内容预览</h2>
        <div class="preview-grid">
          <div
            v-for="(url, index) in recommendation.preview_image_urls"
            :key="index"
            class="preview-item"
            @click="previewImage(index)"
          >
            <img
              :src="url"
              class="preview-image"
            />
            <span class="preview-page">第{{ recommendation.preview_pages[index] }}页</span>
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
        @change="onPreviewChange"
      />

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
        <van-button type="primary" size="large" @click="startReading" class="read-button">
          {{ recommendation.current_page > 1 ? '继续阅读' : '开始阅读' }}
        </van-button>
      </div>
    </div>

    <van-action-sheet
      v-model:show="showActionSheet"
      :actions="actions"
      @select="onActionSelect"
    />

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
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRecommendationStore, useTagStore, useListStore } from '@/stores'
import { recommendationApi } from '@/api'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'

const route = useRoute()
const router = useRouter()
const recommendationStore = useRecommendationStore()
const tagStore = useTagStore()
const listStore = useListStore()

// ============ State ============
const recommendation = ref(null)
const isLoading = ref(true)
const showActionSheet = ref(false)
const showTagPopup = ref(false)
const showListPopup = ref(false)
const showPreview = ref(false)
const previewIndex = ref(0)
const allTags = ref([])
const selectedTagIds = ref([])
const selectedListIds = ref([])
const scoreValue = ref(6)
const favoriteLoading = ref(false)

const actions = [
  { name: '绑定标签', value: 'tags' },
  { name: '移入回收站', value: 'trash', color: '#ee0a24' }
]

// ============ Computed ============
const recommendationId = computed(() => route.params.id)

const progressPercent = computed(() => {
  if (!recommendation.value || !recommendation.value.total_page || recommendation.value.total_page === 0) return 0
  return Math.round((recommendation.value.current_page / recommendation.value.total_page) * 100)
})

const previewImages = computed(() => {
  if (!recommendation.value || !recommendation.value.preview_image_urls) return []
  return recommendation.value.preview_image_urls
})

const isFavorited = computed(() => {
  return listStore.isFavorited(recommendation.value)
})

const customLists = computed(() => listStore.lists || [])

const isRead = computed(() => {
  if (!recommendation.value) return false
  return recommendation.value.current_page >= recommendation.value.total_page
})

// ============ Methods ============

/**
 * 获取推荐漫画详情
 */
async function fetchDetail() {
  const id = recommendationId.value
  isLoading.value = true

  try {
    const detail = await recommendationStore.fetchRecommendationDetail(id)
    if (detail) {
      recommendation.value = detail
      scoreValue.value = detail.score || 6
      selectedTagIds.value = detail.tag_ids || []
    }
  } catch (error) {
    console.error('获取推荐漫画详情失败:', error)
  } finally {
    isLoading.value = false
  }
}

/**
 * 获取所有标签
 */
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

/**
 * 开始阅读
 */
function startReading() {
  router.push(`/recommendation-reader/${recommendation.value.id}`)
}

/**
 * 预览图片
 */
function previewImage(index) {
  previewIndex.value = index
  showPreview.value = true
}

/**
 * 预览图片变化
 */
function onPreviewChange(index) {
  previewIndex.value = index
}

/**
 * 根据标签筛选
 */
function filterByTag(tagId) {
  router.push(`/recommendation?tagId=${tagId}`)
}

/**
 * 评分变化
 */
async function handleScoreChange(value) {
  try {
    const success = await recommendationStore.updateScore(recommendation.value.id, value)
    if (success) {
      recommendation.value.score = value
      showSuccessToast('评分保存成功')
    } else {
      showFailToast('评分保存失败')
    }
  } catch (error) {
    console.error('保存评分失败:', error)
    showFailToast('评分保存失败')
  }
}

/**
 * 操作菜单选择
 */
function onActionSelect(action) {
  showActionSheet.value = false
  if (action.value === 'tags') {
    showTagPopup.value = true
  } else if (action.value === 'trash') {
    handleMoveToTrash()
  }
}

async function handleMoveToTrash() {
  if (!recommendation.value) return
  
  try {
    await showConfirmDialog({
      title: '确认操作',
      message: '确定将此漫画移入回收站吗？'
    })
    
    const res = await recommendationApi.moveToTrash(recommendation.value.id)
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

/**
 * 切换标签选择
 */
function toggleTag(tagId) {
  const index = selectedTagIds.value.indexOf(tagId)
  if (index > -1) {
    selectedTagIds.value.splice(index, 1)
  } else {
    selectedTagIds.value.push(tagId)
  }
}

/**
 * 保存标签
 */
async function saveTags() {
  try {
    const success = await recommendationStore.bindTags(recommendation.value.id, selectedTagIds.value)
    if (success) {
      recommendationStore.clearCache('detail', recommendation.value.id)
      await fetchDetail()
      showTagPopup.value = false
      showSuccessToast('标签绑定成功')
    } else {
      showFailToast('标签绑定失败')
    }
  } catch (error) {
    console.error('标签绑定失败:', error)
    showFailToast('标签绑定失败')
  }
}

/**
 * 切换收藏状态
 */
async function handleToggleFavorite() {
  favoriteLoading.value = true
  try {
    const result = await listStore.toggleFavorite(recommendation.value.id)
    if (result !== null) {
      const FAVORITES_LIST_ID = 'list_favorites'
      if (result) {
        if (!recommendation.value.list_ids) {
          recommendation.value.list_ids = []
        }
        if (!recommendation.value.list_ids.includes(FAVORITES_LIST_ID)) {
          recommendation.value.list_ids.push(FAVORITES_LIST_ID)
        }
      } else {
        if (recommendation.value.list_ids) {
          recommendation.value.list_ids = recommendation.value.list_ids.filter(id => id !== FAVORITES_LIST_ID)
        }
      }
      recommendationStore.clearCache('detail', recommendation.value.id)
    }
  } finally {
    favoriteLoading.value = false
  }
}

/**
 * 切换清单项
 */
function toggleListItem(listId) {
  const index = selectedListIds.value.indexOf(listId)
  if (index > -1) {
    selectedListIds.value.splice(index, 1)
  } else {
    selectedListIds.value.push(listId)
  }
}

/**
 * 添加到清单
 */
async function addToLists() {
  if (selectedListIds.value.length === 0 && (!recommendation.value.list_ids || recommendation.value.list_ids.length === 0)) {
    showFailToast('请选择清单')
    return
  }

  try {
    const currentListIds = recommendation.value.list_ids || []
    const toAdd = selectedListIds.value.filter(id => !currentListIds.includes(id))
    const toRemove = currentListIds.filter(id => !selectedListIds.value.includes(id))

    let addCount = 0
    let removeCount = 0

    for (const listId of toAdd) {
      const result = await listStore.bindComics(listId, [recommendation.value.id])
      if (result) addCount++
    }

    for (const listId of toRemove) {
      const result = await listStore.removeComics(listId, [recommendation.value.id])
      if (result) removeCount++
    }

    if (addCount > 0 || removeCount > 0) {
      showListPopup.value = false
      selectedListIds.value = []
      recommendationStore.clearCache('detail', recommendation.value.id)
      await fetchDetail()
      await listStore.fetchLists()

      let message = ''
      if (addCount > 0) message += `加入${addCount}个清单 `
      if (removeCount > 0) message += `移出${removeCount}个清单`
      showSuccessToast(message.trim())
    } else if (toAdd.length === 0 && toRemove.length === 0) {
      showSuccessToast('清单无变化')
      showListPopup.value = false
    }
  } catch (error) {
    console.error('addToLists error:', error)
    showFailToast('操作失败')
  }
}

/**
 * 标记已读
 */
async function markAsRead() {
  try {
    if (isRead.value) {
      await recommendationStore.saveProgress(recommendation.value.id, 1)
      recommendation.value.current_page = 1
      showSuccessToast('已标记为未读')
    } else {
      await recommendationStore.saveProgress(recommendation.value.id, recommendation.value.total_page)
      recommendation.value.current_page = recommendation.value.total_page
      showSuccessToast('已标记为已读')
    }
  } catch (error) {
    showFailToast('标记失败')
  }
}

// ============ Lifecycle ============
onMounted(async () => {
  await fetchDetail()
  await fetchAllTags()
  await listStore.fetchLists()
})

watch(() => route.params.id, async (newId) => {
  await fetchDetail()
})

watch(showListPopup, async (val) => {
  if (val) {
    await listStore.fetchLists()
    if (recommendation.value) {
      selectedListIds.value = [...(recommendation.value.list_ids || [])]
    }
  }
})
</script>

<style scoped>
.recommendation-detail {
  padding-bottom: 20px;
  min-height: 100vh;
  background: #f5f5f5;
}

.empty {
  padding: 40px 0;
}

.detail-content {
  background: #fff;
}

.cover-section {
  display: flex;
  padding: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
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
}

.info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.title {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.3;
}

.author {
  margin: 0 0 12px 0;
  font-size: 14px;
  opacity: 0.9;
}

.stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.stat-item {
  font-size: 12px;
  background: rgba(255, 255, 255, 0.2);
  padding: 4px 8px;
  border-radius: 4px;
}

.score-section {
  margin-top: auto;
}

.score-display {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.score-label {
  font-size: 14px;
  margin-right: 8px;
}

.score-value {
  font-size: 20px;
  font-weight: bold;
  color: #ff9900;
}

.score-value.no-score {
  font-size: 14px;
  color: #ccc;
}

.score-slider {
  margin: 8px 0;
}

.score-labels {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  opacity: 0.7;
}

.tags-section,
.desc-section,
.preview-section {
  padding: 16px;
  border-bottom: 1px solid #eee;
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
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
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: #666;
  white-space: pre-wrap;
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
  border-radius: 8px;
  overflow: hidden;
  background: #f0f0f0;
}

.preview-image {
  width: 100%;
  height: auto;
  display: block;
}

.preview-page {
  position: absolute;
  bottom: 4px;
  left: 4px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
}

.action-section {
  padding: 16px;
  text-align: center;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.action-buttons .van-button {
  min-width: 80px;
}

.read-button {
  width: 100%;
}

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
  margin-left: 4px;
  color: #999;
  font-size: 12px;
}

.list-action {
  padding: 12px 16px;
  border-top: 1px solid #eee;
}
</style>