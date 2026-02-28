<template>
  <div
    class="comic-card"
    :class="{
      'card-selected': selected,
      'card-read': isRead,
      'card-completed': isCompleted
    }"
    @click="handleClick"
  >
    <!-- 封面图片 -->
    <div class="card-cover">
      <ImageLoader
        :src="coverUrl"
        :alt="comic.title"
        class="cover-image"
      />
      
      <!-- 选中标记 -->
      <div v-if="selectable" class="select-overlay" @click.stop="toggleSelect">
        <div class="select-checkbox" :class="{ checked: selected }">
          <span v-if="selected" class="check-icon">✓</span>
        </div>
      </div>
      
      <!-- 已读标记 -->
      <div v-if="isRead && !selected" class="read-badge">
        <span class="read-text">{{ readProgress }}</span>
      </div>
      
      <!-- 评分 -->
      <div v-if="comic.score > 0" class="score-badge">
        <span class="score-value">{{ comic.score }}</span>
      </div>
    </div>
    
    <!-- 信息区域 -->
    <div class="card-info">
      <h4 class="comic-title" :title="comic.title">{{ comic.title }}</h4>
      
      <div class="comic-meta">
        <span class="page-count">{{ comic.total_pages }}页</span>
        <span v-if="lastReadTime" class="last-read">{{ lastReadTime }}</span>
      </div>
      
      <!-- 标签 -->
      <div v-if="showTags && comic.tags?.length" class="comic-tags">
        <TagBadge
          v-for="tagId in displayedTags"
          :key="tagId"
          :tag="getTagById(tagId)"
          size="small"
        />
        <span v-if="hasMoreTags" class="more-tags">+{{ moreTagsCount }}</span>
      </div>
      
      <!-- 进度条 -->
      <div v-if="showProgress && isRead" class="progress-bar">
        <div
          class="progress-fill"
          :style="{ width: progressPercent + '%' }"
        ></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ImageLoader from '@/components/common/ImageLoader.vue'
import TagBadge from '@/components/tag/TagBadge.vue'

const props = defineProps({
  comic: {
    type: Object,
    required: true
  },
  selected: {
    type: Boolean,
    default: false
  },
  selectable: {
    type: Boolean,
    default: false
  },
  showTags: {
    type: Boolean,
    default: true
  },
  showProgress: {
    type: Boolean,
    default: true
  },
  maxTagCount: {
    type: Number,
    default: 3
  },
  tagNameMap: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['click', 'toggle-select'])

// 封面URL
const coverUrl = computed(() => {
  if (!props.comic.id) return ''
  return `/api/v1/comic/thumbnail?comic_id=${props.comic.id}`
})

// 是否已读
const isRead = computed(() => {
  return props.comic.current_page > 0
})

// 是否已读完
const isCompleted = computed(() => {
  return props.comic.current_page >= props.comic.total_pages
})

// 阅读进度文本
const readProgress = computed(() => {
  if (isCompleted.value) return '已读完'
  return `${props.comic.current_page}/${props.comic.total_pages}`
})

// 进度百分比
const progressPercent = computed(() => {
  if (!props.comic.total_pages) return 0
  return Math.round((props.comic.current_page / props.comic.total_pages) * 100)
})

// 最后阅读时间
const lastReadTime = computed(() => {
  if (!props.comic.last_read_time) return null
  
  const date = new Date(props.comic.last_read_time)
  const now = new Date()
  const diff = now - date
  
  // 小于1小时
  if (diff < 3600000) {
    const minutes = Math.floor(diff / 60000)
    return minutes <= 0 ? '刚刚' : `${minutes}分钟前`
  }
  
  // 小于24小时
  if (diff < 86400000) {
    const hours = Math.floor(diff / 3600000)
    return `${hours}小时前`
  }
  
  // 小于7天
  if (diff < 604800000) {
    const days = Math.floor(diff / 86400000)
    return `${days}天前`
  }
  
  // 其他情况显示日期
  return date.toLocaleDateString('zh-CN')
})

// 显示的标签
const displayedTags = computed(() => {
  return (props.comic.tags || []).slice(0, props.maxTagCount)
})

// 是否有更多标签
const hasMoreTags = computed(() => {
  return (props.comic.tags || []).length > props.maxTagCount
})

// 更多标签数量
const moreTagsCount = computed(() => {
  return (props.comic.tags || []).length - props.maxTagCount
})

// 根据ID获取标签
function getTagById(tagId) {
  return {
    id: tagId,
    name: props.tagNameMap[tagId] || tagId
  }
}

// 处理点击
function handleClick() {
  emit('click', props.comic)
}

// 切换选择
function toggleSelect() {
  emit('toggle-select', props.comic.id)
}
</script>

<style scoped>
.comic-card {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: all 0.3s ease;
  cursor: pointer;
}

.comic-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}

.comic-card.card-selected {
  box-shadow: 0 0 0 3px #07c160;
}

.card-cover {
  position: relative;
  aspect-ratio: 3/4;
  overflow: hidden;
  background: #f5f5f5;
}

.cover-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.select-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  padding: 10px;
}

.select-checkbox {
  width: 24px;
  height: 24px;
  border: 2px solid #fff;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.select-checkbox.checked {
  background: #07c160;
  border-color: #07c160;
}

.check-icon {
  color: #fff;
  font-size: 14px;
  font-weight: bold;
}

.read-badge {
  position: absolute;
  bottom: 10px;
  left: 10px;
  padding: 4px 10px;
  background: rgba(0, 0, 0, 0.7);
  border-radius: 20px;
  color: #fff;
  font-size: 12px;
}

.card-completed .read-badge {
  background: #07c160;
}

.score-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #ffd700, #ffaa00);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(255, 170, 0, 0.4);
}

.score-value {
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.card-info {
  padding: 12px;
}

.comic-title {
  margin: 0 0 8px;
  font-size: 15px;
  font-weight: 600;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.comic-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  font-size: 12px;
  color: #999;
}

.page-count::before {
  content: '📄 ';
}

.last-read::before {
  content: '🕐 ';
}

.comic-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.more-tags {
  font-size: 11px;
  color: #999;
  padding: 2px 6px;
  background: #f0f0f0;
  border-radius: 10px;
}

.progress-bar {
  height: 4px;
  background: #e0e0e0;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #07c160, #10b981);
  border-radius: 2px;
  transition: width 0.3s ease;
}

@media (max-width: 768px) {
  .comic-title {
    font-size: 14px;
  }
  
  .comic-meta {
    font-size: 11px;
  }
}
</style>
