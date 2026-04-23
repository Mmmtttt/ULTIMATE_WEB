import { comicApi } from '@/api/comic'

function normalizeString(value) {
  return String(value || '').trim()
}

function normalizeLower(value) {
  return normalizeString(value).toLowerCase()
}

export function getProtocolPluginCapabilities(plugin) {
  return Array.isArray(plugin?.capabilities) ? plugin.capabilities.map(item => normalizeString(item)) : []
}

export function getProtocolPluginMediaTypes(plugin) {
  return Array.isArray(plugin?.media_types) ? plugin.media_types.map(item => normalizeLower(item)) : []
}

export function pluginSupportsCapability(plugin, capability) {
  const lookup = normalizeString(capability)
  if (!lookup) {
    return true
  }
  return getProtocolPluginCapabilities(plugin).includes(lookup)
}

export function pluginSupportsMediaType(plugin, mediaType) {
  const lookup = normalizeLower(mediaType)
  if (!lookup) {
    return true
  }
  return getProtocolPluginMediaTypes(plugin).includes(lookup)
}

export function getProtocolPluginPlatform(plugin) {
  const identity = plugin?.identity || {}
  const legacyPlatforms = Array.isArray(plugin?.legacy_platforms) ? plugin.legacy_platforms : []
  const candidates = [
    identity?.platform_label,
    legacyPlatforms[0],
    identity?.host_id_prefix,
    plugin?.config_key,
    plugin?.name,
    plugin?.plugin_id,
  ]

  for (const candidate of candidates) {
    const normalized = normalizeLower(candidate)
    if (normalized) {
      return normalized
    }
  }
  return ''
}

export function getProtocolPluginLabel(plugin) {
  const identity = plugin?.identity || {}
  return (
    normalizeString(plugin?.configuration?.label) ||
    normalizeString(identity?.platform_label) ||
    normalizeString(plugin?.name) ||
    normalizeString(getProtocolPluginPlatform(plugin)).toUpperCase()
  )
}

export function filterProtocolPlugins(plugins = [], { mediaType = '', capability = '' } = {}) {
  return (Array.isArray(plugins) ? plugins : [])
    .filter(plugin => pluginSupportsMediaType(plugin, mediaType))
    .filter(plugin => pluginSupportsCapability(plugin, capability))
    .sort((a, b) => Number(a?.order || 100) - Number(b?.order || 100))
}

export function toProtocolPlatformOption(plugin) {
  return {
    pluginId: normalizeString(plugin?.plugin_id),
    platform: getProtocolPluginPlatform(plugin),
    label: getProtocolPluginLabel(plugin),
    configKey: normalizeString(plugin?.config_key),
    capabilities: getProtocolPluginCapabilities(plugin),
    mediaTypes: getProtocolPluginMediaTypes(plugin),
    presentation: plugin?.presentation || {},
    plugin,
  }
}

export async function fetchThirdPartyPluginDescriptors() {
  const response = await comicApi.getThirdPartyConfig()
  if (response?.code !== 200) {
    return []
  }
  return Array.isArray(response?.data?.plugins) ? response.data.plugins : []
}

export async function fetchProtocolPlatformOptions(filters = {}) {
  const plugins = await fetchThirdPartyPluginDescriptors()
  return filterProtocolPlugins(plugins, filters)
    .map(toProtocolPlatformOption)
    .filter(item => item.platform)
}
