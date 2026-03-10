<template>
  <div class="list-manage">
    <van-nav-bar
      title="清单管理"
      left-text="返回"
      left-arrow
      @click-left="$router.back()"
    >
      <template #right>
        <div class="nav-right">
          <van-icon name="down" size="18" class="nav-icon" @click="showImportDialog = true" />
          <van-icon name="plus" size="18" class="nav-icon" @click="showCreateDialog = true" />
        </div>
      </template>
    </van-nav-bar>
    
    <van-loading v-if="loading" class="loading-center" />
    
    <van-empty v-else-if="lists.length === 0" description="暂无清单" />
    
    <van-cell-group v-else inset class="list-group">
      <van-swipe-cell v-for="list in lists" :key="list.id">
        <van-cell
          :title="list.name"
          :label="list.desc || '暂无描述'"
          is-link
          @click="goToDetail(list.id)"
        >
          <template #value>
            <div class="list-counts">
              <van-button v-if="list.platform" size="small" type="success" text="同步" class="sync-btn-inline" @click.stop="syncList(list)" />
              <van-badge v-if="list.content_type === 'comic'" :content="list.comic_count" :show-zero="false" class="count-badge">
                <van-icon name="photo-o" size="16" />
              </van-badge>
              <van-badge v-if="list.content_type === 'video'" :content="list.video_count" :show-zero="false" class="count-badge">
                <van-icon name="video-o" size="16" />
              </van-badge>
            </div>
          </template>
          <template #icon>
            <van-icon v-if="list.is_default" name="star" color="#ffd21e" size="16" class="list-icon" />
            <van-icon v-else name="list-switch" size="16" class="list-icon" />
          </template>
        </van-cell>
        <template #right v-if="!list.is_default">
          <van-button square type="primary" text="编辑" class="edit-btn" @click="openEditDialog(list)" />
          <van-button square type="danger" text="删除" @click="confirmDelete(list)" />
        </template>
      </van-swipe-cell>
    </van-cell-group>
    
    <van-popup v-model:show="showCreateDialog" round position="center">
      <div class="dialog-content">
        <h3>新建清单</h3>
        <van-field v-model="newListName" label="清单名称" placeholder="请输入清单名称" />
        <van-field v-model="newListDesc" label="清单描述" placeholder="请输入清单描述（可选）" />
        <div class="dialog-buttons">
          <van-button @click="showCreateDialog = false">取消</van-button>
          <van-button type="primary" @click="createList" :loading="creating">确定</van-button>
        </div>
      </div>
    </van-popup>
    
    <van-popup v-model:show="showEditDialog" round position="center">
      <div class="dialog-content">
        <h3>编辑清单</h3>
        <van-field v-model="editListName" label="清单名称" placeholder="请输入清单名称" />
        <van-field v-model="editListDesc" label="清单描述" placeholder="请输入清单描述（可选）" />
        <div class="dialog-buttons">
          <van-button @click="showEditDialog = false">取消</van-button>
          <van-button type="primary" @click="updateList" :loading="updating">确定</van-button>
        </div>
      </div>
    </van-popup>
    
    <van-popup v-model:show="showImportDialog" round position="bottom" :style="{ height: '80%' }">
      <div class="import-dialog">
        <div class="import-header">
          <h3>导入清单</h3>
          <van-icon name="cross" size="20" @click="showImportDialog = false" />
        </div>
        
        <div class="import-content">
          <div class="import-step" v-if="currentStep === 1">
            <h4>选择平台</h4>
            <van-radio-group v-model="selectedPlatform">
              <van-cell-group inset>
                <van-cell v-for="platform in availablePlatforms" :key="platform.value" :title="platform.label" clickable @click="selectedPlatform = platform.value">
                  <template #right-icon>
                    <van-radio :name="platform.value" />
                  </template>
                </van-cell>
              </van-cell-group>
            </van-radio-group>
            <div class="step-buttons">
              <van-button type="primary" block @click="goToStep2" :disabled="!selectedPlatform">下一步</van-button>
            </div>
          </div>
          
          <div class="import-step" v-if="currentStep === 2">
            <div class="step-header">
              <van-icon name="arrow-left" size="20" @click="currentStep = 1" />
              <h4>选择导入方式</h4>
            </div>
            <van-radio-group v-model="importMethod">
              <van-cell-group inset>
                <van-cell title="通过清单编号导入" clickable @click="importMethod = 'id'">
                  <template #right-icon>
                    <van-radio name="id" />
                  </template>
                </van-cell>
                <van-cell title="从我的清单导入" clickable @click="importMethod = 'mylist'">
                  <template #right-icon>
                    <van-radio name="mylist" />
                  </template>
                </van-cell>
              </van-cell-group>
            </van-radio-group>
            
            <div v-if="importMethod === 'id'" class="input-section">
              <van-field v-model="listIdInput" label="清单编号" placeholder="请输入清单编号" />
            </div>
            
            <div v-if="importMethod === 'mylist'" class="list-section">
              <van-loading v-if="loadingPlatformLists" class="loading-small" />
              <van-empty v-else-if="platformLists.length === 0" description="暂无清单" />
              <van-cell-group v-else inset>
                <van-cell 
                  v-for="list in platformLists" 
                  :key="list.list_id"
                  :title="list.list_name"
                  :label="`${list.video_count} 部影片`"
                  clickable
                  :is-link="true"
                  :class="{ 'selected': selectedPlatformList?.list_id === list.list_id }"
                  @click="selectPlatformList(list)"
                >
                  <template #icon>
                    <van-icon 
                      v-if="selectedPlatformList?.list_id === list.list_id" 
                      name="success" 
                      color="#07c160" 
                    />
                  </template>
                </van-cell>
              </van-cell-group>
            </div>
            
            <div class="step-buttons">
              <van-button type="primary" block @click="goToStep3" :disabled="!canGoStep3">下一步</van-button>
            </div>
          </div>
          
          <div class="import-step" v-if="currentStep === 3">
            <div class="step-header">
              <van-icon name="arrow-left" size="20" @click="currentStep = 2" />
              <h4>确认导入</h4>
            </div>
            
            <div class="confirm-section">
              <van-cell-group inset>
                <van-cell title="平台" :value="getPlatformLabel(selectedPlatform)" />
                <van-cell title="清单" :value="selectedPlatformList?.list_name || listIdInput" />
                <van-cell title="内容数量" :value="selectedPlatformList?.video_count || '未知'" />
                <van-cell title="目标清单" :value="`远程跟踪：${selectedPlatformList?.list_name || listIdInput}`" />
              </van-cell-group>
              
              <h5 class="section-title">选择导入位置</h5>
              <van-radio-group v-model="importSource">
                <van-cell-group inset>
                  <van-cell title="导入本地库" clickable @click="importSource = 'local'">
                    <template #right-icon>
                      <van-radio name="local" />
                    </template>
                  </van-cell>
                  <van-cell title="导入预览库" clickable @click="importSource = 'preview'">
                    <template #right-icon>
                      <van-radio name="preview" />
                    </template>
                  </van-cell>
                </van-cell-group>
              </van-radio-group>
            </div>
            
            <div class="step-buttons">
              <van-button type="primary" block @click="doImport" :loading="importing">开始导入</van-button>
            </div>
          </div>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useListStore, useModeStore } from '@/stores'
import { showConfirmDialog, showSuccessToast, showFailToast } from 'vant'
import listApi from '@/api/list'

const router = useRouter()
const listStore = useListStore()
const modeStore = useModeStore()

const loading = ref(false)
const creating = ref(false)
const updating = ref(false)
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const newListName = ref('')
const newListDesc = ref('')
const editListName = ref('')
const editListDesc = ref('')
const editingListId = ref('')

const lists = ref([])

const currentContentType = computed(() => modeStore.isVideoMode ? 'video' : 'comic')

const showImportDialog = ref(false)
const currentStep = ref(1)
const selectedPlatform = ref('')
const importMethod = ref('')
const listIdInput = ref('')
const platformLists = ref([])
const loadingPlatformLists = ref(false)
const selectedPlatformList = ref(null)
const importSource = ref('local')
const importing = ref(false)
const syncing = ref(false)

const availablePlatforms = computed(() => {
  if (currentContentType.value === 'video') {
    return [{ label: 'JAVDB', value: 'JAVDB' }]
  } else {
    return [
      { label: 'JMComic', value: 'JM' },
      { label: 'PK', value: 'PK' }
    ]
  }
})

const canGoStep3 = computed(() => {
  if (importMethod.value === 'id') {
    return listIdInput.value.trim() !== ''
  } else if (importMethod.value === 'mylist') {
    return selectedPlatformList.value !== null
  }
  return false
})

async function loadLists() {
  loading.value = true
  await listStore.fetchLists(currentContentType.value)
  lists.value = listStore.lists
  console.log('清单列表数据:', lists.value)
  loading.value = false
}

function goToDetail(listId) {
  router.push(`/list/${listId}`)
}

function openEditDialog(list) {
  editingListId.value = list.id
  editListName.value = list.name
  editListDesc.value = list.desc || ''
  showEditDialog.value = true
}

async function createList() {
  if (!newListName.value.trim()) {
    showFailToast('请输入清单名称')
    return
  }
  
  creating.value = true
  const result = await listStore.createList(newListName.value.trim(), newListDesc.value.trim(), currentContentType.value)
  creating.value = false
  
  if (result) {
    showCreateDialog.value = false
    newListName.value = ''
    newListDesc.value = ''
    await loadLists()
  }
}

async function updateList() {
  if (!editListName.value.trim()) {
    showFailToast('请输入清单名称')
    return
  }
  
  updating.value = true
  const result = await listStore.updateList(
    editingListId.value,
    editListName.value.trim(),
    editListDesc.value.trim(),
    currentContentType.value
  )
  updating.value = false
  
  if (result) {
    showEditDialog.value = false
    await loadLists()
  }
}

async function confirmDelete(list) {
  showConfirmDialog({
    title: '删除清单',
    message: `确定要删除清单「${list.name}」吗？清单内的内容不会被删除。`,
  })
    .then(async () => {
      const result = await listStore.deleteList(list.id, currentContentType.value)
      if (result) {
        await loadLists()
      }
    })
    .catch(() => {})
}

function getPlatformLabel(platform) {
  const p = availablePlatforms.value.find(p => p.value === platform)
  return p ? p.label : platform
}

watch(showImportDialog, (val) => {
  if (val) {
    resetImportDialog()
  }
})

watch(importMethod, async (val) => {
  if (val === 'mylist') {
    await loadPlatformLists()
  }
})

function resetImportDialog() {
  currentStep.value = 1
  selectedPlatform.value = ''
  importMethod.value = ''
  listIdInput.value = ''
  platformLists.value = []
  selectedPlatformList.value = null
  importSource.value = 'local'
}

async function loadPlatformLists() {
  if (!selectedPlatform.value) return
  
  loadingPlatformLists.value = true
  try {
    const res = await listApi.getPlatformUserLists(selectedPlatform.value)
    if (res.code === 200) {
      platformLists.value = res.data.lists || []
    } else {
      showFailToast(res.msg || '获取清单失败')
    }
  } catch (e) {
    showFailToast('获取清单失败')
  } finally {
    loadingPlatformLists.value = false
  }
}

function selectPlatformList(list) {
  selectedPlatformList.value = list
}

function goToStep2() {
  if (!selectedPlatform.value) return
  currentStep.value = 2
}

function goToStep3() {
  if (!canGoStep3.value) return
  
  if (importMethod.value === 'id' && !selectedPlatformList.value) {
    selectedPlatformList.value = {
      list_id: listIdInput.value.trim(),
      list_name: listIdInput.value.trim()
    }
  }
  
  currentStep.value = 3
}

async function doImport() {
  if (!selectedPlatformList.value) {
    showFailToast('请选择清单')
    return
  }
  
  importing.value = true
  try {
    const res = await listApi.importPlatformList(
      selectedPlatform.value,
      selectedPlatformList.value.list_id,
      selectedPlatformList.value.list_name,
      importSource.value
    )
    
    if (res.code === 200) {
      showSuccessToast(res.msg || '导入成功')
      showImportDialog.value = false
      await loadLists()
    } else {
      showFailToast(res.msg || '导入失败')
    }
  } catch (e) {
    showFailToast('导入失败')
  } finally {
    importing.value = false
  }
}

async function syncList(list) {
  try {
    await showConfirmDialog({
      title: '同步清单',
      message: `确定要同步清单"${list.name}"吗？\n\n将从网络侧获取最新内容，新增的内容将被导入到本地。`
    })
  } catch {
    return
  }
  
  syncing.value = true
  try {
    const res = await listApi.syncPlatformList(list.id)
    
    if (res.code === 200) {
      const data = res.data
      let message = res.msg || '同步成功'
      if (data && data.imported_count !== undefined) {
        message = `同步成功，新增 ${data.imported_count} 个，跳过 ${data.skipped_count} 个`
      }
      showSuccessToast(message)
      await loadLists()
    } else {
      showFailToast(res.msg || '同步失败')
    }
  } catch (e) {
    console.error(e)
    showFailToast('同步失败')
  } finally {
    syncing.value = false
  }
}

onMounted(() => {
  loadLists()
})
</script>

<style scoped>
.list-manage {
  min-height: 100vh;
  background: #f5f5f5;
}

.loading-center {
  display: flex;
  justify-content: center;
  padding-top: 100px;
}

.list-group {
  margin-top: 12px;
}

.list-icon {
  margin-right: 8px;
}

.list-counts {
  display: flex;
  gap: 8px;
  align-items: center;
}

.count-badge {
  display: flex;
  align-items: center;
  gap: 4px;
}

.sync-btn-inline {
  margin-right: 8px;
}

.edit-btn,
.sync-btn {
  width: 60px;
}

.nav-right {
  display: flex;
  gap: 16px;
  align-items: center;
}

.nav-icon {
  cursor: pointer;
}

.dialog-content {
  width: 300px;
  padding: 20px;
}

.dialog-content h3 {
  text-align: center;
  margin-bottom: 20px;
}

.dialog-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}

.import-dialog {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.import-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: white;
  border-bottom: 1px solid #eee;
}

.import-header h3 {
  margin: 0;
  font-size: 18px;
}

.import-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.import-step h4 {
  margin-top: 0;
  margin-bottom: 16px;
  font-size: 16px;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.step-header h4 {
  margin: 0;
}

.step-header .van-icon {
  cursor: pointer;
}

.input-section,
.list-section {
  margin-top: 16px;
  margin-bottom: 16px;
}

.loading-small {
  display: flex;
  justify-content: center;
  padding: 20px;
}

.confirm-section {
  margin-bottom: 20px;
}

.section-title {
  font-size: 14px;
  color: #666;
  margin: 20px 0 12px;
  padding-left: 12px;
}

.step-buttons {
  margin-top: 24px;
}

.list-section .selected {
  background-color: #e8f9ef;
}

.list-section .selected .van-cell__title {
  color: #07c160;
  font-weight: 500;
}
</style>
