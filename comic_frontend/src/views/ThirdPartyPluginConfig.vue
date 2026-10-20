<template>
  <div class="plugin-config-page desktop-page-shell">
    <van-nav-bar :title="navTitle" left-text="返回" left-arrow @click-left="goBack" />

    <div v-if="loading" class="page-loading">
      <van-loading size="22px" vertical>正在加载插件配置…</van-loading>
    </div>

    <van-empty v-else-if="!row" description="插件不存在或尚未加载" />

    <template v-else>
      <div class="plugin-summary">
        <div class="summary-main">
          <div class="summary-title">{{ row.label }}</div>
          <div class="summary-meta">{{ summaryMeta }}</div>
        </div>
        <span v-if="row.hasEnabled" class="status-pill" :class="{ 'is-on': row.enabled }">
          {{ row.enabled ? '已启用' : '未启用' }}
        </span>
        <span v-else class="status-pill is-muted">无启用开关</span>
      </div>

      <div class="section-head">
        <span class="section-title">插件配置</span>
        <span class="section-hint">启用开关在插件列表里即时生效</span>
      </div>

      <van-cell-group v-if="editableFields.length > 0" inset>
        <template v-for="field in editableFields" :key="field.key">
          <van-cell v-if="field.type === 'boolean'" :title="field.label">
            <template #right-icon>
              <van-switch v-model="form[field.key]" />
            </template>
          </van-cell>

          <van-field
            v-else-if="field.type === 'textarea'"
            v-model="form[field.key]"
            type="textarea"
            autosize
            :label="field.label"
            :placeholder="field.placeholder || ''"
          />

          <van-field
            v-else
            v-model="form[field.key]"
            :type="field.type === 'password' ? 'password' : (field.type === 'number' ? 'number' : 'text')"
            :label="field.label"
            :placeholder="field.placeholder || ''"
          />
        </template>
      </van-cell-group>

      <div v-else class="no-fields">
        <van-empty image-size="72" description="该插件没有可编辑的配置项" />
      </div>

      <div v-if="row.actions.length > 0" class="action-list">
        <div
          v-for="action in row.actions"
          :key="action.key || action.label"
          class="action-card"
        >
          <div v-if="action.description" class="action-text">{{ action.description }}</div>
          <van-button plain type="primary" block @click="runAction(action)">
            {{ action.label || action.key || '执行动作' }}
          </van-button>
        </div>
      </div>

      <div v-if="editableFields.length > 0" class="save-area">
        <van-button
          type="primary"
          block
          round
          :loading="store.isConfigSaving(row.key)"
          @click="saveConfig"
        >
          保存配置
        </van-button>
      </div>

      <div v-if="row.extension" class="extension-area">
        <div class="section-head">
          <span class="section-title">扩展管理</span>
          <span class="section-hint">操作在重启应用后生效</span>
        </div>
        <div class="extension-card">
          <div class="extension-meta">{{ extensionMeta }}</div>
          <div class="extension-actions">
            <van-button
              v-if="row.canUpdate"
              plain
              type="primary"
              block
              :loading="extensionBusy"
              @click="updatePlugin"
            >
              更新插件
            </van-button>
            <van-button
              plain
              type="danger"
              block
              :loading="extensionBusy"
              @click="deletePlugin"
            >
              删除插件
            </van-button>
          </div>
          <p class="extension-hint">
            更新与删除只处理扩展代码；已保存的平台配置与安装链接会保留。
          </p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showFailToast } from 'vant'

import { useThirdPartyStore } from '@/stores/thirdParty'
import { openExternalUrl } from '@/runtime/browser'
import { resolveBackendApiUrl } from '@/runtime/endpoint'

const store = useThirdPartyStore()
const route = useRoute()
const router = useRouter()

const pluginKey = computed(() => String(route.params.pluginKey || ''))
const row = computed(() => store.rowForConfigKey(pluginKey.value))
const loading = computed(() => !store.loaded && store.loading)
const form = ref({})

const navTitle = computed(() => row.value?.label || '插件配置')

const editableFields = computed(() => {
  const current = row.value
  if (!current) return []
  return current.fields.filter((field) => {
    return !(current.hasEnabled && String(field?.key || '') === current.enabledField)
  })
})

const summaryMeta = computed(() => {
  const current = row.value
  if (!current) return ''
  const parts = []
  if (current.version) parts.push(`v${current.version}`)
  parts.push(sourceText(current.sourceType))
  if (current.pluginId) parts.push(current.pluginId)
  return parts.join(' · ')
})

const extensionMeta = computed(() => {
  const current = row.value
  if (!current?.extension) return ''
  const parts = [`来源 ${sourceText(current.sourceType)}`]
  if (current.version) parts.push(`版本 ${current.version}`)
  if (current.extension.directory) parts.push(`目录 ${current.extension.directory}`)
  return parts.join(' · ')
})

const extensionBusy = computed(() => {
  const pluginId = row.value?.pluginId
  return pluginId ? store.isExtensionBusy(pluginId) : false
})

function sourceText(sourceType) {
  if (sourceType === 'gist') return 'Gist 安装'
  if (sourceType === 'github') return 'GitHub 安装'
  return '内置插件'
}

function resetForm() {
  form.value = store.buildFieldForm(row.value)
}

watch([() => row.value?.key || '', () => store.loaded], resetForm, { immediate: true })

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push({ name: 'ThirdPartyConfig' })
}

async function saveConfig() {
  if (!row.value) return
  await store.savePluginConfig(row.value.key, { ...form.value })
}

function updatePlugin() {
  const pluginId = row.value?.pluginId
  if (!pluginId) return
  store.reinstallExtension(pluginId)
}

function deletePlugin() {
  const pluginId = row.value?.pluginId
  if (!pluginId) return
  store.deleteExtension(pluginId)
}

function runAction(action) {
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
  store.loadConfig()
})
</script>

<style scoped>
.plugin-config-page {
  min-height: 95vh;
  background: transparent;
  padding-bottom: 28px;
}

.page-loading {
  display: flex;
  justify-content: center;
  padding: 60px 0;
  color: var(--text-secondary);
}

.plugin-summary {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 14px 16px 4px;
  padding: 18px 20px;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.summary-main {
  min-width: 0;
  flex: 1;
}

.summary-title {
  font-size: 17px;
  font-weight: 650;
  color: var(--text-strong);
  letter-spacing: 0.01em;
}

.summary-meta {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-tertiary);
  word-break: break-all;
}

.status-pill {
  flex: none;
  padding: 5px 12px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1;
  color: var(--text-tertiary);
  background: rgba(139, 152, 173, 0.14);
}

.status-pill.is-on {
  color: var(--success-500);
  background: rgba(0, 168, 117, 0.12);
}

.status-pill.is-muted {
  color: var(--text-tertiary);
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 24px 8px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.01em;
}

.section-hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

.plugin-config-page :deep(.van-cell-group) {
  margin: 0 16px;
  overflow: hidden;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.no-fields {
  padding: 10px 0;
}

.action-list {
  margin: 14px 16px 0;
  display: grid;
  gap: 10px;
}

.action-card {
  padding: 14px;
  border-radius: 16px;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  box-shadow: var(--shadow-xs);
}

.action-text {
  margin-bottom: 10px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.save-area {
  padding: 18px 16px 4px;
}

.extension-area {
  margin-top: 6px;
}

.extension-card {
  margin: 0 16px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--border-soft);
  background: var(--surface-2);
  box-shadow: var(--shadow-xs);
}

.extension-meta {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
  word-break: break-all;
}

.extension-actions {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.extension-hint {
  margin: 12px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-tertiary);
}

@media (max-width: 767px) {
  .plugin-summary,
  .plugin-config-page :deep(.van-cell-group),
  .action-list,
  .extension-card {
    margin-inline: 10px;
  }

  .section-head {
    padding-inline: 16px;
  }

  .save-area {
    padding-inline: 10px;
  }
}
</style>
