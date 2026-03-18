function hasWindow() {
  return typeof window !== 'undefined'
}

function hasDocument() {
  return typeof document !== 'undefined'
}

function hasNavigator() {
  return typeof navigator !== 'undefined'
}

export function getWindow() {
  return hasWindow() ? window : null
}

export function getDocument() {
  return hasDocument() ? document : null
}

export function getNavigator() {
  return hasNavigator() ? navigator : null
}

export function getLocation() {
  const win = getWindow()
  return win?.location ?? null
}

export function getViewportWidth(fallback = 1280) {
  const win = getWindow()
  const width = win?.innerWidth
  return Number.isFinite(width) && width > 0 ? width : fallback
}

export function getViewportHeight(fallback = 720) {
  const win = getWindow()
  const height = win?.innerHeight
  return Number.isFinite(height) && height > 0 ? height : fallback
}

export function onWindow(eventName, listener, options) {
  const win = getWindow()
  if (!win || typeof win.addEventListener !== 'function') {
    return () => {}
  }
  win.addEventListener(eventName, listener, options)
  return () => {
    win.removeEventListener(eventName, listener, options)
  }
}

export function onDocument(eventName, listener, options) {
  const doc = getDocument()
  if (!doc || typeof doc.addEventListener !== 'function') {
    return () => {}
  }
  doc.addEventListener(eventName, listener, options)
  return () => {
    doc.removeEventListener(eventName, listener, options)
  }
}

export function requestNextFrame(callback) {
  const win = getWindow()
  if (!win || typeof win.requestAnimationFrame !== 'function') {
    return null
  }
  return win.requestAnimationFrame(callback)
}

export function cancelFrame(frameId) {
  const win = getWindow()
  if (!win || typeof win.cancelAnimationFrame !== 'function' || !frameId) {
    return
  }
  win.cancelAnimationFrame(frameId)
}

export function setDocumentTitle(title) {
  const doc = getDocument()
  if (!doc) return
  doc.title = title
}

export function openExternalUrl(url, target = '_blank') {
  const win = getWindow()
  if (!win || typeof win.open !== 'function') return null
  return win.open(url, target)
}

export function reloadPage() {
  const location = getLocation()
  if (!location || typeof location.reload !== 'function') return
  location.reload()
}

export function triggerBlobDownload(blob, filename) {
  const win = getWindow()
  const doc = getDocument()
  if (!win || !doc || !win.URL || typeof win.URL.createObjectURL !== 'function') {
    throw new Error('Blob download is not supported in this runtime.')
  }

  const objectUrl = win.URL.createObjectURL(blob)
  const anchor = doc.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  doc.body.appendChild(anchor)
  anchor.click()
  doc.body.removeChild(anchor)
  win.URL.revokeObjectURL(objectUrl)
}

export function isBrowserRuntime() {
  return Boolean(getWindow() && getDocument())
}
