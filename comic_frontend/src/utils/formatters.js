/**
 * Data format helpers.
 */

import { PAGE_MODE, BACKGROUND, SORT_TYPE } from './constants'

export function formatPageDisplay(current, total) {
  return `${current} / ${total}`
}

export function formatProgress(current, total) {
  if (!total || total <= 0) return '0%'
  const percentage = Math.round((current / total) * 100)
  return `${percentage}%`
}

export function formatDateTime(dateStr, format = 'YYYY-MM-DD HH:mm') {
  if (!dateStr) return '-'

  const date = new Date(dateStr)
  if (Number.isNaN(date.getTime())) return '-'

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

export function formatRelativeTime(dateStr) {
  if (!dateStr) return '-'

  const date = new Date(dateStr)
  if (Number.isNaN(date.getTime())) return '-'

  const now = new Date()
  const diff = now.getTime() - date.getTime()

  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour
  const week = 7 * day
  const month = 30 * day

  if (diff < minute) return '刚刚'
  if (diff < hour) return `${Math.floor(diff / minute)}分钟前`
  if (diff < day) return `${Math.floor(diff / hour)}小时前`
  if (diff < week) return `${Math.floor(diff / day)}天前`
  if (diff < month) return `${Math.floor(diff / week)}周前`
  return formatDateTime(dateStr, 'YYYY-MM-DD')
}

export function formatScore(score, decimals = 1) {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return '未评分'
  }
  return Number(score).toFixed(decimals)
}

export function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B'

  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const k = 1024
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${units[i]}`
}

export function formatPageMode(mode) {
  const modeMap = {
    [PAGE_MODE.LEFT_RIGHT]: '左右翻页',
    [PAGE_MODE.UP_DOWN]: '上下翻页'
  }
  return modeMap[mode] || mode
}

export function formatBackground(background) {
  const bgMap = {
    [BACKGROUND.WHITE]: '白色',
    [BACKGROUND.DARK]: '深色',
    [BACKGROUND.SEPIA]: '护眼色',
    [BACKGROUND.EYE_PROTECTION]: '护眼色'
  }
  return bgMap[background] || background
}

export function formatSortType(sortType) {
  const sortMap = {
    [SORT_TYPE.CREATE_TIME]: '最近导入',
    [SORT_TYPE.SCORE]: '评分',
    [SORT_TYPE.READ_TIME]: '最后阅读'
  }
  return sortMap[sortType] || sortType
}

export function formatComicCount(count) {
  if (count === null || count === undefined) return '0部'
  return `${count}部`
}

export function formatPageRange(start, end) {
  if (start === end) {
    return `第${start}页`
  }
  return `第${start}-${end}页`
}

export function truncateText(text, maxLength = 50, suffix = '...') {
  if (!text || text.length <= maxLength) {
    return text
  }
  return text.substring(0, maxLength - suffix.length) + suffix
}
