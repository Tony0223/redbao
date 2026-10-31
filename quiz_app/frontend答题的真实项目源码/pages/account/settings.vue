<template>
  <view class="page">
    <view class="card account-card">
      <view class="avatar">{{ avatarText }}</view>
      <view class="account-copy">
        <text class="username">{{ user ? user.username : '未登录' }}</text>
        <text class="email">{{ user ? user.email : '' }}</text>
      </view>
    </view>

    <view class="card danger-card">
      <text class="section-title">注销账号</text>
      <text class="warning">注销后，账号资料、全部登录会话和关联学习记录将被永久删除，且无法恢复。</text>
      <text class="field-label">当前密码</text>
      <input
        v-model="password"
        class="password-input"
        password
        maxlength="72"
        placeholder="请输入当前密码确认身份"
        placeholder-class="placeholder-color"
      />
      <view class="confirm-row" @tap="confirmed = !confirmed">
        <view class="checkbox" :class="{ checked: confirmed }">{{ confirmed ? '✓' : '' }}</view>
        <text class="confirm-text">我已了解注销后果，并确认注销账号</text>
      </view>
      <button class="delete-button pressable" :loading="deleting" :disabled="deleting" @tap="confirmDelete">
        {{ deleting ? '正在注销...' : '注销账号' }}
      </button>
    </view>
  </view>
</template>

<script>
import { authApi } from '../../common/api.js'
import { clearAuth, getStoredUser, getToken } from '../../common/auth.js'

export default {
  data() {
    return {
      user: getStoredUser(),
      password: '',
      confirmed: false,
      deleting: false
    }
  },
  computed: {
    avatarText() {
      return this.user && this.user.username ? this.user.username.slice(0, 1) : '答'
    }
  },
  onLoad() {
    if (!getToken()) {
      uni.showToast({ title: '请先登录', icon: 'none' })
      setTimeout(() => uni.reLaunch({ url: '/pages/mine/mine' }), 400)
    }
  },
  methods: {
    confirmDelete() {
      if (this.deleting) return
      if (this.password.length < 8) {
        uni.showToast({ title: '请输入当前密码', icon: 'none' })
        return
      }
      if (!this.confirmed) {
        uni.showToast({ title: '请确认已了解注销后果', icon: 'none' })
        return
      }
      uni.showModal({
        title: '最后确认',
        content: '账号注销后无法恢复，确定继续吗？',
        confirmText: '确认注销',
        confirmColor: '#d84f5f',
        success: (result) => {
          if (result.confirm) this.deleteAccount()
        }
      })
    },
    async deleteAccount() {
      this.deleting = true
      try {
        await authApi.deleteAccount(this.password)
        clearAuth()
        uni.showToast({ title: '账号已注销', icon: 'success' })
        setTimeout(() => uni.reLaunch({ url: '/pages/mine/mine' }), 500)
      } catch (error) {
        uni.showToast({ title: error.message, icon: 'none' })
      } finally {
        this.deleting = false
      }
    }
  }
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  padding: 30rpx 30rpx calc(60rpx + env(safe-area-inset-bottom));
  background: #f6f7fb;
}

.card {
  background: #fff;
  border: 1rpx solid #eceaf3;
  border-radius: 28rpx;
}

.account-card {
  display: flex;
  padding: 28rpx;
  align-items: center;
}

.avatar {
  display: flex;
  width: 86rpx;
  height: 86rpx;
  align-items: center;
  justify-content: center;
  color: #7357f6;
  font-size: 31rpx;
  font-weight: 800;
  background: #eeeaff;
  border-radius: 26rpx;
}

.account-copy {
  margin-left: 22rpx;
}

.username,
.email,
.section-title,
.warning,
.field-label {
  display: block;
}

.username {
  color: #302d40;
  font-size: 28rpx;
  font-weight: 800;
}

.email {
  margin-top: 7rpx;
  color: #9691a2;
  font-size: 21rpx;
}

.danger-card {
  margin-top: 26rpx;
  padding: 32rpx 30rpx 35rpx;
}

.section-title {
  color: #d84f5f;
  font-size: 30rpx;
  font-weight: 800;
}

.warning {
  margin-top: 17rpx;
  padding: 20rpx;
  color: #8e6268;
  font-size: 22rpx;
  line-height: 1.7;
  background: #fff4f5;
  border-radius: 18rpx;
}

.field-label {
  margin: 28rpx 0 11rpx 5rpx;
  color: #4a465b;
  font-size: 23rpx;
  font-weight: 700;
}

.password-input {
  height: 90rpx;
  padding: 0 24rpx;
  color: #302d40;
  font-size: 25rpx;
  background: #f8f8fb;
  border: 1rpx solid #e8e6ee;
  border-radius: 21rpx;
}

.placeholder-color {
  color: #bbb7c4;
}

.confirm-row {
  display: flex;
  margin-top: 25rpx;
  align-items: center;
}

.checkbox {
  display: flex;
  width: 36rpx;
  height: 36rpx;
  margin-right: 12rpx;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20rpx;
  border: 2rpx solid #c9c5d2;
  border-radius: 10rpx;
}

.checkbox.checked {
  background: #d84f5f;
  border-color: #d84f5f;
}

.confirm-text {
  color: #777181;
  font-size: 22rpx;
}

.delete-button {
  display: flex;
  height: 90rpx;
  margin-top: 30rpx;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 26rpx;
  font-weight: 700;
  background: #d84f5f;
  border-radius: 23rpx;
}

.delete-button[disabled] {
  opacity: 0.65;
}
</style>
