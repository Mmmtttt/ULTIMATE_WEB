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
      <!-- 视频播放器 -->
      <div class="video-player-section" v-if="showPlayer">
        <div class="video-wrapper">
          <video 
            ref="videoPlayer"
            controls
            class="video-element"
            :src="currentPlayUrl"
          ></video>
        </div>
        <div class="player-controls">
          <div class="source-selector">
            <van-button 
              v-for="source in availableSources" 
              :key="source.source"
              :type="currentSource === source.source ? 'primary' : 'default'"
              size="small"
              @click="switchSource(source)"
            >
              {{ source.name }}
              <span v-if="source.currentResolution" class="resolution-badge">
                {{ source.currentResolution }}
              </span>
            </van-button>
          </div>
          <div class="quality-selector" v-if="currentStreams.length > 1">
            <span class="quality-label">画质:</span>
            <van-dropdown-menu>
              <van-dropdown-item 
                v-model="currentQuality" 
                :options="qualityOptions"
                @change="changeQuality"
              />
            </van-dropdown-menu>
          </div>
        </div>
      </div>
      
      <!-- 封面预览 -->
      <div v-else class="video-preview" @click="loadPlayUrls">
        <van-image 
          :src="getCoverUrl(video.cover_path)" 
          fit="contain"
          class="cover-image"
        />
        <div class="play-overlay">
          <van-icon name="play-circle-o" class="play-icon" />
          <span class="play-text">点击播放</span>
        </div>
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, showSuccessToast, showFailToast, showConfirmDialog, showImagePreview, showLoadingToast, closeToast } from 'vant'
import { useVideoStore } from '@/stores'
import { EmptyState } from '@/components'
import { videoApi } from '@/api'
import Hls from 'hls.js'

const route = useRoute()
const router = useRouter()
const videoStore = useVideoStore()

const video = ref(null)
const loading = ref(true)
const showActions = ref(false)
const scoreValue = ref(0)

// 播放器相关
const showPlayer = ref(false)
const videoPlayer = ref(null)
const playSources = ref([])
const currentSource = ref('')
const currentStreams = ref([])
const currentQuality = ref(0)
const currentPlayUrl = ref('')
const hls = ref(null)

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

// 播放器相关函数
const availableSources = computed(() => {
  return playSources.value.filter(s => s.available)
})

const qualityOptions = computed(() => {
  return currentStreams.value.map((stream, index) => ({
    text: stream.resolution || '未知画质',
    value: index
  }))
})

async function loadPlayUrls() {
  if (!video.value?.code) {
    showFailToast('视频没有番号信息')
    return
  }
  
  showLoadingToast({
    message: '加载播放链接...',
    forbidClick: true
  })
  
  try {
    const response = await videoApi.getPlayUrls(videoId.value)
    closeToast()
    
    if (response.code === 200 && response.data) {
      playSources.value = response.data.sources || []
      
      const available = playSources.value.filter(s => s.available)
      if (available.length === 0) {
        showFailToast('暂无可用播放源')
        return
      }
      
      // 显示播放器
      showPlayer.value = true
      
      // 默认选择第一个可用源
      const firstSource = available[0]
      await switchSource(firstSource)
    } else {
      showFailToast(response.msg || '加载失败')
    }
  } catch (error) {
    closeToast()
    showFailToast('加载播放链接失败')
    console.error(error)
  }
}

async function switchSource(source) {
  currentSource.value = source.source
  currentStreams.value = source.streams || []
  
  if (currentStreams.value.length > 0) {
    // 默认选择最高画质
    currentQuality.value = 0
    await playStream(currentStreams.value[0])
  }
}

async function changeQuality(index) {
  const stream = currentStreams.value[index]
  if (stream) {
    await playStream(stream)
  }
}

async function playStream(stream) {
  if (!videoPlayer.value) return
  
  // 使用代理URL解决跨域问题
  let url = stream.url
  if (stream.proxy_url) {
    // 将代理URL转换为后端API代理URL
    url = `/api/v1/video${stream.proxy_url}`
  }
  
  // 销毁之前的 HLS 实例
  if (hls.value) {
    hls.value.destroy()
    hls.value = null
  }
  
  // 判断是否是 m3u8
  if (url.includes('.m3u8') || url.includes('m3u8')) {
    if (Hls.isSupported()) {
      hls.value = new Hls({
        debug: false,
        enableWorker: true
      })
      
      hls.value.loadSource(url)
      hls.value.attachMedia(videoPlayer.value)
      
      hls.value.on(Hls.Events.MANIFEST_PARSED, () => {
        videoPlayer.value.play().catch(e => console.log('自动播放被阻止'))
      })
      
      hls.value.on(Hls.Events.ERROR, (event, data) => {
        console.error('HLS 错误:', data)
        if (data.fatal) {
          showFailToast('播放错误，请尝试切换源')
        }
      })
    } else if (videoPlayer.value.canPlayType('application/vnd.apple.mpegurl')) {
      videoPlayer.value.src = url
      videoPlayer.value.play()
    } else {
      showFailToast('当前浏览器不支持播放此格式')
    }
  } else {
    // 普通视频格式
    currentPlayUrl.value = url
    videoPlayer.value.play()
  }
}

onMounted(() => {
  loadVideo()
})

onUnmounted(() => {
  // 清理 HLS 实例
  if (hls.value) {
    hls.value.destroy()
    hls.value = null
  }
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
  position: relative;
  cursor: pointer;
}

.cover-image {
  width: 100%;
  max-height: 300px;
}

.play-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.4);
  transition: background 0.3s;
}

.video-preview:hover .play-overlay {
  background: rgba(0, 0, 0, 0.3);
}

.play-icon {
  font-size: 60px;
  color: rgba(255, 255, 255, 0.9);
}

.play-text {
  margin-top: 10px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 16px;
}

.video-player-section {
  background: #000;
}

.video-wrapper {
  position: relative;
  padding-bottom: 56.25%;
  height: 0;
  overflow: hidden;
}

.video-element {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.player-controls {
  padding: 12px 16px;
  background: #1a1a1a;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}

.source-selector {
  display: flex;
  gap: 10px;
}

.resolution-badge {
  margin-left: 4px;
  font-size: 10px;
  padding: 2px 6px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 4px;
}

.quality-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.quality-label {
  color: #999;
  font-size: 14px;
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
