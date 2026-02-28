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
          :src="coverUrl" 
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
            <span class="stat-item">{{ progressPercent }}%</span>
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
            @click="previewImage(index)"
          >
            <img 
              :src="getImageUrl(comic.id, page)" 
              class="preview-image"
            />
            <span class="preview-page">第{{ page }}页</span>
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
        </div>
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
import { useComicStore, useTagStore, useListStore } from '@/stores'
import { useComic } from '@/composables'
import { buildCoverUrl, buildImageUrl } from '@/api/image'
import { showSuccessToast, showFailToast } from 'vant'

const route = useRoute()
const router = useRouter()
const comicStore = useComicStore()
const tagStore = useTagStore()
const listStore = useListStore()

const { updateScore } = useComic()

const comic = ref(null)
const isLoading = ref(true)
const showActionSheet = ref(false)
const showEditPopup = ref(false)
const showTagPopup = ref(false)
const showListPopup = ref(false)
const showPreview = ref(false)
const previewIndex = ref(0)
const allTags = ref([])
const selectedTagIds = ref([])
const selectedListIds = ref([])
const scoreValue = ref(6)
const favoriteLoading = ref(false)

const editForm = ref({
  title: '',
  author: '',
  desc: ''
})

const actions = [
  { name: '编辑信息', value: 'edit' },
  { name: '绑定标签', value: 'tags' }
]

const coverUrl = computed(() => {
  return comic.value ? buildCoverUrl(comic.value.cover_path) : ''
})

const progressPercent = computed(() => {
  if (!comic.value || !comic.value.total_page || comic.value.total_page === 0) return 0
  return Math.round((comic.value.current_page / comic.value.total_page) * 100)
})

const previewImages = computed(() => {
  if (!comic.value || !comic.value.preview_pages) return []
  return comic.value.preview_pages.map(page => getImageUrl(comic.value.id, page))
})

const isFavorited = computed(() => {
  return listStore.isFavorited(comic.value)
})

const customLists = computed(() => listStore.lists || [])

const isRead = computed(() => {
  if (!comic.value) return false
  return comic.value.current_page >= comic.value.total_page
})

// 方法
function getImageUrl(comicId, pageNum) {
  return buildImageUrl(comicId, pageNum)
}

async function fetchComicDetail() {
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

function goToPage(page) {
  router.push(`/reader/${comic.value.id}?page=${page}`)
}

function previewImage(index) {
  previewIndex.value = index
  showPreview.value = true
}

function onPreviewChange(index) {
  previewIndex.value = index
}

function filterByTag(tagId) {
  router.push(`/?tagId=${tagId}`)
}

async function handleScoreChange(value) {
  try {
    await updateScore(comic.value.id, value)
    comic.value.score = value
    showSuccessToast('评分保存成功')
  } catch (error) {
    console.error('保存评分失败:', error)
    showFailToast('评分保存失败')
  }
}

function onActionSelect(action) {
  showActionSheet.value = false
  if (action.value === 'edit') {
    showEditPopup.value = true
  } else if (action.value === 'tags') {
    showTagPopup.value = true
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
    const result = await listStore.toggleFavorite(comic.value.id)
    if (result !== null) {
      const FAVORITES_LIST_ID = 'list_favorites'
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
  console.log('[Detail] addToLists called')
  console.log('[Detail] selectedListIds:', selectedListIds.value)
  console.log('[Detail] comic.value:', comic.value)
  
  if (selectedListIds.value.length === 0 && (!comic.value.list_ids || comic.value.list_ids.length === 0)) {
    showFailToast('请选择清单')
    return
  }
  
  try {
    const currentListIds = comic.value.list_ids || []
    const toAdd = selectedListIds.value.filter(id => !currentListIds.includes(id))
    const toRemove = currentListIds.filter(id => !selectedListIds.value.includes(id))
    
    console.log('[Detail] currentListIds:', currentListIds)
    console.log('[Detail] toAdd:', toAdd)
    console.log('[Detail] toRemove:', toRemove)
    
    let addCount = 0
    let removeCount = 0
    
    for (const listId of toAdd) {
      console.log('[Detail] 绑定清单:', listId, '漫画ID:', comic.value.id)
      const result = await listStore.bindComics(listId, [comic.value.id])
      console.log('[Detail] 绑定结果:', result)
      if (result) addCount++
    }
    
    for (const listId of toRemove) {
      console.log('[Detail] 移除清单:', listId, '漫画ID:', comic.value.id)
      const result = await listStore.removeComics(listId, [comic.value.id])
      console.log('[Detail] 移除结果:', result)
      if (result) removeCount++
    }
    
    console.log('[Detail] addCount:', addCount, 'removeCount:', removeCount)
    
    if (addCount > 0 || removeCount > 0) {
      showListPopup.value = false
      selectedListIds.value = []
      comicStore.clearCache('detail', comic.value.id)
      await fetchComicDetail()
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
    console.error('[Detail] addToLists error:', error)
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

onMounted(async () => {
  console.log('[Detail] onMounted, id:', route.params.id)
  await fetchComicDetail()
  await fetchAllTags()
  await listStore.fetchLists()
})

watch(() => route.params.id, async (newId) => {
  console.log('[Detail] watch id:', newId)
  await fetchComicDetail()
})

watch(showListPopup, async (val) => {
  console.log('[Detail] showListPopup changed:', val)
  if (val) {
    await listStore.fetchLists()
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
  color: #999;
  margin-left: 4px;
}

.list-action {
  padding: 16px;
}
</style>
