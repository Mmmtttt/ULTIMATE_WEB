<template>
  <div class="comic-detail">
    <van-nav-bar title="漫画详情" left-text="返回" left-arrow @click-left="$router.back()" />
    
    <van-loading v-if="comicStore.isLoading" type="spinner" color="#1989fa" />
    
    <div v-else-if="!comic" class="empty">
      <van-empty description="漫画不存在" />
    </div>
    
    <div v-else class="detail-content">
      <!-- 封面和基本信息 -->
      <div class="cover-section">
        <van-image 
          :src="getCoverUrl(comic.cover_path)" 
          fit="cover" 
          class="cover" 
          lazy-load
        />
        <div class="info">
          <h1 class="title">{{ comic.title }}</h1>
          <p class="author">{{ comic.author || '未知作者' }}</p>
          <div class="stats">
            <span class="stat-item">总页数: {{ comic.total_page }}</span>
            <span class="stat-item">当前页: {{ comic.current_page }}</span>
            <span class="stat-item">进度: {{ Math.round((comic.current_page / comic.total_page) * 100) }}%</span>
          </div>
          <div class="tags">
            <van-tag 
              v-for="tagId in comic.tag_ids" 
              :key="tagId" 
              size="small" 
              type="primary" 
              plain 
              class="tag"
            >
              {{ getTagName(tagId) }}
            </van-tag>
          </div>
        </div>
      </div>
      
      <!-- 简介 -->
      <div class="desc-section" v-if="comic.desc">
        <h2 class="section-title">简介</h2>
        <p class="desc">{{ comic.desc }}</p>
      </div>
      
      <!-- 章节/图片预览 -->
      <div class="preview-section">
        <h2 class="section-title">内容预览</h2>
        <div class="preview-grid">
          <div v-for="i in previewPages" :key="i" class="preview-item" @click="showPreviewImage(i)">
            <van-image 
              :src="getImageUrl(comic.id, i)" 
              fit="cover" 
              class="preview-image"
              lazy-load
            />
            <span class="preview-page">{{ i }}</span>
          </div>
        </div>
      </div>
      
      <!-- 大图预览弹窗 -->
      <van-popup v-model:show="showImagePreview" round class="image-preview-popup">
        <div class="image-preview-container">
          <van-image 
            :src="previewImageUrl" 
            fit="contain" 
            class="preview-large-image"
          />
          <van-icon name="close" class="close-preview" @click="showImagePreview = false" />
        </div>
      </van-popup>
      
      <!-- 操作按钮 -->
      <div class="action-section">
        <van-button type="primary" size="large" @click="startReading" class="read-button">
          开始阅读
        </van-button>
        <div class="action-buttons">
          <van-button icon="star-o" @click="toggleFavorite">
            {{ isFavorite ? '已收藏' : '收藏' }}
          </van-button>
          <van-button icon="share-o" @click="shareComic">
            分享
          </van-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useComicStore } from '../store/modules/comic'

const route = useRoute()
const router = useRouter()
const comicStore = useComicStore()
const comic = ref(null)
const isFavorite = ref(false)
const allTags = ref([])
const showImagePreview = ref(false)
const previewImageUrl = ref('')

import apiConfig from '../config/api'

// 获取完整的封面URL
const getCoverUrl = (coverPath) => {
  return apiConfig.getCoverUrl(coverPath)
}

// 获取图片URL
const getImageUrl = (comicId, pageNum) => {
  return apiConfig.getImageUrl(comicId, pageNum)
}

// 预览页数
const previewPages = computed(() => {
  if (!comic.value) return []
  const total = comic.value.total_page
  const pages = []
  if (total >= 1) pages.push(1)
  if (total >= 5) pages.push(5)
  if (total >= 10) pages.push(10)
  if (total > 10) pages.push(total)
  return pages
})

// 获取标签名称
const getTagName = (tagId) => {
  const tag = allTags.value.find(t => t.id === tagId)
  return tag ? tag.name : tagId
}

const startReading = () => {
  router.push(`/reader/${comic.value.id}`)
}

const toggleFavorite = () => {
  isFavorite.value = !isFavorite.value
  console.log('收藏状态:', isFavorite.value)
}

const shareComic = () => {
  console.log('分享漫画:', comic.value.title)
}

const showPreviewImage = (pageNum) => {
  previewImageUrl.value = getImageUrl(comic.value.id, pageNum)
  showImagePreview.value = true
}

onMounted(async () => {
  const id = route.params.id
  
  // 获取漫画详情
  const data = await comicStore.fetchComicDetail(id)
  comic.value = data
  
  // 获取所有标签
  try {
    const response = await fetch(`${apiConfig.getFullUrl('/api/v1/comic/tags')}`)
    const result = await response.json()
    if (result.code === 200) {
      allTags.value = result.data
    }
  } catch (error) {
    console.error('获取标签失败:', error)
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
  border-radius: 8px;
  margin: 16px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.cover-section {
  display: flex;
  padding: 24px;
  border-bottom: 1px solid #f0f0f0;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
}

.cover {
  width: 160px;
  height: 220px;
  border-radius: 8px;
  background: #f5f5f5;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transition: transform 0.3s ease;
}

.cover:hover {
  transform: scale(1.02);
}

.info {
  flex: 1;
  margin-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  justify-content: center;
}

.title {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
  line-height: 1.3;
  color: #333;
}

.author {
  font-size: 16px;
  color: #666;
  margin: 0;
  font-weight: 500;
}

.stats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
}

.stat-item {
  font-size: 14px;
  color: #999;
  background: #f5f5f5;
  padding: 6px 12px;
  border-radius: 16px;
  border: 1px solid #e0e0e0;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.tag {
  margin-right: 6px;
  margin-bottom: 6px;
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 12px;
}

.desc-section {
  padding: 24px;
  border-bottom: 1px solid #f0f0f0;
}

.section-title {
  font-size: 18px;
  font-weight: 500;
  margin: 0 0 16px 0;
  color: #333;
  position: relative;
  padding-left: 12px;
}

.section-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 16px;
  background: #1989fa;
  border-radius: 2px;
}

.desc {
  font-size: 15px;
  line-height: 1.6;
  color: #666;
  margin: 0;
  text-align: justify;
}

.preview-section {
  padding: 24px;
  border-bottom: 1px solid #f0f0f0;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.preview-item {
  position: relative;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s ease;
}

.preview-item:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  cursor: pointer;
}

.image-preview-popup {
  background: transparent;
  width: 90vw;
  height: 80vh;
  max-width: 1200px;
}

.image-preview-container {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.95);
  border-radius: 8px;
  overflow: hidden;
}

.preview-large-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.close-preview {
  position: absolute;
  top: 16px;
  right: 16px;
  color: #fff;
  font-size: 28px;
  cursor: pointer;
  padding: 8px;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 50%;
  transition: background 0.3s;
}

.close-preview:hover {
  background: rgba(0, 0, 0, 0.8);
}

.preview-image {
  width: 100%;
  aspect-ratio: 3/4;
  background: #f5f5f5;
}

.preview-page {
  position: absolute;
  bottom: 6px;
  right: 6px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 12px;
}

.action-section {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: #f8f9fa;
}

.read-button {
  width: 100%;
  height: 52px;
  font-size: 18px;
  font-weight: 600;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(25, 137, 250, 0.3);
  transition: all 0.3s ease;
}

.read-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(25, 137, 250, 0.4);
}

.action-buttons {
  display: flex;
  gap: 16px;
  justify-content: center;
}

.action-buttons .van-button {
  flex: 1;
  height: 44px;
  font-size: 15px;
  border-radius: 8px;
}

.empty {
  padding: 60px 0;
  text-align: center;
  background: #fff;
  margin: 16px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .cover-section {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }
  
  .cover {
    width: 140px;
    height: 196px;
    margin-bottom: 20px;
  }
  
  .info {
    margin-left: 0;
    align-items: center;
  }
  
  .stats {
    justify-content: center;
  }
  
  .tags {
    justify-content: center;
  }
  
  .preview-grid {
    grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
  }
}
</style>
