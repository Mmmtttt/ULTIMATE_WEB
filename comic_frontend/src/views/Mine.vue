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
      <van-cell title="数据同步" icon="share-o" to="/sync" is-link />
      <van-cell title="存储管理" icon="tosend" @click="showCachePanel = true" is-link />
    </van-cell-group>
    
    <div class="about">
      <p class="version">版本 2.0.0</p>
      <p class="copyright">© 2026 Ultimate Web </p>
      <p><span class="mmmtttt">github@Mmmtttt</span></p>
    </div>
    
    <!-- 存储管理面板 -->
    <van-popup
      v-model:show="showCachePanel"
      position="bottom"
      round
      :style="{ height: '55%' }"
    >
      <div class="cache-panel">
        <van-nav-bar
          title="存储管理"
          left-text="关闭"
          @click-left="showCachePanel = false"
        />

        <div class="cache-content">
          <!-- 存储信息 -->
          <van-cell-group inset class="cache-info-group">
            <van-cell title="data 目录总存储" :value="cacheInfo.data_storage.size_mb + ' MB'">
              <template #label>
                <span class="cache-desc">包含 data 目录下所有文件与子目录</span>
              </template>
            </van-cell>
            <van-cell title="数据缓存" :value="cacheInfo.cache.size_mb + ' MB'">
              <template #label>
                <span class="cache-desc">订阅页封面和数据临时缓存</span>
              </template>
            </van-cell>
            <van-cell title="漫画预览页缓存" :value="cacheInfo.comic_preview_cache.size_mb + ' MB'">
              <template #label>
                <span class="cache-desc">漫画预览页相关缓存资源</span>
              </template>
            </van-cell>
            <van-cell title="视频预览页缓存" :value="cacheInfo.video_preview_page_cache.size_mb + ' MB'">
              <template #label>
                <span class="cache-desc">视频预览图与预览视频本地缓存</span>
              </template>
            </van-cell>
          </van-cell-group>

          <!-- 清除选项 -->
          <van-cell-group inset class="clear-options-group">
            <van-cell title="清除数据缓存" is-link @click="confirmClearCache('cache')" />
            <van-cell title="清除漫画预览页缓存" is-link @click="confirmClearCache('comic_preview_cache')" />
            <van-cell title="清除视频预览页缓存" is-link @click="confirmClearCache('video_preview_page_cache')" />
            <van-cell title="清除所有缓存" is-link @click="confirmClearCache('all')" />
          </van-cell-group>
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
            <van-radio name="by_id">{{ isVideoMode ? '通过 code' : '通过 ID' }}</van-radio>
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
          :label="isVideoMode ? 'Code' : 'ID'"
          :placeholder="isVideoMode ? '请输入视频 code（如 ARBB-048）' : '请输入内容ID'"
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
import { comicApi, authorApi, recommendationApi, configApi } from '@/api'
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
const importType = ref('by_id')
const importTarget = ref('home')
const importPlatform = ref('JM')
const importId = ref('')
const importFile = ref(null)
const importing = ref(false)
const uploading = ref(false)
const selectedFiles = ref([])
const importFileInput = ref(null)
const fileInput = ref(null)

// Cache Info
const cacheInfo = ref({
  data_storage: { size_mb: 0, file_count: 0 },
  cache: { size_mb: 0, file_count: 0 },
  comic_preview_cache: { size_mb: 0, file_count: 0 },
  video_preview_page_cache: { size_mb: 0, file_count: 0 }
})

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

// Cache Logic
async function loadCacheInfo() {
  try {
    const res = await configApi.getCacheInfo()
    if (res.code === 200 && res.data) {
      const recommendationFallback = res.data.recommendation_cache || { size_mb: 0, file_count: 0 }
      cacheInfo.value = {
        data_storage: res.data.data_storage || { size_mb: 0, file_count: 0 },
        cache: res.data.cache || { size_mb: 0, file_count: 0 },
        comic_preview_cache: res.data.comic_preview_cache || recommendationFallback,
        video_preview_page_cache: res.data.video_preview_page_cache || { size_mb: 0, file_count: 0 }
      }
    }
  } catch (e) {
    console.error('加载缓存信息失败', e)
  }
}

function confirmClearCache(cacheType) {
  const messages = {
    'cache': '确定清除数据缓存吗？',
    'comic_preview_cache': '确定清除漫画预览页缓存吗？',
    'video_preview_page_cache': '确定清除视频预览页缓存吗？这会清空预览库中本地预览资源字段。',
    'all': '确定清除所有缓存吗？'
  }
  showConfirmDialog({ title: '确认清除', message: messages[cacheType] || '确定清除缓存吗？' })
    .then(() => clearCache(cacheType))
}

async function clearCache(cacheType) {
  try {
    const res = await configApi.clearSpecificCache(cacheType)
    if (res.code === 200) {
      const localFieldCount = Number(res?.data?.preview_local_fields?.removed_field_count || 0)
      const extraText = localFieldCount > 0 ? `，清理预览库本地字段 ${localFieldCount} 个` : ''
      showSuccessToast(`缓存已清除，释放 ${res.data.freed_size_mb} MB${extraText}`)
      await loadCacheInfo()
    }
  } catch (e) {
    showFailToast('清除缓存失败')
  }
}

// Watch showCachePanel to load info when opened
watch(showCachePanel, (newVal) => {
  if (newVal) {
    loadCacheInfo()
  }
})

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

function normalizeVideoCode(rawCode) {
  return String(rawCode || '').trim()
}

function canonicalizeVideoCode(rawCode) {
  return normalizeVideoCode(rawCode).replace(/-/g, '').toUpperCase()
}

async function parseVideoCodesFromFile(file) {
  if (!file) {
    throw new Error('请先选择导入文件')
  }

  const content = await file.text()
  const uniqueCodes = new Map()

  content
    .split(/[\r\n,\s]+/)
    .map(item => normalizeVideoCode(item))
    .filter(Boolean)
    .forEach(code => {
      const canonical = canonicalizeVideoCode(code)
      if (!canonical || uniqueCodes.has(canonical)) return
      uniqueCodes.set(canonical, code)
    })

  return Array.from(uniqueCodes.values())
}

async function handleComicImport() {
  const params = {
    import_type: importType.value,
    target: importTarget.value,
    platform: importPlatform.value,
    comic_id: normalizeImportId(importId.value, importPlatform.value)
  }

  if (importType.value === 'by_id' && !params.comic_id) {
    throw new Error('请输入漫画ID')
  }

  if (importType.value === 'by_list') {
    const comicIds = await parseIdsFromFile(importFile.value, importPlatform.value)
    if (comicIds.length === 0) {
      throw new Error('文件中没有可导入的ID')
    }
    params.comic_ids = comicIds
    params.comic_id = ''
  } else if (importType.value !== 'by_id') {
    throw new Error('当前模式不支持该导入方式')
  }

  await importTaskStore.createImportTask(params)
  showSuccessToast('任务已创建')
}

async function handleVideoImport() {
  const target = importTarget.value
  const defaultPlatform = String(importPlatform.value || 'JAVDB').toUpperCase()

  if (importType.value === 'by_id') {
    const videoCode = normalizeVideoCode(importId.value)
    if (!videoCode) {
      throw new Error('请输入视频 code')
    }
    const created = await importTaskStore.createImportTask({
      import_type: 'by_id',
      target,
      platform: defaultPlatform,
      comic_id: videoCode,
      content_type: 'video'
    })
    if (!created) {
      throw new Error('创建导入任务失败')
    }
    showSuccessToast('任务已创建')
    return
  }

  if (importType.value === 'by_list') {
    const videoCodes = await parseVideoCodesFromFile(importFile.value)
    if (videoCodes.length === 0) {
      throw new Error('文件中没有可导入的 code')
    }
    const created = await importTaskStore.createImportTask({
      import_type: 'by_list',
      target,
      platform: defaultPlatform,
      comic_ids: videoCodes,
      content_type: 'video'
    })
    if (!created) {
      throw new Error('创建导入任务失败')
    }
    showSuccessToast('任务已创建')
  } else {
    throw new Error('当前模式不支持该导入方式')
  }
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
  background: var(--surface-2);
  padding: 20px 0;
  margin-bottom: 12px;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
}

.stats-overview :deep(.van-grid-item__content) {
  background: transparent;
  color: var(--text-primary);
}

.stats-overview :deep(.van-grid-item__text) {
  color: var(--text-secondary);
}

.stats-overview :deep(.van-icon) {
  color: var(--brand-600);
}

.stats-overview :deep(.van-grid-item__icon) {
  color: var(--brand-600);
}

.mine-menu {
  margin-bottom: 12px;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  overflow: hidden;
}

.about {
  text-align: center;
  padding: 40px 0;
  color: var(--text-tertiary);
}

.version {
  font-size: 14px;
  margin-bottom: 4px;
}

.copyright {
  font-size: 12px;
}

.mmmtttt {
  color: #969799;
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

.cache-info-group, .clear-options-group {
  margin-bottom: 16px;
}

.cache-desc {
  font-size: 12px;
  color: #999;
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
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.dialog-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}

.upload-area {
  border: 2px dashed var(--border-soft);
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
}
</style>
