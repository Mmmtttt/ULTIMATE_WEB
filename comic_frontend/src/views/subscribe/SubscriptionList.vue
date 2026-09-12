<template>
  <div class="subscription-list-page">
    <section class="subscription-hero">
      <div class="hero-copy">
        <p class="eyebrow">{{ isVideoMode ? 'Actor Watch' : 'Author Watch' }}</p>
        <h1>{{ isVideoMode ? '演员订阅' : '作者订阅' }}</h1>
        <p>{{ isVideoMode ? '追踪演员最新视频，优先使用平台演员页缓存。' : '追踪作者最新漫画，缓存命中时显示最新作品封面。' }}</p>
      </div>
      <div class="hero-stat">
        <strong>{{ filteredItems.length }}</strong>
        <span>已订阅</span>
      </div>
    </section>

    <div class="header-actions">
      <van-search
        v-model="searchKeyword"
        placeholder="搜索已订阅..."
        shape="round"
        background="transparent"
      />
      <div class="header-buttons">
        <van-button 
          type="default" 
          size="small" 
          round 
          :loading="checkingUpdates"
          @click="checkAllUpdates"
        >
          检查更新
        </van-button>
        <van-button icon="plus" type="primary" size="small" round @click="openAddDialog">
          添加
        </van-button>
      </div>
    </div>

    <!-- Content -->
    <div class="content-area">
      <van-loading v-if="loading" class="loading-center" />
      
      <EmptyState
        v-else-if="filteredItems.length === 0"
        title="暂无订阅"
        description="添加订阅以获取更新提醒"
      />

      <div v-else class="subscription-grid" :class="{ 'video-mode': isVideoMode }">
        <article
          v-for="item in pagedItems"
          :key="item.id"
          class="subscription-card"
          :data-testid="isVideoMode ? 'subscription-actor-card' : 'subscription-author-card'"
          @click="goToDetail(item)"
        >
          <van-button
            class="subscription-unsubscribe-btn"
            size="mini"
            type="danger"
            plain
            round
            :data-testid="isVideoMode ? 'subscription-actor-unsubscribe' : 'subscription-author-unsubscribe'"
            :loading="unsubscribingIds.has(String(item.id || ''))"
            @click.stop="unsubscribe(item)"
          >
            取消
          </van-button>

          <div class="subscription-cover" :class="{ 'has-cover': Boolean(getCoverUrl(item)) }">
            <img
              v-if="getCoverUrl(item)"
              :src="getCoverUrl(item)"
              :alt="getLatestTitle(item)"
              loading="lazy"
              decoding="async"
            />
            <div v-else class="cover-placeholder" :style="getPlaceholderStyle(item)">
              <span>{{ getInitials(item.name) }}</span>
            </div>
            <span class="kind-chip">{{ isVideoMode ? '演员' : '作者' }}</span>
            <span v-if="item.new_work_count > 0" class="update-badge">{{ item.new_work_count }} 新</span>
          </div>

          <div class="subscription-body">
            <div class="creator-row">
              <h2>{{ item.name }}</h2>
              <van-icon name="arrow" class="creator-arrow" />
            </div>
            <p class="latest-label">最新作品</p>
            <p class="latest-title">{{ getLatestTitle(item) }}</p>
            <div class="subscription-meta">
              <span>{{ formatCheckTime(item.last_check_time) }}</span>
              <span v-if="item.latest_work_platform">{{ item.latest_work_platform }}</span>
            </div>
          </div>
        </article>
      </div>

      <AppPagination
        v-if="filteredItems.length > pageSize"
        v-model="currentPage"
        class="subscription-pagination"
        :total-items="filteredItems.length"
        :page-size="pageSize"
      />
    </div>

    <!-- Add Subscription Popup -->
    <van-dialog 
      v-model:show="showAddPopup" 
      :title="addDialogTitle"
      show-cancel-button
      :before-close="beforeAddDialogClose"
    >
      <div class="subscription-dialog-body">
        <van-field
          v-model="newSubscriptionName"
          :label="isVideoMode ? '演员' : '作者'"
          :placeholder="isVideoMode ? '输入演员名称' : '输入作者名称'"
          clearable
        />

        <template v-if="isVideoMode">
          <button class="manual-source-toggle" type="button" @click="showManualActorSource = !showManualActorSource">
            <span>
              <strong>手动指定来源</strong>
              <small>用于同名演员或自动识别不准</small>
            </span>
            <van-icon :name="showManualActorSource ? 'arrow-up' : 'arrow-down'" />
          </button>

          <div v-if="showManualActorSource" class="manual-source-panel">
            <van-field
              v-model="manualActorPlatform"
              label="平台"
              placeholder="javdb"
              clearable
            />
            <van-field
              v-model="manualActorSource"
              label="链接/ID"
              placeholder="https://javdb.com/actors/0R1n3 或 0R1n3"
              clearable
            />
            <p class="manual-source-hint">
              留空则按演员名自动订阅；填写后会优先使用指定 ID 查询作品。
            </p>
          </div>
        </template>
      </div>
    </van-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useModeStore, useActorStore, useAuthorStore } from '@/stores'
import EmptyState from '@/components/common/EmptyState.vue'
import AppPagination from '@/components/common/AppPagination.vue'
import { showToast, showConfirmDialog } from 'vant'
import { buildCoverUrl } from '@/api/image'
import { useClientPagination } from '@/composables/useClientPagination'

const router = useRouter()
const modeStore = useModeStore()
const actorStore = useActorStore()
const authorStore = useAuthorStore()

const loading = ref(false)
const items = ref([])
const searchKeyword = ref('')
const showAddPopup = ref(false)
const newSubscriptionName = ref('')
const showManualActorSource = ref(false)
const manualActorPlatform = ref('javdb')
const manualActorSource = ref('')
const checkingUpdates = ref(false)
const unsubscribingIds = reactive(new Set())

const isVideoMode = computed(() => modeStore.isVideoMode)
const currentStore = computed(() => isVideoMode.value ? actorStore : authorStore)
const addDialogTitle = computed(() => isVideoMode.value ? '添加演员订阅' : '添加作者订阅')

const filteredItems = computed(() => {
  const safeItems = items.value || []
  if (!searchKeyword.value) return safeItems
  return safeItems.filter(item => 
    item.name?.toLowerCase().includes(searchKeyword.value.toLowerCase())
  )
})

const paginationStorageKey = computed(() => `subscription_list_${isVideoMode.value ? 'video' : 'comic'}`)
const {
  pageSize,
  currentPage,
  pagedItems,
  goFirst
} = useClientPagination(filteredItems, paginationStorageKey)

function getCoverCandidate(item) {
  const latestWork = item?.latest_work && typeof item.latest_work === 'object' ? item.latest_work : {}
  return String(
    item?.latest_work_cover_url ||
    latestWork.cover_path_local ||
    latestWork.cover_path ||
    latestWork.cover_url ||
    item?.avatar_url ||
    ''
  ).trim()
}

function getCoverUrl(item) {
  const cover = getCoverCandidate(item)
  return cover ? buildCoverUrl(cover) : ''
}

function getLatestTitle(item) {
  const latestWork = item?.latest_work && typeof item.latest_work === 'object' ? item.latest_work : {}
  return String(item?.last_work_title || latestWork.title || '').trim() || '暂无更新'
}

function getInitials(name) {
  const text = String(name || '').trim()
  if (!text) return isVideoMode.value ? '演' : '作'
  return Array.from(text).slice(0, 2).join('')
}

function getPlaceholderStyle(item) {
  const seed = Array.from(String(item?.name || '')).reduce((sum, char) => sum + char.charCodeAt(0), 0)
  const hue = seed % 360
  return {
    background: `linear-gradient(135deg, hsl(${hue} 72% 38%), hsl(${(hue + 48) % 360} 78% 58%))`
  }
}

function formatCheckTime(value) {
  const text = String(value || '').trim()
  if (!text) return '尚未检查'
  const normalized = text.replace('T', ' ')
  return `检查 ${normalized.slice(0, 16)}`
}

async function loadData() {
  loading.value = true
  items.value = []
  
  try {
    await currentStore.value.fetchList()
    items.value = currentStore.value.actors || []
  } catch (e) {
    showToast('加载失败')
  } finally {
    loading.value = false
  }
}

async function checkAllUpdates() {
  if (checkingUpdates.value) return
  checkingUpdates.value = true
  try {
    const res = await currentStore.value.checkUpdates()
    if (res) {
      await loadData()
      const total = res?.total_new_works || 0
      if (total > 0) {
        showToast(`共 ${total} 个新作品`)
      } else {
        showToast('暂无新作品')
      }
    } else {
      showToast('检查更新失败')
    }
  } catch (e) {
    showToast('检查更新失败')
  } finally {
    checkingUpdates.value = false
  }
}

function openAddDialog() {
  resetAddForm()
  showAddPopup.value = true
}

function resetAddForm() {
  newSubscriptionName.value = ''
  showManualActorSource.value = false
  manualActorPlatform.value = 'javdb'
  manualActorSource.value = ''
}

function extractActorIdFromManualSource(value) {
  const raw = String(value || '').trim()
  if (!raw) return ''

  const actorPathMatch = raw.match(/\/(?:actors?|stars?|persons?)\/([^/?#]+)/i)
  if (actorPathMatch?.[1]) {
    return decodeURIComponent(actorPathMatch[1]).trim()
  }

  try {
    const url = new URL(raw.includes('://') ? raw : `https://${raw}`)
    const segments = url.pathname.split('/').filter(Boolean)
    const markerIndex = segments.findIndex(segment =>
      ['actor', 'actors', 'star', 'stars', 'person', 'persons'].includes(segment.toLowerCase())
    )
    if (markerIndex >= 0 && segments[markerIndex + 1]) {
      return decodeURIComponent(segments[markerIndex + 1]).trim()
    }
  } catch (_e) {
    // Plain actor IDs are valid manual input.
  }

  return raw
}

function buildManualActorSubscribeOptions(actorName) {
  if (!isVideoMode.value) {
    return {}
  }

  const sourceValue = String(manualActorSource.value || '').trim()
  const platform = String(manualActorPlatform.value || '').trim().toLowerCase()
  if (!sourceValue) {
    return {}
  }
  if (!platform) {
    return { error: '请填写平台名称' }
  }

  const actorId = extractActorIdFromManualSource(sourceValue)
  if (!actorId) {
    return { error: '请填写有效的演员链接或ID' }
  }

  return {
    actorRefs: [
      {
        platform,
        actor_id: actorId,
        actor_name: actorName,
        actor_url: sourceValue.includes('/') ? sourceValue : ''
      }
    ]
  }
}

async function goToDetail(item) {
  const subscriptionId = String(item?.id || '').trim()
  if (subscriptionId && Number(item?.new_work_count || 0) > 0) {
    try {
      await currentStore.value.clearNewCount(subscriptionId)
      items.value = (items.value || []).map(entry => {
        if (String(entry?.id || '') !== subscriptionId) {
          return entry
        }
        return {
          ...entry,
          new_work_count: 0
        }
      })
    } catch (_) {
      // Ignore clear failure and continue navigation.
    }
  }
  router.push(`/creator/${encodeURIComponent(item.name)}`)
}

async function addSubscription() {
  const subscriptionName = String(newSubscriptionName.value || '').trim()
  if (!subscriptionName) {
    showToast(isVideoMode.value ? '请输入演员名称' : '请输入作者名称')
    return false
  }
  
  try {
    const options = buildManualActorSubscribeOptions(subscriptionName)
    if (options.error) {
      showToast(options.error)
      return false
    }

    const res = await currentStore.value.subscribe(subscriptionName, options)
    if (res.success) {
      showToast('订阅成功')
    } else {
      showToast(res.message || '订阅失败')
      return false
    }
    await loadData()
    resetAddForm()
    return true
  } catch (e) {
    showToast('操作失败')
    return false
  }
}

async function beforeAddDialogClose(action) {
  if (action !== 'confirm') {
    resetAddForm()
    return true
  }

  return addSubscription()
}

async function unsubscribe(item) {
  const subId = String(item?.id || '').trim()
  if (!subId || unsubscribingIds.has(subId)) return

  try {
    await showConfirmDialog({
      title: '确认取消订阅',
      message: `确定取消订阅 ${item.name} 吗？`
    })
  } catch (_e) {
    return
  }

  unsubscribingIds.add(subId)
  try {
    const success = await currentStore.value.unsubscribe(subId)
    if (!success) {
      showToast('操作失败')
      return
    }

    showToast('已取消')
    await loadData()
  } catch (_e) {
    showToast('操作失败')
  } finally {
    unsubscribingIds.delete(subId)
  }
}

watch(() => modeStore.currentMode, () => {
  goFirst()
  loadData()
})

watch(searchKeyword, () => {
  goFirst()
})

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.subscription-list-page {
  padding: 12px 12px 80px;
}

.subscription-hero {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 14px;
  margin: 0 0 10px;
  padding: clamp(16px, 3vw, 24px);
  border: 1px solid var(--border-soft);
  border-radius: 24px;
  background:
    radial-gradient(circle at 10% 10%, rgba(47, 116, 255, 0.18), transparent 34%),
    radial-gradient(circle at 92% 12%, rgba(255, 186, 73, 0.2), transparent 32%),
    linear-gradient(135deg, var(--surface-2), var(--surface-1));
  box-shadow: var(--shadow-sm);
}

.hero-copy {
  min-width: 0;
}

.eyebrow {
  margin: 0 0 6px;
  color: var(--brand-600);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-copy h1 {
  margin: 0;
  color: var(--text-primary);
  font-size: clamp(24px, 4vw, 34px);
  line-height: 1.15;
}

.hero-copy p:last-child {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.6;
}

.hero-stat {
  min-width: 88px;
  padding: 14px 16px;
  border: 1px solid rgba(47, 116, 255, 0.16);
  border-radius: 20px;
  background: rgba(47, 116, 255, 0.08);
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: center;
}

.hero-stat strong {
  color: var(--brand-600);
  font-size: 28px;
  line-height: 1;
}

.hero-stat span {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.header-actions {
  display: grid;
  gap: 10px;
  padding: 10px 16px;
  background: var(--surface-2);
  position: sticky;
  top: 0;
  z-index: 10;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  margin: 0;
  box-shadow: var(--shadow-xs);
}

.header-actions .van-search {
  padding: 0;
}

.header-buttons {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}

.loading-center {
  padding: 40px;
  text-align: center;
}

.subscription-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 16px;
  padding: 16px 2px 0;
}

.subscription-grid.video-mode {
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
}

.subscription-pagination {
  margin: 18px auto 0;
}

.subscription-card {
  position: relative;
  overflow: hidden;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 22px;
  padding: 0;
  display: flex;
  flex-direction: column;
  text-align: left;
  box-shadow: var(--shadow-xs);
  cursor: pointer;
  transition:
    transform var(--motion-fast) var(--ease-standard),
    border-color var(--motion-fast) var(--ease-standard),
    box-shadow var(--motion-fast) var(--ease-standard);
}

.subscription-card:hover {
  transform: translateY(-3px);
  border-color: rgba(47, 116, 255, 0.32);
  box-shadow: var(--shadow-sm);
}

.subscription-unsubscribe-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 3;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
}

.subscription-cover {
  position: relative;
  aspect-ratio: 3 / 4;
  overflow: hidden;
  background:
    linear-gradient(145deg, rgba(47, 116, 255, 0.16), rgba(255, 186, 73, 0.12)),
    var(--surface-3, rgba(148, 163, 184, 0.12));
}

.video-mode .subscription-cover {
  aspect-ratio: 16 / 10;
}

.subscription-cover img,
.cover-placeholder {
  width: 100%;
  height: 100%;
  display: block;
}

.subscription-cover img {
  object-fit: cover;
  transform: scale(1.01);
}

.cover-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.92);
  font-size: clamp(28px, 7vw, 54px);
  font-weight: 900;
  letter-spacing: 0.02em;
}

.cover-placeholder::after {
  content: "";
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 30% 20%, rgba(255, 255, 255, 0.28), transparent 28%),
    linear-gradient(180deg, transparent, rgba(2, 8, 18, 0.22));
}

.cover-placeholder span {
  position: relative;
  z-index: 1;
}

.kind-chip,
.update-badge {
  position: absolute;
  z-index: 2;
  border-radius: 999px;
  backdrop-filter: blur(10px);
  font-size: 11px;
  font-weight: 800;
}

.kind-chip {
  left: 10px;
  top: 10px;
  padding: 4px 9px;
  color: #fff;
  background: rgba(2, 8, 18, 0.48);
}

.update-badge {
  left: 10px;
  bottom: 10px;
  padding: 5px 10px;
  color: #fff;
  background: linear-gradient(135deg, #ff4d4f, #ff8a00);
  box-shadow: 0 8px 18px rgba(238, 10, 36, 0.28);
}

.subscription-body {
  padding: 13px 14px 15px;
}

.creator-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.creator-row h2 {
  margin: 0;
  color: var(--text-strong);
  font-size: 17px;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.creator-arrow {
  flex-shrink: 0;
  color: var(--text-tertiary);
}

.latest-label {
  margin: 10px 0 3px;
  color: var(--text-tertiary);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
}

.latest-title {
  min-height: 38px;
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.subscription-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 11px;
  color: var(--text-tertiary);
  font-size: 11px;
}

.subscription-meta span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.subscription-dialog-body {
  padding: 8px 0 4px;
}

.manual-source-toggle {
  width: calc(100% - 32px);
  margin: 10px 16px 0;
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(47, 116, 255, 0.08), rgba(255, 255, 255, 0.02));
  color: var(--text-strong);
  text-align: left;
  cursor: pointer;
}

.manual-source-toggle strong,
.manual-source-toggle small {
  display: block;
}

.manual-source-toggle strong {
  font-size: 14px;
  line-height: 1.3;
}

.manual-source-toggle small {
  margin-top: 2px;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.4;
}

.manual-source-panel {
  margin: 10px 16px 0;
  padding: 10px 0 12px;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  background: var(--surface-1);
  overflow: hidden;
}

.manual-source-panel :deep(.van-cell) {
  background: transparent;
}

.manual-source-hint {
  margin: 6px 16px 0;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.5;
}

@media (min-width: 768px) {
  .header-actions {
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
  }
}

@media (max-width: 767px) {
  .subscription-list-page {
    padding: 10px 10px 72px;
  }

  .subscription-hero {
    flex-direction: column;
    border-radius: 20px;
  }

  .hero-stat {
    width: 100%;
    min-width: 0;
    flex-direction: row;
    align-items: baseline;
    justify-content: center;
    gap: 8px;
  }

  .header-actions {
    top: calc(var(--mobile-header-offset, 0px) + 8px);
    padding: 10px 12px;
  }

  .subscription-grid,
  .subscription-grid.video-mode {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    padding-top: 12px;
  }

  .subscription-card {
    border-radius: 18px;
  }

  .subscription-body {
    padding: 10px 11px 12px;
  }

  .creator-row h2 {
    font-size: 15px;
  }

  .latest-title {
    min-height: 34px;
    font-size: 12px;
  }

  .subscription-unsubscribe-btn {
    padding-inline: 8px;
  }
}
</style>

