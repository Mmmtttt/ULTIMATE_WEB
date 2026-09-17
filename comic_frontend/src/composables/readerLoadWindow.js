export function clampPage(page, totalPages) {
  const safeTotal = Number.isFinite(totalPages) ? Math.max(0, Math.floor(totalPages)) : 0
  if (safeTotal <= 0) return 1

  const numericPage = Number.isFinite(page) ? page : 1
  return Math.min(safeTotal, Math.max(1, Math.round(numericPage)))
}

export function calculateLoadSequence(centerPage, totalPages, options = {}) {
  const safeTotal = Number.isFinite(totalPages) ? Math.max(0, Math.floor(totalPages)) : 0
  if (safeTotal <= 0) return []

  const startPage = clampPage(centerPage, safeTotal)
  const minPage = Math.max(1, Math.min(safeTotal, Math.floor(options.minPage ?? 1)))
  const maxPage = Math.min(safeTotal, Math.max(minPage, Math.floor(options.maxPage ?? safeTotal)))
  const targetCount = maxPage - minPage + 1
  const sequence = []
  const added = new Set()

  const appendPage = (page) => {
    if (page < minPage || page > maxPage || added.has(page)) return
    sequence.push(page)
    added.add(page)
  }

  appendPage(startPage)

  let forwardOffset = 1
  let backwardOffset = 1
  let forwardSinceBackward = 0
  while (added.size < targetCount) {
    appendPage(startPage + forwardOffset)
    forwardOffset += 1
    forwardSinceBackward += 1

    if (forwardSinceBackward >= 4) {
      appendPage(startPage - backwardOffset)
      backwardOffset += 1
      forwardSinceBackward = 0
    }

    // The window is bounded, so this is only a defensive guard for malformed input.
    if (forwardOffset > safeTotal + 1 && backwardOffset > safeTotal + 1) break
  }

  for (let page = minPage; page <= maxPage; page += 1) appendPage(page)
  return sequence
}

export const READER_LOAD_WINDOW = Object.freeze({
  restoreBefore: 1,
  restoreAfter: 24,
  normalBefore: 20,
  normalAfter: 60
})

export function estimateReaderPageExtent(metric, {
  pageMode = 'up_down',
  viewportWidth = 1280,
  viewportHeight = 720,
  sidePadding = 0,
  doublePageMode = false,
  singlePageBrowsing = false
} = {}) {
  const safeWidth = Math.max(1, Number(viewportWidth) || 1280)
  const safeHeight = Math.max(1, Number(viewportHeight) || 720)
  const safePadding = Math.min(40, Math.max(0, Number(sidePadding) || 0))
  const ratio = Number(metric?.width) > 0 && Number(metric?.height) > 0
    ? Number(metric.height) / Number(metric.width)
    : null

  if (pageMode === 'left_right') {
    if (singlePageBrowsing) return safeWidth
    const fallbackWidth = safeWidth * (doublePageMode ? 0.5 : 1)
    return ratio ? Math.min(fallbackWidth, safeHeight / ratio) : fallbackWidth
  }

  if (singlePageBrowsing) return safeHeight
  const availableWidth = safeWidth * (1 - safePadding / 50)
  return ratio ? Math.min(safeHeight, availableWidth * ratio) : safeHeight * 0.82
}

export function estimateReaderRangeExtent(metrics, startPage, endPage, options = {}) {
  const start = Math.max(1, Math.floor(Number(startPage) || 1))
  const end = Math.max(start - 1, Math.floor(Number(endPage) || 0))
  if (end < start) return 0

  const fallback = estimateReaderPageExtent(null, options)
  let extent = (end - start + 1) * fallback
  for (const [pageKey, metric] of Object.entries(metrics || {})) {
    const page = Number(pageKey)
    if (!Number.isInteger(page) || page < start || page > end) continue
    extent += estimateReaderPageExtent(metric, options) - fallback
  }
  return Math.max(0, Math.round(extent))
}
