<template>
  <div class="mode-switch" :class="{ 'is-video': mode === 'video' }" @click="toggle">
    <div class="switch-track">
      <div class="switch-indicator"></div>
      <div class="switch-option option-comic" :class="{ active: mode === 'comic' }">
        <span class="icon">📖</span>
        <span class="text">漫画</span>
      </div>
      <div class="switch-option option-video" :class="{ active: mode === 'video' }">
        <span class="icon">🎬</span>
        <span class="text">视频</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useModeStore } from '@/stores/mode'

const modeStore = useModeStore()
const mode = computed(() => modeStore.currentMode)

function toggle() {
  modeStore.toggleMode()
  // 可以在这里触发全局事件或路由跳转，如果需要
}
</script>

<style scoped>
.mode-switch {
  cursor: pointer;
  user-select: none;
  display: inline-block;
}

.switch-track {
  position: relative;
  display: flex;
  background: var(--surface-3);
  border: 1px solid var(--border-soft);
  border-radius: 20px;
  padding: 4px;
  width: 160px;
  height: 40px;
  box-shadow: inset 0 2px 4px rgba(2, 8, 18, 0.18);
  transition: background-color 0.3s ease, border-color 0.3s ease;
}

.mode-switch.is-video .switch-track {
  background: var(--surface-2);
}

.switch-indicator {
  position: absolute;
  top: 4px;
  left: 4px;
  width: calc(50% - 4px);
  height: calc(100% - 8px);
  background: var(--surface-1);
  border: 1px solid var(--border-soft);
  border-radius: 16px;
  box-shadow: 0 4px 10px rgba(2, 8, 18, 0.2);
  transition: transform 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
  z-index: 1;
}

.mode-switch.is-video .switch-indicator {
  transform: translateX(100%);
}

.switch-option {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  position: relative;
  z-index: 2;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-tertiary);
  transition: color 0.3s;
}

.switch-option.active {
  color: var(--text-strong);
}

.option-comic.active {
  color: #ff9f00;
}

.option-video.active {
  color: #1989fa;
}

.icon {
  font-size: 16px;
}
</style>
