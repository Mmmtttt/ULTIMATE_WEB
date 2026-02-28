/**
 * 应用配置常量
 * 与 utils/constants.js 不同，这里存储的是应用级别的配置
 */

// 应用信息
export const APP_INFO = {
  NAME: '漫画阅读器',
  VERSION: '1.0.0',
  DESCRIPTION: '个人漫画管理与阅读系统'
}

// 分页配置
export const PAGINATION = {
  DEFAULT_PAGE_SIZE: 20,
  PAGE_SIZE_OPTIONS: [10, 20, 50, 100]
}

// 阅读器配置
export const READER_CONFIG = {
  // 缩放配置
  SCALE: {
    MIN: 0.5,
    MAX: 2.0,
    STEP: 0.1,
    DEFAULT: 1.0
  },
  
  // 预加载配置
  PRELOAD: {
    DEFAULT: 3,
    MIN: 1,
    MAX: 10
  },
  
  // 滚动配置
  SCROLL: {
    SMOOTH: true,
    BEHAVIOR: 'smooth'
  }
}

// 移动端配置
export const MOBILE_CONFIG = {
  // 触摸配置
  TOUCH: {
    SWIPE_THRESHOLD: 50,      // 滑动阈值（像素）
    TAP_DELAY: 300,           // 点击延迟（毫秒）
    DOUBLE_TAP_DELAY: 300     // 双击延迟（毫秒）
  },
  
  // 缩放配置
  PINCH: {
    MIN_SCALE: 0.5,
    MAX_SCALE: 3.0
  }
}

// 动画配置
export const ANIMATION = {
  DURATION: {
    FAST: 150,
    NORMAL: 300,
    SLOW: 500
  },
  EASING: {
    DEFAULT: 'ease',
    IN_OUT: 'ease-in-out',
    SPRING: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)'
  }
}

// 消息提示配置
export const MESSAGE = {
  DURATION: {
    SHORT: 2000,
    NORMAL: 3000,
    LONG: 5000
  },
  POSITION: {
    TOP: 'top',
    CENTER: 'center',
    BOTTOM: 'bottom'
  }
}

// 图片配置
export const IMAGE_CONFIG = {
  // 支持的格式
  FORMATS: ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'],
  
  // 封面配置
  COVER: {
    WIDTH: 300,
    HEIGHT: 400,
    QUALITY: 0.9
  },
  
  // 缩略图配置
  THUMBNAIL: {
    WIDTH: 150,
    HEIGHT: 200,
    QUALITY: 0.8
  }
}

// 导入配置
export const IMPORT_CONFIG = {
  // ZIP 配置
  ZIP: {
    MAX_SIZE: 500 * 1024 * 1024,  // 最大 500MB
    ALLOWED_FORMATS: ['.zip']
  },
  
  // 图床配置
  IMAGE_HOST: {
    TIMEOUT: 10000,  // 超时时间（毫秒）
    MAX_URLS: 1000   // 最大链接数
  }
}

// 缓存配置
export const CACHE_CONFIG = {
  // 内存缓存
  MEMORY: {
    MAX_SIZE: 50 * 1024 * 1024  // 最大 50MB
  },
  
  // 本地存储缓存
  STORAGE: {
    MAX_SIZE: 10 * 1024 * 1024  // 最大 10MB
  }
}

// 网络配置
export const NETWORK_CONFIG = {
  // 超时配置
  TIMEOUT: {
    DEFAULT: 10000,
    UPLOAD: 60000,
    DOWNLOAD: 30000
  },
  
  // 重试配置
  RETRY: {
    MAX_TIMES: 3,
    DELAY: 1000
  }
}
