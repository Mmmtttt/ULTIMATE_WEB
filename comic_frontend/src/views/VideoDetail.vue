<template>
  <div class="video-detail" :class="{ 'video-detail-desktop': isDesktop, 'video-detail-mobile': isMobile }">
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
        <div class="cover-container">
          <van-image 
            :src="getCoverUrl(video.cover_path)" 
            fit="cover"
            class="cover-image"
          />
          <van-tag
            v-if="video.source === 'preview'"
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
            <div v-for="actor in video.actors" :key="actor" class="actor-item">
              <van-tag 
                type="primary" 
                plain
                class="actor-tag"
                @click="goToActor(actor)"
              >
                {{ actor }}
              </van-tag>
              <van-button 
                v-if="!isActorSubscribed(actor)" 
                size="mini" 
                type="primary" 
                plain
                class="subscribe-button"
                @click="subscribeActor(actor)"
                :loading="subscribingActors.includes(actor)"
              >
                订阅
              </van-button>
              <van-tag v-else type="success" size="mini" class="subscribed-tag">
                已订阅
              </van-tag>
            </div>
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
              @click="filterByTag(tag.id)"
            >
              {{ tag.name }}
            </van-tag>
          </div>
        </div>
      </div>
      
      <!-- 操作按钮区 -->
      <div class="action-buttons">
        <van-button 
          :icon="isFavoritedVideo ? 'star' : 'star-o'"
          :type="isFavoritedVideo ? 'warning' : 'default'"
          block
          @click="toggleFavorite"
        >
          {{ isFavoritedVideo ? '已收藏' : '收藏' }}
        </van-button>
        <van-button 
          icon="orders-o"
          type="primary"
          block
          @click="showListPopup = true"
        >
          加入清单
        </van-button>
        <van-button 
          icon="delete-o"
          type="danger"
          block
          @click="handleMoveToTrash"
        >
          移入回收站
        </van-button>
      </div>
      
      <div v-if="video.magnets && video.magnets.length > 0" class="magnets-section">
        <van-cell-group title="磁力链接">
          <van-cell 
            v-for="(magnet, index) in video.magnets" 
            :key="index"
            :title="getMagnetSizeText(magnet)"
            :label="getMagnetPreview(magnet)"
            clickable
            @click="copyMagnet(magnet)"
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
    
    <!-- 清单选择弹窗 -->
    <van-popup 
      v-model:show="showListPopup" 
      position="bottom" 
      round 
      :style="{ height: '60%' }"
    >
      <div class="list-popup">
        <van-nav-bar title="选择清单">
          <template #right>
            <van-button type="primary" size="small" @click="addToLists">保存</van-button>
          </template>
        </van-nav-bar>
        
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
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { nextTick } from 'vue'
import { showToast, showSuccessToast, showFailToast, showConfirmDialog, showImagePreview, showLoadingToast, closeToast } from 'vant'
import { useVideoStore, useListStore, useActorStore } from '@/stores'
import { EmptyState } from '@/components'
import { videoApi } from '@/api'
import { useDevice } from '@/composables/useDevice'
import { applyListMembershipChanges, buildListChangeMessage, getCoverUrl } from '@/utils'
import Hls from 'hls.js'

const route = useRoute()
const router = useRouter()
const videoStore = useVideoStore()
const listStore = useListStore()
const actorStore = useActorStore()
const { isDesktop, isMobile } = useDevice()

const video = ref(null)
const loading = ref(true)
const showActions = ref(false)
const showListPopup = ref(false)
const selectedListIds = ref([])
const scoreValue = ref(0)
const subscribingActors = ref([])

// 播放器相关
const showPlayer = ref(false)
const videoPlayer = ref(null)
const playSources = ref([])
const currentSource = ref('')
const currentStreams = ref([])
const currentQuality = ref(0)

const hls = ref(null)

const actions = computed(() => {
  if (video.value?.is_deleted) {
    return [
      { name: '永久删除', value: 'delete', color: '#ee0a24' },
      { name: '分享', value: 'share' }
    ]
  }
  return [
    { name: '移入回收站', value: 'trash', color: '#ee0a24' },
    { name: '分享', value: 'share' }
  ]
})

const videoId = computed(() => route.params.id)

const isFavoritedVideo = computed(() => {
  return listStore.isFavoritedVideo(video.value)
})

const customLists = computed(() => listStore.lists || [])

async function loadVideo() {
  loading.value = true
  const data = await videoStore.fetchDetail(videoId.value)
  video.value = data
  if (data?.score) {
    scoreValue.value = data.score
  }
  if (data?.list_ids) {
    selectedListIds.value = [...data.list_ids]
  }
  await listStore.fetchLists('video')
  await actorStore.fetchList()
  loading.value = false
}

function isActorSubscribed(actorName) {
  return actorStore.actors.some(actor => actor.name.toLowerCase() === actorName.toLowerCase())
}

async function subscribeActor(actorName) {
  if (subscribingActors.value.includes(actorName)) return
  
  subscribingActors.value.push(actorName)
  try {
    const result = await actorStore.subscribe(actorName)
    if (result.success) {
      showSuccessToast(`订阅 ${actorName} 成功`)
    } else {
      showFailToast(result.message || '订阅失败')
    }
  } catch (error) {
    console.error('订阅演员失败:', error)
    showFailToast('订阅失败')
  } finally {
    const index = subscribingActors.value.indexOf(actorName)
    if (index > -1) {
      subscribingActors.value.splice(index, 1)
    }
  }
}

async function toggleFavorite() {
  const result = await listStore.toggleFavoriteVideo(videoId.value, video.value.source || 'local')
  if (result !== null) {
    const FAVORITES_LIST_ID = 'list_favorites_video'
    if (result) {
      video.value.list_ids = video.value.list_ids || []
      if (!video.value.list_ids.includes(FAVORITES_LIST_ID)) {
        video.value.list_ids.push(FAVORITES_LIST_ID)
      }
    } else {
      video.value.list_ids = (video.value.list_ids || []).filter(id => id !== FAVORITES_LIST_ID)
    }
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
  if (selectedListIds.value.length === 0 && (!video.value.list_ids || video.value.list_ids.length === 0)) {
    showFailToast('请选择清单')
    return
  }
  
  try {
    const { addCount, removeCount, unchanged } = await applyListMembershipChanges({
      listStore,
      contentType: 'video',
      selectedListIds: selectedListIds.value,
      currentListIds: video.value.list_ids || [],
      itemId: videoId.value,
      source: video.value.source || 'local'
    })

    if (addCount > 0 || removeCount > 0) {
      showListPopup.value = false
      selectedListIds.value = []
      await loadVideo()
      await listStore.fetchLists('video')

      showSuccessToast(buildListChangeMessage(addCount, removeCount))
    } else if (unchanged) {
      showSuccessToast('清单无变化')
    }
  } catch (error) {
    console.error('addToLists error:', error)
    showFailToast('操作失败')
  }
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
  if (video.value.source === 'preview') {
    router.push({ name: 'Preview', query: { author: actorName } })
  } else {
    router.push({ name: 'Library', query: { author: actorName } })
  }
}

function filterByTag(tagId) {
  if (video.value.source === 'preview') {
    router.push({ name: 'Preview', query: { tagId: tagId } })
  } else {
    router.push({ name: 'Library', query: { tagId: tagId } })
  }
}

function getMagnetText(magnet) {
  if (typeof magnet === 'string') {
    return magnet
  }
  if (!magnet || typeof magnet !== 'object') {
    return ''
  }
  return magnet.magnet || magnet.url || magnet.link || ''
}

function getMagnetSizeText(magnet) {
  if (magnet && typeof magnet === 'object') {
    return magnet.size_text || magnet.size || '未知大小'
  }
  return '未知大小'
}

function getMagnetPreview(magnet) {
  const text = getMagnetText(magnet)
  if (!text) {
    return '磁力链接为空'
  }
  return text.length > 50 ? `${text.slice(0, 50)}...` : text
}

async function copyMagnet(magnet) {
  const text = getMagnetText(magnet)
  if (!text) {
    showFailToast('磁力链接为空')
    return
  }

  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.setAttribute('readonly', 'readonly')
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      textarea.style.pointerEvents = 'none'
      document.body.appendChild(textarea)
      textarea.select()
      textarea.setSelectionRange(0, text.length)
      const copied = document.execCommand('copy')
      document.body.removeChild(textarea)
      if (!copied) {
        throw new Error('execCommand copy failed')
      }
    }
    showSuccessToast('已复制磁力链接')
  } catch (error) {
    console.error('复制磁力链接失败:', error)
    showFailToast('复制失败，请手动复制')
  }
}

function previewImages(index) {
  showImagePreview({
    images: video.value.thumbnail_images,
    startPosition: index
  })
}

async function handleMoveToTrash() {
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
}

async function handleAction(action) {
  showActions.value = false
  
  if (action.value === 'trash') {
    await handleMoveToTrash()
  } else if (action.value === 'delete') {
    try {
      await showConfirmDialog({
        title: '永久删除',
        message: '确定要永久删除此视频吗？此操作不可恢复！'
      })
      
      const success = await videoStore.deletePermanently(videoId.value)
      if (success) {
        showSuccessToast('已永久删除')
        router.back()
      } else {
        showFailToast('删除失败')
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
    // 等待 DOM 更新后再播放
    await nextTick()
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
  if (!videoPlayer.value) {
    console.error('视频元素未找到')
    return
  }
  
  // 使用代理URL解决跨域问题
  let url = stream.url
  if (stream.proxy_url) {
    // 直接使用返回的 proxy_url，已经包含正确的路径
    if (stream.proxy_url.startsWith('http')) {
      url = stream.proxy_url
    } else if (stream.proxy_url.startsWith('/proxy2') || stream.proxy_url.startsWith('/proxy/')) {
      url = `/api/v1/video${stream.proxy_url}`
    } else {
      url = stream.proxy_url
    }
  }
  
  console.log('播放URL:', url)
  
  // 销毁之前的 HLS 实例
  if (hls.value) {
    hls.value.destroy()
    hls.value = null
  }
  
  // 清空视频元素的 src
  videoPlayer.value.src = ''
  videoPlayer.value.load()
  
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
        console.log('HLS manifest 解析成功')
        videoPlayer.value.play().catch(e => console.log('自动播放被阻止:', e))
      })
      
      hls.value.on(Hls.Events.ERROR, (event, data) => {
        console.error('HLS 错误:', event, data)
        if (data.fatal) {
          showFailToast('播放错误，请尝试切换源或清晰度')
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
    videoPlayer.value.src = url
    videoPlayer.value.play()
  }
}

onMounted(() => {
  loadVideo()
})

watch(showListPopup, async (val) => {
  if (val) {
    await listStore.fetchLists('video')
    if (video.value) {
      selectedListIds.value = [...(video.value.list_ids || [])]
    }
  }
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

.cover-container {
  width: 100%;
  display: flex;
  justify-content: center;
  position: relative;
}

.source-tag {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 2;
}

.cover-image {
  width: 100%;
  max-height: 300px;
  object-fit: cover;
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
  gap: 12px;
}

.actor-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.actor-tag {
  cursor: pointer;
}

.subscribe-button {
  flex-shrink: 0;
}

.subscribed-tag {
  flex-shrink: 0;
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

.action-buttons {
  display: flex;
  gap: 12px;
  padding: 0 16px 16px;
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

/* 电脑端样式优化 */
.video-detail-desktop .detail-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.video-detail-desktop .video-preview {
  border-radius: 12px;
  overflow: hidden;
}

.video-detail-desktop .cover-container {
  max-width: 700px;
}

.video-detail-desktop .cover-image {
  max-height: 450px;
  border-radius: 8px;
}

.video-detail-desktop .play-icon {
  font-size: 80px;
}

.video-detail-desktop .play-text {
  font-size: 18px;
}

.video-detail-desktop .video-wrapper {
  max-width: 1000px;
  margin: 0 auto;
  padding-bottom: 56.25%;
}

.video-detail-desktop .player-controls {
  max-width: 1000px;
  margin: 0 auto;
  border-radius: 0 0 12px 12px;
}

.video-detail-desktop .video-info {
  border-radius: 12px;
  margin-top: 20px;
  padding: 24px;
}

.video-detail-desktop .video-title {
  font-size: 22px;
}

.video-detail-desktop .info-row .label {
  font-size: 15px;
  width: 80px;
}

.video-detail-desktop .info-row .value {
  font-size: 15px;
}

.video-detail-desktop .thumbnail-grid {
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  padding: 16px;
}

.video-detail-desktop .thumbnail-item {
  border-radius: 8px;
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
