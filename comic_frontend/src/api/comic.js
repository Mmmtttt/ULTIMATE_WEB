import request from './request'

export const comicApi = {
  init: (data) => {
    return request.post('/v1/comic/init', data)
  },
  
  getList: () => {
    return request.get('/v1/comic/list')
  },
  
  getDetail: (comicId) => {
    return request.get('/v1/comic/detail', {
      params: { comic_id: comicId }
    })
  },
  
  getImages: (comicId) => {
    return request.get('/v1/comic/images', {
      params: { comic_id: comicId }
    })
  },
  
  saveProgress: (comicId, currentPage) => {
    return request.put('/v1/comic/progress', {
      comic_id: comicId,
      current_page: currentPage
    })
  },
  
  updateScore: (comicId, score) => {
    return request.put('/v1/comic/score', {
      comic_id: comicId,
      score: score
    })
  },
  
  bindTags: (comicId, tagIdList) => {
    return request.put('/v1/comic/tag/bind', {
      comic_id: comicId,
      tag_id_list: tagIdList
    })
  },
  
  batchAddTags: (comicIds, tagIds) => {
    return request.put('/v1/comic/tag/batch-add', {
      comic_ids: comicIds,
      tag_ids: tagIds
    })
  },
  
  batchRemoveTags: (comicIds, tagIds) => {
    return request.put('/v1/comic/tag/batch-remove', {
      comic_ids: comicIds,
      tag_ids: tagIds
    })
  },
  
  editComic: (comicId, data) => {
    return request.put('/v1/comic/edit', {
      comic_id: comicId,
      ...data
    })
  },
  
  search: (keyword) => {
    return request.get('/v1/comic/search', {
      params: { keyword }
    })
  },
  
  filter: (includeTagIds = [], excludeTagIds = []) => {
    const params = new URLSearchParams()
    includeTagIds.forEach(id => params.append('include_tag_ids', id))
    excludeTagIds.forEach(id => params.append('exclude_tag_ids', id))
    return request.get(`/v1/comic/filter?${params.toString()}`)
  },
  
  getTags: () => {
    return request.get('/v1/comic/tags')
  }
}

export const tagApi = {
  add: (tagName) => {
    return request.post('/v1/tag/add', { tag_name: tagName })
  },
  
  list: () => {
    return request.get('/v1/tag/list')
  },
  
  edit: (tagId, tagName) => {
    return request.put('/v1/tag/edit', { tag_id: tagId, tag_name: tagName })
  },
  
  delete: (tagId) => {
    return request.delete('/v1/tag/delete', { data: { tag_id: tagId } })
  },
  
  getComics: (tagId) => {
    return request.get('/v1/tag/comics', {
      params: { tag_id: tagId }
    })
  }
}
