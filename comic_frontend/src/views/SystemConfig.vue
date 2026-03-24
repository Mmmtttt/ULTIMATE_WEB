<template>
  <div class="system-config">
    <van-nav-bar title="系统设置" left-text="返回" left-arrow @click-left="$router.back()" />

    <van-cell-group inset class="config-group">
      <van-cell title="默认翻页模式" />
      <van-radio-group v-model="pageModeValue" @change="updatePageMode">
        <van-cell-group inset>
          <van-cell title="左右翻页" clickable @click="selectPageMode('left_right')">
            <template #right-icon>
              <van-radio name="left_right" />
            </template>
          </van-cell>
          <van-cell title="上下翻页" clickable @click="selectPageMode('up_down')">
            <template #right-icon>
              <van-radio name="up_down" />
            </template>
          </van-cell>
        </van-cell-group>
      </van-radio-group>
      <van-cell title="单页浏览" label="开启后阅读页每次仅显示一页漫画（可继续缩放、滑动与翻页）">
        <template #right-icon>
          <van-switch v-model="singlePageBrowsingValue" @change="updateSinglePageBrowsing" />
        </template>
      </van-cell>
    </van-cell-group>

    <van-cell-group inset class="config-group">
      <van-cell title="默认背景色" />
      <van-radio-group v-model="backgroundValue" @change="updateBackground">
        <van-cell-group inset>
          <van-cell title="白色背景" clickable @click="selectBackground('white')">
            <template #right-icon>
              <van-radio name="white" />
            </template>
          </van-cell>
          <van-cell title="深色背景" clickable @click="selectBackground('dark')">
            <template #right-icon>
              <van-radio name="dark" />
            </template>
          </van-cell>
          <van-cell title="护眼色背景" clickable @click="selectBackground('sepia')">
            <template #right-icon>
              <van-radio name="sepia" />
            </template>
          </van-cell>
        </van-cell-group>
      </van-radio-group>
    </van-cell-group>

    <van-cell-group inset class="config-group">
      <van-cell
        title="预览库导入自动下载资源"
        label="开启后：导入到预览库时自动异步下载高清封面和预览视频（JavBus 无预览视频时会自动跳过）"
      >
        <template #right-icon>
          <van-switch v-model="autoDownloadPreviewImportAssets" @change="updatePreviewImportAssetDownload" />
        </template>
      </van-cell>
    </van-cell-group>

    <van-cell-group inset class="config-group">
      <van-cell title="第三方平台配置" is-link @click="showThirdPartyConfig = true" />
    </van-cell-group>

    <van-cell-group inset class="config-group">
      <van-cell title="数据目录配置" :label="runtimeDataDirLabel" />
      <van-field
        v-model="systemDataDir"
        label="data_dir"
        placeholder="例如 ./comic_backend/data 或 D:\\MyData\\ULTIMATE"
      />
      <div class="inline-actions">
        <van-button
          type="primary"
          block
          round
          :loading="savingSystemConfig"
          @click="saveSystemDataDir"
        >
          保存并迁移 data 目录
        </van-button>
      </div>
    </van-cell-group>

    <van-popup v-model:show="showThirdPartyConfig" position="bottom" round :style="{ height: '82%' }">
      <div class="third-party-config">
        <van-nav-bar title="第三方平台配置" left-text="关闭" @click-left="showThirdPartyConfig = false" />

        <div class="popup-content">
          <van-tabs v-model:active="activeAdapter" animated>
            <van-tab
              v-for="adapterName in displayAdapters"
              :key="adapterName"
              :name="adapterName"
              :title="adapterLabel(adapterName)"
            >
              <div class="adapter-panel">
                <van-cell-group inset>
                  <template v-for="field in adapterFields(adapterName)" :key="`${adapterName}-${field.key}`">
                    <van-cell v-if="field.type === 'boolean'" :title="field.label">
                      <template #right-icon>
                        <van-switch v-model="adapterForms[adapterName][field.key]" />
                      </template>
                    </van-cell>

                    <van-field
                      v-else-if="field.type === 'textarea'"
                      v-model="adapterForms[adapterName][field.key]"
                      type="textarea"
                      autosize
                      :label="field.label"
                      :placeholder="field.placeholder || ''"
                    />

                    <van-field
                      v-else
                      v-model="adapterForms[adapterName][field.key]"
                      :type="field.type === 'password' ? 'password' : (field.type === 'number' ? 'number' : 'text')"
                      :label="field.label"
                      :placeholder="field.placeholder || ''"
                    />
                  </template>
                </van-cell-group>

                <div v-if="adapterName === 'javdb'" class="cookie-guide">
                  <div class="cookie-guide-text">JAVDB 需先登录后获取 Cookie，再粘贴到上面的 Cookie 字符串。</div>
                  <van-button plain type="primary" block @click="openJavdbCookieGuide">
                    打开 Cookie 获取教学页
                  </van-button>
                </div>

                <div class="popup-actions">
                  <van-button
                    type="primary"
                    block
                    round
                    :loading="Boolean(savingAdapterMap[adapterName])"
                    @click="saveAdapterConfig(adapterName)"
                  >
                    保存 {{ adapterLabel(adapterName) }} 配置
                  </van-button>
                </div>
              </div>
            </van-tab>
          </van-tabs>
        </div>
      </div>
    </van-popup>

    <div class="action-area">
      <van-button type="primary" block round @click="organizeDatabase">
        整理数据库
      </van-button>
      <van-button type="danger" block round style="margin-top: 10px" @click="confirmReset">
        重置为默认设置
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'

import { comicApi } from '@/api/comic'
import { configApi } from '@/api/config'
import { openExternalUrl, reloadPage } from '@/runtime/browser'
import { useConfigStore } from '@/stores'

const configStore = useConfigStore()

const pageModeValue = ref('left_right')
const singlePageBrowsingValue = ref(false)
const backgroundValue = ref('white')
const autoDownloadPreviewImportAssets = ref(true)

const showThirdPartyConfig = ref(false)
const savingAdapterMap = ref({})
const activeAdapter = ref('')

const thirdPartySchema = ref({})
const thirdPartyAdapters = ref({})
const thirdPartyAdapterOrder = ref([])
const adapterForms = ref({})

const systemDataDir = ref('')
const runtimeDataDir = ref('')
const resolvedDataDir = ref('')
const savingSystemConfig = ref(false)

const displayAdapters = computed(() => {
  if (Array.isArray(thirdPartyAdapterOrder.value) && thirdPartyAdapterOrder.value.length > 0) {
    return thirdPartyAdapterOrder.value
  }

  const schemaKeys = Object.keys(thirdPartySchema.value || {})
  if (schemaKeys.length > 0) {
    return schemaKeys
  }

  return Object.keys(thirdPartyAdapters.value || {})
})

const runtimeDataDirLabel = computed(() => {
  if (!runtimeDataDir.value) {
    return '当前运行目录读取中...'
  }
  if (resolvedDataDir.value && resolvedDataDir.value !== runtimeDataDir.value) {
    return `当前运行目录: ${runtimeDataDir.value}（待生效: ${resolvedDataDir.value}）`
  }
  return `当前运行目录: ${runtimeDataDir.value}`
})

function initValues() {
  pageModeValue.value = configStore.defaultPageMode
  singlePageBrowsingValue.value = configStore.singlePageBrowsing
  backgroundValue.value = configStore.defaultBackground
  autoDownloadPreviewImportAssets.value = configStore.autoDownloadPreviewImportAssets
}

function adapterLabel(adapterName) {
  return thirdPartySchema.value?.[adapterName]?.label || adapterName
}

function adapterFields(adapterName) {
  return thirdPartySchema.value?.[adapterName]?.fields || []
}

function ensureAdapterFormShape() {
  const forms = {}
  const adapters = thirdPartyAdapters.value || {}

  displayAdapters.value.forEach((adapterName) => {
    const source = adapters[adapterName] || {}
    forms[adapterName] = {
      ...source,
    }

    adapterFields(adapterName).forEach((field) => {
      if (forms[adapterName][field.key] === undefined || forms[adapterName][field.key] === null) {
        if (field.type === 'boolean') {
          forms[adapterName][field.key] = false
        } else {
          forms[adapterName][field.key] = ''
        }
      }
    })
  })

  adapterForms.value = forms

  if (!activeAdapter.value && displayAdapters.value.length > 0) {
    activeAdapter.value = displayAdapters.value[0]
  }
}

async function loadThirdPartyConfig() {
  try {
    const response = await comicApi.getThirdPartyConfig()
    if (response.code !== 200) {
      return
    }

    const data = response.data || {}
    thirdPartySchema.value = data.schema || {}
    thirdPartyAdapterOrder.value = data.adapter_order || []

    const adapters = data.adapters || {
      jmcomic: data.jmcomic || {},
      picacomic: data.picacomic || {},
      javdb: data.javdb || {},
    }

    thirdPartyAdapters.value = adapters
    ensureAdapterFormShape()
  } catch (error) {
    showFailToast(error?.message || '加载第三方配置失败')
  }
}

async function loadSystemConfig() {
  try {
    const response = await configApi.getSystemConfig()
    if (response.code !== 200 || !response.data) {
      return
    }

    systemDataDir.value = response.data.configured_data_dir || ''
    runtimeDataDir.value = response.data.current_runtime_data_dir || ''
    resolvedDataDir.value = response.data.resolved_data_dir || ''
  } catch (error) {
    showFailToast(error?.message || '加载系统配置失败')
  }
}

async function updatePageMode() {
  configStore.setPageMode(pageModeValue.value)
  const ok = await configStore.saveConfigToServer()
  if (!ok) {
    showFailToast('默认翻页模式保存失败')
  }
}

async function selectPageMode(mode) {
  if (pageModeValue.value === mode) {
    return
  }
  pageModeValue.value = mode
  await updatePageMode()
}

async function updateBackground() {
  configStore.setBackground(backgroundValue.value)
  const ok = await configStore.saveConfigToServer()
  if (!ok) {
    showFailToast('默认背景色保存失败')
  }
}

async function updateSinglePageBrowsing() {
  configStore.setSinglePageBrowsing(singlePageBrowsingValue.value)
  const ok = await configStore.saveConfigToServer()
  if (!ok) {
    showFailToast('单页浏览设置保存失败')
  }
}

async function selectBackground(background) {
  if (backgroundValue.value === background) {
    return
  }
  backgroundValue.value = background
  await updateBackground()
}

async function updatePreviewImportAssetDownload() {
  configStore.setAutoDownloadPreviewImportAssets(autoDownloadPreviewImportAssets.value)
  const ok = await configStore.saveConfigToServer()
  if (!ok) {
    showFailToast('预览库导入资源下载设置保存失败')
    return
  }
  showSuccessToast('设置已保存')
}

async function saveAdapterConfig(adapterName) {
  const form = adapterForms.value?.[adapterName]
  if (!form) {
    showFailToast('配置数据为空')
    return
  }

  savingAdapterMap.value = {
    ...savingAdapterMap.value,
    [adapterName]: true,
  }

  try {
    const payload = { ...form }

    adapterFields(adapterName).forEach((field) => {
      if (field.type === 'number') {
        const value = payload[field.key]
        if (value !== '' && value !== null && value !== undefined) {
          const num = Number(value)
          payload[field.key] = Number.isFinite(num) ? num : value
        }
      }
    })

    const response = await comicApi.saveThirdPartyConfig({
      adapter: adapterName,
      config: payload,
    })

    if (response.code === 200) {
      showSuccessToast(`${adapterLabel(adapterName)} 配置已保存`)
      await loadThirdPartyConfig()
    } else {
      showFailToast(response.msg || '保存失败')
    }
  } catch (error) {
    showFailToast(error?.message || '保存失败')
  } finally {
    savingAdapterMap.value = {
      ...savingAdapterMap.value,
      [adapterName]: false,
    }
  }
}

async function saveSystemDataDir() {
  const value = String(systemDataDir.value || '').trim()
  if (!value) {
    showFailToast('请填写 data_dir')
    return
  }

  try {
    await showConfirmDialog({
      title: '确认迁移',
      message: '将迁移当前 data 目录到新路径，并自动重启后端使配置生效，是否继续？',
      confirmButtonText: '继续',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  savingSystemConfig.value = true
  try {
    const response = await configApi.updateSystemConfig({
      data_dir: value,
      migrate_data: true,
      restart_now: true,
    })

    if (response.code === 200) {
      showSuccessToast('配置已保存，后端正在重启，请稍后刷新页面')
      setTimeout(() => {
        reloadPage()
      }, 2800)
    } else {
      showFailToast(response.msg || '保存失败')
    }
  } catch (error) {
    if (String(error?.message || '').includes('Network Error')) {
      showSuccessToast('配置已提交，后端重启中，请稍后刷新页面')
      setTimeout(() => {
        reloadPage()
      }, 2800)
      return
    }
    showFailToast(error?.message || '保存失败')
  } finally {
    savingSystemConfig.value = false
  }
}

function openJavdbCookieGuide() {
  const url = configApi.getJavdbCookieGuideUrl()
  const win = openExternalUrl(url, '_blank')
  if (!win) {
    showFailToast('浏览器拦截了弹窗，请允许后重试')
  }
}

async function confirmReset() {
  try {
    await showConfirmDialog({
      title: '重置设置',
      message: '确定要将所有阅读设置恢复为默认值吗？',
    })
  } catch {
    return
  }

  await configStore.resetConfig()
  initValues()
  showSuccessToast('已重置为默认设置')
}

async function organizeDatabase() {
  try {
    await showConfirmDialog({
      title: '整理数据库',
      message: '将补全缺失封面，并回写本地实际页数，是否继续？',
    })
  } catch {
    return
  }

  try {
    const response = await comicApi.organizeDatabase()
    const rewritten = response?.data?.home?.rewritten_total_pages ?? 0
    const downloaded = (response?.data?.home?.downloaded_covers ?? 0) + (response?.data?.recommendation?.downloaded_covers ?? 0)
    showSuccessToast(`整理完成：补全封面 ${downloaded}，回写页数 ${rewritten}`)
  } catch (error) {
    showFailToast(error?.message || '数据库整理失败')
  }
}

onMounted(async () => {
  await configStore.loadConfigFromServer()
  initValues()
  await Promise.all([loadSystemConfig(), loadThirdPartyConfig()])
})
</script>

<style scoped>
.system-config {
  min-height: 100vh;
  background: transparent;
  padding-bottom: 20px;
}

.config-group {
  margin-top: 12px;
}

.inline-actions {
  padding: 10px 16px 16px;
}

.third-party-config {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.popup-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 8px 20px;
}

.adapter-panel {
  padding-top: 10px;
}

.cookie-guide {
  margin: 12px 16px 0;
  padding: 14px;
  border-radius: 12px;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  box-shadow: var(--shadow-xs);
}

.cookie-guide-text {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
  margin-bottom: 10px;
}

.popup-actions {
  padding: 16px;
}

.action-area {
  padding: 20px 16px;
}
</style>
