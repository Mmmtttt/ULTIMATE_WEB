<template>
  <div class="subscription-list-page">
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

      <!-- Video Mode: Actor Grid -->
      <div v-else-if="isVideoMode" class="actor-grid">
        <div 
          v-for="actor in filteredItems" 
          :key="actor.id" 
          class="actor-card"
          data-testid="subscription-actor-card"
          @click="goToDetail(actor)"
        >
          <van-button
            class="actor-unsubscribe-btn"
            size="mini"
            type="danger"
            plain
            round
            data-testid="subscription-actor-unsubscribe"
            :loading="unsubscribingIds.has(String(actor.id || ''))"
            @click.stop="unsubscribe(actor)"
          >
            取消
          </van-button>
          <div class="actor-avatar">
            <!-- Placeholder for avatar if API provides one, currently using icon -->
            <van-icon name="user-circle-o" size="40" color="#ddd" />
            <div v-if="actor.new_work_count > 0" class="badge">{{ actor.new_work_count }}</div>
          </div>
          <div class="actor-name">{{ actor.name }}</div>
          <div class="actor-update">{{ actor.last_work_title || '暂无更新' }}</div>
        </div>
      </div>

      <!-- Comic Mode: Author List -->
      <div v-else class="author-list">
        <div
          v-for="author in filteredItems"
          :key="author.id"
          class="author-card"
          data-testid="subscription-author-card"
          @click="goToDetail(author)"
        >
          <div class="author-main">
            <div class="author-name-row">
              <div class="author-name">{{ author.name }}</div>
              <van-tag v-if="author.new_work_count > 0" type="danger" round class="author-badge">
                {{ author.new_work_count }}
              </van-tag>
            </div>
            <div class="author-update">{{ author.last_work_title || '暂无更新' }}</div>
          </div>

          <div class="author-side">
            <van-button
              size="mini"
              type="danger"
              plain
              round
              class="author-unsubscribe-btn"
              data-testid="subscription-author-unsubscribe"
              :loading="unsubscribingIds.has(String(author.id || ''))"
              @click.stop="unsubscribe(author)"
            >
              取消订阅
            </van-button>
            <van-icon name="arrow" class="author-arrow" />
          </div>
        </div>
      </div>
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
import { showToast, showConfirmDialog } from 'vant'

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
  loadData()
})

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.subscription-list-page {
  padding-bottom: 80px;
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
  border-radius: 14px;
  margin: 10px 10px 0;
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

.actor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 16px;
  padding: 16px;
}

.actor-card {
  position: relative;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  box-shadow: 0 8px 18px rgba(2, 8, 18, 0.34);
  cursor: pointer;
}

.actor-unsubscribe-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 2;
}

.actor-avatar {
  position: relative;
  margin-bottom: 8px;
}

.badge {
  position: absolute;
  top: -4px;
  right: -4px;
  background: #ee0a24;
  color: #fff;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
  border: 2px solid #fff;
}

.actor-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-strong);
  margin-bottom: 4px;
}

.actor-update {
  font-size: 11px;
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}

.author-list {
  display: grid;
  gap: 12px;
  padding: 12px 16px 0;
}

.author-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid var(--border-soft);
  background: var(--surface-2);
  box-shadow: 0 10px 22px rgba(17, 27, 45, 0.08);
  cursor: pointer;
  transition:
    transform var(--motion-fast) var(--ease-standard),
    border-color var(--motion-fast) var(--ease-standard),
    box-shadow var(--motion-fast) var(--ease-standard);
}

.author-card:hover {
  transform: translateY(-2px);
  border-color: rgba(47, 116, 255, 0.28);
  box-shadow: 0 16px 28px rgba(17, 27, 45, 0.12);
}

.author-main {
  min-width: 0;
  flex: 1;
}

.author-name-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.author-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-strong);
}

.author-badge {
  flex-shrink: 0;
}

.author-update {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.author-side {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.author-arrow {
  color: var(--text-tertiary);
  font-size: 16px;
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
  .header-actions {
    top: calc(var(--mobile-header-offset, 0px) + 8px);
    margin: 8px 8px 0;
    padding: 10px 12px;
  }

  .actor-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    padding: 12px;
  }

  .author-list {
    padding: 12px 10px 0;
    gap: 10px;
  }

  .author-card {
    flex-direction: column;
    align-items: stretch;
    padding: 14px;
  }

  .author-side {
    justify-content: space-between;
  }

  .author-unsubscribe-btn {
    min-width: 92px;
  }
}
</style>

