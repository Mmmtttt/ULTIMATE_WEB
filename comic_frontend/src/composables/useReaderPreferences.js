import { computed, onUnmounted, ref, watch } from 'vue'

const TAP_PAGE_TURN_MODES = new Set(['full', 'left', 'right'])
const DOUBLE_TAP_ACTIONS = new Set(['zoom', 'menu'])

export function useReaderPreferences(configStore, { nextPage, isAtEnd, isWebtoon = () => false } = {}) {
  const settingsOpen = ref(false)
  const autoReadActive = ref(Boolean(configStore.autoRead))
  let autoReadTimer = null

  const doublePageMode = computed(() => Boolean(configStore.doublePageMode))
  const doublePageLeadingBlank = computed(() => Boolean(configStore.doublePageLeadingBlank))
  const tapPageTurnMode = computed(() => (
    TAP_PAGE_TURN_MODES.has(configStore.tapPageTurnMode) ? configStore.tapPageTurnMode : 'full'
  ))
  const tapPageTurnInWebtoon = computed(() => Boolean(configStore.tapPageTurnInWebtoon))
  const doubleTapAction = computed(() => (
    DOUBLE_TAP_ACTIONS.has(configStore.doubleTapAction) ? configStore.doubleTapAction : 'zoom'
  ))
  const autoReadInterval = computed(() => Number(configStore.autoReadInterval) || 5000)
  const noReaderAnimation = computed(() => Boolean(configStore.noReaderAnimation))
  const readFilterOpacity = computed(() => Number(configStore.readFilterOpacity) || 0)
  const readerSidePadding = computed(() => Number(configStore.readerSidePadding) || 0)

  const setPreference = (name, value) => configStore.setReaderPreference(name, value)

  const stopAutoRead = () => {
    autoReadActive.value = false
    if (autoReadTimer) {
      clearInterval(autoReadTimer)
      autoReadTimer = null
    }
  }

  const startAutoRead = () => {
    if (typeof nextPage !== 'function') return
    if (typeof isAtEnd === 'function' && isAtEnd()) {
      stopAutoRead()
      return
    }
    if (autoReadTimer) clearInterval(autoReadTimer)
    autoReadActive.value = true
    autoReadTimer = setInterval(() => {
      if (typeof isAtEnd === 'function' && isAtEnd()) {
        stopAutoRead()
        return
      }
      nextPage()
    }, autoReadInterval.value)
  }

  const toggleAutoRead = () => {
    if (autoReadActive.value) stopAutoRead()
    else startAutoRead()
  }

  watch(autoReadInterval, () => {
    if (autoReadActive.value) startAutoRead()
  })

  onUnmounted(stopAutoRead)

  return {
    settingsOpen,
    autoReadActive,
    doublePageMode,
    doublePageLeadingBlank,
    tapPageTurnMode,
    tapPageTurnInWebtoon,
    doubleTapAction,
    autoReadInterval,
    noReaderAnimation,
    readFilterOpacity,
    readerSidePadding,
    setPreference,
    startAutoRead,
    stopAutoRead,
    toggleAutoRead,
    isWebtoon
  }
}

export function resolveTapPageAction({ mode = 'full', x = 0, width = 0, isWebtoon = false, webtoonEnabled = true } = {}) {
  if (isWebtoon && !webtoonEnabled) return 'menu'
  if (mode === 'left' && x < width / 2) return 'previous'
  if (mode === 'right' && x >= width / 2) return 'next'
  if (mode === 'full') return 'menu'
  return 'none'
}
