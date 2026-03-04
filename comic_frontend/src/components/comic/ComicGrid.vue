<template>
  <div class="comic-grid" :class="{ 'grid-desktop': isDesktop, 'grid-mobile': isMobile }">
    <div
      class="grid-container"
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
import { useDevice } from '@/composables'

const { isMobile, isDesktop } = useDevice()

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
    default: 0
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

// 检查是否选中
function isSelected(id) {
  return props.selectedIds.includes(id)
}

function handleCardClick(comic) {
  emit('card-click', comic)
}

function handleToggleSelect(id) {
  emit('toggle-select', id)
}

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
  display: grid;
  gap: 12px;
}

.grid-mobile .grid-container {
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 10px;
}

.grid-desktop .grid-container {
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 16px;
}

@media (min-width: 1200px) {
  .grid-desktop .grid-container {
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 20px;
  }
}

@media (min-width: 1600px) {
  .grid-desktop .grid-container {
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 24px;
  }
}

.loading-more {
  display: flex;
  justify-content: center;
  padding: 30px;
}
</style>
