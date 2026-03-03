import axios from 'axios'
import { showFailToast } from 'vant'

// 动态获取 baseURL
// 如果是开发环境且没有设置环境变量，使用当前页面的主机名
const getBaseURL = () => {
  // 如果设置了环境变量，使用环境变量
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL
  }
  
  // 开发环境使用编译时注入的后端端口（来自 server_config.json）
  const port = import.meta.env.VITE_BACKEND_PORT || 5000
  
  // 否则使用当前页面的主机名（支持局域网访问）
  const protocol = window.location.protocol // http: 或 https:
  const hostname = window.location.hostname // localhost 或 IP地址
  
  return `${protocol}//${hostname}:${port}`
}

// 创建 axios 实例
const request = axios.create({
  baseURL: getBaseURL(),
  timeout: 30000, // 30秒超时
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
request.interceptors.request.use(
  config => {
    // 可以在这里添加 token 等认证信息
    return config
  },
  error => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  response => {
    const res = response.data
    
    // 如果是二进制数据，直接返回
    if (response.config.responseType === 'blob' || response.config.responseType === 'arraybuffer') {
      return response
    }
    
    // 如果是 API 响应，检查 code
    if (res && res.code !== 200) {
      // 显示错误消息
      showFailToast(res.msg || '请求失败')
      return Promise.reject(new Error(res.msg || '请求失败'))
    }
    
    return res
  },
  error => {
    console.error('响应错误:', error)
    
    // 处理网络错误
    if (error.message.includes('Network Error')) {
      showFailToast('网络错误，请检查网络连接')
    } else if (error.message.includes('timeout')) {
      showFailToast('请求超时，请稍后重试')
    } else if (error.response) {
      // 服务器返回错误
      const status = error.response.status
      switch (status) {
        case 401:
          showFailToast('未授权，请重新登录')
          break
        case 403:
          showFailToast('权限不足')
          break
        case 404:
          showFailToast('请求的资源不存在')
          break
        case 500:
          showFailToast('服务器内部错误')
          break
        default:
          showFailToast(`请求失败 (${status})`)
      }
    } else {
      showFailToast('请求失败，请稍后重试')
    }
    
    return Promise.reject(error)
  }
)

export default request
