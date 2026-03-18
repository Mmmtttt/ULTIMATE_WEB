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

export function getScrollX() {
  const win = getWindow()
  return Number.isFinite(win?.scrollX) ? win.scrollX : 0
}

export function getScrollY() {
  const win = getWindow()
  return Number.isFinite(win?.scrollY) ? win.scrollY : 0
}

export function matchMediaQuery(query) {
  const win = getWindow()
  if (!win || typeof win.matchMedia !== 'function') return false
  return Boolean(win.matchMedia(query).matches)
}

export function isOntouchstartSupported() {
  const win = getWindow()
  if (!win) return false
  return 'ontouchstart' in win
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

export function addWindowListener(eventName, listener, options) {
  const win = getWindow()
  if (!win || typeof win.addEventListener !== 'function') return false
  win.addEventListener(eventName, listener, options)
  return true
}

export function removeWindowListener(eventName, listener, options) {
  const win = getWindow()
  if (!win || typeof win.removeEventListener !== 'function') return
  win.removeEventListener(eventName, listener, options)
}

export function addDocumentListener(eventName, listener, options) {
  const doc = getDocument()
  if (!doc || typeof doc.addEventListener !== 'function') return false
  doc.addEventListener(eventName, listener, options)
  return true
}

export function removeDocumentListener(eventName, listener, options) {
  const doc = getDocument()
  if (!doc || typeof doc.removeEventListener !== 'function') return
  doc.removeEventListener(eventName, listener, options)
}

export function getVisibilityState() {
  const doc = getDocument()
  return doc?.visibilityState ?? 'visible'
}

export function getDocumentElement() {
  const doc = getDocument()
  return doc?.documentElement ?? null
}

export function getFullscreenElement() {
  const doc = getDocument()
  return doc?.fullscreenElement ?? null
}

export async function requestFullscreen(element) {
  if (!element || typeof element.requestFullscreen !== 'function') return
  await element.requestFullscreen()
}

export async function exitFullscreen() {
  const doc = getDocument()
  if (!doc || typeof doc.exitFullscreen !== 'function') return
  await doc.exitFullscreen()
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

export function canShare() {
  const nav = getNavigator()
  return Boolean(nav && typeof nav.share === 'function')
}

export async function shareContent(payload) {
  const nav = getNavigator()
  if (!nav || typeof nav.share !== 'function') {
    throw new Error('Share is not supported in this runtime.')
  }
  await nav.share(payload)
}

export async function copyTextToClipboard(text) {
  const nav = getNavigator()
  if (nav?.clipboard?.writeText) {
    await nav.clipboard.writeText(text)
    return
  }

  const doc = getDocument()
  if (!doc || !doc.body || typeof doc.createElement !== 'function') {
    throw new Error('Clipboard is not supported in this runtime.')
  }

  const textarea = doc.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', 'readonly')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  textarea.style.pointerEvents = 'none'
  doc.body.appendChild(textarea)
  textarea.select()
  textarea.setSelectionRange(0, text.length)
  const copied = typeof doc.execCommand === 'function' ? doc.execCommand('copy') : false
  doc.body.removeChild(textarea)

  if (!copied) {
    throw new Error('Clipboard copy failed.')
  }
}
