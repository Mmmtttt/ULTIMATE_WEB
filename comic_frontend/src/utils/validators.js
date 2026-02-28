/**
 * 校验工具
 * 提供各种数据校验函数
 */

import { SCORE_RANGE, PAGE_MODE, BACKGROUND, IMAGE_FORMATS } from './constants'

/**
 * 校验页码是否有效
 * @param {number} page - 页码
 * @param {number} total - 总页数
 * @returns {boolean} 是否有效
 */
export function isValidPage(page, total) {
  const pageNum = Number(page)
  return (
    !isNaN(pageNum) &&
    pageNum >= 1 &&
    pageNum <= total &&
    Number.isInteger(pageNum)
  )
}

/**
 * 校验页码范围
 * @param {number} page - 页码
 * @param {number} total - 总页数
 * @returns {{valid: boolean, message: string}} 校验结果
 */
export function validatePage(page, total) {
  const pageNum = Number(page)
  
  if (isNaN(pageNum)) {
    return { valid: false, message: '页码必须是数字' }
  }
  
  if (!Number.isInteger(pageNum)) {
    return { valid: false, message: '页码必须是整数' }
  }
  
  if (pageNum < 1) {
    return { valid: false, message: '页码不能小于1' }
  }
  
  if (pageNum > total) {
    return { valid: false, message: `页码不能大于${total}` }
  }
  
  return { valid: true, message: '' }
}

/**
 * 校验评分
 * @param {number} score - 评分
 * @returns {{valid: boolean, message: string}} 校验结果
 */
export function validateScore(score) {
  const scoreValue = Number(score)
  
  if (isNaN(scoreValue)) {
    return { valid: false, message: '评分必须是数字' }
  }
  
  if (scoreValue < SCORE_RANGE.MIN) {
    return { valid: false, message: `评分不能小于${SCORE_RANGE.MIN}` }
  }
  
  if (scoreValue > SCORE_RANGE.MAX) {
    return { valid: false, message: `评分不能大于${SCORE_RANGE.MAX}` }
  }
  
  return { valid: true, message: '' }
}

/**
 * 校验翻页模式
 * @param {string} mode - 翻页模式
 * @returns {boolean} 是否有效
 */
export function isValidPageMode(mode) {
  return Object.values(PAGE_MODE).includes(mode)
}

/**
 * 校验背景色
 * @param {string} background - 背景色
 * @returns {boolean} 是否有效
 */
export function isValidBackground(background) {
  return Object.values(BACKGROUND).includes(background)
}

/**
 * 校验标签名称
 * @param {string} name - 标签名称
 * @returns {{valid: boolean, message: string}} 校验结果
 */
export function validateTagName(name) {
  if (!name || name.trim() === '') {
    return { valid: false, message: '标签名称不能为空' }
  }
  
  if (name.trim().length > 20) {
    return { valid: false, message: '标签名称不能超过20个字符' }
  }
  
  return { valid: true, message: '' }
}

/**
 * 校验清单名称
 * @param {string} name - 清单名称
 * @returns {{valid: boolean, message: string}} 校验结果
 */
export function validateListName(name) {
  if (!name || name.trim() === '') {
    return { valid: false, message: '清单名称不能为空' }
  }
  
  if (name.trim().length > 30) {
    return { valid: false, message: '清单名称不能超过30个字符' }
  }
  
  return { valid: true, message: '' }
}

/**
 * 校验搜索关键词
 * @param {string} keyword - 关键词
 * @returns {{valid: boolean, message: string}} 校验结果
 */
export function validateSearchKeyword(keyword) {
  if (!keyword || keyword.trim() === '') {
    return { valid: false, message: '搜索关键词不能为空' }
  }
  
  if (keyword.trim().length > 50) {
    return { valid: false, message: '搜索关键词不能超过50个字符' }
  }
  
  return { valid: true, message: '' }
}

/**
 * 校验漫画ID
 * @param {string} comicId - 漫画ID
 * @returns {boolean} 是否有效
 */
export function isValidComicId(comicId) {
  return comicId && typeof comicId === 'string' && comicId.startsWith('comic_')
}

/**
 * 校验图片文件
 * @param {string} filename - 文件名
 * @returns {boolean} 是否是图片文件
 */
export function isImageFile(filename) {
  if (!filename || typeof filename !== 'string') {
    return false
  }
  
  const lowerFilename = filename.toLowerCase()
  return IMAGE_FORMATS.some(format => lowerFilename.endsWith(format))
}

/**
 * 校验URL
 * @param {string} url - URL
 * @returns {boolean} 是否有效
 */
export function isValidUrl(url) {
  if (!url || typeof url !== 'string') {
    return false
  }
  
  try {
    new URL(url)
    return true
  } catch {
    return false
  }
}

/**
 * 校验图床链接
 * @param {string} url - 图床链接
 * @returns {{valid: boolean, message: string}} 校验结果
 */
export function validateImageHostUrl(url) {
  if (!url || url.trim() === '') {
    return { valid: false, message: '链接不能为空' }
  }
  
  if (!isValidUrl(url)) {
    return { valid: false, message: '链接格式不正确' }
  }
  
  if (!isImageFile(url)) {
    return { valid: false, message: '链接必须是图片文件' }
  }
  
  return { valid: true, message: '' }
}

/**
 * 校验配置对象
 * @param {object} config - 配置对象
 * @returns {{valid: boolean, message: string, errors: object}} 校验结果
 */
export function validateConfig(config) {
  const errors = {}
  
  if (config.default_page_mode !== undefined) {
    if (!isValidPageMode(config.default_page_mode)) {
      errors.default_page_mode = '无效的翻页模式'
    }
  }
  
  if (config.default_background !== undefined) {
    if (!isValidBackground(config.default_background)) {
      errors.default_background = '无效的背景色'
    }
  }
  
  const valid = Object.keys(errors).length === 0
  
  return {
    valid,
    message: valid ? '' : '配置校验失败',
    errors
  }
}

/**
 * 校验评分范围
 * @param {number} minScore - 最低分
 * @param {number} maxScore - 最高分
 * @returns {{valid: boolean, message: string}} 校验结果
 */
export function validateScoreRange(minScore, maxScore) {
  const minResult = validateScore(minScore)
  if (!minResult.valid) {
    return minResult
  }
  
  const maxResult = validateScore(maxScore)
  if (!maxResult.valid) {
    return maxResult
  }
  
  if (minScore > maxScore) {
    return { valid: false, message: '最低分不能大于最高分' }
  }
  
  return { valid: true, message: '' }
}
