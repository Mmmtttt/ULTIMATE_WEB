<template>
  <div class="comic-grid">
    <div
      class="grid-container"
      :style="gridStyle"
    >
      <ComicCard
        v-for="comic in comics"
        :key="comic.id"
        :comic="comic"
        :selected="isSelected(comic.id)"
        :selectable="selectable"
        @click="handleCardClick"
        @toggle-select="handleToggleSelect"
        @author-click="handleAuthorClick"
      />
    </div>
    
    <!-- 空状态 -->
    <EmptyState
      v-if="comics.length === 0 && !loading"
      :title="emptyTitle"
      :description="emptyDescription"
      :icon="emptyIcon"
    />
    
    <!-- 加载更多 -->
    <div v-if="loading" class="loading-more">
      <LoadingSpinner size="medium" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ComicCard from './ComicCard.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const props = defineProps({
  comics: {
    type: Array,
    default: () => []
  },
  selectedIds: {
    type: Array,
    default: () => []
  },
  selectable: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  },
  columns: {
    type: Number,
    default: 0 // 0 表示响应式
  },
  gap: {
    type: Number,
    default: 12
  },
  emptyTitle: {
    type: String,
    default: '暂无漫画'
  },
  emptyDescription: {
    type: String,
    default: '还没有添加任何漫画'
  },
  emptyIcon: {
    type: String,
    default: '📚'
  }
})

const emit = defineEmits(['card-click', 'toggle-select', 'author-click'])

// 网格样式 - 与原 Home.vue 一致
const gridStyle = computed(() => {
  if (props.columns > 0) {
    return {
      display: 'grid',
      gridTemplateColumns: `repeat(${props.columns}, 1fr)`,
      gap: `${props.gap}px`
    }
  }
  
  // 响应式布局 - 与原 Home.vue 一致
  return {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
    gap: `${props.gap}px`
  }
})

// 检查是否选中
function isSelected(id) {
  return props.selectedIds.includes(id)
}

// 处理卡片点击
function handleCardClick(comic) {
  emit('card-click', comic)
}

// 处理选择切换
function handleToggleSelect(id) {
  emit('toggle-select', id)
}

// 处理作者点击
function handleAuthorClick(author) {
  emit('author-click', author)
}
</script>

<style scoped>
.comic-grid {
  padding: 10px;
  width: 100%;
  box-sizing: border-box;
}

.grid-container {
  width: 100%;
}

.loading-more {
  display: flex;
  justify-content: center;
  padding: 30px;
}
</style>
