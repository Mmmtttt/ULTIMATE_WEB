<template>
  <div class="trash">
    <van-nav-bar :title="pageTitle" left-text="返回" left-arrow @click-left="$router.back()" />
    
    <!-- 视频模式：单列表 -->
    <div v-if="isVideoMode" class="trash-content">
      <van-loading v-if="loading.video" type="spinner" color="#1989fa" class="loading-center" />
      
      <EmptyState
        v-else-if="videoTrashList.length === 0"
        icon="🗑️"
        title="回收站为空"
        description="没有已删除的视频"
      />
      
      <template v-else>
        <div class="manage-bar">
          <span class="selected-info">已选 {{ selectedVideoIds.length }} 个</span>
          <div class="manage-actions">
            <van-button 
              size="small" 
              type="primary" 
              :disabled="selectedVideoIds.length === 0"
              @click="batchRestore('video')"
            >
              批量恢复
            </van-button>
            <van-button 
              size="small" 
              type="danger" 
              :disabled="selectedVideoIds.length === 0"
              @click="batchDelete('video')"
            >
              批量删除
            </van-button>
          </div>
        </div>
        
        <div class="media-grid">
          <div 
            v-for="video in videoTrashList" 
            :key="video.id" 
            class="media-item"
            :class="{ selected: selectedVideoIds.includes(video.id) }"
            @click="toggleVideoSelection(video.id)"
          >
            <van-image 
              :src="getCoverUrl(video.cover_path)" 
              fit="cover" 
              class="media-thumb video-thumb"
            />
            <div class="media-title">{{ video.title }}</div>
            <div class="select-check" v-if="selectedVideoIds.includes(video.id)">
              <van-icon name="success" />
            </div>
            <div class="item-actions">
              <van-button size="mini" type="primary" @click.stop="restoreComic('video', video.id)">恢复</van-button>
              <van-button size="mini" type="danger" @click.stop="deleteComic('video', video.id)">删除</van-button>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- 漫画模式：Tabs -->
    <van-tabs v-else v-model:active="activeTab" sticky>
      <van-tab title="主页回收站">
        <van-loading v-if="loading.home" type="spinner" color="#1989fa" class="loading-center" />
        
        <EmptyState
          v-else-if="homeTrashList.length === 0"
          icon="🗑️"
          title="回收站为空"
          description="没有已删除的漫画"
        />
        
        <template v-else>
          <div class="manage-bar">
            <span class="selected-info">已选 {{ selectedHomeIds.length }} 个</span>
            <div class="manage-actions">
              <van-button 
                size="small" 
                type="primary" 
                :disabled="selectedHomeIds.length === 0"
                @click="batchRestore('home')"
              >
                批量恢复
              </van-button>
              <van-button 
                size="small" 
                type="danger" 
                :disabled="selectedHomeIds.length === 0"
                @click="batchDelete('home')"
              >
                批量删除
              </van-button>
            </div>
          </div>
          
          <div class="media-grid">
            <div 
              v-for="comic in homeTrashList" 
              :key="comic.id" 
              class="media-item"
              :class="{ selected: selectedHomeIds.includes(comic.id) }"
              @click="toggleHomeSelection(comic.id)"
            >
              <van-image 
                :src="getCoverUrl(comic.cover_path)" 
                fit="contain" 
                class="media-thumb"
              />
              <div class="media-title">{{ comic.title }}</div>
              <div class="select-check" v-if="selectedHomeIds.includes(comic.id)">
                <van-icon name="success" />
              </div>
              <div class="item-actions">
                <van-button size="mini" type="primary" @click.stop="restoreComic('home', comic.id)">恢复</van-button>
                <van-button size="mini" type="danger" @click.stop="deleteComic('home', comic.id)">删除</van-button>
              </div>
            </div>
          </div>
        </template>
      </van-tab>
      
      <van-tab title="推荐页回收站">
        <van-loading v-if="loading.recommendation" type="spinner" color="#1989fa" class="loading-center" />
        
        <EmptyState
          v-else-if="recommendationTrashList.length === 0"
          icon="🗑️"
          title="回收站为空"
          description="没有已删除的漫画"
        />
        
        <template v-else>
          <div class="manage-bar">
            <span class="selected-info">已选 {{ selectedRecommendationIds.length }} 个</span>
            <div class="manage-actions">
              <van-button 
                size="small" 
                type="primary" 
                :disabled="selectedRecommendationIds.length === 0"
                @click="batchRestore('recommendation')"
              >
                批量恢复
              </van-button>
              <van-button 
                size="small" 
                type="danger" 
                :disabled="selectedRecommendationIds.length === 0"
                @click="batchDelete('recommendation')"
              >
                批量删除
              </van-button>
            </div>
          </div>
          
          <div class="media-grid">
            <div 
              v-for="comic in recommendationTrashList" 
              :key="comic.id" 
              class="media-item"
              :class="{ selected: selectedRecommendationIds.includes(comic.id) }"
              @click="toggleRecommendationSelection(comic.id)"
            >
              <van-image 
                :src="getCoverUrl(comic.cover_path)" 
                fit="contain" 
                class="media-thumb"
              />
              <div class="media-title">{{ comic.title }}</div>
              <div class="select-check" v-if="selectedRecommendationIds.includes(comic.id)">
                <van-icon name="success" />
              </div>
              <div class="item-actions">
                <van-button size="mini" type="primary" @click.stop="restoreComic('recommendation', comic.id)">恢复</van-button>
                <van-button size="mini" type="danger" @click.stop="deleteComic('recommendation', comic.id)">删除</van-button>
              </div>
            </div>
          </div>
        </template>
      </van-tab>
    </van-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import { comicApi, recommendationApi } from '@/api'
import { useVideoStore, useModeStore } from '@/stores'
import EmptyState from '@/components/common/EmptyState.vue'

const activeTab = ref(0)
const homeTrashList = ref([])
const recommendationTrashList = ref([])
const videoTrashList = ref([])
const selectedHomeIds = ref([])
const selectedRecommendationIds = ref([])
const selectedVideoIds = ref([])
const loading = ref({
  home: false,
  recommendation: false,
  video: false
})

const videoStore = useVideoStore()
const modeStore = useModeStore()

const isVideoMode = computed(() => modeStore.isVideoMode)
const pageTitle = computed(() => isVideoMode.value ? '视频回收站' : '漫画回收站')

async function fetchHomeTrash() {
  loading.value.home = true
  try {
    const res = await comicApi.getTrashList()
    if (res.code === 200) {
      homeTrashList.value = res.data || []
    }
  } catch (e) {
    showToast('获取主页回收站失败')
  } finally {
    loading.value.home = false
  }
}

async function fetchRecommendationTrash() {
  loading.value.recommendation = true
  try {
    const res = await recommendationApi.getTrashList()
    if (res.code === 200) {
      recommendationTrashList.value = res.data || []
    }
  } catch (e) {
    showToast('获取推荐页回收站失败')
  } finally {
    loading.value.recommendation = false
  }
}

async function fetchVideoTrash() {
  loading.value.video = true
  try {
    await videoStore.fetchTrashList()
    videoTrashList.value = videoStore.trashList
  } catch (e) {
    showToast('获取视频回收站失败')
  } finally {
    loading.value.video = false
  }
}

function getCoverUrl(coverPath) {
  if (!coverPath) return ''
  if (coverPath.startsWith('http')) return coverPath
  if (coverPath.startsWith('/static/')) return coverPath
  if (coverPath.startsWith('/')) return coverPath
  return `/${coverPath}`
}

function toggleHomeSelection(comicId) {
  const index = selectedHomeIds.value.indexOf(comicId)
  if (index > -1) {
    selectedHomeIds.value.splice(index, 1)
  } else {
    selectedHomeIds.value.push(comicId)
  }
}

function toggleRecommendationSelection(comicId) {
  const index = selectedRecommendationIds.value.indexOf(comicId)
  if (index > -1) {
    selectedRecommendationIds.value.splice(index, 1)
  } else {
    selectedRecommendationIds.value.push(comicId)
  }
}

function toggleVideoSelection(videoId) {
  const index = selectedVideoIds.value.indexOf(videoId)
  if (index > -1) {
    selectedVideoIds.value.splice(index, 1)
  } else {
    selectedVideoIds.value.push(videoId)
  }
}

async function restoreComic(type, comicId) {
  try {
    if (type === 'video') {
      const res = await videoStore.restoreFromTrash(comicId)
      if (res) {
        showToast('已恢复')
        videoTrashList.value = videoTrashList.value.filter(v => v.id !== comicId)
        selectedVideoIds.value = selectedVideoIds.value.filter(id => id !== comicId)
      } else {
        showToast('恢复失败')
      }
      return
    }

    const api = type === 'home' ? comicApi : recommendationApi
    const res = await api.restoreFromTrash(comicId)
    if (res.code === 200) {
      showToast('已恢复')
      if (type === 'home') {
        homeTrashList.value = homeTrashList.value.filter(c => c.id !== comicId)
        selectedHomeIds.value = selectedHomeIds.value.filter(id => id !== comicId)
      } else {
        recommendationTrashList.value = recommendationTrashList.value.filter(c => c.id !== comicId)
        selectedRecommendationIds.value = selectedRecommendationIds.value.filter(id => id !== comicId)
      }
    } else {
      showToast(res.msg || '恢复失败')
    }
  } catch (e) {
    showToast('恢复失败')
  }
}

async function deleteComic(type, comicId) {
  try {
    await showConfirmDialog({
      title: '永久删除',
      message: '确定要永久删除此内容吗？此操作不可恢复！'
    })
    
    if (type === 'video') {
      const res = await videoStore.deletePermanently(comicId)
      if (res) {
        showToast('已永久删除')
        videoTrashList.value = videoTrashList.value.filter(v => v.id !== comicId)
        selectedVideoIds.value = selectedVideoIds.value.filter(id => id !== comicId)
      } else {
        showToast('删除失败')
      }
      return
    }

    const api = type === 'home' ? comicApi : recommendationApi
    const res = await api.deletePermanently(comicId)
    if (res.code === 200) {
      showToast('已永久删除')
      if (type === 'home') {
        homeTrashList.value = homeTrashList.value.filter(c => c.id !== comicId)
        selectedHomeIds.value = selectedHomeIds.value.filter(id => id !== comicId)
      } else {
        recommendationTrashList.value = recommendationTrashList.value.filter(c => c.id !== comicId)
        selectedRecommendationIds.value = selectedRecommendationIds.value.filter(id => id !== comicId)
      }
    } else {
      showToast(res.msg || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      showToast('删除失败')
    }
  }
}

async function batchRestore(type) {
  if (type === 'video') {
    const ids = selectedVideoIds.value
    if (ids.length === 0) return
    
    let successCount = 0
    for (const id of ids) {
      const res = await videoStore.restoreFromTrash(id)
      if (res) successCount++
    }
    
    showToast(`已恢复 ${successCount} 个视频`)
    videoTrashList.value = videoTrashList.value.filter(v => !ids.includes(v.id))
    selectedVideoIds.value = []
    return
  }

  const ids = type === 'home' ? selectedHomeIds.value : selectedRecommendationIds.value
  if (ids.length === 0) return
  
  try {
    const api = type === 'home' ? comicApi : recommendationApi
    const res = await api.batchRestoreFromTrash(ids)
    if (res.code === 200) {
      showToast(`已恢复 ${ids.length} 个漫画`)
      if (type === 'home') {
        homeTrashList.value = homeTrashList.value.filter(c => !ids.includes(c.id))
        selectedHomeIds.value = []
      } else {
        recommendationTrashList.value = recommendationTrashList.value.filter(c => !ids.includes(c.id))
        selectedRecommendationIds.value = []
      }
    } else {
      showToast(res.msg || '恢复失败')
    }
  } catch (e) {
    showToast('恢复失败')
  }
}

async function batchDelete(type) {
  if (type === 'video') {
    const ids = selectedVideoIds.value
    if (ids.length === 0) return
    
    try {
      await showConfirmDialog({
        title: '永久删除',
        message: `确定要永久删除 ${ids.length} 个视频吗？此操作不可恢复！`
      })
      
      let successCount = 0
      for (const id of ids) {
        const res = await videoStore.deletePermanently(id)
        if (res) successCount++
      }
      
      showToast(`已永久删除 ${successCount} 个视频`)
      videoTrashList.value = videoTrashList.value.filter(v => !ids.includes(v.id))
      selectedVideoIds.value = []
    } catch (e) {
      if (e !== 'cancel') showToast('删除失败')
    }
    return
  }

  const ids = type === 'home' ? selectedHomeIds.value : selectedRecommendationIds.value
  if (ids.length === 0) return
  
  try {
    await showConfirmDialog({
      title: '永久删除',
      message: `确定要永久删除 ${ids.length} 个漫画吗？此操作不可恢复！`
    })
    
    const api = type === 'home' ? comicApi : recommendationApi
    const res = await api.batchDeletePermanently(ids)
    if (res.code === 200) {
      showToast(`已永久删除 ${ids.length} 个漫画`)
      if (type === 'home') {
        homeTrashList.value = homeTrashList.value.filter(c => !ids.includes(c.id))
        selectedHomeIds.value = []
      } else {
        recommendationTrashList.value = recommendationTrashList.value.filter(c => !ids.includes(c.id))
        selectedRecommendationIds.value = []
      }
    } else {
      showToast(res.msg || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      showToast('删除失败')
    }
  }
}

function loadData() {
  if (isVideoMode.value) {
    fetchVideoTrash()
  } else {
    fetchHomeTrash()
    fetchRecommendationTrash()
  }
}

watch(isVideoMode, () => {
  loadData()
})

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.trash {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 50px;
}

.loading-center {
  padding: 40px;
  text-align: center;
}

.manage-bar {
  padding: 10px 16px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #eee;
}

.selected-info {
  font-size: 14px;
  color: #333;
}

.manage-actions {
  display: flex;
  gap: 8px;
}

.media-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 8px;
}

.media-item {
  position: relative;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid transparent;
  transition: border-color 0.2s;
}

.media-item.selected {
  border-color: #1989fa;
}

.media-thumb {
  width: 100%;
  aspect-ratio: 3/4;
}

.video-thumb {
  aspect-ratio: 16/9;
}

.media-title {
  padding: 4px 6px;
  font-size: 12px;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.select-check {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  background: #1989fa;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 12px;
}

.item-actions {
  display: flex;
  gap: 4px;
  padding: 4px 6px 6px;
}

.item-actions .van-button {
  flex: 1;
  font-size: 10px;
}
</style>
