import { ref, onMounted, onUnmounted } from 'vue'
import { getViewportWidth, onWindow } from '@/runtime/browser'

const MOBILE_BREAKPOINT = 768
const TABLET_BREAKPOINT = 1024

export function useDevice() {
  // 初值直接按当前视口算，别先按桌面渲染再在 onMounted 纠正：
  // 那样移动端首帧会先排一遍桌面布局，挂载后才补移动端内容，页面会跳一下。
  const initialWidth = getViewportWidth()
  const isMobile = ref(initialWidth < MOBILE_BREAKPOINT)
  const isTablet = ref(initialWidth >= MOBILE_BREAKPOINT && initialWidth < TABLET_BREAKPOINT)
  const isDesktop = ref(initialWidth >= TABLET_BREAKPOINT)
  const windowWidth = ref(initialWidth)
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
