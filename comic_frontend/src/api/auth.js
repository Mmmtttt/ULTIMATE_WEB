import request from './request'

export function login(password) {
  return request({
    url: '/v1/auth/login',
    method: 'post',
    data: { password }
  })
}

export function getAuthStatus(options = {}) {
  return request({
    url: '/v1/auth/status',
    method: 'get',
    // 启动期探测由就绪门兜底，失败时只写诊断日志，不弹用户提示。
    silentToast: options.silentToast === true
  })
}

export function logout() {
  return request({
    url: '/v1/auth/logout',
    method: 'post'
  })
}

export function updateProjectPassword(password) {
  return request({
    url: '/v1/auth/password',
    method: 'put',
    data: { password }
  })
}
