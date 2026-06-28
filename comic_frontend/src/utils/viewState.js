import { getRawItem, removeRawItem, setRawItem, StorageArea } from '@/runtime/storage'

export const SORT_ORDER = {
  ASC: 'asc',
  DESC: 'desc'
}

export const DEFAULT_SORT_ORDER = SORT_ORDER.DESC
export const DEFAULT_SORT_FIELD = ''

const UI_STATE_CLIENT_ID_KEY = 'ui_state_client_id'
const BROWSE_STATE_PREFIX = 'browse_state'

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

export function buildBrowseStateStorageKey(scope) {
  return `${BROWSE_STATE_PREFIX}:${String(scope || '').trim()}`
}

export function loadBrowseState(scope, fallback = null, area = StorageArea.SESSION) {
  const normalizedScope = String(scope || '').trim()
  if (!normalizedScope) {
    return fallback
  }

  const raw = getRawItem(buildBrowseStateStorageKey(normalizedScope), area)
  if (!raw) {
    return fallback
  }

  try {
    return JSON.parse(raw)
  } catch {
    return fallback
  }
}

export function saveBrowseState(scope, state, area = StorageArea.SESSION) {
  const normalizedScope = String(scope || '').trim()
  if (!normalizedScope || !state || typeof state !== 'object') {
    return
  }

  try {
    setRawItem(buildBrowseStateStorageKey(normalizedScope), JSON.stringify(state), area)
  } catch (error) {
    console.error('saveBrowseState error:', error)
  }
}

export function clearBrowseState(scope, area = StorageArea.SESSION) {
  const normalizedScope = String(scope || '').trim()
  if (!normalizedScope) {
    return
  }

  try {
    removeRawItem(buildBrowseStateStorageKey(normalizedScope), area)
  } catch (error) {
    console.error('clearBrowseState error:', error)
  }
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
    { text: '名称 A-Z', value: encodeSortSelection('name', SORT_ORDER.ASC) },
    { text: '名称 Z-A', value: encodeSortSelection('name', SORT_ORDER.DESC) },
    { text: '评分最高', value: encodeSortSelection('score', SORT_ORDER.DESC) },
    { text: '评分最低', value: encodeSortSelection('score', SORT_ORDER.ASC) },
    { text: '随机排序', value: encodeSortSelection('random', DEFAULT_SORT_ORDER) },
    { text: '自定义顺序', value: encodeSortSelection('custom', SORT_ORDER.ASC) },
  ]
  if (isVideoMode) {
    options.push(
      { text: '最新发布', value: encodeSortSelection('date', SORT_ORDER.DESC) },
      { text: '最早发布', value: encodeSortSelection('date', SORT_ORDER.ASC) },
    )
  } else {
    options.push(
      { text: '页数最多', value: encodeSortSelection('page_count', SORT_ORDER.DESC) },
      { text: '页数最少', value: encodeSortSelection('page_count', SORT_ORDER.ASC) },
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

function compareText(left, right) {
  return String(left || '').localeCompare(String(right || ''), 'zh-Hans-CN', {
    numeric: true,
    sensitivity: 'base',
  })
}

function compareCustomOrder(left, right) {
  const normalizeOrder = (value) => {
    if (value === '' || value === null || value === undefined) {
      return null
    }
    const numericValue = Number(value)
    return Number.isInteger(numericValue) && numericValue >= 0 ? numericValue : null
  }
  const leftOrder = normalizeOrder(left?.custom_order)
  const rightOrder = normalizeOrder(right?.custom_order)

  if (leftOrder !== null && rightOrder !== null) {
    return leftOrder - rightOrder
  }
  if (leftOrder !== null) {
    return -1
  }
  if (rightOrder !== null) {
    return 1
  }

  const createTimeCompare = compareText(String(right?.create_time || ''), String(left?.create_time || ''))
  if (createTimeCompare !== 0) {
    return createTimeCompare
  }
  return compareText(left?.title || left?.name || left?.id, right?.title || right?.name || right?.id)
}

export function sortContentItems(items = [], sortField = '', sortOrder = DEFAULT_SORT_ORDER) {
  const normalizedField = String(sortField || '').trim()
  if (!normalizedField) {
    return Array.isArray(items) ? [...items] : []
  }

  const safeItems = Array.isArray(items) ? [...items] : []
  const factor = normalizeSortOrder(sortOrder) === SORT_ORDER.ASC ? 1 : -1

  if (normalizedField === 'random') {
    return [...safeItems].sort(() => Math.random() - 0.5)
  }

  if (normalizedField === 'custom') {
    return [...safeItems].sort(compareCustomOrder)
  }

  return safeItems.sort((left, right) => {
    if (normalizedField === 'score') {
      return compareValues(Number(left?.score || 0), Number(right?.score || 0)) * factor
    }
    if (normalizedField === 'page_count') {
      return compareValues(Number(left?.total_page || left?.total_units || 0), Number(right?.total_page || right?.total_units || 0)) * factor
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

    if (normalizedField === 'name') {
      return compareText(left?.title || left?.name || left?.id, right?.title || right?.name || right?.id) * factor
    }

    const leftValue = String(left?.[normalizedField] || '').trim()
    const rightValue = String(right?.[normalizedField] || '').trim()
    return compareText(leftValue, rightValue) * factor
  })
}
