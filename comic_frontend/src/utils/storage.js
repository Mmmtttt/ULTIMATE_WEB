/**
 * 本地存储封装
 * 提供统一的 localStorage 和 sessionStorage 操作接口
 */

/**
 * 存储类型
 */
const StorageType = {
  LOCAL: 'localStorage',
  SESSION: 'sessionStorage'
}

/**
 * 获取存储实例
 * @param {string} type - 存储类型
 * @returns {Storage} 存储实例
 */
function getStorage(type = StorageType.LOCAL) {
  return type === StorageType.SESSION ? sessionStorage : localStorage
}

/**
 * 设置存储项
 * @param {string} key - 键名
 * @param {*} value - 值
 * @param {string} type - 存储类型
 */
export function setItem(key, value, type = StorageType.LOCAL) {
  try {
    const storage = getStorage(type)
    const serializedValue = JSON.stringify(value)
    storage.setItem(key, serializedValue)
  } catch (error) {
    console.error('Storage setItem error:', error)
  }
}

/**
 * 获取存储项
 * @param {string} key - 键名
 * @param {*} defaultValue - 默认值
 * @param {string} type - 存储类型
 * @returns {*} 存储的值
 */
export function getItem(key, defaultValue = null, type = StorageType.LOCAL) {
  try {
    const storage = getStorage(type)
    const item = storage.getItem(key)
    if (item === null) {
      return defaultValue
    }
    return JSON.parse(item)
  } catch (error) {
    console.error('Storage getItem error:', error)
    return defaultValue
  }
}

/**
 * 移除存储项
 * @param {string} key - 键名
 * @param {string} type - 存储类型
 */
export function removeItem(key, type = StorageType.LOCAL) {
  try {
    const storage = getStorage(type)
    storage.removeItem(key)
  } catch (error) {
    console.error('Storage removeItem error:', error)
  }
}

/**
 * 清空存储
 * @param {string} type - 存储类型
 */
export function clear(type = StorageType.LOCAL) {
  try {
    const storage = getStorage(type)
    storage.clear()
  } catch (error) {
    console.error('Storage clear error:', error)
  }
}

/**
 * 获取所有键名
 * @param {string} type - 存储类型
 * @returns {string[]} 键名数组
 */
export function getKeys(type = StorageType.LOCAL) {
  try {
    const storage = getStorage(type)
    return Object.keys(storage)
  } catch (error) {
    console.error('Storage getKeys error:', error)
    return []
  }
}

/**
 * 检查键是否存在
 * @param {string} key - 键名
 * @param {string} type - 存储类型
 * @returns {boolean} 是否存在
 */
export function hasItem(key, type = StorageType.LOCAL) {
  try {
    const storage = getStorage(type)
    return storage.getItem(key) !== null
  } catch (error) {
    console.error('Storage hasItem error:', error)
    return false
  }
}

/**
 * 设置带有过期时间的存储项
 * @param {string} key - 键名
 * @param {*} value - 值
 * @param {number} expireTime - 过期时间（毫秒）
 * @param {string} type - 存储类型
 */
export function setItemWithExpiry(key, value, expireTime, type = StorageType.LOCAL) {
  const item = {
    value,
    expiry: Date.now() + expireTime
  }
  setItem(key, item, type)
}

/**
 * 获取带有过期时间的存储项
 * @param {string} key - 键名
 * @param {*} defaultValue - 默认值
 * @param {string} type - 存储类型
 * @returns {*} 存储的值
 */
export function getItemWithExpiry(key, defaultValue = null, type = StorageType.LOCAL) {
  const item = getItem(key, null, type)
  
  if (!item) {
    return defaultValue
  }
  
  // 检查是否过期
  if (item.expiry && Date.now() > item.expiry) {
    removeItem(key, type)
    return defaultValue
  }
  
  return item.value
}

/**
 * 创建命名空间的存储对象
 * @param {string} namespace - 命名空间
 * @param {string} type - 存储类型
 * @returns {object} 存储对象
 */
export function createNamespacedStorage(namespace, type = StorageType.LOCAL) {
  const prefix = `${namespace}:`
  
  return {
    /**
     * 设置存储项
     */
    set(key, value) {
      setItem(`${prefix}${key}`, value, type)
    },
    
    /**
     * 获取存储项
     */
    get(key, defaultValue = null) {
      return getItem(`${prefix}${key}`, defaultValue, type)
    },
    
    /**
     * 移除存储项
     */
    remove(key) {
      removeItem(`${prefix}${key}`, type)
    },
    
    /**
     * 获取所有键名
     */
    keys() {
      const allKeys = getKeys(type)
      return allKeys
        .filter(key => key.startsWith(prefix))
        .map(key => key.slice(prefix.length))
    },
    
    /**
     * 清空命名空间下的所有存储项
     */
    clear() {
      const keys = this.keys()
      keys.forEach(key => this.remove(key))
    },
    
    /**
     * 设置带有过期时间的存储项
     */
    setWithExpiry(key, value, expireTime) {
      setItemWithExpiry(`${prefix}${key}`, value, expireTime, type)
    },
    
    /**
     * 获取带有过期时间的存储项
     */
    getWithExpiry(key, defaultValue = null) {
      return getItemWithExpiry(`${prefix}${key}`, defaultValue, type)
    }
  }
}

// 导出存储类型常量
export { StorageType }
