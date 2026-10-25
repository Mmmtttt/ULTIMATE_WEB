import request from './request'

/**
 * 引用式入库（library.sync.*）接口。
 *
 * 这一组接口做的事是「扫远端 → 写进预览库」，不搬运字节：
 * 播放与封面仍然在打开时按文件 ID 现取。
 */

// 扫一次网盘要逐层走目录，比普通接口慢得多，单独放宽超时。
const SYNC_APPLY_TIMEOUT_MS = 180000

export const librarySyncApi = {
  listPlugins() {
    return request.get('/v1/library-sync/plugins')
  },
  preview(pluginId) {
    return request.post('/v1/library-sync/preview', { plugin_id: pluginId }, { timeout: SYNC_APPLY_TIMEOUT_MS })
  },
  apply(pluginId) {
    return request.post('/v1/library-sync/apply', { plugin_id: pluginId }, { timeout: SYNC_APPLY_TIMEOUT_MS })
  }
}

export default librarySyncApi
