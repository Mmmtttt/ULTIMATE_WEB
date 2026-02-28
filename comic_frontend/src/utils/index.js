/**
 * 工具函数统一导出
 */

// 常量
export * from './constants'

// 格式化工具
export * from './formatters'

// 校验工具
export * from './validators'

// 存储工具
export * from './storage'

/**
 * 防抖函数
 * @param {Function} fn - 要执行的函数
 * @param {number} delay - 延迟时间（毫秒）
 * @returns {Function} 防抖后的函数
 */
export function debounce(fn, delay = 300) {
  let timer = null
  return function (...args) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      fn.apply(this, args)
    }, delay)
  }
}
