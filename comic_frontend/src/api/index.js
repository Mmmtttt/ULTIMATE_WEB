/**
 * API unified exports.
 */

export { default as request } from './request'

export { comicApi } from './comic'
export { videoApi, actorApi } from './video'
export { recommendationApi } from './recommendation'
export { tagApi } from './tag'
export { listApi } from './list'
export { authorApi } from './author'
export { configApi } from './config'
export { imageApi, buildImageUrl, buildCoverUrl, buildThumbnailUrl } from './image'
export { syncApi } from './sync'

import { comicApi } from './comic'
export default comicApi
