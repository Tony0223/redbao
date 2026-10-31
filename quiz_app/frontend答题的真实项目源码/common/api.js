// 线上 API 地址，H5 浏览器测试和 APP 打包统一使用 HTTPS。
import { clearAuth, getToken, PRIVACY_AGREED_KEY } from './auth.js'

export const BASE_URL = 'https://zero-start.online'

export function request(options) {
  return new Promise((resolve, reject) => {
    if (!uni.getStorageSync(PRIVACY_AGREED_KEY)) {
      reject(new Error('请先阅读并同意隐私政策'))
      return
    }
    const token = getToken()
    const headers = {
      'content-type': 'application/json'
    }
    if (token) {
      headers.Authorization = 'Bearer ' + token
    }
    uni.request({
      url: BASE_URL + options.url,
      method: options.method || 'GET',
      data: options.data || {},
      timeout: 10000,
      header: headers,
      success: (response) => {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data)
          return
        }
        if (response.statusCode === 401 && options.url.indexOf('/api/auth/login') !== 0) {
          clearAuth()
        }
        const detail = response.data && response.data.detail
        const message = typeof detail === 'string' ? detail : '请求失败，请稍后重试'
        reject(new Error(message))
      },
      fail: (error) => reject(new Error(error.errMsg || '无法连接服务器'))
    })
  })
}

export const quizApi = {
  getTopics: () => request({ url: '/api/topics' }),
  getStats: () => request({ url: '/api/stats' }),
  getQuestions: (topicId) => request({
    url: '/api/topics/' + encodeURIComponent(topicId) + '/questions'
  }),
  checkAnswer: (questionId, answer) => request({
    url: '/api/answers',
    method: 'POST',
    data: { question_id: questionId, answer: answer }
  }),
  saveResult: (payload) => request({
    url: '/api/results',
    method: 'POST',
    data: payload
  })
}

export const authApi = {
  register: (payload) => request({
    url: '/api/auth/register',
    method: 'POST',
    data: payload
  }),
  login: (payload) => request({
    url: '/api/auth/login',
    method: 'POST',
    data: payload
  }),
  getMe: () => request({ url: '/api/auth/me' }),
  logout: () => request({ url: '/api/auth/logout', method: 'POST' }),
  deleteAccount: (password) => request({
    url: '/api/auth/account',
    method: 'DELETE',
    data: { password: password }
  })
}
