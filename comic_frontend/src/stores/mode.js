import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getItem, setItem } from '@/utils/storage'

export const useModeStore = defineStore('mode', () => {
  const currentMode = ref(getItem('app_mode', 'comic'))
  const mediaViewMode = ref(getItem('media_view_mode', 'large'))
  
  const isComicMode = computed(() => currentMode.value === 'comic')
  const isVideoMode = computed(() => currentMode.value === 'video')
  
  function setMode(mode) {
    if (mode === 'comic' || mode === 'video') {
      currentMode.value = mode
      setItem('app_mode', mode)
    }
  }
  
  function toggleMode() {
    setMode(currentMode.value === 'comic' ? 'video' : 'comic')
  }

  function setMediaViewMode(mode) {
    if (['large', 'medium', 'small', 'list'].includes(mode)) {
      mediaViewMode.value = mode
      setItem('media_view_mode', mode)
    }
  }
  
  return {
    currentMode,
    mediaViewMode,
    isComicMode,
    isVideoMode,
    setMode,
    toggleMode,
    setMediaViewMode
  }
})
