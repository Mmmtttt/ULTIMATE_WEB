<template>
  <span
    class="directory-picker-trigger"
    title="浏览服务端目录..."
    @click="openBrowser"
  >
    <van-icon name="folder-o" class="picker-icon" />
    <span class="picker-label">浏览</span>
  </span>

  <van-popup
    v-model:show="showPopup"
    :position="isMobile ? 'bottom' : 'center'"
    :round="isMobile"
    :style="isMobile ? { height: '70vh' } : { width: 'min(540px, 90vw)', maxHeight: '80vh', borderRadius: '12px' }"
    closeable
    close-icon-position="top-right"
    @click-overlay="showPopup = false"
  >
    <div class="directory-browser" :class="{ 'desktop-browser': !isMobile }">
      <!-- Header -->
      <div class="browser-header">
        <div class="browser-title">选择服务端目录</div>
        <div class="browser-path-bar">
          <van-button
            v-if="currentPath"
            icon="arrow-left"
            size="small"
            plain
            :disabled="!parentPath"
            @click="goUp"
          >
            上级
          </van-button>
          <span class="current-path-text">{{ displayPath }}</span>
        </div>
      </div>

      <!-- Loading -->
      <van-loading v-if="loading" type="spinner" class="browser-loading" />

      <!-- Error -->
      <van-empty v-else-if="error" :description="error">
        <van-button size="small" @click="refreshCurrent">重试</van-button>
      </van-empty>

      <!-- Directory List -->
      <div v-else class="browser-list">
        <div
          v-for="entry in entries"
          :key="entry.path"
          class="browser-item"
          :class="{ 'is-dir': entry.is_dir }"
          @click="entry.is_dir ? enterDir(entry) : null"
        >
          <van-icon
            :name="entry.is_dir ? 'folder' : 'file-o'"
            class="item-icon"
            :class="{ 'dir-icon': entry.is_dir }"
          />
          <span class="item-name">{{ entry.name }}</span>
          <span v-if="!entry.is_dir && entry.size" class="item-size">{{ formatSize(entry.size) }}</span>
          <van-icon v-if="entry.is_dir" name="arrow" class="item-arrow" />
        </div>

        <van-empty v-if="entries.length === 0" description="此目录为空" />
      </div>

      <!-- Footer -->
      <div v-if="currentPath" class="browser-footer">
        <van-button type="primary" block @click="confirmSelect">
          选中当前目录
        </van-button>
      </div>
    </div>
  </van-popup>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { listDirectory } from '@/api/comic'
import { useDevice } from '@/composables/useDevice'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  }
})

const { isMobile } = useDevice()

const emit = defineEmits(['update:modelValue'])

const showPopup = ref(false)
const loading = ref(false)
const error = ref('')
const currentPath = ref('')
const parentPath = ref(null)
const entries = ref([])
const hasNativePicker = ref(false)
const nativePickerBusy = ref(false)
let nativeRetryTimer = null

// ── Android Native Directory Picker ──
// Use global callback store so it survives component instance changes

function getPendingCallbacks() {
  if (typeof window === 'undefined') return null
  if (!window.__nativeDirPickerCallbacks) {
    window.__nativeDirPickerCallbacks = {}
  }
  return window.__nativeDirPickerCallbacks
}

function setupNativeBridge(retries = 12) {
  if (typeof window === 'undefined') return
  const bridge = window.AndroidBridge
  if (bridge && typeof bridge.pickDirectory === 'function') {
    hasNativePicker.value = true

    // Register the callback handler once (shared across all instances)
    if (!window._nativePickerRegistered) {
      window.AndroidBridge.onDirectoryPicked = (callbackId, path) => {
        const callbacks = getPendingCallbacks()
        if (!callbacks) return
        const resolve = callbacks[callbackId]
        if (resolve) {
          resolve(path)
          delete callbacks[callbackId]
        }
      }
      window._nativePickerRegistered = true
    }
    return
  }

  // Retry: bridge may not be ready yet in Android WebView
  if (retries > 0) {
    nativeRetryTimer = setTimeout(() => setupNativeBridge(retries - 1), 400)
  }
}

// Fresh check whether the native bridge is available right now
function checkNativeBridgeNow() {
  if (hasNativePicker.value) return true
  if (typeof window === 'undefined') return false
  const bridge = window.AndroidBridge
  if (bridge && typeof bridge.pickDirectory === 'function') {
    hasNativePicker.value = true
    // Also ensure the callback handler is registered
    if (!window._nativePickerRegistered) {
      window.AndroidBridge.onDirectoryPicked = (callbackId, path) => {
        const callbacks = getPendingCallbacks()
        if (!callbacks) return
        const resolve = callbacks[callbackId]
        if (resolve) {
          resolve(path)
          delete callbacks[callbackId]
        }
      }
      window._nativePickerRegistered = true
    }
    return true
  }
  return false
}

function pickNativeDirectory() {
  return new Promise((resolve) => {
    const callbacks = getPendingCallbacks()
    if (!callbacks) { resolve(null); return }

    const callbackId = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    callbacks[callbackId] = (path) => {
      resolve(path)
    }
    try {
      window.AndroidBridge.pickDirectory(callbackId)

      // The JS onDirectoryPicked callback may be lost if the WebView JS
      // context was cleared while the SAF picker was open.
      // Poll sessionStorage every 300ms as a reliable fallback.
      const pollTimer = setInterval(() => {
        const stored = drainSessionStorageResult()
        if (stored) {
          clearInterval(pollTimer)
          if (callbacks[callbackId]) {
            delete callbacks[callbackId]
            resolve(stored)
          }
        }
      }, 300)

      // Hard timeout: give up after 12s
      setTimeout(() => {
        clearInterval(pollTimer)
        if (callbacks[callbackId]) {
          delete callbacks[callbackId]
          resolve(null)
        }
      }, 12000)
    } catch (e) {
      delete callbacks[callbackId]
      resolve(null)
    }
  })
}

// Consume a path written to sessionStorage by the Java side.
// This is the fallback channel when the JS callback (onDirectoryPicked)
// gets lost due to WebView lifecycle pause / page reload.
function drainSessionStorageResult() {
  try {
    const raw = sessionStorage.getItem('__native_dir_path')
    if (!raw) return null
    sessionStorage.removeItem('__native_dir_path')
    const path = JSON.parse(raw)
    if (path && typeof path === 'string' && !path.startsWith('__error__:')) {
      return path
    }
  } catch (_) { /* ignore parse errors */ }
  return null
}

onMounted(() => {
  setupNativeBridge()
  // On mount, check for a result left behind in sessionStorage
  // (e.g. WebView was killed while SAF picker was open)
  const stored = drainSessionStorageResult()
  if (stored) {
    emit('update:modelValue', stored)
  }
})

function formatSize(bytes) {
  if (!bytes) return ''
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`
}

// ── Server-side Directory Browser ──

async function loadDirectory(path) {
  loading.value = true
  error.value = ''
  try {
    const res = await listDirectory(path)
    if (res.code !== 200) {
      error.value = res.msg || '加载失败'
      return
    }
    currentPath.value = res.data.current_path || ''
    parentPath.value = res.data.parent_path || null
    entries.value = res.data.entries || []
  } catch (e) {
    error.value = e?.message || '网络错误'
  } finally {
    loading.value = false
  }
}

async function openBrowser() {
  console.log('[DirPicker] openBrowser called')

  // Android APK: try native SAF directory picker first
  const bridgeAvailable = checkNativeBridgeNow()
  console.log('[DirPicker] bridgeAvailable:', bridgeAvailable, 'busy:', nativePickerBusy.value)

  if (bridgeAvailable && !nativePickerBusy.value) {
    nativePickerBusy.value = true
    try {
      console.log('[DirPicker] calling pickNativeDirectory...')
      const path = await pickNativeDirectory()
      console.log('[DirPicker] pickNativeDirectory returned:', path)

      if (path && !path.startsWith('__error__:')) {
        console.log('[DirPicker] emitting path via callback:', path)
        emit('update:modelValue', path)
        return
      }

      // Callback didn't fire — check sessionStorage fallback
      const stored = drainSessionStorageResult()
      console.log('[DirPicker] sessionStorage fallback:', stored)
      if (stored) {
        console.log('[DirPicker] emitting path via sessionStorage:', stored)
        emit('update:modelValue', stored)
        return
      }
      // Native picker returned null/error → fall through to server-side browser
    } finally {
      nativePickerBusy.value = false
    }
  }

  // Desktop / browser / Android fallback
  console.log('[DirPicker] falling back to server-side directory browser')
  showPopup.value = true
  loadDirectory(props.modelValue || '')
}

function enterDir(entry) {
  loadDirectory(entry.path)
}

function goUp() {
  if (parentPath.value) {
    loadDirectory(parentPath.value)
  }
}

function refreshCurrent() {
  loadDirectory(currentPath.value)
}

function confirmSelect() {
  if (currentPath.value) {
    emit('update:modelValue', currentPath.value)
  }
  showPopup.value = false
}
</script>

<style scoped>
.directory-picker-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-soft);
  background: var(--surface-1);
  transition: all var(--motion-fast) var(--ease-standard);
  user-select: none;
  white-space: nowrap;
}

.directory-picker-trigger:hover {
  border-color: var(--brand-400);
  background: var(--surface-2);
}

.directory-picker-trigger:active {
  border-color: var(--brand-600);
}

.picker-icon {
  font-size: 18px;
  color: var(--text-tertiary);
}

.picker-label {
  font-size: 13px;
  color: var(--text-tertiary);
  line-height: 1;
}

.directory-picker-trigger:hover .picker-icon,
.directory-picker-trigger:hover .picker-label {
  color: var(--brand-600);
}

/* ── Browser Panel ── */

.directory-browser {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--surface-0);
}

.directory-browser.desktop-browser {
  border-radius: 12px;
  overflow: hidden;
}

.browser-header {
  padding: 16px 14px 8px;
  border-bottom: 1px solid var(--border-soft);
  flex-shrink: 0;
}

.browser-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-strong);
  margin-bottom: 8px;
}

.browser-path-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.current-path-text {
  font-size: 12px;
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.browser-loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}

.browser-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.browser-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  cursor: pointer;
  transition: background var(--motion-fast) var(--ease-standard);
}

.browser-item:hover {
  background: var(--surface-2);
}

.browser-item:active {
  background: var(--surface-3);
}

.browser-item.is-dir {
  cursor: pointer;
}

.item-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.dir-icon {
  color: #ff976a;
}

.item-name {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-size {
  font-size: 11px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.item-arrow {
  font-size: 14px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.browser-footer {
  padding: 10px 14px;
  padding-bottom: calc(10px + env(safe-area-inset-bottom, 0px));
  border-top: 1px solid var(--border-soft);
  flex-shrink: 0;
}
</style>
