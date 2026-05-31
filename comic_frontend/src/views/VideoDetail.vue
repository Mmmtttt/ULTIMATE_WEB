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
            @error="handlePlayerElementError"
          ></video>
        </div>
        <div class="player-controls">
          <div v-if="primarySourceGroups.length > 1" class="source-selector">
            <span class="source-label">播放源</span>
            <van-button
              v-for="group in primarySourceGroups"
              :key="group.key"
              :type="activePrimarySourceKey === group.key ? 'primary' : 'default'"
              size="small"
              class="episode-button"
              @click="switchPrimarySourceGroup(group)"
            >
              {{ group.label }}
              <span v-if="!group.available" class="resolution-badge">
                不可用
              </span>
            </van-button>
          </div>
          <div v-if="currentProviderGroups.length > 1" class="source-selector">
            <span class="source-label">{{ activePrimarySourceKey === 'remote' ? '远程平台' : '播放平台' }}</span>
            <van-button 
              v-for="group in currentProviderGroups"
              :key="group.key"
              :type="activeProviderKey === group.key ? 'primary' : 'default'"
              size="small"
              class="episode-button"
              @click="switchProviderGroup(group)"
            >
              {{ group.label }}
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
            v-if="preferredCoverUrl"
            :src="preferredCoverUrl" 
            fit="cover"
            class="cover-image"
          />
          <div v-else class="cover-placeholder">
            <van-icon name="video-o" />
            <span>暂无封面</span>
          </div>
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

      <div v-if="detailEpisodeList.length > 1" class="episode-section">
        <div class="episode-section-header">
          <span>{{ activePrimarySourceLabel }}选集</span>
          <span>{{ detailEpisodeList.length }} 集</span>
        </div>
        <div class="episode-grid">
          <button
            v-for="episode in detailEpisodeList"
            :key="episode.index"
            type="button"
            class="episode-card"
            :class="{ 'is-active': currentEpisodeIndex === episode.index }"
            @click="playEpisode(episode)"
          >
            <span class="episode-index">{{ episode.index }}</span>
            <span class="episode-name">{{ episode.name }}</span>
          </button>
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

        <div v-if="videoStoragePath" class="info-row">
          <span class="label">Path:</span>
          <span class="value path-value" :title="videoStoragePath">{{ videoStoragePath }}</span>
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
            <span class="score-chip" :class="{ 'is-empty': !video.score }">{{ video.score || '未评分' }}</span>
          </div>
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
      
      <div v-if="video.magnets && video.magnets.length > 0" class="magnets-section">
        <van-cell
          class="magnets-toggle"
          :title="`磁力链接（${video.magnets.length}）`"
          :value="showMagnets ? '收起' : '展开'"
          is-link
          @click="showMagnets = !showMagnets"
        />
        <van-cell-group v-show="showMagnets">
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

      <div v-if="video" class="preview-video-section">
        <van-cell-group title="预览视频">
          <div class="preview-video-actions">
            <van-button
              v-if="isLocalVideo"
              size="small"
              plain
              type="success"
              :loading="refreshingLocalMetadata"
              @click="refreshLocalMetadata"
            >
              更新详情信息
            </van-button>
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
          <div v-if="previewAssetList.length > 1" class="preview-video-source-selector">
            <van-button
              v-for="asset in previewAssetList"
              :key="asset.key"
              size="small"
              :type="activePreviewAssetKey === asset.key ? 'primary' : 'default'"
              class="preview-video-source-button"
              @click="selectPreviewAsset(asset.key)"
            >
              {{ asset.label }}
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
            <div
              v-for="(img, index) in preferredThumbnailImages"
              :key="index"
              class="thumbnail-card"
              @click="previewImages(index)"
            >
              <van-image
                :src="getCoverUrl(img)"
                fit="cover"
                class="thumbnail-item"
              />
              <span
                v-if="isCurrentLocalCoverThumbnail(index)"
                class="thumbnail-cover-badge"
              >
                当前封面
              </span>
            </div>
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

    <van-popup
      v-model:show="showThumbnailPicker"
      position="bottom"
      round
      class="thumbnail-picker-popup"
      :style="thumbnailPickerPopupStyle"
    >
      <div class="thumbnail-picker">
        <van-nav-bar title="选择视频封面">
          <template #right>
            <van-button
              type="primary"
              size="small"
              :disabled="!canSubmitThumbnailCover"
              :loading="savingThumbnailCover"
              @click="saveThumbnailCoverSelection"
            >
              设为封面
            </van-button>
          </template>
        </van-nav-bar>

        <div class="thumbnail-picker-hint">
          从已生成的本地缩略图里选择一张，作为这个视频的封面。
        </div>

        <div v-if="localThumbnailImages.length > 0" class="thumbnail-picker-grid">
          <button
            v-for="(img, index) in localThumbnailImages"
            :key="img || index"
            type="button"
            class="thumbnail-picker-card"
            :class="{
              'is-selected': selectedThumbnailCoverIndex === index,
              'is-current': currentLocalCoverIndex === index
            }"
            @click="selectedThumbnailCoverIndex = index"
          >
            <img
              :src="getCoverUrl(img)"
              alt=""
              class="thumbnail-picker-image"
            />
            <span v-if="currentLocalCoverIndex === index" class="thumbnail-picker-badge">
              当前封面
            </span>
            <span v-else-if="selectedThumbnailCoverIndex === index" class="thumbnail-picker-badge is-pending">
              待设为封面
            </span>
          </button>
        </div>

        <div v-else class="thumbnail-picker-empty">
          还没有可用的本地缩略图，请先在右上角菜单里生成。
        </div>
      </div>
    </van-popup>

    <van-popup 
      v-model:show="showEditPopup" 
      position="bottom" 
      round 
      :style="{ height: '60%' }"
    >
      <div class="edit-popup">
        <van-nav-bar title="编辑视频信息">
          <template #right>
            <van-button type="primary" size="small" @click="saveEdit">保存</van-button>
          </template>
        </van-nav-bar>

        <van-cell-group inset>
          <van-field v-model="editForm.title" label="标题" placeholder="请输入标题" />
          <van-field v-model="editForm.code" label="番号" placeholder="请输入番号" />
          <van-field v-model="editForm.date" label="日期" placeholder="请输入发布日期" />
          <van-field v-model="editForm.series" label="系列" placeholder="请输入系列名称" />
          <van-field
            v-model="editForm.actors"
            label="演员"
            placeholder="多个演员请用逗号分隔"
          />
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
                  <span class="tag-count">({{ tag.video_count || 0 }})</span>
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
import { useVideoStore, useListStore, useActorStore, useTagStore } from '@/stores'
import { EmptyState } from '@/components'
import { useDevice } from '@/composables/useDevice'
import { copyTextToClipboard } from '@/runtime/browser'
import { applyListMembershipChanges, buildListChangeMessage, getCoverUrl } from '@/utils'
import {
  buildEpisodeListFromPlayableSources,
  resolvePlayProviderGroups,
  resolveVideoPlaybackModel
} from '@/utils/videoPlaybackModel'
import Hls from 'hls.js'

const route = useRoute()
const router = useRouter()
const videoStore = useVideoStore()
const listStore = useListStore()
const actorStore = useActorStore()
const tagStore = useTagStore()
const { isDesktop, isMobile } = useDevice()

const video = ref(null)
const loading = ref(true)
const showActions = ref(false)
const showEditPopup = ref(false)
const showTagPopup = ref(false)
const showListPopup = ref(false)
const showThumbnailPicker = ref(false)
const allTags = ref([])
const selectedTagIds = ref([])
const selectedListIds = ref([])
const selectedThumbnailCoverIndex = ref(-1)
const scoreValue = ref(0)
const subscribingActors = ref([])
const showMagnets = ref(false)

const editForm = ref({
  title: '',
  code: '',
  date: '',
  series: '',
  actors: '',
  desc: ''
})

// 播放器相关
const showPlayer = ref(false)
const videoPlayer = ref(null)
const playSources = ref([])
const playerProviderGroups = ref([])
const loadedPlaybackSourceKey = ref('')
const currentSource = ref('')
const currentStreams = ref([])
const currentQuality = ref(0)
const activePrimarySourceKey = ref('')
const activeProviderKey = ref('')
const previewVideoPlayer = ref(null)
const activePreviewAssetKey = ref('')
const assetRefreshTimer = ref(null)
const assetRefreshAttempts = ref(0)
const refreshingPreviewVideo = ref(false)
const refreshingLocalMetadata = ref(false)
const generatingLocalThumbnails = ref(false)
const savingThumbnailCover = ref(false)

const hls = ref(null)
const previewHls = ref(null)
const MAX_ASSET_REFRESH_ATTEMPTS = 4
const ASSET_REFRESH_DELAY_MS = 2500

const videoId = computed(() => route.params.id)
const isLocalVideo = computed(() => video.value?.source !== 'preview')

const actions = computed(() => {
  if (video.value?.is_deleted) {
    return [
      { name: '永久删除', value: 'delete', color: '#ee0a24' }
    ]
  }

  const menuActions = []
  if (isLocalVideo.value) {
    if (localThumbnailCapability.value.show_generate_action) {
      const generateAction = {
        name: localThumbnailImages.value.length > 0 ? '重新生成缩略图' : '生成缩略图',
        value: 'generate_local_thumbnails',
        disabled: !localThumbnailCapability.value.can_generate
      }
      const capabilityReason = String(localThumbnailCapability.value.reason || '').trim()
      if (!localThumbnailCapability.value.can_generate && capabilityReason) {
        generateAction.subname = capabilityReason
      }
      menuActions.push(generateAction)
    }
    if (localThumbnailCapability.value.can_select_cover) {
      menuActions.push({ name: '选择封面', value: 'select_local_thumbnail_cover' })
    }
    menuActions.push(
      { name: '更新详情信息', value: 'refresh_local_metadata' },
      { name: '编辑信息', value: 'edit' },
      { name: '绑定标签', value: 'tags' }
    )
  }
  menuActions.push(
    { name: '移入回收站', value: 'trash', color: '#ee0a24' }
  )
  return menuActions
})

const isFavoritedVideo = computed(() => {
  return listStore.isFavoritedVideo(video.value)
})

const customLists = computed(() => listStore.lists || [])
const preferredCoverPath = computed(() => {
  const localPath = String(video.value?.cover_path_local || '').trim()
  const remotePath = String(video.value?.cover_path || '').trim()
  return localPath || remotePath
})
const preferredCoverUrl = computed(() => getCoverUrl({
  cover_path_local: String(video.value?.cover_path_local || '').trim(),
  cover_path: String(video.value?.cover_path || '').trim() || preferredCoverPath.value,
  local_cover_asset_version: String(video.value?.local_cover_asset_version || '').trim()
}))
const preferredThumbnailImages = computed(() => {
  const local = Array.isArray(video.value?.thumbnail_images_local) ? video.value.thumbnail_images_local : []
  const remote = Array.isArray(video.value?.thumbnail_images) ? video.value.thumbnail_images : []
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
const playbackModel = computed(() => resolveVideoPlaybackModel(video.value))
const primaryPlayback = computed(() => playbackModel.value.primary || {})
const previewPlayback = computed(() => playbackModel.value.preview || {})
const primarySourceGroups = computed(() => {
  const groups = Array.isArray(primaryPlayback.value.source_groups) ? primaryPlayback.value.source_groups : []
  return groups.filter((group) => group && group.available)
})
const activePrimarySourceGroup = computed(() => {
  const groups = primarySourceGroups.value
  if (!groups.length) {
    return null
  }
  return groups.find((group) => group.key === activePrimarySourceKey.value) || groups[0]
})
const activePrimarySourceLabel = computed(() => {
  return String(activePrimarySourceGroup.value?.label || '当前').trim() || '当前'
})
const currentProviderGroups = computed(() => {
  return playerProviderGroups.value.filter((group) => group)
})
const activeProviderGroup = computed(() => {
  const groups = currentProviderGroups.value
  if (!groups.length) {
    return null
  }
  return groups.find((group) => group.key === activeProviderKey.value) || groups[0]
})
const previewAssetList = computed(() => {
  const assets = Array.isArray(previewPlayback.value.assets) ? previewPlayback.value.assets : []
  return assets.filter((asset) => String(asset?.url || '').trim())
})
const activePreviewAsset = computed(() => {
  const assets = previewAssetList.value
  if (!assets.length) {
    return null
  }
  return assets.find((asset) => asset.key === activePreviewAssetKey.value) || assets[0]
})
const previewVideoPlayerUrl = computed(() => {
  return resolvePreviewVideoUrl(activePreviewAsset.value?.url || '')
})
const previewRefreshSource = computed(() => (video.value?.source === 'preview' ? 'preview' : 'local'))
const hasPreviewVideo = computed(() => Boolean(previewVideoPlayerUrl.value))
const detailEpisodeList = computed(() => {
  if (showPlayer.value && loadedPlaybackSourceKey.value === activePrimarySourceKey.value) {
    const providerGroup = activeProviderGroup.value
    if (providerGroup?.selection_mode === 'episodes') {
      return buildEpisodeListFromPlayableSources(providerGroup.sources)
    }
    return []
  }

  const episodes = Array.isArray(activePrimarySourceGroup.value?.episodes) ? activePrimarySourceGroup.value.episodes : []
  return episodes
    .map((episode, index) => {
      const fallbackIndex = index + 1
      const normalizedIndex = Number(episode?.index) || fallbackIndex
      const name = String(episode?.name || `第 ${normalizedIndex} 集`).trim()
      return {
        index: normalizedIndex,
        name: name || `第 ${normalizedIndex} 集`
      }
    })
    .filter((episode) => episode.index > 0)
})
const hasLocalPlayableSource = computed(() => {
  return Boolean(
    primarySourceGroups.value.length > 0 ||
    detailEpisodeList.value.length > 0 ||
    String(video.value?.local_source_path || video.value?.storage_path || '').trim()
  )
})
const videoStoragePath = computed(() => {
  const path = String(video.value?.storage_path || video.value?.local_source_path || '').trim()
  return path
})
const localThumbnailCapability = computed(() => {
  const capability = video.value?.local_thumbnail_capability
  if (!capability || typeof capability !== 'object') {
    return {
      supported: false,
      has_local_source: false,
      show_generate_action: false,
      can_generate: false,
      can_select_cover: false,
      generated_count: 0,
      target_count: 20,
      selected_index: -1,
      reason: ''
    }
  }
  return capability
})
const localThumbnailImages = computed(() => {
  const thumbnails = Array.isArray(video.value?.thumbnail_images_local) ? video.value.thumbnail_images_local : []
  return thumbnails.filter((item) => String(item || '').trim())
})
const currentLocalCoverIndex = computed(() => {
  const rawIndex = Number(video.value?.local_cover_thumbnail_index)
  if (!Number.isInteger(rawIndex) || rawIndex < 0 || rawIndex >= localThumbnailImages.value.length) {
    return -1
  }
  return rawIndex
})
const canSubmitThumbnailCover = computed(() => {
  return (
    selectedThumbnailCoverIndex.value >= 0 &&
    selectedThumbnailCoverIndex.value < localThumbnailImages.value.length &&
    selectedThumbnailCoverIndex.value !== currentLocalCoverIndex.value
  )
})
const thumbnailPickerPopupStyle = computed(() => ({
  height: isDesktop.value ? '72%' : '78%'
}))

function syncThumbnailSelectionState(detail = video.value) {
  const thumbnails = Array.isArray(detail?.thumbnail_images_local) ? detail.thumbnail_images_local : []
  const rawIndex = Number(detail?.local_cover_thumbnail_index)
  if (Number.isInteger(rawIndex) && rawIndex >= 0 && rawIndex < thumbnails.length) {
    selectedThumbnailCoverIndex.value = rawIndex
    return
  }
  selectedThumbnailCoverIndex.value = thumbnails.length > 0 ? 0 : -1
}

function openThumbnailPicker() {
  syncThumbnailSelectionState()
  showThumbnailPicker.value = true
}

function isCurrentLocalCoverThumbnail(index) {
  return (
    index >= 0 &&
    index < localThumbnailImages.value.length &&
    currentLocalCoverIndex.value === index
  )
}

function clearAssetRefreshTimer() {
  if (assetRefreshTimer.value) {
    clearTimeout(assetRefreshTimer.value)
    assetRefreshTimer.value = null
  }
}

function syncPreviewAssetSelection(detail = video.value) {
  const model = resolveVideoPlaybackModel(detail)
  const assets = Array.isArray(model?.preview?.assets) ? model.preview.assets : []
  if (!assets.length) {
    activePreviewAssetKey.value = ''
    return
  }

  if (assets.some((asset) => asset.key === activePreviewAssetKey.value)) {
    return
  }

  activePreviewAssetKey.value = String(model?.preview?.default_asset_key || assets[0]?.key || '').trim()
}

function syncPrimarySourceSelection(detail = video.value) {
  const model = resolveVideoPlaybackModel(detail)
  const groups = Array.isArray(model?.primary?.source_groups) ? model.primary.source_groups : []
  if (!groups.length) {
    activePrimarySourceKey.value = ''
    return
  }

  const defaultSourceKey = String(model?.primary?.default_source_key || groups[0]?.key || '').trim()
  const matchedGroup = groups.find((group) => group.key === activePrimarySourceKey.value)
  const activeGroup = matchedGroup || groups.find((group) => group.key === defaultSourceKey) || groups[0]
  activePrimarySourceKey.value = String(activeGroup?.key || '').trim()
}

function selectPreviewAsset(assetKey) {
  const normalizedKey = String(assetKey || '').trim()
  if (!normalizedKey || normalizedKey === activePreviewAssetKey.value) {
    return
  }
  activePreviewAssetKey.value = normalizedKey
}

function isLocalPreviewAssetPath(path) {
  if (!path || typeof path !== 'string') {
    return false
  }
  return path.startsWith('/media/')
}

function hasPendingLocalAssets(detail) {
  if (!detail || typeof detail !== 'object') {
    return false
  }

  const localCover = String(detail.cover_path_local || '').trim()
  const remoteCover = String(detail.cover_path || '').trim()
  const coverPath = localCover || remoteCover

  const localThumbnails = Array.isArray(detail.thumbnail_images_local) ? detail.thumbnail_images_local : []
  const remoteThumbnails = Array.isArray(detail.thumbnail_images) ? detail.thumbnail_images : []
  const thumbnails = localThumbnails.length > 0 ? localThumbnails : remoteThumbnails

  const coverNeedsRefresh = Boolean(coverPath) && !isLocalPreviewAssetPath(coverPath)
  const thumbsNeedRefresh = thumbnails.some((item) => {
    const value = String(item || '').trim()
    return Boolean(value) && !isLocalPreviewAssetPath(value)
  })

  return coverNeedsRefresh || thumbsNeedRefresh
}

function scheduleLocalAssetRefresh() {
  clearAssetRefreshTimer()

  if (!isLocalVideo.value || !video.value || !hasPendingLocalAssets(video.value)) {
    return
  }

  if (assetRefreshAttempts.value >= MAX_ASSET_REFRESH_ATTEMPTS) {
    return
  }

  assetRefreshAttempts.value += 1
  assetRefreshTimer.value = setTimeout(async () => {
    try {
      const detail = await videoStore.fetchDetailSnapshot(videoId.value)
      if (detail) {
        video.value = detail
        syncPrimarySourceSelection(detail)
        syncPreviewAssetSelection(detail)
        if (detail?.score) {
          scoreValue.value = detail.score
        }
      }
    } catch (error) {
      console.warn('刷新本地资源失败:', error)
    } finally {
      if (hasPendingLocalAssets(video.value)) {
        scheduleLocalAssetRefresh()
      }
    }
  }, ASSET_REFRESH_DELAY_MS)
}

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
    return url
  }

  if (url.startsWith('/v1/video/proxy2')) {
    return `/api${url}`
  }

  if (url.startsWith('/proxy2?') || url.startsWith('/proxy/')) {
    return `/api/v1/video${url}`
  }

  if (/^https?:\/\//i.test(url)) {
    if (!isLikelyPreviewMediaUrl(url)) {
      return ''
    }
    return `/api/v1/video/proxy2?url=${encodeURIComponent(url)}`
  }

  if (url.startsWith('/')) {
    if (!isLikelyPreviewMediaUrl(url)) {
      return ''
    }
    return url
  }

  if (!isLikelyPreviewMediaUrl(url)) {
    return ''
  }

  return `/api/v1/video/proxy2?url=${encodeURIComponent(`https://${url}`)}`
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
  if (!videoId.value || refreshingPreviewVideo.value) {
    return
  }

  refreshingPreviewVideo.value = true
  showLoadingToast({
    message: '正在更新预览视频...',
    forbidClick: true
  })

  try {
    const response = await videoStore.refreshPreviewVideo(videoId.value, previewRefreshSource.value)
    closeToast()

    if (response?.code !== 200 || !response?.data) {
      showFailToast(response?.msg || '更新预览视频失败')
      return
    }

    video.value = response.data
    showMagnets.value = false
    syncPrimarySourceSelection(response.data)
    syncPreviewAssetSelection(response.data)
    syncThumbnailSelectionState(response.data)
    if (response.data?.score) {
      scoreValue.value = response.data.score
    }
    scheduleLocalAssetRefresh()
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

async function refreshLocalMetadata() {
  if (!videoId.value || refreshingLocalMetadata.value || !isLocalVideo.value) {
    return
  }

  refreshingLocalMetadata.value = true
  showLoadingToast({
    message: '正在更新详情信息...',
    forbidClick: true
  })

  try {
    const response = await videoStore.refreshLocalMetadata(videoId.value)
    closeToast()

    if (response?.code !== 200 || !response?.data) {
      showFailToast(response?.msg || '更新详情信息失败')
      return
    }

    video.value = response.data
    selectedTagIds.value = [...(response.data?.tag_ids || [])]
    syncEditFormFromVideo(response.data)
    syncPrimarySourceSelection(response.data)
    syncPreviewAssetSelection(response.data)
    syncThumbnailSelectionState(response.data)
    if (response.data?.score) {
      scoreValue.value = response.data.score
    }
    await fetchAllTags()
    scheduleLocalAssetRefresh()
    await mountPreviewVideoSource()
    showSuccessToast(response?.msg || '详情信息已更新')
  } catch (error) {
    closeToast()
    console.error('更新详情信息失败:', error)
    showFailToast(error?.message || '更新详情信息失败')
  } finally {
    refreshingLocalMetadata.value = false
  }
}

async function generateLocalThumbnails() {
  if (!videoId.value || generatingLocalThumbnails.value) {
    return
  }
  if (!localThumbnailCapability.value.can_generate) {
    showFailToast(localThumbnailCapability.value.reason || '当前环境暂不可生成缩略图')
    return
  }

  generatingLocalThumbnails.value = true
  showLoadingToast({
    message: '正在生成 20 张缩略图...',
    forbidClick: true,
    duration: 0
  })

  try {
    const response = await videoStore.generateLocalThumbnails(videoId.value)
    closeToast()

    if (response?.code !== 200 || !response?.data) {
      showFailToast(response?.msg || '生成缩略图失败')
      return
    }

    video.value = response.data
    syncPrimarySourceSelection(response.data)
    syncPreviewAssetSelection(response.data)
    syncThumbnailSelectionState(response.data)
    showMagnets.value = false
    showThumbnailPicker.value = true
    showSuccessToast(response?.msg || '缩略图生成成功')
  } catch (error) {
    closeToast()
    console.error('生成本地缩略图失败:', error)
    showFailToast(error?.message || '生成缩略图失败')
  } finally {
    generatingLocalThumbnails.value = false
  }
}

async function saveThumbnailCoverSelection() {
  if (!videoId.value || savingThumbnailCover.value || !canSubmitThumbnailCover.value) {
    return
  }

  savingThumbnailCover.value = true
  showLoadingToast({
    message: '正在更新封面...',
    forbidClick: true
  })

  try {
    const response = await videoStore.selectLocalThumbnailCover(
      videoId.value,
      selectedThumbnailCoverIndex.value
    )
    closeToast()

    if (response?.code !== 200 || !response?.data) {
      showFailToast(response?.msg || '设置封面失败')
      return
    }

    video.value = response.data
    syncPrimarySourceSelection(response.data)
    syncPreviewAssetSelection(response.data)
    syncThumbnailSelectionState(response.data)
    showThumbnailPicker.value = false
    showSuccessToast(response?.msg || '封面已更新')
  } catch (error) {
    closeToast()
    console.error('设置本地缩略图封面失败:', error)
    showFailToast(error?.message || '设置封面失败')
  } finally {
    savingThumbnailCover.value = false
  }
}

function syncEditFormFromVideo(detail) {
  if (!detail) {
    return
  }
  editForm.value = {
    title: detail.title || '',
    code: detail.code || '',
    date: detail.date || '',
    series: detail.series || '',
    actors: Array.isArray(detail.actors) ? detail.actors.join(', ') : '',
    desc: detail.desc || ''
  }
}

async function fetchAllTags() {
  try {
    const tags = await tagStore.fetchTags('video')
    allTags.value = tags || []
  } catch (error) {
    console.error('获取视频标签失败:', error)
    allTags.value = []
  }
}

async function loadVideo() {
  clearAssetRefreshTimer()
  assetRefreshAttempts.value = 0
  loading.value = true
  try {
    const data = await videoStore.fetchDetail(videoId.value)
    video.value = data
    showMagnets.value = false
    if (data?.score) {
      scoreValue.value = data.score
    }
    if (data?.list_ids) {
      selectedListIds.value = [...data.list_ids]
    }
    selectedTagIds.value = [...(data?.tag_ids || [])]
    syncEditFormFromVideo(data)
    syncPrimarySourceSelection(data)
    syncPreviewAssetSelection(data)
    syncThumbnailSelectionState(data)
    scheduleLocalAssetRefresh()
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

function normalizeActorName(actorName) {
  return String(actorName || '').trim().toLocaleLowerCase()
}

function getActorRefForName(actorName) {
  const targetName = normalizeActorName(actorName)
  const actorRefs = Array.isArray(video.value?.actor_refs) ? video.value.actor_refs : []
  return actorRefs.find((ref) => {
    const refName = normalizeActorName(ref?.actor_name || ref?.name)
    return refName && refName === targetName
  })
}

function buildActorSubscribeOptions(actorName) {
  const actorRef = getActorRefForName(actorName)
  return actorRef ? { actorRefs: [actorRef] } : {}
}

async function subscribeActor(actorName) {
  if (subscribingActors.value.includes(actorName)) return
  
  subscribingActors.value.push(actorName)
  try {
    const result = await actorStore.subscribe(actorName, buildActorSubscribeOptions(actorName))
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
    await copyTextToClipboard(text)
    showSuccessToast('已复制磁力链接')
  } catch (error) {
    console.error('复制磁力链接失败:', error)
    showFailToast('复制失败，请手动复制')
  }
}

function previewImages(index) {
  showImagePreview({
    images: preferredThumbnailImages.value.map(img => getCoverUrl(img)),
    startPosition: index,
    closeable: true,
    closeIcon: 'close'
  })
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
  if (!video.value || !isLocalVideo.value) {
    showFailToast('仅本地库视频支持绑定标签')
    return
  }

  try {
    const response = await videoStore.bindTags(videoId.value, selectedTagIds.value)
    if (response.code === 200) {
      showTagPopup.value = false
      await loadVideo()
      showSuccessToast('标签绑定成功')
    } else {
      showFailToast(response.msg || '标签绑定失败')
    }
  } catch (error) {
    console.error('绑定标签失败:', error)
    showFailToast('标签绑定失败')
  }
}

async function saveEdit() {
  if (!video.value || !isLocalVideo.value) {
    showFailToast('仅本地库视频支持编辑')
    return
  }

  try {
    const actorList = (editForm.value.actors || '')
      .replace(/，/g, ',')
      .split(',')
      .map(actor => actor.trim())
      .filter(Boolean)

    const payload = {
      title: editForm.value.title?.trim(),
      code: editForm.value.code?.trim(),
      date: editForm.value.date?.trim(),
      series: editForm.value.series?.trim(),
      actors: actorList,
      creator: actorList[0] || '',
      desc: editForm.value.desc?.trim()
    }

    const response = await videoStore.editVideo(videoId.value, payload)
    if (response.code === 200) {
      showEditPopup.value = false
      await loadVideo()
      showSuccessToast('保存成功')
    } else {
      showFailToast(response.msg || '保存失败')
    }
  } catch (error) {
    console.error('保存视频信息失败:', error)
    showFailToast('保存失败')
  }
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
  
  if (action.value === 'edit') {
    syncEditFormFromVideo(video.value)
    showEditPopup.value = true
  } else if (action.value === 'generate_local_thumbnails') {
    await generateLocalThumbnails()
  } else if (action.value === 'select_local_thumbnail_cover') {
    openThumbnailPicker()
  } else if (action.value === 'tags') {
    selectedTagIds.value = [...(video.value?.tag_ids || [])]
    await fetchAllTags()
    showTagPopup.value = true
  } else if (action.value === 'refresh_local_metadata') {
    await refreshLocalMetadata()
  } else if (action.value === 'trash') {
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

const currentEpisodeIndex = computed(() => {
  const matchedSource = availableSources.value.find((source) => sourceKey(source) === currentSource.value)
  if (matchedSource) {
    return Number(matchedSource.episode_index) || 0
  }
  const matched = String(currentSource.value || '').match(/_episode_(\d+)$/)
  return matched ? Number(matched[1]) || 0 : 0
})

function findSourceByEpisodeIndex(index, sources = availableSources.value) {
  const normalizedIndex = Number(index) || 0
  if (normalizedIndex <= 0) {
    return null
  }
  return sources.find((source) => {
    return Number(source?.episode_index) === normalizedIndex || String(sourceKey(source)).endsWith(`_episode_${normalizedIndex}`)
  }) || sources[normalizedIndex - 1] || null
}

function resolveInitialPlaybackSourceKey() {
  if (activePrimarySourceKey.value) {
    return activePrimarySourceKey.value
  }
  return String(primaryPlayback.value?.default_source_key || primarySourceGroups.value[0]?.key || '').trim()
}

async function playEpisode(episode) {
  const episodeIndex = Number(episode?.index) || 1
  if (!playSources.value.length) {
    await loadPlayUrls({
      playbackSource: resolveInitialPlaybackSourceKey(),
      episodeIndex
    })
    return
  }

  const source = findSourceByEpisodeIndex(episodeIndex)
  if (!source) {
    await loadPlayUrls({
      playbackSource: resolveInitialPlaybackSourceKey(),
      episodeIndex
    })
    return
  }

  showPlayer.value = true
  await switchSource(source)
}

async function loadPlayUrls(options = {}) {
  const playbackSource = String(options.playbackSource || resolveInitialPlaybackSourceKey()).trim()
  if (!video.value?.code && !hasLocalPlayableSource.value) {
    showFailToast('视频没有番号信息')
    return
  }

  if (!options.silentLoading) {
    showLoadingToast({
      message: playbackSource === 'remote' ? '加载远程播放源...' : '加载播放链接...',
      forbidClick: true
    })
  }
  
  try {
    const params = {}
    if (playbackSource) {
      params.playback_source = playbackSource
    }
    if (playbackSource === 'remote' && options.providerKey) {
      params.remote_provider = options.providerKey
    }
    const response = await videoStore.getPlayUrls(videoId.value, params)
    if (!options.silentLoading) {
      closeToast()
    }
    
    if (response.code === 200 && response.data) {
      const { providerGroups, defaultProviderKey } = resolvePlayProviderGroups(response.data)
      if (!providerGroups.length) {
        playSources.value = []
        playerProviderGroups.value = []
        activeProviderKey.value = ''
        showFailToast('暂无可用播放平台')
        return
      }

      playerProviderGroups.value = providerGroups
      loadedPlaybackSourceKey.value = playbackSource || resolveInitialPlaybackSourceKey()
      activePrimarySourceKey.value = loadedPlaybackSourceKey.value
      activeProviderKey.value = String(options.providerKey || defaultProviderKey || providerGroups[0]?.key || '').trim()

      showPlayer.value = true
      const providerGroup = providerGroups.find((group) => group.key === activeProviderKey.value) || providerGroups[0]
      await switchProviderGroup(providerGroup, {
        episodeIndex: options.episodeIndex,
        force: true
      })
    } else {
      showFailToast(response.msg || '加载失败')
    }
  } catch (error) {
    if (!options.silentLoading) {
      closeToast()
    }
    showFailToast('加载播放链接失败')
    console.error(error)
    throw error
  }
}

async function switchProviderGroup(group, options = {}) {
  const normalizedGroup = group && typeof group === 'object' ? group : null
  if (!normalizedGroup) {
    return
  }

  const providerSources = Array.isArray(normalizedGroup.available_sources)
    ? normalizedGroup.available_sources
    : []
  if (!providerSources.length) {
    showFailToast(normalizedGroup.error || '当前平台暂不可用')
    return
  }

  activeProviderKey.value = String(normalizedGroup.key || '').trim()
  playSources.value = providerSources

  const preferredEpisodeIndex = Number(options.episodeIndex) || currentEpisodeIndex.value || 0
  const selectedSource = normalizedGroup.selection_mode === 'episodes'
    ? (findSourceByEpisodeIndex(preferredEpisodeIndex, providerSources) || providerSources[0])
    : providerSources[0]

  if (!selectedSource) {
    showFailToast('当前平台暂无可播放内容')
    return
  }

  if (!showPlayer.value) {
    showPlayer.value = true
  }
  await switchSource(selectedSource)
}

async function switchSource(source) {
  currentSource.value = sourceKey(source)
  currentStreams.value = Array.isArray(source.streams) && source.streams.length
    ? source.streams
    : (source.url ? [{ url: source.url, resolution: source.currentResolution || '原始', type: source.type || 'direct' }] : [])
  
  if (currentStreams.value.length > 0) {
    // 默认选择最高画质
    currentQuality.value = 0
    // 等待 DOM 更新后再播放
    await nextTick()
    await playStream(currentStreams.value[0])
  }
}

async function switchPrimarySourceGroup(group) {
  const sourceKeyValue = String(group?.key || '').trim()
  if (!sourceKeyValue) {
    return
  }

  const preferredEpisodeIndex = currentEpisodeIndex.value || Number(group?.default_episode_index || 1) || 1
  activePrimarySourceKey.value = sourceKeyValue

  if (!showPlayer.value) {
    return
  }

  await loadPlayUrls({
    playbackSource: sourceKeyValue,
    episodeIndex: preferredEpisodeIndex
  })
}

function sourceKey(source) {
  return String(source?.key || source?.source || source?.name || source?.url || '')
}

function normalizePlayableUrl(rawUrl) {
  let url = String(rawUrl || '').trim()
  if (!url || url.startsWith('blob:')) {
    return ''
  }

  if (url.startsWith('//')) {
    return `https:${url}`
  }

  if (/^https?:\/\//i.test(url)) {
    return url
  }

  if (url.startsWith('/proxy2?') || url.startsWith('/proxy/')) {
    return `/api/v1/video${url}`
  }

  if (url.startsWith('/v1/')) {
    return `/api${url}`
  }

  if (url.startsWith('/api/')) {
    return url
  }

  if (url.startsWith('/')) {
    return url
  }

  if (/^[^\\/:?#]+\.[^\\/:?#]+\/.+/.test(url)) {
    return `/api/v1/video/proxy2?url=${encodeURIComponent(`https://${url}`)}`
  }

  return ''
}

function resolvePlayableStreamUrl(stream) {
  if (!stream || typeof stream !== 'object') {
    return ''
  }

  let url = String(stream.url || '').trim()
  const proxyUrl = String(stream.proxy_url || '').trim()
  if (proxyUrl) {
    url = proxyUrl.startsWith('/proxy2') || proxyUrl.startsWith('/proxy/')
      ? `/v1/video${proxyUrl}`
      : proxyUrl
  }
  return normalizePlayableUrl(url)
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
  
  const url = resolvePlayableStreamUrl(stream)
  if (!url) {
    showFailToast('播放地址不可用')
    console.warn('播放地址不可用', stream)
    return
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
          showFailToast('当前平台播放失败，请手动切换播放平台或清晰度')
        }
      })
    } else if (videoPlayer.value.canPlayType('application/vnd.apple.mpegurl')) {
      videoPlayer.value.src = url
      videoPlayer.value.play().catch(e => console.warn('播放启动失败:', e))
    } else {
      showFailToast('当前浏览器不支持播放此格式')
    }
  } else {
    // 普通视频格式
    videoPlayer.value.src = url
    videoPlayer.value.play().catch(e => console.warn('播放启动失败:', e))
  }
}

async function handlePlayerElementError(event) {
  const mediaErrorCode = event?.target?.error?.code
  console.error('主播放器加载失败', {
    videoId: videoId.value,
    activeSource: activePrimarySourceKey.value,
    providerKey: activeProviderKey.value,
    currentSource: currentSource.value,
    mediaErrorCode
  })
  showFailToast('当前平台播放失败，请手动切换播放平台')
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

watch(showTagPopup, async (val) => {
  if (val) {
    selectedTagIds.value = [...(video.value?.tag_ids || [])]
    if (allTags.value.length === 0) {
      await fetchAllTags()
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
  clearAssetRefreshTimer()
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
  min-height: 220px;
}

.cover-container {
  width: 100%;
  display: flex;
  justify-content: center;
  position: relative;
  min-height: inherit;
}

.source-tag {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 2;
}

.cover-image {
  width: 100%;
  min-height: 220px;
  max-height: 340px;
  object-fit: cover;
}

.cover-placeholder {
  width: 100%;
  min-height: 220px;
  aspect-ratio: 16 / 9;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-secondary);
  background:
    linear-gradient(135deg, rgba(42, 105, 188, 0.14), rgba(42, 105, 188, 0.03)),
    var(--surface-2);
}

.cover-placeholder .van-icon {
  font-size: 42px;
  color: rgba(42, 105, 188, 0.82);
}

.cover-placeholder span {
  font-size: 14px;
  font-weight: 600;
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
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.source-label {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
  margin-right: 2px;
}

.episode-button {
  max-width: min(260px, 100%);
}

.episode-button :deep(.van-button__text) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.episode-section {
  margin-top: 12px;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  background: var(--surface-2);
  overflow: hidden;
}

.episode-section-header {
  height: 44px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-soft);
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
}

.episode-section-header span:last-child {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.episode-grid {
  padding: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
}

.episode-card {
  min-width: 0;
  height: 42px;
  padding: 0 10px;
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  background: var(--surface-1);
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: border-color var(--motion-base) var(--ease-standard), background var(--motion-base) var(--ease-standard);
}

.episode-card.is-active {
  border-color: rgba(42, 105, 188, 0.56);
  background: rgba(42, 105, 188, 0.12);
  color: #1f5fb8;
}

.episode-index {
  flex: 0 0 auto;
  min-width: 22px;
  font-size: 12px;
  font-weight: 700;
}

.episode-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
  text-align: left;
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

.path-value {
  flex: 1;
  min-width: 0;
  word-break: break-all;
  line-height: 1.4;
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
  flex-wrap: wrap;
}

.actor-tag {
  cursor: pointer;
}

.subscribe-button,
.subscribed-tag {
  flex-shrink: 0;
}

.score-row {
  align-items: flex-start;
}

.score-controls {
  display: grid;
  gap: 8px;
  width: 100%;
  min-width: 0;
}

.score-controls :deep(.van-rate) {
  --van-rate-icon-size: 18px;
  width: max-content;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  white-space: nowrap;
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
  gap: 8px;
  justify-content: flex-end;
}

.preview-video-source-selector {
  padding: 12px 12px 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preview-video-source-button {
  min-width: 88px;
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

.thumbnail-card {
  position: relative;
  cursor: pointer;
}

.thumbnail-item {
  aspect-ratio: 16/9;
  border-radius: 8px;
  overflow: hidden;
}

.thumbnail-cover-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(14, 28, 51, 0.78);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  backdrop-filter: blur(8px);
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

.video-detail-desktop .thumbnail-picker-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.edit-popup,
.tag-popup,
.list-popup,
.thumbnail-picker {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.thumbnail-picker-popup {
  background: linear-gradient(180deg, var(--surface-1) 0%, var(--surface-2) 100%);
}

.thumbnail-picker-hint {
  padding: 16px 18px 8px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.thumbnail-picker-grid {
  flex: 1;
  overflow-y: auto;
  padding: 12px 18px 20px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  align-content: start;
}

.thumbnail-picker-card {
  position: relative;
  width: 100%;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.78) 0%, rgba(244, 248, 255, 0.92) 100%);
  padding: 0;
  appearance: none;
  cursor: pointer;
  text-align: left;
  transition: transform var(--motion-base) var(--ease-standard), box-shadow var(--motion-base) var(--ease-standard), border-color var(--motion-base) var(--ease-standard);
  box-shadow: 0 10px 20px rgba(17, 27, 45, 0.08);
}

.thumbnail-picker-card.is-selected,
.thumbnail-picker-card.is-current {
  border-color: rgba(30, 110, 255, 0.42);
  box-shadow: 0 14px 26px rgba(30, 110, 255, 0.14);
}

.thumbnail-picker-card.is-selected {
  transform: translateY(-2px);
}

.thumbnail-picker-image {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
}

.thumbnail-picker-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  padding: 5px 8px;
  border-radius: 999px;
  background: rgba(14, 28, 51, 0.78);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  backdrop-filter: blur(8px);
}

.thumbnail-picker-badge.is-pending {
  background: rgba(24, 96, 220, 0.86);
}

.thumbnail-picker-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: var(--text-secondary);
  font-size: 14px;
  text-align: center;
}

.tag-select-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 0 16px;
}

.tag-count,
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
  .episode-section,
  .video-info,
  .magnets-section,
  .preview-video-section,
  .thumbnails-section {
    border-radius: 12px;
  }

  .cover-image {
    min-height: 180px;
    max-height: 250px;
  }

  .cover-placeholder {
    min-height: 180px;
  }

  .play-icon {
    font-size: 54px;
  }

  .action-buttons {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    padding: 0 2px;
    background: transparent;
    border: none;
    border-radius: 0;
    box-shadow: none;
  }

  .action-buttons .van-button {
    width: 100%;
    min-width: 0;
  }

  .info-row .label {
    width: 60px;
  }

  .score-controls :deep(.van-rate) {
    --van-rate-icon-size: 16px;
  }

  .preview-video-actions {
    flex-wrap: wrap;
    justify-content: flex-start;
  }

  .preview-video-source-selector {
    justify-content: flex-start;
  }

  .episode-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    padding: 10px;
  }

  .thumbnail-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .thumbnail-picker-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    padding: 10px 12px 18px;
  }

  .thumbnail-picker-hint {
    padding: 14px 14px 6px;
  }
}
</style>

