<template>
  <div class="trash">
    <van-nav-bar title="回收站" left-text="返回" left-arrow @click-left="$router.back()" />
    
    <van-tabs v-model:active="activeTab" sticky>
      <van-tab title="主页回收站">
        <van-loading v-if="loading.home" type="spinner" color="#1989fa" />
        
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
          
          <div class="comic-select-grid">
            <div 
              v-for="comic in homeTrashList" 
              :key="comic.id" 
              class="comic-select-item"
              :class="{ selected: selectedHomeIds.includes(comic.id) }"
              @click="toggleHomeSelection(comic.id)"
            >
              <van-image 
                :src="getCoverUrl(comic.cover_path)" 
                fit="contain" 
                class="comic-thumb"
              />
              <div class="comic-title-line">{{ comic.title }}</div>
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
        <van-loading v-if="loading.recommendation" type="spinner" color="#1989fa" />
        
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
          
          <div class="comic-select-grid">
            <div 
              v-for="comic in recommendationTrashList" 
              :key="comic.id" 
              class="comic-select-item"
              :class="{ selected: selectedRecommendationIds.includes(comic.id) }"
              @click="toggleRecommendationSelection(comic.id)"
            >
              <van-image 
                :src="getCoverUrl(comic.cover_path)" 
                fit="contain" 
                class="comic-thumb"
              />
              <div class="comic-title-line">{{ comic.title }}</div>
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
import { ref, onMounted } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import { comicApi, recommendationApi } from '@/api'
import EmptyState from '@/components/common/EmptyState.vue'

const activeTab = ref(0)
const homeTrashList = ref([])
const recommendationTrashList = ref([])
const selectedHomeIds = ref([])
const selectedRecommendationIds = ref([])
const loading = ref({
  home: false,
  recommendation: false
})

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

async function restoreComic(type, comicId) {
  try {
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
      message: '确定要永久删除此漫画吗？此操作不可恢复！'
    })
    
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

onMounted(() => {
  fetchHomeTrash()
  fetchRecommendationTrash()
})
</script>

<style scoped>
.trash {
  min-height: 100vh;
  background: #f5f5f5;
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

.comic-select-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 8px;
}

.comic-select-item {
  position: relative;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid transparent;
  transition: border-color 0.2s;
}

.comic-select-item.selected {
  border-color: #1989fa;
}

.comic-thumb {
  width: 100%;
  aspect-ratio: 3/4;
}

.comic-title-line {
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
