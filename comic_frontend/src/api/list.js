import request from './request'

export const listApi = {
  getListAll() {
    return request.get('/v1/list/list')
  },
  
  getDetail(listId) {
    return request.get('/v1/list/detail', { params: { list_id: listId } })
  },
  
  create(name, desc = '') {
    return request.post('/v1/list/add', { list_name: name, desc })
  },
  
  update(listId, name = null, desc = null) {
    return request.put('/v1/list/edit', { list_id: listId, list_name: name, desc })
  },
  
  delete(listId) {
    return request.delete('/v1/list/delete', { params: { list_id: listId } })
  },
  
  bindComics(listId, comicIds) {
    return request.put('/v1/list/comic/bind', { list_id: listId, comic_id_list: comicIds })
  },
  
  removeComics(listId, comicIds) {
    const params = new URLSearchParams()
    params.append('list_id', listId)
    comicIds.forEach(id => params.append('comic_id_list', id))
    return request.delete('/v1/list/comic/remove', { params })
  },
  
  toggleFavorite(comicId) {
    return request.put('/v1/list/favorite/toggle', { comic_id: comicId })
  },
  
  checkFavorite(comicId) {
    return request.get('/v1/list/favorite/check', { params: { comic_id: comicId } })
  }
}

export default listApi
