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
      <van-cell title="通过ID导入" icon="add-o" @click="showImportDialog = true" is-link />
      <van-cell title="任务中心" icon="clock-o" to="/import-tasks" is-link>
        <template #value>
          <van-tag v-if="activeTaskCount > 0" type="primary" round>
            {{ activeTaskCount }}
          </van-tag>
        </template>
      </van-cell>
      <van-cell v-if="!isVideoMode" title="本地漫画导入" icon="description" to="/comic-local-import" is-link />
      <van-cell v-else title="本地视频导入" icon="description" to="/video-local-import" is-link />
    </van-cell-group>

    <van-cell-group class="mine-menu" inset>
      <van-cell title="数据同步" icon="share-o" to="/sync" is-link />
      <van-cell title="数据库整理" icon="brush-o" @click="openOrganizePanel" is-link />
      <van-cell title="存储管理" icon="tosend" @click="showCachePanel = true" is-link />
    </van-cell-group>

    <van-cell-group class="mine-menu" inset>
      <van-cell title="系统设置" icon="setting-o" to="/config" is-link />
    </van-cell-group>
    
    <div class="about">
      <div class="about-card">
        <div class="about-meta">
          <p class="version">版本 {{ appVersionLabel }}</p>
          <p class="copyright">© 2026 Ultimate Web</p>
          <p class="mmmtttt">github@Mmmtttt</p>
          <p class="mmmtttt link-wrap">持续更新开源链接 https://github.com/Mmmtttt/ULTIMATE_WEB</p>
        </div>
        <div class="update-card">
          <div class="update-status">{{ updateStatusText }}</div>
          <div class="update-meta">上次检查：{{ updateCheckedAtText }}</div>
          <div class="update-actions">
            <van-button
              size="small"
              type="primary"
              :loading="updateChecking"
              @click="handleManualCheckUpdate"
            >
              检查更新
            </van-button>
            <van-button
              v-if="hasNewVersion"
              size="small"
              plain
              @click="handleOpenReleasePage"
            >
              前往下载
            </van-button>
          </div>
        </div>
      </div>
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
        <div class="dialog-header">
          <h3>{{ isVideoMode ? '导入视频' : '导入漫画' }}</h3>
          <p>创建在线任务后，可在“任务中心”里持续跟进进度。</p>
        </div>

        <div class="dialog-section">
          <div class="option-title">导入方式</div>
          <div class="option-grid option-grid-two">
            <button
              type="button"
              class="option-card"
              :class="{ active: importType === 'by_id' }"
              @click="importType = 'by_id'"
            >
              <span class="option-card-title">{{ isVideoMode ? '通过 Code' : '通过 ID' }}</span>
              <span class="option-card-desc">输入单个标识，快速创建任务</span>
            </button>
            <button
              type="button"
              class="option-card"
              :class="{ active: importType === 'by_list' }"
              @click="importType = 'by_list'"
            >
              <span class="option-card-title">批量文件</span>
              <span class="option-card-desc">读取 `.txt` 清单，批量导入</span>
            </button>
          </div>
        </div>

        <div class="dialog-section">
          <div class="option-title">导入位置</div>
          <div class="option-grid option-grid-two">
            <button
              type="button"
              class="option-card compact"
              :class="{ active: importTarget === 'home' }"
              @click="importTarget = 'home'"
            >
              <span class="option-card-title">本地库</span>
              <span class="option-card-desc">直接加入当前设备内容库</span>
            </button>
            <button
              type="button"
              class="option-card compact"
              :class="{ active: importTarget === 'recommendation' }"
              @click="importTarget = 'recommendation'"
            >
              <span class="option-card-title">预览库</span>
              <span class="option-card-desc">先进入预览区，再决定是否保留</span>
            </button>
          </div>
        </div>

        <div class="dialog-section">
          <div class="option-title">来源平台</div>
          <div v-if="currentImportPlatforms.length > 0" class="option-grid option-grid-platforms">
            <button
              v-for="platform in currentImportPlatforms"
              :key="platform.value"
              type="button"
              class="option-card compact"
              :class="{ active: importPlatform === platform.value }"
              @click="importPlatform = platform.value"
            >
              <span class="option-card-title">{{ platform.label }}</span>
              <span class="option-card-desc">{{ isVideoMode ? '按平台视频标识导入' : '按平台作品标识导入' }}</span>
            </button>
          </div>
          <div v-else class="option-empty">当前模式暂无可用平台</div>
        </div>
        
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

    <van-action-sheet
      v-model:show="showOrganizeSheet"
      :actions="organizeActions"
      cancel-text="取消"
      close-on-click-action
      @select="handleOrganizeActionSelect"
    />
    
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useComicStore, useVideoStore, useCacheStore, useTagStore, useListStore, useModeStore, useImportTaskStore, useAppUpdateStore } from '@/stores'
import { configApi, organizeApi } from '@/api'
import { closeToast, showFailToast, showConfirmDialog, showLoadingToast, showSuccessToast } from 'vant'
import { openReleasePage } from '@/services/appUpdate'
import { fetchProtocolPlatformOptions } from '@/utils'

const router = useRouter()
const modeStore = useModeStore()
const comicStore = useComicStore()
const videoStore = useVideoStore()
const cacheStore = useCacheStore()
const tagStore = useTagStore()
const listStore = useListStore()
const importTaskStore = useImportTaskStore()
const appUpdateStore = useAppUpdateStore()

const isVideoMode = computed(() => modeStore.isVideoMode)

// State
const showImportDialog = ref(false)
const showCachePanel = ref(false)
const importType = ref('by_id')
const importTarget = ref('home')
const importPlatform = ref('')
const importId = ref('')
const importFile = ref(null)
const importing = ref(false)
const importFileInput = ref(null)
const showOrganizeSheet = ref(false)
const organizeActions = ref([])
const runningOrganizeAction = ref(false)
const loadingOrganizeOptions = ref(false)
const importPlatformOptions = ref([])

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
const organizeModeKey = computed(() => (isVideoMode.value ? 'video' : 'comic'))
const appVersionLabel = computed(() => String(import.meta.env.VITE_APP_VERSION || '0.0.0').trim() || '0.0.0')
const updateChecking = computed(() => appUpdateStore.checking)
const hasNewVersion = computed(() => appUpdateStore.hasUpdate)
const updateStatusText = computed(() => appUpdateStore.statusText)
const updateCheckedAtText = computed(() => appUpdateStore.checkedAtText)
const updateReleaseUrl = computed(() => appUpdateStore.releaseUrl)
const currentImportPlatforms = computed(() => importPlatformOptions.value)

async function handleManualCheckUpdate() {
  const result = await appUpdateStore.checkForUpdates({ source: 'manual', showPrompt: true })
  if (result?.hasUpdate) {
    showSuccessToast(`发现新版本 ${result.latestVersion}`)
    return
  }
  if (result?.reason === 'up-to-date') {
    showSuccessToast('当前已是最新版本')
    return
  }
  if (result?.reason === 'network-error') {
    showFailToast('检查更新失败，请稍后重试')
  }
}

function handleOpenReleasePage() {
  openReleasePage(updateReleaseUrl.value)
}

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

function mapOrganizeActions(rawOptions) {
  if (!Array.isArray(rawOptions)) {
    return []
  }
  return rawOptions.map((item) => ({
    ...item,
    name: item?.name || item?.action || '未知功能',
    subname: item?.description || '',
    disabled: item?.implemented === false,
  }))
}

function buildOrganizeResultMessage(action, payload) {
  if (payload?.summary) {
    return payload.summary
  }
  if (action === 'repair_cover') {
    const rewritten = Number(payload?.home?.rewritten_total_pages || 0)
    const repaired = Number(payload?.home?.updated_cover_paths || 0) + Number(payload?.recommendation?.updated_cover_paths || 0)
    return `修复封面完成：修复封面 ${repaired}，回写页数 ${rewritten}`
  }
  if (action === 'deduplicate_by_title' || action === 'deduplicate_by_code') {
    const home = Number(payload?.home?.moved_to_trash || 0)
    const recommendation = Number(payload?.recommendation?.moved_to_trash || 0)
    return `查重完成：本地库 ${home} 条，预览库 ${recommendation} 条`
  }
  if (action === 'enrich_local_metadata') {
    const updated = Number(payload?.updated_records || 0)
    const noMatch = Number(payload?.skipped_no_match || 0)
    return `LOCAL 补全完成：成功 ${updated}，无匹配 ${noMatch}`
  }
  return '数据库整理已完成'
}

function buildOrganizeResultDetail(action, payload) {
  const summary = buildOrganizeResultMessage(action, payload)
  if (action === 'enrich_local_metadata') {
    const lines = [
      summary,
      `处理候选: ${Number(payload?.processed_candidates || 0)}`,
      `无匹配: ${Number(payload?.skipped_no_match || 0)}`,
      `已补全跳过: ${Number(payload?.skipped_already_enriched || 0)}`
    ]
    const matchedByPlatform = payload?.matched_by_platform
    const entries = matchedByPlatform && typeof matchedByPlatform === 'object'
      ? Object.entries(matchedByPlatform)
      : []
    if (entries.length > 0) {
      entries.forEach(([platform, count]) => {
        lines.push(`${String(platform || '').toUpperCase()}命中: ${Number(count || 0)}`)
      })
    } else {
      const platformOrder = Array.isArray(payload?.search_platform_order)
        ? payload.search_platform_order
        : []
      platformOrder.forEach((platform) => {
        lines.push(`${String(platform || '').toUpperCase()}命中: 0`)
      })
    }
    return lines.join('\n')
  }
  if (action === 'deduplicate_by_title' || action === 'deduplicate_by_code') {
    return [
      summary,
      `本地库移入回收站: ${Number(payload?.home?.moved_to_trash || 0)}`,
      `预览库移入回收站: ${Number(payload?.recommendation?.moved_to_trash || 0)}`
    ].join('\n')
  }
  return summary
}

async function loadImportPlatformOptions() {
  try {
    const options = await fetchProtocolPlatformOptions({
      mediaType: isVideoMode.value ? 'video' : 'comic',
      capability: 'catalog.search'
    })
    importPlatformOptions.value = options.map((item) => ({
      label: item.label,
      value: String(item.platform || '').trim().toUpperCase()
    }))
  } catch (error) {
    importPlatformOptions.value = []
    console.error('加载导入平台失败', error)
  }

  if (!importPlatformOptions.value.some(item => item.value === importPlatform.value)) {
    importPlatform.value = importPlatformOptions.value[0]?.value || ''
  }
}

async function openOrganizePanel() {
  if (runningOrganizeAction.value || loadingOrganizeOptions.value) {
    return
  }
  loadingOrganizeOptions.value = true
  try {
    const response = await organizeApi.getOptions(organizeModeKey.value)
    organizeActions.value = mapOrganizeActions(response?.data?.options)
    if (!organizeActions.value.length) {
      showFailToast('当前模式暂无可用整理功能')
      return
    }
    showOrganizeSheet.value = true
  } catch (error) {
    showFailToast(error?.message || '加载数据库整理功能失败')
  } finally {
    loadingOrganizeOptions.value = false
  }
}

async function handleOrganizeActionSelect(selectedAction) {
  if (!selectedAction?.action) {
    return
  }
  if (selectedAction?.implemented === false) {
    showFailToast(selectedAction?.confirm_message || '该功能尚未实现')
    return
  }

  try {
    await showConfirmDialog({
      title: '数据库整理',
      message: selectedAction?.confirm_message || `确定执行「${selectedAction?.name || selectedAction?.action}」吗？`
    })
  } catch {
    return
  }

  runningOrganizeAction.value = true
  showLoadingToast({
    message: `正在执行「${selectedAction?.name || '数据库整理'}」...`,
    forbidClick: true,
    duration: 0
  })
  try {
    const response = await organizeApi.run(organizeModeKey.value, selectedAction.action)
    closeToast()
    const resultText = buildOrganizeResultDetail(selectedAction.action, response?.data || {})
    await showConfirmDialog({
      title: '执行完成',
      message: resultText,
      confirmButtonText: '知道了',
      showCancelButton: false
    })
  } catch (error) {
    closeToast()
    showFailToast(error?.message || '数据库整理失败')
  } finally {
    runningOrganizeAction.value = false
  }
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
    platform: String(importPlatform.value || '').trim().toUpperCase(),
    content_type: 'comic',
    comic_id: normalizeImportId(importId.value, importPlatform.value)
  }

  if (!params.platform) {
    throw new Error('当前模式暂无可用平台')
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
  const defaultPlatform = String(importPlatform.value || '').trim().toUpperCase()

  if (!defaultPlatform) {
    throw new Error('当前模式暂无可用平台')
  }

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
  await loadImportPlatformOptions()
})

watch(() => modeStore.currentMode, async () => {
  organizeActions.value = []
  await loadImportPlatformOptions()
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
  padding: 28px 0 16px;
  color: var(--text-tertiary);
}

.about-card {
  max-width: 420px;
  margin: 0 auto;
  padding: 14px;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.about-meta {
  text-align: center;
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

.link-wrap {
  line-height: 1.6;
  word-break: break-all;
}

.update-card {
  margin-top: 14px;
  padding: 12px;
  background: var(--surface-1);
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  text-align: left;
}

.update-status {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.4;
}

.update-meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.update-actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}

/* Panels & Dialogs */
.cache-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.cache-content {
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
  width: min(92vw, 420px);
  padding: 20px;
}

.dialog-header {
  margin-bottom: 18px;
}

.dialog-header h3 {
  margin: 0;
  text-align: center;
}

.dialog-header p {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-tertiary);
  text-align: center;
}

.dialog-section {
  margin-bottom: 16px;
}

.option-title {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.option-grid {
  display: grid;
  gap: 10px;
}

.option-grid-two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.option-grid-platforms {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.option-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  padding: 12px;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  background: var(--surface-1);
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  transition:
    transform var(--motion-fast) var(--ease-standard),
    border-color var(--motion-fast) var(--ease-standard),
    box-shadow var(--motion-fast) var(--ease-standard),
    background-color var(--motion-fast) var(--ease-standard);
}

.option-card.compact {
  min-height: 88px;
}

.option-card.active {
  border-color: rgba(47, 116, 255, 0.5);
  background: rgba(89, 160, 255, 0.14);
  box-shadow: 0 12px 20px rgba(47, 116, 255, 0.12);
}

.option-card-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-strong);
}

.option-card-desc {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-tertiary);
}

.option-empty {
  font-size: 13px;
  color: var(--text-tertiary);
}

.dialog-buttons {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
}

@media (max-width: 767px) {
  .about {
    padding: 22px 12px 12px;
  }

  .update-actions {
    justify-content: flex-start;
  }

  .update-actions .van-button {
    flex: 1;
  }

  .import-dialog {
    padding: 16px;
  }

  .option-grid-two,
  .option-grid-platforms {
    grid-template-columns: 1fr;
  }

  .dialog-buttons .van-button {
    flex: 1;
  }
}

</style>
