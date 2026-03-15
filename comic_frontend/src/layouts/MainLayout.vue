<template>
  <div class="main-layout">
    <!-- Desktop Sidebar -->
    <aside v-if="isDesktop" class="sidebar">
      <div class="sidebar-header">
        <div class="logo">Ultimate</div>
        <ModeSwitch class="sidebar-mode-switch" />
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
        <router-link to="/subscribe" class="nav-item" active-class="active">
          <van-icon name="star-o" />
          <span>订阅</span>
        </router-link>
        <router-link to="/mine" class="nav-item" active-class="active">
          <van-icon name="user-o" />
          <span>我的</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <router-link to="/search" class="nav-item search-btn">
          <van-icon name="search" />
          <span>全局搜索</span>
        </router-link>
      </div>
    </aside>

    <!-- Mobile Top Navbar -->
    <header v-if="isMobile" class="mobile-header">
      <div class="header-content">
        <div class="page-title">{{ pageTitle }}</div>
        <ModeSwitch class="header-mode-switch" />
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content" :class="{ 'with-sidebar': isDesktop, 'with-header': isMobile, 'with-tabbar': isMobile }">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <!-- Mobile Bottom Tabbar -->
    <van-tabbar v-if="isMobile" route fixed placeholder>
      <van-tabbar-item to="/library" icon="home-o">本地库</van-tabbar-item>
      <van-tabbar-item to="/preview" icon="eye-o">预览库</van-tabbar-item>
      <van-tabbar-item to="/subscribe" icon="star-o">订阅</van-tabbar-item>
      <van-tabbar-item to="/mine" icon="user-o">我的</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useDevice } from '@/composables/useDevice'
import ModeSwitch from '@/components/common/ModeSwitch.vue'

const { isDesktop, isMobile } = useDevice()
const route = useRoute()

const pageTitle = computed(() => {
  switch (route.path) {
    case '/library': return '本地库'
    case '/preview': return '预览库'
    case '/subscribe': return '订阅'
    case '/mine': return '我的'
    default: return 'Ultimate'
  }
})
</script>

<style scoped>
.main-layout {
  min-height: 100vh;
  background: transparent;
  display: flex;
  color: var(--text-primary);
}

.sidebar {
  width: var(--sidebar-width);
  background: rgba(255, 255, 255, 0.76);
  backdrop-filter: blur(14px);
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-soft);
  box-shadow: 6px 0 24px rgba(22, 39, 68, 0.06);
  z-index: 100;
}

.sidebar-header {
  padding: 22px 18px 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.logo {
  font-family: var(--font-display);
  font-size: 31px;
  font-weight: 800;
  letter-spacing: 0.02em;
  background: linear-gradient(120deg, #ff8d16 0%, #ff5a3a 40%, #2f74ff 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
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
  background: rgba(255, 255, 255, 0.92);
  color: var(--text-strong);
  transform: translateX(2px);
  box-shadow: 0 4px 14px rgba(17, 27, 45, 0.08);
}

.nav-item.active {
  background: linear-gradient(135deg, rgba(47, 116, 255, 0.16), rgba(47, 116, 255, 0.08));
  color: var(--brand-600);
  box-shadow: inset 0 0 0 1px rgba(47, 116, 255, 0.24);
}

.nav-item .van-icon {
  font-size: 18px;
}

.sidebar-footer {
  padding: 16px 14px;
  border-top: 1px solid var(--border-soft);
}

.search-btn {
  margin: 0;
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(73, 98, 146, 0.18);
  border-radius: 11px;
  justify-content: center;
}

.mobile-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  background: rgba(255, 255, 255, 0.84);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-soft);
  z-index: 99;
  box-shadow: 0 8px 20px rgba(17, 27, 45, 0.06);
  height: 58px;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  height: 100%;
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
  min-height: 100vh;
  width: 100%;
}

.with-sidebar {
  margin-left: var(--sidebar-width);
  padding: clamp(14px, 1.8vw, 24px);
}

.with-header {
  padding-top: 58px;
}

.with-tabbar {
  padding-bottom: 54px;
}

.fade-enter-active,
.fade-leave-active {
  transition:
    opacity var(--motion-base) var(--ease-standard),
    transform var(--motion-base) var(--ease-standard);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

:deep(.van-tabbar) {
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(12px);
  border-top: 1px solid var(--border-soft);
}

:deep(.van-tabbar-item--active) {
  color: var(--brand-600);
}

@media (max-width: 1023px) {
  .main-layout {
    display: block;
  }

  .with-sidebar {
    margin-left: 0;
    padding: 0;
  }
}

@media (min-width: 1024px) and (max-width: 1400px) {
  .with-sidebar {
    padding: 16px;
  }
}
</style>
