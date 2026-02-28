<template>
  <div class="comic-detail">
    <van-nav-bar title="漫画详情" left-text="返回" left-arrow @click-left="$router.back()">
      <template #right>
        <van-icon name="ellipsis" @click="showActionSheet = true" />
      </template>
    </van-nav-bar>
    
    <van-loading v-if="isLoading" type="spinner" color="#1989fa" />
    
    <div v-else-if="!comic" class="empty">
      <van-empty description="漫画不存在" />
    </div>
    
    <div v-else class="detail-content">
      <div class="cover-section">
        <van-image 
          :src="getCoverUrl(comic.cover_path)" 
          fit="cover" 
          class="cover" 
          lazy-load
          @click="startReading"
        />
        <div class="info">
          <h1 class="title">{{ comic.title }}</h1>
          <p class="author" v-if="comic.author">{{ comic.author }}</p>
          <p class="author" v-else>未知作者</p>
          
          <div class="stats">
            <span class="stat-item">总页数: {{ comic.total_page }}</span>
            <span class="stat-item">进度: {{ comic.current_page }}/{{ comic.total_page }}</span>
            <span class="stat-item">{{ Math.round((comic.current_page / comic.total_page) * 100) }}%</span>
          </div>
          
          <div class="score-section">
            <div class="score-display">
              <span class="score-label">评分:</span>
              <span class="score-value" v-if="comic.score">{{ comic.score }}</span>
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
            v-for="tag in comic.tags" 
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
      
      <div class="preview-section">
        <h2 class="section-title">内容预览</h2>
        <div class="preview-grid">
          <div 
            v-for="(page, index) in comic.preview_pages" 
            :key="index" 
            class="preview-item" 
            @click="goToPage(page)"
          >
            <van-image 
              :src="getImageUrl(comic.id, page)" 
              fit="contain" 
              class="preview-image"
              lazy-load
            />
            <span class="preview-page">第{{ page }}页</span>
          </div>
        </div>
      </div>
      
      <div class="action-section">
        <van-button type="primary" size="large" @click="startReading" class="read-button">
          {{ comic.current_page > 1 ? '继续阅读' : '开始阅读' }}
        </van-button>
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
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useComicStore } from '../store/modules/comic'
import { comicApi } from '../api/comic'
import apiConfig from '../config/api'
import { showSuccessToast, showFailToast } from 'vant'

const route = useRoute()
const router = useRouter()
const comicStore = useComicStore()
const comic = ref(null)
const isLoading = ref(true)
const showActionSheet = ref(false)
const showEditPopup = ref(false)
const showTagPopup = ref(false)
const allTags = ref([])
const selectedTagIds = ref([])
const scoreValue = ref(6)

const editForm = ref({
  title: '',
  author: '',
  desc: ''
})

const actions = [
  { name: '编辑信息', value: 'edit' },
  { name: '绑定标签', value: 'tags' }
]

const getCoverUrl = (coverPath) => {
  return apiConfig.getCoverUrl(coverPath)
}

const getImageUrl = (comicId, pageNum) => {
  return apiConfig.getImageUrl(comicId, pageNum)
}

const fetchComicDetail = async () => {
  const comicId = route.params.id
  isLoading.value = true
  
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
    }
  } catch (error) {
    console.error('获取漫画详情失败:', error)
  } finally {
    isLoading.value = false
  }
}

const fetchAllTags = async () => {
  try {
    const tags = await comicStore.fetchTags()
    if (tags) {
      allTags.value = tags
    }
  } catch (error) {
    console.error('获取标签列表失败:', error)
  }
}

const startReading = () => {
  router.push(`/reader/${comic.value.id}`)
}

const goToPage = (page) => {
  router.push(`/reader/${comic.value.id}?page=${page}`)
}

const filterByTag = (tagId) => {
  router.push(`/?tagId=${tagId}`)
}

const handleScoreChange = async (value) => {
  try {
    const response = await comicApi.updateScore(comic.value.id, value)
    if (response.code === 200) {
      comic.value.score = value
      showSuccessToast('评分保存成功')
    } else {
      showFailToast(response.msg || '评分保存失败')
    }
  } catch (error) {
    console.error('保存评分失败:', error)
    showFailToast('评分保存失败')
  }
}

const onActionSelect = (action) => {
  showActionSheet.value = false
  if (action.value === 'edit') {
    showEditPopup.value = true
  } else if (action.value === 'tags') {
    showTagPopup.value = true
  }
}

const saveEdit = async () => {
  try {
    const response = await comicApi.editComic(comic.value.id, editForm.value)
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

const toggleTag = (tagId) => {
  const index = selectedTagIds.value.indexOf(tagId)
  if (index > -1) {
    selectedTagIds.value.splice(index, 1)
  } else {
    selectedTagIds.value.push(tagId)
  }
}

const saveTags = async () => {
  try {
    const response = await comicApi.bindTags(comic.value.id, selectedTagIds.value)
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

onMounted(async () => {
  console.log('[Detail] onMounted, id:', route.params.id)
  await fetchComicDetail()
  await fetchAllTags()
})

watch(() => route.params.id, async (newId) => {
  console.log('[Detail] watch id:', newId)
  await fetchComicDetail()
})
</script>

<style scoped>
.comic-detail {
  padding-bottom: 20px;
  min-height: 100vh;
  background: #f5f5f5;
}

.detail-content {
  background: #fff;
}

.cover-section {
  display: flex;
  padding: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
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
  margin-left: 16px;
  display: flex;
  flex-direction: column;
}

.title {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 8px 0;
  line-height: 1.3;
}

.author {
  font-size: 14px;
  margin: 0 0 12px 0;
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
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 12px 0;
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
  font-size: 14px;
  line-height: 1.6;
  color: #666;
  margin: 0;
  white-space: pre-wrap;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
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

.preview-image :deep(.van-image__img) {
  width: 100%;
  height: auto;
  object-fit: contain;
}

.preview-page {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  font-size: 10px;
  padding: 4px;
  text-align: center;
}

.action-section {
  padding: 16px;
  position: sticky;
  bottom: 0;
  background: #fff;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
}

.read-button {
  border-radius: 24px;
}

.empty {
  padding: 40px 0;
  text-align: center;
}

.edit-popup,
.tag-popup {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.tag-select-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
}

.tag-count {
  font-size: 12px;
  color: #999;
  margin-left: 8px;
}

@media (max-width: 480px) {
  .cover-section {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }
  
  .cover {
    width: 160px;
    height: 200px;
    margin-bottom: 16px;
  }
  
  .info {
    margin-left: 0;
    width: 100%;
  }
  
  .stats {
    justify-content: center;
  }
  
  .preview-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
