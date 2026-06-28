<template>
  <div class="storage-page">
    <van-nav-bar
      title="存储管理"
      left-arrow
      fixed
      placeholder
      safe-area-inset-top
      @click-left="goBack"
    >
      <template #right>
        <van-button size="small" plain class="refresh-btn" :loading="loading" @click="loadOverview">
          刷新
        </van-button>
      </template>
    </van-nav-bar>

    <main class="storage-shell">
      <section class="overview-card">
        <div class="overview-copy">
          <p class="eyebrow">DATA STORAGE</p>
          <h1>{{ total.size_label || '0 B' }}</h1>
          <p class="overview-desc">
            当前 data 目录共 {{ total.file_count || 0 }} 个文件。软连接和外部真实文件不会计入，也不会被存储管理删除。
          </p>
        </div>

        <div class="donut-wrap" aria-label="存储占比">
          <div class="storage-donut" :style="donutStyle">
            <div class="donut-core">
              <span>{{ moduleCount }}</span>
              <small>模块</small>
            </div>
          </div>
        </div>

        <div class="overview-facts">
          <div class="fact">
            <span>本地内容</span>
            <strong>{{ localContentSizeLabel }}</strong>
          </div>
          <div class="fact">
            <span>可清理缓存</span>
            <strong>{{ clearableSizeLabel }}</strong>
          </div>
        </div>
      </section>

      <section v-if="notes.length > 0" class="notice-card">
        <van-icon name="info-o" />
        <div>
          <p v-for="note in notes" :key="note">{{ note }}</p>
        </div>
      </section>

      <van-skeleton v-if="loading && modules.length === 0" title :row="8" class="storage-skeleton" />

      <section v-else class="module-section">
        <div class="section-heading">
          <div>
            <p class="eyebrow">MODULES</p>
            <h2>分模块管理</h2>
          </div>
          <span>按真实目录统计</span>
        </div>

        <div class="module-grid">
          <article
            v-for="module in modules"
            :key="module.key"
            class="module-card"
            :class="{ clearable: module.clearable }"
          >
            <div class="module-top">
              <span class="module-dot" :style="{ background: module.color }"></span>
              <span class="module-percent">{{ modulePercent(module) }}</span>
            </div>
            <h3>{{ module.label }}</h3>
            <strong>{{ module.size_label }}</strong>
            <p>{{ module.description }}</p>
            <div class="module-footer">
              <span>{{ module.file_count || 0 }} 文件</span>
              <van-button
                v-if="module.clearable"
                size="small"
                plain
                type="danger"
                :loading="clearingType === module.cache_type"
                @click="confirmClearModule(module)"
              >
                清理
              </van-button>
              <van-button
                v-else-if="moduleRoute(module)"
                size="small"
                plain
                type="primary"
                @click="goModule(module)"
              >
                查看
              </van-button>
            </div>
          </article>
        </div>
      </section>

      <section class="ranking-section">
        <div class="section-heading">
          <div>
            <p class="eyebrow">LARGEST ITEMS</p>
            <h2>大文件排行</h2>
          </div>
          <van-button size="small" plain type="primary" :loading="rankingLoading" @click="loadActiveRanking">
            查询排行
          </van-button>
        </div>

        <div class="ranking-tabs">
          <button
            v-for="tab in rankingTabs"
            :key="tab.key"
            type="button"
            :class="{ active: activeRanking === tab.key }"
            @click="activeRanking = tab.key"
          >
            <span>{{ tab.label }}</span>
            <small>{{ tab.count }}</small>
          </button>
        </div>

        <div class="ranking-card">
          <div v-if="rankingLoading" class="ranking-empty">
            正在扫描当前分类，请稍候...
          </div>

          <div v-else-if="!isActiveRankingLoaded" class="ranking-empty">
            点击“查询排行”后再扫描当前分类，避免进入页面时卡顿
          </div>

          <div v-else-if="activeRankingItems.length === 0" class="ranking-empty">
            暂无可统计的本地文件
          </div>

          <template v-else>
            <button
              v-for="(item, index) in activeRankingItems"
              :key="`${item.source}-${item.content_type}-${item.id}`"
              type="button"
              class="ranking-row"
              @click="goRankingItem(item)"
            >
              <span class="rank-index">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="rank-main">
                <strong>{{ item.title || item.id }}</strong>
                <small>
                  {{ item.file_count || 0 }} 文件
                  <template v-if="item.path_kind"> · {{ item.path_kind }}</template>
                  <template v-if="item.is_soft_ref"> · 软连接</template>
                </small>
              </span>
              <span class="rank-size">{{ item.size_label }}</span>
              <van-icon name="arrow" />
            </button>
          </template>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { closeToast, showConfirmDialog, showFailToast, showLoadingToast, showSuccessToast } from 'vant'
import { configApi } from '@/api'
import { useModeStore } from '@/stores'

const router = useRouter()
const modeStore = useModeStore()

const loading = ref(false)
const rankingLoading = ref(false)
const overview = ref(null)
const rankingData = ref({})
const rankingTotals = ref({})
const rankingLoadedKeys = ref(new Set())
const activeRanking = ref('local_comics')
const clearingType = ref('')

const total = computed(() => overview.value?.total || { size_bytes: 0, size_label: '0 B', file_count: 0 })
const modules = computed(() => Array.isArray(overview.value?.modules) ? overview.value.modules : [])
const rankings = computed(() => rankingData.value || {})
const notes = computed(() => Array.isArray(overview.value?.notes) ? overview.value.notes : [])
const moduleCount = computed(() => modules.value.filter((item) => Number(item.size_bytes || 0) > 0).length)

function rankingTotalLabel(key) {
  return Object.prototype.hasOwnProperty.call(rankingTotals.value, key) ? rankingTotals.value[key] : '按需'
}

const rankingTabs = computed(() => [
  { key: 'local_comics', label: '本地漫画', count: rankingTotalLabel('local_comics') },
  { key: 'local_videos', label: '本地视频', count: rankingTotalLabel('local_videos') },
  { key: 'preview_comics', label: '预览漫画', count: rankingTotalLabel('preview_comics') },
  { key: 'preview_videos', label: '预览视频', count: rankingTotalLabel('preview_videos') },
])

const activeRankingItems = computed(() => {
  const items = rankings.value?.[activeRanking.value]
  return Array.isArray(items) ? items : []
})

const isActiveRankingLoaded = computed(() => rankingLoadedKeys.value.has(activeRanking.value))

const donutStyle = computed(() => {
  const totalSize = Number(total.value.size_bytes || 0)
  const visibleModules = modules.value.filter((item) => Number(item.size_bytes || 0) > 0)
  if (totalSize <= 0 || visibleModules.length === 0) {
    return { background: 'conic-gradient(rgba(139, 152, 173, 0.26) 0deg 360deg)' }
  }

  let cursor = 0
  const segments = visibleModules.map((module, index) => {
    const size = Number(module.size_bytes || 0)
    const start = cursor
    const width = index === visibleModules.length - 1 ? Math.max(0, 360 - cursor) : Math.max(1, (size / totalSize) * 360)
    cursor = Math.min(360, cursor + width)
    return `${module.color || '#8b98ad'} ${start.toFixed(2)}deg ${cursor.toFixed(2)}deg`
  })
  return { background: `conic-gradient(${segments.join(', ')})` }
})

const localContentSizeLabel = computed(() => {
  const size = modules.value
    .filter((item) => ['local_comics', 'local_videos'].includes(item.key))
    .reduce((sum, item) => sum + Number(item.size_bytes || 0), 0)
  return formatBytes(size)
})

const clearableSizeLabel = computed(() => {
  const size = modules.value
    .filter((item) => item.clearable)
    .reduce((sum, item) => sum + Number(item.size_bytes || 0), 0)
  return formatBytes(size)
})

function formatBytes(bytes) {
  const value = Number(bytes || 0)
  if (!Number.isFinite(value) || value <= 0) {
    return '0 B'
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  if (index === 0) {
    return `${Math.round(size)} B`
  }
  return `${size >= 10 ? size.toFixed(1) : size.toFixed(2)} ${units[index]}`
}

function modulePercent(module) {
  const totalSize = Number(total.value.size_bytes || 0)
  const size = Number(module?.size_bytes || 0)
  if (totalSize <= 0 || size <= 0) {
    return '0%'
  }
  return `${Math.max(1, Math.round((size / totalSize) * 100))}%`
}

function moduleRoute(module) {
  const routes = {
    local_comics: { name: 'Library', mode: 'comic' },
    local_videos: { name: 'Library', mode: 'video' },
    comic_preview_cache: { name: 'Preview', mode: 'comic' },
    video_preview_page_cache: { name: 'Preview', mode: 'video' },
  }
  return routes[module?.key] || null
}

function goModule(module) {
  const target = moduleRoute(module)
  if (!target) {
    return
  }
  modeStore.setMode(target.mode)
  router.push({ name: target.name })
}

function goRankingItem(item) {
  const contentType = String(item?.content_type || '').toLowerCase()
  const source = String(item?.source || '').toLowerCase()
  const id = String(item?.id || '').trim()
  if (!id) {
    return
  }
  if (contentType === 'video') {
    router.push({ name: source === 'preview' ? 'VideoRecommendationDetail' : 'VideoDetail', params: { id } })
    return
  }
  router.push({ name: source === 'preview' ? 'RecommendationDetail' : 'ComicDetail', params: { id } })
}

function goBack() {
  if (window.history.length > 1) {
    router.back()
    return
  }
  router.push({ name: 'Mine' })
}

async function loadOverview() {
  loading.value = true
  try {
    const response = await configApi.getStorageOverview()
    if (response?.code === 200) {
      overview.value = response.data || {}
      return
    }
    showFailToast(response?.msg || '加载存储信息失败')
  } catch (error) {
    console.error('load storage overview failed:', error)
    showFailToast('加载存储信息失败')
  } finally {
    loading.value = false
  }
}

async function loadActiveRanking() {
  const category = activeRanking.value
  rankingLoading.value = true
  try {
    const response = await configApi.getStorageRanking({ category, limit: 12 })
    if (response?.code === 200) {
      const items = Array.isArray(response.data?.items) ? response.data.items : []
      rankingData.value = {
        ...rankingData.value,
        [category]: items,
      }
      rankingTotals.value = {
        ...rankingTotals.value,
        [category]: Number(response.data?.total ?? items.length),
      }
      rankingLoadedKeys.value = new Set([...rankingLoadedKeys.value, category])
      return
    }
    showFailToast(response?.msg || '查询排行失败')
  } catch (error) {
    console.error('load storage ranking failed:', error)
    showFailToast('查询排行失败')
  } finally {
    rankingLoading.value = false
  }
}

function confirmClearModule(module) {
  if (!module?.cache_type) {
    return
  }
  showConfirmDialog({
    title: `清理${module.label}`,
    message: module.cache_type === 'video_preview_page_cache'
      ? '将清理预览库视频的本地预览资源，并重置对应本地缓存字段。确定继续吗？'
      : '只会清理缓存目录，不会删除本地库真实内容。确定继续吗？',
  }).then(() => clearModule(module)).catch(() => {})
}

async function clearModule(module) {
  clearingType.value = module.cache_type
  showLoadingToast({
    message: '正在清理...',
    forbidClick: true,
    duration: 0,
  })
  try {
    const response = await configApi.clearSpecificCache(module.cache_type)
    closeToast()
    if (response?.code === 200) {
      const freed = response?.data?.freed_size_mb ?? 0
      showSuccessToast(`已释放 ${freed} MB`)
      rankingData.value = {}
      rankingTotals.value = {}
      rankingLoadedKeys.value = new Set()
      await loadOverview()
      return
    }
    showFailToast(response?.msg || '清理失败')
  } catch (error) {
    closeToast()
    console.error('clear storage cache failed:', error)
    showFailToast('清理失败')
  } finally {
    clearingType.value = ''
  }
}

onMounted(loadOverview)
</script>

<style scoped>
.storage-page {
  min-height: 100vh;
  color: var(--text-primary);
  padding-bottom: calc(24px + env(safe-area-inset-bottom));
}

.storage-page :deep(.van-nav-bar) {
  background: var(--nav-bg);
  border-bottom: 1px solid var(--border-soft);
}

.refresh-btn {
  border-radius: 999px;
  background: var(--plain-btn-bg);
}

.storage-shell {
  width: min(var(--desktop-page-fluid), 1180px);
  margin: 0 auto;
  padding: clamp(14px, 2vw, 28px);
}

.overview-card,
.notice-card,
.module-card,
.ranking-card {
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(14px);
}

.overview-card {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(190px, 0.42fr);
  gap: clamp(18px, 3vw, 36px);
  align-items: center;
  border-radius: 28px;
  padding: clamp(22px, 4vw, 42px);
}

.overview-card::before {
  content: "";
  position: absolute;
  inset: -35% -18% auto auto;
  width: 360px;
  height: 360px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(89, 160, 255, 0.24), transparent 68%);
  pointer-events: none;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 11px;
  letter-spacing: 0.16em;
  color: var(--brand-600);
  font-weight: 800;
}

.overview-copy h1 {
  margin: 0;
  color: var(--text-strong);
  font-family: var(--font-display);
  font-size: clamp(34px, 7vw, 68px);
  line-height: 0.94;
}

.overview-desc {
  max-width: 520px;
  margin: 16px 0 0;
  color: var(--text-secondary);
  line-height: 1.75;
  font-size: 14px;
}

.donut-wrap {
  display: grid;
  place-items: center;
}

.storage-donut {
  position: relative;
  width: clamp(164px, 22vw, 240px);
  aspect-ratio: 1;
  border-radius: 50%;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.24),
    0 22px 44px rgba(20, 42, 81, 0.16);
  animation: donutIn 560ms var(--ease-standard) both;
}

.storage-donut::after {
  content: "";
  position: absolute;
  inset: 16%;
  border-radius: 50%;
  background: var(--surface-1);
  border: 1px solid var(--border-soft);
  box-shadow: inset 0 10px 24px rgba(22, 39, 68, 0.08);
}

.donut-core {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: grid;
  place-items: center;
  align-content: center;
  color: var(--text-strong);
}

.donut-core span {
  font-size: 36px;
  font-weight: 900;
  line-height: 1;
}

.donut-core small {
  margin-top: 5px;
  color: var(--text-tertiary);
  font-size: 12px;
}

.overview-facts {
  display: grid;
  gap: 12px;
}

.fact {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--border-soft);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.24), rgba(89, 160, 255, 0.08));
}

.fact span {
  display: block;
  color: var(--text-tertiary);
  font-size: 12px;
  margin-bottom: 6px;
}

.fact strong {
  color: var(--text-strong);
  font-size: 18px;
}

.notice-card {
  display: flex;
  gap: 12px;
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 18px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.notice-card .van-icon {
  margin-top: 3px;
  color: var(--brand-600);
}

.notice-card p {
  margin: 0;
  font-size: 13px;
}

.storage-skeleton,
.module-section,
.ranking-section {
  margin-top: 28px;
}

.section-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.section-heading h2 {
  margin: 0;
  color: var(--text-strong);
  font-size: 21px;
}

.section-heading span {
  color: var(--text-tertiary);
  font-size: 13px;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.module-card {
  display: flex;
  flex-direction: column;
  min-height: 210px;
  border-radius: 22px;
  padding: 18px;
  transition:
    transform var(--motion-base) var(--ease-standard),
    box-shadow var(--motion-base) var(--ease-standard),
    border-color var(--motion-base) var(--ease-standard);
}

.module-card:hover {
  transform: translateY(-3px);
  border-color: var(--border-strong);
  box-shadow: var(--shadow-md);
}

.module-top,
.module-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.module-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  box-shadow: 0 0 0 6px rgba(89, 160, 255, 0.08);
}

.module-percent {
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 700;
}

.module-card h3 {
  margin: 18px 0 8px;
  color: var(--text-strong);
  font-size: 17px;
}

.module-card strong {
  color: var(--text-strong);
  font-size: 26px;
  letter-spacing: -0.03em;
}

.module-card p {
  flex: 1;
  margin: 10px 0 18px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.module-footer span {
  color: var(--text-tertiary);
  font-size: 12px;
}

.ranking-tabs {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}

.ranking-tabs button {
  border: 1px solid var(--border-soft);
  border-radius: 16px;
  background: var(--surface-2);
  color: var(--text-secondary);
  padding: 12px 14px;
  text-align: left;
  cursor: pointer;
  transition:
    border-color var(--motion-base) var(--ease-standard),
    background var(--motion-base) var(--ease-standard),
    color var(--motion-base) var(--ease-standard);
}

.ranking-tabs button.active {
  border-color: rgba(89, 160, 255, 0.5);
  background: linear-gradient(135deg, rgba(89, 160, 255, 0.18), rgba(0, 168, 117, 0.08));
  color: var(--text-strong);
}

.ranking-tabs span,
.ranking-tabs small {
  display: block;
}

.ranking-tabs span {
  font-weight: 800;
}

.ranking-tabs small {
  margin-top: 4px;
  color: var(--text-tertiary);
}

.ranking-card {
  overflow: hidden;
  border-radius: 22px;
}

.ranking-empty {
  padding: 34px 18px;
  text-align: center;
  color: var(--text-tertiary);
}

.ranking-row {
  width: 100%;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 14px;
  padding: 15px 18px;
  border: 0;
  border-bottom: 1px solid var(--border-soft);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.ranking-row:last-child {
  border-bottom: 0;
}

.ranking-row:hover {
  background: rgba(89, 160, 255, 0.08);
}

.rank-index {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: var(--surface-3);
  color: var(--brand-600);
  font-weight: 900;
  font-size: 12px;
}

.rank-main {
  min-width: 0;
}

.rank-main strong,
.rank-main small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank-main strong {
  color: var(--text-strong);
  font-size: 14px;
}

.rank-main small {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: 12px;
}

.rank-size {
  color: var(--text-strong);
  font-weight: 900;
  white-space: nowrap;
}

@keyframes donutIn {
  from {
    transform: scale(0.92) rotate(-14deg);
    opacity: 0;
  }
  to {
    transform: scale(1) rotate(0deg);
    opacity: 1;
  }
}

@media (max-width: 960px) {
  .overview-card {
    grid-template-columns: 1fr;
  }

  .donut-wrap {
    order: -1;
  }

  .overview-facts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .module-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .storage-shell {
    width: 100%;
    padding: 12px;
  }

  .overview-card {
    border-radius: 22px;
    padding: 20px;
  }

  .overview-copy h1 {
    font-size: 40px;
  }

  .overview-facts,
  .module-grid,
  .ranking-tabs {
    grid-template-columns: 1fr;
  }

  .section-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }

  .ranking-row {
    grid-template-columns: auto minmax(0, 1fr) auto;
  }

  .ranking-row .van-icon {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .storage-donut,
  .module-card,
  .ranking-tabs button {
    transition: none;
    animation: none;
  }
}
</style>
