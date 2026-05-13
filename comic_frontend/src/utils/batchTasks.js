import { isLocalComicCandidateId, isLocalVideoCandidateId } from './helpers'

function normalizeSelectedItems(items = []) {
  return Array.isArray(items) ? items.filter((item) => item && typeof item === 'object') : []
}

function collectEligibleIds(items = [], predicate) {
  return normalizeSelectedItems(items)
    .map((item) => String(item.id || '').trim())
    .filter((id) => id && predicate(id))
}

export function buildBatchTaskActions({
  contentType = 'comic',
  selectedItems = [],
  thirdPartyEnabled = false,
  supportsVideoThumbnailBatch = false,
} = {}) {
  const normalizedType = String(contentType || '').trim().toLowerCase()

  if (normalizedType === 'video') {
    const eligibleVideoIds = collectEligibleIds(selectedItems, isLocalVideoCandidateId)
    return [
      {
        name: '批量补全信息',
        taskType: 'video_local_metadata_refresh',
        eligibleIds: eligibleVideoIds,
        disabled: !thirdPartyEnabled || eligibleVideoIds.length === 0,
        reason: !thirdPartyEnabled
          ? '当前运行配置未启用第三方能力'
          : (eligibleVideoIds.length === 0 ? '当前所选内容里没有 LOCAL 本地导入视频' : ''),
      },
      {
        name: '批量生成缩略图',
        taskType: 'video_local_thumbnail_generate',
        eligibleIds: eligibleVideoIds,
        disabled: !supportsVideoThumbnailBatch || eligibleVideoIds.length === 0,
        reason: !supportsVideoThumbnailBatch
          ? '当前运行时暂不支持批量生成视频缩略图'
          : (eligibleVideoIds.length === 0 ? '当前所选内容里没有 LOCAL 本地导入视频' : ''),
      },
    ]
  }

  const eligibleComicIds = collectEligibleIds(selectedItems, isLocalComicCandidateId)
  return [
    {
      name: '批量补全信息',
      taskType: 'comic_local_metadata_refresh',
      eligibleIds: eligibleComicIds,
      disabled: !thirdPartyEnabled || eligibleComicIds.length === 0,
      reason: !thirdPartyEnabled
        ? '当前运行配置未启用第三方能力'
        : (eligibleComicIds.length === 0 ? '当前所选内容里没有 LOCAL 本地导入漫画' : ''),
    },
  ]
}
