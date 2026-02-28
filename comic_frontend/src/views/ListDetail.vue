<template>
  <div class="list-detail">
    <van-nav-bar
      :title="listInfo?.name || '清单详情'"
      left-text="返回"
      left-arrow
      @click-left="$router.back()"
    >
      <template #right v-if="!listInfo?.is_default">
        <van-icon name="delete-o" size="18" @click="confirmDelete" />
      </template>
    </van-nav-bar>
    
    <van-loading v-if="loading" class="loading-center" />
    
    <template v-else-if="listInfo">
      <div class="list-header">
        <p class="list-desc">{{ listInfo.desc || '暂无描述' }}</p>
        <p class="list-count">共 {{ filteredComics.length }} 部漫画</p>
      </div>
      
      <div class="action-bar">
        <van-button 
          size="small" 
          type="primary" 
          plain 
          @click="showSortPanel = true"
          class="action-btn"
        >
          排序
          <van-icon name="sort" />
        </van-button>
        <van-button 
          size="small" 
          type="primary" 
          plain 
          @click="showFilterPanel = true"
          class="action-btn"
        >
          筛选
          <van-icon name="filter-o" />
        </van-button>
      </div>
      
      <div v-if="hasActiveFilter" class="active-filter-bar">
        <van-tag 
          v-if="currentSortType" 
          type="primary" 
          closeable 
          @close="clearSort"
          class="filter-tag"
        >
          {{ sortLabel }}
        </van-tag>
        <van-tag 
          v-if="minScore !== null && minScore > 0" 
          type="primary" 
          closeable 
          @close="clearScoreFilter"
          class="filter-tag"
        >
          评分 ≥ {{ minScore }}
        </van-tag>
        <van-tag 
          v-for="tag in selectedIncludeTags" 
          :key="tag.id" 
          type="success" 
          closeable 
          @close="removeIncludeTag(tag.id)"
          class="filter-tag"
        >
          包含: {{ tag.name }}
        </van-tag>
        <van-tag 
          v-for="tag in selectedExcludeTags" 
          :key="tag.id" 
          type="danger" 
          closeable 
          @close="removeExcludeTag(tag.id)"
          class="filter-tag"
        >
          排除: {{ tag.name }}
        </van-tag>
        <van-button size="mini" plain @click="clearAllFilters">清空</van-button>
      </div>
      
      <van-empty v-if="filteredComics.length === 0" description="没有匹配的漫画" />
      
      <div v-else class="comic-grid">
        <div
          v-for="comic in filteredComics"
          :key="comic.id"
          class="comic-card"
          @click="goToComic(comic.id)"
        >
          <img :src="getCoverUrl(comic.cover_path)" class="comic-cover" alt="" />
          <div class="comic-info">
            <p class="comic-title">{{ comic.title }}</p>
            <div class="comic-meta">
              <span v-if="comic.score" class="comic-score">{{ comic.score }}分</span>
              <span class="comic-pages">{{ comic.current_page }}/{{ comic.total_page }}</span>
            </div>
          </div>
          <van-icon
            v-if="!listInfo.is_default"
            name="cross"
            class="remove-btn"
            @click.stop="removeComic(comic.id)"
          />
        </div>
      </div>
    </template>
    
    <van-popup 
      v-model:show="showSortPanel" 
      position="bottom" 
      round 
      :style="{ height: '40%' }"
    >
      <div class="sort-panel">
        <van-nav-bar title="排序方式" left-text="关闭" @click-left="showSortPanel = false" />
        <van-cell-group>
          <van-cell 
            title="按添加时间" 
            clickable 
            @click="setSortType('create_time')"
          >
            <template #right-icon>
              <van-icon v-if="currentSortType === 'create_time'" name="success" color="#1989fa" />
            </template>
          </van-cell>
          <van-cell 
            title="按评分从高到低" 
            clickable 
            @click="setSortType('score')"
          >
            <template #right-icon>
              <van-icon v-if="currentSortType === 'score'" name="success" color="#1989fa" />
            </template>
          </van-cell>
          <van-cell 
            title="按最后阅读时间" 
            clickable 
            @click="setSortType('read_time')"
          >
            <template #right-icon>
              <van-icon v-if="currentSortType === 'read_time'" name="success" color="#1989fa" />
            </template>
          </van-cell>
          <van-cell 
            title="已读/未读（未读优先）" 
            clickable 
            @click="setSortType('read_status')"
          >
            <template #right-icon>
              <van-icon v-if="currentSortType === 'read_status'" name="success" color="#1989fa" />
            </template>
          </van-cell>
        </van-cell-group>
      </div>
    </van-popup>
    
    <van-popup 
      v-model:show="showFilterPanel" 
      position="bottom" 
      round 
      :style="{ height: '70%' }"
    >
      <div class="filter-panel">
        <van-nav-bar title="筛选" left-text="关闭" @click-left="showFilterPanel = false">
          <template #right>
            <van-button type="primary" size="small" @click="applyFilterAndClose">确定</van-button>
          </template>
        </van-nav-bar>
        
        <div class="filter-content">
          <div class="score-filter-section">
            <div class="section-title">评分筛选</div>
            <div class="score-input">
              <span class="label">最低评分</span>
              <van-stepper v-model="tempMinScore" :min="0" :max="10" :step="0.5" />
            </div>
          </div>
          
          <div class="tag-filter-section">
            <TagFilter
              v-model:include-tags="tempIncludeTags"
              v-model:exclude-tags="tempExcludeTags"
              :tags="allTags"
              show-count
            />
          </div>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useListStore, useTagStore } from '@/stores'
import { buildCoverUrl } from '@/api/image'
import { showConfirmDialog, showSuccessToast, showFailToast } from 'vant'
import { TagFilter } from '@/components'

const route = useRoute()
const router = useRouter()
const listStore = useListStore()
const tagStore = useTagStore()

const loading = ref(false)
const listInfo = ref(null)
const listId = computed(() => route.params.id)

const showSortPanel = ref(false)
const showFilterPanel = ref(false)
const currentSortType = ref('')
const minScore = ref(null)
const maxScore = ref(null)
const includeTags = ref([])
const excludeTags = ref([])

const tempMinScore = ref(0)
const tempIncludeTags = ref([])
const tempExcludeTags = ref([])

const comics = computed(() => listInfo.value?.comics || [])
const allTags = computed(() => tagStore.tags)

const sortLabel = computed(() => {
  const labels = {
    'create_time': '按添加时间',
    'score': '按评分',
    'read_time': '按阅读时间',
    'read_status': '已读/未读'
  }
  return labels[currentSortType.value] || ''
})

const selectedIncludeTags = computed(() => {
  return includeTags.value
    .map(id => allTags.value.find(tag => tag.id === id))
    .filter(Boolean)
})

const selectedExcludeTags = computed(() => {
  return excludeTags.value
    .map(id => allTags.value.find(tag => tag.id === id))
    .filter(Boolean)
})

const hasActiveFilter = computed(() => {
  return currentSortType.value || 
         (minScore.value !== null && minScore.value > 0) || 
         includeTags.value.length > 0 || 
         excludeTags.value.length > 0
})

const filteredComics = computed(() => {
  let result = [...comics.value]
  
  if (minScore.value !== null && minScore.value > 0) {
    result = result.filter(c => {
      const score = c.score ?? 0
      return score >= minScore.value
    })
  }
  
  if (includeTags.value.length > 0) {
    result = result.filter(c => {
      const comicTags = c.tag_ids || []
      return includeTags.value.every(tagId => comicTags.includes(tagId))
    })
  }
  
  if (excludeTags.value.length > 0) {
    result = result.filter(c => {
      const comicTags = c.tag_ids || []
      return !excludeTags.value.some(tagId => comicTags.includes(tagId))
    })
  }
  
  if (currentSortType.value) {
    switch (currentSortType.value) {
      case 'create_time':
        result.sort((a, b) => (b.create_time || '').localeCompare(a.create_time || ''))
        break
      case 'score':
        result.sort((a, b) => (b.score || 0) - (a.score || 0))
        break
      case 'read_time':
        result.sort((a, b) => (b.last_read_time || '').localeCompare(a.last_read_time || ''))
        break
      case 'read_status':
        result.sort((a, b) => {
          const aRead = a.current_page >= a.total_page
          const bRead = b.current_page >= b.total_page
          if (aRead !== bRead) return aRead ? 1 : -1
          return (b.score || 0) - (a.score || 0)
        })
        break
    }
  }
  
  return result
})

function getCoverUrl(coverPath) {
  return buildCoverUrl(coverPath)
}

async function loadDetail() {
  loading.value = true
  const result = await listStore.fetchListDetail(listId.value)
  listInfo.value = result
  loading.value = false
}

function goToComic(comicId) {
  router.push(`/comic/${comicId}`)
}

async function removeComic(comicId) {
  showConfirmDialog({
    title: '移出漫画',
    message: '确定要将该漫画从清单中移出吗？',
  })
    .then(async () => {
      const result = await listStore.removeComics(listId.value, [comicId])
      if (result) {
        await loadDetail()
      }
    })
    .catch(() => {})
}

async function confirmDelete() {
  showConfirmDialog({
    title: '删除清单',
    message: `确定要删除清单「${listInfo.value.name}」吗？`,
  })
    .then(async () => {
      const result = await listStore.deleteList(listId.value)
      if (result) {
        router.back()
      }
    })
    .catch(() => {})
}

function setSortType(sortType) {
  currentSortType.value = sortType
  showSortPanel.value = false
}

function clearSort() {
  currentSortType.value = ''
}

function removeIncludeTag(tagId) {
  includeTags.value = includeTags.value.filter(id => id !== tagId)
}

function removeExcludeTag(tagId) {
  excludeTags.value = excludeTags.value.filter(id => id !== tagId)
}

function clearScoreFilter() {
  minScore.value = null
  tempMinScore.value = 0
}

function clearAllFilters() {
  currentSortType.value = ''
  minScore.value = null
  tempMinScore.value = 0
  includeTags.value = []
  excludeTags.value = []
  tempIncludeTags.value = []
  tempExcludeTags.value = []
}

function applyFilterAndClose() {
  minScore.value = tempMinScore.value > 0 ? tempMinScore.value : null
  includeTags.value = [...tempIncludeTags.value]
  excludeTags.value = [...tempExcludeTags.value]
  showFilterPanel.value = false
}

watch(showFilterPanel, (val) => {
  if (val) {
    tempMinScore.value = minScore.value || 0
    tempIncludeTags.value = [...includeTags.value]
    tempExcludeTags.value = [...excludeTags.value]
  }
})

onMounted(async () => {
  if (tagStore.tags.length === 0) {
    await tagStore.fetchTags()
  }
  await loadDetail()
})
</script>

<style scoped>
.list-detail {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 20px;
}

.loading-center {
  display: flex;
  justify-content: center;
  padding-top: 100px;
}

.list-header {
  padding: 16px;
  background: #fff;
  margin-bottom: 12px;
}

.list-desc {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.list-count {
  font-size: 12px;
  color: #999;
}

.action-bar {
  padding: 8px 16px;
  background: #fff;
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.action-btn {
  flex: 1;
}

.active-filter-bar {
  padding: 8px 16px;
  background: #fff;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  border-bottom: 1px solid #eee;
}

.filter-tag {
  margin-right: 4px;
}

.comic-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 8px;
}

.comic-card {
  position: relative;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}

.comic-cover {
  width: 100%;
  aspect-ratio: 3/4;
  object-fit: cover;
}

.comic-info {
  padding: 8px;
}

.comic-title {
  font-size: 12px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  margin-bottom: 4px;
}

.comic-meta {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #999;
}

.comic-score {
  color: #ffd21e;
}

.remove-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  border-radius: 50%;
  padding: 4px;
  font-size: 12px;
}

.filter-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.filter-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.score-filter-section {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #eee;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}

.score-input {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.score-input .label {
  font-size: 14px;
  color: #666;
}

.tag-filter-section {
  margin-top: 8px;
}

@media (min-width: 768px) {
  .comic-grid {
    grid-template-columns: repeat(5, 1fr);
  }
}
</style>
