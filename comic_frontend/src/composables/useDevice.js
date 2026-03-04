import { ref, onMounted, onUnmounted } from 'vue'

const MOBILE_BREAKPOINT = 768
const TABLET_BREAKPOINT = 1024

export function useDevice() {
  const isMobile = ref(false)
  const isTablet = ref(false)
  const isDesktop = ref(true)
  const windowWidth = ref(window.innerWidth)

  function updateDeviceType() {
    const width = window.innerWidth
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
    window.addEventListener('resize', updateDeviceType)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', updateDeviceType)
  })

  return {
    isMobile,
    isTablet,
    isDesktop,
    windowWidth
  }
}
