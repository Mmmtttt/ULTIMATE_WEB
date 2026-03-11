<template>
  <div class="base-tag-manage">
    <van-nav-bar :title="pageTitle" left-text="返回" left-arrow @click-left="$router.back()">
      <template #right>
        <van-icon name="plus" @click="showAddPopup = true" />
      </template>
    </van-nav-bar>
    
    <van-tabs v-model:active="activeTab" sticky>
      <van-tab v-for="tab in tabs" :key="tab.key" :title="tab.title">
        <van-loading v-if="loading" type="spinner" color="#1989fa" />
        
        <div v-else-if="getTagList(tab.key).length === 0" class="empty">
          <van-empty description="暂无标签" />
          <van-button type="primary" @click="showAddPopup = true">添加标签</van-button>
        </div>
        
        <div v-else class="tag-list">
          <van-swipe-cell v-for="tag in getTagList(tab.key)" :key="tag.id">
            <van-cell 
              :title="tag.name" 
              :label="getTagLabel(tag, tab.key)"
              is-link
              @click="goToTagDetail(tag.id, tab.key)"
            >
              <template #icon>
                <van-icon name="label-o" class="tag-icon" />
              </template>
            </van-cell>
            <template #right>
              <van-button square type="primary" text="编辑" class="swipe-btn" @click="openEditPopup(tag)" />
              <van-button square type="danger" text="删除" class="swipe-btn" @click="confirmDelete(tag)" />
            </template>
          </van-swipe-cell>
        </div>
      </van-tab>
      
      <van-tab title="批量操作">
        <div class="batch-section">
          <div class="section-header">
            <span class="section-title">{{ contentLabel }}</span>
            <span class="selected-count" v-if="selectedContentIds.length > 0">
              已选 {{ selectedContentIds.length }} 个
            </span>
          </div>
          
          <div class="content-select-grid">
            <div 
              v-for="item in contentList" 
              :key="item.id" 
              class="content-select-item"
              :class="{ selected: selectedContentIds.includes(item.id) }"
              @click="toggleContentSelection(item.id)"
            >
              <van-image 
                :src="getCoverUrl(item.cover_path)" 
                :fit="coverFit"
                class="content-thumb"
              />
              <div class="content-title-line">{{ item.title }}</div>
              <div v-if="item.code" class="content-code-line">{{ item.code }}</div>
              <div class="select-check" v-if="selectedContentIds.includes(item.id)">
                <van-icon name="success" />
              </div>
            </div>
          </div>
          
          <div class="section-header">
            <span class="section-title">选择标签</span>
          </div>
          
          <div class="tag-select-grid">
            <van-tag 
              v-for="tag in allTags" 
              :key="tag.id" 
              :type="selectedTagIds.includes(tag.id) ? 'primary' : 'default'"
              size="large"
              class="tag-select-item"
              @click="toggleTagSelection(tag.id)"
            >
              {{ tag.name }}
            </van-tag>
          </div>
          
          <div class="batch-actions">
            <van-button 
              type="primary" 
              block 
              :disabled="!canBatchAdd"
              @click="batchAddTags"
            >
              批量添加标签
            </van-button>
            <van-button 
              type="danger" 
              block 
              :disabled="!canBatchRemove"
              @click="batchRemoveTags"
            >
              批量移除标签
            </van-button>
          </div>
        </div>
      </van-tab>
    </van-tabs>
    
    <van-popup 
      v-model:show="showAddPopup" 
      position="bottom" 
      round 
      :style="{ height: '40%' }"
    >
      <div class="popup-content">
        <van-nav-bar title="添加标签">
          <template #right>
            <van-button type="primary" size="small" @click="addTag">确定</van-button>
          </template>
        </van-nav-bar>
        
        <van-cell-group inset>
          <van-field 
            v-model="newTagName" 
            label="标签名称" 
            placeholder="请输入标签名称"
          />
        </van-cell-group>
      </div>
    </van-popup>
    
    <van-popup 
      v-model:show="showEditPopup" 
      position="bottom" 
      round 
      :style="{ height: '40%' }"
    >
      <div class="popup-content">
        <van-nav-bar title="编辑标签">
          <template #right>
            <van-button type="primary" size="small" @click="editTag">保存</van-button>
          </template>
        </van-nav-bar>
        
        <van-cell-group inset>
          <van-field 
            v-model="editTagName" 
            label="标签名称" 
            placeholder="请输入标签名称"
          />
        </van-cell-group>
      </div>
    </van-popup>
    
    <van-tabbar v-model="active" route>
      <van-tabbar-item icon="home-o" :to="homePath">主页</van-tabbar-item>
      <van-tabbar-item icon="user-o" to="/mine">我的</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { getCoverUrl, toggleSelection } from '@/utils/helpers'

const props = defineProps({
  contentType: {
    type: String,
    default: 'comic',
    validator: (v) => ['comic', 'video'].includes(v)
  },
  tagStore: {
    type: Object,
    required: true
  },
  tagApi: {
    type: Object,
    required: true
  },
  homePath: {
    type: String,
    default: '/'
  }
})

const emit = defineEmits(['tab-change'])

const router = useRouter()

const active = ref(1)
const activeTab = ref(0)
const loading = ref(true)
const contentList = ref([])
const showAddPopup = ref(false)
const showEditPopup = ref(false)
const newTagName = ref('')
const editTagName = ref('')
const editingTag = ref(null)
const selectedContentIds = ref([])
const selectedTagIds = ref([])

const isVideo = computed(() => props.contentType === 'video')

const pageTitle = computed(() => isVideo.value ? '视频标签管理' : '标签管理')

const contentLabel = computed(() => isVideo.value ? '选择视频' : '选择漫画')

const coverFit = computed(() => isVideo.value ? 'cover' : 'contain')

const tabs = computed(() => {
  if (isVideo.value) {
    return [{ key: 'video', title: '标签列表' }]
  }
  return [
    { key: 'comic', title: '漫画标签' },
    { key: 'video', title: '视频标签' }
  ]
})

const allTags = computed(() => {
  const currentTab = tabs.value[activeTab.value]
  if (!currentTab) return []
  return getTagList(currentTab.key)
})

const canBatchAdd = computed(() => {
  return selectedContentIds.value.length > 0 && selectedTagIds.value.length > 0
})

const canBatchRemove = computed(() => {
  return selectedContentIds.value.length > 0 && selectedTagIds.value.length > 0
})

function getTagList(tabKey) {
  if (tabKey === 'video') {
    return sortTags(props.tagStore.videoTags || [], 'video_count')
  }
  return sortTags(props.tagStore.tags || [], 'comic_count')
}

function sortTags(tags, countField) {
  return [...tags].sort((a, b) => (b[countField] || 0) - (a[countField] || 0))
}

function getTagLabel(tag, tabKey) {
  const count = tabKey === 'video' ? (tag.video_count || 0) : (tag.comic_count || 0)
  const unit = tabKey === 'video' ? '个视频' : '个漫画'
  return `${count} ${unit}`
}

async function fetchTagList() {
  loading.value = true
  try {
    if (isVideo.value) {
      await props.tagStore.fetchTags('video')
    } else {
      await Promise.all([
        props.tagStore.fetchTags('comic'),
        props.tagStore.fetchTags('video')
      ])
    }
  } catch (error) {
    console.error('获取标签列表失败:', error)
    showFailToast('获取标签列表失败')
  } finally {
    loading.value = false
  }
}

async function fetchContentList() {
  try {
    const response = isVideo.value 
      ? await props.tagApi.getAllVideos()
      : await props.tagApi.getAllComics()
    
    if (response.code === 200) {
      if (isVideo.value) {
        const homeVideos = response.data.home_videos || []
        const recVideos = response.data.recommendation_videos || []
        contentList.value = [
          ...homeVideos.map(v => ({ ...v, source: 'home' })),
          ...recVideos.map(v => ({ ...v, source: 'recommendation' }))
        ]
      } else {
        const homeComics = response.data.home_comics || []
        const recComics = response.data.recommendation_comics || []
        contentList.value = [...homeComics, ...recComics]
      }
    }
  } catch (error) {
    console.error('获取内容列表失败:', error)
  }
}

async function addTag() {
  if (!newTagName.value.trim()) {
    showFailToast('请输入标签名称')
    return
  }
  
  const currentTab = tabs.value[activeTab.value]
  const contentType = currentTab?.key || props.contentType
  
  try {
    const response = await props.tagStore.addTag(newTagName.value.trim(), contentType)
    if (response.success) {
      showAddPopup.value = false
      newTagName.value = ''
      showSuccessToast('添加成功')
      await fetchTagList()
    } else {
      showFailToast(response.message || '添加失败')
    }
  } catch (error) {
    console.error('添加标签失败:', error)
    showFailToast('添加失败')
  }
}

function openEditPopup(tag) {
  editingTag.value = tag
  editTagName.value = tag.name
  showEditPopup.value = true
}

async function editTag() {
  if (!editTagName.value.trim()) {
    showFailToast('请输入标签名称')
    return
  }
  
  try {
    const response = await props.tagStore.editTag(editingTag.value.id, editTagName.value.trim())
    if (response.success) {
      showEditPopup.value = false
      showSuccessToast('修改成功')
      await fetchTagList()
    } else {
      showFailToast(response.message || '修改失败')
    }
  } catch (error) {
    console.error('修改标签失败:', error)
    showFailToast('修改失败')
  }
}

async function confirmDelete(tag) {
  try {
    const unit = isVideo.value ? '视频' : '漫画'
    await showConfirmDialog({
      title: '确认删除',
      message: `确定要删除标签"${tag.name}"吗？删除后该标签将从所有${unit}中移除。`,
    })
    
    await deleteTag(tag.id)
  } catch {
  }
}

async function deleteTag(tagId) {
  try {
    const response = await props.tagStore.deleteTag(tagId)
    if (response.success) {
      showSuccessToast('删除成功')
      await fetchTagList()
    } else {
      showFailToast(response.message || '删除失败')
    }
  } catch (error) {
    console.error('删除标签失败:', error)
    showFailToast('删除失败')
  }
}

function goToTagDetail(tagId, tabKey) {
  const route = tabKey === 'video' ? `/video-tag/${tagId}` : `/tag/${tagId}`
  router.push(route)
}

function toggleContentSelection(id) {
  toggleSelection(selectedContentIds, id)
}

function toggleTagSelection(id) {
  toggleSelection(selectedTagIds, id)
}

async function batchAddTags() {
  try {
    const unit = isVideo.value ? '视频' : '漫画'
    await showConfirmDialog({
      title: '确认操作',
      message: `确定为 ${selectedContentIds.value.length} 个${unit}添加 ${selectedTagIds.value.length} 个标签？`,
    })
    
    const contentData = contentList.value
      .filter(c => selectedContentIds.value.includes(c.id))
      .map(c => ({ id: c.id, source: c.source }))
    
    const response = isVideo.value
      ? await props.tagApi.batchAddTagsToVideos(contentData, selectedTagIds.value)
      : await props.tagApi.batchAddTags(contentData, selectedTagIds.value)
    
    if (response.code === 200) {
      showSuccessToast(response.msg || '操作成功')
      selectedContentIds.value = []
      selectedTagIds.value = []
      await fetchTagList()
      await fetchContentList()
    } else {
      showFailToast(response.msg || '操作失败')
    }
  } catch {
  }
}

async function batchRemoveTags() {
  try {
    const unit = isVideo.value ? '视频' : '漫画'
    await showConfirmDialog({
      title: '确认操作',
      message: `确定从 ${selectedContentIds.value.length} 个${unit}移除 ${selectedTagIds.value.length} 个标签？`,
    })
    
    const contentData = contentList.value
      .filter(c => selectedContentIds.value.includes(c.id))
      .map(c => ({ id: c.id, source: c.source }))
    
    const response = isVideo.value
      ? await props.tagApi.batchRemoveTagsFromVideos(contentData, selectedTagIds.value)
      : await props.tagApi.batchRemoveTags(contentData, selectedTagIds.value)
    
    if (response.code === 200) {
      showSuccessToast(response.msg || '操作成功')
      selectedContentIds.value = []
      selectedTagIds.value = []
      await fetchTagList()
      await fetchContentList()
    } else {
      showFailToast(response.msg || '操作失败')
    }
  } catch {
  }
}

onMounted(async () => {
  await fetchTagList()
  await fetchContentList()
})
</script>

<style scoped>
.base-tag-manage {
  padding-bottom: 50px;
  min-height: 100vh;
  background: #f5f5f5;
}

.tag-list {
  margin-top: 10px;
}

.tag-icon {
  margin-right: 8px;
  color: #1989fa;
}

.swipe-btn {
  height: 100%;
}

.empty {
  padding: 40px 0;
  text-align: center;
}

.empty .van-button {
  margin-top: 20px;
}

.popup-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.popup-content .van-cell-group {
  margin-top: 16px;
}

.batch-section {
  padding: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.selected-count {
  font-size: 12px;
  color: #1989fa;
}

.content-select-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 20px;
}

.content-select-item {
  position: relative;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid transparent;
  transition: all 0.2s;
}

.content-select-item.selected {
  border-color: #1989fa;
}

.content-thumb {
  width: 100%;
  height: auto;
  display: block;
}

.content-thumb :deep(.van-image__img) {
  width: 100%;
  height: auto;
  object-fit: contain;
}

.content-title-line {
  padding: 4px 6px;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content-code-line {
  padding: 0 6px 4px;
  font-size: 10px;
  color: #999;
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

.tag-select-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 20px;
}

.tag-select-item {
  cursor: pointer;
}

.batch-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
