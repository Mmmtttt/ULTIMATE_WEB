export function clampPage(page, totalPages) {
  const safeTotal = Number.isFinite(totalPages) ? Math.max(0, Math.floor(totalPages)) : 0
  if (safeTotal <= 0) return 1

  const numericPage = Number.isFinite(page) ? page : 1
  const roundedPage = Math.round(numericPage)
  return Math.min(safeTotal, Math.max(1, roundedPage))
}

export function calculateLoadSequence(centerPage, totalPages) {
  const safeTotal = Number.isFinite(totalPages) ? Math.max(0, Math.floor(totalPages)) : 0
  if (safeTotal <= 0) return []

  const startPage = clampPage(centerPage, safeTotal)
  const sequence = []
  const added = new Set()

  const appendPage = (page) => {
    if (page < 1 || page > safeTotal || added.has(page)) return
    sequence.push(page)
    added.add(page)
  }

  appendPage(startPage)

  let forwardOffset = 1
  let backwardOffset = 1
  let forwardSinceBackward = 0
  let safety = 0
  const maxSafety = safeTotal * 4

  while (added.size < safeTotal && safety < maxSafety) {
    safety += 1
    appendPage(startPage + forwardOffset)
    if (added.has(startPage + forwardOffset)) {
      forwardSinceBackward += 1
    }
    forwardOffset += 1

    if (forwardSinceBackward >= 4) {
      appendPage(startPage - backwardOffset)
      backwardOffset += 1
      forwardSinceBackward = 0
    }
  }

  for (let page = 1; page <= safeTotal; page += 1) {
    appendPage(page)
  }

  return sequence
}

export function isLikelyLanHost(hostname) {
  const host =
    hostname ||
    (typeof window !== 'undefined' && window.location ? window.location.hostname || '' : '')

  if (!host) return false

  return (
    host === 'localhost' ||
    host === '127.0.0.1' ||
    host === '::1' ||
    /^10\./.test(host) ||
    /^192\.168\./.test(host) ||
    /^172\.(1[6-9]|2\d|3[0-1])\./.test(host)
  )
}

export function getAdaptiveMaxConcurrent({
  isMobileViewport = false,
  lanHost = false,
  hardwareConcurrency
} = {}) {
  const cores =
    Number.isFinite(hardwareConcurrency) && hardwareConcurrency > 0
      ? hardwareConcurrency
      : typeof navigator !== 'undefined' && navigator.hardwareConcurrency
        ? navigator.hardwareConcurrency
        : 8

  const lanBoost = lanHost ? 4 : 0

  if (isMobileViewport) {
    return Math.min(10, Math.max(3, Math.floor(cores / 2) + Math.floor(lanBoost / 2)))
  }

  return Math.min(28, Math.max(8, cores + 4 + lanBoost))
}

export function nextAnimationFrame() {
  if (typeof window === 'undefined' || typeof window.requestAnimationFrame !== 'function') {
    return Promise.resolve()
  }

  return new Promise((resolve) => {
    window.requestAnimationFrame(() => resolve())
  })
}

export function updateViewportHeightCssVar(varName = '--reader-vh') {
  if (typeof document === 'undefined' || typeof window === 'undefined') return
  const height = window.innerHeight
  document.documentElement.style.setProperty(varName, `${height}px`)
}
