// API 配置
// 使用相对路径，让请求通过 Vite 代理转发

const getBaseURL = () => {
  return ''
}

const API_BASE_URL = getBaseURL()

export default {
  baseURL: API_BASE_URL,
  
  getFullUrl: (path) => {
    if (path.startsWith('http')) return path
    return `${getBaseURL()}${path}`
  },
  
  getImageUrl: (comicId, pageNum) => {
    return `/api/v1/comic/image?comic_id=${comicId}&page_num=${pageNum}`
  },
  
  getCoverUrl: (coverPath) => {
    if (!coverPath) return ''
    if (coverPath.startsWith('http')) return coverPath
    return coverPath
  }
}
