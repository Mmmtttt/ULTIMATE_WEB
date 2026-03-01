<template>
  <div class="system-config">
    <van-nav-bar
      title="系统设置"
      left-text="返回"
      left-arrow
      @click-left="$router.back()"
    />
    
    <van-cell-group inset class="config-group">
      <van-cell title="默认翻页模式" />
      <van-radio-group v-model="pageModeValue" @change="updatePageMode">
        <van-cell-group inset>
          <van-cell title="左右翻页" clickable @click="pageModeValue = 'left_right'">
            <template #right-icon>
              <van-radio name="left_right" />
            </template>
          </van-cell>
          <van-cell title="上下翻页" clickable @click="pageModeValue = 'up_down'">
            <template #right-icon>
              <van-radio name="up_down" />
            </template>
          </van-cell>
        </van-cell-group>
      </van-radio-group>
    </van-cell-group>
    
    <van-cell-group inset class="config-group">
      <van-cell title="默认背景色" />
      <van-radio-group v-model="backgroundValue" @change="updateBackground">
        <van-cell-group inset>
          <van-cell title="白色背景" clickable @click="backgroundValue = 'white'">
            <template #right-icon>
              <van-radio name="white" />
            </template>
          </van-cell>
          <van-cell title="深色背景" clickable @click="backgroundValue = 'dark'">
            <template #right-icon>
              <van-radio name="dark" />
            </template>
          </van-cell>
          <van-cell title="护眼色背景" clickable @click="backgroundValue = 'sepia'">
            <template #right-icon>
              <van-radio name="sepia" />
            </template>
          </van-cell>
        </van-cell-group>
      </van-radio-group>
    </van-cell-group>
    
    <van-cell-group inset class="config-group">
      <van-cell title="自动隐藏工具栏">
        <template #right-icon>
          <van-switch v-model="autoHideValue" @change="updateAutoHide" />
        </template>
      </van-cell>
      <van-cell title="显示页码">
        <template #right-icon>
          <van-switch v-model="showPageNumValue" @change="updateShowPageNum" />
        </template>
      </van-cell>
    </van-cell-group>
    
    <van-cell-group inset class="config-group">
      <van-cell title="第三方库配置" is-link @click="showThirdPartyConfig = true" />
    </van-cell-group>
    
    <van-popup v-model:show="showThirdPartyConfig" position="bottom" round :style="{ height: '60%' }">
      <div class="third-party-config">
        <van-nav-bar title="第三方库配置" left-text="关闭" @click-left="showThirdPartyConfig = false" />
        
        <div class="config-content">
          <van-cell-group inset>
            <van-cell title="JMComic 账号" />
            <van-field v-model="jmcomicUsername" placeholder="请输入用户名" />
            
            <van-cell title="JMComic 密码" />
            <van-field v-model="jmcomicPassword" type="password" placeholder="请输入密码" />
            
            <van-cell title="下载目录" />
            <van-field v-model="jmcomicDownloadDir" placeholder="默认为 pictures" />
          </van-cell-group>
          
          <div class="action-buttons">
            <van-button type="primary" block round @click="saveThirdPartyConfig" :loading="saving">
              保存配置
            </van-button>
          </div>
        </div>
      </div>
    </van-popup>
    
    <div class="action-area">
      <van-button type="danger" block round @click="confirmReset">
        重置为默认设置
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useConfigStore } from '@/stores'
import { showConfirmDialog, showSuccessToast } from 'vant'
import { comicApi } from '@/api/comic'

const configStore = useConfigStore()

const pageModeValue = ref('left_right')
const backgroundValue = ref('white')
const autoHideValue = ref(true)
const showPageNumValue = ref(true)

const showThirdPartyConfig = ref(false)
const jmcomicUsername = ref('')
const jmcomicPassword = ref('')
const jmcomicDownloadDir = ref('pictures')
const saving = ref(false)

function initValues() {
  pageModeValue.value = configStore.defaultPageMode
  backgroundValue.value = configStore.defaultBackground
  autoHideValue.value = configStore.autoHideToolbar
  showPageNumValue.value = configStore.showPageNumber
}

async function updatePageMode() {
  configStore.setPageMode(pageModeValue.value)
  await configStore.saveConfigToServer()
}

async function updateBackground() {
  configStore.setBackground(backgroundValue.value)
  await configStore.saveConfigToServer()
}

async function updateAutoHide() {
  configStore.setAutoHideToolbar(autoHideValue.value)
  await configStore.saveConfigToServer()
}

async function updateShowPageNum() {
  configStore.setShowPageNumber(showPageNumValue.value)
  await configStore.saveConfigToServer()
}

async function saveThirdPartyConfig() {
  if (!jmcomicUsername.value.trim()) {
    showSuccessToast('请输入用户名')
    return
  }
  
  saving.value = true
  
  try {
    const response = await comicApi.saveThirdPartyConfig({
      adapter: 'jmcomic',
      username: jmcomicUsername.value.trim(),
      password: jmcomicPassword.value,
      download_dir: jmcomicDownloadDir.value.trim() || 'pictures'
    })
    
    if (response.code === 200) {
      showSuccessToast('配置保存成功')
      showThirdPartyConfig.value = false
    } else {
      showSuccessToast(response.msg || '配置保存失败')
    }
  } catch (error) {
    showSuccessToast('配置保存失败：' + (error.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

async function loadThirdPartyConfig() {
  try {
    const response = await comicApi.getThirdPartyConfig()
    if (response.code === 200) {
      const config = response.data
      if (config.jmcomic) {
        jmcomicUsername.value = config.jmcomic.username || ''
        jmcomicPassword.value = config.jmcomic.password || ''
        jmcomicDownloadDir.value = config.jmcomic.download_dir || 'pictures'
      }
    }
  } catch (error) {
    console.error('加载第三方库配置失败:', error)
  }
}

async function confirmReset() {
  showConfirmDialog({
    title: '重置设置',
    message: '确定要将所有设置恢复为默认值吗？',
  })
    .then(async () => {
      await configStore.resetConfig()
      initValues()
      showSuccessToast('已重置为默认设置')
    })
    .catch(() => {})
}

onMounted(async () => {
  await configStore.loadConfigFromServer()
  await loadThirdPartyConfig()
  initValues()
})
</script>

<style scoped>
.system-config {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 20px;
}

.config-group {
  margin-top: 12px;
}

.action-area {
  padding: 20px 16px;
}

.third-party-config {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.config-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.action-buttons {
  padding: 20px 16px;
}
</style>
