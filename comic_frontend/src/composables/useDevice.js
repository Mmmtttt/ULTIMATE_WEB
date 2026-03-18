import { ref, onMounted, onUnmounted } from 'vue'
import { getViewportWidth, onWindow } from '@/runtime/browser'

const MOBILE_BREAKPOINT = 768
const TABLET_BREAKPOINT = 1024

export function useDevice() {
  const isMobile = ref(false)
  const isTablet = ref(false)
  const isDesktop = ref(true)
  const windowWidth = ref(getViewportWidth())
  let removeResizeListener = null

  function updateDeviceType() {
    const width = getViewportWidth()
    windowWidth.value = width
    
    if (width < MOBILE_BREAKPOINT) {
      isMobile.value = true
      isTablet.value = false
      isDesktop.value = false
    } else if (width < TABLET_BREAKPOINT) {
      isMobile.value = false
      isTablet.value = true
      isDesktop.value = false
    } else {
      isMobile.value = false
      isTablet.value = false
      isDesktop.value = true
    }
  }

  onMounted(() => {
    updateDeviceType()
    removeResizeListener = onWindow('resize', updateDeviceType)
  })

  onUnmounted(() => {
    if (typeof removeResizeListener === 'function') {
      removeResizeListener()
      removeResizeListener = null
    }
  })

  return {
    isMobile,
    isTablet,
    isDesktop,
    windowWidth
  }
}
