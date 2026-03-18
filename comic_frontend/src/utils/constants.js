import { getRawItem } from '@/runtime/storage'

/**
 * 甯搁噺瀹氫箟
 * 闆嗕腑绠＄悊搴旂敤涓殑鎵€鏈夊父閲忥紝閬垮厤纭紪鐮?
 */

// 闃呰鍣ㄧ炕椤垫ā寮?
export const PAGE_MODE = {
  LEFT_RIGHT: 'left_right',
  UP_DOWN: 'up_down'
}

// 闃呰鍣ㄨ儗鏅壊
export const BACKGROUND = {
  WHITE: 'white',
  DARK: 'dark',
  SEPIA: 'sepia',
  // Legacy value kept for backward compatibility with old local data.
  EYE_PROTECTION: 'eye_protection'
}

// 鑳屾櫙鑹插搴旂殑棰滆壊鍊?
export const BACKGROUND_COLORS = {
  [BACKGROUND.WHITE]: '#ffffff',
  [BACKGROUND.DARK]: '#1a1a1a',
  [BACKGROUND.SEPIA]: '#c7edcc',
  [BACKGROUND.EYE_PROTECTION]: '#c7edcc'
}

// 榛樿閰嶇疆
export const DEFAULT_CONFIG = {
  PAGE_MODE: PAGE_MODE.LEFT_RIGHT,
  BACKGROUND: BACKGROUND.WHITE,
  AUTO_HIDE_TOOLBAR: true,
  SHOW_PAGE_NUMBER: true,
  AUTO_DOWNLOAD_PREVIEW_IMPORT_ASSETS: true
}

// 璇勫垎鑼冨洿
export const SCORE_RANGE = {
  MIN: 0,
  MAX: 10
}

// 缂撳瓨杩囨湡鏃堕棿锛堟绉掞級
export const CACHE_EXPIRY = {
  COMIC_LIST: getCacheExpiry(),    // 鍔ㄦ€佽幏鍙?
  COMIC_DETAIL: getCacheExpiry(),  // 鍔ㄦ€佽幏鍙?
  TAGS: getCacheExpiry() * 2,      // 2鍊嶆椂闂?
  IMAGES: getCacheExpiry() * 6,    // 6鍊嶆椂闂?
  AUTHORS: getCacheExpiry() * 2,   // 浣滆€呭垪琛ㄧ紦瀛?
  AUTHOR_WORKS: getCacheExpiry()   // 浣滆€呬綔鍝佺紦瀛?
}

// 鑾峰彇缂撳瓨杩囨湡鏃堕棿锛堟敮鎸佺敤鎴疯嚜瀹氫箟锛?
function getCacheExpiry() {
  const minutes = parseInt(getRawItem('cache_expiry_minutes'), 10)
  if (minutes && minutes > 0) {
    return minutes * 60 * 1000
  }
  return 30 * 60 * 1000 // 榛樿30鍒嗛挓
}

// 鏈湴瀛樺偍閿悕
export const STORAGE_KEYS = {
  CONFIG: 'comic_config',
  READ_PROGRESS: 'comic_read_progress',
  CACHE: 'comic_cache'
}

// 鎺掑簭绫诲瀷
export const SORT_TYPE = {
  CREATE_TIME: 'create_time',
  SCORE: 'score',
  READ_TIME: 'read_time'
}

// 鎺掑簭閫夐」
export const SORT_OPTIONS = [
  { label: 'Recently Imported', value: SORT_TYPE.CREATE_TIME },
  { label: 'Score', value: SORT_TYPE.SCORE },
  { label: 'Last Read', value: SORT_TYPE.READ_TIME }
]

// 鍥剧墖鏍煎紡
export const IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']

// 榛樿娓呭崟ID
export const DEFAULT_LIST_ID = 'list_favorites'

// 榛樿娓呭崟鍚嶇О
export const DEFAULT_LIST_NAME = '鎴戠殑鏀惰棌'

// 瀵煎叆绫诲瀷
export const IMPORT_TYPE = {
  SCRIPT: 'script',
  DIRECTORY: 'directory',
  ZIP: 'zip',
  IMAGE_HOST: 'image_host'
}

// 瀵煎叆绫诲瀷閫夐」
export const IMPORT_OPTIONS = [
  { label: '鑴氭湰瀵煎叆', value: IMPORT_TYPE.SCRIPT },
  { label: '鐩綍瀵煎叆', value: IMPORT_TYPE.DIRECTORY },
  { label: 'ZIP瀵煎叆', value: IMPORT_TYPE.ZIP },
  { label: '鍥惧簥瀵煎叆', value: IMPORT_TYPE.IMAGE_HOST }
]

