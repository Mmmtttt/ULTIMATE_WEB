import { toBackendUrl } from './url'
import { StorageArea, getRawItem, setRawItem } from '@/runtime/storage'

export function toggleSelection(selectedIds, id) {
  const index = selectedIds.value.indexOf(id)
  if (index > -1) {
    selectedIds.value.splice(index, 1)
  } else {
    selectedIds.value.push(id)
  }
}

function collectScopeIds(items = [], getId = (item) => item.id) {
  if (!Array.isArray(items) || items.length === 0) {
    return []
  }
  return items
    .map((item) => getId(item))
    .filter((id) => Boolean(id))
}

export function isAllSelected(selectedIds = [], items = [], getId = (item) => item.id) {
  const scopeIds = collectScopeIds(items, getId)
  if (scopeIds.length === 0) {
    return false
  }
  const selectedSet = new Set(Array.isArray(selectedIds) ? selectedIds : [])
  return scopeIds.every((id) => selectedSet.has(id))
}

export function toggleSelectAll(selectedIdsRef, items = [], getId = (item) => item.id) {
  if (!selectedIdsRef) {
    return
  }

  const scopeIds = collectScopeIds(items, getId)
  if (scopeIds.length === 0) {
    return
  }

  const currentSelected = Array.isArray(selectedIdsRef.value) ? selectedIdsRef.value : []
  const scopeIdSet = new Set(scopeIds)

  if (isAllSelected(currentSelected, items, getId)) {
    selectedIdsRef.value = currentSelected.filter((id) => !scopeIdSet.has(id))
    return
  }

  selectedIdsRef.value = [...new Set([...currentSelected, ...scopeIds])]
}

export function keepSelectionWithinItems(selectedIds = [], items = [], getId = (item) => item.id) {
  const scopeIdSet = new Set(collectScopeIds(items, getId))
  if (scopeIdSet.size === 0) {
    return []
  }
  return (Array.isArray(selectedIds) ? selectedIds : []).filter((id) => scopeIdSet.has(id))
}

function normalizeLocalIdentifier(input) {
  return String(input || '').trim().toUpperCase()
}

export function isLocalComicCandidateId(comicId) {
  const normalized = normalizeLocalIdentifier(comicId)
  if (!normalized) {
    return false
  }
  if (normalized.startsWith('LOCAL')) {
    return true
  }
  const parts = normalized.split(/[^A-Z0-9]+/).filter(Boolean)
  return parts.some((part) => part.startsWith('LOCAL'))
}

export function isLocalVideoCandidateId(videoId) {
  const normalized = normalizeLocalIdentifier(videoId)
  return normalized.startsWith('LOCAL')
}

export function getCoverUrl(coverInput) {
  let coverPath = ''
  let localCoverAssetVersion = ''
  let usingLocalCover = false
  if (typeof coverInput === 'string') {
    coverPath = coverInput
  } else if (coverInput && typeof coverInput === 'object') {
    const versionedCoverUrl = String(coverInput.cover_url || '').trim()
    const localCoverPath = String(coverInput.cover_path_local || '').trim()
    const fallbackCoverPath = String(coverInput.cover_path || '').trim()
    coverPath = versionedCoverUrl || localCoverPath || fallbackCoverPath
    usingLocalCover = Boolean(localCoverPath) && coverPath === localCoverPath
    localCoverAssetVersion = String(coverInput.local_cover_asset_version || '').trim()
  } else if (coverInput !== null && coverInput !== undefined) {
    coverPath = String(coverInput)
  }

  const normalizedCoverPath = String(coverPath || '').trim()
  if (!normalizedCoverPath) return ''
  const resolvedUrl = toBackendUrl(normalizedCoverPath)
  if (!usingLocalCover || !localCoverAssetVersion) {
    return resolvedUrl
  }
  const separator = resolvedUrl.includes('?') ? '&' : '?'
  return `${resolvedUrl}${separator}v=${encodeURIComponent(localCoverAssetVersion)}`
}

export function getDisplayConfig(item) {
  if (!item || typeof item !== 'object' || !item.display || typeof item.display !== 'object') {
    return {}
  }
  return item.display
}

export function normalizeAspectRatio(value) {
  const raw = String(value || '').trim()
  if (!raw) {
    return ''
  }

  const compact = raw.replace(/\s+/g, '')
  if (!/^\d+(\.\d+)?\/\d+(\.\d+)?$/.test(compact)) {
    return raw
  }

  const [width, height] = compact.split('/')
  return `${width} / ${height}`
}

export function resolveDisplayCoverAspectRatio(item) {
  return normalizeAspectRatio(getDisplayConfig(item).cover?.aspect_ratio)
}

export function resolveDisplayMobileCoverAspectRatio(item) {
  return normalizeAspectRatio(getDisplayConfig(item).cover?.mobile_aspect_ratio)
}

export function resolveDisplayCoverFit(item) {
  const fit = String(getDisplayConfig(item).cover?.fit || '').trim().toLowerCase()
  return fit === 'contain' || fit === 'cover' ? fit : ''
}

export function resolvePlatformBadgeLabel(item) {
  const badgeLabel = String(getDisplayConfig(item).badge?.label || '').trim()
  if (badgeLabel) {
    return badgeLabel
  }
  return String(item?.platform || item?.plugin_name || '').trim()
}

export function shouldShowPlatformBadge(item) {
  const badgeConfig = getDisplayConfig(item).badge
  if (typeof badgeConfig?.show_platform_label === 'boolean') {
    return badgeConfig.show_platform_label && Boolean(resolvePlatformBadgeLabel(item))
  }
  return Boolean(resolvePlatformBadgeLabel(item))
}

export function resolveImportPlatform(item) {
  return String(
    item?.platform ||
    item?.display?.badge?.label ||
    item?.plugin_name ||
    ''
  ).trim()
}

function isVideoDisplayItem(item) {
  if (!item || typeof item !== 'object') {
    return false
  }

  const contentType = String(item.content_type || '').trim().toLowerCase()
  if (contentType === 'video') {
    return true
  }

  const pluginId = String(item.plugin_id || '').trim().toLowerCase()
  if (pluginId.startsWith('video.')) {
    return true
  }

  if (
    Array.isArray(item.actors) && item.actors.length > 0 ||
    String(item.video_id || '').trim() ||
    String(item.preview_video || '').trim() ||
    String(item.preview_video_local || '').trim() ||
    String(item.local_video_path || '').trim()
  ) {
    return true
  }

  return false
}

export function buildDisplayCoverStyle(item, fallbackAspectRatio = '', fallbackMobileAspectRatio = '') {
  const defaultVideoAspectRatio = isVideoDisplayItem(item) ? '16 / 9' : ''
  const aspectRatio =
    resolveDisplayCoverAspectRatio(item) ||
    normalizeAspectRatio(fallbackAspectRatio) ||
    defaultVideoAspectRatio
  const mobileAspectRatio =
    resolveDisplayMobileCoverAspectRatio(item) ||
    normalizeAspectRatio(fallbackMobileAspectRatio) ||
    defaultVideoAspectRatio ||
    aspectRatio

  const style = {}
  if (aspectRatio) {
    style['--media-cover-aspect-ratio'] = aspectRatio
  }
  if (mobileAspectRatio) {
    style['--media-cover-aspect-ratio-mobile'] = mobileAspectRatio
  }
  return style
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

export function normalizeReadPage(currentPage) {
  const page = Number(currentPage)
  if (!Number.isFinite(page)) {
    return 1
  }
  return page
}

export function isUnreadByProgress(currentPage) {
  return normalizeReadPage(currentPage) === 1
}

export function isReadByProgress(currentPage) {
  return !isUnreadByProgress(currentPage)
}

export function filterItemsByUnread(items = [], unreadOnly = false) {
  const safeItems = Array.isArray(items) ? items : []
  if (!unreadOnly) {
    return [...safeItems]
  }
  return safeItems.filter(item => isUnreadByProgress(item?.current_page))
}

export function getFilterStorageKey(baseKey, isVideoMode) {
  return `${baseKey}_${isVideoMode ? 'video' : 'comic'}`
}

export function saveToSession(key, data) {
  try {
    setRawItem(key, JSON.stringify(data), StorageArea.SESSION)
  } catch (e) {
    console.error('Failed to save data to session storage:', e)
  }
}

export function loadFromSession(key) {
  try {
    const raw = getRawItem(key, StorageArea.SESSION)
    return raw ? JSON.parse(raw) : null
  } catch (e) {
    console.error('Failed to load data from session storage:', e)
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
    message += `Added to ${addCount} list(s)`
  }
  if (removeCount > 0) {
    message += `Removed from ${removeCount} list(s)`
  }
  return message.trim() || 'No list changes'
}



