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
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useModeStore } from '@/stores'
import { useTabsResize } from '@/composables/useTabsResize'
import ComicLocalImport from '@/views/ComicLocalImport.vue'
import VideoLocalImport from '@/views/VideoLocalImport.vue'
import OnlineImportPanel from '@/components/import/OnlineImportPanel.vue'

const route = useRoute()
const router = useRouter()
const modeStore = useModeStore()

const isVideoMode = computed(() => modeStore.isVideoMode)
const activeTab = ref(String(route.query.tab || '') === 'id' ? 'id' : 'local')

const tabsRef = ref(null)
// 侧边导航栏收起/展开会改变内容区宽度，让选项卡下划线跟着重算
useTabsResize(tabsRef, '.import-tabs')

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/mine')
}
</script>

<style scoped>
.import-center {
  min-height: 95vh;
  min-height: 95dvh;
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
