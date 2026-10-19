import { onBeforeUnmount, onMounted } from 'vue'

/**
 * 让 van-tabs 的下划线跟随容器宽度变化。
 *
 * Vant 只在 window resize 时重算下划线，而侧边导航栏收起/展开只会改变内容区宽度
 * （CSS 过渡），不会触发 window resize。这里用 ResizeObserver 监听选项卡容器，
 * 变化时调用 Tabs 暴露的 resize()，并用 rAF 合并高频回调。
 */
export function useTabsResize(tabsRef, fallbackSelector = '.van-tabs') {
  let observer = null
  let frame = 0

  function schedule() {
    if (frame) return
    frame = window.requestAnimationFrame(() => {
      frame = 0
      tabsRef.value?.resize?.()
    })
  }

  onMounted(() => {
    window.addEventListener('resize', schedule)
    if (typeof ResizeObserver !== 'undefined') {
      const target = tabsRef.value?.$el || document.querySelector(fallbackSelector)
      if (target) {
        observer = new ResizeObserver(schedule)
        observer.observe(target)
      }
    }
    schedule()
  })

  onBeforeUnmount(() => {
    window.removeEventListener('resize', schedule)
    observer?.disconnect()
    observer = null
    if (frame) {
      window.cancelAnimationFrame(frame)
      frame = 0
    }
  })
}
