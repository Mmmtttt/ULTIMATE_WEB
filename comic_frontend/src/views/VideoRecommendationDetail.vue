<template>
  <div class="video-detail" :class="{ 'video-detail-desktop': isDesktop, 'video-detail-mobile': isMobile }">
    <van-nav-bar
      :title="recommendation?.title || '视频详情'"
      left-arrow
      @click-left="goBack"
    >
      <template #right>
        <van-icon name="ellipsis" @click="showActions = true" />
      </template>
    </van-nav-bar>
    
    <van-loading v-if="loading" type="spinner" color="#1989fa" class="loading-center" />
    
    <div v-else-if="recommendation" class="detail-content">
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
            :src="getCoverUrl(preferredCoverPath)" 
            fit="cover"
            class="cover-image"
          />
          <van-tag
            type="primary"
            size="small"
            class="source-tag"
          >预览库</van-tag>
        </div>
        <div class="play-overlay">
          <van-icon name="play-circle-o" class="play-icon" />
          <span class="play-text">点击播放</span>
        </div>
      </div>
      
      <div class="video-info">
        <div class="video-title">{{ recommendation.title }}</div>
        
        <div class="info-row">
          <span class="label">番号:</span>
          <span class="value">{{ recommendation.code || '-' }}</span>
        </div>
        
        <div class="info-row">
          <span class="label">发布日期:</span>
          <span class="value">{{ recommendation.date || '-' }}</span>
        </div>
        
        <div v-if="recommendation.actors && recommendation.actors.length > 0" class="info-row">
          <span class="label">演员:</span>
          <div class="actor-tags">
            <div v-for="actor in recommendation.actors" :key="actor" class="actor-item">
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
        
        <div v-if="recommendation.series" class="info-row">
          <span class="label">系列:</span>
          <span class="value">{{ recommendation.series }}</span>
        </div>
        
        <div class="info-row score-row">
          <span class="label">评分:</span>
          <div class="score-controls">
            <van-rate 
              v-model="scoreValue" 
              :count="12" 
              allow-half 
              @change="updateScore"
            />
            <span class="score-chip" :class="{ 'is-empty': !recommendation.score }">{{ recommendation.score || '未评分' }}</span>
          </div>
        </div>
        
        <div v-if="recommendation.tags && recommendation.tags.length > 0" class="info-row">
          <span class="label">标签:</span>
          <div class="tag-list">
            <van-tag 
              v-for="tag in recommendation.tags" 
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
          :type="isFavoritedVideo ? 'warning' : 'default'"
          size="small"
          @click="toggleFavorite"
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
      
      <div v-if="recommendation.magnets && recommendation.magnets.length > 0" class="magnets-section">
        <van-cell-group title="磁力链接">
          <van-cell 
            v-for="(magnet, index) in recommendation.magnets" 
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

      <div v-if="recommendation" class="preview-video-section">
        <van-cell-group title="预览视频">
          <div class="preview-video-actions">
            <van-button
              size="small"
              plain
              type="primary"
              :loading="refreshingPreviewVideo"
              @click="refreshPreviewVideo"
            >
              更新预览视频
            </van-button>
          </div>
          <div class="preview-video-player-container">
            <video
              v-if="hasPreviewVideo"
              ref="previewVideoPlayer"
              controls
              playsinline
              preload="metadata"
              @error="handlePreviewVideoError"
              class="preview-video-player"
            ></video>
            <div v-else class="preview-video-empty">
              暂无可用预览视频，可点击上方按钮尝试更新
            </div>
          </div>
        </van-cell-group>
      </div>
      
      <div v-if="preferredThumbnailImages.length > 0" class="thumbnails-section">
        <van-cell-group title="预览图">
          <div class="thumbnail-grid">
            <van-image 
              v-for="(img, index) in preferredThumbnailImages" 
              :key="index"
              :src="getCoverUrl(img)"
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
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, showSuccessToast, showFailToast, showConfirmDialog, showImagePreview, showLoadingToast, closeToast } from 'vant'
import { useVideoRecommendationStore, useListStore, useActorStore } from '@/stores'
import { EmptyState } from '@/components'
import { videoApi } from '@/api'
import { useDevice } from '@/composables/useDevice'
import { applyListMembershipChanges, buildListChangeMessage, getCoverUrl, toBackendApiUrl, toBackendUrl } from '@/utils'
import Hls from 'hls.js'

const route = useRoute()
const router = useRouter()
const videoRecommendationStore = useVideoRecommendationStore()
const listStore = useListStore()
const actorStore = useActorStore()
const { isDesktop, isMobile } = useDevice()

const recommendation = ref(null)
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
const previewVideoPlayer = ref(null)
const refreshingPreviewVideo = ref(false)

const hls = ref(null)
const previewHls = ref(null)

const actions = computed(() => {
  if (recommendation.value?.is_deleted) {
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

const recommendationId = computed(() => route.params.id)

const isFavoritedVideo = computed(() => {
  return listStore.isFavoritedVideo(recommendation.value)
})

const customLists = computed(() => listStore.lists || [])
const preferredCoverPath = computed(() => {
  const localPath = String(recommendation.value?.cover_path_local || '').trim()
  const remotePath = String(recommendation.value?.cover_path || '').trim()
  return localPath || remotePath
})
const preferredThumbnailImages = computed(() => {
  const local = Array.isArray(recommendation.value?.thumbnail_images_local) ? recommendation.value.thumbnail_images_local : []
  const remote = Array.isArray(recommendation.value?.thumbnail_images) ? recommendation.value.thumbnail_images : []
  if (!local.length) {
    return remote
  }

  const maxLen = Math.max(local.length, remote.length)
  const merged = []
  for (let index = 0; index < maxLen; index += 1) {
    const localUrl = String(local[index] || '').trim()
    const remoteUrl = String(remote[index] || '').trim()
    if (localUrl) {
      merged.push(localUrl)
    } else if (remoteUrl) {
      merged.push(remoteUrl)
    }
  }
  return merged
})
const previewVideoPlayerUrl = computed(() => {
  const localPreview = String(recommendation.value?.preview_video_local || '').trim()
  const remotePreview = String(recommendation.value?.preview_video || '').trim()
  return resolvePreviewVideoUrl(localPreview || remotePreview)
})
const hasPreviewVideo = computed(() => Boolean(previewVideoPlayerUrl.value))

function isLikelyPreviewMediaUrl(url) {
  if (!url || typeof url !== 'string') {
    return false
  }

  const lower = url.toLowerCase()
  if (
    lower.startsWith('/api/v1/video/proxy2') ||
    lower.startsWith('/v1/video/proxy2') ||
    lower.startsWith('/proxy2?') ||
    lower.startsWith('/proxy/')
  ) {
    return true
  }

  return /\.(mp4|m3u8|webm|mov|m4v)(?:$|[?#])/i.test(lower)
}

function resolvePreviewVideoUrl(rawUrl) {
  if (!rawUrl || typeof rawUrl !== 'string') {
    return ''
  }

  let url = rawUrl.trim()
  if (!url || url.startsWith('blob:')) {
    return ''
  }

  if (url.startsWith('//')) {
    url = `https:${url}`
  }

  if (url.startsWith('/api/v1/video/proxy2')) {
    return toBackendUrl(url)
  }

  if (url.startsWith('/v1/video/proxy2')) {
    return toBackendUrl(`/api${url}`)
  }

  if (url.startsWith('/proxy2?') || url.startsWith('/proxy/')) {
    return toBackendApiUrl(`/v1/video${url}`)
  }

  if (/^https?:\/\//i.test(url)) {
    if (!isLikelyPreviewMediaUrl(url)) {
      return ''
    }
    return toBackendApiUrl(`/v1/video/proxy2?url=${encodeURIComponent(url)}`)
  }

  if (url.startsWith('/')) {
    if (!isLikelyPreviewMediaUrl(url)) {
      return ''
    }
    return toBackendUrl(url)
  }

  if (!isLikelyPreviewMediaUrl(url)) {
    return ''
  }

  return toBackendApiUrl(`/v1/video/proxy2?url=${encodeURIComponent(`https://${url}`)}`)
}

function handlePreviewVideoError(event) {
  const mediaErrorCode = event?.target?.error?.code
  console.warn('预览视频加载失败', {
    url: previewVideoPlayerUrl.value,
    mediaErrorCode
  })
}

function isM3u8Url(url) {
  if (!url || typeof url !== 'string') {
    return false
  }
  return /\.m3u8(?:$|[?#])/i.test(url) || url.toLowerCase().includes('m3u8')
}

function destroyPreviewHls() {
  if (previewHls.value) {
    previewHls.value.destroy()
    previewHls.value = null
  }
}

async function mountPreviewVideoSource() {
  await nextTick()

  const videoEl = previewVideoPlayer.value
  const src = previewVideoPlayerUrl.value
  if (!videoEl) {
    return
  }

  destroyPreviewHls()
  videoEl.pause()
  videoEl.removeAttribute('src')
  videoEl.load()

  if (!src) {
    return
  }

  if (isM3u8Url(src)) {
    if (Hls.isSupported()) {
      const instance = new Hls({
        debug: false,
        enableWorker: true
      })

      previewHls.value = instance
      instance.loadSource(src)
      instance.attachMedia(videoEl)
      instance.on(Hls.Events.ERROR, (event, data) => {
        console.error('预览视频 HLS 错误:', event, data)
        if (data?.fatal) {
          showFailToast('预览视频播放失败，请稍后重试')
          destroyPreviewHls()
        }
      })
      return
    }

    if (videoEl.canPlayType('application/vnd.apple.mpegurl')) {
      videoEl.src = src
      return
    }

    showFailToast('当前浏览器不支持 m3u8 预览播放')
    return
  }

  videoEl.src = src
}

async function refreshPreviewVideo() {
  if (!recommendationId.value || refreshingPreviewVideo.value) {
    return
  }

  refreshingPreviewVideo.value = true
  showLoadingToast({
    message: '正在更新预览视频...',
    forbidClick: true
  })

  try {
    const response = await videoApi.refreshPreviewVideo(recommendationId.value, 'preview')
    closeToast()

    if (response?.code !== 200 || !response?.data) {
      showFailToast(response?.msg || '更新预览视频失败')
      return
    }

    recommendation.value = response.data
    if (response.data?.score) {
      scoreValue.value = response.data.score
    }
    await mountPreviewVideoSource()
    showSuccessToast('预览视频链接已刷新，后台正在重新下载')
  } catch (error) {
    closeToast()
    console.error('更新预览视频失败:', error)
    showFailToast('更新预览视频失败')
  } finally {
    refreshingPreviewVideo.value = false
  }
}

async function loadVideo() {
  loading.value = true
  try {
    const data = await videoRecommendationStore.fetchDetail(recommendationId.value)
    recommendation.value = data
    if (data?.score) {
      scoreValue.value = data.score
    }
    if (data?.list_ids) {
      selectedListIds.value = [...data.list_ids]
    }
  } finally {
    loading.value = false
  }

  Promise.allSettled([
    listStore.fetchLists('video'),
    actorStore.fetchList()
  ]).catch((error) => {
    console.warn('加载附加数据失败:', error)
  })
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
  if (selectedListIds.value.length === 0 && (!recommendation.value.list_ids || recommendation.value.list_ids.length === 0)) {
    showFailToast('请选择清单')
    return
  }
  
  try {
    const { addCount, removeCount, unchanged } = await applyListMembershipChanges({
      listStore,
      contentType: 'video',
      selectedListIds: selectedListIds.value,
      currentListIds: recommendation.value.list_ids || [],
      itemId: recommendationId.value,
      source: 'preview'
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
  const success = await videoRecommendationStore.updateScore(recommendationId.value, value)
  if (success) {
    showSuccessToast('评分已更新')
  } else {
    showFailToast('评分失败')
  }
}

function goToActor(actorName) {
  router.push({ name: 'Preview', query: { author: actorName } })
}

function filterByTag(tagId) {
  router.push({ name: 'Preview', query: { tagId: tagId } })
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
    images: preferredThumbnailImages.value.map(img => getCoverUrl(img)),
    startPosition: index,
    closeable: true,
    closeIcon: 'close'
  })
}

async function handleMoveToTrash() {
  try {
    await showConfirmDialog({
      title: '确认操作',
      message: '确定将此视频移入回收站吗？'
    })
    
    const success = await videoRecommendationStore.moveToTrash(recommendationId.value)
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
      
      const success = await videoRecommendationStore.deletePermanently(recommendationId.value)
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
        title: recommendation.value.title,
        text: `${recommendation.value.code} - ${recommendation.value.title}`
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
  if (!recommendation.value?.code) {
    showFailToast('视频没有番号信息')
    return
  }
  
  showLoadingToast({
    message: '加载播放链接...',
    forbidClick: true
  })
  
  try {
    const response = await videoApi.getRecommendationPlayUrls(recommendationId.value)
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
    if (recommendation.value) {
      selectedListIds.value = [...(recommendation.value.list_ids || [])]
    }
  }
})

watch(
  [previewVideoPlayerUrl, loading],
  ([, isLoading]) => {
    if (isLoading) {
      return
    }
    mountPreviewVideoSource()
  },
  { immediate: true, flush: 'post' }
)

onUnmounted(() => {
  // 清理 HLS 实例
  if (hls.value) {
    hls.value.destroy()
    hls.value = null
  }
  destroyPreviewHls()
})
</script>

<style scoped>
.video-detail {
  min-height: 100vh;
  background: transparent;
  color: var(--text-primary);
}

.loading-center {
  display: flex;
  justify-content: center;
  padding-top: 92px;
}

.detail-content {
  padding-bottom: 24px;
}

.video-preview {
  background: var(--surface-3);
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 14px 28px rgba(17, 27, 45, 0.18);
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
  top: 10px;
  left: 10px;
  z-index: 2;
}

.cover-image {
  width: 100%;
  max-height: 340px;
  object-fit: cover;
}

.play-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, rgba(8, 15, 30, 0.16) 0%, rgba(6, 13, 24, 0.62) 100%);
  transition: background var(--motion-base) var(--ease-standard);
}

.video-preview:hover .play-overlay {
  background: linear-gradient(180deg, rgba(8, 15, 30, 0.08) 0%, rgba(6, 13, 24, 0.44) 100%);
}

.play-icon {
  font-size: 64px;
  color: rgba(255, 255, 255, 0.94);
  text-shadow: 0 8px 18px rgba(0, 0, 0, 0.4);
}

.play-text {
  margin-top: 8px;
  color: rgba(255, 255, 255, 0.92);
  font-size: 15px;
  font-weight: 600;
}

.video-player-section {
  background: var(--surface-3);
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 14px 28px rgba(17, 27, 45, 0.16);
}

.video-wrapper {
  position: relative;
  padding-bottom: 56.25%;
  height: 0;
  overflow: hidden;
}

.video-element {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.player-controls {
  padding: 12px 16px;
  background: var(--surface-2);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  border-top: 1px solid var(--border-soft);
}

.source-selector {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.resolution-badge {
  margin-left: 4px;
  font-size: 10px;
  padding: 2px 6px;
  background: var(--surface-1);
  border: 1px solid var(--border-soft);
  color: var(--text-secondary);
  border-radius: 4px;
}

.quality-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.quality-label {
  color: var(--text-secondary);
  font-size: 14px;
}

.video-info {
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  box-shadow: 0 10px 24px rgba(17, 27, 45, 0.08);
  padding: 16px;
  margin-top: 12px;
  margin-bottom: 12px;
}

.video-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-strong);
  margin-bottom: 14px;
}

.info-row {
  display: flex;
  align-items: flex-start;
  margin-bottom: 12px;
}

.info-row .label {
  width: 70px;
  font-size: 14px;
  color: var(--text-secondary);
  font-weight: 600;
  flex-shrink: 0;
}

.info-row .value {
  font-size: 14px;
  color: var(--text-strong);
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

.subscribe-button,
.subscribed-tag {
  flex-shrink: 0;
}

.score-row {
  align-items: center;
}

.score-controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.score-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 58px;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #ffc657 0%, #f78a1d 70%);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  box-shadow: 0 6px 12px rgba(245, 154, 34, 0.34);
}

.score-chip.is-empty {
  background: rgba(80, 107, 156, 0.16);
  color: var(--text-secondary);
  box-shadow: none;
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
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
  padding: 0 2px;
}

.action-buttons .van-button {
  min-width: 80px;
}

.magnets-section {
  margin-bottom: 12px;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  overflow: hidden;
}

.preview-video-section {
  margin-bottom: 12px;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  overflow: hidden;
  background: var(--surface-2);
}

.preview-video-player-container {
  padding: 12px;
}

.preview-video-actions {
  padding: 12px 12px 0;
  display: flex;
  justify-content: flex-end;
}

.preview-video-player {
  width: 100%;
  display: block;
  border-radius: 10px;
  background: #000;
  aspect-ratio: 16 / 9;
}

.preview-video-empty {
  border: 1px dashed var(--border-soft);
  border-radius: 10px;
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 13px;
  padding: 12px;
  text-align: center;
}

.thumbnails-section {
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  overflow: hidden;
}

.thumbnail-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  padding: 12px;
}

.thumbnail-item {
  aspect-ratio: 16/9;
  border-radius: 8px;
  overflow: hidden;
}

.video-detail-desktop .detail-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px 20px 28px;
}

.video-detail-desktop .video-preview {
  border-radius: 16px;
}

.video-detail-desktop .cover-container {
  max-width: 760px;
}

.video-detail-desktop .cover-image {
  max-height: 460px;
}

.video-detail-desktop .play-icon {
  font-size: 82px;
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
  border-radius: 0 0 16px 16px;
}

.video-detail-desktop .video-info {
  border-radius: 16px;
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

.video-detail-desktop .preview-video-player-container {
  padding: 16px;
}

.video-detail-desktop .preview-video-player {
  border-radius: 12px;
}

.list-popup {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.list-count {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-left: 4px;
}

.list-action {
  padding: 16px;
}

@media (max-width: 767px) {
  .video-detail-mobile .detail-content {
    padding: 10px 10px 76px;
  }

  .video-preview,
  .video-player-section,
  .video-info,
  .magnets-section,
  .preview-video-section,
  .thumbnails-section {
    border-radius: 12px;
  }

  .cover-image {
    max-height: 250px;
  }

  .play-icon {
    font-size: 54px;
  }

  .action-buttons {
    position: sticky;
    bottom: 62px;
    z-index: 8;
    padding: 10px;
    background: var(--surface-2);
    backdrop-filter: blur(10px);
    border: 1px solid var(--border-soft);
    border-radius: 14px;
    box-shadow: 0 10px 22px rgba(17, 27, 45, 0.14);
  }

  .thumbnail-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>

