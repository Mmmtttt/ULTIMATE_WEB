import axios from 'axios'
import { showFailToast } from 'vant'
import { getLocation } from '@/runtime/browser'

const getBaseURL = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL
  }

  const location = getLocation()
  if (!location) {
    return '/api'
  }

  const backendPort = import.meta.env.VITE_BACKEND_PORT || 5000
  return `${location.protocol}//${location.hostname}:${backendPort}`
}

const request = axios.create({
  baseURL: getBaseURL(),
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
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
    if (res && res.code !== 200) {
      showFailToast(res.msg || 'Request failed')
      return Promise.reject(new Error(res.msg || 'Request failed'))
    }
    return res
  },
  error => {
    if (error.message.includes('Network Error')) {
      showFailToast('Network error, please check your connection')
    } else if (error.message.includes('timeout')) {
      showFailToast('Request timeout, please retry')
    } else if (error.response) {
      const status = error.response.status
      switch (status) {
        case 401:
          showFailToast('Unauthorized')
          break
        case 403:
          showFailToast('Forbidden')
          break
        case 404:
          showFailToast('Resource not found')
          break
        case 500:
          showFailToast('Internal server error')
          break
        default:
          showFailToast(`Request failed (${status})`)
      }
    } else {
      showFailToast('Request failed, please retry')
    }

    return Promise.reject(error)
  }
)

export default request
