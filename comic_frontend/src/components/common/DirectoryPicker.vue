<template>
  <span class="directory-picker-trigger" @click="openBrowser">
    <van-icon name="folder-o" class="picker-icon" />
  </span>

  <van-popup
    v-model:show="showPopup"
    position="bottom"
    round
    :style="{ height: '70vh' }"
    closeable
    close-icon-position="top-right"
  >
    <div class="directory-browser">
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
import { ref, computed } from 'vue'
import { listDirectory } from '@/api/comic'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue'])

const showPopup = ref(false)
const loading = ref(false)
const error = ref('')
const currentPath = ref('')
const parentPath = ref(null)
const entries = ref([])

const displayPath = computed(() => currentPath.value || '此电脑')

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

function openBrowser() {
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
  cursor: pointer;
  padding: 0 4px;
}

.picker-icon {
  font-size: 20px;
  color: var(--text-tertiary);
  transition: color var(--motion-fast) var(--ease-standard);
}

.picker-icon:active {
  color: var(--brand-600);
}

.directory-browser {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--surface-0);
  border-radius: 14px 14px 0 0;
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
