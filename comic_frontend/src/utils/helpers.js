export function toggleSelection(selectedIds, id) {
  const index = selectedIds.value.indexOf(id)
  if (index > -1) {
    selectedIds.value.splice(index, 1)
  } else {
    selectedIds.value.push(id)
  }
}

export function getCoverUrl(coverPath) {
  if (!coverPath) return ''
  if (coverPath.startsWith('http')) return coverPath
  if (coverPath.startsWith('/static/')) return coverPath
  if (coverPath.startsWith('/')) return coverPath
  return `/${coverPath}`
}

export function extractAuthors(items) {
  const authors = new Set()
  items.forEach(item => {
    if (item.author) authors.add(item.author)
    if (item.creator) authors.add(item.creator)
  })
  return Array.from(authors).sort()
}

export function getFilterStorageKey(baseKey, isVideoMode) {
  return `${baseKey}_${isVideoMode ? 'video' : 'comic'}`
}

export function saveToSession(key, data) {
  try {
    sessionStorage.setItem(key, JSON.stringify(data))
  } catch (e) {
    console.error('保存到 sessionStorage 失败:', e)
  }
}

export function loadFromSession(key) {
  try {
    const raw = sessionStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch (e) {
    console.error('从 sessionStorage 加载失败:', e)
    return null
  }
}

export function hasActiveFilters(filters) {
  return Object.values(filters).some(v => 
    Array.isArray(v) ? v.length > 0 : Boolean(v)
  )
}

export function clearFilters(filters) {
  Object.keys(filters).forEach(key => {
    if (Array.isArray(filters[key])) {
      filters[key] = []
    } else {
      filters[key] = null
    }
  })
}

export function buildQueryParams(params) {
  const queryParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      if (Array.isArray(value)) {
        value.forEach(v => queryParams.append(key, v))
      } else {
        queryParams.append(key, value)
      }
    }
  })
  return queryParams.toString()
}

export const FAVORITES_COMIC_LIST_ID = 'list_favorites_comic'
export const FAVORITES_VIDEO_LIST_ID = 'list_favorites_video'

export function isFavorited(item, isVideo = false) {
  const listId = isVideo ? FAVORITES_VIDEO_LIST_ID : FAVORITES_COMIC_LIST_ID
  return item?.list_ids?.includes(listId) || false
}
