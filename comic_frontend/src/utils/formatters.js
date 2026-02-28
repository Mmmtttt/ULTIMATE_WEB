/**
 * 格式化工具
 * 提供各种数据格式化函数
 */

import { PAGE_MODE, BACKGROUND, SORT_TYPE } from './constants'

/**
 * 格式化页码显示
 * @param {number} current - 当前页
 * @param {number} total - 总页数
 * @returns {string} 格式化后的页码字符串
 */
export function formatPageDisplay(current, total) {
  return `${current} / ${total}`
}

/**
 * 格式化进度百分比
 * @param {number} current - 当前页
 * @param {number} total - 总页数
 * @returns {string} 百分比字符串
 */
export function formatProgress(current, total) {
  if (!total || total <= 0) return '0%'
  const percentage = Math.round((current / total) * 100)
  return `${percentage}%`
}

/**
 * 格式化日期时间
 * @param {string} dateStr - 日期字符串
 * @param {string} format - 格式模板
 * @returns {string} 格式化后的日期
 */
export function formatDateTime(dateStr, format = 'YYYY-MM-DD HH:mm') {
  if (!dateStr) return '-'
  
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return '-'
  
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  
  return format
    .replace('YYYY', year)
    .replace('MM', month)
    .replace('DD', day)
    .replace('HH', hours)
    .replace('mm', minutes)
}

/**
 * 格式化相对时间
 * @param {string} dateStr - 日期字符串
 * @returns {string} 相对时间描述
 */
export function formatRelativeTime(dateStr) {
  if (!dateStr) return '-'
  
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return '-'
  
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour
  const week = 7 * day
  const month = 30 * day
  
  if (diff < minute) {
    return '刚刚'
  } else if (diff < hour) {
    return `${Math.floor(diff / minute)}分钟前`
  } else if (diff < day) {
    return `${Math.floor(diff / hour)}小时前`
  } else if (diff < week) {
    return `${Math.floor(diff / day)}天前`
  } else if (diff < month) {
    return `${Math.floor(diff / week)}周前`
  } else {
    return formatDateTime(dateStr, 'YYYY-MM-DD')
  }
}

/**
 * 格式化评分显示
 * @param {number} score - 评分
 * @param {number} decimals - 小数位数
 * @returns {string} 格式化后的评分
 */
export function formatScore(score, decimals = 1) {
  if (score === null || score === undefined || isNaN(score)) {
    return '未评分'
  }
  return score.toFixed(decimals)
}

/**
 * 格式化文件大小
 * @param {number} bytes - 字节数
 * @returns {string} 格式化后的文件大小
 */
export function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const k = 1024
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + units[i]
}

/**
 * 格式化翻页模式显示
 * @param {string} mode - 翻页模式
 * @returns {string} 显示文本
 */
export function formatPageMode(mode) {
  const modeMap = {
    [PAGE_MODE.LEFT_RIGHT]: '左右翻页',
    [PAGE_MODE.UP_DOWN]: '上下翻页'
  }
  return modeMap[mode] || mode
}

/**
 * 格式化背景色显示
 * @param {string} background - 背景色
 * @returns {string} 显示文本
 */
export function formatBackground(background) {
  const bgMap = {
    [BACKGROUND.WHITE]: '白色',
    [BACKGROUND.DARK]: '深色',
    [BACKGROUND.EYE_PROTECTION]: '护眼色'
  }
  return bgMap[background] || background
}

/**
 * 格式化排序类型显示
 * @param {string} sortType - 排序类型
 * @returns {string} 显示文本
 */
export function formatSortType(sortType) {
  const sortMap = {
    [SORT_TYPE.CREATE_TIME]: '添加时间',
    [SORT_TYPE.SCORE]: '评分',
    [SORT_TYPE.READ_TIME]: '最后阅读'
  }
  return sortMap[sortType] || sortType
}

/**
 * 格式化漫画数量
 * @param {number} count - 数量
 * @returns {string} 格式化后的数量
 */
export function formatComicCount(count) {
  if (count === null || count === undefined) return '0部'
  return `${count}部`
}

/**
 * 格式化页码范围
 * @param {number} start - 起始页
 * @param {number} end - 结束页
 * @returns {string} 格式化后的范围
 */
export function formatPageRange(start, end) {
  if (start === end) {
    return `第${start}页`
  }
  return `第${start}-${end}页`
}

/**
 * 截断文本
 * @param {string} text - 原文本
 * @param {number} maxLength - 最大长度
 * @param {string} suffix - 后缀
 * @returns {string} 截断后的文本
 */
export function truncateText(text, maxLength = 50, suffix = '...') {
  if (!text || text.length <= maxLength) {
    return text
  }
  return text.substring(0, maxLength - suffix.length) + suffix
}
