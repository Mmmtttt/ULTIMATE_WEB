import { defineStore } from 'pinia'
import { comicApi } from '../../api/comic'

export const useComicStore = defineStore('comic', {
  state: () => ({
    comics: [],
    currentComic: null,
    loading: false,
    error: null
  }),
  
  getters: {
    comicList: (state) => state.comics,
    currentComicInfo: (state) => state.currentComic,
    isLoading: (state) => state.loading
  },
  
  actions: {
    async fetchComics() {
      this.loading = true
      this.error = null
      try {
        const response = await comicApi.getList()
        this.comics = response.data
      } catch (error) {
        this.error = error.message
        console.error('获取漫画列表失败:', error)
      } finally {
        this.loading = false
      }
    },
    
    async fetchComicDetail(id) {
      this.loading = true
      this.error = null
      try {
        const response = await comicApi.getDetail(id)
        this.currentComic = response.data
        return response.data
      } catch (error) {
        this.error = error.message
        console.error('获取漫画详情失败:', error)
        return null
      } finally {
        this.loading = false
      }
    },
    
    async saveProgress(id, page) {
      try {
        const response = await comicApi.saveProgress(id, page)
        // 更新本地状态
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
