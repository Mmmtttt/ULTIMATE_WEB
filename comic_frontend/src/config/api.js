// API 配置
// 动态获取当前访问的host，支持手机和电脑同时访问

const getBaseURL = () => {
  // 在浏览器环境中，使用当前访问的host
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol
    const host = window.location.hostname
    return `${protocol}//${host}:5000`
  }
  // 服务端渲染时使用默认值
  return 'http://192.168.137.1:5000'
}

const API_BASE_URL = getBaseURL()

export default {
  baseURL: API_BASE_URL,
  
  // 获取完整URL
  getFullUrl: (path) => {
    if (path.startsWith('http')) return path
    return `${getBaseURL()}${path}`
  },
  
  // 获取图片URL
  getImageUrl: (comicId, pageNum) => {
    return `${getBaseURL()}/api/v1/comic/image?comic_id=${comicId}&page_num=${pageNum}`
  },
  
  // 获取封面URL
  getCoverUrl: (coverPath) => {
    if (!coverPath) return ''
    if (coverPath.startsWith('http')) return coverPath
    return `${getBaseURL()}${coverPath}`
  }
}
