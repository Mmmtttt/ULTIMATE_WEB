import axios from 'axios'

const getBaseURL = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL
  }

  // 开发环境直连后端，避免本机代理目标端口被其他进程占用导致误路由
  if (import.meta.env.DEV) {
    const protocol = window.location.protocol
    const hostname = window.location.hostname
    const backendPort = import.meta.env.VITE_BACKEND_PORT || 5000
    return `${protocol}//${hostname}:${backendPort}/api`
  }

  return '/api'
}

const request = axios.create({
  baseURL: getBaseURL(),
  timeout: 30000
})

// 请求拦截器
request.interceptors.request.use(
  config => {
    // 可以在这里添加token等
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  response => {
    const res = response.data
    if (res.code === 200) {
      return res
    } else {
      // 处理错误
      console.error('请求失败:', res.msg)
      return Promise.reject(new Error(res.msg || '请求失败'))
    }
  },
  error => {
    console.error('网络错误:', error)
    return Promise.reject(error)
  }
)

export default request
