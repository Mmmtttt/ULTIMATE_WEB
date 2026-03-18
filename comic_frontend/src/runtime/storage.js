import { getWindow } from './browser'

export const StorageArea = {
  LOCAL: 'local',
  SESSION: 'session'
}

function createMemoryStorage() {
  const map = new Map()
  return {
    getItem(key) {
      return map.has(key) ? map.get(key) : null
    },
    setItem(key, value) {
      map.set(key, String(value))
    },
    removeItem(key) {
      map.delete(key)
    },
    clear() {
      map.clear()
    },
    keys() {
      return Array.from(map.keys())
    }
  }
}

const localMemoryStorage = createMemoryStorage()
const sessionMemoryStorage = createMemoryStorage()

function getNativeStorage(area) {
  const win = getWindow()
  if (!win) return null
  if (area === StorageArea.SESSION) {
    return win.sessionStorage ?? null
  }
  return win.localStorage ?? null
}

function getStorageBackend(area = StorageArea.LOCAL) {
  const nativeStorage = getNativeStorage(area)
  if (nativeStorage) {
    return {
      getItem: (key) => nativeStorage.getItem(key),
      setItem: (key, value) => nativeStorage.setItem(key, value),
      removeItem: (key) => nativeStorage.removeItem(key),
      clear: () => nativeStorage.clear(),
      keys: () => Object.keys(nativeStorage)
    }
  }

  return area === StorageArea.SESSION ? sessionMemoryStorage : localMemoryStorage
}

export function setRawItem(key, value, area = StorageArea.LOCAL) {
  const backend = getStorageBackend(area)
  backend.setItem(key, value)
}

export function getRawItem(key, area = StorageArea.LOCAL) {
  const backend = getStorageBackend(area)
  return backend.getItem(key)
}

export function removeRawItem(key, area = StorageArea.LOCAL) {
  const backend = getStorageBackend(area)
  backend.removeItem(key)
}

export function clearStorage(area = StorageArea.LOCAL) {
  const backend = getStorageBackend(area)
  backend.clear()
}

export function getStorageKeys(area = StorageArea.LOCAL) {
  const backend = getStorageBackend(area)
  return backend.keys()
}

export function hasRawItem(key, area = StorageArea.LOCAL) {
  return getRawItem(key, area) !== null
}
