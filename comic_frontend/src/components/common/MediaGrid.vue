<template>
  <div class="media-grid" :class="{ 'grid-mobile': isMobile, 'grid-desktop': isDesktop }">
    <div 
      v-for="item in items" 
      :key="item.id" 
      class="media-card"
      @click="$emit('click', item)"
    >
      <div class="media-cover">
        <van-image 
          :src="getCoverUrl(item)" 
          fit="cover" 
          class="cover-image"
          lazy-load
        />
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

        <!-- 选中状态覆盖层 (管理模式) -->
        <div v-if="selectable" class="select-overlay" :class="{ selected: isSelected(item) }" @click.stop="$emit('select', item)">
          <van-icon name="success" class="select-icon" />
        </div>
      </div>
      
      <div class="media-info">
        <div class="media-title">{{ item.title }}</div>
        <div v-if="item.actors && item.actors.length > 0" class="media-subtitle">
          {{ item.actors.slice(0, 2).join(', ') }}
        </div>
        <div v-else-if="item.author" class="media-subtitle">
          {{ item.author }}
        </div>
        <div class="media-meta">
          <span v-if="item.date">{{ item.date }}</span>
          <span v-else-if="item.total_page">{{ item.total_page }}P</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useDevice } from '@/composables/useDevice'

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
  }
})

const emit = defineEmits(['click', 'toggle-favorite', 'select'])
const { isMobile, isDesktop } = useDevice()

function getCoverUrl(item) {
  const coverPath = item.cover_path || item.cover_url
  if (!coverPath) return ''
  if (coverPath.startsWith('http')) return coverPath
  if (coverPath.startsWith('/static/')) return coverPath
  if (coverPath.startsWith('/')) return coverPath
  return `/${coverPath}`
}

function isSelected(item) {
  return props.selectedIds.includes(item.id)
}
</script>

<style scoped>
.media-grid {
  display: grid;
  gap: 12px;
  padding: 12px;
}

.grid-mobile {
  grid-template-columns: repeat(2, 1fr);
}

.grid-desktop {
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
  padding: 20px;
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

.media-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px rgba(0,0,0,0.1);
}

.media-cover {
  position: relative;
  aspect-ratio: 2/3; /* 默认竖版，适合漫画封面 */
  background: #f0f2f5;
}

/* 视频模式下可能需要横版，可以通过 CSS 类或 props 控制，这里暂时统一用竖版或自适应 */
/* 如果要支持视频的 16:9，可以在父组件通过 class 传递 */

.cover-image {
  width: 100%;
  height: 100%;
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
}

.media-info {
  padding: 10px;
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
