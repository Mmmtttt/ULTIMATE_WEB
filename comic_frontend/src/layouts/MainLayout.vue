<template>
  <div class="main-layout" :class="{ dragging: isDragging }">
    <!-- Desktop Sidebar -->
    <aside v-if="isDesktop" class="sidebar" :class="{ collapsed: sidebarCollapsed, hidden: sidebarHidden, dragging: isDragging }" :style="{ width: sidebarWidthPx }">
      <div class="sidebar-inner">
        <div class="sidebar-header">
          <div class="logo">Ultimate</div>
          <div class="mode-switch-wrap" :class="{ hidden: sidebarCollapsed }">
            <ModeSwitch class="sidebar-mode-switch" />
          </div>
        </div>
        
        <nav class="sidebar-nav">
          <router-link to="/library" class="nav-item" active-class="active">
            <van-icon name="home-o" />
            <span>本地库</span>
          </router-link>
          <router-link to="/preview" class="nav-item" active-class="active">
            <van-icon name="eye-o" />
            <span>预览库</span>
          </router-link>
          <router-link to="/random-feed" class="nav-item" active-class="active">
            <van-icon name="fire-o" />
            <span>随机流</span>
          </router-link>
          <router-link v-if="showTeleDriveNav" to="/teledrive-import" class="nav-item" active-class="active">
            <van-icon name="exchange" />
            <span>TeleDrive</span>
          </router-link>
          <router-link to="/subscribe" class="nav-item" active-class="active">
            <van-icon name="star-o" />
            <span>订阅</span>
          </router-link>
          <router-link to="/mine" class="nav-item" active-class="active">
            <van-icon name="user-o" />
            <span>管理</span>
          </router-link>
        </nav>

        <div class="mmmtttt-footer">github@Mmmtttt</div>
        <div class="sidebar-footer">  
          <router-link to="/search" class="nav-item search-btn">
            <van-icon name="search" />
            <span>全网搜索</span>
          </router-link>
        </div>
      </div>

      <button
        class="sidebar-toggle"
        @mousedown.prevent="startDrag"
        @click.prevent
        :title="sidebarHidden ? '展开菜单' : '收起菜单'"
      >
        <van-icon :name="sidebarHidden ? 'arrow' : 'arrow-left'" />
      </button>
    </aside>

    <!-- Mobile Top Navbar -->
    <header v-if="isMobile" class="mobile-header">
      <div class="header-content">
        <div class="page-title">{{ pageTitle }}</div>
        <ModeSwitch class="header-mode-switch" />
      </div>
    </header>

    <!-- Main Content -->
    <main
      class="main-content"
      :class="{
        'with-sidebar': isDesktop,
        'sidebar-collapsed-layout': isDesktop && sidebarCollapsed,
        'sidebar-hidden-layout': isDesktop && sidebarHidden,
        'with-header': isMobile,
        'with-tabbar': isMobile,
        'random-feed-immersive': isRandomFeedRoute
      }"
      :style="isDesktop ? { marginLeft: sidebarWidthPx, width: 'calc(100% - ' + sidebarWidthPx + ')' } : {}"
    >
      <router-view v-slot="{ Component }">
        <transition name="slide-left" mode="out-in">
          <keep-alive :include="cachedViewNames">
            <component :is="Component" />
          </keep-alive>
        </transition>
      </router-view>
    </main>

    <!-- Mobile Bottom Tabbar -->
    <van-tabbar v-if="isMobile" route fixed>
      <van-tabbar-item to="/library" icon="home-o">本地库</van-tabbar-item>
      <van-tabbar-item to="/preview" icon="eye-o">预览库</van-tabbar-item>
      <van-tabbar-item to="/random-feed" icon="fire-o">随机流</van-tabbar-item>
      <van-tabbar-item v-if="showTeleDriveNav" to="/teledrive-import" icon="exchange">TeleDrive</van-tabbar-item>
      <van-tabbar-item to="/subscribe" icon="star-o">订阅</van-tabbar-item>
      <van-tabbar-item to="/mine" icon="user-o">管理</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useDevice } from '@/composables/useDevice'
import ModeSwitch from '@/components/common/ModeSwitch.vue'
import { comicApi } from '@/api/comic'
import { useRuntimeStore } from '@/stores'

const { isDesktop, isMobile } = useDevice()
const route = useRoute()
const runtimeStore = useRuntimeStore()

// keep-alive 缓存的视图：从详情页返回时不重新请求数据
const cachedViewNames = ['Library', 'Preview', 'RandomFeed', 'Subscribe', 'Mine']

const showTeleDriveNav = ref(false)
const sidebarState = ref(0) // 0=展开, 1=仅图标, 2=隐藏
const SIDEBAR_WIDTHS = [248, 64, 0] // 对应三个状态的宽度

const dragWidth = ref(null)  // 拖拽中的实时宽度, null=未拖拽
const isDragging = ref(false)
const dragStartX = ref(0)
const dragStartWidth = ref(0)
const dragMoved = ref(false) // 是否发生了实际拖拽移动

const sidebarWidthPx = computed(() => {
  if (dragWidth.value !== null) return dragWidth.value + 'px'
  return SIDEBAR_WIDTHS[sidebarState.value] + 'px'
})

const sidebarCurrentWidth = computed(() =>
  dragWidth.value !== null ? dragWidth.value : SIDEBAR_WIDTHS[sidebarState.value]
)

const sidebarCollapsed = computed(() => sidebarCurrentWidth.value <= SIDEBAR_WIDTHS[0] * 0.70)
const sidebarHidden = computed(() => sidebarCurrentWidth.value <= SIDEBAR_WIDTHS[1] * 0.35)
const isRandomFeedRoute = computed(() => route.path === '/random-feed')

const pageTitle = computed(() => {
  const title = route.meta?.title
  if (title) return title
  switch (route.path) {
    case '/library': return '本地库'
    case '/preview': return '预览库'
    case '/random-feed': return '随机流'
    case '/teledrive-import': return 'TeleDrive'
    case '/subscribe': return '订阅'
    case '/mine': return '管理'
    case '/sync': return '数据同步'
    case '/search': return '全网搜索'
    case '/lists': return '清单管理'
    case '/tags': return '标签管理'
    case '/video-tags': return '视频标签管理'
    case '/config': return '系统设置'
    case '/trash': return '回收站'
    case '/import-tasks': return '任务中心'
    case '/comic-local-import': return '本地漫画导入'
    case '/video-local-import': return '本地视频导入'
    default: return 'Ultimate'
  }
})

onMounted(() => {
  loadTeleDriveNavState()
  window.addEventListener('mousemove', onDragMove)
  window.addEventListener('mouseup', onDragEnd)
})

// 运行时状态加载后重试，以及路由切换时重试
watch(() => runtimeStore.loaded, (loaded) => { if (loaded) loadTeleDriveNavState() })
watch(() => route.path, () => { loadTeleDriveNavState() })

onUnmounted(() => {
  window.removeEventListener('mousemove', onDragMove)
  window.removeEventListener('mouseup', onDragEnd)
})

function snapToNearest(width) {
  let best = 0
  let bestDist = Infinity
  for (let i = 0; i < SIDEBAR_WIDTHS.length; i++) {
    const dist = Math.abs(width - SIDEBAR_WIDTHS[i])
    if (dist < bestDist) {
      bestDist = dist
      best = i
    }
  }
  sidebarState.value = best
}

function startDrag(e) {
  isDragging.value = true
  dragMoved.value = false
  dragStartX.value = e.clientX
  dragStartWidth.value = SIDEBAR_WIDTHS[sidebarState.value]
  dragWidth.value = dragStartWidth.value
}

function onDragMove(e) {
  if (!isDragging.value) return
  const delta = e.clientX - dragStartX.value
  let newWidth = dragStartWidth.value + delta
  newWidth = Math.max(0, Math.min(SIDEBAR_WIDTHS[0], newWidth))
  dragWidth.value = newWidth
  if (Math.abs(delta) > 4) dragMoved.value = true
}

function onDragEnd() {
  if (!isDragging.value) return
  isDragging.value = false

  if (!dragMoved.value) {
    // 点击行为：展开 ↔ 隐藏
    sidebarState.value = sidebarState.value === 0 ? 2 : 0
  } else {
    // 拖拽行为：吸附到最近状态
    snapToNearest(dragWidth.value)
  }
  dragWidth.value = null
}

async function loadTeleDriveNavState() {
  try {
    await runtimeStore.fetchRuntime()
    if (!runtimeStore.thirdPartyEnabled) {
      showTeleDriveNav.value = false
      return
    }

    const response = await comicApi.getThirdPartyConfig()
    if (response.code !== 200) {
      showTeleDriveNav.value = false
      return
    }
    const data = response.data || {}
    const adapters = data.adapters || {}
    const schema = data.schema || {}
    const order = Array.isArray(data.adapter_order) ? data.adapter_order : []
    const hasTeleDrive = Boolean(adapters.teledrive || schema.teledrive || order.includes('teledrive'))
    const enabled = adapters.teledrive?.enabled !== false
    showTeleDriveNav.value = hasTeleDrive && enabled
  } catch (_error) {
    // 加载失败时保持当前状态，避免闪烁
  }
}
</script>

<style scoped>
.main-layout {
  --sidebar-width: 248px;
  --sidebar-collapsed-width: 64px;
  --mobile-safe-top: 0px;
  --mobile-header-height: 0px;
  --mobile-header-offset: 0px;
  --mobile-tabbar-offset: 0px;
  min-height: 100vh;
  background: transparent;
  display: flex;
  color: var(--text-primary);
}

.sidebar {
  width: var(--sidebar-width);
  background: var(--layout-sidebar-bg);
  backdrop-filter: blur(14px);
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-soft);
  box-shadow: var(--layout-sidebar-shadow);
  z-index: 100;
  transition: width 240ms var(--ease-standard);
}

.sidebar.dragging {
  transition: none;
}

.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
}

.sidebar.hidden {
  width: 0;
}

.sidebar-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.sidebar-header {
  padding: 22px 18px 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.mode-switch-wrap {
  overflow: hidden;
  max-height: 60px;
  opacity: 1;
  transition: max-height 180ms var(--ease-standard), opacity 180ms var(--ease-standard);
}

.mode-switch-wrap.hidden {
  max-height: 0;
  opacity: 0;
}

.logo {
  font-family: var(--font-display);
  font-size: 31px;
  font-weight: 800;
  letter-spacing: 0.02em;
  white-space: nowrap;
  overflow: hidden;
  opacity: 1;
  transition: opacity 180ms var(--ease-standard), width 180ms var(--ease-standard);
  background: linear-gradient(120deg, #ff8d16 0%, #ff5a3a 40%, #2f74ff 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.sidebar.collapsed .logo {
  opacity: 0;
  width: 0;
}

.sidebar-nav {
  flex: 1;
  padding: 16px 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 20px;
  margin: 0 10px;
  color: var(--text-secondary);
  text-decoration: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  transition:
    color var(--motion-fast) var(--ease-standard),
    background-color var(--motion-fast) var(--ease-standard),
    transform var(--motion-fast) var(--ease-standard),
    box-shadow var(--motion-fast) var(--ease-standard);
}

.nav-item:hover {
  background: var(--layout-nav-hover-bg);
  color: var(--layout-nav-hover-text);
  transform: translateX(2px);
  box-shadow: var(--layout-nav-hover-shadow);
}

.nav-item.active {
  background: var(--layout-nav-active-bg);
  color: var(--layout-nav-active-text);
  box-shadow: inset 0 0 0 1px var(--layout-nav-active-border);
}

.nav-item span {
  white-space: nowrap;
  overflow: hidden;
  opacity: 1;
  transition: opacity 180ms var(--ease-standard), width 180ms var(--ease-standard);
}

.sidebar.collapsed .nav-item span {
  opacity: 0;
  width: 0;
}

.nav-item .van-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.sidebar.collapsed .nav-item {
  justify-content: center;
  margin: 0 6px;
  padding: 11px 0;
  gap: 0;
}

.sidebar.collapsed .sidebar-footer {
  padding: 14px 8px;
}

.sidebar.collapsed .search-btn {
  justify-content: center;
  padding: 11px 0;
}

.sidebar-footer {
  padding: 16px 14px;
  border-top: 1px solid var(--border-soft);
}

.search-btn {
  margin: 0;
  background: var(--layout-search-btn-bg);
  border: 1px solid var(--layout-search-btn-border);
  border-radius: 11px;
  justify-content: center;
}

.mmmtttt-footer {
  font-size: 10px;
  color: #969799;
  text-align: center;
  margin-top: 8px;
  white-space: nowrap;
  overflow: hidden;
  opacity: 1;
  transition: opacity 180ms var(--ease-standard), width 180ms var(--ease-standard);
}

.sidebar.collapsed .mmmtttt-footer {
  opacity: 0;
  width: 0;
}

.sidebar-toggle {
  position: absolute;
  right: -14px;
  top: 50%;
  transform: translateY(-50%);
  width: 28px;
  height: 28px;
  border: 1px solid var(--border-soft);
  border-radius: 50%;
  background: var(--layout-sidebar-bg);
  backdrop-filter: blur(14px);
  color: var(--text-secondary);
  cursor: ew-resize;
  user-select: none;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 101;
  transition:
    color var(--motion-fast) var(--ease-standard),
    background-color var(--motion-fast) var(--ease-standard),
    box-shadow var(--motion-fast) var(--ease-standard);
}

.main-layout.dragging {
  user-select: none;
  cursor: ew-resize;
}

.sidebar-toggle:hover {
  color: var(--brand-600);
  background: var(--surface-3);
  box-shadow: var(--shadow-sm);
}

.sidebar-toggle .van-icon {
  font-size: 14px;
}

.mobile-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  background: var(--layout-header-bg);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-soft);
  z-index: 99;
  box-shadow: var(--layout-header-shadow);
  min-height: var(--mobile-header-offset);
  padding-top: var(--mobile-safe-top);
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 calc(14px + env(safe-area-inset-right, 0px)) 0 calc(14px + env(safe-area-inset-left, 0px));
  min-height: var(--mobile-header-height);
}

.page-title {
  font-size: 19px;
  font-weight: 700;
  color: var(--text-strong);
}

.header-mode-switch {
  transform: scale(0.84);
  transform-origin: right center;
}

.main-content {
  flex: 1;
  width: 100%;
  min-width: 0;
}

.main-content.random-feed-immersive {
  height: 100vh;
  min-height: 100vh;
  overflow: hidden;
}

.with-sidebar {
  margin-left: var(--sidebar-width);
  width: calc(100% - var(--sidebar-width));
  padding: clamp(14px, 1.8vw, 24px);
  padding-bottom: 0;
  transition: margin-left 240ms var(--ease-standard), width 240ms var(--ease-standard);
}

.main-layout.dragging .with-sidebar {
  transition: none;
}

.sidebar-collapsed-layout {
  margin-left: var(--sidebar-collapsed-width);
  width: calc(100% - var(--sidebar-collapsed-width));
}

.sidebar-hidden-layout {
  margin-left: 0;
  width: 100%;
}

.with-sidebar .desktop-page-shell {
  width: 100%;
  min-width: 0;
}

.with-sidebar.random-feed-immersive {
  padding: 0;
}

.with-header {
    padding-top: var(--mobile-header-offset);
  }

  .with-tabbar {
    padding-bottom: calc(54px + env(safe-area-inset-bottom, 0px));
  }

  .slide-left-enter-active,
.slide-left-leave-active {
  transition:
    opacity var(--motion-base) var(--ease-standard),
    transform var(--motion-base) var(--ease-standard);
}

.slide-left-enter-from {
  opacity: 0;
  transform: translateX(24px);
}

.slide-left-leave-to {
  opacity: 0;
  transform: translateX(-12px);
}

:deep(.van-tabbar) {
  background: var(--layout-tabbar-bg);
  backdrop-filter: blur(12px);
  border-top: 1px solid var(--border-soft);
  will-change: auto;
}

:deep(.van-tabbar-item) {
  will-change: auto;
}

:deep(.van-tabbar-item--active) {
  color: var(--brand-600);
}

@media (max-width: 1023px) {
  .main-layout {
    --mobile-safe-top: env(safe-area-inset-top, 0px);
    --mobile-header-height: 58px;
    --mobile-header-offset: calc(var(--mobile-header-height) + var(--mobile-safe-top));
    --mobile-tabbar-offset: calc(54px + env(safe-area-inset-bottom, 0px));
    display: flex;
    flex-direction: column;
    height: 100dvh;
    min-height: 0;
  }

  .main-content {
    flex: 1;
  }

  .with-sidebar {
    margin-left: 0;
    width: 100%;
    padding: 0;
  }
}

@media (min-width: 1024px) and (max-width: 1400px) {
  .with-sidebar {
    padding: 16px;
  }
}
</style>
