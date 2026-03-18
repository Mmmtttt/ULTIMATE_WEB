import {
  resolveBackendApiUrl,
  resolveBackendOrigin,
  resolveBackendUrl
} from '@/runtime/endpoint'

export function getBackendOrigin() {
  return resolveBackendOrigin()
}

export function toBackendUrl(path) {
  return resolveBackendUrl(path)
}

export function toBackendApiUrl(path) {
  return resolveBackendApiUrl(path)
}

