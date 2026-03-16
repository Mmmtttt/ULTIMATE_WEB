<template>
  <div class="tag-filter">
    <!-- 筛选标题 -->
    <div class="filter-header">
      <span class="filter-title">标签筛选</span>
      <button
        v-if="hasSelection"
        class="btn-clear"
        @click="handleClear"
      >
        清除
      </button>
    </div>
    
    <!-- 已选标签 -->
    <div v-if="hasSelection" class="selected-tags">
      <div class="selected-section">
        <span class="section-label">包含:</span>
        <div class="tags-list">
          <TagBadge
            v-for="tag in selectedIncludeTags"
            :key="tag.id"
            :tag="tag"
            type="success"
            closable
            @close="removeIncludeTag(tag.id)"
          />
        </div>
      </div>
      
      <div v-if="selectedExcludeTags.length" class="selected-section">
        <span class="section-label">排除:</span>
        <div class="tags-list">
          <TagBadge
            v-for="tag in selectedExcludeTags"
            :key="tag.id"
            :tag="tag"
            type="danger"
            closable
            @close="removeExcludeTag(tag.id)"
          />
        </div>
      </div>
    </div>
    
    <!-- 所有标签 -->
    <div class="all-tags">
      <div class="tags-grid">
        <TagBadge
          v-for="tag in sortedTags"
          :key="tag.id"
          :tag="tag"
          :selected="isIncludeTag(tag.id)"
          :type="getTagType(tag.id)"
          clickable
          :show-count="showCount"
          :count="tag[tagCountKey]"
          @click="toggleTag(tag.id)"
        />
      </div>
    </div>
    
    <!-- 操作提示 -->
    <div class="filter-hint">
      <span class="hint-text">💡 单击添加，长按排除</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import TagBadge from './TagBadge.vue'

const props = defineProps({
  tags: {
    type: Array,
    default: () => []
  },
  includeTags: {
    type: Array,
    default: () => []
  },
  excludeTags: {
    type: Array,
    default: () => []
  },
  showCount: {
    type: Boolean,
    default: true
  },
  isVideoMode: {
    type: Boolean,
    default: false
  }
})

const tagCountKey = computed(() => {
  return props.isVideoMode ? 'video_count' : 'comic_count'
})

const sortedTags = computed(() => {
  return [...props.tags].sort((a, b) => {
    const countA = a[tagCountKey.value] || 0
    const countB = b[tagCountKey.value] || 0
    return countB - countA
  })
})

const emit = defineEmits([
  'update:includeTags',
  'update:excludeTags',
  'change'
])

// 是否有选中
const hasSelection = computed(() => {
  return props.includeTags.length > 0 || props.excludeTags.length > 0
})

// 已选的包含标签
const selectedIncludeTags = computed(() => {
  return props.includeTags
    .map(id => props.tags.find(tag => tag.id === id))
    .filter(Boolean)
})

// 已选的排除标签
const selectedExcludeTags = computed(() => {
  return props.excludeTags
    .map(id => props.tags.find(tag => tag.id === id))
    .filter(Boolean)
})

// 检查是否为包含标签
function isIncludeTag(tagId) {
  return props.includeTags.includes(tagId)
}

// 检查是否为排除标签
function isExcludeTag(tagId) {
  return props.excludeTags.includes(tagId)
}

// 获取标签类型
function getTagType(tagId) {
  if (isIncludeTag(tagId)) return 'success'
  if (isExcludeTag(tagId)) return 'danger'
  return 'default'
}

// 切换标签
function toggleTag(tagId) {
  let newIncludeTags = [...props.includeTags]
  let newExcludeTags = [...props.excludeTags]
  
  if (isIncludeTag(tagId)) {
    // 从包含移到排除
    newIncludeTags = newIncludeTags.filter(id => id !== tagId)
    newExcludeTags.push(tagId)
  } else if (isExcludeTag(tagId)) {
    // 从排除移除
    newExcludeTags = newExcludeTags.filter(id => id !== tagId)
  } else {
    // 添加到包含
    newIncludeTags.push(tagId)
  }
  
  emit('update:includeTags', newIncludeTags)
  emit('update:excludeTags', newExcludeTags)
  emit('change', { include: newIncludeTags, exclude: newExcludeTags })
}

// 移除包含标签
function removeIncludeTag(tagId) {
  const newIncludeTags = props.includeTags.filter(id => id !== tagId)
  emit('update:includeTags', newIncludeTags)
  emit('change', { include: newIncludeTags, exclude: props.excludeTags })
}

// 移除排除标签
function removeExcludeTag(tagId) {
  const newExcludeTags = props.excludeTags.filter(id => id !== tagId)
  emit('update:excludeTags', newExcludeTags)
  emit('change', { include: props.includeTags, exclude: newExcludeTags })
}

// 清除所有
function handleClear() {
  emit('update:includeTags', [])
  emit('update:excludeTags', [])
  emit('change', { include: [], exclude: [] })
}
</script>

<style scoped>
.tag-filter {
  background: var(--surface-2);
  border-radius: 12px;
  padding: 16px;
  border: 1px solid var(--border-soft);
  box-shadow: 0 8px 20px rgba(2, 8, 18, 0.32);
}

.filter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.filter-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-strong);
}

.btn-clear {
  padding: 4px 12px;
  border: none;
  border-radius: 6px;
  background: rgba(27, 43, 70, 0.9);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-clear:hover {
  background: rgba(37, 56, 88, 0.96);
  color: var(--text-primary);
}

.selected-tags {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-soft);
}

.selected-section {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 10px;
}

.selected-section:last-child {
  margin-bottom: 0;
}

.section-label {
  font-size: 13px;
  color: var(--text-tertiary);
  white-space: nowrap;
  padding-top: 4px;
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex: 1;
}

.all-tags {
  max-height: 300px;
  overflow-y: auto;
}

.tags-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-hint {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-soft);
}

.hint-text {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* 滚动条样式 */
.all-tags::-webkit-scrollbar {
  width: 4px;
}

.all-tags::-webkit-scrollbar-track {
  background: transparent;
}

.all-tags::-webkit-scrollbar-thumb {
  background: rgba(122, 148, 205, 0.4);
  border-radius: 2px;
}

@media (max-width: 768px) {
  .tag-filter {
    padding: 12px;
  }
  
  .all-tags {
    max-height: 200px;
  }
}
</style>
