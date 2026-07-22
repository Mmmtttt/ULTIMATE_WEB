<template>
  <div class="third-party-page desktop-page-shell">
    <van-nav-bar title="第三方平台配置" left-text="返回" left-arrow @click-left="$router.back()" />

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
import { showFailToast, showSuccessToast } from 'vant'

import { comicApi } from '@/api/comic'
import { openExternalUrl } from '@/runtime/browser'
import { resolveBackendApiUrl } from '@/runtime/endpoint'

const savingAdapterMap = ref({})
const activeAdapter = ref('')

const thirdPartySchema = ref({})
const thirdPartyAdapters = ref({})
const thirdPartyAdapterOrder = ref([])
const adapterForms = ref({})

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
    ensureAdapterFormShape()
  } catch (error) {
    showFailToast(error?.message || '加载第三方配置失败')
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

.adapter-panel {
  padding: 12px 0 20px;
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

.save-area {
  padding: 16px;
}
</style>
