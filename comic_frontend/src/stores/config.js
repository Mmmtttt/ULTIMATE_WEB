import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  DEFAULT_CONFIG,
  PAGE_MODE,
  BACKGROUND,
  LIST_PAGE_SIZE_OPTIONS,
  STORAGE_KEYS
} from '@/utils'
import { getDocumentElement } from '@/runtime/browser'
import { getItem, setItem } from '@/utils/storage'
import { configApi } from '@/api'

export const useConfigStore = defineStore('config', () => {
  const normalizeReaderInterval = (value) => {
    const normalized = Number(value)
    if (!Number.isFinite(normalized)) return DEFAULT_CONFIG.AUTO_READ_INTERVAL
    return Math.min(30000, Math.max(1000, Math.round(normalized)))
  }

  const normalizeReaderOpacity = (value) => {
    const normalized = Number(value)
    if (!Number.isFinite(normalized)) return DEFAULT_CONFIG.READ_FILTER_OPACITY
    return Math.min(0.8, Math.max(0, Number(normalized.toFixed(2))))
  }

  const normalizeReaderPadding = (value) => {
    const normalized = Number(value)
    if (!Number.isFinite(normalized)) return DEFAULT_CONFIG.READER_SIDE_PADDING
    return Math.min(30, Math.max(0, Math.round(normalized)))
  }

  const defaultPageMode = ref(DEFAULT_CONFIG.PAGE_MODE)
  const defaultBackground = ref(DEFAULT_CONFIG.BACKGROUND)
  const autoHideToolbar = ref(DEFAULT_CONFIG.AUTO_HIDE_TOOLBAR)
  const showPageNumber = ref(DEFAULT_CONFIG.SHOW_PAGE_NUMBER)
  const autoDownloadPreviewImportAssets = ref(DEFAULT_CONFIG.AUTO_DOWNLOAD_PREVIEW_IMPORT_ASSETS)
  const singlePageBrowsing = ref(DEFAULT_CONFIG.SINGLE_PAGE_BROWSING)
  const listPageSize = ref(DEFAULT_CONFIG.LIST_PAGE_SIZE)
  const leftRightReadingReversed = ref(DEFAULT_CONFIG.LEFT_RIGHT_READING_REVERSED)
  const doublePageMode = ref(DEFAULT_CONFIG.DOUBLE_PAGE_MODE)
  const doublePageLeadingBlank = ref(DEFAULT_CONFIG.DOUBLE_PAGE_LEADING_BLANK)
  const tapPageTurnMode = ref(DEFAULT_CONFIG.TAP_PAGE_TURN_MODE)
  const tapPageTurnInWebtoon = ref(DEFAULT_CONFIG.TAP_PAGE_TURN_IN_WEBTOON)
  const doubleTapAction = ref(DEFAULT_CONFIG.DOUBLE_TAP_ACTION)
  const autoRead = ref(DEFAULT_CONFIG.AUTO_READ)
  const autoReadInterval = ref(DEFAULT_CONFIG.AUTO_READ_INTERVAL)
  const noReaderAnimation = ref(DEFAULT_CONFIG.NO_READER_ANIMATION)
  const readFilterOpacity = ref(DEFAULT_CONFIG.READ_FILTER_OPACITY)
  const readerSidePadding = ref(DEFAULT_CONFIG.READER_SIDE_PADDING)
  const debugMode = ref(DEFAULT_CONFIG.DEBUG_MODE)
  const loading = ref(false)

  const normalizePageMode = (mode) => {
    if (Object.values(PAGE_MODE).includes(mode)) {
      return mode
    }
    return DEFAULT_CONFIG.PAGE_MODE
  }

  const normalizeBackground = (background) => {
    if (background === BACKGROUND.EYE_PROTECTION) {
      return BACKGROUND.SEPIA
    }
    if (
      background === BACKGROUND.WHITE ||
      background === BACKGROUND.DARK ||
      background === BACKGROUND.SEPIA
    ) {
      return background
    }
    return DEFAULT_CONFIG.BACKGROUND
  }

  const normalizeListPageSize = (size) => {
    const normalized = Number(size)
    if (LIST_PAGE_SIZE_OPTIONS.includes(normalized)) {
      return normalized
    }
    return DEFAULT_CONFIG.LIST_PAGE_SIZE
  }

  const resolveTheme = (background) => {
    const normalized = normalizeBackground(background)
    if (normalized === BACKGROUND.DARK) return 'dark'
    if (normalized === BACKGROUND.SEPIA) return 'sepia'
    return 'light'
  }

  const applyAppTheme = (background = defaultBackground.value) => {
    const rootElement = getDocumentElement()
    if (!rootElement) return
    const theme = resolveTheme(background)
    rootElement.setAttribute('data-theme', theme)
  }

  const config = computed(() => ({
    defaultPageMode: defaultPageMode.value,
    defaultBackground: defaultBackground.value,
    autoHideToolbar: autoHideToolbar.value,
    showPageNumber: showPageNumber.value,
    autoDownloadPreviewImportAssets: autoDownloadPreviewImportAssets.value,
    singlePageBrowsing: singlePageBrowsing.value,
    listPageSize: listPageSize.value,
    leftRightReadingReversed: leftRightReadingReversed.value,
    doublePageMode: doublePageMode.value,
    doublePageLeadingBlank: doublePageLeadingBlank.value,
    tapPageTurnMode: tapPageTurnMode.value,
    tapPageTurnInWebtoon: tapPageTurnInWebtoon.value,
    doubleTapAction: doubleTapAction.value,
    autoRead: autoRead.value,
    autoReadInterval: autoReadInterval.value,
    noReaderAnimation: noReaderAnimation.value,
    readFilterOpacity: readFilterOpacity.value,
    readerSidePadding: readerSidePadding.value,
    debugMode: debugMode.value
  }))

  const isLeftRightMode = computed(() => defaultPageMode.value === PAGE_MODE.LEFT_RIGHT)
  const isUpDownMode = computed(() => defaultPageMode.value === PAGE_MODE.UP_DOWN)

  const backgroundStyle = computed(() => {
    const colors = {
      [BACKGROUND.WHITE]: '#ffffff',
      [BACKGROUND.DARK]: '#1a1a1a',
      [BACKGROUND.SEPIA]: '#c7edcc',
      [BACKGROUND.EYE_PROTECTION]: '#c7edcc'
    }
    return {
      backgroundColor: colors[defaultBackground.value] || colors[BACKGROUND.WHITE]
    }
  })

  const backgroundName = computed(() => {
    const names = {
      [BACKGROUND.WHITE]: '白色',
      [BACKGROUND.DARK]: '深色',
      [BACKGROUND.SEPIA]: '护眼色',
      [BACKGROUND.EYE_PROTECTION]: '护眼色'
    }
    return names[defaultBackground.value] || '白色'
  })

  const pageModeName = computed(() => (isLeftRightMode.value ? '左右翻页' : '上下翻页'))
  function loadConfig() {
    const saved = getItem(STORAGE_KEYS.CONFIG, null)
    if (!saved) {
      applyAppTheme(DEFAULT_CONFIG.BACKGROUND)
      return
    }

    defaultPageMode.value = normalizePageMode(saved.defaultPageMode ?? DEFAULT_CONFIG.PAGE_MODE)
    defaultBackground.value = normalizeBackground(saved.defaultBackground ?? DEFAULT_CONFIG.BACKGROUND)
    autoHideToolbar.value = saved.autoHideToolbar ?? DEFAULT_CONFIG.AUTO_HIDE_TOOLBAR
    showPageNumber.value = saved.showPageNumber ?? DEFAULT_CONFIG.SHOW_PAGE_NUMBER
    autoDownloadPreviewImportAssets.value = (
      saved.autoDownloadPreviewImportAssets ??
      DEFAULT_CONFIG.AUTO_DOWNLOAD_PREVIEW_IMPORT_ASSETS
    )
    singlePageBrowsing.value = saved.singlePageBrowsing ?? DEFAULT_CONFIG.SINGLE_PAGE_BROWSING
    listPageSize.value = normalizeListPageSize(
      saved.listPageSize ??
      saved.pageSize ??
      DEFAULT_CONFIG.LIST_PAGE_SIZE
    )
    leftRightReadingReversed.value = Boolean(
      saved.leftRightReadingReversed ??
      saved.left_right_reading_reversed ??
      DEFAULT_CONFIG.LEFT_RIGHT_READING_REVERSED
    )
    doublePageMode.value = Boolean(saved.doublePageMode ?? DEFAULT_CONFIG.DOUBLE_PAGE_MODE)
    doublePageLeadingBlank.value = saved.doublePageLeadingBlank ?? DEFAULT_CONFIG.DOUBLE_PAGE_LEADING_BLANK
    tapPageTurnMode.value = ['full', 'left', 'right'].includes(saved.tapPageTurnMode)
      ? saved.tapPageTurnMode
      : DEFAULT_CONFIG.TAP_PAGE_TURN_MODE
    tapPageTurnInWebtoon.value = saved.tapPageTurnInWebtoon ?? DEFAULT_CONFIG.TAP_PAGE_TURN_IN_WEBTOON
    doubleTapAction.value = ['zoom', 'menu'].includes(saved.doubleTapAction)
      ? saved.doubleTapAction
      : DEFAULT_CONFIG.DOUBLE_TAP_ACTION
    autoRead.value = Boolean(saved.autoRead ?? DEFAULT_CONFIG.AUTO_READ)
    autoReadInterval.value = normalizeReaderInterval(saved.autoReadInterval)
    noReaderAnimation.value = Boolean(saved.noReaderAnimation ?? DEFAULT_CONFIG.NO_READER_ANIMATION)
    readFilterOpacity.value = normalizeReaderOpacity(saved.readFilterOpacity)
    readerSidePadding.value = normalizeReaderPadding(saved.readerSidePadding)
    applyAppTheme(defaultBackground.value)
  }

  async function loadConfigFromServer() {
    loading.value = true
    try {
      const res = await configApi.get()
      if (res.code !== 200 || !res.data) {
        return false
      }

      const serverConfig = res.data
      defaultPageMode.value = normalizePageMode(serverConfig.default_page_mode ?? DEFAULT_CONFIG.PAGE_MODE)
      defaultBackground.value = normalizeBackground(serverConfig.default_background ?? DEFAULT_CONFIG.BACKGROUND)
      autoHideToolbar.value = serverConfig.auto_hide_toolbar ?? DEFAULT_CONFIG.AUTO_HIDE_TOOLBAR
      showPageNumber.value = serverConfig.show_page_number ?? DEFAULT_CONFIG.SHOW_PAGE_NUMBER
      autoDownloadPreviewImportAssets.value = (
        serverConfig.auto_download_preview_assets_for_preview_import ??
        DEFAULT_CONFIG.AUTO_DOWNLOAD_PREVIEW_IMPORT_ASSETS
      )
      singlePageBrowsing.value = (
        serverConfig.single_page_browsing ??
        DEFAULT_CONFIG.SINGLE_PAGE_BROWSING
      )
      listPageSize.value = normalizeListPageSize(
        serverConfig.list_page_size ??
        serverConfig.page_size ??
        listPageSize.value
      )
      leftRightReadingReversed.value = Boolean(
        serverConfig.left_right_reading_reversed ??
        serverConfig.leftRightReadingReversed ??
        leftRightReadingReversed.value
      )
      doublePageMode.value = Boolean(serverConfig.double_page_mode ?? serverConfig.doublePageMode ?? DEFAULT_CONFIG.DOUBLE_PAGE_MODE)
      doublePageLeadingBlank.value = serverConfig.double_page_leading_blank ?? serverConfig.doublePageLeadingBlank ?? DEFAULT_CONFIG.DOUBLE_PAGE_LEADING_BLANK
      tapPageTurnMode.value = ['full', 'left', 'right'].includes(serverConfig.tap_page_turn_mode ?? serverConfig.tapPageTurnMode)
        ? (serverConfig.tap_page_turn_mode ?? serverConfig.tapPageTurnMode)
        : DEFAULT_CONFIG.TAP_PAGE_TURN_MODE
      tapPageTurnInWebtoon.value = serverConfig.tap_page_turn_in_webtoon ?? serverConfig.tapPageTurnInWebtoon ?? DEFAULT_CONFIG.TAP_PAGE_TURN_IN_WEBTOON
      doubleTapAction.value = ['zoom', 'menu'].includes(serverConfig.double_tap_action ?? serverConfig.doubleTapAction)
        ? (serverConfig.double_tap_action ?? serverConfig.doubleTapAction)
        : DEFAULT_CONFIG.DOUBLE_TAP_ACTION
      autoRead.value = Boolean(serverConfig.auto_read ?? serverConfig.autoRead ?? DEFAULT_CONFIG.AUTO_READ)
      autoReadInterval.value = normalizeReaderInterval(serverConfig.auto_read_interval ?? serverConfig.autoReadInterval)
      noReaderAnimation.value = Boolean(serverConfig.no_reader_animation ?? serverConfig.noReaderAnimation ?? DEFAULT_CONFIG.NO_READER_ANIMATION)
      readFilterOpacity.value = normalizeReaderOpacity(serverConfig.read_filter_opacity ?? serverConfig.readFilterOpacity)
      readerSidePadding.value = normalizeReaderPadding(serverConfig.reader_side_padding ?? serverConfig.readerSidePadding)
      debugMode.value = Boolean(serverConfig.debug_mode ?? DEFAULT_CONFIG.DEBUG_MODE)
      saveConfig()
      applyAppTheme(defaultBackground.value)
      return true
    } catch (error) {
      console.error('[Config] load config from server failed:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  function saveConfig() {
    setItem(STORAGE_KEYS.CONFIG, config.value)
  }

  async function saveConfigToServer() {
    try {
      const payload = {
        default_page_mode: defaultPageMode.value,
        default_background: defaultBackground.value,
        auto_hide_toolbar: autoHideToolbar.value,
        show_page_number: showPageNumber.value,
        auto_download_preview_assets_for_preview_import: autoDownloadPreviewImportAssets.value,
        single_page_browsing: singlePageBrowsing.value,
        double_page_mode: doublePageMode.value,
        double_page_leading_blank: doublePageLeadingBlank.value,
        tap_page_turn_mode: tapPageTurnMode.value,
        tap_page_turn_in_webtoon: tapPageTurnInWebtoon.value,
        double_tap_action: doubleTapAction.value,
        auto_read: autoRead.value,
        auto_read_interval: autoReadInterval.value,
        no_reader_animation: noReaderAnimation.value,
        read_filter_opacity: readFilterOpacity.value,
        reader_side_padding: readerSidePadding.value,
        debug_mode: debugMode.value
      }
      const res = await configApi.update(payload)
      return res.code === 200
    } catch (error) {
      console.error('[Config] save config to server failed:', error)
      return false
    }
  }

  function setPageMode(mode) {
    defaultPageMode.value = normalizePageMode(mode)
    saveConfig()
  }

  function togglePageMode() {
    const newMode = isLeftRightMode.value ? PAGE_MODE.UP_DOWN : PAGE_MODE.LEFT_RIGHT
    setPageMode(newMode)
  }

  function setBackground(background) {
    defaultBackground.value = normalizeBackground(background)
    saveConfig()
    applyAppTheme(defaultBackground.value)
  }

  function toggleBackground() {
    const backgrounds = [BACKGROUND.WHITE, BACKGROUND.DARK, BACKGROUND.SEPIA]
    const currentIndex = backgrounds.indexOf(defaultBackground.value)
    const nextIndex = (currentIndex + 1) % backgrounds.length
    setBackground(backgrounds[nextIndex])
  }

  function setAutoHideToolbar(value) {
    autoHideToolbar.value = !!value
    saveConfig()
  }

  function setShowPageNumber(value) {
    showPageNumber.value = !!value
    saveConfig()
  }

  function setAutoDownloadPreviewImportAssets(value) {
    autoDownloadPreviewImportAssets.value = !!value
    saveConfig()
  }

  function setSinglePageBrowsing(value) {
    singlePageBrowsing.value = !!value
    saveConfig()
  }

  function setListPageSize(size) {
    listPageSize.value = normalizeListPageSize(size)
    saveConfig()
  }

  function setLeftRightReadingReversed(value) {
    leftRightReadingReversed.value = !!value
    saveConfig()
  }

  function setReaderPreference(name, value) {
    const setters = {
      doublePageMode: (next) => { doublePageMode.value = Boolean(next) },
      doublePageLeadingBlank: (next) => { doublePageLeadingBlank.value = Boolean(next) },
      tapPageTurnMode: (next) => { if (['full', 'left', 'right'].includes(next)) tapPageTurnMode.value = next },
      tapPageTurnInWebtoon: (next) => { tapPageTurnInWebtoon.value = Boolean(next) },
      doubleTapAction: (next) => { if (['zoom', 'menu'].includes(next)) doubleTapAction.value = next },
      autoRead: (next) => { autoRead.value = Boolean(next) },
      autoReadInterval: (next) => { autoReadInterval.value = normalizeReaderInterval(next) },
      noReaderAnimation: (next) => { noReaderAnimation.value = Boolean(next) },
      readFilterOpacity: (next) => { readFilterOpacity.value = normalizeReaderOpacity(next) },
      readerSidePadding: (next) => { readerSidePadding.value = normalizeReaderPadding(next) }
    }
    if (!setters[name]) return
    setters[name](value)
    saveConfig()
  }

  async function resetConfig() {
    defaultPageMode.value = DEFAULT_CONFIG.PAGE_MODE
    defaultBackground.value = DEFAULT_CONFIG.BACKGROUND
    autoHideToolbar.value = DEFAULT_CONFIG.AUTO_HIDE_TOOLBAR
    showPageNumber.value = DEFAULT_CONFIG.SHOW_PAGE_NUMBER
    autoDownloadPreviewImportAssets.value = DEFAULT_CONFIG.AUTO_DOWNLOAD_PREVIEW_IMPORT_ASSETS
    singlePageBrowsing.value = DEFAULT_CONFIG.SINGLE_PAGE_BROWSING
    listPageSize.value = DEFAULT_CONFIG.LIST_PAGE_SIZE
    leftRightReadingReversed.value = DEFAULT_CONFIG.LEFT_RIGHT_READING_REVERSED
    doublePageMode.value = DEFAULT_CONFIG.DOUBLE_PAGE_MODE
    doublePageLeadingBlank.value = DEFAULT_CONFIG.DOUBLE_PAGE_LEADING_BLANK
    tapPageTurnMode.value = DEFAULT_CONFIG.TAP_PAGE_TURN_MODE
    tapPageTurnInWebtoon.value = DEFAULT_CONFIG.TAP_PAGE_TURN_IN_WEBTOON
    doubleTapAction.value = DEFAULT_CONFIG.DOUBLE_TAP_ACTION
    autoRead.value = DEFAULT_CONFIG.AUTO_READ
    autoReadInterval.value = DEFAULT_CONFIG.AUTO_READ_INTERVAL
    noReaderAnimation.value = DEFAULT_CONFIG.NO_READER_ANIMATION
    readFilterOpacity.value = DEFAULT_CONFIG.READ_FILTER_OPACITY
    readerSidePadding.value = DEFAULT_CONFIG.READER_SIDE_PADDING
    debugMode.value = DEFAULT_CONFIG.DEBUG_MODE
    saveConfig()
    applyAppTheme(defaultBackground.value)
    await saveConfigToServer()
  }

  function updateConfig(newConfig) {
    if (newConfig.defaultPageMode !== undefined) {
      setPageMode(newConfig.defaultPageMode)
    }
    if (newConfig.defaultBackground !== undefined) {
      setBackground(newConfig.defaultBackground)
    }
    if (newConfig.autoHideToolbar !== undefined) {
      setAutoHideToolbar(newConfig.autoHideToolbar)
    }
    if (newConfig.showPageNumber !== undefined) {
      setShowPageNumber(newConfig.showPageNumber)
    }
    if (newConfig.autoDownloadPreviewImportAssets !== undefined) {
      setAutoDownloadPreviewImportAssets(newConfig.autoDownloadPreviewImportAssets)
    }
    if (newConfig.singlePageBrowsing !== undefined) {
      setSinglePageBrowsing(newConfig.singlePageBrowsing)
    }
    if (newConfig.listPageSize !== undefined) {
      setListPageSize(newConfig.listPageSize)
    }
    if (newConfig.leftRightReadingReversed !== undefined) {
      setLeftRightReadingReversed(newConfig.leftRightReadingReversed)
    }
    if (newConfig.debugMode !== undefined) {
      debugMode.value = Boolean(newConfig.debugMode)
      saveConfig()
    }
    for (const name of [
      'doublePageMode', 'doublePageLeadingBlank', 'tapPageTurnMode', 'tapPageTurnInWebtoon',
      'doubleTapAction', 'autoRead', 'autoReadInterval', 'noReaderAnimation',
      'readFilterOpacity', 'readerSidePadding'
    ]) {
      if (newConfig[name] !== undefined) setReaderPreference(name, newConfig[name])
    }
  }

  loadConfig()

  return {
    defaultPageMode,
    defaultBackground,
    autoHideToolbar,
    showPageNumber,
    autoDownloadPreviewImportAssets,
    singlePageBrowsing,
    listPageSize,
    leftRightReadingReversed,
    doublePageMode,
    doublePageLeadingBlank,
    tapPageTurnMode,
    tapPageTurnInWebtoon,
    doubleTapAction,
    autoRead,
    autoReadInterval,
    noReaderAnimation,
    readFilterOpacity,
    readerSidePadding,
    debugMode,
    loading,

    config,
    isLeftRightMode,
    isUpDownMode,
    backgroundStyle,
    backgroundName,
    pageModeName,

    loadConfig,
    applyAppTheme,
    loadConfigFromServer,
    saveConfig,
    saveConfigToServer,
    setPageMode,
    togglePageMode,
    setBackground,
    toggleBackground,
    setAutoHideToolbar,
    setShowPageNumber,
    setAutoDownloadPreviewImportAssets,
    setSinglePageBrowsing,
    setListPageSize,
    setLeftRightReadingReversed,
    setReaderPreference,
    resetConfig,
    updateConfig
  }
})
