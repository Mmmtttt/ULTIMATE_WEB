<template>
  <div class="system-config desktop-page-shell">
    <van-nav-bar title="系统设置" left-text="返回" left-arrow @click-left="$router.back()" />

    <section class="settings-section">
      <div class="section-heading">
        <div>
          <span class="section-kicker">READER EXPERIENCE</span>
          <h2>阅读体验</h2>
        </div>
        <span class="section-note">常用设置</span>
      </div>
      <van-cell-group inset class="config-group settings-card">
        <div class="select-row" @click.stop="toggleDropdown('pageMode', $event)">
          <div class="setting-copy">
            <span class="select-label">默认翻页模式</span>
            <span class="setting-description">可选择上下翻页、左→右或右→左翻页</span>
          </div>
          <span class="select-value">{{ pageModeLabel }} <van-icon name="arrow-down" size="12" /></span>
        </div>
        <van-cell title="单页浏览" label="开启后阅读页每次仅显示一页内容（可继续缩放、滑动与翻页）">
          <template #right-icon>
            <van-switch v-model="singlePageBrowsingValue" @change="updateSinglePageBrowsing" />
          </template>
        </van-cell>
        <div class="select-row" @click.stop="toggleDropdown('background', $event)">
          <div class="setting-copy">
            <span class="select-label">默认背景色</span>
            <span class="setting-description">应用于漫画阅读页的默认背景</span>
          </div>
          <span class="select-value">{{ backgroundLabel }} <van-icon name="arrow-down" size="12" /></span>
        </div>
      </van-cell-group>
    </section>

    <section class="settings-section">
      <div class="section-heading">
        <div>
          <span class="section-kicker">LIBRARY & CONTENT</span>
          <h2>列表与内容</h2>
        </div>
        <span class="section-note">显示设置</span>
      </div>
      <van-cell-group inset class="config-group settings-card">
        <van-cell title="内容模式" label="切换漫画与视频的内容模式">
          <template #right-icon>
            <ModeSwitch class="settings-mode-switch" />
          </template>
        </van-cell>
        <van-cell :title="`当前模式：${currentModeLabel}`" class="mode-status-cell" />
        <div class="select-row" @click.stop="toggleDropdown('pageSize', $event)">
          <div class="setting-copy">
            <span class="select-label">列表分页数量</span>
            <span class="setting-description">本地库、预览库等列表的默认分页数量</span>
          </div>
          <span class="select-value">{{ pageSizeLabel }} <van-icon name="arrow-down" size="12" /></span>
        </div>
        <van-cell
          title="预览库导入自动下载资源"
          label="开启后导入到预览库时将自动异步下载高清封面和预览视频（无预览视频时自动跳过）"
        >
          <template #right-icon>
            <van-switch v-model="autoDownloadPreviewImportAssets" @change="updatePreviewImportAssetDownload" />
          </template>
        </van-cell>
      </van-cell-group>
    </section>

    <section class="settings-section settings-section--compact">
      <div class="section-heading">
        <div>
          <span class="section-kicker">PLATFORM</span>
          <h2>平台与诊断</h2>
        </div>
      </div>
      <van-cell-group inset class="config-group settings-card">
        <van-cell
          title="Debug 日志模式"
          label="开启后记录更完整的诊断日志；关闭时保留错误和重要操作日志。"
        >
          <template #right-icon>
            <van-switch v-model="debugModeValue" @change="updateDebugMode" />
          </template>
        </van-cell>
        <van-cell title="第三方平台配置" label="管理搜索、导入和补全信息使用的平台" is-link to="/config/third-party" />
      </van-cell-group>
    </section>

    <section class="settings-section settings-section--advanced">
      <div class="section-heading">
        <div>
          <span class="section-kicker">SERVICE & DATA</span>
          <h2>服务与数据</h2>
        </div>
        <span class="section-note">高级设置</span>
      </div>

      <details class="config-disclosure">
        <summary class="config-disclosure-summary">
          <span class="disclosure-icon"><van-icon name="lock" size="17" /></span>
          <span class="disclosure-copy">
            <strong>项目密码</strong>
            <small>{{ canChangeProjectPassword ? '正常空间可修改登录密码' : '仅正常空间可修改' }}</small>
          </span>
          <van-icon name="arrow" size="16" class="disclosure-chevron" />
        </summary>
        <div class="disclosure-body">
          <p class="disclosure-note">保存后新密码立即用于后续登录，不会显示当前密码。</p>
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
        </div>
      </details>

      <details class="config-disclosure">
        <summary class="config-disclosure-summary">
          <span class="disclosure-icon"><van-icon name="folder-o" size="17" /></span>
          <span class="disclosure-copy">
            <strong>数据目录配置</strong>
            <small>{{ runtimeDataDir || '正在读取当前运行目录' }}</small>
          </span>
          <van-icon name="arrow" size="16" class="disclosure-chevron" />
        </summary>
        <div class="disclosure-body">
          <p class="disclosure-note">修改后会重启后端；迁移模式会同时移动当前 data 目录内容。</p>
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
        </div>
      </details>

      <details class="config-disclosure">
        <summary class="config-disclosure-summary">
          <span class="disclosure-icon"><van-icon name="setting-o" size="17" /></span>
          <span class="disclosure-copy">
            <strong>配置文件目录</strong>
            <small>{{ selectedConfigDir || runtimeConfigDir || '正在读取当前配置目录' }}</small>
          </span>
          <van-icon name="arrow" size="16" class="disclosure-chevron" />
        </summary>
        <div class="disclosure-body">
          <p class="disclosure-note">会迁移 server_config.json 与 third_party_config.json，并在保存后自动重启后端。</p>
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
        </div>
      </details>
    </section>

    <div class="action-area">
      <van-button type="danger" block round @click="confirmReset">
        重置为默认设置
      </van-button>
    </div>

    <div class="mmmtttt-config">github@Mmmtttt</div>

    <Teleport to="body">
      <div
        v-if="activeDropdown"
        class="select-dropdown-overlay"
        :style="dropdownStyle"
        @click.stop
      >
        <div
          v-for="opt in activeDropdownColumns"
          :key="opt.value"
          class="select-option"
          :class="{ active: activeDropdownValue === opt.value }"
          @click="onDropdownSelect(opt.value)"
        >{{ opt.text }}</div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
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
const debugModeValue = ref(false)
const pageSizeOptions = [20, 40, 60]

const activeDropdown = ref('')
const dropdownPos = ref({ top: 0, left: 0, width: 0 })

const dropdownStyle = computed(() => ({
  top: `${dropdownPos.value.top}px`,
  left: `${dropdownPos.value.left}px`,
  minWidth: `${dropdownPos.value.width}px`,
}))

const pageModeColumns = [
  { text: '上下翻页', value: 'up_down' },
  { text: '左→右翻页', value: 'left_right' },
  { text: '右→左翻页', value: 'left_right_reversed' },
]

const pageSizeColumns = pageSizeOptions.map(s => ({ text: `每页 ${s} 条`, value: s }))

const backgroundColumns = [
  { text: '白色背景', value: 'white' },
  { text: '深色背景', value: 'dark' },
  { text: '护眼色背景', value: 'sepia' },
]

const dropdownColumnMap = {
  pageMode: pageModeColumns,
  pageSize: pageSizeColumns,
  background: backgroundColumns,
}

const pageModeSelection = computed(() => {
  if (pageModeValue.value !== 'left_right') return 'up_down'
  return leftRightReadingReversedValue.value ? 'left_right_reversed' : 'left_right'
})

const dropdownValueMap = computed(() => ({
  pageMode: pageModeSelection.value,
  pageSize: pageSizeValue.value,
  background: backgroundValue.value,
}))

const activeDropdownColumns = computed(() => dropdownColumnMap[activeDropdown.value] || [])
const activeDropdownValue = computed(() => dropdownValueMap.value[activeDropdown.value])

const backgroundMap = { white: '白色背景', dark: '深色背景', sepia: '护眼色背景' }

const pageModeLabel = computed(() => {
  const selected = pageModeColumns.find(option => option.value === pageModeSelection.value)
  return selected?.text || '上下翻页'
})
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
const canChangeProjectPassword = computed(() => (
  authStore.authenticated && (authStore.mode === 'normal' || !authStore.enabled)
))

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
  debugModeValue.value = configStore.debugMode
}

function closeAllDropdowns() {
  activeDropdown.value = ''
}

function toggleDropdown(name, event) {
  if (activeDropdown.value === name) {
    activeDropdown.value = ''
    return
  }
  const rect = event.currentTarget.getBoundingClientRect()
  dropdownPos.value = {
    top: rect.bottom + 4,
    left: rect.right - 140,
    width: rect.width,
  }
  activeDropdown.value = name
}

async function onDropdownSelect(value) {
  const name = activeDropdown.value
  activeDropdown.value = ''
  if (name === 'pageMode') {
    if (pageModeSelection.value === value) return
    await updateReadingMode(value)
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

function onDocumentClick() {
  activeDropdown.value = ''
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

async function updateReadingMode(value) {
  const reversed = value === 'left_right_reversed'
  pageModeValue.value = value === 'up_down' ? 'up_down' : 'left_right'
  leftRightReadingReversedValue.value = reversed
  configStore.setPageMode(pageModeValue.value)
  configStore.setLeftRightReadingReversed(reversed)
  const ok = await configStore.saveConfigToServer()
  if (!ok) {
    showFailToast('默认翻页模式保存失败')
  }
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

async function updateDebugMode() {
  configStore.updateConfig({ debugMode: debugModeValue.value })
  const ok = await configStore.saveConfigToServer()
  if (!ok) {
    showFailToast('Debug 日志模式保存失败')
    return
  }
  showSuccessToast(debugModeValue.value ? 'Debug 日志已开启' : 'Debug 日志已关闭')
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
    showSuccessToast('项目密码已更新，请重启应用以启用双空间')
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
  try {
    await authStore.checkStatus()
  } catch {
    // The router already handles unavailable startup status; keep settings usable when it recovers.
  }
  await configStore.loadConfigFromServer()
  initValues()
  await Promise.all([loadSystemConfig(), loadConfigDirInfo()])
  document.addEventListener('click', onDocumentClick)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
})
</script>

<style scoped>
.system-config {
  width: min(100%, 1080px);
  min-height: 95vh;
  margin: 0 auto;
  background: transparent;
  padding: 0 var(--page-gutter) calc(28px + env(safe-area-inset-bottom, 0px));
}

.settings-section {
  margin: 0 0 22px;
}

.settings-section--compact {
  margin-bottom: 24px;
}

.settings-section--advanced {
  margin-top: 28px;
}

.section-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  margin: 0 4px 10px;
}

.section-heading h2 {
  margin: 3px 0 0;
  color: var(--text-strong);
  font-size: 18px;
  line-height: 1.2;
  letter-spacing: -0.02em;
}

.section-kicker {
  display: block;
  color: var(--brand-600);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.section-note {
  padding-bottom: 2px;
  color: var(--text-tertiary);
  font-size: 12px;
  white-space: nowrap;
}

.config-group {
  margin: 0;
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

.settings-card :deep(.van-cell) {
  min-height: 58px;
  padding: 12px 16px;
}

.settings-card :deep(.van-cell__title) {
  min-width: 0;
}

.settings-card :deep(.van-cell__value) {
  flex: 0 0 auto;
}

.settings-card :deep(.van-cell__label) {
  max-width: 700px;
  margin-top: 4px;
  color: var(--text-tertiary);
  line-height: 1.5;
}

.mode-status-cell :deep(.van-cell__title) {
  color: var(--text-tertiary);
  font-size: 12px;
}

.select-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 68px;
  padding: 12px 16px;
  cursor: pointer;
  position: relative;
  background: transparent;
  transition: background var(--motion-fast) var(--ease-standard);
}

.select-row:hover {
  background: var(--brand-soft, rgba(89, 160, 255, 0.08));
}

.setting-copy {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.select-label {
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.35;
}

.setting-description {
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.45;
}

.select-value {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 4px;
  color: var(--text-secondary);
  font-size: 14px;
  white-space: nowrap;
}

.config-disclosure {
  margin: 0 0 10px;
  overflow: hidden;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.config-disclosure-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 70px;
  padding: 12px 16px;
  cursor: pointer;
  list-style: none;
  transition: background var(--motion-fast) var(--ease-standard);
}

.config-disclosure-summary::-webkit-details-marker {
  display: none;
}

.config-disclosure-summary:hover {
  background: var(--brand-soft, rgba(89, 160, 255, 0.08));
}

.disclosure-icon {
  display: inline-flex;
  flex: 0 0 34px;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 1px solid rgba(89, 160, 255, 0.24);
  border-radius: 11px;
  color: var(--brand-600);
  background: var(--brand-soft, rgba(89, 160, 255, 0.1));
}

.disclosure-copy {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 4px;
}

.disclosure-copy strong {
  overflow: hidden;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.disclosure-copy small {
  overflow: hidden;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.disclosure-chevron {
  flex: 0 0 auto;
  color: var(--text-tertiary);
  transition: transform var(--motion-base) var(--ease-standard);
}

details[open] .disclosure-chevron {
  transform: rotate(90deg);
  color: var(--brand-600);
}

.disclosure-body {
  border-top: 1px solid var(--border-soft);
  padding: 4px 0 2px;
}

.disclosure-note {
  margin: 10px 16px 4px;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.6;
}

.disclosure-body :deep(.van-field) {
  background: transparent;
}

.path-summary-grid {
  display: grid;
  gap: 10px;
  padding: 10px 16px 6px;
}

.path-summary-card {
  display: grid;
  gap: 6px;
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  background: var(--surface-1);
}

.path-summary-card.emphasis {
  border-color: rgba(47, 116, 255, 0.3);
  background: rgba(89, 160, 255, 0.08);
}

.path-summary-label {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.path-summary-value {
  overflow-wrap: anywhere;
  color: var(--text-primary);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.path-summary-meta {
  color: var(--text-tertiary);
  font-size: 12px;
}

.inline-actions {
  display: grid;
  grid-template-columns: 1fr;
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
  padding: 16px;
  color: var(--text-tertiary);
  font-size: 12px;
  text-align: center;
}

.action-area {
  padding: 16px 0 10px;
}

.settings-mode-switch {
  transform: scale(0.78);
  transform-origin: right center;
}

@media (min-width: 1024px) {
  .system-config {
    padding-inline: 24px;
  }
}

@media (max-width: 767px) {
  .system-config {
    padding-inline: 10px;
  }

  .section-heading {
    margin-inline: 2px;
  }

  .section-heading h2 {
    font-size: 17px;
  }

  .section-note {
    font-size: 11px;
  }

  .config-group,
  .config-disclosure {
    border-radius: 16px;
  }

  .config-disclosure-summary {
    min-height: 66px;
    padding-inline: 13px;
  }

  .disclosure-copy small {
    max-width: calc(100vw - 112px);
  }

  .select-row {
    min-height: 64px;
    padding-inline: 14px;
  }

  .select-value {
    font-size: 13px;
  }
}
</style>

<style>
.select-dropdown-overlay {
  position: fixed;
  z-index: 3000;
  background: var(--popup-bg, #fff);
  border: 1px solid var(--border-soft, rgba(0, 0, 0, 0.08));
  border-radius: 14px;
  box-shadow: var(--shadow-md, 0 8px 24px rgba(0, 0, 0, 0.15));
  overflow: hidden;
  backdrop-filter: blur(12px);
}

.select-dropdown-overlay .select-option {
  padding: 10px 16px;
  font-size: 14px;
  color: var(--text-primary, #333);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.select-dropdown-overlay .select-option:hover {
  background: rgba(47, 116, 255, 0.08);
}

.select-dropdown-overlay .select-option.active {
  color: var(--brand-600, #1989fa);
  font-weight: 600;
  background: rgba(89, 160, 255, 0.12);
}
</style>

