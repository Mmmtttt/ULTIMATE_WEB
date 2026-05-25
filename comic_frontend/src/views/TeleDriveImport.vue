<template>
  <div class="teledrive-import-page desktop-page-shell">
    <van-nav-bar
      title="TeleDrive"
      left-arrow
      @click-left="$router.back()"
    />

    <section class="hero card-surface">
      <div>
        <h2>Telegram 云媒体库</h2>
        <p>
          扫描已绑定频道中的转发消息，把图片和视频纳入 Ultimate 管理。普通 Telegram 图片会按需转存为 document，视频保留 Range 播放能力。
        </p>
      </div>
      <van-button
        plain
        type="primary"
        size="small"
        :loading="loadingStatus"
        @click="loadStatus"
      >
        刷新状态
      </van-button>
    </section>

    <section class="status-grid">
      <div class="status-card card-surface">
        <span class="status-label">连接状态</span>
        <strong :class="statusClass">{{ statusLabel }}</strong>
        <small>{{ statusHint }}</small>
      </div>
      <div class="status-card card-surface">
        <span class="status-label">最近导入</span>
        <strong>{{ latestResult ? `${latestResult.imported || 0} 个新增` : '-' }}</strong>
        <small>{{ latestResult ? `扫描 ${latestResult.scanned || 0}，跳过 ${latestResult.skipped || 0}` : '暂无记录' }}</small>
      </div>
      <div class="status-card card-surface">
        <span class="status-label">Bridge</span>
        <strong>{{ bridgeBaseUrl || '-' }}</strong>
        <small>前端通过 Ultimate 后端代理访问</small>
      </div>
    </section>

    <section class="card-surface form-card">
      <div class="section-title">
        <h3>扫描频道</h3>
        <span class="hint">建议先预览，再真实导入</span>
      </div>

      <van-field
        v-model.number="limit"
        type="number"
        label="扫描条数"
        placeholder="100"
        min="1"
        max="1000"
      />

      <van-cell title="转存普通图片" label="开启后会把 Telegram photo 转成 document，再写入 Teldrive 文件表">
        <template #right-icon>
          <van-switch v-model="convertPhotos" />
        </template>
      </van-cell>

      <div class="actions">
        <van-button
          plain
          type="primary"
          :loading="previewing"
          :disabled="running"
          @click="previewImport"
        >
          预览扫描
        </van-button>
        <van-button
          type="primary"
          :loading="running"
          :disabled="previewing"
          @click="runImport"
        >
          确认导入
        </van-button>
      </div>
    </section>

    <section v-if="currentResult" class="card-surface result-card">
      <div class="section-title">
        <h3>{{ currentResult.dry_run ? '预览结果' : '导入结果' }}</h3>
        <van-tag :type="currentResult.dry_run ? 'warning' : 'success'">
          {{ currentResult.dry_run ? 'dry-run' : '已执行' }}
        </van-tag>
      </div>

      <div class="stats-grid">
        <div class="stat-item">
          <div class="label">扫描</div>
          <div class="value">{{ currentResult.scanned || 0 }}</div>
        </div>
        <div class="stat-item">
          <div class="label">新增</div>
          <div class="value success">{{ currentResult.imported || 0 }}</div>
        </div>
        <div class="stat-item">
          <div class="label">转存图片</div>
          <div class="value">{{ currentResult.converted_photos || 0 }}</div>
        </div>
        <div class="stat-item">
          <div class="label">跳过</div>
          <div class="value warning">{{ currentResult.skipped || 0 }}</div>
        </div>
        <div class="stat-item">
          <div class="label">错误</div>
          <div class="value danger">{{ resultErrors.length }}</div>
        </div>
      </div>

      <van-cell-group v-if="resultFiles.length" inset title="文件">
        <van-cell
          v-for="file in resultFiles"
          :key="`${file.original_message_id}-${file.file_id}`"
          :title="file.name || file.file_id || '-'"
          :label="`${file.category || '-'} · ${file.mime_type || '-'} · ${formatBytes(file.size)}`"
        >
          <template #right-icon>
            <van-tag v-if="file.converted" type="primary" size="small">已转存</van-tag>
          </template>
        </van-cell>
      </van-cell-group>

      <van-cell-group v-if="resultErrors.length" inset title="错误">
        <van-cell
          v-for="(error, index) in resultErrors"
          :key="`err-${index}`"
          :title="String(error)"
        />
      </van-cell-group>
    </section>

    <section class="card-surface form-card">
      <div class="section-title">
        <h3>同步预览库</h3>
        <span class="hint">只识别 /comic 和 /video 固定目录</span>
      </div>

      <van-field
        v-model.number="syncLimit"
        type="number"
        label="扫描文件数"
        placeholder="10000"
        min="1"
        max="50000"
      />

      <div class="actions">
        <van-button
          plain
          type="primary"
          :loading="syncPreviewing"
          :disabled="syncing"
          @click="previewLibrarySync"
        >
          预览同步
        </van-button>
        <van-button
          type="primary"
          :loading="syncing"
          :disabled="syncPreviewing"
          @click="runLibrarySync"
        >
          写入预览库
        </van-button>
      </div>
    </section>

    <section v-if="syncResult" class="card-surface result-card">
      <div class="section-title">
        <h3>{{ syncResult.dry_run ? '同步预览' : '同步结果' }}</h3>
        <van-tag :type="syncResult.dry_run ? 'warning' : 'success'">
          {{ syncResult.dry_run ? 'dry-run' : '已写入' }}
        </van-tag>
      </div>

      <div class="stats-grid">
        <div class="stat-item">
          <div class="label">漫画</div>
          <div class="value success">{{ syncStats.recognized_comics || 0 }}</div>
        </div>
        <div class="stat-item">
          <div class="label">视频</div>
          <div class="value success">{{ syncStats.recognized_videos || 0 }}</div>
        </div>
        <div class="stat-item">
          <div class="label">跳过</div>
          <div class="value warning">{{ syncStats.skipped || 0 }}</div>
        </div>
        <div class="stat-item">
          <div class="label">新增</div>
          <div class="value">{{ syncAddedCount }}</div>
        </div>
        <div class="stat-item">
          <div class="label">更新</div>
          <div class="value">{{ syncUpdatedCount }}</div>
        </div>
      </div>

      <van-cell-group v-if="syncComics.length" inset title="识别到的漫画">
        <van-cell
          v-for="comic in syncComics.slice(0, 20)"
          :key="comic.id"
          :title="comic.title || comic.id"
          :label="`${comic.total_page || 0} 页 · ${comic.display?.teledrive?.path || ''}`"
        />
      </van-cell-group>

      <van-cell-group v-if="syncVideos.length" inset title="识别到的视频">
        <van-cell
          v-for="video in syncVideos.slice(0, 20)"
          :key="video.id"
          :title="video.title || video.id"
          :label="`${video.total_units || 0} 集 · ${video.display?.teledrive?.path || ''}`"
        />
      </van-cell-group>

      <van-cell-group v-if="syncSkipped.length" inset title="跳过项">
        <van-cell
          v-for="(item, index) in syncSkipped.slice(0, 20)"
          :key="`skip-${index}`"
          :title="item.path || '-'"
          :label="item.reason || ''"
        />
      </van-cell-group>
    </section>

    <section class="card-surface catalog-card">
      <div class="section-title">
        <h3>最近媒体</h3>
        <van-button
          plain
          type="primary"
          size="small"
          :loading="loadingCatalog"
          @click="loadCatalog"
        >
          刷新
        </van-button>
      </div>

      <div v-if="activeVideoUrl" class="video-preview">
        <video controls playsinline preload="metadata" :src="activeVideoUrl"></video>
      </div>

      <van-empty v-if="!catalogItems.length && !loadingCatalog" description="暂无 TeleDrive 媒体" />
      <div v-else class="catalog-list">
        <article
          v-for="item in catalogItems"
          :key="item.id"
          class="catalog-item"
        >
          <div class="thumb">
            <van-image
              v-if="itemKind(item) === 'image'"
              :src="mediaUrl(item)"
              fit="cover"
            />
            <van-icon v-else name="play-circle-o" />
          </div>
          <div class="catalog-info">
            <strong>{{ item.name }}</strong>
            <span>{{ itemKind(item) || '-' }} · {{ item.mime_type || '-' }}</span>
            <small>{{ formatBytes(item.size) }}</small>
          </div>
          <van-button
            v-if="itemKind(item) === 'video'"
            size="small"
            plain
            type="primary"
            @click="playVideo(item)"
          >
            播放
          </van-button>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { closeToast, showFailToast, showLoadingToast, showSuccessToast } from 'vant'
import { teledriveApi } from '@/api'

const loadingStatus = ref(false)
const loadingCatalog = ref(false)
const previewing = ref(false)
const running = ref(false)
const syncPreviewing = ref(false)
const syncing = ref(false)

const status = ref(null)
const catalogItems = ref([])
const currentResult = ref(null)
const syncResult = ref(null)
const activeVideoUrl = ref('')
const limit = ref(100)
const syncLimit = ref(10000)
const convertPhotos = ref(true)

const latestResult = computed(() => {
  const data = status.value || {}
  return data?.latest_import?.job?.result
    || data?.latest_import?.result
    || data?.latest_import?.last_result
    || data?.last_result
    || data?.import_status?.last_result
    || null
})

const bridgeBaseUrl = computed(() => {
  const data = status.value || {}
  return data?.config?.bridge_base_url || data?.bridge_base_url || ''
})

const isHealthy = computed(() => {
  const data = status.value || {}
  if (data.enabled === false || data.configured === false) return false
  if (data.ok === true || data.bridge_health?.ok === true || data.health?.ok === true) return true
  return false
})

const statusLabel = computed(() => {
  if (!status.value) return '未检测'
  return isHealthy.value ? '已连接' : '需检查'
})

const statusHint = computed(() => {
  if (!status.value) return '点击刷新状态'
  if (isHealthy.value) return 'TeleDrive Bridge 可用'
  return status.value?.error || status.value?.message || '请检查 Bridge 地址、Token 或 TeleDrive 服务'
})

const statusClass = computed(() => ({
  success: isHealthy.value,
  danger: status.value && !isHealthy.value
}))

const resultFiles = computed(() => {
  const files = currentResult.value?.files
  return Array.isArray(files) ? files : []
})

const resultErrors = computed(() => {
  const errors = currentResult.value?.errors
  return Array.isArray(errors) ? errors : []
})

const syncStats = computed(() => syncResult.value?.stats || {})
const syncComics = computed(() => Array.isArray(syncResult.value?.comics) ? syncResult.value.comics : [])
const syncVideos = computed(() => Array.isArray(syncResult.value?.videos) ? syncResult.value.videos : [])
const syncSkipped = computed(() => Array.isArray(syncResult.value?.skipped) ? syncResult.value.skipped : [])
const syncAddedCount = computed(() => {
  const stats = syncStats.value
  return Number(stats.comic_added || 0) + Number(stats.video_added || 0)
})
const syncUpdatedCount = computed(() => {
  const stats = syncStats.value
  return Number(stats.comic_updated || 0) + Number(stats.video_updated || 0)
})

onMounted(async () => {
  await Promise.all([loadStatus(), loadCatalog()])
})

async function loadStatus() {
  loadingStatus.value = true
  try {
    const response = await teledriveApi.getStatus()
    status.value = response.data || {}
  } catch (error) {
    status.value = { enabled: false, error: error?.message || '状态读取失败' }
  } finally {
    loadingStatus.value = false
  }
}

async function loadCatalog() {
  loadingCatalog.value = true
  try {
    const response = await teledriveApi.getCatalog({ limit: 40 })
    const data = response.data || {}
    catalogItems.value = data.items || data.catalog?.items || []
  } catch (error) {
    showFailToast(error?.message || '读取 TeleDrive 媒体失败')
  } finally {
    loadingCatalog.value = false
  }
}

async function previewImport() {
  previewing.value = true
  showLoadingToast({ message: '正在预览扫描...', duration: 0, forbidClick: true })
  try {
    const response = await teledriveApi.previewImport(buildImportPayload())
    closeToast()
    currentResult.value = extractImportResult(response.data)
    showSuccessToast('预览完成')
    await loadStatus()
  } catch (error) {
    closeToast()
    showFailToast(error?.message || '预览失败')
  } finally {
    previewing.value = false
  }
}

async function runImport() {
  running.value = true
  showLoadingToast({ message: '正在导入 TeleDrive 媒体...', duration: 0, forbidClick: true })
  try {
    const response = await teledriveApi.runImport(buildImportPayload())
    closeToast()
    currentResult.value = extractImportResult(response.data)
    showSuccessToast('导入完成')
    await Promise.all([loadStatus(), loadCatalog()])
  } catch (error) {
    closeToast()
    showFailToast(error?.message || '导入失败')
  } finally {
    running.value = false
  }
}

async function previewLibrarySync() {
  syncPreviewing.value = true
  showLoadingToast({ message: '正在扫描固定目录...', duration: 0, forbidClick: true })
  try {
    const response = await teledriveApi.previewLibrarySync(buildLibrarySyncPayload())
    closeToast()
    syncResult.value = response.data || null
    showSuccessToast('同步预览完成')
  } catch (error) {
    closeToast()
    showFailToast(error?.message || '同步预览失败')
  } finally {
    syncPreviewing.value = false
  }
}

async function runLibrarySync() {
  syncing.value = true
  showLoadingToast({ message: '正在写入预览库...', duration: 0, forbidClick: true })
  try {
    const response = await teledriveApi.runLibrarySync(buildLibrarySyncPayload())
    closeToast()
    syncResult.value = response.data || null
    showSuccessToast('预览库同步完成')
  } catch (error) {
    closeToast()
    showFailToast(error?.message || '预览库同步失败')
  } finally {
    syncing.value = false
  }
}

function buildImportPayload() {
  return {
    limit: limit.value,
    convert_photos: convertPhotos.value
  }
}

function buildLibrarySyncPayload() {
  return {
    limit: syncLimit.value
  }
}

function extractImportResult(data) {
  return data?.job?.result || data?.result || data || null
}

function mediaUrl(item) {
  if (!item?.id) return ''
  return teledriveApi.buildFileContentUrl(item.id, item.name ? { name: item.name } : {})
}

function playVideo(item) {
  activeVideoUrl.value = mediaUrl(item)
}

function itemKind(item) {
  const kind = String(item?.kind || item?.category || '').toLowerCase()
  const mime = String(item?.mime_type || '').toLowerCase()
  if (kind === 'video' || mime.startsWith('video/')) return 'video'
  if (kind === 'image' || mime.startsWith('image/')) return 'image'
  return kind || ''
}

function formatBytes(value) {
  const size = Number(value || 0)
  if (!Number.isFinite(size) || size <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let next = size
  let index = 0
  while (next >= 1024 && index < units.length - 1) {
    next /= 1024
    index += 1
  }
  return `${next.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}
</script>

<style scoped>
.teledrive-import-page {
  min-height: 100vh;
  padding: 0 12px 80px;
  background: var(--surface-0);
}

.card-surface {
  margin-top: 12px;
  padding: 14px;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.hero h2 {
  margin: 0;
  font-size: 18px;
  color: var(--text-strong);
}

.hero p {
  margin: 10px 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.status-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.status-label,
.hint,
.catalog-info span,
.catalog-info small,
.status-card small {
  color: var(--text-tertiary);
  font-size: 12px;
}

.status-card strong {
  color: var(--text-primary);
  font-size: 15px;
  overflow-wrap: anywhere;
}

.status-card strong.success {
  color: #0f8a35;
}

.status-card strong.danger {
  color: #b42318;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.section-title h3 {
  margin: 0;
  font-size: 16px;
  color: var(--text-strong);
}

.actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 12px;
}

.stats-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.stat-item {
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  padding: 10px;
  background: var(--surface-1);
}

.stat-item .label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.stat-item .value {
  margin-top: 6px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.stat-item .value.success {
  color: #0f8a35;
}

.stat-item .value.warning {
  color: #a56200;
}

.stat-item .value.danger {
  color: #b42318;
}

.video-preview {
  margin-bottom: 12px;
  border-radius: 12px;
  overflow: hidden;
  background: #050505;
}

.video-preview video {
  display: block;
  width: 100%;
  max-height: 480px;
}

.catalog-list {
  display: grid;
  gap: 8px;
}

.catalog-item {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 8px;
  background: var(--surface-1);
}

.thumb {
  width: 64px;
  height: 48px;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(89, 160, 255, 0.12);
  color: var(--brand-700);
}

.thumb :deep(.van-image) {
  width: 100%;
  height: 100%;
}

.thumb .van-icon {
  font-size: 25px;
}

.catalog-info {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.catalog-info strong {
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 1080px) {
  .hero {
    flex-direction: column;
  }

  .status-grid,
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .actions {
    grid-template-columns: 1fr;
  }
}
</style>
