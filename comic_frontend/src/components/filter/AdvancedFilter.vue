<template>
  <div class="advanced-filter">
    <div class="filter-header">
      <span class="filter-title">高级筛选</span>
      <button v-if="hasSelection" class="btn-clear" @click="handleClear">
        清除
      </button>
    </div>

    <div v-if="hasSelection" class="selected-items">
      <div v-if="selectedIncludeTags.length" class="selected-section">
        <span class="section-label">标签-包含:</span>
        <div class="items-list">
          <span
            v-for="tag in selectedIncludeTags"
            :key="tag.id"
            class="selected-badge success"
          >
            {{ tag.name }}
            <span class="close-btn" @click="removeIncludeTag(tag.id)">×</span>
          </span>
        </div>
      </div>

      <div v-if="selectedExcludeTags.length" class="selected-section">
        <span class="section-label">标签-排除:</span>
        <div class="items-list">
          <span
            v-for="tag in selectedExcludeTags"
            :key="tag.id"
            class="selected-badge danger"
          >
            {{ tag.name }}
            <span class="close-btn" @click="removeExcludeTag(tag.id)">×</span>
          </span>
        </div>
      </div>

      <div v-if="selectedAuthors.length" class="selected-section">
        <span class="section-label">作者:</span>
        <div class="items-list">
          <span
            v-for="author in selectedAuthors"
            :key="author"
            class="selected-badge primary"
          >
            {{ author }}
            <span class="close-btn" @click="removeAuthor(author)">×</span>
          </span>
        </div>
      </div>

      <div v-if="selectedLists.length" class="selected-section">
        <span class="section-label">清单:</span>
        <div class="items-list">
          <span
            v-for="list in selectedLists"
            :key="list.id"
            class="selected-badge warning"
          >
            {{ list.name }}
            <span class="close-btn" @click="removeList(list.id)">×</span>
          </span>
        </div>
      </div>

      <div v-if="normalizedMinScore > 0" class="selected-section">
        <span class="section-label">最低评分:</span>
        <div class="items-list">
          <span class="selected-badge info">
            {{ normalizedMinScore }}
            <span class="close-btn" @click="removeMinScore">×</span>
          </span>
        </div>
      </div>

      <div v-if="showUnreadFilter && unreadOnly" class="selected-section">
        <span class="section-label">阅读状态:</span>
        <div class="items-list">
          <span class="selected-badge danger">
            仅未读
            <span class="close-btn" @click="removeUnreadOnly">×</span>
          </span>
        </div>
      </div>
    </div>

    <div class="filter-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="tab-btn"
        :class="{ active: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        {{ tab.name }}
      </button>
    </div>

    <div class="filter-content">
      <div v-show="activeTab === 'tags'" class="tag-panel">
        <div class="tags-grid">
          <span
            v-for="tag in sortedTags"
            :key="tag.id"
            class="tag-item"
            :class="getTagType(tag.id)"
            @click="toggleTag(tag.id)"
          >
            {{ tag.name }}
            <span v-if="showTagCount" class="count">({{ tag[tagCountKey] }})</span>
          </span>
        </div>
        <div class="filter-hint">
          <span class="hint-text">💡 单击添加，再次单击排除，第三次取消</span>
        </div>
      </div>

      <div v-show="activeTab === 'authors'" class="author-panel">
        <div class="search-box">
          <input
            v-model="authorSearch"
            type="text"
            placeholder="搜索作者..."
            class="search-input"
          />
        </div>
        <div class="authors-grid">
          <span
            v-for="author in filteredAuthors"
            :key="author"
            class="author-item"
            :class="{ selected: selectedAuthors.includes(author) }"
            @click="toggleAuthor(author)"
          >
            {{ author }}
          </span>
        </div>
      </div>

      <div v-show="activeTab === 'lists'" class="list-panel">
        <div class="lists-grid">
          <span
            v-for="list in lists"
            :key="list.id"
            class="list-item"
            :class="{ selected: selectedListIds.includes(list.id) }"
            @click="toggleList(list.id)"
          >
            {{ list.name }}
            <span class="count">({{ list.item_count }})</span>
          </span>
        </div>
      </div>

      <div v-show="activeTab === 'score'" class="score-panel">
        <div class="score-row">
          <span class="score-label">最低评分</span>
          <van-stepper
            :model-value="normalizedMinScore"
            :min="minScoreMin"
            :max="minScoreMax"
            :step="minScoreStep"
            @update:model-value="updateMinScore"
          />
        </div>
        <div class="score-hint">只显示评分不低于该值的内容</div>
      </div>

      <div v-if="showUnreadFilter" v-show="activeTab === 'unread'" class="unread-panel">
        <div class="score-row">
          <span class="score-label">仅显示未读漫画</span>
          <van-switch :model-value="unreadOnly" @update:model-value="updateUnreadOnly" />
        </div>
        <div class="score-hint">阅读进度为 1 判定为未读</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  tags: {
    type: Array,
    default: () => []
  },
  authors: {
    type: Array,
    default: () => []
  },
  lists: {
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
  selectedAuthors: {
    type: Array,
    default: () => []
  },
  selectedListIds: {
    type: Array,
    default: () => []
  },
  minScore: {
    type: Number,
    default: 0
  },
  minScoreMin: {
    type: Number,
    default: 0
  },
  minScoreMax: {
    type: Number,
    default: 10
  },
  minScoreStep: {
    type: Number,
    default: 0.5
  },
  unreadOnly: {
    type: Boolean,
    default: false
  },
  showTagCount: {
    type: Boolean,
    default: true
  },
  isVideoMode: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits([
  'update:includeTags',
  'update:excludeTags',
  'update:selectedAuthors',
  'update:selectedListIds',
  'update:minScore',
  'update:unreadOnly',
  'change'
])

const activeTab = ref('tags')
const authorSearch = ref('')

const showUnreadFilter = computed(() => !props.isVideoMode)

const tabs = computed(() => {
  const baseTabs = [
    { id: 'tags', name: '标签' },
    { id: 'authors', name: '作者' },
    { id: 'lists', name: '清单' },
    { id: 'score', name: '最低评分' }
  ]
  if (showUnreadFilter.value) {
    baseTabs.push({ id: 'unread', name: '未读' })
  }
  return baseTabs
})

watch(tabs, (value) => {
  const hasActive = value.some(tab => tab.id === activeTab.value)
  if (!hasActive) {
    activeTab.value = 'tags'
  }
})

const hasSelection = computed(() => {
  return (
    props.includeTags.length > 0 ||
    props.excludeTags.length > 0 ||
    props.selectedAuthors.length > 0 ||
    props.selectedListIds.length > 0 ||
    normalizedMinScore.value > 0 ||
    (showUnreadFilter.value && props.unreadOnly)
  )
})

const normalizedMinScore = computed(() => normalizeMinScoreValue(props.minScore))

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

const selectedIncludeTags = computed(() => {
  return props.includeTags
    .map(id => props.tags.find(tag => tag.id === id))
    .filter(Boolean)
})

const selectedExcludeTags = computed(() => {
  return props.excludeTags
    .map(id => props.tags.find(tag => tag.id === id))
    .filter(Boolean)
})

const selectedLists = computed(() => {
  return props.selectedListIds
    .map(id => props.lists.find(list => list.id === id))
    .filter(Boolean)
})

const filteredAuthors = computed(() => {
  if (!authorSearch.value) return props.authors
  return props.authors.filter(author =>
    author.toLowerCase().includes(authorSearch.value.toLowerCase())
  )
})

function isIncludeTag(tagId) {
  return props.includeTags.includes(tagId)
}

function isExcludeTag(tagId) {
  return props.excludeTags.includes(tagId)
}

function getTagType(tagId) {
  if (isIncludeTag(tagId)) return 'success'
  if (isExcludeTag(tagId)) return 'danger'
  return ''
}

function toggleTag(tagId) {
  let newIncludeTags = [...props.includeTags]
  let newExcludeTags = [...props.excludeTags]

  if (isIncludeTag(tagId)) {
    newIncludeTags = newIncludeTags.filter(id => id !== tagId)
    newExcludeTags.push(tagId)
  } else if (isExcludeTag(tagId)) {
    newExcludeTags = newExcludeTags.filter(id => id !== tagId)
  } else {
    newIncludeTags.push(tagId)
  }

  emit('update:includeTags', newIncludeTags)
  emit('update:excludeTags', newExcludeTags)
  emitChange(newIncludeTags, newExcludeTags)
}

function removeIncludeTag(tagId) {
  const newIncludeTags = props.includeTags.filter(id => id !== tagId)
  emit('update:includeTags', newIncludeTags)
  emitChange(newIncludeTags, props.excludeTags)
}

function removeExcludeTag(tagId) {
  const newExcludeTags = props.excludeTags.filter(id => id !== tagId)
  emit('update:excludeTags', newExcludeTags)
  emitChange(props.includeTags, newExcludeTags)
}

function toggleAuthor(author) {
  let newAuthors
  if (props.selectedAuthors.includes(author)) {
    newAuthors = props.selectedAuthors.filter(a => a !== author)
  } else {
    newAuthors = [...props.selectedAuthors, author]
  }
  emit('update:selectedAuthors', newAuthors)
  emitChange(props.includeTags, props.excludeTags, newAuthors)
}

function removeAuthor(author) {
  const newAuthors = props.selectedAuthors.filter(a => a !== author)
  emit('update:selectedAuthors', newAuthors)
  emitChange(props.includeTags, props.excludeTags, newAuthors)
}

function toggleList(listId) {
  let newListIds
  if (props.selectedListIds.includes(listId)) {
    newListIds = props.selectedListIds.filter(id => id !== listId)
  } else {
    newListIds = [...props.selectedListIds, listId]
  }
  emit('update:selectedListIds', newListIds)
  emitChange(props.includeTags, props.excludeTags, props.selectedAuthors, newListIds)
}

function removeList(listId) {
  const newListIds = props.selectedListIds.filter(id => id !== listId)
  emit('update:selectedListIds', newListIds)
  emitChange(props.includeTags, props.excludeTags, props.selectedAuthors, newListIds)
}

function normalizeMinScoreValue(value) {
  const score = Number(value)
  if (!Number.isFinite(score) || score <= 0) {
    return 0
  }
  return score
}

function updateMinScore(value) {
  const nextScore = normalizeMinScoreValue(value)
  emit('update:minScore', nextScore)
  emitChange(props.includeTags, props.excludeTags, props.selectedAuthors, props.selectedListIds, nextScore)
}

function removeMinScore() {
  emit('update:minScore', 0)
  emitChange(props.includeTags, props.excludeTags, props.selectedAuthors, props.selectedListIds, 0)
}

function updateUnreadOnly(value) {
  const unreadOnly = Boolean(value)
  emit('update:unreadOnly', unreadOnly)
  emitChange(props.includeTags, props.excludeTags, props.selectedAuthors, props.selectedListIds, props.minScore, unreadOnly)
}

function removeUnreadOnly() {
  emit('update:unreadOnly', false)
  emitChange(props.includeTags, props.excludeTags, props.selectedAuthors, props.selectedListIds, props.minScore, false)
}

function emitChange(
  includeTags,
  excludeTags,
  authors = props.selectedAuthors,
  listIds = props.selectedListIds,
  minScore = props.minScore,
  unreadOnly = props.unreadOnly
) {
  emit('change', {
    includeTags,
    excludeTags,
    authors,
    listIds,
    minScore: normalizeMinScoreValue(minScore),
    unreadOnly: Boolean(unreadOnly)
  })
}

function handleClear() {
  emit('update:includeTags', [])
  emit('update:excludeTags', [])
  emit('update:selectedAuthors', [])
  emit('update:selectedListIds', [])
  emit('update:minScore', 0)
  emit('update:unreadOnly', false)
  emit('change', {
    includeTags: [],
    excludeTags: [],
    authors: [],
    listIds: [],
    minScore: 0,
    unreadOnly: false
  })
}
</script>

<style scoped>
.advanced-filter {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
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
  color: #333;
}

.btn-clear {
  padding: 4px 12px;
  border: none;
  border-radius: 6px;
  background: #f5f5f5;
  color: #666;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-clear:hover {
  background: #e0e0e0;
  color: #333;
}

.selected-items {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #eee;
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
  color: #999;
  white-space: nowrap;
  padding-top: 4px;
}

.items-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex: 1;
}

.selected-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 16px;
  font-size: 13px;
  background: #f0f0f0;
}

.selected-badge.success {
  background: #e6f7ff;
  color: #1890ff;
}

.selected-badge.danger {
  background: #fff1f0;
  color: #ff4d4f;
}

.selected-badge.primary {
  background: #f6ffed;
  color: #52c41a;
}

.selected-badge.warning {
  background: #fffbe6;
  color: #faad14;
}

.selected-badge.info {
  background: #f6ffed;
  color: #52c41a;
}

.close-btn {
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}

.filter-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 12px;
}

.tab-btn {
  padding: 6px 16px;
  border: none;
  border-radius: 20px;
  background: #f5f5f5;
  color: #666;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: #e0e0e0;
}

.tab-btn.active {
  background: #1890ff;
  color: #fff;
}

.filter-content {
  min-height: 200px;
}

.tag-panel,
.author-panel,
.list-panel,
.score-panel,
.unread-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.score-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.score-label {
  font-size: 14px;
  color: #333;
}

.score-hint {
  font-size: 12px;
  color: #999;
}

.tags-grid,
.authors-grid,
.lists-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-height: 280px;
  overflow-y: auto;
}

.tag-item,
.author-item,
.list-item {
  padding: 6px 14px;
  border-radius: 16px;
  font-size: 13px;
  cursor: pointer;
  background: #f5f5f5;
  color: #333;
  transition: all 0.2s;
}

.tag-item:hover,
.author-item:hover,
.list-item:hover {
  background: #e0e0e0;
}

.tag-item.success {
  background: #e6f7ff;
  color: #1890ff;
}

.tag-item.danger {
  background: #fff1f0;
  color: #ff4d4f;
}

.author-item.selected,
.list-item.selected {
  background: #1890ff;
  color: #fff;
}

.count {
  font-size: 11px;
  color: #999;
  margin-left: 4px;
}

.search-box {
  margin-bottom: 8px;
}

.search-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: all 0.2s;
}

.search-input:focus {
  border-color: #1890ff;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.1);
}

.filter-hint {
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.hint-text {
  font-size: 12px;
  color: #999;
}

.tags-grid::-webkit-scrollbar,
.authors-grid::-webkit-scrollbar,
.lists-grid::-webkit-scrollbar {
  width: 4px;
}

.tags-grid::-webkit-scrollbar-track,
.authors-grid::-webkit-scrollbar-track,
.lists-grid::-webkit-scrollbar-track {
  background: transparent;
}

.tags-grid::-webkit-scrollbar-thumb,
.authors-grid::-webkit-scrollbar-thumb,
.lists-grid::-webkit-scrollbar-thumb {
  background: #ddd;
  border-radius: 2px;
}

@media (max-width: 768px) {
  .advanced-filter {
    padding: 12px;
  }
}
</style>
