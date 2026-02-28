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
        <p class="list-count">共 {{ listInfo.comic_count }} 部漫画</p>
      </div>
      
      <van-empty v-if="comics.length === 0" description="清单内暂无漫画" />
      
      <div v-else class="comic-grid">
        <div
          v-for="comic in comics"
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useListStore } from '@/stores'
import { buildCoverUrl } from '@/api/image'
import { showConfirmDialog, showSuccessToast, showFailToast } from 'vant'

const route = useRoute()
const router = useRouter()
const listStore = useListStore()

const loading = ref(false)
const listInfo = ref(null)
const listId = computed(() => route.params.id)

const comics = computed(() => listInfo.value?.comics || [])

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

onMounted(() => {
  loadDetail()
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

@media (min-width: 768px) {
  .comic-grid {
    grid-template-columns: repeat(5, 1fr);
  }
}
</style>
