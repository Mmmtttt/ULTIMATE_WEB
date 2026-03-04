<template>
  <div
    class="comic-card"
    :class="{
      'card-selected': selected,
      'card-desktop': isDesktop,
      'card-mobile': isMobile
    }"
    @click="handleClick"
  >
    <!-- 封面图片 -->
    <div class="comic-cover-container">
      <van-image 
        :src="coverUrl" 
        fit="cover" 
        class="comic-cover"
        lazy-load
      />
      
      <!-- 选中标记 -->
      <div v-if="selectable" class="select-overlay" @click.stop="toggleSelect">
        <div class="select-checkbox" :class="{ checked: selected }">
          <span v-if="selected" class="check-icon">✓</span>
        </div>
      </div>
      
      <!-- 收藏标识 -->
      <div v-if="comic.is_favorited" class="favorite-badge">
        <van-icon name="star" color="#ffd21e" />
      </div>
      
      <!-- 已读标记 -->
      <div class="comic-badge" v-if="comic.current_page > 1 && comic.total_page > 0">
        {{ readProgress }}%
      </div>
      
      <!-- 评分 -->
      <div class="score-badge" v-if="comic.score && !isNaN(comic.score)">
        {{ comic.score }}分
      </div>
    </div>
    
    <!-- 信息区域 -->
    <div class="comic-info">
      <h3 class="comic-title">{{ comic.title }}</h3>
      
      <!-- 标签区域 -->
      <div class="comic-tags" v-if="comic.tags && comic.tags.length > 0">
        <!-- 电脑端显示3个标签 -->
        <template v-if="isDesktop">
          <van-tag 
            v-for="(tag, index) in comic.tags.slice(0, 3)" 
            :key="tag.id || index" 
            size="small" 
            type="primary" 
            plain
            class="comic-tag"
          >
            {{ tag.name }}
          </van-tag>
          <span v-if="comic.tags.length > 3" class="more-tags">+{{ comic.tags.length - 3 }}</span>
        </template>
        
        <!-- 手机端显示2个标签 -->
        <template v-else>
          <van-tag 
            v-for="(tag, index) in comic.tags.slice(0, 2)" 
            :key="tag.id || index" 
            size="mini" 
            type="primary" 
            plain
            class="comic-tag"
          >
            {{ tag.name }}
          </van-tag>
          <span v-if="comic.tags.length > 2" class="more-tags">+{{ comic.tags.length - 2 }}</span>
        </template>
      </div>
      
      <div class="comic-meta">
        <span class="page-info">
          <van-icon v-if="isDesktop" name="eye-o" size="12" />
          {{ comic.current_page }}/{{ comic.total_page || 0 }}
        </span>
        <span 
          v-if="comic.author" class="author clickable" @click.stop="handleAuthorClick">
          <van-icon v-if="isDesktop" name="user-o" size="12" />
          {{ comic.author }}
        </span>
        <span v-else class="author">
          <van-icon v-if="isDesktop" name="user-o" size="12" />
          未知
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { buildCoverUrl } from '@/api/image'
import { useDevice } from '@/composables'

const { isMobile, isDesktop } = useDevice()

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
  }
})

const emit = defineEmits(['click', 'toggle-select', 'author-click'])

const coverUrl = computed(() => {
  return buildCoverUrl(props.comic.cover_path)
})

const readProgress = computed(() => {
  if (!props.comic.total_page || props.comic.total_page <= 0) return 0
  return Math.round((props.comic.current_page / props.comic.total_page) * 100)
})

function handleClick() {
  emit('click', props.comic)
}

function handleAuthorClick() {
  emit('author-click', props.comic.author)
}

function toggleSelect() {
  emit('toggle-select', props.comic.id)
}
</script>

<style scoped>
.comic-card {
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
  cursor: pointer;
  position: relative;
}

.comic-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.comic-cover-container {
  position: relative;
  width: 100%;
  padding-top: 140%;
  overflow: hidden;
}

.comic-cover {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: #f0f0f0;
}

.comic-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
}

.favorite-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 50%;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.score-badge {
  position: absolute;
  bottom: 8px;
  left: 8px;
  background: rgba(255, 153, 0, 0.9);
  color: #fff;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
  font-weight: bold;
}

.comic-info {
  padding: 8px;
}

.comic-title {
  font-size: 12px;
  font-weight: 500;
  margin: 0 0 4px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: 1.3;
}

.comic-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 4px;
}

.comic-tag {
  font-size: 10px;
}

.more-tags {
  font-size: 10px;
  color: #999;
  display: flex;
  align-items: center;
}

.comic-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10px;
  color: #999;
  gap: 4px;
}

.page-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 2px;
}

.author {
  flex: 1;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 2px;
  justify-content: flex-end;
}

.author span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.author.clickable {
  color: #1989fa;
  cursor: pointer;
  text-decoration: underline;
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

/* 电脑端样式 */
.card-desktop .comic-info {
  padding: 12px;
}

.card-desktop .comic-title {
  font-size: 14px;
  line-height: 1.4;
}

.card-desktop .comic-tag {
  font-size: 11px;
}

.card-desktop .comic-meta {
  font-size: 12px;
}

.card-desktop .comic-badge {
  font-size: 11px;
  padding: 4px 8px;
}

.card-desktop .score-badge {
  font-size: 11px;
  padding: 4px 8px;
}

.card-desktop .favorite-badge {
  width: 24px;
  height: 24px;
}

.card-desktop .favorite-badge .van-icon {
  font-size: 14px;
}

/* 手机端优化 */
@media (max-width: 767px) {
  .comic-card:hover {
    transform: none;
  }
  
  .comic-card:active {
    transform: scale(0.98);
  }
}

/* 电脑端更大的卡片 */
@media (min-width: 1024px) {
  .card-desktop .comic-cover-container {
    padding-top: 135%;
  }
}
</style>
