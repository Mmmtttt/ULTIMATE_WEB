<template>
  <div class="media-grid" :class="gridClassList">
    <div 
      v-for="item in items" 
      :key="item.id" 
      class="media-card"
      :class="{ 'list-mode-card': isListMode }"
      @click="$emit('click', item)"
    >
      <template v-if="!isListMode">
        <div class="media-cover">
          <van-image 
            :src="getCoverUrl(item)" 
            fit="cover" 
            class="cover-image"
            lazy-load
          />
          <div v-if="item.platform" class="media-platform">{{ item.platform }}</div>
          <div v-if="item.code" class="media-code">{{ item.code }}</div>
          <div v-if="item.score" class="media-score">{{ item.score }}</div>
          <div v-if="showProgress && item.current_page && item.current_page > 0" class="media-progress">
            {{ item.current_page }}{{ item.total_page ? `/${item.total_page}` : '' }}
          </div>
          
          <div v-if="showFavorite" class="favorite-btn" @click.stop="$emit('toggle-favorite', item)">
            <van-icon 
              :name="isFavorited(item) ? 'star' : 'star-o'" 
              :color="isFavorited(item) ? '#ff9500' : '#fff'" 
            />
          </div>

          <div v-if="isVideoItem(item)" class="play-btn">
            <van-icon name="play-circle-o" size="48" />
          </div>

          <div v-if="selectable" class="select-overlay" :class="{ selected: isSelected(item) }" @click.stop="$emit('select', item)">
            <van-icon name="success" class="select-icon" />
          </div>
        </div>
        
        <div class="media-info">
          <div class="media-title">{{ item.title }}</div>
          <div v-if="displaySubtitle(item)" class="media-subtitle">
            {{ displaySubtitle(item) }}
          </div>
          <div class="media-meta">
            <span v-if="item.date">{{ item.date }}</span>
            <span v-else-if="item.total_page">{{ item.total_page }}P</span>
          </div>
        </div>
      </template>

      <template v-else>
        <div class="list-content">
          <div class="list-main">
            <div class="media-title">{{ item.title }}</div>
            <div v-if="displaySubtitle(item)" class="media-subtitle">
              {{ displaySubtitle(item) }}
            </div>
            <div class="media-meta">
              <span v-if="showProgress && item.current_page && item.current_page > 0">
                {{ item.current_page }}{{ item.total_page ? `/${item.total_page}` : '' }}
              </span>
              <span v-else-if="item.date">{{ item.date }}</span>
              <span v-else-if="item.total_page">{{ item.total_page }}P</span>
              <span v-else>-</span>
            </div>
          </div>

          <div class="list-side">
            <div v-if="showFavorite" class="favorite-btn list-favorite" @click.stop="$emit('toggle-favorite', item)">
              <van-icon 
                :name="isFavorited(item) ? 'star' : 'star-o'" 
                :color="isFavorited(item) ? '#ff9500' : '#999'" 
              />
            </div>
            <div
              v-if="selectable"
              class="list-select"
              :class="{ selected: isSelected(item) }"
              @click.stop="$emit('select', item)"
            >
              <van-icon :name="isSelected(item) ? 'success' : 'circle'" />
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useDevice } from '@/composables/useDevice'
import { useModeStore } from '@/stores'
import { getCoverUrl as resolveCoverUrl } from '@/utils'

const props = defineProps({
  items: {
    type: Array,
    required: true
  },
  showFavorite: {
    type: Boolean,
    default: false
  },
  isFavorited: {
    type: Function,
    default: () => false
  },
  selectable: {
    type: Boolean,
    default: false
  },
  selectedIds: {
    type: Array,
    default: () => []
  },
  showProgress: {
    type: Boolean,
    default: false
  },
  viewMode: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['click', 'toggle-favorite', 'select'])
const { isMobile, isDesktop } = useDevice()
const modeStore = useModeStore()

const resolvedViewMode = computed(() => {
  return props.viewMode || modeStore.mediaViewMode || 'large'
})

const isListMode = computed(() => resolvedViewMode.value === 'list')

const gridClassList = computed(() => ({
  'grid-mobile': isMobile.value,
  'grid-desktop': isDesktop.value,
  'mode-large': resolvedViewMode.value === 'large',
  'mode-medium': resolvedViewMode.value === 'medium',
  'mode-small': resolvedViewMode.value === 'small',
  'mode-list': resolvedViewMode.value === 'list'
}))

function getCoverUrl(item) {
  return resolveCoverUrl(item.cover_path || item.cover_url)
}

function isSelected(item) {
  return props.selectedIds.includes(item.id)
}

function isVideoItem(item) {
  return item.actors && item.actors.length > 0
}

function displaySubtitle(item) {
  if (item.actors && item.actors.length > 0) {
    return item.actors.slice(0, 2).join(', ')
  }
  return item.author || item.creator || item.actor || ''
}
</script>

<style scoped>
.media-grid {
  display: grid;
  gap: 12px;
  padding: 12px;
}

.grid-mobile.mode-large {
  grid-template-columns: repeat(2, 1fr);
}

.grid-mobile.mode-medium {
  grid-template-columns: repeat(3, 1fr);
}

.grid-mobile.mode-small {
  grid-template-columns: repeat(4, 1fr);
}

.grid-mobile.mode-list {
  grid-template-columns: 1fr;
  gap: 8px;
}

.grid-desktop.mode-large {
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
  padding: 20px;
}

.grid-desktop.mode-medium {
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 16px;
  padding: 16px;
}

.grid-desktop.mode-small {
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 12px;
  padding: 12px;
}

.grid-desktop.mode-list {
  grid-template-columns: 1fr;
  gap: 10px;
  max-width: 1100px;
  margin: 0 auto;
}

.media-card {
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  transition: transform 0.2s, box-shadow 0.2s;
  cursor: pointer;
  position: relative;
}

.list-mode-card {
  transform: none !important;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.media-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px rgba(0,0,0,0.1);
}

.media-cover {
  position: relative;
  aspect-ratio: 2/3;
  background: #f0f2f5;
}

.cover-image {
  width: 100%;
  height: 100%;
}

.media-platform {
  position: absolute;
  top: 6px;
  left: 6px;
  background: rgba(0,0,0,0.7);
  color: #fff;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  z-index: 1;
}

.media-code {
  position: absolute;
  top: 6px;
  left: 6px;
  background: rgba(0,0,0,0.6);
  color: #fff;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
}

.media-score {
  position: absolute;
  top: 6px;
  right: 6px;
  background: #ff9500;
  color: #fff;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
}

.media-progress {
  position: absolute;
  bottom: 6px;
  left: 6px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.favorite-btn {
  position: absolute;
  bottom: 6px;
  right: 6px;
  padding: 4px;
  background: rgba(0,0,0,0.3);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(4px);
  z-index: 2;
}

.play-btn {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #fff;
  text-shadow: 0 2px 8px rgba(0,0,0,0.5);
  z-index: 1;
  pointer-events: none;
}

.media-info {
  padding: 10px;
}

.mode-small .media-info {
  padding: 8px;
}

.media-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: 1.4;
}

.mode-small .media-title {
  font-size: 12px;
}

.media-subtitle {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.media-meta {
  font-size: 11px;
  color: #999;
}

.mode-small .media-meta {
  font-size: 10px;
}

.list-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
}

.list-main {
  min-width: 0;
  flex: 1;
}

.list-side {
  display: flex;
  align-items: center;
  gap: 8px;
}

.list-favorite {
  position: static;
  background: transparent;
  padding: 0;
}

.list-select {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1px solid #d9d9d9;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
}

.list-select.selected {
  border-color: #1989fa;
  color: #1989fa;
}

/* Selection Styles */
.select-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s;
}

.select-overlay.selected {
  opacity: 1;
  background: rgba(25, 137, 250, 0.3);
  border: 2px solid #1989fa;
}

.select-icon {
  font-size: 32px;
  color: #fff;
  background: #1989fa;
  border-radius: 50%;
  padding: 8px;
}
</style>
