<template>
  <div class="system-config desktop-page-shell">
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
      <van-cell
        title="左右翻页方向（漫画阅读）"
        :label="pageModeValue === 'left_right' ? '开启后按右→左方向翻页（更接近日漫阅读习惯）' : '仅在左右翻页模式下生效'"
      >
        <template #right-icon>
          <van-switch
            :model-value="leftRightReadingReversedValue"
            :disabled="pageModeValue !== 'left_right'"
            @update:model-value="updateLeftRightReadingReversed"
          />
        </template>
      </van-cell>
      <van-cell title="单页浏览" label="开启后阅读页每次仅显示一页内容（可继续缩放、滑动与翻页）">
        <template #right-icon>
          <van-switch v-model="singlePageBrowsingValue" @change="updateSinglePageBrowsing" />
        </template>
      </van-cell>
    </van-cell-group>

    <van-cell-group inset class="config-group">
      <van-cell title="内容模式">
        <template #right-icon>
          <ModeSwitch class="settings-mode-switch" />
        </template>
      </van-cell>
      <van-cell :title="`当前模式：${currentModeLabel}`" />
    </van-cell-group>

    <van-cell-group inset class="config-group">
      <van-cell title="列表分页数量" :label="`当前每页 ${pageSizeValue} 条，用于本地库、预览库、清单和回收站等页面`" />
      <van-radio-group v-model="pageSizeValue" @change="updatePageSize">
        <van-cell-group inset>
          <van-cell
            v-for="size in pageSizeOptions"
            :key="size"
            :title="`每页 ${size} 条`"
            clickable
            @click="selectPageSize(size)"
          >
            <template #right-icon>
              <van-radio :name="size" />
            </template>
          </van-cell>
        </van-cell-group>
      </van-radio-group>
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
        label="开启后导入到预览库时将自动异步下载高清封面和预览视频（JavBus 无预览视频时自动跳过）"
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
          :loading="savingSystemConfigMode === 'migrate'"
          @click="saveSystemDataDirWithMigration"
        >
          保存并迁移 data 目录
        </van-button>
        <van-button
          plain
          type="primary"
          block
          round
          class="secondary-action"
          :loading="savingSystemConfigMode === 'rebind'"
          @click="saveSystemDataDirWithoutMigration"
        >
          仅保存 data 目录路径
        </van-button>
      </div>
    </van-cell-group>

    <van-cell-group inset class="config-group">
      <van-cell title="配置文件目录" :label="configDirStatusLabel" />
      <van-cell title="默认目录" :value="defaultConfigDir || '-'" />
      <van-cell title="目录来源" :value="configDirSourceLabel" />
      <van-field
        v-model="configDirInput"
        label="config_dir"
        placeholder="例如 C:\\Users\\用户名\\AppData\\Roaming\\ULTIMATE_WEB"
      />
      <div class="inline-actions">
        <van-button
          type="primary"
          block
          round
          :loading="savingConfigDir"
          @click="saveConfigDir"
        >
          保存配置目录并迁移配置文件
        </van-button>
      </div>
    </van-cell-group>

    <van-popup
      v-model:show="showThirdPartyConfig"
      class="third-party-popup"
      position="bottom"
      round
      teleport="body"
      :style="thirdPartyPopupStyle"
    >
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

                <div v-if="adapterActions(adapterName).length > 0" class="adapter-actions">
                  <div
                    v-for="action in adapterActions(adapterName)"
                    :key="`${adapterName}-${action.key || action.label}`"
                    class="adapter-action-card"
                  >
                    <div v-if="action.description" class="adapter-action-text">{{ action.description }}</div>
                    <van-button plain type="primary" block @click="runAdapterAction(action)">
                      {{ action.label || action.key || '执行动作' }}
                    </van-button>
                  </div>
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
      <van-button type="danger" block round @click="confirmReset">
        重置为默认设置
      </van-button>
    </div>

    <div class="mmmtttt-config">github@Mmmtttt</div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'

import { comicApi } from '@/api/comic'
import { configApi } from '@/api/config'
import { useDevice } from '@/composables/useDevice'
import { openExternalUrl, reloadPage } from '@/runtime/browser'
import { resolveBackendApiUrl } from '@/runtime/endpoint'
import { useConfigStore, useModeStore } from '@/stores'
import ModeSwitch from '@/components/common/ModeSwitch.vue'

const configStore = useConfigStore()
const modeStore = useModeStore()
const { isDesktop } = useDevice()

const pageModeValue = ref('up_down')
const singlePageBrowsingValue = ref(false)
const backgroundValue = ref('white')
const autoDownloadPreviewImportAssets = ref(true)
const pageSizeValue = ref(20)
const leftRightReadingReversedValue = ref(false)
const pageSizeOptions = [20, 40, 60]

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
const savingSystemConfigMode = ref('')
const configDirInput = ref('')
const runtimeConfigDir = ref('')
const selectedConfigDir = ref('')
const defaultConfigDir = ref('')
const configDirSource = ref('')
const savingConfigDir = ref(false)
const currentModeLabel = computed(() => (modeStore.isVideoMode ? '视频' : '漫画'))

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

const configDirSourceLabel = computed(() => {
  const source = String(configDirSource.value || '').toLowerCase()
  if (source === 'env') return '环境变量'
  if (source === 'persisted') return '用户设置'
  if (source === 'default') return '系统默认'
  return source || '-'
})

const configDirStatusLabel = computed(() => {
  if (!runtimeConfigDir.value) {
    return '配置目录读取中...'
  }

  const segments = [`当前运行: ${runtimeConfigDir.value}`]
  if (selectedConfigDir.value && selectedConfigDir.value !== runtimeConfigDir.value) {
    segments.push(`重启后生效: ${selectedConfigDir.value}`)
  }
  if (defaultConfigDir.value) {
    segments.push(`默认: ${defaultConfigDir.value}`)
  }
  segments.push(`来源: ${configDirSourceLabel.value}`)
  return segments.join('；')
})

const thirdPartyPopupStyle = computed(() => ({
  height: isDesktop.value ? '90vh' : '82%'
}))

function initValues() {
  pageModeValue.value = configStore.defaultPageMode
  singlePageBrowsingValue.value = configStore.singlePageBrowsing
  backgroundValue.value = configStore.defaultBackground
  autoDownloadPreviewImportAssets.value = configStore.autoDownloadPreviewImportAssets
  pageSizeValue.value = configStore.listPageSize
  leftRightReadingReversedValue.value = configStore.leftRightReadingReversed
}

function adapterLabel(adapterName) {
  return thirdPartySchema.value?.[adapterName]?.label || adapterName
}

function adapterFields(adapterName) {
  return thirdPartySchema.value?.[adapterName]?.fields || []
}

function adapterActions(adapterName) {
  return thirdPartySchema.value?.[adapterName]?.actions || []
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

    const adapters = data.adapters || {}

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

async function loadConfigDirInfo() {
  try {
    const response = await configApi.getConfigDirInfo()
    if (response.code !== 200 || !response.data) {
      return
    }

    runtimeConfigDir.value = response.data.runtime_config_dir || ''
    selectedConfigDir.value = response.data.selected_config_dir || ''
    defaultConfigDir.value = response.data.default_config_dir || ''
    configDirSource.value = response.data.source || ''
    configDirInput.value = response.data.selected_config_dir || response.data.runtime_config_dir || ''
  } catch (error) {
    showFailToast(error?.message || '加载配置目录信息失败')
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

function updatePageSize() {
  configStore.setListPageSize(pageSizeValue.value)
}

function selectPageSize(size) {
  if (pageSizeValue.value === size) {
    return
  }
  pageSizeValue.value = size
  updatePageSize()
}

function updateLeftRightReadingReversed(value) {
  leftRightReadingReversedValue.value = Boolean(value)
  configStore.setLeftRightReadingReversed(leftRightReadingReversedValue.value)
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

async function saveSystemDataDir({ migrateData }) {
  const value = String(systemDataDir.value || '').trim()
  if (!value) {
    showFailToast('请填写 data_dir')
    return
  }

  try {
    await showConfirmDialog({
      title: migrateData ? '确认迁移' : '确认仅修改路径',
      message: migrateData
        ? '将直接移动当前 data 目录到新路径，并自动重启后端使配置生效，是否继续？'
        : '将仅修改 data_dir 配置并重启后端，原目录数据不会移动，是否继续？',
      confirmButtonText: '继续',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  savingSystemConfigMode.value = migrateData ? 'migrate' : 'rebind'
  try {
    const response = await configApi.updateSystemConfig({
      data_dir: value,
      migrate_data: Boolean(migrateData),
      restart_now: true,
    })

    if (response.code === 200) {
      showSuccessToast(
        migrateData
          ? 'data 目录已迁移，后端正在重启，请稍后刷新页面'
          : 'data 目录路径已保存，后端正在重启，请稍后刷新页面'
      )
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
    savingSystemConfigMode.value = ''
  }
}

function saveSystemDataDirWithMigration() {
  return saveSystemDataDir({ migrateData: true })
}

function saveSystemDataDirWithoutMigration() {
  return saveSystemDataDir({ migrateData: false })
}

async function saveConfigDir() {
  const value = String(configDirInput.value || '').trim()
  if (!value) {
    showFailToast('请填写 config_dir')
    return
  }

  try {
    await showConfirmDialog({
      title: '确认修改配置目录',
      message: '将迁移 server_config.json 和 third_party_config.json 到新目录，并重启后端使其生效，是否继续？',
      confirmButtonText: '继续',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  savingConfigDir.value = true
  try {
    const response = await configApi.updateConfigDir({
      config_dir: value,
      migrate_configs: true,
      restart_now: true,
    })

    if (response.code === 200) {
      showSuccessToast('配置目录已保存，后端正在重启，请稍后刷新页面')
      setTimeout(() => {
        reloadPage()
      }, 2800)
    } else {
      showFailToast(response.msg || '保存失败')
    }
  } catch (error) {
    if (String(error?.message || '').includes('Network Error')) {
      showSuccessToast('配置目录已提交，后端重启中，请稍后刷新页面')
      setTimeout(() => {
        reloadPage()
      }, 2800)
      return
    }
    showFailToast(error?.message || '保存失败')
  } finally {
    savingConfigDir.value = false
  }
}

function runAdapterAction(action) {
  const kind = String(action?.kind || '').trim().toLowerCase()
  const rawUrl = String(action?.url || '').trim()
  if (kind !== 'open_url' || !rawUrl) {
    showFailToast('当前动作暂不支持')
    return
  }

  const url = /^https?:\/\//i.test(rawUrl) ? rawUrl : resolveBackendApiUrl(rawUrl)
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
      message: '将补全缺失封面并回写本地实际页数，是否继续？',
    })
  } catch {
    return
  }

  try {
    const response = await comicApi.organizeDatabase()
    const rewritten = response?.data?.home?.rewritten_total_pages ?? 0
    const downloaded = (response?.data?.home?.updated_cover_paths ?? 0) + (response?.data?.recommendation?.updated_cover_paths ?? 0)
    showSuccessToast(`整理完成：补全封面 ${downloaded}，回写页数 ${rewritten}`)
  } catch (error) {
    showFailToast(error?.message || '数据库整理失败')
  }
}

onMounted(async () => {
  await configStore.loadConfigFromServer()
  initValues()
  await Promise.all([loadSystemConfig(), loadThirdPartyConfig(), loadConfigDirInfo()])
})
</script>

<style scoped>
.system-config {
  min-height: 100vh;
  background: transparent;
  padding-bottom: 20px;
}

@media (min-width: 1024px) {
  .system-config.desktop-page-shell {
    overflow: visible;
  }
}

.config-group {
  margin-top: 12px;
}

.inline-actions {
  padding: 10px 16px 16px;
}

.secondary-action {
  margin-top: 10px;
}

.mmmtttt-config {
  text-align: center;
  font-size: 12px;
  color: #969799;
  padding: 16px;
}

.third-party-config {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.popup-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px 8px 20px;
}

.adapter-panel {
  padding-top: 10px;
}

.adapter-actions {
  margin: 12px 16px 0;
  display: grid;
  gap: 10px;
}

.adapter-action-card {
  padding: 14px;
  border-radius: 12px;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  box-shadow: var(--shadow-xs);
}

.adapter-action-text {
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

.settings-mode-switch {
  transform: scale(0.78);
  transform-origin: right center;
}
</style>

