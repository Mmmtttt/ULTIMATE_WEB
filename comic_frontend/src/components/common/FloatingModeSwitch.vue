<template>
  <button
    ref="rootEl"
    type="button"
    class="floating-mode-switch"
    :class="[`is-${mode}`, { 'is-dragging': dragging, 'is-snapping': snapping }]"
    :style="{ left: `${pos.x}px`, top: `${pos.y}px` }"
    :aria-label="ariaLabel"
    @pointerdown="onPointerDown"
    @keydown.enter.prevent="toggleMode"
    @keydown.space.prevent="toggleMode"
    @contextmenu.prevent
  >
    <van-icon :name="mode === 'video' ? 'video-o' : 'photo-o'" class="fms-icon" />
  </button>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import { useModeStore } from '@/stores/mode'

const EDGE_MARGIN = 14
const DRAG_THRESHOLD = 6
const STORAGE_KEY = 'ULTIMATE_MODE_SWITCH_POS'

const modeStore = useModeStore()
const mode = computed(() => modeStore.currentMode)
const ariaLabel = computed(() => (
  mode.value === 'video' ? '当前是视频模式，点击切换到漫画' : '当前是漫画模式，点击切换到视频'
))

const rootEl = ref(null)
const pos = reactive({ x: 0, y: 0 })
const dragging = ref(false)
const snapping = ref(false)

let drag = null
let snapTimer = null

function viewportSize() {
  return { w: window.innerWidth, h: window.innerHeight }
}

/** 顶栏与底部 tabbar 占用的区域不参与吸附，避免按钮压住导航 */
function layoutInsets() {
  const header = document.querySelector('.mobile-header')
  const tabbar = document.querySelector('.van-tabbar')
  let top = 0
  if (header) {
    top = header.getBoundingClientRect().height
  } else {
    // 顶栏被移除时（悬浮按钮开启），用内容区顶部的安全留白避开状态栏
    const main = document.querySelector('.main-content')
    const paddingTop = main ? Number.parseFloat(window.getComputedStyle(main).paddingTop) : 0
    top = Number.isFinite(paddingTop) ? paddingTop : 0
  }
  return {
    top,
    bottom: tabbar ? tabbar.getBoundingClientRect().height : 0
  }
}

function bounds() {
  const el = rootEl.value
  const rect = el?.getBoundingClientRect()
  const width = rect?.width || 84
  const height = rect?.height || 38
  const { w, h } = viewportSize()
  const inset = layoutInsets()
  const minX = EDGE_MARGIN
  const maxX = Math.max(minX, w - width - EDGE_MARGIN)
  const minY = inset.top + EDGE_MARGIN
  const maxY = Math.max(minY, h - height - inset.bottom - EDGE_MARGIN)
  return { minX, maxX, minY, maxY }
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

function clampPosition() {
  const b = bounds()
  pos.x = clamp(pos.x, b.minX, b.maxX)
  pos.y = clamp(pos.y, b.minY, b.maxY)
}

function persistPosition() {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ x: Math.round(pos.x), y: Math.round(pos.y) }))
  } catch (_) {
    // 存不了就只保留本次会话的位置
  }
}

function placeDefault() {
  const b = bounds()
  pos.x = b.maxX
  pos.y = Math.round(b.minY + (b.maxY - b.minY) * 0.42)
}

function restorePosition() {
  let saved = null
  try {
    saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || 'null')
  } catch (_) {
    saved = null
  }
  if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y)) {
    pos.x = saved.x
    pos.y = saved.y
    clampPosition()
    return
  }
  placeDefault()
}

function toggleMode() {
  modeStore.toggleMode()
}

function onPointerDown(event) {
  if (event.pointerType === 'mouse' && event.button !== 0) return
  const el = rootEl.value
  if (!el) return
  drag = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    originX: pos.x,
    originY: pos.y,
    moved: false
  }
  try {
    el.setPointerCapture(event.pointerId)
  } catch (_) {
    // 某些 WebView 不支持捕获，退化成窗口监听
  }
  window.addEventListener('pointermove', onPointerMove, { passive: false })
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('pointercancel', onPointerUp)
}

function onPointerMove(event) {
  if (!drag || event.pointerId !== drag.pointerId) return
  const dx = event.clientX - drag.startX
  const dy = event.clientY - drag.startY
  if (!drag.moved) {
    if (Math.hypot(dx, dy) < DRAG_THRESHOLD) return
    drag.moved = true
    dragging.value = true
  }
  event.preventDefault()
  const b = bounds()
  pos.x = clamp(drag.originX + dx, b.minX, b.maxX)
  pos.y = clamp(drag.originY + dy, b.minY, b.maxY)
}

function onPointerUp(event) {
  if (!drag) return
  if (event?.pointerId !== undefined && event.pointerId !== drag.pointerId) return
  const moved = drag.moved
  endDrag()
  if (moved) {
    snapToNearestEdge()
  } else {
    toggleMode()
  }
}

function endDrag() {
  drag = null
  dragging.value = false
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerUp)
}

/** 以按钮与四条边的距离取最近的一条，贴边吸附 */
function snapToNearestEdge() {
  const b = bounds()
  const distances = {
    left: pos.x - b.minX,
    right: b.maxX - pos.x,
    top: pos.y - b.minY,
    bottom: b.maxY - pos.y
  }
  const edge = Object.keys(distances).reduce(
    (best, key) => (distances[key] < distances[best] ? key : best),
    'left'
  )

  snapping.value = true
  if (edge === 'left') pos.x = b.minX
  else if (edge === 'right') pos.x = b.maxX
  else if (edge === 'top') pos.y = b.minY
  else pos.y = b.maxY

  clampPosition()
  persistPosition()

  window.clearTimeout(snapTimer)
  snapTimer = window.setTimeout(() => {
    snapping.value = false
  }, 240)
}

function handleResize() {
  clampPosition()
}

onMounted(() => {
  window.requestAnimationFrame(() => {
    restorePosition()
    window.addEventListener('resize', handleResize)
    window.addEventListener('orientationchange', handleResize)
  })
})

onBeforeUnmount(() => {
  endDrag()
  window.clearTimeout(snapTimer)
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('orientationchange', handleResize)
})
</script>

<style scoped>
.floating-mode-switch {
  position: fixed;
  z-index: 120;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  padding: 0;
  border: 1px solid var(--border-soft);
  border-radius: 50%;
  background: var(--surface-2);
  box-shadow: var(--shadow-md);
  color: var(--text-strong);
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
  -webkit-tap-highlight-color: transparent;
  cursor: grab;
  transition: box-shadow 0.18s ease, border-color 0.18s ease, transform 0.12s ease;
}

.floating-mode-switch.is-dragging {
  cursor: grabbing;
  box-shadow: 0 18px 38px rgba(20, 42, 81, 0.24);
  transform: scale(1.04);
}

.floating-mode-switch.is-snapping {
  transition:
    left 0.22s var(--ease-standard, cubic-bezier(0.4, 0, 0.2, 1)),
    top 0.22s var(--ease-standard, cubic-bezier(0.4, 0, 0.2, 1)),
    box-shadow 0.18s ease,
    border-color 0.18s ease,
    transform 0.12s ease;
}

.floating-mode-switch:active {
  transform: scale(0.96);
}

.floating-mode-switch:focus-visible {
  outline: 2px solid var(--brand-500);
  outline-offset: 2px;
}

.fms-icon {
  font-size: 20px;
}

.floating-mode-switch.is-comic .fms-icon {
  color: #ff9f00;
}

.floating-mode-switch.is-video .fms-icon {
  color: #1989fa;
}
</style>
