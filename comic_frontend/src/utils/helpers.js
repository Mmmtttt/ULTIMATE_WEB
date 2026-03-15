export function toggleSelection(selectedIds, id) {
  const index = selectedIds.value.indexOf(id)
  if (index > -1) {
    selectedIds.value.splice(index, 1)
  } else {
    selectedIds.value.push(id)
  }
}

export function isAllSelected(selectedIds = [], items = [], getId = (item) => item.id) {
  if (!Array.isArray(items) || items.length === 0) {
    return false
  }
  return items.every(item => selectedIds.includes(getId(item)))
}

export function toggleSelectAll(selectedIdsRef, items = [], getId = (item) => item.id) {
  if (!selectedIdsRef || !Array.isArray(items) || items.length === 0) {
    return
  }
  if (isAllSelected(selectedIdsRef.value, items, getId)) {
    selectedIdsRef.value = []
  } else {
    selectedIdsRef.value = items.map(item => getId(item)).filter(Boolean)
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
    extractItemAuthors(item).forEach(name => authors.add(name))
  })
  return Array.from(authors).sort()
}

export function extractItemAuthors(item = {}) {
  const target = item && typeof item === 'object' ? item : {}
  const values = []

  const pushValue = (value) => {
    if (typeof value === 'string' && value.trim()) {
      values.push(value.trim())
    }
  }

  pushValue(target.author)
  pushValue(target.creator)
  pushValue(target.actor)

  if (Array.isArray(target.actors)) {
    target.actors.forEach(pushValue)
  }

  if (Array.isArray(target.authors)) {
    target.authors.forEach(pushValue)
  }

  return Array.from(new Set(values))
}

export function normalizeMinScore(minScore) {
  const score = Number(minScore)
  if (!Number.isFinite(score) || score <= 0) {
    return 0
  }
  return score
}

export function filterItemsByMinScore(items = [], minScore = 0) {
  const safeItems = Array.isArray(items) ? items : []
  const threshold = normalizeMinScore(minScore)
  if (threshold <= 0) {
    return [...safeItems]
  }
  return safeItems.filter(item => {
    const score = Number(item?.score ?? 0)
    return Number.isFinite(score) && score >= threshold
  })
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

/**
 * Apply list membership changes for a single item.
 * Returns how many list operations succeeded.
 */
export async function applyListMembershipChanges({
  listStore,
  contentType = 'comic',
  selectedListIds = [],
  currentListIds = [],
  itemId,
  source = 'local'
}) {
  const toAdd = selectedListIds.filter(id => !currentListIds.includes(id))
  const toRemove = currentListIds.filter(id => !selectedListIds.includes(id))

  const bindAction = contentType === 'video'
    ? listStore.bindVideos.bind(listStore)
    : listStore.bindComics.bind(listStore)
  const removeAction = contentType === 'video'
    ? listStore.removeVideos.bind(listStore)
    : listStore.removeComics.bind(listStore)

  let addCount = 0
  let removeCount = 0

  for (const listId of toAdd) {
    const result = await bindAction(listId, [itemId], source)
    if (result) {
      addCount++
    }
  }

  for (const listId of toRemove) {
    const result = await removeAction(listId, [itemId], source)
    if (result) {
      removeCount++
    }
  }

  return {
    addCount,
    removeCount,
    unchanged: toAdd.length === 0 && toRemove.length === 0
  }
}

export function buildListChangeMessage(addCount, removeCount) {
  let message = ''
  if (addCount > 0) {
    message += `加入${addCount}个清单 `
  }
  if (removeCount > 0) {
    message += `移出${removeCount}个清单`
  }
  return message.trim() || '清单无变化'
}
