import request from './request'

export function login(password) {
  return request({
    url: '/v1/auth/login',
    method: 'post',
    data: { password }
  })
}

export function getAuthStatus() {
  return request({
    url: '/v1/auth/status',
    method: 'get'
  })
}

export function logout() {
  return request({
    url: '/v1/auth/logout',
    method: 'post'
  })
}
