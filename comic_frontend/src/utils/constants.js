/**
 * 常量定义
 * 集中管理应用中的所有常量，避免硬编码
 */

// 阅读器翻页模式
export const PAGE_MODE = {
  LEFT_RIGHT: 'left_right',
  UP_DOWN: 'up_down'
}

// 阅读器背景色
export const BACKGROUND = {
  WHITE: 'white',
  DARK: 'dark',
  EYE_PROTECTION: 'eye_protection'
}

// 背景色对应的颜色值
export const BACKGROUND_COLORS = {
  [BACKGROUND.WHITE]: '#ffffff',
  [BACKGROUND.DARK]: '#1a1a1a',
  [BACKGROUND.EYE_PROTECTION]: '#c7edcc'
}

// 默认配置
export const DEFAULT_CONFIG = {
  PAGE_MODE: PAGE_MODE.LEFT_RIGHT,
  BACKGROUND: BACKGROUND.WHITE,
  AUTO_HIDE_TOOLBAR: true,
  SHOW_PAGE_NUMBER: true
}

// 评分范围
export const SCORE_RANGE = {
  MIN: 0,
  MAX: 10
}

// 缓存过期时间（毫秒）
export const CACHE_EXPIRY = {
  COMIC_LIST: getCacheExpiry(),    // 动态获取
  COMIC_DETAIL: getCacheExpiry(),  // 动态获取
  TAGS: getCacheExpiry() * 2,      // 2倍时间
  IMAGES: getCacheExpiry() * 6,    // 6倍时间
  AUTHORS: getCacheExpiry() * 2,   // 作者列表缓存
  AUTHOR_WORKS: getCacheExpiry()   // 作者作品缓存
}

// 获取缓存过期时间（支持用户自定义）
function getCacheExpiry() {
  if (typeof window !== 'undefined') {
    const minutes = parseInt(localStorage.getItem('cache_expiry_minutes'), 10)
    if (minutes && minutes > 0) {
      return minutes * 60 * 1000
    }
  }
  return 30 * 60 * 1000 // 默认30分钟
}

// 本地存储键名
export const STORAGE_KEYS = {
  CONFIG: 'comic_config',
  READ_PROGRESS: 'comic_read_progress',
  CACHE: 'comic_cache'
}

// 排序类型
export const SORT_TYPE = {
  CREATE_TIME: 'create_time',
  SCORE: 'score',
  READ_TIME: 'read_time'
}

// 排序选项
export const SORT_OPTIONS = [
  { label: '最近导入', value: SORT_TYPE.CREATE_TIME },
  { label: '评分', value: SORT_TYPE.SCORE },
  { label: '最后阅读', value: SORT_TYPE.READ_TIME }
]

// 图片格式
export const IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']

// 默认清单ID
export const DEFAULT_LIST_ID = 'list_favorites'

// 默认清单名称
export const DEFAULT_LIST_NAME = '我的收藏'

// 导入类型
export const IMPORT_TYPE = {
  SCRIPT: 'script',
  DIRECTORY: 'directory',
  ZIP: 'zip',
  IMAGE_HOST: 'image_host'
}

// 导入类型选项
export const IMPORT_OPTIONS = [
  { label: '脚本导入', value: IMPORT_TYPE.SCRIPT },
  { label: '目录导入', value: IMPORT_TYPE.DIRECTORY },
  { label: 'ZIP导入', value: IMPORT_TYPE.ZIP },
  { label: '图床导入', value: IMPORT_TYPE.IMAGE_HOST }
]
