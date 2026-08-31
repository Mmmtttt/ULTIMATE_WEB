<template>
  <div class="base-tag-manage">
    <van-nav-bar :title="pageTitle" left-text="返回" left-arrow @click-left="$router.back()">
      <template #right>
        <button type="button" class="nav-add-button" @click="showAddPopup = true">
          <van-icon name="plus" />
          <span>添加</span>
        </button>
      </template>
    </van-nav-bar>
    
    <van-tabs v-model:active="activeTab" sticky>
      <van-tab v-for="tab in tabs" :key="tab.key" :title="tab.title">
        <van-loading v-if="loading" type="spinner" color="#1989fa" />
        
        <div v-else-if="getTagList(tab.key).length === 0" class="empty">
          <van-empty description="暂无标签" />
          <van-button type="primary" @click="showAddPopup = true">添加标签</van-button>
        </div>
        
        <div v-else class="tag-list" :class="{ 'tag-list-desktop': isDesktop }">
          <van-search
            v-model.trim="tagListKeyword"
            class="tag-search-bar"
            shape="round"
            clearable
            placeholder="搜索标签..."
          />
          <template v-for="tag in getFilteredTagList(tab.key)" :key="tag.id">
            <van-cell
              v-if="isDesktop"
              class="tag-cell-desktop"
              :title="tag.name"
              :label="getTagLabel(tag, tab.key)"
              is-link
              @click="goToTagDetail(tag.id, tab.key)"
            >
              <template #icon>
                <van-icon name="label-o" class="tag-icon" />
              </template>
              <template #right-icon>
                <div class="desktop-tag-actions" @click.stop>
                  <van-button
                    size="small"
                    plain
                    round
                    type="primary"
                    class="tag-action-btn edit-btn"
                    data-testid="tag-edit-inline"
                    @click.stop="openEditPopup(tag)"
                  >
                    编辑
                  </van-button>
                  <van-button
                    size="small"
                    plain
                    round
                    type="danger"
                    class="tag-action-btn delete-btn"
                    data-testid="tag-delete-inline"
                    @click.stop="confirmDelete(tag)"
                  >
                    删除
                  </van-button>
                  <van-icon name="arrow" class="desktop-tag-arrow" />
                </div>
              </template>
            </van-cell>

            <van-swipe-cell v-else>
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
                <van-button square type="primary" text="编辑" class="swipe-btn edit-btn" @click="openEditPopup(tag)" />
                <van-button square type="danger" text="删除" class="swipe-btn delete-btn" @click="confirmDelete(tag)" />
              </template>
            </van-swipe-cell>
          </template>
          <div v-if="getFilteredTagList(tab.key).length === 0" class="empty-search-result">
            没有匹配的标签
          </div>
        </div>
      </van-tab>
      
      <van-tab title="批量操作">
        <div class="batch-section">
          <div class="section-header">
            <span class="section-title">{{ contentLabel }}</span>
            <div class="section-right">
              <span class="selected-count" v-if="selectedContentIds.length > 0">
                已选 {{ selectedContentIds.length }} 项
              </span>
              <van-button size="mini" plain type="primary" @click="toggleSelectAllContent">
                {{ isAllContentSelected ? '取消全选' : '全选' }}
              </van-button>
            </div>
          </div>
          
          <div class="content-select-grid">
            <div 
              v-for="item in pagedContentList" 
              :key="item.id" 
              class="content-select-item"
              :class="{ selected: selectedContentIds.includes(item.id) }"
              @click="toggleContentSelection(item.id)"
            >
              <van-image 
                :src="getCoverUrl(item)" 
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

          <AppPagination
            v-if="contentList.length > 0"
            v-model="currentPage"
            class="batch-pagination"
            :total-items="totalItems"
            :page-size="pageSize"
          />
          
          <div class="section-header">
            <span class="section-title">选择标签</span>
          </div>

          <van-search
            v-model.trim="batchTagKeyword"
            class="tag-search-bar"
            shape="round"
            clearable
            placeholder="搜索可添加的标签..."
          />
          
          <div class="tag-select-grid">
            <van-tag 
              v-for="tag in filteredBatchTags" 
              :key="tag.id" 
              :type="selectedTagIds.includes(tag.id) ? 'primary' : 'default'"
              size="large"
              class="tag-select-item"
              @click="toggleTagSelection(tag.id)"
            >
              {{ tag.name }}
            </van-tag>
          </div>
          <div v-if="filteredBatchTags.length === 0" class="empty-search-result">
            没有匹配的标签
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
              type="primary"
              plain
              block
              :disabled="selectedContentIds.length === 0"
              @click="openBatchTaskSheet"
            >
              批量处理
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
      :style="{ height: 'min(360px, 72vh)' }"
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
      :style="{ height: 'min(360px, 72vh)' }"
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
    
    <van-action-sheet
      v-model:show="showBatchTaskSheet"
      title="批量处理"
      :actions="batchTaskActions"
      close-on-click-action
      @select="handleBatchTaskAction"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { useImportTaskStore, useRuntimeStore } from '@/stores'
import {
  buildBatchTaskActions,
  clearBrowseState,
  getCoverUrl,
  isAllSelected,
  keepSelectionWithinItems,
  loadBrowseState,
  saveBrowseState,
  toggleSelection
} from '@/utils'
import AppPagination from '@/components/common/AppPagination.vue'
import { useClientPagination } from '@/composables/useClientPagination'
import { useDevice } from '@/composables/useDevice'

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
const importTaskStore = useImportTaskStore()
const runtimeStore = useRuntimeStore()
const { isDesktop } = useDevice()

const activeTab = ref(0)
const loading = ref(true)
const contentList = ref([])
const showAddPopup = ref(false)
const showEditPopup = ref(false)
const newTagName = ref('')
const editTagName = ref('')
const editingTag = ref(null)
const tagListKeyword = ref('')
const batchTagKeyword = ref('')
const selectedContentIds = ref([])
const selectedTagIds = ref([])
const showBatchTaskSheet = ref(false)

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
  // 批量操作标签始终按当前页面内容类型展示，避免切到“批量操作”页时无标签可选
  return isVideo.value
    ? sortTags(props.tagStore.videoTags || [], 'video_count')
    : sortTags(props.tagStore.tags || [], 'comic_count')
})

const filteredBatchTags = computed(() => filterTagsByKeyword(allTags.value, batchTagKeyword.value))

const paginationStorageKey = computed(() => `tag_manage_batch_${props.contentType}`)
const {
  pageSize,
  currentPage,
  totalItems,
  pagedItems
} = useClientPagination(contentList, paginationStorageKey)
const pagedContentList = computed(() => pagedItems.value)

function getBrowseStateKey() {
  return `tag_manage_state_${props.contentType}`
}

function persistBrowseState() {
  const payload = {}
  if (activeTab.value > 0) {
    payload.activeTab = activeTab.value
  }
  if (currentPage.value > 1) {
    payload.currentPage = currentPage.value
  }
  if (String(tagListKeyword.value || '').trim()) {
    payload.tagListKeyword = String(tagListKeyword.value || '').trim()
  }
  if (String(batchTagKeyword.value || '').trim()) {
    payload.batchTagKeyword = String(batchTagKeyword.value || '').trim()
  }

  if (Object.keys(payload).length === 0) {
    clearBrowseState(getBrowseStateKey())
    return
  }

  saveBrowseState(getBrowseStateKey(), payload)
}

function restoreBrowseState() {
  const parsed = loadBrowseState(getBrowseStateKey(), null)
  if (!parsed) {
    return
  }
  if (Number(parsed.activeTab) >= 0) {
    activeTab.value = Math.max(0, Math.floor(Number(parsed.activeTab)))
  }
  if (Number(parsed.currentPage) >= 1) {
    currentPage.value = Math.max(1, Math.floor(Number(parsed.currentPage)))
  }
  tagListKeyword.value = String(parsed.tagListKeyword || '').trim()
  batchTagKeyword.value = String(parsed.batchTagKeyword || '').trim()
}

const canBatchAdd = computed(() => {
  return selectedContentIds.value.length > 0 && selectedTagIds.value.length > 0
})

const canBatchRemove = computed(() => {
  return selectedContentIds.value.length > 0 && selectedTagIds.value.length > 0
})

const selectedContentItems = computed(() => {
  const selectedIdSet = new Set(selectedContentIds.value)
  return contentList.value.filter((item) => selectedIdSet.has(item.id))
})

const isAllContentSelected = computed(() => {
  return isAllSelected(selectedContentIds.value, contentList.value, (item) => item.id)
})

const batchTaskActions = computed(() => {
  return buildBatchTaskActions({
    contentType: props.contentType,
    selectedItems: selectedContentItems.value,
    thirdPartyEnabled: runtimeStore.thirdPartyEnabled,
    supportsVideoThumbnailBatch: runtimeStore.supportsLocalVideoThumbnailBatch,
  }).map((action) => ({
    ...action,
    subname: action.reason || '',
  }))
})

function getTagList(tabKey) {
  if (tabKey === 'video') {
    return sortTags(props.tagStore.videoTags || [], 'video_count')
  }
  return sortTags(props.tagStore.tags || [], 'comic_count')
}

function getFilteredTagList(tabKey) {
  return filterTagsByKeyword(getTagList(tabKey), tagListKeyword.value)
}

function sortTags(tags, countField) {
  return [...tags].sort((a, b) => (b[countField] || 0) - (a[countField] || 0))
}

function filterTagsByKeyword(tags, keyword) {
  const normalizedKeyword = String(keyword || '').trim().toLowerCase()
  if (!normalizedKeyword) {
    return Array.isArray(tags) ? tags : []
  }
  return (Array.isArray(tags) ? tags : []).filter((tag) => {
    const name = String(tag?.name || '').toLowerCase()
    const id = String(tag?.id || '').toLowerCase()
    return name.includes(normalizedKeyword) || id.includes(normalizedKeyword)
  })
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
      showSuccessToast(response.message || '修改成功')
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
      message: `确定要删除标签「${tag.name}」吗？删除后将从所有${unit}中移除。`,
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

function toggleSelectAllContent() {
  if (isAllContentSelected.value) {
    selectedContentIds.value = []
    return
  }
  selectedContentIds.value = contentList.value.map(item => item.id)
}

function toggleTagSelection(id) {
  toggleSelection(selectedTagIds, id)
}

async function openBatchTaskSheet() {
  if (selectedContentIds.value.length === 0) {
    return
  }
  await runtimeStore.fetchRuntime()
  showBatchTaskSheet.value = true
}

async function handleBatchTaskAction(action) {
  if (!action || action.disabled) {
    if (action?.reason) {
      showFailToast(action.reason)
    }
    return
  }

  const eligibleIds = Array.isArray(action.eligibleIds) ? action.eligibleIds : []
  if (eligibleIds.length === 0) {
    showFailToast('当前没有可执行的内容')
    return
  }

  try {
    await showConfirmDialog({
      title: action.name,
      message: `确定对 ${eligibleIds.length} 项内容执行“${action.name}”吗？`
    })
  } catch {
    return
  }

  const created = await importTaskStore.createContentTask({
    taskType: action.taskType,
    itemIds: eligibleIds,
  })
  if (created) {
    showBatchTaskSheet.value = false
    selectedContentIds.value = []
  }
}

async function batchAddTags() {
  try {
    const unit = isVideo.value ? '视频' : '漫画'
    await showConfirmDialog({
      title: '确认操作',
      message: `确定为 ${selectedContentIds.value.length} 个${unit}添加 ${selectedTagIds.value.length} 个标签吗？`,
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
      message: `确定从 ${selectedContentIds.value.length} 个${unit}移除 ${selectedTagIds.value.length} 个标签吗？`,
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
  restoreBrowseState()
  await fetchTagList()
  await fetchContentList()
})

watch(contentList, (nextItems) => {
  selectedContentIds.value = keepSelectionWithinItems(
    selectedContentIds.value,
    nextItems,
    (item) => item.id
  )
})

watch([activeTab, currentPage, tagListKeyword, batchTagKeyword], () => {
  persistBrowseState()
})
</script>

<style scoped>
.base-tag-manage {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: transparent;
  padding-bottom: 18px;
}

.nav-add-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid var(--plain-primary-border);
  border-radius: 999px;
  background: var(--plain-btn-bg);
  color: var(--plain-primary-text);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.base-tag-manage :deep(.van-tabs) {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.base-tag-manage :deep(.van-tabs__content) {
  flex: 1;
}

.base-tag-manage :deep(.van-tab__panel) {
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.tag-list {
  margin: 12px;
  padding: 12px;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.tag-list-desktop {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}

.tag-icon {
  margin-right: 8px;
  color: #1989fa;
}

.tag-search-bar {
  margin-bottom: 12px;
  grid-column: 1 / -1;
}

.tag-search-bar :deep(.van-search) {
  padding: 0;
  background: transparent;
}

.tag-search-bar :deep(.van-search__content) {
  border-radius: 999px;
  border: 1px solid var(--border-soft);
  background: var(--surface-2);
}

.swipe-btn {
  height: 100%;
}

.tag-cell-desktop {
  min-height: 72px;
  border-radius: 16px;
  border: 1px solid var(--border-soft);
  background: var(--surface-1);
  box-shadow: none;
  transition:
    transform var(--motion-fast) var(--ease-standard),
    border-color var(--motion-fast) var(--ease-standard),
    box-shadow var(--motion-fast) var(--ease-standard);
}

.tag-cell-desktop:hover {
  transform: translateY(-1px);
  border-color: rgba(47, 116, 255, 0.26);
  box-shadow: 0 16px 32px rgba(12, 24, 43, 0.12);
}

.tag-cell-desktop :deep(.van-cell__right-icon) {
  display: flex;
  align-items: center;
}

.desktop-tag-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.tag-action-btn {
  min-width: 68px;
}

.desktop-tag-arrow {
  color: var(--text-tertiary);
  font-size: 15px;
}

.empty {
  margin: 12px;
  padding: 40px 0;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: var(--surface-2);
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
  margin: 12px;
  padding: 14px;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
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
  color: var(--text-strong);
}

.selected-count {
  font-size: 12px;
  color: #1989fa;
}

.section-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.content-select-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.batch-pagination {
  margin-top: auto;
  background: var(--surface-1);
  padding: 8px 0 12px;
  margin-bottom: 0;
}

.content-select-item {
  position: relative;
  background: var(--surface-1);
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid var(--border-soft);
  transition:
    transform var(--motion-fast) var(--ease-standard),
    border-color var(--motion-fast) var(--ease-standard),
    box-shadow var(--motion-fast) var(--ease-standard);
}

.content-select-item:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.content-select-item.selected {
  border-color: rgba(89, 160, 255, 0.68);
  box-shadow: 0 0 0 2px rgba(89, 160, 255, 0.16);
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
  color: var(--text-tertiary);
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
  background: var(--brand-600);
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

.empty-search-result {
  padding: 8px 0 16px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.batch-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

@media (max-width: 767px) {
  .tag-list {
    margin-top: 8px;
    padding: 10px;
  }

  .nav-add-button span {
    display: none;
  }

  .content-select-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }

  .section-header {
    align-items: flex-start;
    gap: 8px;
  }

  .section-right {
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .batch-actions {
    grid-template-columns: 1fr;
  }
}
</style>

