<template>
  <div class="system-config desktop-page-shell">
    <van-nav-bar title="系统设置" left-text="返回" left-arrow @click-left="$router.back()" />

    <van-cell-group inset class="config-group">
      <div class="select-row" @click="openSelectPanel('pageMode')">
        <span class="select-label">默认翻页模式</span>
        <span class="select-value">{{ pageModeLabel }} <van-icon name="arrow-down" size="12" /></span>
      </div>
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
      <div class="select-row" @click="openSelectPanel('pageSize')">
        <span class="select-label">列表分页数量</span>
        <span class="select-value">{{ pageSizeLabel }} <van-icon name="arrow-down" size="12" /></span>
      </div>
    </van-cell-group>

    <van-cell-group inset class="config-group">
      <div class="select-row" @click="openSelectPanel('background')">
        <span class="select-label">默认背景色</span>
        <span class="select-value">{{ backgroundLabel }} <van-icon name="arrow-down" size="12" /></span>
      </div>
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
      <van-cell title="第三方平台配置" is-link to="/config/third-party" />
    </van-cell-group>

    <van-cell-group inset class="config-group">
      <div class="config-group-header compact">
        <div class="config-group-title">项目密码</div>
        <div class="config-group-desc">仅在正常空间可修改；保存后新密码立即用于后续登录。</div>
      </div>
      <van-field
        v-model="projectPassword"
        type="password"
        label="新密码"
        placeholder="请输入新的登录密码"
        autocomplete="new-password"
      />
      <van-field
        v-model="projectPasswordConfirm"
        type="password"
        label="确认密码"
        placeholder="再次输入新密码"
        autocomplete="new-password"
      />
      <div class="inline-actions single">
        <van-button
          type="primary"
          block
          round
          :disabled="!canChangeProjectPassword"
          :loading="savingProjectPassword"
          @click="saveProjectPassword"
        >
          {{ canChangeProjectPassword ? '保存项目密码' : '仅正常空间可修改' }}
        </van-button>
      </div>
    </van-cell-group>

    <van-cell-group inset class="config-group">
      <div class="config-group-header">
        <div class="config-group-title">数据目录配置</div>
        <div class="config-group-desc">修改后会重启后端；迁移模式会同时移动当前 `data` 目录内容。</div>
      </div>
      <div class="path-summary-grid">
        <div class="path-summary-card">
          <span class="path-summary-label">当前运行目录</span>
          <code class="path-summary-value">{{ runtimeDataDir || '读取中...' }}</code>
        </div>
        <div v-if="resolvedDataDir && resolvedDataDir !== runtimeDataDir" class="path-summary-card emphasis">
          <span class="path-summary-label">待生效目录</span>
          <code class="path-summary-value">{{ resolvedDataDir }}</code>
        </div>
      </div>
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
      <div class="config-group-header">
        <div class="config-group-title">配置文件目录</div>
        <div class="config-group-desc">会迁移 `server_config.json` 与 `third_party_config.json`，并在保存后自动重启后端。</div>
      </div>
      <div class="path-summary-grid">
        <div class="path-summary-card">
          <span class="path-summary-label">当前运行目录</span>
          <code class="path-summary-value">{{ runtimeConfigDir || '读取中...' }}</code>
        </div>
        <div v-if="selectedConfigDir" class="path-summary-card" :class="{ emphasis: selectedConfigDir !== runtimeConfigDir }">
          <span class="path-summary-label">{{ selectedConfigDir === runtimeConfigDir ? '当前选中目录' : '重启后生效目录' }}</span>
          <code class="path-summary-value">{{ selectedConfigDir }}</code>
        </div>
        <div class="path-summary-card">
          <span class="path-summary-label">默认目录 / 来源</span>
          <code class="path-summary-value">{{ defaultConfigDir || '-' }}</code>
          <span class="path-summary-meta">来源：{{ configDirSourceLabel }}</span>
        </div>
      </div>
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

    <div class="action-area">
      <van-button type="danger" block round @click="confirmReset">
        重置为默认设置
      </van-button>
    </div>

    <div class="mmmtttt-config">github@Mmmtttt</div>

    <van-popup
      v-model:show="showSelectPanel"
      position="center"
      round
      :style="{ width: 'min(360px, calc(100vw - 32px))' }"
    >
      <div class="select-panel">
        <div class="select-panel__header">
          <div class="select-panel__title">{{ activeSelectTitle }}</div>
          <button type="button" class="select-panel__close" @click="showSelectPanel = false">
            <van-icon name="cross" />
          </button>
        </div>
        <button
          v-for="opt in activeSelectColumns"
          :key="opt.value"
          type="button"
          class="select-panel__option"
          :class="{ active: activeSelectValue === opt.value }"
          @click="onSelectPanelChoose(opt.value)"
        >
          <span>{{ opt.text }}</span>
          <van-icon v-if="activeSelectValue === opt.value" name="success" />
        </button>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'

import { comicApi } from '@/api/comic'
import { configApi } from '@/api/config'
import { reloadPage } from '@/runtime/browser'
import { useAuthStore, useConfigStore, useModeStore } from '@/stores'
import ModeSwitch from '@/components/common/ModeSwitch.vue'

const configStore = useConfigStore()
const modeStore = useModeStore()
const authStore = useAuthStore()

const pageModeValue = ref('up_down')
const singlePageBrowsingValue = ref(false)
const backgroundValue = ref('white')
const autoDownloadPreviewImportAssets = ref(true)
const pageSizeValue = ref(20)
const leftRightReadingReversedValue = ref(false)
const pageSizeOptions = [20, 40, 60]

const activeSelectPanel = ref('')
const showSelectPanel = ref(false)

const pageModeColumns = [
  { text: '左右翻页', value: 'left_right' },
  { text: '上下翻页', value: 'up_down' },
]

const pageSizeColumns = pageSizeOptions.map(s => ({ text: `每页 ${s} 条`, value: s }))

const backgroundColumns = [
  { text: '白色背景', value: 'white' },
  { text: '深色背景', value: 'dark' },
  { text: '护眼色背景', value: 'sepia' },
]

const selectColumnMap = {
  pageMode: pageModeColumns,
  pageSize: pageSizeColumns,
  background: backgroundColumns,
}

const selectValueMap = computed(() => ({
  pageMode: pageModeValue.value,
  pageSize: pageSizeValue.value,
  background: backgroundValue.value,
}))

const selectTitleMap = {
  pageMode: '默认翻页模式',
  pageSize: '列表分页数量',
  background: '默认背景色',
}

const activeSelectColumns = computed(() => selectColumnMap[activeSelectPanel.value] || [])
const activeSelectValue = computed(() => selectValueMap.value[activeSelectPanel.value])
const activeSelectTitle = computed(() => selectTitleMap[activeSelectPanel.value] || '选择设置')

const pageModeMap = { left_right: '左右翻页', up_down: '上下翻页' }
const backgroundMap = { white: '白色背景', dark: '深色背景', sepia: '护眼色背景' }

const pageModeLabel = computed(() => pageModeMap[pageModeValue.value] || pageModeValue.value)
const pageSizeLabel = computed(() => `每页 ${pageSizeValue.value} 条`)
const backgroundLabel = computed(() => backgroundMap[backgroundValue.value] || backgroundValue.value)

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
const projectPassword = ref('')
const projectPasswordConfirm = ref('')
const savingProjectPassword = ref(false)
const currentModeLabel = computed(() => (modeStore.isVideoMode ? '视频' : '漫画'))
const canChangeProjectPassword = computed(() => authStore.mode === 'normal' && authStore.authenticated)

const configDirSourceLabel = computed(() => {
  const source = String(configDirSource.value || '').toLowerCase()
  if (source === 'env') return '环境变量'
  if (source === 'persisted') return '用户设置'
  if (source === 'default') return '系统默认'
  return source || '-'
})

function initValues() {
  pageModeValue.value = configStore.defaultPageMode
  singlePageBrowsingValue.value = configStore.singlePageBrowsing
  backgroundValue.value = configStore.defaultBackground
  autoDownloadPreviewImportAssets.value = configStore.autoDownloadPreviewImportAssets
  pageSizeValue.value = configStore.listPageSize
  leftRightReadingReversedValue.value = configStore.leftRightReadingReversed
}

function openSelectPanel(name) {
  activeSelectPanel.value = name
  showSelectPanel.value = true
}

function onSelectPanelChoose(value) {
  const name = activeSelectPanel.value
  showSelectPanel.value = false
  if (name === 'pageMode') {
    if (pageModeValue.value === value) return
    pageModeValue.value = value
    updatePageMode()
  } else if (name === 'pageSize') {
    if (pageSizeValue.value === value) return
    pageSizeValue.value = value
    configStore.setListPageSize(pageSizeValue.value)
  } else if (name === 'background') {
    if (backgroundValue.value === value) return
    backgroundValue.value = value
    updateBackground()
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

async function updatePreviewImportAssetDownload() {
  configStore.setAutoDownloadPreviewImportAssets(autoDownloadPreviewImportAssets.value)
  const ok = await configStore.saveConfigToServer()
  if (!ok) {
    showFailToast('预览库导入资源下载设置保存失败')
    return
  }
  showSuccessToast('设置已保存')
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

async function saveProjectPassword() {
  if (!canChangeProjectPassword.value) {
    showFailToast('请先进入正常空间')
    return
  }
  const password = String(projectPassword.value || '').trim()
  const confirm = String(projectPasswordConfirm.value || '').trim()
  if (!password) {
    showFailToast('请输入新密码')
    return
  }
  if (password !== confirm) {
    showFailToast('两次输入的密码不一致')
    return
  }

  savingProjectPassword.value = true
  try {
    const response = await authStore.changePassword(password)
    if (response?.code !== 200) {
      showFailToast(response?.msg || '密码保存失败')
      return
    }
    projectPassword.value = ''
    projectPasswordConfirm.value = ''
    showSuccessToast('项目密码已更新')
  } catch (error) {
    showFailToast(error?.message || '密码保存失败')
  } finally {
    savingProjectPassword.value = false
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
  await Promise.all([loadSystemConfig(), loadConfigDirInfo()])
})
</script>

<style scoped>
.system-config {
  min-height: 95vh;
  background: transparent;
  padding-bottom: 20px;
}

.config-group {
  margin: 12px;
  overflow: hidden;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.config-group :deep(.van-cell),
.config-group :deep(.van-field) {
  background: transparent;
}

.config-group-header {
  padding: 16px 16px 10px;
}

.config-group-header.compact {
  padding-bottom: 6px;
}

.config-group-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-strong);
}

.config-group-desc {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-tertiary);
}

.path-summary-grid {
  display: grid;
  gap: 10px;
  padding: 0 16px 14px;
}

.path-summary-card {
  display: grid;
  gap: 6px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--border-soft);
  background: var(--surface-1);
}

.path-summary-card.emphasis {
  border-color: rgba(47, 116, 255, 0.3);
  background: rgba(89, 160, 255, 0.08);
}

.path-summary-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.path-summary-value {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
}

.path-summary-meta {
  font-size: 12px;
  color: var(--text-tertiary);
}

.inline-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding: 10px 16px 16px;
}

.secondary-action {
  margin-top: 0;
}

.inline-actions.single {
  grid-template-columns: 1fr;
}

.mmmtttt-config {
  text-align: center;
  font-size: 12px;
  color: #969799;
  padding: 16px;
}

.action-area {
  padding: 20px 16px;
}

.settings-mode-switch {
  transform: scale(0.78);
  transform-origin: right center;
}

.select-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  min-height: 48px;
  cursor: pointer;
  position: relative;
  background: transparent;
}

.select-label {
  font-size: 14px;
  color: var(--text-primary);
  flex-shrink: 0;
}

.select-value {
  font-size: 14px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
}

@media (min-width: 1024px) {
  .path-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .config-group {
    margin-inline: 10px;
    border-radius: 16px;
  }

  .inline-actions {
    grid-template-columns: 1fr;
  }
}
</style>

<style>
.select-panel {
  padding: 14px;
  background: var(--popup-bg, var(--surface-2));
}

.select-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 2px 2px 12px;
}

.select-panel__title {
  color: var(--text-strong);
  font-size: 16px;
  font-weight: 800;
}

.select-panel__close,
.select-panel__option {
  border: 0;
  font: inherit;
  cursor: pointer;
}

.select-panel__close {
  display: inline-grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 999px;
  background: var(--surface-1);
  color: var(--text-secondary);
}

.select-panel__option {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 46px;
  margin-top: 8px;
  padding: 0 14px;
  border-radius: 14px;
  background: var(--surface-1);
  color: var(--text-primary);
  text-align: left;
}

.select-panel__option.active {
  background: rgba(89, 160, 255, 0.14);
  color: var(--brand-700, #1989fa);
  font-weight: 700;
}
</style>

