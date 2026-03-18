import {
  StorageArea,
  clearStorage,
  getRawItem,
  getStorageKeys,
  hasRawItem,
  removeRawItem,
  setRawItem
} from '@/runtime/storage'

export const StorageType = {
  LOCAL: 'localStorage',
  SESSION: 'sessionStorage'
}

function toStorageArea(type = StorageType.LOCAL) {
  return type === StorageType.SESSION ? StorageArea.SESSION : StorageArea.LOCAL
}

export function setItem(key, value, type = StorageType.LOCAL) {
  try {
    setRawItem(key, JSON.stringify(value), toStorageArea(type))
  } catch (error) {
    console.error('Storage setItem error:', error)
  }
}

export function getItem(key, defaultValue = null, type = StorageType.LOCAL) {
  try {
    const raw = getRawItem(key, toStorageArea(type))
    if (raw === null) {
      return defaultValue
    }
    return JSON.parse(raw)
  } catch (error) {
    console.error('Storage getItem error:', error)
    return defaultValue
  }
}

export function removeItem(key, type = StorageType.LOCAL) {
  try {
    removeRawItem(key, toStorageArea(type))
  } catch (error) {
    console.error('Storage removeItem error:', error)
  }
}

export function clear(type = StorageType.LOCAL) {
  try {
    clearStorage(toStorageArea(type))
  } catch (error) {
    console.error('Storage clear error:', error)
  }
}

export function getKeys(type = StorageType.LOCAL) {
  try {
    return getStorageKeys(toStorageArea(type))
  } catch (error) {
    console.error('Storage getKeys error:', error)
    return []
  }
}

export function hasItem(key, type = StorageType.LOCAL) {
  try {
    return hasRawItem(key, toStorageArea(type))
  } catch (error) {
    console.error('Storage hasItem error:', error)
    return false
  }
}

export function setItemWithExpiry(key, value, expireTime, type = StorageType.LOCAL) {
  const item = {
    value,
    expiry: Date.now() + expireTime
  }
  setItem(key, item, type)
}

export function getItemWithExpiry(key, defaultValue = null, type = StorageType.LOCAL) {
  const item = getItem(key, null, type)
  if (!item) {
    return defaultValue
  }

  if (item.expiry && Date.now() > item.expiry) {
    removeItem(key, type)
    return defaultValue
  }

  return item.value
}

export function createNamespacedStorage(namespace, type = StorageType.LOCAL) {
  const prefix = `${namespace}:`

  return {
    set(key, value) {
      setItem(`${prefix}${key}`, value, type)
    },
    get(key, defaultValue = null) {
      return getItem(`${prefix}${key}`, defaultValue, type)
    },
    remove(key) {
      removeItem(`${prefix}${key}`, type)
    },
    keys() {
      const allKeys = getKeys(type)
      return allKeys
        .filter(key => key.startsWith(prefix))
        .map(key => key.slice(prefix.length))
    },
    clear() {
      const keys = this.keys()
      keys.forEach(key => this.remove(key))
    },
    setWithExpiry(key, value, expireTime) {
      setItemWithExpiry(`${prefix}${key}`, value, expireTime, type)
    },
    getWithExpiry(key, defaultValue = null) {
      return getItemWithExpiry(`${prefix}${key}`, defaultValue, type)
    }
  }
}
