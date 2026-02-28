<template>
  <div class="cache-manager">
    <van-cell-group inset class="cache-group">
      <van-cell title="缓存管理" is-link @click="showPanel = true">
        <template #icon>
          <van-icon name="cache" class="cache-icon" />
        </template>
        <template #value>
          <van-tag type="primary" size="medium">{{ cacheSizeText }}</van-tag>
        </template>
      </van-cell>
    </van-cell-group>

    <!-- 缓存管理面板 -->
    <van-popup
      v-model:show="showPanel"
      position="bottom"
      round
      :style="{ height: '60%' }"
    >
      <div class="cache-panel">
        <van-nav-bar
          title="缓存管理"
          left-text="关闭"
          @click-left="showPanel = false"
        />

        <div class="cache-content">
          <!-- 缓存统计 -->
          <van-cell-group inset class="stats-group">
            <van-cell title="缓存大小" :value="cacheSizeText" />
            <van-cell title="漫画列表" :value="listCacheStatus" />
            <van-cell title="漫画详情" :value="detailCacheCount + ' 个'" />
            <van-cell title="图片列表" :value="imagesCacheCount + ' 个'" />
            <van-cell title="标签列表" :value="tagsCacheStatus" />
          </van-cell-group>

          <!-- 缓存时间设置 -->
          <van-cell-group inset class="settings-group">
            <van-cell title="缓存有效期">
              <template #value>
                <van-stepper
                  v-model="cacheExpiryMinutes"
                  :min="1"
                  :max="1440"
                  :step="10"
                  @change="saveCacheExpiry"
                />
              </template>
            </van-cell>
            <div class="setting-hint">{{ cacheExpiryHint }}</div>
          </van-cell-group>

          <!-- 操作按钮 -->
          <div class="action-buttons">
            <van-button
              type="danger"
              block
              round
              @click="confirmClearCache"
            >
              清除所有缓存
            </van-button>
          </div>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useCacheStore } from '@/stores'
import { showConfirmDialog, showSuccessToast, showToast } from 'vant'

const cacheStore = useCacheStore()
const showPanel = ref(false)
const cacheSizeText = ref('计算中...')
const cacheExpiryMinutes = ref(30)

// 计算缓存状态
const listCacheStatus = computed(() => {
  return cacheStore.listCache ? '已缓存' : '未缓存'
})

const detailCacheCount = computed(() => {
  return Object.keys(cacheStore.detailCache || {}).length
})

const imagesCacheCount = computed(() => {
  return Object.keys(cacheStore.imagesCache || {}).length
})

const tagsCacheStatus = computed(() => {
  return cacheStore.tagsCache ? '已缓存' : '未缓存'
})

const cacheExpiryHint = computed(() => {
  const hours = Math.floor(cacheExpiryMinutes.value / 60)
  const mins = cacheExpiryMinutes.value % 60
  if (hours > 0) {
    return `缓存将在 ${hours}小时${mins > 0 ? mins + '分钟' : ''} 后过期`
  }
  return `缓存将在 ${mins}分钟 后过期`
})

// 计算缓存大小
async function calculateCacheSize() {
  try {
    let totalSize = 0

    // 计算 localStorage 大小
    for (const key in localStorage) {
      if (localStorage.hasOwnProperty(key)) {
        totalSize += localStorage[key].length * 2 // UTF-16 编码，每个字符2字节
      }
    }

    // 转换为可读格式
    cacheSizeText.value = formatSize(totalSize)
  } catch (e) {
    cacheSizeText.value = '未知'
    console.error('计算缓存大小失败:', e)
  }
}

// 格式化大小
function formatSize(bytes) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 保存缓存时间设置
function saveCacheExpiry() {
  localStorage.setItem('cache_expiry_minutes', cacheExpiryMinutes.value.toString())
  showToast(`缓存有效期已设置为 ${cacheExpiryMinutes.value} 分钟`)
}

// 确认清除缓存
function confirmClearCache() {
  showConfirmDialog({
    title: '确认清除缓存',
    message: '清除后需要重新加载数据，是否继续？',
  })
    .then(() => {
      clearAllCache()
    })
    .catch(() => {
      // 取消
    })
}

// 清除所有缓存
function clearAllCache() {
  try {
    // 清除 store 缓存
    cacheStore.clearCache('all')

    // 清除 localStorage 中的缓存数据（保留设置）
    const keysToKeep = ['cache_expiry_minutes', 'vueuse-color-scheme']
    const keysToRemove = []

    for (const key in localStorage) {
      if (localStorage.hasOwnProperty(key) && !keysToKeep.includes(key)) {
        keysToRemove.push(key)
      }
    }

    keysToRemove.forEach(key => localStorage.removeItem(key))

    // 刷新缓存大小显示
    calculateCacheSize()

    showSuccessToast('缓存已清除')
    showPanel.value = false
  } catch (e) {
    console.error('清除缓存失败:', e)
    showToast('清除缓存失败')
  }
}

// 加载缓存时间设置
function loadCacheExpiry() {
  const saved = localStorage.getItem('cache_expiry_minutes')
  if (saved) {
    cacheExpiryMinutes.value = parseInt(saved, 10) || 30
  }
}

onMounted(() => {
  calculateCacheSize()
  loadCacheExpiry()
})
</script>

<style scoped>
.cache-manager {
  margin: 8px 0;
}

.cache-group {
  margin: 0 12px;
}

.cache-icon {
  margin-right: 4px;
  font-size: 18px;
}

.cache-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.cache-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.stats-group,
.settings-group {
  margin-bottom: 16px;
}

.setting-hint {
  padding: 8px 16px;
  font-size: 12px;
  color: #969799;
  background: #f7f8fa;
}

.action-buttons {
  padding: 16px;
}
</style>
