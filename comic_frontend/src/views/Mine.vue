<template>
  <div class="mine">
    <van-nav-bar title="我的" />
    
    <van-cell-group class="mine-menu">
      <van-cell title="导入漫画" icon="add-o" @click="showImportDialog = true" is-link />
      <van-cell title="标签管理" icon="tag-o" to="/tags" is-link />
      <van-cell title="清单管理" icon="list-o" is-link />
      <van-cell title="缓存管理" icon="cache" @click="showCachePanel = true" is-link />
      <van-cell title="系统设置" icon="settings-o" is-link />
    </van-cell-group>
    
    <!-- 缓存管理面板 -->
    <van-popup
      v-model:show="showCachePanel"
      position="bottom"
      round
      :style="{ height: '60%' }"
    >
      <div class="cache-panel">
        <van-nav-bar
          title="缓存管理"
          left-text="关闭"
          @click-left="showCachePanel = false"
        />

        <div class="cache-content">
          <!-- 缓存统计 -->
          <van-cell-group inset class="stats-group">
            <van-cell title="漫画列表" :value="listCacheStatus" />
            <van-cell title="漫画详情" :value="detailCacheCount + ' 个'" />
            <!-- 图片缓存由浏览器控制，无法设置缓存时间
            <van-cell title="图片列表" :value="imagesCacheCount + ' 个'" />
            -->
            <van-cell title="标签列表" :value="tagsCacheStatus" />
          </van-cell-group>

          <!-- 缓存时间设置 -->
          <van-cell-group inset class="settings-group">
            <van-cell title="缓存有效期（分钟，只能设置详情页，无法设置图片列表）">
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
    
    <div class="about">
      <p class="version">版本 2.0.0</p>
      <p class="copyright">© 2026 自用漫画浏览网站</p>
    </div>
    
    <van-tabbar v-model="active" route>
      <van-tabbar-item icon="home-o" to="/">主页</van-tabbar-item>
      <van-tabbar-item icon="user-o" to="/mine">我的</van-tabbar-item>
    </van-tabbar>
    
    <van-popup v-model:show="showImportDialog" round position="center">
      <div class="import-dialog">
        <h3>导入漫画</h3>
        <van-field v-model="comicId" label="漫画ID" placeholder="请输入漫画ID" />
        <van-field v-model="comicTitle" label="漫画标题" placeholder="请输入漫画标题" />
        <div class="dialog-buttons">
          <van-button @click="showImportDialog = false">取消</van-button>
          <van-button type="primary" @click="importComic" :loading="importing">确定</van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useComicStore, useCacheStore } from '@/stores'
import { showSuccessToast, showFailToast, showConfirmDialog, showToast } from 'vant'

const active = ref(1)
const showImportDialog = ref(false)
const showCachePanel = ref(false)
const comicId = ref('')
const comicTitle = ref('')
const importing = ref(false)
const cacheExpiryMinutes = ref(30)

const comicStore = useComicStore()
const cacheStore = useCacheStore()

// 缓存状态
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

    showSuccessToast('缓存已清除')
    showCachePanel.value = false
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
  loadCacheExpiry()
})

const importComic = async () => {
  if (!comicId.value) {
    showFailToast('请输入漫画ID')
    return
  }
  
  importing.value = true
  
  try {
    const response = await comicStore.initComic({
      comic_id: comicId.value,
      title: comicTitle.value || comicId.value
    })
    
    if (response.code === 200) {
      showSuccessToast('导入成功')
      showImportDialog.value = false
      await comicStore.fetchComics()
      comicId.value = ''
      comicTitle.value = ''
    } else {
      showFailToast(response.msg || '导入失败')
    }
  } catch (error) {
    showFailToast('导入失败')
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.mine {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 50px;
}

.mine-menu {
  margin-top: 10px;
}

.about {
  text-align: center;
  padding: 40px 0;
  color: #999;
}

.version {
  font-size: 14px;
  margin-bottom: 8px;
}

.copyright {
  font-size: 12px;
}

.import-dialog {
  width: 300px;
  padding: 20px;
}

.import-dialog h3 {
  text-align: center;
  margin-bottom: 20px;
}

.dialog-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
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
