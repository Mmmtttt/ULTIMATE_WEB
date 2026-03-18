import axios from 'axios'
import { resolveApiBaseUrl } from '@/runtime/endpoint'

const request = axios.create({
  baseURL: resolveApiBaseUrl(),
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
