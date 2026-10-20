<template>
  <div class="third-party-page desktop-page-shell">
    <van-nav-bar title="第三方平台配置" left-text="返回" left-arrow @click-left="$router.back()" />

    <div class="panel">
      <van-cell-group inset>
        <van-cell
          title="安装扩展包"
          label="安装本地 .zip，或从 GitHub 仓库 / Gist 安装；安装后需要重启应用才会生效"
        />
        <van-cell title="本地扩展包">
          <template #right-icon>
            <van-button
              size="small"
              type="primary"
              :loading="store.installingPackage"
              @click="selectExtensionPackage"
            >
              选择 .zip
            </van-button>
          </template>
        </van-cell>
        <van-field
          v-model="githubExtensionUrl"
          label="仓库 / Gist"
          placeholder="仓库地址或 Gist 链接"
          clearable
        >
          <template #button>
            <van-button
              size="small"
              type="primary"
              :loading="store.installingGithub"
              @click="installGithubExtension"
            >
              安装
            </van-button>
          </template>
        </van-field>
        <van-cell
          v-for="item in store.savedExtensionSources"
          :key="`source-${item.plugin_id}`"
          :title="item.plugin_id"
          :label="sourceLabel(item)"
        >
          <template #right-icon>
            <van-button
              size="small"
              type="primary"
              :loading="store.isExtensionBusy(item.plugin_id)"
              @click="store.reinstallExtension(item.plugin_id)"
            >
              安装
            </van-button>
          </template>
        </van-cell>
      </van-cell-group>
      <input
        ref="extensionFileInput"
        class="extension-file-input"
        type="file"
        accept=".zip,application/zip"
        @change="installSelectedExtension"
      />
    </div>

    <div class="panel">
      <div class="section-head">
        <span class="section-title">插件</span>
        <span class="section-hint">开关即时生效 · 点条目进配置</span>
      </div>
      <div v-if="!store.loaded && store.loading" class="panel-loading">
        <van-loading size="20px">正在加载插件…</van-loading>
      </div>
      <van-cell-group v-else-if="store.pluginRows.length > 0" inset>
        <van-cell
          v-for="row in store.pluginRows"
          :key="row.key"
          :title="row.label"
          :label="pluginMeta(row)"
          is-link
          center
          class="plugin-cell"
          @click="openPlugin(row)"
        >
          <template #right-icon>
            <span class="plugin-trailing">
              <span class="plugin-switch" @click.stop>
                <van-switch
                  v-if="row.hasEnabled"
                  :model-value="row.enabled"
                  :loading="store.isEnabledSaving(row.key)"
                  size="20px"
                  @update:model-value="togglePlugin(row, $event)"
                />
              </span>
              <van-icon name="arrow" class="plugin-arrow" />
            </span>
          </template>
        </van-cell>
      </van-cell-group>
      <van-empty v-else description="暂无可配置的第三方平台" />
    </div>

    <div v-if="store.pendingExtensions.length > 0" class="panel">
      <div class="section-head">
        <span class="section-title">待重启生效</span>
        <span class="section-hint">已安装，当前进程尚未加载</span>
      </div>
      <van-cell-group inset>
        <van-cell
          v-for="item in store.pendingExtensions"
          :key="item.plugin_id"
          :title="item.name || item.plugin_id"
          :label="pendingLabel(item)"
        >
          <template #right-icon>
            <div class="pending-actions" @click.stop>
              <van-button
                v-if="item.source?.url"
                size="mini"
                plain
                type="primary"
                :loading="store.isExtensionBusy(item.plugin_id)"
                @click="store.reinstallExtension(item.plugin_id)"
              >
                更新
              </van-button>
              <van-button
                size="mini"
                plain
                type="danger"
                icon="cross"
                title="删除"
                :loading="store.isExtensionBusy(item.plugin_id)"
                @click="store.deleteExtension(item.plugin_id)"
              />
            </div>
          </template>
        </van-cell>
      </van-cell-group>
    </div>

    <div class="panel">
      <div class="section-head">
        <span class="section-title">隐私空间可用范围</span>
      </div>
      <van-cell-group inset>
        <van-cell
          title="插件代码和配置仍由正常空间统一管理"
          label="这里只控制哪些插件允许在隐私空间参与搜索、导入和播放。"
        />
        <van-cell
          v-for="plugin in store.authorizablePlugins"
          :key="plugin.plugin_id"
          :title="plugin.name || plugin.plugin_id"
          :label="plugin.plugin_id"
        >
          <template #right-icon>
            <van-switch
              :model-value="store.isPrivatePluginEnabled(plugin.plugin_id)"
              @update:model-value="store.setPrivatePluginEnabled(plugin.plugin_id, $event)"
            />
          </template>
        </van-cell>
        <div class="space-access-save">
          <van-button
            type="primary"
            block
            round
            :loading="store.savingSpaceAccess"
            :disabled="store.authorizablePlugins.length === 0"
            @click="store.saveSpaceAccess()"
          >
            保存隐私空间授权
          </van-button>
        </div>
      </van-cell-group>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useThirdPartyStore } from '@/stores/thirdParty'

const store = useThirdPartyStore()
const router = useRouter()

const extensionFileInput = ref(null)
const githubExtensionUrl = ref('')

function pluginMeta(row) {
  const parts = []
  if (row.version) parts.push(`v${row.version}`)
  if (row.sourceType === 'gist') parts.push('Gist 安装')
  else if (row.sourceType === 'github') parts.push('GitHub 安装')
  else parts.push('内置')
  if (row.pluginId) parts.push(row.pluginId)
  return parts.join(' · ')
}

function pendingLabel(item) {
  const parts = []
  if (item?.version) parts.push(`v${item.version}`)
  parts.push('重启应用后生效')
  return parts.join(' · ')
}

function sourceLabel(item) {
  if (item?.type === 'gist') return 'Gist 扩展来源'
  const repo = [item?.owner, item?.repo].filter(Boolean).join('/')
  if (repo) return `GitHub · ${repo}`
  return '已保存安装来源'
}

function selectExtensionPackage() {
  extensionFileInput.value?.click()
}

async function installSelectedExtension(event) {
  const file = event?.target?.files?.[0]
  if (!file) return
  await store.installExtensionPackage(file)
  if (event?.target) {
    event.target.value = ''
  }
}

async function installGithubExtension() {
  const installed = await store.installExtensionFromGithub(githubExtensionUrl.value)
  if (installed) githubExtensionUrl.value = ''
}

function openPlugin(row) {
  if (!row?.key) return
  router.push({ name: 'ThirdPartyPluginConfig', params: { pluginKey: row.key } })
}

function togglePlugin(row, nextEnabled) {
  store.setPluginEnabled(row, nextEnabled)
}

onMounted(() => {
  store.loadConfig()
})
</script>

<style scoped>
.third-party-page {
  min-height: 95vh;
  min-height: 95dvh;
  background: transparent;
  padding-bottom: 24px;
}

.panel {
  padding: 10px 0 2px;
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 24px 8px;
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

.panel :deep(.van-cell-group) {
  margin: 0 16px;
  overflow: hidden;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.plugin-cell :deep(.van-cell__title) {
  min-width: 0;
}

.plugin-cell :deep(.van-cell__label) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.plugin-trailing {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.plugin-switch {
  display: inline-flex;
  align-items: center;
}

.plugin-arrow {
  font-size: 14px;
  color: var(--text-tertiary);
}

.pending-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}

.panel-loading {
  display: flex;
  justify-content: center;
  padding: 26px 0;
  color: var(--text-secondary);
}

.extension-file-input {
  display: none;
}

.space-access-save {
  padding: 12px 16px 16px;
}

@media (max-width: 767px) {
  .panel :deep(.van-cell-group) {
    margin-inline: 10px;
  }

  .section-head {
    padding-inline: 16px;
  }
}
</style>
