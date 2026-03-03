<template>
  <div class="video-detail">
    <van-nav-bar
      :title="video?.title || '视频详情'"
      left-arrow
      @click-left="goBack"
    >
      <template #right>
        <van-icon name="ellipsis" @click="showActions = true" />
      </template>
    </van-nav-bar>
    
    <van-loading v-if="loading" type="spinner" color="#1989fa" class="loading-center" />
    
    <div v-else-if="video" class="detail-content">
      <div class="video-preview">
        <van-image 
          :src="getCoverUrl(video.cover_path)" 
          fit="contain"
          class="cover-image"
        />
      </div>
      
      <div class="video-info">
        <div class="video-title">{{ video.title }}</div>
        
        <div class="info-row">
          <span class="label">番号:</span>
          <span class="value">{{ video.code || '-' }}</span>
        </div>
        
        <div class="info-row">
          <span class="label">发布日期:</span>
          <span class="value">{{ video.date || '-' }}</span>
        </div>
        
        <div v-if="video.actors && video.actors.length > 0" class="info-row">
          <span class="label">演员:</span>
          <div class="actor-tags">
            <van-tag 
              v-for="actor in video.actors" 
              :key="actor" 
              type="primary" 
              plain
              @click="goToActor(actor)"
            >
              {{ actor }}
            </van-tag>
          </div>
        </div>
        
        <div v-if="video.series" class="info-row">
          <span class="label">系列:</span>
          <span class="value">{{ video.series }}</span>
        </div>
        
        <div class="info-row">
          <span class="label">评分:</span>
          <van-rate 
            v-model="scoreValue" 
            :count="10" 
            allow-half 
            @change="updateScore"
          />
          <span class="score-text">{{ video.score || '未评分' }}</span>
        </div>
        
        <div v-if="video.tags && video.tags.length > 0" class="info-row">
          <span class="label">标签:</span>
          <div class="tag-list">
            <van-tag 
              v-for="tag in video.tags" 
              :key="tag.id" 
              plain 
              class="tag-item"
            >
              {{ tag.name }}
            </van-tag>
          </div>
        </div>
      </div>
      
      <div v-if="video.magnets && video.magnets.length > 0" class="magnets-section">
        <van-cell-group title="磁力链接">
          <van-cell 
            v-for="(magnet, index) in video.magnets" 
            :key="index"
            :title="magnet.size_text || '未知大小'"
            :label="magnet.magnet.substring(0, 50) + '...'"
            clickable
            @click="copyMagnet(magnet.magnet)"
          >
            <template #right-icon>
              <van-icon name="description" />
            </template>
          </van-cell>
        </van-cell-group>
      </div>
      
      <div v-if="video.thumbnail_images && video.thumbnail_images.length > 0" class="thumbnails-section">
        <van-cell-group title="预览图">
          <div class="thumbnail-grid">
            <van-image 
              v-for="(img, index) in video.thumbnail_images" 
              :key="index"
              :src="img"
              fit="cover"
              class="thumbnail-item"
              @click="previewImages(index)"
            />
          </div>
        </van-cell-group>
      </div>
    </div>
    
    <EmptyState
      v-else
      icon="🎬"
      title="视频不存在"
      description="该视频可能已被删除"
    />
    
    <van-action-sheet 
      v-model:show="showActions" 
      :actions="actions" 
      @select="handleAction"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, showSuccessToast, showFailToast, showConfirmDialog, showImagePreview } from 'vant'
import { useVideoStore } from '@/stores'
import { EmptyState } from '@/components'

const route = useRoute()
const router = useRouter()
const videoStore = useVideoStore()

const video = ref(null)
const loading = ref(true)
const showActions = ref(false)
const scoreValue = ref(0)

const actions = [
  { name: '移入回收站', value: 'trash' },
  { name: '分享', value: 'share' }
]

const videoId = computed(() => route.params.id)

function getCoverUrl(coverPath) {
  if (!coverPath) return ''
  if (coverPath.startsWith('http')) return coverPath
  if (coverPath.startsWith('/static/')) return coverPath
  if (coverPath.startsWith('/')) return coverPath
  return `/${coverPath}`
}

async function loadVideo() {
  loading.value = true
  const data = await videoStore.fetchDetail(videoId.value)
  video.value = data
  if (data?.score) {
    scoreValue.value = data.score
  }
  loading.value = false
}

async function updateScore(value) {
  const success = await videoStore.updateScore(videoId.value, value)
  if (success) {
    showSuccessToast('评分已更新')
  } else {
    showFailToast('评分失败')
  }
}

function goToActor(actorName) {
  router.push(`/actors?name=${encodeURIComponent(actorName)}`)
}

function copyMagnet(magnet) {
  navigator.clipboard.writeText(magnet).then(() => {
    showSuccessToast('已复制到剪贴板')
  }).catch(() => {
    showFailToast('复制失败')
  })
}

function previewImages(index) {
  showImagePreview({
    images: video.value.thumbnail_images,
    startPosition: index
  })
}

async function handleAction(action) {
  showActions.value = false
  
  if (action.value === 'trash') {
    try {
      await showConfirmDialog({
        title: '确认操作',
        message: '确定将此视频移入回收站吗？'
      })
      
      const success = await videoStore.moveToTrash(videoId.value)
      if (success) {
        showSuccessToast('已移入回收站')
        router.back()
      } else {
        showFailToast('操作失败')
      }
    } catch (e) {
      // 取消操作
    }
  } else if (action.value === 'share') {
    if (navigator.share) {
      navigator.share({
        title: video.value.title,
        text: `${video.value.code} - ${video.value.title}`
      })
    } else {
      showToast('当前浏览器不支持分享')
    }
  }
}

function goBack() {
  router.back()
}

onMounted(() => {
  loadVideo()
})
</script>

<style scoped>
.video-detail {
  min-height: 100vh;
  background: #f5f5f5;
}

.loading-center {
  display: flex;
  justify-content: center;
  padding-top: 100px;
}

.detail-content {
  padding-bottom: 20px;
}

.video-preview {
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cover-image {
  width: 100%;
  max-height: 300px;
}

.video-info {
  background: #fff;
  padding: 16px;
  margin-bottom: 12px;
}

.video-title {
  font-size: 18px;
  font-weight: 500;
  color: #333;
  margin-bottom: 12px;
}

.info-row {
  display: flex;
  align-items: flex-start;
  margin-bottom: 10px;
}

.info-row .label {
  width: 70px;
  font-size: 14px;
  color: #666;
  flex-shrink: 0;
}

.info-row .value {
  font-size: 14px;
  color: #333;
}

.actor-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.score-text {
  margin-left: 10px;
  font-size: 14px;
  color: #666;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-item {
  margin-bottom: 4px;
}

.magnets-section {
  margin-bottom: 12px;
}

.thumbnails-section {
  background: #fff;
}

.thumbnail-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 12px;
}

.thumbnail-item {
  aspect-ratio: 16/9;
  border-radius: 4px;
  overflow: hidden;
}
</style>
