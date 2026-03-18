/**
 * 鍥剧墖鐩稿叧 API
 */
import request from './request'
import { toBackendApiUrl, toBackendUrl } from '@/utils/url'

/**
 * 鏋勫缓鍥剧墖 URL
 * @param {string} comicId - 婕敾ID
 * @param {number} pageNum - 椤电爜
 * @param {string} source - 鍥剧墖鏉ユ簮锛坙ocal/image_host锛?
 * @returns {string} 鍥剧墖URL
 */
export function buildImageUrl(comicId, pageNum, source = 'local') {
  const params = new URLSearchParams()
  params.append('comic_id', comicId)
  params.append('page_num', pageNum)
  if (source !== 'local') {
    params.append('source', source)
  }
  return toBackendApiUrl(`/v1/comic/image?${params.toString()}`)
}

/**
 * 鏋勫缓灏侀潰 URL
 * @param {string} coverPath - 灏侀潰璺緞
 * @returns {string} 灏侀潰URL
 */
export function buildCoverUrl(coverPath) {
  let normalizedPath = ''
  if (typeof coverPath === 'string') {
    normalizedPath = coverPath.trim()
  } else if (coverPath && typeof coverPath === 'object') {
    normalizedPath = String(
      coverPath.cover_path_local ||
      coverPath.cover_path ||
      coverPath.cover_url ||
      coverPath.thumbnail_url ||
      ''
    ).trim()
  } else if (coverPath !== null && coverPath !== undefined) {
    normalizedPath = String(coverPath).trim()
  }

  normalizedPath = String(normalizedPath || '').trim()

  if (!normalizedPath) {
    return '/default-cover.jpg'
  }

  if (normalizedPath.startsWith('/')) {
    return toBackendUrl(normalizedPath)
  }

  if (normalizedPath.startsWith('http')) {
    const match = normalizedPath.match(/\/(\d+)\.jpg$/)
    if (match) {
      const comicId = match[1]
      return toBackendUrl(`/static/cover/JM/${comicId}.jpg`)
    }
    return normalizedPath
  }

  return toBackendUrl(normalizedPath)
}
/**
 * 鏋勫缓缂╃暐鍥?URL
 * @param {string} comicId - 婕敾ID
 * @param {number} pageNum - 椤电爜
 * @returns {string} 缂╃暐鍥綰RL
 */
export function buildThumbnailUrl(comicId, pageNum) {
  return toBackendApiUrl(`/v1/comic/thumbnail?comic_id=${comicId}&page_num=${pageNum}`)
}

export const imageApi = {
  /**
   * 鑾峰彇鍥剧墖锛堢敤浜庣洿鎺ヤ笅杞芥垨棰勮锛?
   * @param {string} comicId - 婕敾ID
   * @param {number} pageNum - 椤电爜
   * @param {string} source - 鍥剧墖鏉ユ簮
   * @returns {string} 鍥剧墖URL
   */
  getImageUrl: buildImageUrl,
  
  /**
   * 鑾峰彇灏侀潰URL
   * @param {string} coverPath - 灏侀潰璺緞
   * @returns {string} 灏侀潰URL
   */
  getCoverUrl: buildCoverUrl,
  
  /**
   * 鑾峰彇缂╃暐鍥綰RL
   * @param {string} comicId - 婕敾ID
   * @param {number} pageNum - 椤电爜
   * @returns {string} 缂╃暐鍥綰RL
   */
  getThumbnailUrl: buildThumbnailUrl,
  
  /**
   * 棰勫姞杞藉浘鐗?
   * @param {string} url - 鍥剧墖URL
   * @returns {Promise}
   */
  preload: (url) => {
    return new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => resolve(url)
      img.onerror = () => reject(new Error(`Failed to load image: ${url}`))
      img.src = url
    })
  },
  
  /**
   * 鎵归噺棰勫姞杞藉浘鐗?
   * @param {string[]} urls - 鍥剧墖URL鏁扮粍
   * @param {number} concurrency - 骞跺彂鏁?
   * @returns {Promise}
   */
  preloadBatch: async (urls, concurrency = 3) => {
    const results = []
    const executing = []
    
    for (const url of urls) {
      const promise = imageApi.preload(url).then(
        () => ({ url, success: true }),
        (error) => ({ url, success: false, error })
      )
      
      results.push(promise)
      
      if (urls.indexOf(url) >= concurrency) {
        executing.push(promise)
        if (executing.length >= concurrency) {
          await Promise.race(executing)
          executing.splice(executing.findIndex(p => p === promise), 1)
        }
      }
    }
    
    return Promise.all(results)
  }
}
