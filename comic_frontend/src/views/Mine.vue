<template>
  <div class="mine">
    <van-nav-bar title="我的" />
    
    <div class="stats-overview">
      <van-grid :column-num="4" :border="false">
        <van-grid-item icon="photo-o" :text="comicCount + ' 漫画'" />
        <van-grid-item icon="bookmark-o" :text="readCount + ' 已读'" />
        <van-grid-item icon="label-o" :text="tagCount + ' 标签'" />
        <van-grid-item icon="bars" :text="listCount + ' 清单'" />
      </van-grid>
    </div>
    
    <van-cell-group class="mine-menu">
      <van-cell title="我的清单" icon="list-switch-o" to="/lists" is-link />
      <van-cell title="我的收藏" icon="star-o" @click="goToFavorites" is-link />
      <van-cell title="标签管理" icon="tag-o" to="/tags" is-link />
      <van-cell title="系统设置" icon="setting-o" to="/config" is-link />
      <van-cell title="缓存管理" icon="tosend" @click="showCachePanel = true" is-link />
      <van-cell title="导入漫画" icon="add-o" @click="showImportDialog = true" is-link />
      <van-cell title="批量上传" icon="description" @click="showUploadPanel = true" is-link />
    </van-cell-group>
    
    <!-- 缓存管理面板 -->
    <van-popup
      v-model:show="showCachePanel"
      position="bottom"
      round
      :style="{ height: '60%' }"
    >
      <div class="cache-panel">
        <van-nav-bar
          title="缓存管理"
          left-text="关闭"
          @click-left="showCachePanel = false"
        />

        <div class="cache-content">
          <!-- 缓存统计 -->
          <van-cell-group inset class="stats-group">
            <van-cell title="漫画列表" :value="listCacheStatus" />
            <van-cell title="漫画详情" :value="detailCacheCount + ' 个'" />
            <!-- 图片缓存由浏览器控制，无法设置缓存时间
            <van-cell title="图片列表" :value="imagesCacheCount + ' 个'" />
            -->
            <van-cell title="标签列表" :value="tagsCacheStatus" />
          </van-cell-group>

          <!-- 缓存时间设置 -->
          <van-cell-group inset class="settings-group">
            <van-cell title="缓存有效期（分钟，只能设置详情页，无法设置图片列表）">
              <template #value>
                <van-stepper
                  v-model="cacheExpiryMinutes"
                  :min="1"
                  :max="1440"
                  :step="10"
                  @change="saveCacheExpiry"
                />
              </template>
            </van-cell>
            <div class="setting-hint">{{ cacheExpiryHint }}</div>
          </van-cell-group>

          <!-- 操作按钮 -->
          <div class="action-buttons">
            <van-button
              type="danger"
              block
              round
              @click="confirmClearCache"
            >
              清除所有缓存
            </van-button>
          </div>
        </div>
      </div>
    </van-popup>
    
    <div class="about">
      <p class="version">版本 2.0.0</p>
      <p class="copyright">© 2026 自用漫画浏览网站</p>
    </div>
    
    <van-tabbar v-model="active" route>
      <van-tabbar-item icon="home-o" to="/">主页</van-tabbar-item>
      <van-tabbar-item icon="star-o" to="/recommendation">推荐</van-tabbar-item>
      <van-tabbar-item icon="user-o" to="/mine">我的</van-tabbar-item>
    </van-tabbar>
    
    <van-popup v-model:show="showImportDialog" round position="center">
      <div class="import-dialog">
        <h3>在线导入漫画</h3>
        
        <van-radio-group v-model="importType" class="import-options">
          <div class="option-group">
            <div class="option-title">导入方式</div>
            <van-radio name="by_id">通过 ID 导入</van-radio>
            <van-radio name="by_search">通过搜索导入</van-radio>
            <van-radio name="by_favorite">从收藏夹导入</van-radio>
          </div>
        </van-radio-group>
        
        <van-radio-group v-model="importTarget" class="import-options">
          <div class="option-group">
            <div class="option-title">导入目录</div>
            <van-radio name="home">导入主页</van-radio>
            <van-radio name="recommendation">导入推荐页</van-radio>
          </div>
        </van-radio-group>
        
        <van-field
          v-if="importType === 'by_id'"
          v-model="importId"
          label="漫画ID"
          placeholder="请输入漫画ID"
        />
        
        <van-field
          v-if="importType === 'by_search'"
          v-model="importKeyword"
          label="搜索关键词"
          placeholder="请输入搜索关键词"
        />
        
        <van-field
          v-if="importType === 'by_search'"
          v-model="importMaxPages"
          type="number"
          label="最大页数"
          placeholder="默认为1页"
        />
        
        <div class="dialog-buttons">
          <van-button @click="showImportDialog = false">取消</van-button>
          <van-button type="primary" @click="handleOnlineImport" :loading="importing">导入</van-button>
        </div>
      </div>
    </van-popup>
    
    <van-popup 
      v-model:show="showUploadPanel" 
      position="bottom" 
      round 
      :style="{ height: '50%' }"
    >
      <div class="upload-panel">
        <van-nav-bar title="批量上传" left-text="关闭" @click-left="showUploadPanel = false" />
        
        <div class="upload-content">
          <div class="upload-area" @click="triggerFileInput" @dragover.prevent @drop.prevent="handleDrop">
            <van-icon name="add-o" size="40" />
            <p class="upload-hint">点击或拖拽 ZIP 文件到此处</p>
            <p class="upload-tip">支持多个 ZIP 文件同时上传</p>
          </div>
          
          <input 
            ref="fileInput" 
            type="file" 
            accept=".zip" 
            multiple 
            style="display: none" 
            @change="handleFileSelect"
          />
          
          <div v-if="selectedFiles.length > 0" class="selected-files">
            <p class="files-title">已选择 {{ selectedFiles.length }} 个文件:</p>
            <div class="files-list">
              <div v-for="(file, index) in selectedFiles" :key="index" class="file-item">
                <van-icon name="description" />
                <span class="file-name">{{ file.name }}</span>
                <van-icon name="cross" @click="removeFile(index)" />
              </div>
            </div>
          </div>
          
          <van-button 
            type="primary" 
            block 
            :disabled="selectedFiles.length === 0" 
            :loading="uploading"
            @click="handleUpload"
          >
            开始上传
          </van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useComicStore, useCacheStore, useTagStore, useListStore } from '@/stores'
import { comicApi } from '@/api/comic'
import { showSuccessToast, showFailToast, showConfirmDialog, showToast } from 'vant'

const router = useRouter()
const active = ref(1)
const showImportDialog = ref(false)
const showCachePanel = ref(false)
const showUploadPanel = ref(false)
const comicId = ref('')
const comicTitle = ref('')
const importing = ref(false)
const importType = ref('by_id')
const importTarget = ref('home')
const importId = ref('')
const importKeyword = ref('')
const importMaxPages = ref(1)
const cacheExpiryMinutes = ref(30)
const fileInput = ref(null)
const selectedFiles = ref([])
const uploading = ref(false)

const comicStore = useComicStore()
const cacheStore = useCacheStore()
const tagStore = useTagStore()
const listStore = useListStore()

const comicCount = computed(() => comicStore.comics?.length || 0)
const readCount = computed(() => {
  const comics = comicStore.comics || []
  return comics.filter(c => c.current_page > 1).length
})
const tagCount = computed(() => tagStore.tags?.length || 0)
const listCount = computed(() => listStore.lists?.length || 0)

// 缓存状态
const listCacheStatus = computed(() => {
  return cacheStore.listCache ? '已缓存' : '未缓存'
})

const detailCacheCount = computed(() => {
  return Object.keys(cacheStore.detailCache || {}).length
})

const imagesCacheCount = computed(() => {
  return Object.keys(cacheStore.imagesCache || {}).length
})

const tagsCacheStatus = computed(() => {
  return cacheStore.tagsCache ? '已缓存' : '未缓存'
})

const cacheExpiryHint = computed(() => {
  const hours = Math.floor(cacheExpiryMinutes.value / 60)
  const mins = cacheExpiryMinutes.value % 60
  if (hours > 0) {
    return `缓存将在 ${hours}小时${mins > 0 ? mins + '分钟' : ''} 后过期`
  }
  return `缓存将在 ${mins}分钟 后过期`
})

// 保存缓存时间设置
function saveCacheExpiry() {
  localStorage.setItem('cache_expiry_minutes', cacheExpiryMinutes.value.toString())
  showToast(`缓存有效期已设置为 ${cacheExpiryMinutes.value} 分钟`)
}

// 确认清除缓存
function confirmClearCache() {
  showConfirmDialog({
    title: '确认清除缓存',
    message: '清除后需要重新加载数据，是否继续？',
  })
    .then(() => {
      clearAllCache()
    })
    .catch(() => {
      // 取消
    })
}

// 清除所有缓存
function clearAllCache() {
  try {
    // 清除 store 缓存
    cacheStore.clearCache('all')

    // 清除 localStorage 中的缓存数据（保留设置）
    const keysToKeep = ['cache_expiry_minutes', 'vueuse-color-scheme']
    const keysToRemove = []

    for (const key in localStorage) {
      if (localStorage.hasOwnProperty(key) && !keysToKeep.includes(key)) {
        keysToRemove.push(key)
      }
    }

    keysToRemove.forEach(key => localStorage.removeItem(key))

    showSuccessToast('缓存已清除')
    showCachePanel.value = false
  } catch (e) {
    console.error('清除缓存失败:', e)
    showToast('清除缓存失败')
  }
}

// 加载缓存时间设置
function loadCacheExpiry() {
  const saved = localStorage.getItem('cache_expiry_minutes')
  if (saved) {
    cacheExpiryMinutes.value = parseInt(saved, 10) || 30
  }
}

function goToFavorites() {
  router.push('/list/list_favorites')
}

onMounted(async () => {
  loadCacheExpiry()
  await Promise.all([
    comicStore.fetchComics(),
    tagStore.fetchTags(),
    listStore.fetchLists()
  ])
})

const importComic = async () => {
  if (!comicId.value) {
    showFailToast('请输入漫画ID')
    return
  }
  
  importing.value = true
  
  try {
    const response = await comicStore.initComic({
      comic_id: comicId.value,
      title: comicTitle.value || comicId.value
    })
    
    if (response.code === 200) {
      showSuccessToast('导入成功')
      showImportDialog.value = false
      await comicStore.fetchComics()
      comicId.value = ''
      comicTitle.value = ''
    } else {
      showFailToast(response.msg || '导入失败')
    }
  } catch (error) {
    showFailToast('导入失败')
  } finally {
    importing.value = false
  }
}

const handleOnlineImport = async () => {
  if (importType.value === 'by_id' && !importId.value.trim()) {
    showFailToast('请输入漫画ID')
    return
  }
  if (importType.value === 'by_search' && !importKeyword.value.trim()) {
    showFailToast('请输入搜索关键词')
    return
  }
  
  importing.value = true
  
  try {
    const response = await comicApi.onlineImport({
      import_type: importType.value,
      target: importTarget.value,
      comic_id: importId.value.trim(),
      keyword: importKeyword.value.trim(),
      max_pages: importMaxPages.value || 1
    })
    
    if (response.code === 200) {
      const data = response.data
      let message = `导入成功！新增 ${data.imported_count} 部，跳过 ${data.skipped_count} 部`
      
      // 如果导入到主页，显示下载结果
      if (importTarget.value === 'home' && data.downloaded_count !== undefined) {
        message += `，下载成功 ${data.downloaded_count} 部`
        if (data.failed_downloads && data.failed_downloads.length > 0) {
          message += `，下载失败 ${data.failed_downloads.length} 部`
        }
      }
      
      showSuccessToast(message)
      showImportDialog.value = false
      importId.value = ''
      importKeyword.value = ''
      importMaxPages.value = 1
      if (importTarget.value === 'home') {
        await comicStore.fetchComics()
      }
    } else {
      showFailToast(response.msg || '导入失败')
    }
  } catch (error) {
    showFailToast('导入失败：' + (error.message || '未知错误'))
  } finally {
    importing.value = false
  }
}

function triggerFileInput() {
  fileInput.value?.click()
}

function handleFileSelect(event) {
  const files = Array.from(event.target.files || [])
  const zipFiles = files.filter(f => f.name.toLowerCase().endsWith('.zip'))
  
  if (zipFiles.length !== files.length) {
    showToast('只支持 .zip 格式文件')
  }
  
  selectedFiles.value = [...selectedFiles.value, ...zipFiles]
  event.target.value = ''
}

function handleDrop(event) {
  const files = Array.from(event.dataTransfer?.files || [])
  const zipFiles = files.filter(f => f.name.toLowerCase().endsWith('.zip'))
  
  if (zipFiles.length !== files.length) {
    showToast('只支持 .zip 格式文件')
  }
  
  selectedFiles.value = [...selectedFiles.value, ...zipFiles]
}

function removeFile(index) {
  selectedFiles.value.splice(index, 1)
}

async function handleUpload() {
  if (selectedFiles.value.length === 0) return
  
  uploading.value = true
  try {
    const result = await comicApi.batchUpload(selectedFiles.value)
    showSuccessToast(`成功上传 ${result.count} 部漫画`)
    selectedFiles.value = []
    showUploadPanel.value = false
    await comicStore.fetchComics()
  } catch (error) {
    showFailToast(error.message || '上传失败')
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.mine {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 50px;
}

.stats-overview {
  background: #fff;
  padding: 12px 0;
}

.mine-menu {
  margin-top: 10px;
}

.about {
  text-align: center;
  padding: 40px 0;
  color: #999;
}

.version {
  font-size: 14px;
  margin-bottom: 8px;
}

.copyright {
  font-size: 12px;
}

.import-dialog {
  width: 320px;
  padding: 20px;
}

.import-dialog h3 {
  text-align: center;
  margin-bottom: 20px;
}

.import-options {
  margin-bottom: 16px;
}

.option-group {
  margin-bottom: 12px;
}

.option-title {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.dialog-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}

.cache-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.cache-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.stats-group,
.settings-group {
  margin-bottom: 16px;
}

.setting-hint {
  padding: 8px 16px;
  font-size: 12px;
  color: #969799;
  background: #f7f8fa;
}

.action-buttons {
  padding: 16px;
}

.upload-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.upload-content {
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.upload-area {
  border: 2px dashed #ddd;
  border-radius: 8px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
}

.upload-area:hover {
  border-color: #1989fa;
  background: #f0f7ff;
}

.upload-hint {
  margin-top: 12px;
  font-size: 14px;
  color: #333;
}

.upload-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #999;
}

.selected-files {
  flex: 1;
  overflow-y: auto;
}

.files-title {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.files-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f7f8fa;
  border-radius: 4px;
}

.file-name {
  flex: 1;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-item .van-icon-cross {
  cursor: pointer;
  color: #999;
}
</style>
