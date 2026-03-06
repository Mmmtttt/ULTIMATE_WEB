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
  background: #f5f5f5;
  display: flex;
}

/* Sidebar Styles */
.sidebar {
  width: 240px;
  background: #fff;
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #eee;
  z-index: 100;
}

.sidebar-header {
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.logo {
  font-size: 24px;
  font-weight: 800;
  background: linear-gradient(45deg, #ff9f00, #ff0055);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.sidebar-nav {
  flex: 1;
  padding: 20px 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 24px;
  color: #666;
  text-decoration: none;
  font-size: 16px;
  font-weight: 500;
  transition: all 0.2s;
  border-left: 3px solid transparent;
}

.nav-item:hover {
  background: #f9f9f9;
  color: #333;
}

.nav-item.active {
  background: #f0f7ff;
  color: #1989fa;
  border-left-color: #1989fa;
}

.nav-item .van-icon {
  font-size: 20px;
}

.sidebar-footer {
  padding: 20px;
  border-top: 1px solid #eee;
}

.search-btn {
  background: #f5f5f5;
  border-radius: 8px;
  justify-content: center;
  border: none;
}

/* Mobile Header */
.mobile-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  background: #fff;
  z-index: 99;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  height: 60px;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  height: 100%;
}

.page-title {
  font-size: 18px;
  font-weight: 700;
  color: #333;
}

.header-mode-switch {
  transform: scale(0.8);
  transform-origin: right center;
}

/* Main Content Area */
.main-content {
  flex: 1;
  min-height: 100vh;
  width: 100%;
}

.with-sidebar {
  margin-left: 240px;
  padding: 24px;
}

.with-header {
  padding-top: 60px;
}

.with-tabbar {
  padding-bottom: 50px;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
