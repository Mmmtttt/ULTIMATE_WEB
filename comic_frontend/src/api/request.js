import axios from 'axios'
import { getLocation } from '@/runtime/browser'

const getBaseURL = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL
  }

  if (import.meta.env.DEV) {
    const location = getLocation()
    if (!location) {
      return '/api'
    }
    const backendPort = import.meta.env.VITE_BACKEND_PORT || 5000
    return `${location.protocol}//${location.hostname}:${backendPort}/api`
  }

  return '/api'
}

const request = axios.create({
  baseURL: getBaseURL(),
  timeout: 30000
})

request.interceptors.request.use(
  config => config,
  error => Promise.reject(error)
)

request.interceptors.response.use(
  response => {
    if (response.config.responseType === 'blob' || response.config.responseType === 'arraybuffer') {
      return response
    }

    const res = response.data
    if (res.code === 200) {
      return res
    }
    return Promise.reject(new Error(res.msg || 'Request failed'))
  },
  error => Promise.reject(error)
)

export default request
