<template>
  <div class="teledrive-page desktop-page-shell">
    <van-nav-bar title="TeleDrive" left-arrow @click-left="$router.back()">
      <template #right>
        <van-button
          icon="replay"
          size="small"
          plain
          type="primary"
          :loading="loadingStatus"
          @click="refreshAll"
        >
          刷新
        </van-button>
      </template>
    </van-nav-bar>

    <section class="topline">
      <div class="title-block">
        <h2>Telegram 媒体桥</h2>
        <p>把频道里的图片、视频交给 TeleDrive 存储，再按固定目录同步到 Ultimate 预览库。</p>
      </div>
      <div class="status-strip">
        <div class="status-pill" :class="{ healthy: isHealthy, danger: status && !isHealthy }">
          <van-icon :name="isHealthy ? 'passed' : 'warning-o'" />
          <span>{{ statusLabel }}</span>
        </div>
        <span class="status-detail">{{ statusHint }}</span>
      </div>
    </section>

    <section class="metrics">
      <div class="metric">
        <span>Bridge</span>
        <strong>{{ bridgeBaseUrl || '-' }}</strong>
      </div>
      <div class="metric">
        <span>最近导入</span>
        <strong>{{ latestResult ? `${latestResult.imported || 0} 个新增` : '-' }}</strong>
      </div>
      <div class="metric">
        <span>最近扫描</span>
        <strong>{{ latestResult ? `${latestResult.scanned || 0} 条` : '-' }}</strong>
      </div>
      <div class="metric">
        <span>预览库</span>
        <strong>{{ syncResult ? `${syncStats.recognized_comics || 0} 漫画 / ${syncStats.recognized_videos || 0} 视频` : '待同步' }}</strong>
      </div>
    </section>

    <section v-if="!isHealthy && status" class="notice-panel">
      <van-icon name="info-o" />
      <span>{{ statusHint }}</span>
      <router-link to="/config">去配置</router-link>
    </section>

    <div class="workspace-grid">
      <section class="panel workflow-panel">
        <van-tabs v-model:active="activeWorkflow" shrink>
          <van-tab title="频道导入" name="import">
            <div class="workflow-head">
              <div>
                <h3>导入频道媒体</h3>
                <p>读取已绑定频道的最近消息，补进 TeleDrive 文件表。</p>
              </div>
              <HelpPopover
                text="用于处理你转发到 Telegram 频道里的媒体。普通 photo 可转存为 document，视频会保留可在线播放的文件记录。"
              />
            </div>

            <van-cell-group inset>
              <van-field
                v-model.number="limit"
                type="number"
                label="扫描条数"
                placeholder="100"
                min="1"
                max="1000"
              />
              <van-cell title="转存普通图片" label="让 Telegram photo 也能进入 TeleDrive 文件管理">
                <template #right-icon>
                  <van-switch v-model="convertPhotos" />
                </template>
              </van-cell>
            </van-cell-group>

            <div class="action-row">
              <van-button
                icon="search"
                plain
                type="primary"
                :loading="previewing"
                :disabled="running"
                @click="previewImport"
              >
                预览
              </van-button>
              <van-button
                icon="plus"
                type="primary"
                :loading="running"
                :disabled="previewing"
                @click="runImport"
              >
                导入
              </van-button>
            </div>
          </van-tab>

          <van-tab title="预览库同步" name="sync">
            <div class="workflow-head">
              <div>
                <h3>同步固定目录</h3>
                <p>扫描 TeleDrive 的 /comic 与 /video，写入 Ultimate 预览库。</p>
              </div>
              <HelpPopover
                text="Ultimate 只识别固定目录：/comic/{作品}、/comic/{平台}/{作品}、/video/{视频}、/video/{平台}/{视频}。不符合结构的文件会跳过。"
              />
            </div>

            <van-cell-group inset>
              <van-field
                v-model.number="syncLimit"
                type="number"
                label="扫描文件数"
                placeholder="10000"
                min="1"
                max="50000"
              />
            </van-cell-group>

            <div class="action-row">
              <van-button
                icon="search"
                plain
                type="primary"
                :loading="syncPreviewing"
                :disabled="syncing"
                @click="previewLibrarySync"
              >
                预览
              </van-button>
              <van-button
                icon="success"
                type="primary"
                :loading="syncing"
                :disabled="syncPreviewing"
                @click="runLibrarySync"
              >
                同步
              </van-button>
            </div>
          </van-tab>
        </van-tabs>

        <ResultSummary
          v-if="currentResult && activeWorkflow === 'import'"
          title="导入结果"
          :dry-run="Boolean(currentResult.dry_run)"
          :items="importMetrics"
          :details="importDetails"
        />
        <ResultSummary
          v-if="syncResult && activeWorkflow === 'sync'"
          title="同步结果"
          :dry-run="Boolean(syncResult.dry_run)"
          :items="syncMetrics"
          :details="syncDetails"
        />
      </section>

      <section class="panel media-panel">
        <div class="panel-title">
          <div>
            <h3>最近媒体</h3>
            <p>确认图片和视频是否能经 Ultimate 后端代理打开。</p>
          </div>
          <van-button
            icon="replay"
            size="small"
            plain
            type="primary"
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
        <div v-else class="media-list">
          <article v-for="item in catalogItems" :key="item.id" class="media-item">
            <button class="thumb" type="button" @click="selectMedia(item)">
              <van-image v-if="itemKind(item) === 'image'" :src="mediaUrl(item)" fit="cover" />
              <van-icon v-else :name="itemKind(item) === 'video' ? 'play-circle-o' : 'description-o'" />
            </button>
            <div class="media-meta">
              <strong>{{ item.name || item.id }}</strong>
              <span>{{ itemKind(item) || 'file' }} · {{ formatBytes(item.size) }}</span>
            </div>
            <van-button
              v-if="itemKind(item) === 'video'"
              icon="play-circle-o"
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

    <section class="panel console-panel">
      <div class="panel-title">
        <div>
          <h3>TeleDrive 控制台</h3>
          <p>需要调整目录时再打开；Ultimate 只按固定目录识别内容。</p>
        </div>
        <div class="console-actions">
          <HelpPopover text="这里嵌入的是 TeleDrive 原生页面，主要用于移动文件夹或检查文件。同步规则仍由 Ultimate 的 /comic 与 /video 目录决定。" />
          <van-button
            v-if="teldriveWebUrl"
            icon="link-o"
            size="small"
            plain
            type="primary"
            @click="openConsoleExternal"
          >
            新窗口
          </van-button>
          <van-button
            icon="desktop-o"
            size="small"
            plain
            type="primary"
            @click="showConsole = !showConsole"
          >
            {{ showConsole ? '收起' : '打开' }}
          </van-button>
        </div>
      </div>

      <div v-if="showConsole" class="console-frame-wrap">
        <iframe
          v-if="teldriveWebUrl"
          class="console-frame"
          :src="teldriveWebUrl"
          title="TeleDrive"
        ></iframe>
        <van-empty v-else description="未能推断 TeleDrive Web 地址" />
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { closeToast, showFailToast, showLoadingToast, showSuccessToast } from 'vant'
import { teledriveApi } from '@/api'
import { openExternalUrl } from '@/runtime/browser'

const HelpPopover = defineComponent({
  name: 'HelpPopover',
  props: {
    text: {
      type: String,
      required: true
    }
  },
  setup(props) {
    return () => h('span', { class: 'help-wrap' }, [
      h(
        'span',
        {
          class: 'help-button',
          role: 'button',
          tabindex: '0',
          'aria-label': '说明',
        },
        '?'
      ),
      h('span', { class: 'help-bubble', role: 'tooltip' }, props.text)
    ])
  }
})

const ResultSummary = defineComponent({
  name: 'ResultSummary',
  props: {
    title: {
      type: String,
      required: true
    },
    dryRun: {
      type: Boolean,
      default: false
    },
    items: {
      type: Array,
      default: () => []
    },
    details: {
      type: Array,
      default: () => []
    }
  },
  setup(props) {
    return () => h('div', { class: 'result-summary' }, [
      h('div', { class: 'result-head' }, [
        h('strong', props.title),
        h('span', { class: ['result-badge', props.dryRun ? 'warning' : 'success'] }, props.dryRun ? '预览' : '已执行')
      ]),
      h('div', { class: 'result-metrics' }, props.items.map((item) => h('div', { class: 'result-metric', key: item.label }, [
        h('span', item.label),
        h('strong', { class: item.tone || '' }, String(item.value ?? 0))
      ]))),
      props.details.length
        ? h('div', { class: 'result-details' }, props.details.map((detail) => h(
          'details',
          { key: detail.title },
          [
            h('summary', detail.title),
            h('div', { class: 'detail-lines' }, detail.lines.map((line) => h('p', { key: line }, line)))
          ]
        )))
        : null
    ])
  }
})

const loadingStatus = ref(false)
const loadingCatalog = ref(false)
const previewing = ref(false)
const running = ref(false)
const syncPreviewing = ref(false)
const syncing = ref(false)
const showConsole = ref(false)
const activeWorkflow = ref('sync')

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

const teldriveWebUrl = computed(() => {
  const raw = String(bridgeBaseUrl.value || '').trim()
  if (!raw) return ''
  try {
    const url = new URL(raw)
    if (url.port === '8892') {
      url.port = '8787'
    }
    return url.origin
  } catch (_error) {
    return ''
  }
})

const isHealthy = computed(() => {
  const data = status.value || {}
  if (data.enabled === false || data.configured === false) return false
  if (data.ok === true || data.bridge_health?.ok === true || data.health?.ok === true) return true
  return false
})

const statusLabel = computed(() => {
  if (!status.value) return '未检测'
  return isHealthy.value ? '已连接' : '需配置'
})

const statusHint = computed(() => {
  if (!status.value) return '点击刷新状态'
  if (isHealthy.value) return 'Bridge 正常，页面可用'
  return status.value?.error || status.value?.message || '请检查 Bridge 地址、Token 或 TeleDrive 服务'
})

const resultFiles = computed(() => Array.isArray(currentResult.value?.files) ? currentResult.value.files : [])
const resultErrors = computed(() => Array.isArray(currentResult.value?.errors) ? currentResult.value.errors : [])
const syncStats = computed(() => syncResult.value?.stats || {})
const syncComics = computed(() => Array.isArray(syncResult.value?.comics) ? syncResult.value.comics : [])
const syncVideos = computed(() => Array.isArray(syncResult.value?.videos) ? syncResult.value.videos : [])
const syncSkipped = computed(() => Array.isArray(syncResult.value?.skipped) ? syncResult.value.skipped : [])
const syncAddedCount = computed(() => Number(syncStats.value.comic_added || 0) + Number(syncStats.value.video_added || 0))
const syncUpdatedCount = computed(() => Number(syncStats.value.comic_updated || 0) + Number(syncStats.value.video_updated || 0))

const importMetrics = computed(() => [
  { label: '扫描', value: currentResult.value?.scanned || 0 },
  { label: '新增', value: currentResult.value?.imported || 0, tone: 'success' },
  { label: '转存图片', value: currentResult.value?.converted_photos || 0 },
  { label: '跳过', value: currentResult.value?.skipped || 0, tone: 'warning' },
  { label: '错误', value: resultErrors.value.length, tone: 'danger' }
])

const syncMetrics = computed(() => [
  { label: '漫画', value: syncStats.value.recognized_comics || 0, tone: 'success' },
  { label: '视频', value: syncStats.value.recognized_videos || 0, tone: 'success' },
  { label: '跳过', value: syncStats.value.skipped || 0, tone: 'warning' },
  { label: '新增', value: syncAddedCount.value },
  { label: '更新', value: syncUpdatedCount.value }
])

const importDetails = computed(() => {
  const details = []
  if (resultFiles.value.length) {
    details.push({
      title: `文件 ${resultFiles.value.length}`,
      lines: resultFiles.value.slice(0, 12).map((file) => `${file.name || file.file_id || '-'} · ${file.category || '-'} · ${formatBytes(file.size)}`)
    })
  }
  if (resultErrors.value.length) {
    details.push({
      title: `错误 ${resultErrors.value.length}`,
      lines: resultErrors.value.slice(0, 12).map((error) => String(error))
    })
  }
  return details
})

const syncDetails = computed(() => {
  const details = []
  if (syncComics.value.length) {
    details.push({
      title: `漫画 ${syncComics.value.length}`,
      lines: syncComics.value.slice(0, 12).map((comic) => `${comic.title || comic.id} · ${comic.total_page || 0} 页`)
    })
  }
  if (syncVideos.value.length) {
    details.push({
      title: `视频 ${syncVideos.value.length}`,
      lines: syncVideos.value.slice(0, 12).map((video) => `${video.title || video.id} · ${video.total_units || 0} 集`)
    })
  }
  if (syncSkipped.value.length) {
    details.push({
      title: `跳过 ${syncSkipped.value.length}`,
      lines: syncSkipped.value.slice(0, 12).map((item) => `${item.path || '-'} · ${item.reason || ''}`)
    })
  }
  return details
})

onMounted(async () => {
  await refreshAll()
})

async function refreshAll() {
  await Promise.all([loadStatus(), loadCatalog()])
}

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
    const response = await teledriveApi.getCatalog({ limit: 24 })
    const data = response.data || {}
    catalogItems.value = data.items || data.catalog?.items || []
  } catch (error) {
    showFailToast(error?.message || '读取最近媒体失败')
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
  showLoadingToast({ message: '正在导入媒体...', duration: 0, forbidClick: true })
  try {
    const response = await teledriveApi.runImport(buildImportPayload())
    closeToast()
    currentResult.value = extractImportResult(response.data)
    showSuccessToast('导入完成')
    await refreshAll()
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
    showSuccessToast('预览完成')
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
    showSuccessToast('同步完成')
  } catch (error) {
    closeToast()
    showFailToast(error?.message || '同步失败')
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
  return { limit: syncLimit.value }
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

function selectMedia(item) {
  if (itemKind(item) === 'video') {
    playVideo(item)
  }
}

function openConsoleExternal() {
  if (teldriveWebUrl.value) {
    openExternalUrl(teldriveWebUrl.value)
  }
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
.teledrive-page {
  width: 100%;
  max-width: 1180px;
  min-width: 0;
  min-height: 95vh;
  margin: 0 auto;
  padding: 0 0 80px;
  overflow-x: hidden;
  color: var(--text-primary);
}

.teledrive-page.desktop-page-shell {
  width: 100%;
  min-width: 0;
}

.topline {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 2px 12px;
  align-items: flex-end;
}

.title-block h2,
.workflow-head h3,
.panel-title h3 {
  margin: 0;
  color: var(--text-strong);
  letter-spacing: 0;
}

.title-block h2 {
  font-size: 22px;
}

.title-block p,
.workflow-head p,
.panel-title p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  line-height: 1.55;
  font-size: 13px;
}

.status-strip {
  min-width: 220px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 11px;
  border-radius: 999px;
  border: 1px solid var(--border-soft);
  color: var(--text-secondary);
  background: var(--surface-2);
  font-size: 13px;
  font-weight: 700;
}

.status-pill.healthy {
  color: #0f7a3a;
  border-color: rgba(27, 143, 73, 0.28);
  background: rgba(27, 143, 73, 0.08);
}

.status-pill.danger {
  color: #b42318;
  border-color: rgba(180, 35, 24, 0.24);
  background: rgba(180, 35, 24, 0.08);
}

.status-detail {
  max-width: 360px;
  color: var(--text-tertiary);
  font-size: 12px;
  text-align: right;
  overflow-wrap: anywhere;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 0 0 12px;
}

.metric,
.panel,
.notice-panel {
  border: 1px solid var(--border-soft);
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.metric {
  min-width: 0;
  padding: 12px;
  border-radius: 8px;
}

.metric span {
  display: block;
  color: var(--text-tertiary);
  font-size: 12px;
}

.metric strong {
  display: block;
  margin-top: 6px;
  color: var(--text-primary);
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notice-panel {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  color: var(--text-secondary);
  font-size: 13px;
}

.notice-panel a {
  margin-left: auto;
  color: var(--brand-600);
  text-decoration: none;
  font-weight: 700;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 440px) minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.panel {
  min-width: 0;
  border-radius: 8px;
  padding: 14px;
}

.workflow-panel :deep(.van-tabs__wrap) {
  margin-bottom: 12px;
}

.workflow-head,
.panel-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.workflow-head > div,
.panel-title > div {
  min-width: 0;
  flex: 1 1 auto;
}

.workflow-head h3,
.panel-title h3 {
  font-size: 16px;
}

:deep(.help-wrap) {
  position: relative;
  display: inline-flex;
  align-items: center;
  flex: 0 0 auto;
  vertical-align: top;
}

:deep(.help-button) {
  width: 22px;
  height: 22px;
  border: 1px solid rgba(148, 163, 184, 0.55);
  border-radius: 999px;
  color: #64748b;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: help;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9), 0 1px 2px rgba(15, 23, 42, 0.06);
  transition: border-color 0.16s ease, color 0.16s ease, box-shadow 0.16s ease, transform 0.16s ease;
}

:deep(.help-wrap:hover .help-button),
:deep(.help-wrap:focus-within .help-button) {
  border-color: rgba(37, 99, 235, 0.7);
  color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1), 0 2px 8px rgba(15, 23, 42, 0.1);
  transform: translateY(-1px);
}

:deep(.help-bubble) {
  position: absolute;
  right: 0;
  top: 30px;
  z-index: 20;
  width: min(280px, calc(100vw - 44px));
  max-width: 280px;
  padding: 10px 12px;
  border-radius: 8px;
  color: #fff;
  background: rgba(17, 24, 39, 0.96);
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.18);
  line-height: 1.55;
  font-size: 13px;
  text-align: left;
  overflow-wrap: anywhere;
  opacity: 0;
  pointer-events: none;
  transform: translateY(-4px);
  visibility: hidden;
  transition: opacity 0.16s ease, transform 0.16s ease, visibility 0.16s ease;
}

:deep(.help-bubble::before) {
  content: '';
  position: absolute;
  right: 7px;
  top: -5px;
  width: 10px;
  height: 10px;
  background: rgba(17, 24, 39, 0.96);
  transform: rotate(45deg);
}

:deep(.help-wrap:hover .help-bubble),
:deep(.help-wrap:focus-within .help-bubble) {
  opacity: 1;
  transform: translateY(0);
  visibility: visible;
}

.action-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 12px;
}

.result-summary {
  margin-top: 14px;
  border-top: 1px solid var(--border-soft);
  padding-top: 12px;
}

.result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.result-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.result-badge.success {
  color: #0f7a3a;
  background: rgba(27, 143, 73, 0.1);
}

.result-badge.warning {
  color: #9a5d00;
  background: rgba(154, 93, 0, 0.1);
}

.result-metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.result-metric {
  min-width: 0;
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  padding: 8px;
  background: var(--surface-1);
}

.result-metric span {
  display: block;
  color: var(--text-tertiary);
  font-size: 12px;
}

.result-metric strong {
  display: block;
  margin-top: 4px;
  color: var(--text-primary);
  font-size: 15px;
}

.result-metric strong.success {
  color: #0f7a3a;
}

.result-metric strong.warning {
  color: #9a5d00;
}

.result-metric strong.danger {
  color: #b42318;
}

.result-details {
  margin-top: 8px;
}

.result-details details {
  border-top: 1px solid var(--border-soft);
  padding: 8px 0;
}

.result-details summary {
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
}

.detail-lines p {
  margin: 0 0 6px;
  color: var(--text-secondary);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.video-preview {
  margin-bottom: 12px;
  border-radius: 8px;
  overflow: hidden;
  background: #050505;
}

.video-preview video {
  display: block;
  width: 100%;
  max-height: min(42vh, 420px);
}

.media-list {
  display: grid;
  gap: 8px;
  max-height: min(58vh, 560px);
  overflow: auto;
  padding-right: 2px;
}

.media-item {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-width: 0;
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  padding: 8px;
  background: var(--surface-1);
}

.thumb {
  width: 56px;
  height: 42px;
  border: 0;
  border-radius: 6px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(89, 160, 255, 0.12);
  color: var(--brand-700);
  cursor: pointer;
}

.thumb :deep(.van-image) {
  width: 100%;
  height: 100%;
}

.thumb .van-icon {
  font-size: 24px;
}

.media-meta {
  min-width: 0;
}

.media-meta strong,
.media-meta span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.media-meta strong {
  color: var(--text-primary);
  font-size: 13px;
}

.media-meta span {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: 12px;
}

.console-panel {
  margin-top: 12px;
}

.console-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
  flex: 0 0 auto;
}

.console-frame-wrap {
  width: 100%;
  height: clamp(380px, 62vh, 720px);
  overflow: hidden;
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  background: var(--surface-1);
}

.console-frame {
  display: block;
  width: 100%;
  height: 100%;
  border: 0;
}

@media (max-width: 1180px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .teledrive-page {
    padding: 0 12px 80px;
  }

  .topline {
    flex-direction: column;
    align-items: stretch;
  }

  .status-strip {
    align-items: flex-start;
  }

  .status-detail {
    text-align: left;
  }

  .metrics,
  .result-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .media-item {
    grid-template-columns: 52px minmax(0, 1fr);
  }

  .media-item .van-button {
    grid-column: 1 / -1;
  }

  .action-row {
    grid-template-columns: 1fr;
  }

  .workflow-head,
  .panel-title {
    flex-wrap: wrap;
  }

  .console-frame-wrap {
    height: min(62vh, 560px);
  }

  .media-list {
    max-height: 460px;
  }
}
</style>
