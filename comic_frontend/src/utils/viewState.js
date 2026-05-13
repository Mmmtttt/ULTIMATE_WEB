import { getRawItem, setRawItem, StorageArea } from '@/runtime/storage'

export const SORT_ORDER = {
  ASC: 'asc',
  DESC: 'desc'
}

export const DEFAULT_SORT_ORDER = SORT_ORDER.DESC
export const DEFAULT_SORT_FIELD = ''

const UI_STATE_CLIENT_ID_KEY = 'ui_state_client_id'

function generateClientId() {
  const prefix = 'ui'
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID()}`
  }
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

export function getOrCreateUiStateClientId() {
  const cached = String(getRawItem(UI_STATE_CLIENT_ID_KEY, StorageArea.LOCAL) || '').trim()
  if (cached) {
    return cached
  }
  const nextValue = generateClientId()
  setRawItem(UI_STATE_CLIENT_ID_KEY, nextValue, StorageArea.LOCAL)
  return nextValue
}

export function buildUiStateScope(baseScope, isVideoMode = false) {
  return `${String(baseScope || '').trim()}_${isVideoMode ? 'video' : 'comic'}`
}

export function normalizeSortOrder(value) {
  return String(value || '').trim().toLowerCase() === SORT_ORDER.ASC ? SORT_ORDER.ASC : SORT_ORDER.DESC
}

export function isDefaultSortState(sortField, sortOrder = DEFAULT_SORT_ORDER) {
  return !String(sortField || '').trim() && normalizeSortOrder(sortOrder) === DEFAULT_SORT_ORDER
}

export function encodeSortSelection(sortField, sortOrder = DEFAULT_SORT_ORDER) {
  const field = String(sortField || '').trim()
  if (!field) {
    return 'default'
  }
  return `${field}:${normalizeSortOrder(sortOrder)}`
}

export function decodeSortSelection(rawValue) {
  const value = String(rawValue || '').trim()
  if (!value || value === 'default') {
    return {
      sortField: DEFAULT_SORT_FIELD,
      sortOrder: DEFAULT_SORT_ORDER,
    }
  }
  const [sortField, sortOrder] = value.split(':', 2)
  return {
    sortField: String(sortField || '').trim(),
    sortOrder: normalizeSortOrder(sortOrder),
  }
}

export function buildSortOptions(isVideoMode = false) {
  const options = [
    { text: '默认顺序', value: encodeSortSelection('', DEFAULT_SORT_ORDER) },
    { text: '最近导入', value: encodeSortSelection('create_time', SORT_ORDER.DESC) },
    { text: '最早导入', value: encodeSortSelection('create_time', SORT_ORDER.ASC) },
    { text: '评分最高', value: encodeSortSelection('score', SORT_ORDER.DESC) },
    { text: '评分最低', value: encodeSortSelection('score', SORT_ORDER.ASC) },
  ]
  if (isVideoMode) {
    options.push(
      { text: '最新发布', value: encodeSortSelection('date', SORT_ORDER.DESC) },
      { text: '最早发布', value: encodeSortSelection('date', SORT_ORDER.ASC) },
    )
  }
  return options
}

function compareValues(left, right) {
  if (left === right) {
    return 0
  }
  if (left === '' || left === null || left === undefined) {
    return -1
  }
  if (right === '' || right === null || right === undefined) {
    return 1
  }
  if (left > right) {
    return 1
  }
  if (left < right) {
    return -1
  }
  return 0
}

export function sortContentItems(items = [], sortField = '', sortOrder = DEFAULT_SORT_ORDER) {
  const normalizedField = String(sortField || '').trim()
  if (!normalizedField) {
    return Array.isArray(items) ? [...items] : []
  }

  const safeItems = Array.isArray(items) ? [...items] : []
  const factor = normalizeSortOrder(sortOrder) === SORT_ORDER.ASC ? 1 : -1

  return safeItems.sort((left, right) => {
    if (normalizedField === 'score') {
      return compareValues(Number(left?.score || 0), Number(right?.score || 0)) * factor
    }
    if (normalizedField === 'read_status') {
      const leftRead = Number(left?.current_page || 0) >= Number(left?.total_page || 0) ? 1 : 0
      const rightRead = Number(right?.current_page || 0) >= Number(right?.total_page || 0) ? 1 : 0
      const readCompare = compareValues(leftRead, rightRead)
      if (readCompare !== 0) {
        return readCompare * factor
      }
      return compareValues(Number(left?.score || 0), Number(right?.score || 0)) * -1
    }

    const leftValue = String(left?.[normalizedField] || '').trim()
    const rightValue = String(right?.[normalizedField] || '').trim()
    return compareValues(leftValue, rightValue) * factor
  })
}
