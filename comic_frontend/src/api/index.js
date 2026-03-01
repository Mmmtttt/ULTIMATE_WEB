/**
 * API 统一导出
 * 集中管理所有 API 模块
 */

// 请求实例
export { default as request } from './request'

// 漫画 API
export { comicApi } from './comic'

// 推荐漫画 API
export { recommendationApi } from './recommendation'

// 标签 API
export { tagApi } from './tag'

// 清单 API
export { listApi } from './list'

// 配置 API
export { configApi } from './config'

// 图片 API
export { imageApi, buildImageUrl, buildCoverUrl, buildThumbnailUrl } from './image'

// 为了保持向后兼容，默认导出 comicApi
import { comicApi } from './comic'
export default comicApi
