function normalizeString(value) {
  return String(value || '').trim()
}

function normalizeEpisode(episode, fallbackIndex = 1) {
  const index = Number(episode?.index) || fallbackIndex
  const name = normalizeString(
    episode?.name ||
    episode?.relative_path ||
    episode?.title ||
    `第 ${index} 集`
  ) || `第 ${index} 集`
  return {
    index: index > 0 ? index : fallbackIndex,
    name,
    url: normalizeString(episode?.url),
    kind: normalizeString(episode?.kind)
  }
}

function isLikelyVideoUrl(url) {
  const lower = normalizeString(url).toLowerCase()
  if (!lower) {
    return false
  }
  if (
    lower.startsWith('/api/v1/video/proxy2') ||
    lower.startsWith('/v1/video/proxy2') ||
    lower.startsWith('/proxy2?') ||
    lower.startsWith('/proxy/')
  ) {
    return true
  }
  return /\.(mp4|m3u8|webm|mov|m4v)(?:$|[?#])/i.test(lower)
}

function buildTeledriveFileUrl(episode) {
  const fileId = normalizeString(episode?.file_id)
  if (!fileId) {
    return ''
  }
  const query = new URLSearchParams({ name: normalizeString(episode?.name) }).toString()
  return `/api/v1/teledrive/files/${encodeURIComponent(fileId)}/content?${query}`
}

function buildLegacyPrimary(item) {
  const display = item?.display && typeof item.display === 'object' ? item.display : {}
  const localEpisodes = Array.isArray(display.local_episodes) ? display.local_episodes : []
  if (localEpisodes.length > 0) {
    const episodes = localEpisodes.map((episode, index) => normalizeEpisode(episode, index + 1))
    return {
      available: true,
      mode: 'local',
      supports_play_session: true,
      supports_episode_selection: episodes.length > 1,
      default_episode_index: episodes[0]?.index || 1,
      episodes,
      sources: [{ key: 'primary_local', label: '本地正片', kind: 'local' }]
    }
  }

  const teledriveEpisodes =
    display.teledrive && Array.isArray(display.teledrive.episodes)
      ? display.teledrive.episodes
      : []
  if (teledriveEpisodes.length > 0) {
    const episodes = teledriveEpisodes
      .map((episode, index) => {
        const normalized = normalizeEpisode({
          ...episode,
          url: buildTeledriveFileUrl(episode)
        }, index + 1)
        return normalized.url ? { ...normalized, kind: normalized.kind || 'teledrive_episode' } : null
      })
      .filter(Boolean)
    if (episodes.length > 0) {
      return {
        available: true,
        mode: 'storage_remote',
        supports_play_session: true,
        supports_episode_selection: episodes.length > 1,
        default_episode_index: episodes[0]?.index || 1,
        episodes,
        sources: [{ key: 'primary_remote', label: '远程正片', kind: 'storage_remote' }]
      }
    }
  }

  const onlineAvailable = Boolean(normalizeString(item?.code))
  return {
    available: onlineAvailable,
    mode: onlineAvailable ? 'online' : 'none',
    supports_play_session: onlineAvailable,
    supports_episode_selection: false,
    default_episode_index: 1,
    episodes: [],
    sources: onlineAvailable ? [{ key: 'primary_online', label: '在线播放', kind: 'online' }] : []
  }
}

function buildLegacyPreviewAssets(item, primaryEpisodes = []) {
  const primaryUrls = new Set(
    primaryEpisodes
      .map((episode) => normalizeString(episode?.url))
      .filter(Boolean)
  )
  const localVideoPath = normalizeString(item?.local_video_path)
  if (localVideoPath) {
    primaryUrls.add(localVideoPath)
  }

  const assets = []
  const seenUrls = new Set()

  const pushAsset = (key, label, url, origin) => {
    const normalized = normalizeString(url)
    if (!isLikelyVideoUrl(normalized) || primaryUrls.has(normalized) || seenUrls.has(normalized)) {
      return
    }
    seenUrls.add(normalized)
    const lower = normalized.toLowerCase()
    assets.push({
      key,
      label,
      url: normalized,
      origin,
      transport: lower.includes('m3u8') ? 'hls' : 'direct'
    })
  }

  pushAsset('preview_local', '本地预览', item?.preview_video_local, 'local')
  pushAsset('preview_remote', '远端预览', item?.preview_video, 'remote')
  return assets
}

function normalizePreviewAsset(asset, fallbackIndex = 1) {
  const key = normalizeString(asset?.key) || `preview_asset_${fallbackIndex}`
  const label = normalizeString(asset?.label) || `预览 ${fallbackIndex}`
  const url = normalizeString(asset?.url)
  const origin = normalizeString(asset?.origin) || 'remote'
  const transport = normalizeString(asset?.transport) || (url.toLowerCase().includes('m3u8') ? 'hls' : 'direct')
  return {
    key,
    label,
    url,
    origin,
    transport
  }
}

function normalizePlayStream(stream, fallbackSource = '') {
  if (!stream || typeof stream !== 'object') {
    return null
  }
  const url = normalizeString(stream.url || stream.proxy_url)
  if (!url) {
    return null
  }
  return {
    ...stream,
    url,
    resolution: normalizeString(stream.resolution) || '原始',
    type: normalizeString(stream.type) || 'direct',
    source: normalizeString(stream.source) || fallbackSource
  }
}

function guessEpisodeIndex(source, fallbackIndex = 0) {
  const direct = Number(source?.episode_index)
  if (direct > 0) {
    return direct
  }
  const key = normalizeString(source?.key || source?.source || '')
  const matched = key.match(/(?:^|_episode_)(\d+)$/)
  if (matched) {
    return Number(matched[1]) || fallbackIndex
  }
  return fallbackIndex
}

function normalizePlayableSource(source, fallbackIndex = 1) {
  const key = normalizeString(source?.key || source?.source || source?.name) || `play_source_${fallbackIndex}`
  const streams = Array.isArray(source?.streams)
    ? source.streams.map((stream) => normalizePlayStream(stream, key)).filter(Boolean)
    : []
  const directUrl = normalizeString(source?.url)
  const normalizedStreams = streams.length > 0
    ? streams
    : (directUrl ? [{
        url: directUrl,
        resolution: normalizeString(source?.currentResolution) || '原始',
        type: normalizeString(source?.type) || 'direct',
        source: key
      }] : [])
  const episodeIndex = guessEpisodeIndex(source, fallbackIndex)
  return {
    ...source,
    key,
    source: normalizeString(source?.source) || key,
    name: normalizeString(source?.name || source?.label) || `播放项 ${fallbackIndex}`,
    type: normalizeString(source?.type) || 'direct',
    available: Boolean(source?.available !== false && normalizedStreams.length > 0),
    currentResolution: normalizeString(source?.currentResolution),
    episode_index: episodeIndex > 0 ? episodeIndex : 0,
    streams: normalizedStreams
  }
}

function normalizePlayProviderGroup(group, fallbackIndex = 1) {
  const key = normalizeString(group?.key || group?.provider_key || group?.provider || group?.label) || `provider_${fallbackIndex}`
  const sources = Array.isArray(group?.sources)
    ? group.sources.map((source, index) => normalizePlayableSource(source, index + 1))
    : []
  const availableSources = sources.filter((source) => source.available)
  return {
    key,
    label: normalizeString(group?.label || group?.provider_label) || `平台 ${fallbackIndex}`,
    kind: normalizeString(group?.kind || group?.mode) || 'remote',
    selection_mode: normalizeString(group?.selection_mode) === 'episodes' ? 'episodes' : 'streams',
    available: typeof group?.available === 'boolean' ? group.available : availableSources.length > 0,
    supports_episode_selection: typeof group?.supports_episode_selection === 'boolean'
      ? group.supports_episode_selection
      : (normalizeString(group?.selection_mode) === 'episodes' && availableSources.length > 1),
    default_source_key: normalizeString(group?.default_source_key) || availableSources[0]?.key || '',
    error: normalizeString(group?.error),
    sources,
    available_sources: availableSources
  }
}

export function resolvePlayProviderGroups(payload) {
  const providerGroups = Array.isArray(payload?.provider_groups)
    ? payload.provider_groups.map((group, index) => normalizePlayProviderGroup(group, index + 1)).filter((group) => group.sources.length > 0)
    : []
  const defaultProviderKey = normalizeString(payload?.default_provider_key) || providerGroups[0]?.key || ''
  return {
    providerGroups,
    defaultProviderKey
  }
}

export function buildEpisodeListFromPlayableSources(sources) {
  if (!Array.isArray(sources)) {
    return []
  }
  return sources
    .map((source, index) => {
      const episodeIndex = guessEpisodeIndex(source, index + 1)
      if (episodeIndex <= 0) {
        return null
      }
      return {
        index: episodeIndex,
        name: normalizeString(source?.name) || `第 ${episodeIndex} 集`
      }
    })
    .filter(Boolean)
}

function normalizeSourceSummary(source, fallbackIndex = 1) {
  return {
    key: normalizeString(source?.key) || `primary_source_${fallbackIndex}`,
    label: normalizeString(source?.label) || `播放源 ${fallbackIndex}`,
    kind: normalizeString(source?.kind || source?.mode)
  }
}

function normalizeSourceGroup(group, fallbackIndex = 1) {
  const episodes = Array.isArray(group?.episodes)
    ? group.episodes.map((episode, index) => normalizeEpisode(episode, index + 1)).filter((episode) => episode.url)
    : []
  const key = normalizeString(group?.key) || `primary_source_${fallbackIndex}`
  return {
    key,
    label: normalizeString(group?.label) || `播放源 ${fallbackIndex}`,
    mode: normalizeString(group?.mode) || 'none',
    available: typeof group?.available === 'boolean' ? group.available : Boolean(episodes.length || key),
    supports_play_session: typeof group?.supports_play_session === 'boolean'
      ? group.supports_play_session
      : Boolean(episodes.length || normalizeString(group?.provider)),
    supports_episode_selection: typeof group?.supports_episode_selection === 'boolean'
      ? group.supports_episode_selection
      : episodes.length > 1,
    default_episode_index: Number(group?.default_episode_index) || (episodes[0]?.index || 1),
    episodes
  }
}

function buildLegacySourceGroups(item, legacyPrimary) {
  const groups = []
  if (legacyPrimary?.available) {
    const mode = normalizeString(legacyPrimary.mode) || 'none'
    const isRemote = mode === 'storage_remote' || mode === 'online'
    groups.push({
      key: isRemote ? 'remote' : 'local',
      label: isRemote ? '远程' : '本地',
      mode,
      available: true,
      supports_play_session: Boolean(legacyPrimary.supports_play_session),
      supports_episode_selection: Boolean(legacyPrimary.supports_episode_selection),
      default_episode_index: Number(legacyPrimary.default_episode_index) || (legacyPrimary.episodes?.[0]?.index || 1),
      episodes: Array.isArray(legacyPrimary.episodes) ? legacyPrimary.episodes : []
    })
  }
  return groups
}

export function resolveVideoPlaybackModel(item) {
  const rawPlayback = item?.playback && typeof item.playback === 'object' ? item.playback : null
  const hasPlaybackProjection = Boolean(rawPlayback && (rawPlayback.primary || rawPlayback.preview || rawPlayback.bucket))

  const rawPrimary = rawPlayback?.primary && typeof rawPlayback.primary === 'object' ? rawPlayback.primary : {}
  const rawPreview = rawPlayback?.preview && typeof rawPlayback.preview === 'object' ? rawPlayback.preview : {}

  const legacyPrimary = buildLegacyPrimary(item)
  const primaryEpisodes = hasPlaybackProjection
    ? (Array.isArray(rawPrimary.episodes) ? rawPrimary.episodes.map((episode, index) => normalizeEpisode(episode, index + 1)) : [])
    : legacyPrimary.episodes

  const previewAssets = hasPlaybackProjection
    ? (Array.isArray(rawPreview.assets) ? rawPreview.assets.map((asset, index) => normalizePreviewAsset(asset, index + 1)).filter((asset) => asset.url) : [])
    : buildLegacyPreviewAssets(item, primaryEpisodes)

  const sourceGroups = hasPlaybackProjection
    ? (Array.isArray(rawPrimary.source_groups)
      ? rawPrimary.source_groups.map((group, index) => normalizeSourceGroup(group, index + 1)).filter((group) => group.available)
      : [])
    : buildLegacySourceGroups(item, legacyPrimary)

  const defaultSourceKey = hasPlaybackProjection
    ? (normalizeString(rawPrimary.default_source_key) || sourceGroups[0]?.key || '')
    : (sourceGroups[0]?.key || '')

  const primary = hasPlaybackProjection
    ? {
        available: typeof rawPrimary.available === 'boolean' ? rawPrimary.available : Boolean(primaryEpisodes.length),
        mode: normalizeString(rawPrimary.mode) || 'none',
        supports_play_session: typeof rawPrimary.supports_play_session === 'boolean'
          ? rawPrimary.supports_play_session
          : Boolean(primaryEpisodes.length || normalizeString(item?.code)),
        supports_episode_selection: typeof rawPrimary.supports_episode_selection === 'boolean'
          ? rawPrimary.supports_episode_selection
          : primaryEpisodes.length > 1,
        default_episode_index: Number(rawPrimary.default_episode_index) || (primaryEpisodes[0]?.index || 1),
        default_source_key: defaultSourceKey,
        episodes: primaryEpisodes,
        source_groups: sourceGroups,
        sources: Array.isArray(rawPrimary.sources)
          ? rawPrimary.sources.map((source, index) => normalizeSourceSummary(source, index + 1))
          : sourceGroups.map((group, index) => normalizeSourceSummary(group, index + 1))
      }
    : {
        ...legacyPrimary,
        default_source_key: defaultSourceKey,
        source_groups: sourceGroups,
        sources: sourceGroups.map((group, index) => normalizeSourceSummary(group, index + 1))
      }

  const preview = {
    available: hasPlaybackProjection
      ? (typeof rawPreview.available === 'boolean' ? rawPreview.available : previewAssets.length > 0)
      : previewAssets.length > 0,
    default_asset_key: hasPlaybackProjection
      ? (normalizeString(rawPreview.default_asset_key) || previewAssets[0]?.key || '')
      : (previewAssets[0]?.key || ''),
    assets: previewAssets
  }

  return {
    bucket: hasPlaybackProjection
      ? (normalizeString(rawPlayback.bucket) || (normalizeString(item?.source) === 'preview' ? 'candidate' : 'local'))
      : (normalizeString(item?.source) === 'preview' ? 'candidate' : 'local'),
    primary,
    preview
  }
}
