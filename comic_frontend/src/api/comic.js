import request from './request'

export const comicApi = {
  // 漫画初始化
  init: (data) => {
    return request.post('/v1/comic/init', data)
  },
  
  // 获取漫画列表
  getList: () => {
    return request.get('/v1/comic/list')
  },
  
  // 获取漫画详情
  getDetail: (comicId) => {
    return request.get('/v1/comic/detail', {
      params: { comic_id: comicId }
    })
  },
  
  // 获取图片列表
  getImages: (comicId) => {
    return request.get('/v1/comic/images', {
      params: { comic_id: comicId }
    })
  },
  
  // 保存阅读进度
  saveProgress: (comicId, currentPage) => {
    return request.put('/v1/comic/progress', {
      comic_id: comicId,
      current_page: currentPage
    })
  }
}
