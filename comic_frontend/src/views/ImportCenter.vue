<template>
  <div class="import-center desktop-page-shell">
    <van-nav-bar title="导入" left-text="返回" left-arrow @click-left="goBack" />

    <van-tabs ref="tabsRef" v-model:active="activeTab" class="import-tabs">
      <van-tab title="本地导入" name="local">
        <ComicLocalImport v-if="!isVideoMode" embedded />
        <VideoLocalImport v-else embedded />
      </van-tab>
      <van-tab title="ID 导入" name="id">
        <OnlineImportPanel />
      </van-tab>
    </van-tabs>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useModeStore } from '@/stores'
import ComicLocalImport from '@/views/ComicLocalImport.vue'
import VideoLocalImport from '@/views/VideoLocalImport.vue'
import OnlineImportPanel from '@/components/import/OnlineImportPanel.vue'

const route = useRoute()
const router = useRouter()
const modeStore = useModeStore()

const isVideoMode = computed(() => modeStore.isVideoMode)
const activeTab = ref(String(route.query.tab || '') === 'id' ? 'id' : 'local')

const tabsRef = ref(null)
let resizeObserver = null
let resizeFrame = 0

// 侧边导航栏收起/展开会改变内容区宽度，Vant 只在 window resize 时重算下划线，
// 这里监听容器尺寸变化，让选项卡宽度与下划线都跟着内容区自适应。
function scheduleTabResize() {
  if (resizeFrame) return
  resizeFrame = window.requestAnimationFrame(() => {
    resizeFrame = 0
    tabsRef.value?.resize?.()
  })
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/mine')
}

onMounted(() => {
  window.addEventListener('resize', scheduleTabResize)
  if (typeof ResizeObserver !== 'undefined') {
    const target = document.querySelector('.import-tabs')
    if (target) {
      resizeObserver = new ResizeObserver(scheduleTabResize)
      resizeObserver.observe(target)
    }
  }
  scheduleTabResize()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', scheduleTabResize)
  resizeObserver?.disconnect()
  resizeObserver = null
  if (resizeFrame) {
    window.cancelAnimationFrame(resizeFrame)
    resizeFrame = 0
  }
})
</script>

<style scoped>
.import-center {
  min-height: 95vh;
  background: transparent;
  padding-bottom: 24px;
}

.import-tabs :deep(.van-tabs__wrap) {
  background: transparent;
}

/* 两个标签平分内容区宽度，侧边栏伸缩时一起自适应 */
.import-tabs :deep(.van-tab) {
  flex: 1;
  font-size: 14px;
}

.import-tabs :deep(.van-tab--active) {
  font-weight: 600;
}
</style>
