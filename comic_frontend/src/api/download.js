import request from './request'

// 下载能力 API（磁力链接投递到 Aria2 等下载插件）
export const downloadApi = {
  // 列出可用的下载引擎
  listEngines() {
    return request.get('/v1/download/engines')
  },

  // 投递磁力链接到下载引擎
  addMagnet(data = {}) {
    return request.post('/v1/download/magnet', data)
  },

  // 按 gid 查询任务状态
  getTaskStatus(gid, engine = '') {
    return request.get('/v1/download/task', { params: { gid, engine } })
  },

  // 查询任务列表
  listTasks(params = {}) {
    return request.get('/v1/download/tasks', { params })
  },

  // 删除任务
  removeTask(gid, engine = '', force = true) {
    return request.post('/v1/download/task/remove', { gid, engine, force })
  }
}
