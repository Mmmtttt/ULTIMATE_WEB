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
          <div v-if="item.score" class="media-score score-badge">{{ formatScore(item.score) }}</div>
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

function formatScore(score) {
  const value = Number(score)
  if (!Number.isFinite(value)) {
    return score
  }
  return value % 1 === 0 ? value.toFixed(0) : value.toFixed(1)
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
  gap: 14px;
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
  padding-inline: 4px;
}

.grid-desktop.mode-large {
  grid-template-columns: repeat(auto-fill, minmax(198px, 1fr));
  gap: 18px;
  padding: 16px;
}

.grid-desktop.mode-medium {
  grid-template-columns: repeat(auto-fill, minmax(156px, 1fr));
  gap: 16px;
  padding: 16px;
}

.grid-desktop.mode-small {
  grid-template-columns: repeat(auto-fill, minmax(128px, 1fr));
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
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(78, 104, 155, 0.14);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 8px 18px rgba(17, 27, 45, 0.08);
  transition:
    transform var(--motion-base) var(--ease-standard),
    box-shadow var(--motion-base) var(--ease-standard),
    border-color var(--motion-base) var(--ease-standard);
  cursor: pointer;
  position: relative;
  isolation: isolate;
}

.media-card::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(130deg, rgba(255, 255, 255, 0.22), transparent 55%);
  opacity: 0;
  transition: opacity var(--motion-base) var(--ease-standard);
  pointer-events: none;
  z-index: 0;
}

.list-mode-card {
  transform: none !important;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(17, 27, 45, 0.08);
}

.media-card:hover {
  transform: translateY(-4px);
  border-color: rgba(47, 116, 255, 0.32);
  box-shadow: 0 18px 34px rgba(22, 44, 84, 0.16);
}

.media-card:hover::before {
  opacity: 1;
}

.media-cover {
  position: relative;
  aspect-ratio: 2 / 3;
  background: linear-gradient(145deg, #eff4ff 0%, #dfe9ff 100%);
}

.cover-image {
  width: 100%;
  height: 100%;
}

.media-platform {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(18, 31, 58, 0.78);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #fff;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
  z-index: 1;
  backdrop-filter: blur(4px);
}

.media-code {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(18, 31, 58, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.16);
  color: #fff;
  padding: 2px 6px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
  backdrop-filter: blur(4px);
}

.media-score {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 2;
}

.media-progress {
  position: absolute;
  bottom: 8px;
  left: 8px;
  background: rgba(16, 29, 57, 0.76);
  border: 1px solid rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(4px);
  color: #fff;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.favorite-btn {
  position: absolute;
  bottom: 8px;
  right: 8px;
  padding: 4px;
  background: rgba(17, 30, 57, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(6px);
  z-index: 2;
}

.play-btn {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #fff;
  text-shadow: 0 3px 14px rgba(0, 0, 0, 0.65);
  z-index: 1;
  pointer-events: none;
  animation: playPulse 2s ease-in-out infinite;
}

@keyframes playPulse {
  0%,
  100% {
    opacity: 0.86;
    transform: translate(-50%, -50%) scale(1);
  }
  50% {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1.05);
  }
}

.media-info {
  padding: 11px 11px 12px;
  position: relative;
  z-index: 1;
}

.mode-small .media-info {
  padding: 8px;
}

.media-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-strong);
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
  color: var(--text-secondary);
  margin-bottom: 5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.media-meta {
  font-size: 11px;
  color: var(--text-tertiary);
  font-weight: 500;
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
  border: none;
  padding: 0;
}

.list-select {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1px solid rgba(73, 98, 146, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
}

.list-select.selected {
  border-color: var(--brand-600);
  color: var(--brand-600);
}

.select-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(17, 30, 57, 0.24);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity var(--motion-fast) var(--ease-standard);
}

.select-overlay.selected {
  opacity: 1;
  background: rgba(47, 116, 255, 0.28);
  border: 2px solid var(--brand-500);
}

.select-icon {
  font-size: 32px;
  color: #fff;
  background: var(--brand-500);
  border-radius: 50%;
  padding: 8px;
}

@media (max-width: 767px) {
  .media-grid {
    gap: 10px;
    padding: 10px;
  }

  .grid-mobile.mode-small {
    grid-template-columns: repeat(3, 1fr);
  }

  .media-card {
    border-radius: 12px;
  }

  .media-info {
    padding: 8px 8px 10px;
  }

  .media-title {
    font-size: 13px;
  }
}

@media (min-width: 1024px) {
  .grid-desktop.mode-large {
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  }
}

@media (prefers-reduced-motion: reduce) {
  .media-card,
  .media-card::before,
  .select-overlay,
  .play-btn {
    transition: none;
    animation: none;
  }
}
</style>
