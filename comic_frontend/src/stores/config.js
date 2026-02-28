import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { 
  DEFAULT_CONFIG, 
  PAGE_MODE, 
  BACKGROUND,
  STORAGE_KEYS 
} from '@/utils'
import { getItem, setItem } from '@/utils/storage'
import { configApi } from '@/api'

/**
 * 配置管理 Store
 * 管理用户配置和阅读器设置
 */
export const useConfigStore = defineStore('config', () => {
  // ============ State ============
  
  // 默认翻页模式
  const defaultPageMode = ref(DEFAULT_CONFIG.PAGE_MODE)
  
  // 默认背景色
  const defaultBackground = ref(DEFAULT_CONFIG.BACKGROUND)
  
  // 自动隐藏工具栏
  const autoHideToolbar = ref(DEFAULT_CONFIG.AUTO_HIDE_TOOLBAR)
  
  // 显示页码
  const showPageNumber = ref(DEFAULT_CONFIG.SHOW_PAGE_NUMBER)
  
  // 加载状态
  const loading = ref(false)
  
  // ============ Getters ============
  
  /**
   * 当前配置对象
   */
  const config = computed(() => ({
    defaultPageMode: defaultPageMode.value,
    defaultBackground: defaultBackground.value,
    autoHideToolbar: autoHideToolbar.value,
    showPageNumber: showPageNumber.value
  }))
  
  /**
   * 是否为左右翻页模式
   */
  const isLeftRightMode = computed(() => 
    defaultPageMode.value === PAGE_MODE.LEFT_RIGHT
  )
  
  /**
   * 是否为上下翻页模式
   */
  const isUpDownMode = computed(() => 
    defaultPageMode.value === PAGE_MODE.UP_DOWN
  )
  
  /**
   * 背景色样式
   */
  const backgroundStyle = computed(() => {
    const colors = {
      [BACKGROUND.WHITE]: '#ffffff',
      [BACKGROUND.DARK]: '#1a1a1a',
      [BACKGROUND.EYE_PROTECTION]: '#c7edcc'
    }
    return {
      backgroundColor: colors[defaultBackground.value] || colors[BACKGROUND.WHITE]
    }
  })
  
  /**
   * 背景色名称
   */
  const backgroundName = computed(() => {
    const names = {
      [BACKGROUND.WHITE]: '白色',
      [BACKGROUND.DARK]: '深色',
      [BACKGROUND.EYE_PROTECTION]: '护眼色'
    }
    return names[defaultBackground.value] || '白色'
  })
  
  /**
   * 翻页模式名称
   */
  const pageModeName = computed(() => 
    isLeftRightMode.value ? '左右翻页' : '上下翻页'
  )
  
  // ============ Actions ============
  
  /**
   * 从本地存储加载配置
   */
  function loadConfig() {
    const saved = getItem(STORAGE_KEYS.CONFIG, null)
    if (saved) {
      defaultPageMode.value = saved.defaultPageMode ?? DEFAULT_CONFIG.PAGE_MODE
      defaultBackground.value = saved.defaultBackground ?? DEFAULT_CONFIG.BACKGROUND
      autoHideToolbar.value = saved.autoHideToolbar ?? DEFAULT_CONFIG.AUTO_HIDE_TOOLBAR
      showPageNumber.value = saved.showPageNumber ?? DEFAULT_CONFIG.SHOW_PAGE_NUMBER
      console.log('[Config] 从本地加载配置')
    }
  }
  
  /**
   * 从服务器加载配置
   */
  async function loadConfigFromServer() {
    loading.value = true
    try {
      const res = await configApi.get()
      if (res.code === 200 && res.data) {
        const serverConfig = res.data
        defaultPageMode.value = serverConfig.default_page_mode ?? DEFAULT_CONFIG.PAGE_MODE
        defaultBackground.value = serverConfig.default_background ?? DEFAULT_CONFIG.BACKGROUND
        autoHideToolbar.value = serverConfig.auto_hide_toolbar ?? DEFAULT_CONFIG.AUTO_HIDE_TOOLBAR
        showPageNumber.value = serverConfig.show_page_number ?? DEFAULT_CONFIG.SHOW_PAGE_NUMBER
        saveConfig()
        console.log('[Config] 从服务器加载配置成功')
        return true
      }
      return false
    } catch (e) {
      console.error('[Config] 从服务器加载配置失败:', e)
      return false
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 保存配置到本地存储
   */
  function saveConfig() {
    setItem(STORAGE_KEYS.CONFIG, config.value)
    console.log('[Config] 保存配置到本地')
  }
  
  /**
   * 保存配置到服务器
   */
  async function saveConfigToServer() {
    try {
      const data = {
        default_page_mode: defaultPageMode.value,
        default_background: defaultBackground.value,
        auto_hide_toolbar: autoHideToolbar.value,
        show_page_number: showPageNumber.value
      }
      const res = await configApi.update(data)
      if (res.code === 200) {
        console.log('[Config] 保存配置到服务器成功')
        return true
      }
      return false
    } catch (e) {
      console.error('[Config] 保存配置到服务器失败:', e)
      return false
    }
  }
  
  /**
   * 设置翻页模式
   * @param {string} mode - 翻页模式
   */
  function setPageMode(mode) {
    if (Object.values(PAGE_MODE).includes(mode)) {
      defaultPageMode.value = mode
      saveConfig()
      console.log('[Config] 设置翻页模式:', mode)
    }
  }
  
  /**
   * 切换翻页模式
   */
  function togglePageMode() {
    const newMode = isLeftRightMode.value ? PAGE_MODE.UP_DOWN : PAGE_MODE.LEFT_RIGHT
    setPageMode(newMode)
  }
  
  /**
   * 设置背景色
   * @param {string} background - 背景色
   */
  function setBackground(background) {
    if (Object.values(BACKGROUND).includes(background)) {
      defaultBackground.value = background
      saveConfig()
      console.log('[Config] 设置背景色:', background)
    }
  }
  
  /**
   * 切换背景色
   */
  function toggleBackground() {
    const backgrounds = [BACKGROUND.WHITE, BACKGROUND.DARK, BACKGROUND.EYE_PROTECTION]
    const currentIndex = backgrounds.indexOf(defaultBackground.value)
    const nextIndex = (currentIndex + 1) % backgrounds.length
    setBackground(backgrounds[nextIndex])
  }
  
  /**
   * 设置自动隐藏工具栏
   * @param {boolean} value - 是否自动隐藏
   */
  function setAutoHideToolbar(value) {
    autoHideToolbar.value = !!value
    saveConfig()
  }
  
  /**
   * 设置显示页码
   * @param {boolean} value - 是否显示
   */
  function setShowPageNumber(value) {
    showPageNumber.value = !!value
    saveConfig()
  }
  
  /**
   * 重置为默认配置
   */
  async function resetConfig() {
    defaultPageMode.value = DEFAULT_CONFIG.PAGE_MODE
    defaultBackground.value = DEFAULT_CONFIG.BACKGROUND
    autoHideToolbar.value = DEFAULT_CONFIG.AUTO_HIDE_TOOLBAR
    showPageNumber.value = DEFAULT_CONFIG.SHOW_PAGE_NUMBER
    saveConfig()
    await saveConfigToServer()
    console.log('[Config] 重置为默认配置')
  }
  
  /**
   * 更新多个配置项
   * @param {Object} newConfig - 新配置对象
   */
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
  }
  
  // 初始化时加载配置
  loadConfig()
  
  return {
    // State
    defaultPageMode,
    defaultBackground,
    autoHideToolbar,
    showPageNumber,
    loading,
    
    // Getters
    config,
    isLeftRightMode,
    isUpDownMode,
    backgroundStyle,
    backgroundName,
    pageModeName,
    
    // Actions
    loadConfig,
    loadConfigFromServer,
    saveConfig,
    saveConfigToServer,
    setPageMode,
    togglePageMode,
    setBackground,
    toggleBackground,
    setAutoHideToolbar,
    setShowPageNumber,
    resetConfig,
    updateConfig
  }
})
