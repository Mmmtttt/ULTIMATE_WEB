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
        sources: [{ key: 'primary_teledrive', label: 'TeleDrive 正片', kind: 'storage_remote' }]
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
        episodes: primaryEpisodes,
        sources: Array.isArray(rawPrimary.sources) ? rawPrimary.sources : []
      }
    : legacyPrimary

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
