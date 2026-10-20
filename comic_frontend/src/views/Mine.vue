<template>
  <div class="mine-page">
    <div class="stats-overview">
      <div class="stats-grid">
        <button
          v-for="item in statCards"
          :key="item.key"
          type="button"
          class="stat-card"
          :title="item.hint"
          :aria-label="`${item.label} ${item.value}，${item.hint}`"
          @click="openStat(item)"
        >
          <!-- 纵向排列时自上而下必须是：图标 → 文字说明 → 数据，所以 DOM 顺序按此写，
               横向排版再靠 grid-template-areas 把数据放回说明上方。 -->
          <span class="stat-icon"><van-icon :name="item.icon" /></span>
          <span class="stat-label">{{ item.label }}</span>
          <span class="stat-value">{{ item.value }}</span>
          <van-icon name="arrow" class="stat-arrow" />
        </button>
      </div>
    </div>
    
    <van-cell-group class="mine-menu" inset>
      <!-- 本地导入与按 ID 导入合并为同一个入口，进去用选项卡区分 -->
      <van-cell title="导入" icon="add-o" to="/import" is-link />
      <van-cell title="任务中心" icon="clock-o" to="/import-tasks" is-link>
        <template #value>
          <van-tag v-if="activeTaskCount > 0" type="primary" round>
            {{ activeTaskCount }}
          </van-tag>
        </template>
      </van-cell>
    </van-cell-group>

    <van-cell-group class="mine-menu" inset>
      <van-cell title="数据同步" icon="share-o" to="/sync" is-link />
      <van-cell title="数据库整理" icon="brush-o" to="/organize" is-link />
      <van-cell title="存储管理" icon="tosend" to="/storage" is-link />
    </van-cell-group>

    <van-cell-group class="mine-menu" inset>
      <van-cell title="系统设置" icon="setting-o" to="/config" is-link />
    </van-cell-group>

    <van-cell-group v-if="authEnabled" class="mine-menu" inset>
      <van-cell title="退出登录" icon="logout" @click="handleLogout" is-link>
        <template #value>
          <span style="color: var(--text-tertiary); font-size: 13px;">{{ currentModeText }}</span>
        </template>
      </van-cell>
    </van-cell-group>
    
    <div class="about">
      <div class="about-card">
        <div class="about-meta">
          <p class="version">版本 {{ appVersionLabel }}</p>
          <p class="copyright">© 2026 Ultimate Web</p>
          <p class="mmmtttt">个人漫画电影内容管理小工具，为避免隐私泄露，禁止部署在公网</p>
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
    
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useComicStore, useVideoStore, useCacheStore, useTagStore, useListStore, useModeStore, useImportTaskStore, useAppUpdateStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { showFailToast, showConfirmDialog, showSuccessToast } from 'vant'
import { openReleasePage } from '@/services/appUpdate'
import { useDevice } from '@/composables/useDevice'
import { comicApi, videoApi } from '@/api'

const router = useRouter()
const modeStore = useModeStore()
const authStore = useAuthStore()
const comicStore = useComicStore()
const videoStore = useVideoStore()
const cacheStore = useCacheStore()
const tagStore = useTagStore()
const listStore = useListStore()
const importTaskStore = useImportTaskStore()
const appUpdateStore = useAppUpdateStore()
const { isMobile } = useDevice()

const isVideoMode = computed(() => modeStore.isVideoMode)
const authEnabled = computed(() => authStore.enabled)
const currentModeText = computed(() => authStore.mode === 'normal' ? '正常模式' : '隐私模式')

// State

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

const tagManagePath = '/tags'

const favoritesPath = computed(() => (
  isVideoMode.value ? '/list/list_favorites_video' : '/list/list_favorites_comic'
))

const favoritesCount = computed(() => {
  const list = listStore.favoritesList
  if (!list) return '—'
  return Number(isVideoMode.value ? (list.video_count || 0) : (list.comic_count || 0))
})

const trashCount = ref(null)

const statCards = computed(() => [
  { key: 'count', icon: 'photo-o', value: stats.value.count, label: '内容', to: '/library', hint: '进入本地库' },
  { key: 'read', icon: 'bookmark-o', value: stats.value.read, label: '历史', to: '/history', hint: '进入阅读记录' },
  { key: 'tags', icon: 'label-o', value: stats.value.tags, label: '标签', to: tagManagePath, hint: '进入标签管理' },
  { key: 'lists', icon: 'orders-o', value: stats.value.lists, label: '清单', to: '/lists', hint: '进入我的清单' },
  { key: 'favorites', icon: 'star-o', value: favoritesCount.value, label: '收藏', to: favoritesPath.value, hint: '进入我的收藏' },
  { key: 'trash', icon: 'delete-o', value: trashCount.value === null ? '—' : trashCount.value, label: '回收站', to: '/trash', hint: '进入回收站' }
])

async function loadTrashCount() {
  try {
    const api = isVideoMode.value ? videoApi : comicApi
    const response = await api.getTrashList()
    const data = response?.data
    const items = Array.isArray(data) ? data : (Array.isArray(data?.list) ? data.list : [])
    trashCount.value = items.length
  } catch (_) {
    trashCount.value = null
  }
}

function openStat(item) {
  if (!item?.to) return
  router.push(item.to)
}

const activeTaskCount = computed(() => importTaskStore.activeTaskCount)
const appVersionLabel = computed(() => String(import.meta.env.VITE_APP_VERSION || '0.0.0').trim() || '0.0.0')
const updateChecking = computed(() => appUpdateStore.checking)
const hasNewVersion = computed(() => appUpdateStore.hasUpdate)
const updateStatusText = computed(() => appUpdateStore.statusText)
const updateCheckedAtText = computed(() => appUpdateStore.checkedAtText)
const updateReleaseUrl = computed(() => appUpdateStore.releaseUrl)

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


async function handleLogout() {
  try {
    await showConfirmDialog({
      title: '退出登录',
      message: '确定要退出登录吗？退出后将进入隐私模式。',
      confirmButtonText: '退出',
      cancelButtonText: '取消'
    })
  } catch (e) {
    // 用户取消
    return
  }

  try {
    await authStore.logout()
    showSuccessToast('已退出登录')
  } catch (e) {
    showFailToast('退出失败')
    return
  }

  // 跳转到登录页
  router.replace('/login')
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
  loadTrashCount()
})

watch(() => modeStore.currentMode, async () => {
  loadTrashCount()
})
</script>

<style scoped>
.mine-page {
  padding: 2px 0 20px;
}

.stats-overview {
  background: var(--surface-2);
  padding: 12px;
  margin: 12px 16px;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  box-shadow: var(--shadow-sm);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

@media (min-width: 768px) {
  .stats-grid {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }
}

.stat-card {
  min-width: 0;
  min-height: 66px;
  border: 1px solid var(--border-soft);
  border-radius: 16px;
  background: var(--surface-1);
  display: grid;
  grid-template-areas:
    "icon value"
    "icon label";
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  column-gap: 8px;
  padding: 10px;
  position: relative;
  appearance: none;
  -webkit-appearance: none;
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.18s ease, background-color 0.18s ease, transform 0.12s ease;
}

.stat-card:hover {
  border-color: rgba(89, 160, 255, 0.45);
  background: var(--surface-3);
}

.stat-card:active {
  transform: scale(0.98);
}

.stat-card:focus-visible {
  outline: 2px solid var(--brand-500);
  outline-offset: 2px;
}

.stat-arrow {
  position: absolute;
  right: 8px;
  bottom: 8px;
  font-size: 10px;
  color: var(--text-tertiary);
  opacity: 0.5;
}

.stat-icon {
  grid-area: icon;
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 11px;
  background: rgba(89, 160, 255, 0.12);
  color: var(--brand-600);
  font-size: 17px;
}

.stat-value {
  grid-area: value;
  color: var(--text-strong);
  font-size: 17px;
  font-weight: 800;
  line-height: 1.1;
}

.stat-label {
  grid-area: label;
  color: var(--text-secondary);
  font-size: 12px;
  white-space: nowrap;
}

.mine-menu {
  margin: 0 16px 12px;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  overflow: hidden;
  box-shadow: var(--shadow-xs);
}

.mine-menu :deep(.van-cell) {
  background: transparent;
  min-height: 52px;
}

.mine-menu :deep(.van-cell__left-icon) {
  width: 30px;
  height: 30px;
  margin-right: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 11px;
  background: rgba(89, 160, 255, 0.12);
  color: var(--brand-600);
  font-size: 16px;
}

.about {
  padding: 16px 16px;
  color: var(--text-tertiary);
}

.about-card {
  width: 100%;
  padding: 16px;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
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

@media (max-width: 767px) {
  .stats-overview {
    padding: 8px;
    border-radius: 16px;
  }

  .stats-grid {
    gap: 6px;
  }

  .stat-card {
    min-height: 56px;
    /* 纵向排列时自上而下：图标 → 文字说明 → 数据 */
    grid-template-areas:
      "icon"
      "label"
      "value";
    grid-template-columns: 1fr;
    justify-items: center;
    row-gap: 3px;
    padding: 8px 4px;
  }

  .stat-icon {
    width: 24px;
    height: 24px;
    border-radius: 9px;
    font-size: 14px;
  }

  .stat-value {
    font-size: 14px;
  }

  .stat-label {
    font-size: 10px;
  }

  .stats-overview,
  .mine-menu {
    margin-inline: 10px;
  }

  .about {
    padding: 12px 10px;
  }

  .update-actions {
    justify-content: flex-start;
  }

  .update-actions .van-button {
    flex: 1;
  }

}

</style>
