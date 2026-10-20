import { defineStore } from 'pinia'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'

import { comicApi } from '@/api/comic'

const DEFAULT_ENABLED_FIELD = 'enabled'

function normalizeExtensionState(raw) {
  return {
    installed: Array.isArray(raw?.installed) ? raw.installed : [],
    saved_sources: Array.isArray(raw?.saved_sources) ? raw.saved_sources : []
  }
}

function normalizeFieldValue(field, value) {
  if (value !== undefined && value !== null) return value
  if (field?.type === 'boolean') return Boolean(field?.default)
  if (field?.default !== undefined) return field.default
  return ''
}

function coerceFieldPayload(fields, payload) {
  const next = { ...payload }
  ;(fields || []).forEach((field) => {
    if (field?.type !== 'number') return
    const value = next[field.key]
    if (value === '' || value === null || value === undefined) return
    const num = Number(value)
    next[field.key] = Number.isFinite(num) ? num : value
  })
  return next
}

/**
 * 第三方插件配置：列表页与单个插件配置页共用同一份数据。
 * 启用开关在列表条目上即时生效（不再依赖「保存配置」）。
 */
export const useThirdPartyStore = defineStore('thirdParty', {
  state: () => ({
    loaded: false,
    loading: false,
    loadError: '',

    schema: {},
    configOrder: [],
    adapters: {},
    descriptors: [],
    plugins: [],
    extensions: normalizeExtensionState(null),
    authorizablePlugins: [],
    privateEnabledPluginIds: [],

    enabledSavingMap: {},
    configSavingMap: {},
    extensionActionMap: {},
    installingPackage: false,
    installingGithub: false,
    savingSpaceAccess: false
  }),

  getters: {
    /** 列表条目：配置顺序 × 插件元数据 × 已安装扩展 */
    pluginRows(state) {
      const descriptorByConfigKey = new Map()
      ;[...(state.descriptors || []), ...(state.plugins || [])].forEach((descriptor) => {
        const key = String(descriptor?.config_key || '').trim()
        if (key && !descriptorByConfigKey.has(key)) descriptorByConfigKey.set(key, descriptor)
      })

      const extensionByPluginId = new Map()
      ;(state.extensions.installed || []).forEach((item) => {
        const pluginId = String(item?.plugin_id || '').trim()
        if (pluginId) extensionByPluginId.set(pluginId, item)
      })

      const order = state.configOrder.length > 0
        ? state.configOrder
        : Object.keys(state.schema || {})

      // 已加载但没声明配置字段的插件也要能进条目，否则它的更新/删除入口会丢失。
      const orderedKeys = new Set(order.map((rawKey) => String(rawKey || '').trim()))
      const appendedKeys = []
      ;(state.plugins || []).forEach((descriptor) => {
        const key = String(descriptor?.config_key || '').trim()
        if (key && !orderedKeys.has(key)) {
          orderedKeys.add(key)
          appendedKeys.push(key)
        }
      })

      return [...order, ...appendedKeys].map((rawKey) => {
        const key = String(rawKey || '').trim()
        const schemaEntry = state.schema?.[key] || {}
        const fields = Array.isArray(schemaEntry.fields) ? schemaEntry.fields : []
        const descriptor = descriptorByConfigKey.get(key) || {}
        const pluginId = String(descriptor.plugin_id || '').trim()
        const extension = pluginId ? extensionByPluginId.get(pluginId) : null
        const enabledField = String(schemaEntry.enabled_field || DEFAULT_ENABLED_FIELD)
        const config = state.adapters?.[key] || {}
        return {
          key,
          label: String(schemaEntry.label || descriptor.name || key),
          pluginId,
          version: String(extension?.version || descriptor.version || ''),
          extension,
          sourceType: String(extension?.source?.type || ''),
          canUpdate: Boolean(extension?.source?.url),
          fields,
          actions: Array.isArray(schemaEntry.actions) ? schemaEntry.actions : [],
          enabledField,
          hasEnabled: fields.some((field) => String(field?.key || '') === enabledField),
          enabled: Boolean(config?.[enabledField]),
          config
        }
      })
    },

    /** 已安装、但本次进程还没加载进注册表的扩展（通常是在等重启） */
    pendingExtensions(state) {
      const known = new Set()
      ;[...(state.descriptors || []), ...(state.plugins || [])].forEach((descriptor) => {
        const pluginId = String(descriptor?.plugin_id || '').trim()
        if (pluginId) known.add(pluginId)
      })
      return (state.extensions.installed || []).filter((item) => {
        const pluginId = String(item?.plugin_id || '').trim()
        return pluginId && !known.has(pluginId)
      })
    },

    savedExtensionSources(state) {
      const sources = state.extensions.saved_sources || []
      const installedIds = new Set(
        (state.extensions.installed || []).map((item) => item?.plugin_id).filter(Boolean)
      )
      return sources.filter((item) => item?.plugin_id && !installedIds.has(item.plugin_id))
    }
  },

  actions: {
    rowForConfigKey(configKey) {
      const key = String(configKey || '').trim()
      return this.pluginRows.find((row) => row.key === key) || null
    },

    isEnabledSaving(configKey) {
      return Boolean(this.enabledSavingMap?.[configKey])
    },

    isConfigSaving(configKey) {
      return Boolean(this.configSavingMap?.[configKey])
    },

    isExtensionBusy(pluginId) {
      return Boolean(this.extensionActionMap?.[pluginId])
    },

    async loadConfig(force = false) {
      if (this.loading) return
      if (this.loaded && !force) return
      this.loading = true
      this.loadError = ''
      try {
        const response = await comicApi.getThirdPartyConfig()
        if (response.code !== 200) {
          throw new Error(response.msg || '加载第三方配置失败')
        }
        const data = response.data || {}
        this.schema = data.schema || {}
        this.configOrder = Array.isArray(data.config_order)
          ? data.config_order
          : (Array.isArray(data.adapter_order) ? data.adapter_order : [])
        this.adapters = data.adapters || {}
        this.descriptors = Array.isArray(data.configurable_plugins) ? data.configurable_plugins : []
        this.plugins = Array.isArray(data.plugins) ? data.plugins : []
        this.extensions = normalizeExtensionState(data.extensions)
        this.authorizablePlugins = Array.isArray(data.authorizable_plugins)
          ? data.authorizable_plugins
          : (Array.isArray(data.plugins) ? data.plugins : [])
        this.privateEnabledPluginIds = Array.isArray(data.space_access?.private_enabled_plugin_ids)
          ? [...data.space_access.private_enabled_plugin_ids]
          : []
        this.loaded = true
      } catch (error) {
        this.loadError = error?.message || '加载第三方配置失败'
        showFailToast(this.loadError)
      } finally {
        this.loading = false
      }
    },

    /** 列表条目上的启用开关：点击即保存，失败回滚 */
    async setPluginEnabled(row, nextEnabled) {
      if (!row?.hasEnabled) return false
      const key = row.key
      if (this.enabledSavingMap?.[key]) return false

      const previousConfig = { ...(this.adapters?.[key] || {}) }
      const previousEnabled = Boolean(previousConfig?.[row.enabledField])
      const targetEnabled = Boolean(nextEnabled)
      if (previousEnabled === targetEnabled) return true

      const nextConfig = { ...previousConfig, [row.enabledField]: targetEnabled }
      this.enabledSavingMap = { ...this.enabledSavingMap, [key]: true }
      this.adapters = { ...this.adapters, [key]: nextConfig }
      try {
        const response = await comicApi.saveThirdPartyConfig({
          adapter: key,
          config: nextConfig
        })
        if (response.code !== 200) {
          throw new Error(response.msg || '保存失败')
        }
        showSuccessToast(targetEnabled ? `已启用 ${row.label}` : `已停用 ${row.label}`)
        return true
      } catch (error) {
        this.adapters = { ...this.adapters, [key]: previousConfig }
        showFailToast(error?.message || '切换启用状态失败')
        return false
      } finally {
        this.enabledSavingMap = { ...this.enabledSavingMap, [key]: false }
      }
    },

    async savePluginConfig(configKey, payload) {
      const key = String(configKey || '').trim()
      const row = this.rowForConfigKey(key)
      if (!row) {
        showFailToast('插件不存在')
        return false
      }
      this.configSavingMap = { ...this.configSavingMap, [key]: true }
      try {
        const body = coerceFieldPayload(row.fields, payload)
        const response = await comicApi.saveThirdPartyConfig({ adapter: key, config: body })
        if (response.code !== 200) {
          throw new Error(response.msg || '保存失败')
        }
        this.adapters = { ...this.adapters, [key]: { ...(this.adapters?.[key] || {}), ...body } }
        showSuccessToast(`${row.label} 配置已保存`)
        return true
      } catch (error) {
        showFailToast(error?.message || '保存失败')
        return false
      } finally {
        this.configSavingMap = { ...this.configSavingMap, [key]: false }
      }
    },

    async installExtensionPackage(file) {
      if (!file) return false
      this.installingPackage = true
      try {
        const response = await comicApi.installThirdPartyExtension(file)
        if (response.code !== 200) {
          throw new Error(response.msg || '扩展安装失败')
        }
        showSuccessToast(response.data?.message || '扩展安装成功，重启后生效')
        await this.loadConfig(true)
        return true
      } catch (error) {
        showFailToast(error?.message || '扩展安装失败')
        return false
      } finally {
        this.installingPackage = false
      }
    },

    async installExtensionFromGithub(url) {
      const target = String(url || '').trim()
      if (!target) {
        showFailToast('请输入 GitHub 仓库或 Gist 链接')
        return false
      }
      this.installingGithub = true
      try {
        const response = await comicApi.installThirdPartyExtensionFromGithub(target)
        if (response.code !== 200) {
          throw new Error(response.msg || '扩展安装失败')
        }
        showSuccessToast(response.data?.message || '扩展安装成功，重启后生效')
        await this.loadConfig(true)
        return true
      } catch (error) {
        showFailToast(error?.message || '扩展安装失败')
        return false
      } finally {
        this.installingGithub = false
      }
    },

    async reinstallExtension(pluginId) {
      const target = String(pluginId || '').trim()
      if (!target) return false
      this.extensionActionMap = { ...this.extensionActionMap, [target]: true }
      try {
        const response = await comicApi.reinstallThirdPartyExtension(target)
        if (response.code !== 200) {
          throw new Error(response.msg || '扩展更新失败')
        }
        showSuccessToast(response.data?.message || '扩展更新成功，重启后生效')
        await this.loadConfig(true)
        return true
      } catch (error) {
        showFailToast(error?.message || '扩展更新失败')
        return false
      } finally {
        this.extensionActionMap = { ...this.extensionActionMap, [target]: false }
      }
    },

    async deleteExtension(pluginId) {
      const target = String(pluginId || '').trim()
      if (!target) return false
      try {
        await showConfirmDialog({
          title: '删除扩展代码',
          message: '只会删除扩展代码，已保存的安装链接和平台配置会保留。删除后需要重启应用才会生效。'
        })
      } catch {
        return false
      }
      this.extensionActionMap = { ...this.extensionActionMap, [target]: true }
      try {
        const response = await comicApi.deleteThirdPartyExtension(target)
        if (response.code !== 200) {
          throw new Error(response.msg || '删除扩展失败')
        }
        showSuccessToast(response.data?.message || '扩展代码已删除，重启后生效')
        await this.loadConfig(true)
        return true
      } catch (error) {
        showFailToast(error?.message || '删除扩展失败')
        return false
      } finally {
        this.extensionActionMap = { ...this.extensionActionMap, [target]: false }
      }
    },

    isPrivatePluginEnabled(pluginId) {
      return this.privateEnabledPluginIds.includes(pluginId)
    },

    setPrivatePluginEnabled(pluginId, enabled) {
      const current = new Set(this.privateEnabledPluginIds)
      if (enabled) current.add(pluginId)
      else current.delete(pluginId)
      this.privateEnabledPluginIds = Array.from(current)
    },

    async saveSpaceAccess() {
      this.savingSpaceAccess = true
      try {
        const response = await comicApi.saveThirdPartyConfig({
          space_access: {
            private_enabled_plugin_ids: this.privateEnabledPluginIds
          }
        })
        if (response.code !== 200) {
          throw new Error(response.msg || '隐私空间授权保存失败')
        }
        showSuccessToast('隐私空间授权已保存')
        await this.loadConfig(true)
        return true
      } catch (error) {
        showFailToast(error?.message || '隐私空间授权保存失败')
        return false
      } finally {
        this.savingSpaceAccess = false
      }
    },

    buildFieldForm(row) {
      const form = {}
      ;(row?.fields || []).forEach((field) => {
        if (!field?.key) return
        if (row.hasEnabled && String(field.key) === row.enabledField) return
        form[field.key] = normalizeFieldValue(field, row.config?.[field.key])
      })
      return form
    }
  }
})
