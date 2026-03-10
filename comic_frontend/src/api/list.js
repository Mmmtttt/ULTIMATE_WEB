import request from './request'

export const listApi = {
  getListAll(contentType = null) {
    const params = contentType ? { content_type: contentType } : {}
    return request.get('/v1/list/list', { params })
  },
  
  getDetail(listId) {
    return request.get('/v1/list/detail', { params: { list_id: listId } })
  },
  
  create(name, desc = '', contentType = 'comic') {
    return request.post('/v1/list/add', { list_name: name, desc, content_type: contentType })
  },
  
  update(listId, name = null, desc = null) {
    return request.put('/v1/list/edit', { list_id: listId, list_name: name, desc })
  },
  
  delete(listId) {
    return request.delete('/v1/list/delete', { params: { list_id: listId } })
  },
  
  bindComics(listId, comicIds, source = 'local') {
    return request.put('/v1/list/comic/bind', { list_id: listId, comic_id_list: comicIds, source })
  },
  
  removeComics(listId, comicIds, source = 'local') {
    const params = new URLSearchParams()
    params.append('list_id', listId)
    params.append('source', source)
    comicIds.forEach(id => params.append('comic_id_list', id))
    return request.delete('/v1/list/comic/remove', { params })
  },
  
  toggleFavorite(comicId, source = 'local') {
    return request.put('/v1/list/favorite/toggle', { comic_id: comicId, source })
  },
  
  checkFavorite(comicId, source = 'local') {
    return request.get('/v1/list/favorite/check', { params: { comic_id: comicId, source } })
  },

  bindVideos(listId, videoIds, source = 'local') {
    return request.put('/v1/list/video/bind', { list_id: listId, video_id_list: videoIds, source })
  },

  removeVideos(listId, videoIds, source = 'local') {
    const params = new URLSearchParams()
    params.append('list_id', listId)
    params.append('source', source)
    videoIds.forEach(id => params.append('video_id_list', id))
    return request.delete('/v1/list/video/remove', { params })
  },

  toggleFavoriteVideo(videoId, source = 'local') {
    return request.put('/v1/list/video/favorite/toggle', { video_id: videoId, source })
  },

  checkFavoriteVideo(videoId, source = 'local') {
    return request.get('/v1/list/video/favorite/check', { params: { video_id: videoId, source } })
  },

  getPlatformUserLists(platform) {
    return request.get('/v1/list/platform/lists', { params: { platform } })
  },

  getPlatformListDetail(platform, listId) {
    return request.get('/v1/list/platform/list/detail', { params: { platform, list_id: listId } })
  },

  importPlatformList(platform, platformListId, platformListName, source = 'local') {
    return request.post('/v1/list/import', { platform, platform_list_id: platformListId, platform_list_name: platformListName, source })
  },

  syncPlatformList(listId) {
    return request.post('/v1/list/sync', { list_id: listId })
  }
}

export default listApi
