import { defineStore } from 'pinia'
import { comicApi } from '../../api/comic'

const CACHE_DURATION = 5 * 60 * 1000  // 5分钟缓存

export const useComicStore = defineStore('comic', {
  state: () => ({
    comics: [],
    currentComic: null,
    loading: false,
    error: null,
    caches: {
      list: null,
      listTime: 0,
      detail: {},
      detailTime: {},
      images: {},
      imagesTime: {},
      tags: null,
      tagsTime: 0
    }
  }),
  
  getters: {
    comicList: (state) => state.comics,
    currentComicInfo: (state) => state.currentComic,
    isLoading: (state) => state.loading,
    cacheStatus: (state) => ({
      list: state.caches.list ? 'cached' : 'empty',
      detailCount: Object.keys(state.caches.detail).length,
      imagesCount: Object.keys(state.caches.images).length,
      tags: state.caches.tags ? 'cached' : 'empty'
    })
  },
  
  actions: {
    async fetchComics() {
      const now = Date.now()
      
      if (this.caches.list && now - this.caches.listTime < CACHE_DURATION) {
        console.log('[Cache] 使用缓存的漫画列表', { age: Math.round((now - this.caches.listTime) / 1000) + 's' })
        this.comics = this.caches.list
        return this.caches.list
      }
      
      console.log('[Cache] 重新获取漫画列表')
      
      this.loading = true
      this.error = null
      try {
        const response = await comicApi.getList()
        this.comics = response.data
        this.caches.list = response.data
        this.caches.listTime = now
        return response.data
      } catch (error) {
        this.error = error.message
        console.error('获取漫画列表失败:', error)
        return null
      } finally {
        this.loading = false
      }
    },
    
    async fetchComicDetail(id) {
      const now = Date.now()
      
      if (this.caches.detail[id] && now - this.caches.detailTime[id] < CACHE_DURATION) {
        console.log('[Cache] 使用缓存的漫画详情', { id, age: Math.round((now - this.caches.detailTime[id]) / 1000) + 's' })
        this.currentComic = this.caches.detail[id]
        return this.caches.detail[id]
      }
      
      console.log('[Cache] 重新获取漫画详情', { id })
      
      this.loading = true
      this.error = null
      try {
        const response = await comicApi.getDetail(id)
        this.currentComic = response.data
        this.caches.detail[id] = response.data
        this.caches.detailTime[id] = now
        return response.data
      } catch (error) {
        this.error = error.message
        console.error('获取漫画详情失败:', error)
        return null
      } finally {
        this.loading = false
      }
    },
    
    async fetchImages(id) {
      const now = Date.now()
      
      if (this.caches.images[id] && now - this.caches.imagesTime[id] < CACHE_DURATION) {
        console.log('[Cache] 使用缓存的图片列表', { id, age: Math.round((now - this.caches.imagesTime[id]) / 1000) + 's' })
        return this.caches.images[id]
      }
      
      console.log('[Cache] 重新获取图片列表', { id })
      
      try {
        const response = await comicApi.getImages(id)
        this.caches.images[id] = response.data
        this.caches.imagesTime[id] = now
        return response.data
      } catch (error) {
        console.error('获取图片列表失败:', error)
        return null
      }
    },
    
    async fetchTags() {
      const now = Date.now()
      
      if (this.caches.tags && now - this.caches.tagsTime < CACHE_DURATION) {
        console.log('[Cache] 使用缓存的标签列表', { age: Math.round((now - this.caches.tagsTime) / 1000) + 's' })
        return this.caches.tags
      }
      
      console.log('[Cache] 重新获取标签列表')
      
      try {
        const response = await comicApi.getTags()
        this.caches.tags = response.data
        this.caches.tagsTime = now
        return response.data
      } catch (error) {
        console.error('获取标签列表失败:', error)
        return null
      }
    },
    
    clearCache(type = 'all', id = null) {
      if (type === 'all' || type === 'list') {
        this.caches.list = null
        this.caches.listTime = 0
      }
      if (type === 'all' || type === 'detail') {
        if (id) {
          delete this.caches.detail[id]
          delete this.caches.detailTime[id]
        } else {
          this.caches.detail = {}
          this.caches.detailTime = {}
        }
      }
      if (type === 'all' || type === 'images') {
        if (id) {
          delete this.caches.images[id]
          delete this.caches.imagesTime[id]
        } else {
          this.caches.images = {}
          this.caches.imagesTime = {}
        }
      }
      if (type === 'all' || type === 'tags') {
        this.caches.tags = null
        this.caches.tagsTime = 0
      }
    },
    
    async saveProgress(id, page) {
      try {
        const response = await comicApi.saveProgress(id, page)
        const comic = this.comics.find(c => c.id === id)
        if (comic) {
          comic.current_page = page
          comic.last_read_time = response.data.last_read_time
        }
        if (this.currentComic && this.currentComic.id === id) {
          this.currentComic.current_page = page
          this.currentComic.last_read_time = response.data.last_read_time
        }
        return response
      } catch (error) {
        console.error('保存阅读进度失败:', error)
        throw error
      }
    }
  }
})
