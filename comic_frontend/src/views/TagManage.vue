<template>
  <div class="tag-manage">
    <van-nav-bar title="标签管理" left-text="返回" left-arrow @click-left="$router.back()">
      <template #right>
        <van-icon name="plus" @click="showAddPopup = true" />
      </template>
    </van-nav-bar>
    
    <van-tabs v-model:active="activeTab" sticky>
      <van-tab title="标签列表">
        <van-loading v-if="isLoading" type="spinner" color="#1989fa" />
        
        <div v-else-if="tagList.length === 0" class="empty">
          <van-empty description="暂无标签" />
          <van-button type="primary" @click="showAddPopup = true">添加标签</van-button>
        </div>
        
        <div v-else class="tag-list">
          <van-swipe-cell v-for="tag in tagList" :key="tag.id">
            <van-cell 
              :title="tag.name" 
              :label="`${tag.comic_count || 0} 个漫画`"
              is-link
              @click="goToTagComics(tag.id)"
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
            <span class="section-title">选择漫画</span>
            <span class="selected-count" v-if="selectedComicIds.length > 0">
              已选 {{ selectedComicIds.length }} 个
            </span>
          </div>
          
          <div class="comic-select-grid">
            <div 
              v-for="comic in comicList" 
              :key="comic.id" 
              class="comic-select-item"
              :class="{ selected: selectedComicIds.includes(comic.id) }"
              @click="toggleComicSelection(comic.id)"
            >
              <van-image 
                :src="getCoverUrl(comic.cover_path)" 
                fit="contain" 
                class="comic-thumb"
              />
              <div class="comic-title-line">{{ comic.title }}</div>
              <div class="select-check" v-if="selectedComicIds.includes(comic.id)">
                <van-icon name="success" />
              </div>
            </div>
          </div>
          
          <div class="section-header">
            <span class="section-title">选择标签</span>
          </div>
          
          <div class="tag-select-grid">
            <van-tag 
              v-for="tag in tagList" 
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
      <van-tabbar-item icon="home-o" to="/">主页</van-tabbar-item>
      <van-tabbar-item icon="user-o" to="/mine">我的</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useComicStore, useTagStore } from '@/stores'
import { tagApi } from '@/api'
import { buildCoverUrl } from '@/api/image'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'

const router = useRouter()
const comicStore = useComicStore()
const tagStore = useTagStore()

const active = ref(1)
const activeTab = ref(0)
const isLoading = ref(true)
const tagList = ref([])
const comicList = ref([])
const showAddPopup = ref(false)
const showEditPopup = ref(false)
const newTagName = ref('')
const editTagName = ref('')
const editingTag = ref(null)

const selectedComicIds = ref([])
const selectedTagIds = ref([])

const canBatchAdd = computed(() => {
  return selectedComicIds.value.length > 0 && selectedTagIds.value.length > 0
})

const canBatchRemove = computed(() => {
  return selectedComicIds.value.length > 0 && selectedTagIds.value.length > 0
})

const getCoverUrl = (coverPath) => {
  return buildCoverUrl(coverPath)
}

const fetchTagList = async () => {
  isLoading.value = true
  try {
    const response = await tagStore.fetchTags()
    if (response) {
      tagList.value = response
    }
  } catch (error) {
    console.error('获取标签列表失败:', error)
    showFailToast('获取标签列表失败')
  } finally {
    isLoading.value = false
  }
}

const fetchComicList = async () => {
  try {
    const response = await tagApi.getAllComics()
    if (response.code === 200) {
      const homeComics = response.data.home_comics || []
      const recommendationComics = response.data.recommendation_comics || []
      comicList.value = [...homeComics, ...recommendationComics]
    }
  } catch (error) {
    console.error('获取漫画列表失败:', error)
  }
}

const addTag = async () => {
  if (!newTagName.value.trim()) {
    showFailToast('请输入标签名称')
    return
  }
  
  try {
    const response = await tagStore.addTag(newTagName.value.trim())
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

const openEditPopup = (tag) => {
  editingTag.value = tag
  editTagName.value = tag.name
  showEditPopup.value = true
}

const editTag = async () => {
  if (!editTagName.value.trim()) {
    showFailToast('请输入标签名称')
    return
  }
  
  try {
    const response = await tagStore.editTag(editingTag.value.id, editTagName.value.trim())
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

const confirmDelete = async (tag) => {
  try {
    await showConfirmDialog({
      title: '确认删除',
      message: `确定要删除标签"${tag.name}"吗？删除后该标签将从所有漫画中移除。`,
    })
    
    await deleteTag(tag.id)
  } catch {
  }
}

const deleteTag = async (tagId) => {
  try {
    const response = await tagStore.deleteTag(tagId)
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

const goToTagComics = (tagId) => {
  router.push(`/tag/${tagId}`)
}

const toggleComicSelection = (comicId) => {
  const index = selectedComicIds.value.indexOf(comicId)
  if (index > -1) {
    selectedComicIds.value.splice(index, 1)
  } else {
    selectedComicIds.value.push(comicId)
  }
}

const toggleTagSelection = (tagId) => {
  const index = selectedTagIds.value.indexOf(tagId)
  if (index > -1) {
    selectedTagIds.value.splice(index, 1)
  } else {
    selectedTagIds.value.push(tagId)
  }
}

const batchAddTags = async () => {
  try {
    await showConfirmDialog({
      title: '确认操作',
      message: `确定为 ${selectedComicIds.value.length} 个漫画添加 ${selectedTagIds.value.length} 个标签？`,
    })
    
    const comicData = comicList.value
      .filter(c => selectedComicIds.value.includes(c.id))
      .map(c => ({ id: c.id, source: c.source }))
    
    const response = await tagApi.batchAddTags(comicData, selectedTagIds.value)
    if (response.code === 200) {
      showSuccessToast(response.msg || '操作成功')
      selectedComicIds.value = []
      selectedTagIds.value = []
      await fetchTagList()
      await fetchComicList()
    } else {
      showFailToast(response.msg || '操作失败')
    }
  } catch {
  }
}

const batchRemoveTags = async () => {
  try {
    await showConfirmDialog({
      title: '确认操作',
      message: `确定从 ${selectedComicIds.value.length} 个漫画移除 ${selectedTagIds.value.length} 个标签？`,
    })
    
    const comicData = comicList.value
      .filter(c => selectedComicIds.value.includes(c.id))
      .map(c => ({ id: c.id, source: c.source }))
    
    const response = await tagApi.batchRemoveTags(comicData, selectedTagIds.value)
    if (response.code === 200) {
      showSuccessToast(response.msg || '操作成功')
      selectedComicIds.value = []
      selectedTagIds.value = []
      await fetchTagList()
      await fetchComicList()
    } else {
      showFailToast(response.msg || '操作失败')
    }
  } catch {
  }
}

onMounted(async () => {
  await fetchTagList()
  await fetchComicList()
})
</script>

<style scoped>
.tag-manage {
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

.comic-select-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 20px;
}

.comic-select-item {
  position: relative;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid transparent;
  transition: all 0.2s;
}

.comic-select-item.selected {
  border-color: #1989fa;
}

.comic-thumb {
  width: 100%;
  height: auto;
  display: block;
}

.comic-thumb :deep(.van-image__img) {
  width: 100%;
  height: auto;
  object-fit: contain;
}

.comic-title-line {
  padding: 4px 6px;
  font-size: 11px;
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
