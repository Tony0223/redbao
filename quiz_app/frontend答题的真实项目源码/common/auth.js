export const AUTH_TOKEN_KEY = 'quiz_auth_token'
export const AUTH_USER_KEY = 'quiz_auth_user'
export const PRIVACY_AGREED_KEY = 'privacy_agreed_v3'

export function getToken() {
  return uni.getStorageSync(AUTH_TOKEN_KEY) || ''
}

export function getStoredUser() {
  return uni.getStorageSync(AUTH_USER_KEY) || null
}

export function saveAuth(token, user) {
  uni.setStorageSync(AUTH_TOKEN_KEY, token)
  uni.setStorageSync(AUTH_USER_KEY, user)
}

export function clearAuth() {
  uni.removeStorageSync(AUTH_TOKEN_KEY)
  uni.removeStorageSync(AUTH_USER_KEY)
}
