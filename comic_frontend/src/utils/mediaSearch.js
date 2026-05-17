function normalizeSearchText(value) {
  return String(value || '').trim().toLowerCase()
}

function appendCandidate(parts, value) {
  if (Array.isArray(value)) {
    value.forEach((item) => appendCandidate(parts, item))
    return
  }
  if (value && typeof value === 'object') {
    appendCandidate(parts, value.name)
    appendCandidate(parts, value.title)
    appendCandidate(parts, value.code)
    return
  }
  const normalized = normalizeSearchText(value)
  if (normalized) {
    parts.push(normalized)
  }
}

function buildSearchHaystack(item) {
  const parts = []
  if (!item || typeof item !== 'object') {
    return ''
  }
  appendCandidate(parts, item.id)
  appendCandidate(parts, item.code)
  appendCandidate(parts, item.title)
  appendCandidate(parts, item.title_jp)
  appendCandidate(parts, item.author)
  appendCandidate(parts, item.creator)
  appendCandidate(parts, item.desc)
  appendCandidate(parts, item.actors)
  appendCandidate(parts, item.tags)
  appendCandidate(parts, item.tag_ids)
  return parts.join('\n')
}

export function filterMediaItemsByKeyword(items, keyword) {
  const normalizedKeyword = normalizeSearchText(keyword)
  if (!normalizedKeyword) {
    return Array.isArray(items) ? items : []
  }
  const tokens = normalizedKeyword.split(/\s+/).filter(Boolean)
  if (tokens.length === 0) {
    return Array.isArray(items) ? items : []
  }
  return (Array.isArray(items) ? items : []).filter((item) => {
    const haystack = buildSearchHaystack(item)
    return tokens.every((token) => haystack.includes(token))
  })
}
