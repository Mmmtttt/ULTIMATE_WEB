<template>
  <div class="third-party-page desktop-page-shell">
    <van-nav-bar title="第三方平台配置" left-text="返回" left-arrow @click-left="$router.back()" />

    <div class="extension-panel">
      <van-cell-group inset>
        <van-cell title="扩展包" label="安装本地 .zip 扩展包，安装后需要重启应用才会生效">
          <template #right-icon>
            <van-button size="small" type="primary" :loading="installingExtension" @click="selectExtensionPackage">
              安装
            </van-button>
          </template>
        </van-cell>
        <van-field
          v-model="githubExtensionUrl"
          label="GitHub"
          placeholder="https://github.com/owner/repo"
          clearable
        >
          <template #button>
            <van-button size="small" type="primary" :loading="installingGithubExtension" @click="installGithubExtension">
              安装
            </van-button>
          </template>
        </van-field>
        <van-cell
          v-for="item in installedExtensions"
          :key="item.plugin_id || item.directory"
          :title="item.name || item.plugin_id || item.directory"
          :label="extensionLabel(item)"
        >
          <template #right-icon>
            <div class="extension-actions">
              <van-button
                v-if="item.source?.url"
                size="mini"
                plain
                type="primary"
                :loading="Boolean(extensionActionMap[item.plugin_id])"
                @click="reinstallExtension(item.plugin_id)"
              >
                更新
              </van-button>
              <van-button
                size="mini"
                plain
                type="danger"
                :loading="Boolean(extensionActionMap[item.plugin_id])"
                @click="deleteExtension(item.plugin_id)"
              >
                删除
              </van-button>
            </div>
          </template>
        </van-cell>
        <van-cell
          v-for="item in savedExtensionSources"
          :key="`source-${item.plugin_id}`"
          :title="item.plugin_id"
          :label="sourceLabel(item)"
        >
          <template #right-icon>
            <van-button
              size="small"
              type="primary"
              :loading="Boolean(extensionActionMap[item.plugin_id])"
              @click="reinstallExtension(item.plugin_id)"
            >
              安装
            </van-button>
          </template>
        </van-cell>
        <van-cell v-if="installedExtensions.length === 0 && savedExtensionSources.length === 0" title="未安装扩展" label="集成模式下可能已内置平台；扩展模式下可从这里安装" />
      </van-cell-group>
      <input
        ref="extensionFileInput"
        class="extension-file-input"
        type="file"
        accept=".zip,application/zip"
        @change="installSelectedExtension"
      />
    </div>

    <div v-if="displayAdapters.length === 0" class="empty-hint">
      <van-empty description="暂无可配置的第三方平台" />
    </div>

    <van-tabs v-else v-model:active="activeAdapter" animated>
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

          <div class="save-area">
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
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'

import { comicApi } from '@/api/comic'
import { openExternalUrl } from '@/runtime/browser'
import { resolveBackendApiUrl } from '@/runtime/endpoint'

const savingAdapterMap = ref({})
const activeAdapter = ref('')

const thirdPartySchema = ref({})
const thirdPartyAdapters = ref({})
const thirdPartyAdapterOrder = ref([])
const adapterForms = ref({})
const extensionFileInput = ref(null)
const installingExtension = ref(false)
const installingGithubExtension = ref(false)
const githubExtensionUrl = ref('')
const extensionState = ref({ installed: [] })
const extensionActionMap = ref({})

const installedExtensions = computed(() => {
  return Array.isArray(extensionState.value?.installed) ? extensionState.value.installed : []
})

const savedExtensionSources = computed(() => {
  const sources = Array.isArray(extensionState.value?.saved_sources) ? extensionState.value.saved_sources : []
  const installedIds = new Set(installedExtensions.value.map((item) => item.plugin_id).filter(Boolean))
  return sources.filter((item) => item?.plugin_id && !installedIds.has(item.plugin_id))
})

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
    forms[adapterName] = { ...source }

    adapterFields(adapterName).forEach((field) => {
      if (forms[adapterName][field.key] === undefined || forms[adapterName][field.key] === null) {
        forms[adapterName][field.key] = field.type === 'boolean' ? false : ''
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
    if (response.code !== 200) return

    const data = response.data || {}
    thirdPartySchema.value = data.schema || {}
    thirdPartyAdapterOrder.value = data.config_order || data.adapter_order || []
    thirdPartyAdapters.value = data.adapters || {}
    extensionState.value = data.extensions || { installed: [] }
    ensureAdapterFormShape()
  } catch (error) {
    showFailToast(error?.message || '加载第三方配置失败')
  }
}

function extensionLabel(item) {
  const version = item?.version ? `版本 ${item.version}` : ''
  const directory = item?.directory ? `目录 ${item.directory}` : ''
  const source = item?.source?.url ? `来源 ${item.source.url}` : ''
  return [version, directory, source].filter(Boolean).join(' · ') || '重启后生效'
}

function sourceLabel(item) {
  return item?.url || [item?.owner, item?.repo].filter(Boolean).join('/') || '已保存安装来源'
}

function selectExtensionPackage() {
  extensionFileInput.value?.click()
}

async function installSelectedExtension(event) {
  const file = event?.target?.files?.[0]
  if (!file) return
  installingExtension.value = true
  try {
    const response = await comicApi.installThirdPartyExtension(file)
    if (response.code === 200) {
      showSuccessToast(response.data?.message || '扩展安装成功，重启后生效')
      await loadThirdPartyConfig()
    } else {
      showFailToast(response.msg || '扩展安装失败')
    }
  } catch (error) {
    showFailToast(error?.message || '扩展安装失败')
  } finally {
    installingExtension.value = false
    if (event?.target) {
      event.target.value = ''
    }
  }
}

async function installGithubExtension() {
  const url = githubExtensionUrl.value.trim()
  if (!url) {
    showFailToast('请输入 GitHub 仓库链接')
    return
  }
  installingGithubExtension.value = true
  try {
    const response = await comicApi.installThirdPartyExtensionFromGithub(url)
    if (response.code === 200) {
      showSuccessToast(response.data?.message || '扩展安装成功，重启后生效')
      githubExtensionUrl.value = ''
      await loadThirdPartyConfig()
    } else {
      showFailToast(response.msg || '扩展安装失败')
    }
  } catch (error) {
    showFailToast(error?.message || '扩展安装失败')
  } finally {
    installingGithubExtension.value = false
  }
}

function setExtensionAction(pluginId, loading) {
  extensionActionMap.value = { ...extensionActionMap.value, [pluginId]: loading }
}

async function reinstallExtension(pluginId) {
  if (!pluginId) return
  setExtensionAction(pluginId, true)
  try {
    const response = await comicApi.reinstallThirdPartyExtension(pluginId)
    if (response.code === 200) {
      showSuccessToast(response.data?.message || '扩展安装成功，重启后生效')
      await loadThirdPartyConfig()
    } else {
      showFailToast(response.msg || '扩展安装失败')
    }
  } catch (error) {
    showFailToast(error?.message || '扩展安装失败')
  } finally {
    setExtensionAction(pluginId, false)
  }
}

async function deleteExtension(pluginId) {
  if (!pluginId) return
  try {
    await showConfirmDialog({
      title: '删除扩展代码',
      message: '只会删除扩展代码，已保存的安装链接和平台配置会保留。删除后需要重启应用才会生效。'
    })
  } catch {
    return
  }
  setExtensionAction(pluginId, true)
  try {
    const response = await comicApi.deleteThirdPartyExtension(pluginId)
    if (response.code === 200) {
      showSuccessToast(response.data?.message || '扩展代码已删除，重启后生效')
      await loadThirdPartyConfig()
    } else {
      showFailToast(response.msg || '删除扩展失败')
    }
  } catch (error) {
    showFailToast(error?.message || '删除扩展失败')
  } finally {
    setExtensionAction(pluginId, false)
  }
}

async function saveAdapterConfig(adapterName) {
  const form = adapterForms.value?.[adapterName]
  if (!form) {
    showFailToast('配置数据为空')
    return
  }

  savingAdapterMap.value = { ...savingAdapterMap.value, [adapterName]: true }

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

    const response = await comicApi.saveThirdPartyConfig({ adapter: adapterName, config: payload })
    if (response.code === 200) {
      showSuccessToast(`${adapterLabel(adapterName)} 配置已保存`)
      await loadThirdPartyConfig()
    } else {
      showFailToast(response.msg || '保存失败')
    }
  } catch (error) {
    showFailToast(error?.message || '保存失败')
  } finally {
    savingAdapterMap.value = { ...savingAdapterMap.value, [adapterName]: false }
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

onMounted(() => {
  loadThirdPartyConfig()
})
</script>

<style scoped>
.third-party-page {
  min-height: 95vh;
  background: transparent;
  padding-bottom: 24px;
}

.empty-hint {
  padding-top: 60px;
}

.extension-panel {
  padding: 12px 0 4px;
}

.extension-panel :deep(.van-cell-group) {
  margin: 0 16px;
  overflow: hidden;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.extension-file-input {
  display: none;
}

.extension-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}

.adapter-panel {
  padding: 12px 0 20px;
}

.adapter-panel :deep(.van-cell-group) {
  margin: 0 16px;
  overflow: hidden;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.adapter-panel :deep(.van-cell),
.adapter-panel :deep(.van-field) {
  background: transparent;
}

.adapter-actions {
  margin: 12px 16px 0;
  display: grid;
  gap: 10px;
}

.adapter-action-card {
  padding: 14px;
  border-radius: 16px;
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

.save-area {
  padding: 16px;
}

@media (max-width: 767px) {
  .adapter-panel :deep(.van-cell-group),
  .adapter-actions {
    margin-inline: 10px;
  }

  .save-area {
    padding-inline: 10px;
  }
}
</style>
