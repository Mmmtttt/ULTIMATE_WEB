/**
 * 图片相关 API
 */
import request from './request'
import { toBackendApiUrl, toBackendUrl } from '@/utils/url'

/**
 * 构建图片 URL
 * @param {string} comicId - 漫画ID
 * @param {number} pageNum - 页码
 * @param {string} source - 图片来源（local/image_host）
 * @returns {string} 图片URL
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
 * 构建封面 URL
 * @param {string} coverPath - 封面路径
 * @returns {string} 封面URL
 */
export function buildCoverUrl(coverPath) {
  if (!coverPath) {
    return '/default-cover.jpg'
  }
  
  // 如果是本地路径，直接返回
  if (coverPath.startsWith('/')) {
    return toBackendUrl(coverPath)
  }
  
  // 如果是图床URL，提取ID并构建本地路径
  if (coverPath.startsWith('http')) {
    // 尝试从图床URL中提取漫画ID
    // 例如: https://cdn-msp3.18comic.vip/media/albums/1257321.jpg
    const match = coverPath.match(/\/(\d+)\.jpg$/)
    if (match) {
      const comicId = match[1]
      // 返回本地路径
      return toBackendUrl(`/static/cover/JM/${comicId}.jpg`)
    }
    // 如果无法提取ID，返回原图床URL
    return coverPath
  }
  
  // 其他情况，作为本地路径处理
  return toBackendUrl(coverPath)
}

/**
 * 构建缩略图 URL
 * @param {string} comicId - 漫画ID
 * @param {number} pageNum - 页码
 * @returns {string} 缩略图URL
 */
export function buildThumbnailUrl(comicId, pageNum) {
  return toBackendApiUrl(`/v1/comic/thumbnail?comic_id=${comicId}&page_num=${pageNum}`)
}

export const imageApi = {
  /**
   * 获取图片（用于直接下载或预览）
   * @param {string} comicId - 漫画ID
   * @param {number} pageNum - 页码
   * @param {string} source - 图片来源
   * @returns {string} 图片URL
   */
  getImageUrl: buildImageUrl,
  
  /**
   * 获取封面URL
   * @param {string} coverPath - 封面路径
   * @returns {string} 封面URL
   */
  getCoverUrl: buildCoverUrl,
  
  /**
   * 获取缩略图URL
   * @param {string} comicId - 漫画ID
   * @param {number} pageNum - 页码
   * @returns {string} 缩略图URL
   */
  getThumbnailUrl: buildThumbnailUrl,
  
  /**
   * 预加载图片
   * @param {string} url - 图片URL
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
   * 批量预加载图片
   * @param {string[]} urls - 图片URL数组
   * @param {number} concurrency - 并发数
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
