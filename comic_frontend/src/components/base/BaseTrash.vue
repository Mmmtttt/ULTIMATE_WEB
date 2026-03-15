<template>
  <div class="base-trash">
    <van-nav-bar :title="pageTitle" left-text="返回" left-arrow @click-left="$router.back()" />
    
    <van-tabs v-model:active="activeTab" sticky>
      <van-tab v-for="tab in tabs" :key="tab.key" :title="tab.title">
        <van-loading v-if="loading[tab.key]" type="spinner" color="#1989fa" class="loading-center" />
        
        <EmptyState
          v-else-if="getTrashList(tab.key).length === 0"
          icon="🗑️"
          title="回收站为空"
          :description="`没有已删除的${tab.label}`"
        />
        
        <template v-else>
          <div class="manage-bar">
            <span class="selected-info">已选 {{ getSelectedIds(tab.key).length }} 个</span>
            <div class="manage-actions">
              <van-button
                size="small"
                plain
                type="primary"
                @click="toggleTabSelectAll(tab.key)"
              >
                {{ isAllTabSelected(tab.key) ? '取消全选' : '全选' }}
              </van-button>
              <van-button 
                size="small" 
                type="primary" 
                :disabled="getSelectedIds(tab.key).length === 0"
                @click="batchRestore(tab.key)"
              >
                批量恢复
              </van-button>
              <van-button 
                size="small" 
                type="danger" 
                :disabled="getSelectedIds(tab.key).length === 0"
                @click="batchDelete(tab.key)"
              >
                批量删除
              </van-button>
            </div>
          </div>
          
          <div class="media-grid">
            <div 
              v-for="item in getTrashList(tab.key)" 
              :key="item.id" 
              class="media-item"
              :class="{ selected: getSelectedIds(tab.key).includes(item.id) }"
              @click="toggleItemSelection(tab.key, item.id)"
            >
              <van-image 
                :src="getCoverUrl(item.cover_path)" 
                :fit="coverFit"
                class="media-thumb"
              />
              <div class="media-title">{{ item.title }}</div>
              <div class="select-check" v-if="getSelectedIds(tab.key).includes(item.id)">
                <van-icon name="success" />
              </div>
              <div class="item-actions">
                <van-button size="mini" type="primary" @click.stop="restoreItem(tab.key, item.id)">恢复</van-button>
                <van-button size="mini" type="danger" @click.stop="deleteItem(tab.key, item.id)">删除</van-button>
              </div>
            </div>
          </div>
        </template>
      </van-tab>
    </van-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import { getCoverUrl, isAllSelected, toggleSelection } from '@/utils/helpers'
import EmptyState from '@/components/common/EmptyState.vue'

const props = defineProps({
  contentType: {
    type: String,
    default: 'comic',
    validator: (v) => ['comic', 'video'].includes(v)
  },
  stores: {
    type: Object,
    required: true
  },
  apis: {
    type: Object,
    required: true
  }
})

const router = useRouter()

const activeTab = ref(0)
const trashLists = ref({
  home: [],
  recommendation: [],
  video: [],
  videoRecommendation: []
})
const selectedIds = ref({
  home: [],
  recommendation: [],
  video: [],
  videoRecommendation: []
})
const loading = ref({
  home: false,
  recommendation: false,
  video: false,
  videoRecommendation: false
})

const isVideo = computed(() => props.contentType === 'video')

const pageTitle = computed(() => isVideo.value ? '视频回收站' : '漫画回收站')

const coverFit = computed(() => isVideo.value ? 'cover' : 'contain')

const tabs = computed(() => {
  if (isVideo.value) {
    return [
      { key: 'video', title: '主页回收站', label: '视频' },
      { key: 'videoRecommendation', title: '推荐页回收站', label: '视频' }
    ]
  }
  return [
    { key: 'home', title: '主页回收站', label: '漫画' },
    { key: 'recommendation', title: '推荐页回收站', label: '漫画' }
  ]
})

function getTrashList(key) {
  return trashLists.value[key] || []
}

function getSelectedIds(key) {
  return selectedIds.value[key] || []
}

function toggleItemSelection(tabKey, id) {
  if (!selectedIds.value[tabKey]) {
    selectedIds.value[tabKey] = []
  }
  toggleSelection(
    { value: selectedIds.value[tabKey] },
    id
  )
}

function isAllTabSelected(tabKey) {
  return isAllSelected(getSelectedIds(tabKey), getTrashList(tabKey), (item) => item.id)
}

function toggleTabSelectAll(tabKey) {
  const list = getTrashList(tabKey)
  if (isAllTabSelected(tabKey)) {
    selectedIds.value[tabKey] = []
    return
  }
  selectedIds.value[tabKey] = list.map(item => item.id)
}

async function fetchTrashList(key) {
  loading.value[key] = true
  try {
    if (key === 'home') {
      const res = await props.apis.comic.getTrashList()
      if (res.code === 200) {
        trashLists.value.home = res.data || []
      }
    } else if (key === 'recommendation') {
      const res = await props.apis.recommendation.getTrashList()
      if (res.code === 200) {
        trashLists.value.recommendation = res.data || []
      }
    } else if (key === 'video') {
      await props.stores.video.fetchTrashList()
      trashLists.value.video = props.stores.video.trashList || []
    } else if (key === 'videoRecommendation') {
      await props.stores.videoRecommendation.fetchTrashList()
      trashLists.value.videoRecommendation = props.stores.videoRecommendation.trashList || []
    }
  } catch (e) {
    showToast('获取回收站失败')
  } finally {
    loading.value[key] = false
  }
}

async function restoreItem(key, id) {
  try {
    let success = false
    
    if (key === 'video') {
      success = await props.stores.video.restoreFromTrash(id)
    } else if (key === 'videoRecommendation') {
      success = await props.stores.videoRecommendation.restoreFromTrash(id)
    } else {
      const api = key === 'home' ? props.apis.comic : props.apis.recommendation
      const res = await api.restoreFromTrash(id)
      success = res.code === 200
    }
    
    if (success) {
      showToast('已恢复')
      trashLists.value[key] = trashLists.value[key].filter(i => i.id !== id)
      selectedIds.value[key] = selectedIds.value[key].filter(i => i !== id)
    } else {
      showToast('恢复失败')
    }
  } catch (e) {
    showToast('恢复失败')
  }
}

async function deleteItem(key, id) {
  try {
    await showConfirmDialog({
      title: '永久删除',
      message: '确定要永久删除此内容吗？此操作不可恢复！'
    })
    
    let success = false
    
    if (key === 'video') {
      success = await props.stores.video.deletePermanently(id)
    } else if (key === 'videoRecommendation') {
      success = await props.stores.videoRecommendation.deletePermanently(id)
    } else {
      const api = key === 'home' ? props.apis.comic : props.apis.recommendation
      const res = await api.deletePermanently(id)
      success = res.code === 200
    }
    
    if (success) {
      showToast('已永久删除')
      trashLists.value[key] = trashLists.value[key].filter(i => i.id !== id)
      selectedIds.value[key] = selectedIds.value[key].filter(i => i !== id)
    } else {
      showToast('删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      showToast('删除失败')
    }
  }
}

async function batchRestore(key) {
  const ids = selectedIds.value[key] || []
  if (ids.length === 0) return
  
  let success = false
  
  if (key === 'video') {
    const results = await Promise.all(ids.map(id => props.stores.video.restoreFromTrash(id)))
    success = results.some(Boolean)
  } else if (key === 'videoRecommendation') {
    success = await props.stores.videoRecommendation.batchRestoreFromTrash(ids)
  } else {
    const api = key === 'home' ? props.apis.comic : props.apis.recommendation
    const res = await api.batchRestoreFromTrash(ids)
    success = res.code === 200
  }
  
  if (success) {
    showToast(`已恢复 ${ids.length} 个内容`)
    trashLists.value[key] = trashLists.value[key].filter(i => !ids.includes(i.id))
    selectedIds.value[key] = []
  } else {
    showToast('恢复失败')
  }
}

async function batchDelete(key) {
  const ids = selectedIds.value[key] || []
  if (ids.length === 0) return
  
  try {
    await showConfirmDialog({
      title: '永久删除',
      message: `确定要永久删除 ${ids.length} 个内容吗？此操作不可恢复！`
    })
    
    let success = false
    
    if (key === 'video') {
      const results = await Promise.all(ids.map(id => props.stores.video.deletePermanently(id)))
      success = results.some(Boolean)
    } else if (key === 'videoRecommendation') {
      success = await props.stores.videoRecommendation.batchDeletePermanently(ids)
    } else {
      const api = key === 'home' ? props.apis.comic : props.apis.recommendation
      const res = await api.batchDeletePermanently(ids)
      success = res.code === 200
    }
    
    if (success) {
      showToast(`已永久删除 ${ids.length} 个内容`)
      trashLists.value[key] = trashLists.value[key].filter(i => !ids.includes(i.id))
      selectedIds.value[key] = []
    } else {
      showToast('删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      showToast('删除失败')
    }
  }
}

onMounted(async () => {
  for (const tab of tabs.value) {
    await fetchTrashList(tab.key)
  }
})
</script>

<style scoped>
.base-trash {
  min-height: 100vh;
  background: #f5f5f5;
}

.loading-center {
  display: flex;
  justify-content: center;
  padding: 100px 0;
}

.manage-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #eee;
}

.selected-info {
  font-size: 14px;
  color: #666;
}

.manage-actions {
  display: flex;
  gap: 8px;
}

.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
  padding: 10px;
}

.media-item {
  position: relative;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid transparent;
  transition: all 0.2s;
}

.media-item.selected {
  border-color: #1989fa;
}

.media-thumb {
  width: 100%;
  aspect-ratio: 3/4;
}

.media-thumb :deep(.van-image__img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.media-title {
  padding: 6px 8px;
  font-size: 12px;
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
  padding: 0 6px 6px;
}

.item-actions .van-button {
  flex: 1;
}
</style>
