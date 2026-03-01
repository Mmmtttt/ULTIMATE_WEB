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
            v-for="(page, index) in recommendation.preview_pages"
            :key="index"
            class="preview-item"
            @click="startReadingFromPage(page)"
          >
            <img
              :src="getPreviewImageUrl(page)"
              class="preview-image"
            />
            <span class="preview-page">第{{ page }}页</span>
          </div>
        </div>
      </div>

      <div class="action-section">
        <van-button
          type="primary"
          size="large"
          block
          @click="startReading"
        >
          开始阅读
        </van-button>
        <van-button
          :type="recommendation.is_favorited ? 'danger' : 'default'"
          size="large"
          block
          @click="toggleFavorite"
        >
          {{ recommendation.is_favorited ? '取消收藏' : '加入收藏' }}
        </van-button>
      </div>
    </div>

    <!-- 操作菜单 -->
    <van-action-sheet
      v-model:show="showActionSheet"
      :actions="actions"
      @select="onActionSelect"
      cancel-text="取消"
    />

    <!-- 标签选择弹窗 -->
    <van-popup
      v-model:show="showTagPicker"
      position="bottom"
      round
      :style="{ height: '70%' }"
    >
      <div class="tag-picker">
        <van-nav-bar title="选择标签" left-text="关闭" @click-left="showTagPicker = false">
          <template #right>
            <van-button type="primary" size="small" @click="confirmTagSelection">确定</van-button>
          </template>
        </van-nav-bar>
        <TagFilter
          :tags="availableTags"
          :selected-ids="selectedTagIds"
          @change="selectedTagIds = $event"
        />
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import { useRecommendationStore, useTagStore, useListStore } from '@/stores'
import TagFilter from '@/components/tag/TagFilter.vue'

const route = useRoute()
const router = useRouter()
const recommendationStore = useRecommendationStore()
const tagStore = useTagStore()
const listStore = useListStore()

// ============ State ============
const showActionSheet = ref(false)
const showTagPicker = ref(false)
const selectedTagIds = ref([])

// ============ Computed ============
const recommendationId = computed(() => route.params.id)
const recommendation = computed(() => recommendationStore.currentRecommendationInfo)
const isLoading = computed(() => recommendationStore.loading)
const availableTags = computed(() => tagStore.tags)

const scoreValue = computed({
  get: () => recommendation.value?.score || 0,
  set: (val) => {}
})

const progressPercent = computed(() => {
  if (!recommendation.value || recommendation.value.total_page === 0) return 0
  return Math.round((recommendation.value.current_page / recommendation.value.total_page) * 100)
})

const actions = [
  { name: '编辑标签', value: 'edit_tags' },
  { name: '添加到清单', value: 'add_to_list' },
  { name: '删除', value: 'delete', color: '#ee0a24' }
]

// ============ Methods ============

/**
 * 获取推荐漫画详情
 */
async function fetchDetail() {
  console.log('[RecommendationDetail] 获取详情:', recommendationId.value)
  await recommendationStore.fetchRecommendationDetail(recommendationId.value)
  if (recommendation.value) {
    selectedTagIds.value = recommendation.value.tag_ids || []
  }
}

/**
 * 开始阅读
 */
function startReading() {
  console.log('[RecommendationDetail] 开始阅读:', recommendationId.value)
  router.push(`/recommendation-reader/${recommendationId.value}`)
}

/**
 * 从指定页开始阅读
 */
function startReadingFromPage(page) {
  console.log('[RecommendationDetail] 从第', page, '页开始阅读')
  router.push(`/recommendation-reader/${recommendationId.value}?page=${page}`)
}

/**
 * 获取预览图片 URL
 * 推荐漫画的图片存储在图床，直接返回 URL
 */
function getPreviewImageUrl(page) {
  // 假设图片 URL 格式为: base_url/001.jpg, base_url/002.jpg, ...
  const baseUrl = recommendation.value?.cover_path?.replace(/\/[^\/]*$/, '') || ''
  return `${baseUrl}/${String(page).padStart(3, '0')}.jpg`
}

/**
 * 评分变化
 */
async function handleScoreChange(value) {
  console.log('[RecommendationDetail] 更新评分:', value)
  const success = await recommendationStore.updateScore(recommendationId.value, value)
  if (success) {
    showToast('评分已更新')
  } else {
    showToast('评分更新失败')
  }
}

/**
 * 切换收藏状态
 */
async function toggleFavorite() {
  console.log('[RecommendationDetail] 切换收藏状态')
  const isFavorited = recommendation.value.is_favorited

  if (isFavorited) {
    // 取消收藏 - 从收藏清单中移除
    await listStore.removeComicFromList('list_favorites', recommendationId.value)
    showToast('已取消收藏')
  } else {
    // 添加收藏 - 添加到收藏清单
    await listStore.addComicToList('list_favorites', recommendationId.value)
    showToast('已加入收藏')
  }

  // 刷新详情
  await fetchDetail()
}

/**
 * 操作菜单选择
 */
function onActionSelect(action) {
  showActionSheet.value = false

  switch (action.value) {
    case 'edit_tags':
      showTagPicker.value = true
      break
    case 'add_to_list':
      router.push(`/recommendation-add-to-list/${recommendationId.value}`)
      break
    case 'delete':
      handleDelete()
      break
  }
}

/**
 * 确认标签选择
 */
async function confirmTagSelection() {
  console.log('[RecommendationDetail] 更新标签:', selectedTagIds.value)
  const success = await recommendationStore.bindTags(recommendationId.value, selectedTagIds.value)
  if (success) {
    showToast('标签已更新')
    showTagPicker.value = false
    await fetchDetail()
  } else {
    showToast('标签更新失败')
  }
}

/**
 * 根据标签筛选
 */
function filterByTag(tagId) {
  console.log('[RecommendationDetail] 根据标签筛选:', tagId)
  router.push({
    path: '/recommendation',
    query: { tag: tagId }
  })
}

/**
 * 删除推荐漫画
 */
async function handleDelete() {
  try {
    await showConfirmDialog({
      title: '确认删除',
      message: '确定要删除这个推荐漫画吗？此操作不可恢复。'
    })

    const success = await recommendationStore.deleteRecommendation(recommendationId.value)
    if (success) {
      showToast('删除成功')
      router.back()
    } else {
      showToast('删除失败')
    }
  } catch {
    // 用户取消
  }
}

// ============ Lifecycle ============
onMounted(async () => {
  console.log('[RecommendationDetail] 页面挂载')
  await tagStore.fetchTags()
  await fetchDetail()
})
</script>

<style scoped>
.recommendation-detail {
  min-height: 100vh;
  background: #f5f5f5;
}

.empty {
  padding: 40px 0;
}

.detail-content {
  padding-bottom: 24px;
}

.cover-section {
  display: flex;
  padding: 16px;
  background: #fff;
  gap: 16px;
}

.cover {
  width: 120px;
  height: 160px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
}

.info {
  flex: 1;
  min-width: 0;
}

.title {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.author {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #666;
}

.stats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.stat-item {
  font-size: 12px;
  color: #999;
}

.score-section {
  background: #f8f8f8;
  padding: 12px;
  border-radius: 8px;
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
  font-size: 14px;
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
.desc-section,
.preview-section {
  margin-top: 12px;
  padding: 16px;
  background: #fff;
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
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
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.preview-item {
  position: relative;
  aspect-ratio: 3/4;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
}

.preview-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview-page {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 4px;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 12px;
  text-align: center;
}

.action-section {
  margin-top: 12px;
  padding: 16px;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tag-picker {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.tag-picker .van-nav-bar {
  flex-shrink: 0;
}

.tag-picker TagFilter {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
</style>
