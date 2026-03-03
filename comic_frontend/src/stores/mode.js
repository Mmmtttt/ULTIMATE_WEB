import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useModeStore = defineStore('mode', () => {
  const currentMode = ref(localStorage.getItem('app_mode') || 'comic')
  
  const isComicMode = computed(() => currentMode.value === 'comic')
  const isVideoMode = computed(() => currentMode.value === 'video')
  
  function setMode(mode) {
    if (mode === 'comic' || mode === 'video') {
      currentMode.value = mode
      localStorage.setItem('app_mode', mode)
    }
  }
  
  function toggleMode() {
    setMode(currentMode.value === 'comic' ? 'video' : 'comic')
  }
  
  return {
    currentMode,
    isComicMode,
    isVideoMode,
    setMode,
    toggleMode
  }
})
