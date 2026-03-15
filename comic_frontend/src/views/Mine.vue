<template>
  <div class="mine-page">
    <div class="stats-overview">
      <van-grid :column-num="4" :border="false">
        <van-grid-item icon="photo-o" :text="stats.count + ' 内容'" />
        <van-grid-item icon="bookmark-o" :text="stats.read + ' 已读'" />
        <van-grid-item icon="label-o" :text="stats.tags + ' 标签'" />
        <van-grid-item icon="bars" :text="stats.lists + ' 清单'" />
      </van-grid>
    </div>
    
    <van-cell-group class="mine-menu" inset>
      <van-cell title="我的清单" icon="list-switch-o" to="/lists" is-link />
      <van-cell title="我的收藏" icon="star-o" @click="goToFavorites" is-link />
      <van-cell title="回收站" icon="delete-o" to="/trash" is-link />
      <van-cell title="标签管理" icon="tag-o" :to="tagManagePath" is-link />
    </van-cell-group>

    <van-cell-group class="mine-menu" inset>
      <van-cell title="导入内容" icon="add-o" @click="showImportDialog = true" is-link />
      <van-cell title="导入任务" icon="clock-o" to="/import-tasks" is-link>
        <template #value>
          <van-tag v-if="activeTaskCount > 0" type="primary" round>
            {{ activeTaskCount }}
          </van-tag>
        </template>
      </van-cell>
      <van-cell v-if="!isVideoMode" title="批量上传" icon="description" @click="showUploadPanel = true" is-link />
    </van-cell-group>

    <van-cell-group class="mine-menu" inset>
      <van-cell title="系统设置" icon="setting-o" to="/config" is-link />
      <van-cell title="缓存管理" icon="tosend" @click="showCachePanel = true" is-link />
    </van-cell-group>
    
    <div class="about">
      <p class="version">版本 2.0.0</p>
      <p class="copyright">© 2026 Ultimate Web</p>
    </div>
    
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
            <van-cell title="列表缓存" :value="listCacheStatus" />
            <van-cell title="详情缓存" :value="detailCacheCount + ' 个'" />
            <van-cell title="标签缓存" :value="tagsCacheStatus" />
          </van-cell-group>

          <!-- 缓存时间设置 -->
          <van-cell-group inset class="settings-group">
            <van-cell title="缓存有效期（分钟）">
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
    
    <!-- 导入弹窗 (保持原有逻辑) -->
    <van-popup v-model:show="showImportDialog" round position="center">
      <div class="import-dialog">
        <h3>{{ isVideoMode ? '导入视频' : '导入漫画' }}</h3>
        
        <van-radio-group v-model="importType" class="import-options">
          <div class="option-group">
            <div class="option-title">导入方式</div>
            <van-radio name="by_id">通过 ID</van-radio>
            <van-radio name="by_search">通过搜索</van-radio>
            <van-radio name="by_list">批量文件</van-radio>
          </div>
        </van-radio-group>
        
        <van-radio-group v-model="importTarget" class="import-options">
          <div class="option-group">
            <div class="option-title">导入位置</div>
            <van-radio name="home">本地库</van-radio>
            <van-radio name="recommendation">预览库</van-radio>
          </div>
        </van-radio-group>
        
        <van-radio-group v-model="importPlatform" class="import-options">
          <div class="option-group">
            <div class="option-title">来源平台</div>
            <van-radio v-if="!isVideoMode" name="JM">JMComic</van-radio>
            <van-radio v-if="!isVideoMode" name="PK">Picacomic</van-radio>
            <van-radio v-if="isVideoMode" name="JAVDB">JavDB</van-radio>
          </div>
        </van-radio-group>
        
        <van-field
          v-if="importType === 'by_id'"
          v-model="importId"
          label="ID"
          placeholder="请输入内容ID"
        />
        
        <van-field
          v-if="importType === 'by_list'"
          :model-value="importFile ? importFile.name : ''"
          label="文件"
          placeholder="选择txt文件"
          readonly
          @click="triggerImportFileInput"
        />
        
        <input 
          ref="importFileInput" 
          type="file" 
          accept=".txt" 
          style="display: none" 
          @change="handleImportFileSelect"
        />
        
        <van-field
          v-if="importType === 'by_search'"
          v-model="importKeyword"
          label="关键词"
          placeholder="请输入搜索关键词"
        />
        
        <div class="dialog-buttons">
          <van-button @click="showImportDialog = false">取消</van-button>
          <van-button type="primary" @click="handleOnlineImport" :loading="importing">导入</van-button>
        </div>
      </div>
    </van-popup>
    
    <!-- 批量上传面板 (漫画独有) -->
    <van-popup 
      v-if="!isVideoMode"
      v-model:show="showUploadPanel" 
      position="bottom" 
      round 
      :style="{ height: '50%' }"
    >
      <div class="upload-panel">
        <van-nav-bar title="批量上传" left-text="关闭" @click-left="showUploadPanel = false" />
        <div class="upload-content">
          <div class="upload-area" @click="triggerFileInput">
            <van-icon name="add-o" size="40" />
            <p class="upload-hint">点击选择 ZIP 文件</p>
          </div>
          <input 
            ref="fileInput" 
            type="file" 
            accept=".zip" 
            multiple 
            style="display: none" 
            @change="handleFileSelect"
          />
          <!-- Simplified upload UI -->
          <van-button 
            type="primary" 
            block 
            :disabled="selectedFiles.length === 0" 
            :loading="uploading"
            @click="handleUpload"
            style="margin-top: 20px"
          >
            开始上传 ({{ selectedFiles.length }})
          </van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useComicStore, useVideoStore, useCacheStore, useTagStore, useListStore, useModeStore, useImportTaskStore } from '@/stores'
import { comicApi, authorApi, recommendationApi, videoApi } from '@/api'
import { showSuccessToast, showFailToast, showConfirmDialog, showToast } from 'vant'

const router = useRouter()
const modeStore = useModeStore()
const comicStore = useComicStore()
const videoStore = useVideoStore()
const cacheStore = useCacheStore()
const tagStore = useTagStore()
const listStore = useListStore()
const importTaskStore = useImportTaskStore()

const isVideoMode = computed(() => modeStore.isVideoMode)

// State
const showImportDialog = ref(false)
const showCachePanel = ref(false)
const showUploadPanel = ref(false)
const cacheExpiryMinutes = ref(30)
const importType = ref('by_id')
const importTarget = ref('home')
const importPlatform = ref('JM')
const importId = ref('')
const importKeyword = ref('')
const importFile = ref(null)
const importing = ref(false)
const uploading = ref(false)
const selectedFiles = ref([])
const importFileInput = ref(null)
const fileInput = ref(null)

// Stats
const stats = computed(() => {
  if (isVideoMode.value) {
    return {
      count: videoStore.videoList.length,
      read: 0, // Video read count logic if exists
      tags: tagStore.videoTags.length,
      lists: listStore.lists.length
    }
  } else {
    return {
      count: comicStore.comics.length,
      read: comicStore.comics.filter(c => c.current_page > 1).length,
      tags: tagStore.tags.length,
      lists: listStore.lists.length
    }
  }
})

const activeTaskCount = computed(() => importTaskStore.activeTaskCount)
const tagManagePath = computed(() => isVideoMode.value ? '/video-tags' : '/tags')

// Cache Logic (Reuse)
const listCacheStatus = computed(() => cacheStore.listCache ? '已缓存' : '未缓存')
const detailCacheCount = computed(() => Object.keys(cacheStore.detailCache || {}).length)
const tagsCacheStatus = computed(() => cacheStore.tagsCache ? '已缓存' : '未缓存')
const cacheExpiryHint = computed(() => `缓存将在 ${cacheExpiryMinutes.value} 分钟后过期`)

function saveCacheExpiry() {
  localStorage.setItem('cache_expiry_minutes', cacheExpiryMinutes.value.toString())
  showToast('设置已保存')
}

function confirmClearCache() {
  showConfirmDialog({ title: '确认清除', message: '确定清除所有缓存吗？' })
    .then(clearAllCache)
}

async function clearAllCache() {
  cacheStore.clearCache('all')
  showSuccessToast('缓存已清除')
  showCachePanel.value = false
}

function goToFavorites() {
  const favoritesListId = isVideoMode.value ? 'list_favorites_video' : 'list_favorites_comic'
  router.push(`/list/${favoritesListId}`)
}

// Import Logic
function triggerImportFileInput() {
  importFileInput.value?.click()
}

function handleImportFileSelect(event) {
  const file = event.target.files[0]
  if (file) importFile.value = file
}

function normalizeImportId(rawId, platform = '') {
  let id = String(rawId || '').trim()
  if (!id) return ''

  const normalizedPlatform = String(platform || '').toUpperCase()
  if (normalizedPlatform) {
    const platformPrefixRegex = new RegExp(`^${normalizedPlatform}_?`, 'i')
    id = id.replace(platformPrefixRegex, '')
  }

  return id.trim()
}

async function parseIdsFromFile(file, platform = '') {
  if (!file) {
    throw new Error('请先选择导入文件')
  }

  const content = await file.text()
  const ids = content
    .split(/[\r\n,\s]+/)
    .map(item => normalizeImportId(item, platform))
    .filter(Boolean)

  return Array.from(new Set(ids))
}

async function handleComicImport() {
  const params = {
    import_type: importType.value,
    target: importTarget.value,
    platform: importPlatform.value,
    comic_id: normalizeImportId(importId.value, importPlatform.value),
    keyword: (importKeyword.value || '').trim()
  }

  if (importType.value === 'by_id' && !params.comic_id) {
    throw new Error('请输入漫画ID')
  }

  if (importType.value === 'by_search' && !params.keyword) {
    throw new Error('请输入搜索关键词')
  }

  if (importType.value === 'by_list') {
    const comicIds = await parseIdsFromFile(importFile.value, importPlatform.value)
    if (comicIds.length === 0) {
      throw new Error('文件中没有可导入的ID')
    }
    params.comic_ids = comicIds
    params.comic_id = ''
    params.keyword = ''
  }

  await importTaskStore.createImportTask(params)
  showSuccessToast('任务已创建')
}

async function handleVideoImport() {
  const target = importTarget.value
  const defaultPlatform = (importPlatform.value || 'JAVDB').toLowerCase()
  let successCount = 0
  let failedCount = 0

  if (importType.value === 'by_id') {
    const videoId = normalizeImportId(importId.value, importPlatform.value)
    if (!videoId) {
      throw new Error('请输入视频ID')
    }
    await videoApi.thirdPartyImport(videoId, target, defaultPlatform)
    showSuccessToast('导入成功')
    return
  }

  if (importType.value === 'by_search') {
    const keyword = (importKeyword.value || '').trim()
    if (!keyword) {
      throw new Error('请输入搜索关键词')
    }

    const searchRes = await videoApi.thirdPartySearch(keyword, 1, defaultPlatform)
    const videos = searchRes?.data?.videos || []
    if (videos.length === 0) {
      throw new Error('未找到可导入的视频')
    }

    for (const item of videos) {
      const itemId = normalizeImportId(item.video_id || item.id || '', item.platform || importPlatform.value)
      if (!itemId) continue
      const itemPlatform = (item.platform || defaultPlatform).toLowerCase()
      try {
        await videoApi.thirdPartyImport(itemId, target, itemPlatform)
        successCount += 1
      } catch (e) {
        failedCount += 1
      }
    }
  } else if (importType.value === 'by_list') {
    const videoIds = await parseIdsFromFile(importFile.value, importPlatform.value)
    if (videoIds.length === 0) {
      throw new Error('文件中没有可导入的ID')
    }

    for (const videoId of videoIds) {
      try {
        await videoApi.thirdPartyImport(videoId, target, defaultPlatform)
        successCount += 1
      } catch (e) {
        failedCount += 1
      }
    }
  } else {
    throw new Error('当前模式不支持该导入方式')
  }

  if (successCount === 0) {
    throw new Error('导入失败')
  }
  showSuccessToast(`导入完成：成功 ${successCount}，失败 ${failedCount}`)
}

async function handleOnlineImport() {
  importing.value = true
  try {
    if (isVideoMode.value) {
      await handleVideoImport()
    } else {
      await handleComicImport()
    }
    showImportDialog.value = false
  } catch (e) {
    showFailToast(e?.message || '操作失败')
  } finally {
    importing.value = false
  }
}

// Upload Logic
function triggerFileInput() {
  fileInput.value?.click()
}

function handleFileSelect(event) {
  selectedFiles.value = Array.from(event.target.files)
}

async function handleUpload() {
  uploading.value = true
  try {
    await comicApi.batchUpload(selectedFiles.value)
    showSuccessToast('上传成功')
    showUploadPanel.value = false
  } catch (e) {
    showFailToast('上传失败')
  } finally {
    uploading.value = false
  }
}

// Init
onMounted(async () => {
  // Initial data fetch based on mode
  if (isVideoMode.value) {
    await videoStore.fetchList()
    await tagStore.fetchTags('video')
  } else {
    await comicStore.fetchComics()
    await tagStore.fetchTags('comic')
  }
  await listStore.fetchLists()
  await importTaskStore.fetchTasks()
})

watch(() => modeStore.currentMode, () => {
  importPlatform.value = isVideoMode.value ? 'JAVDB' : 'JM'
})
</script>

<style scoped>
.mine-page {
  padding-bottom: 80px;
}

.stats-overview {
  background: #fff;
  padding: 20px 0;
  margin-bottom: 12px;
}

.mine-menu {
  margin-bottom: 12px;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}

.about {
  text-align: center;
  padding: 40px 0;
  color: #999;
}

.version {
  font-size: 14px;
  margin-bottom: 4px;
}

.copyright {
  font-size: 12px;
}

/* Panels & Dialogs */
.cache-panel, .upload-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.cache-content, .upload-content {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
}

.import-dialog {
  width: 300px;
  padding: 20px;
}

.import-dialog h3 {
  text-align: center;
  margin-bottom: 20px;
}

.import-options {
  margin-bottom: 16px;
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

.upload-area {
  border: 2px dashed #ddd;
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
}
</style>
