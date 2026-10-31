<template>
  <view class="page">
    <view class="safe-top"></view>
    <view class="decoration decoration-one"></view>
    <view class="decoration decoration-two"></view>

    <view class="top-bar">
      <view class="back pressable" @tap="goBack">‹</view>
      <text class="top-title">账号中心</text>
      <view class="placeholder"></view>
    </view>

    <view class="welcome">
      <view class="mini-logo">答</view>
      <text class="welcome-title">{{ isRegister ? '创建你的学习账号' : '欢迎回来' }}</text>
      <text class="welcome-desc">{{ isRegister ? '注册后，学习记录会跟随你的账号' : '登录以同步你的答题进度与成就' }}</text>
    </view>

    <view class="form-card">
      <view class="mode-tabs">
        <view class="mode-tab" :class="{ active: !isRegister }" @tap="setMode(false)">登录</view>
        <view class="mode-tab" :class="{ active: isRegister }" @tap="setMode(true)">注册</view>
      </view>

      <view v-if="isRegister" class="field">
        <text class="field-label">用户名</text>
        <input v-model.trim="form.username" class="input" maxlength="20" placeholder="2-20 位中文、字母、数字或下划线" placeholder-class="placeholder-color" />
      </view>
      <view class="field">
        <text class="field-label">{{ isRegister ? '邮箱' : '用户名或邮箱' }}</text>
        <input v-model.trim="form.account" class="input" :type="isRegister ? 'text' : 'text'" maxlength="255" :placeholder="isRegister ? '用于登录和找回账号' : '请输入用户名或邮箱'" placeholder-class="placeholder-color" />
      </view>
      <view class="field">
        <text class="field-label">密码</text>
        <input v-model="form.password" class="input" password maxlength="72" placeholder="至少 8 位字符" placeholder-class="placeholder-color" />
      </view>
      <view v-if="isRegister" class="field">
        <text class="field-label">确认密码</text>
        <input v-model="form.confirmPassword" class="input" password maxlength="72" placeholder="请再次输入密码" placeholder-class="placeholder-color" @confirm="submit" />
      </view>

      <view class="agreement" @tap="agreed = !agreed">
        <view class="checkbox" :class="{ checked: agreed }">{{ agreed ? '✓' : '' }}</view>
        <text class="agreement-text">我已阅读并同意</text>
        <text class="agreement-link" @tap.stop="openAgreement">《用户协议》</text>
        <text class="agreement-text">和</text>
        <text class="agreement-link" @tap.stop="openPrivacy">《隐私政策》</text>
      </view>

      <button class="submit pressable" :loading="loading" :disabled="loading" @tap="submit">
        {{ loading ? '请稍候...' : (isRegister ? '注册并登录' : '登录') }}
      </button>

      <text class="switch-text" @tap="setMode(!isRegister)">
        {{ isRegister ? '已有账号？去登录' : '还没有账号？立即注册' }}
      </text>
    </view>
  </view>
</template>

<script>
import { authApi } from '../../common/api.js'
import { saveAuth } from '../../common/auth.js'

export default {
  data() {
    return {
      isRegister: false,
      agreed: false,
      loading: false,
      form: {
        username: '',
        account: '',
        password: '',
        confirmPassword: ''
      }
    }
  },
  onLoad(options) {
    this.isRegister = options.mode === 'register'
  },
  methods: {
    setMode(value) {
      this.isRegister = value
      this.form.password = ''
      this.form.confirmPassword = ''
    },
    goBack() {
      uni.navigateBack({
        fail: () => uni.reLaunch({ url: '/pages/mine/mine' })
      })
    },
    openPrivacy() {
      uni.navigateTo({ url: '/pages/privacy/privacy' })
    },
    openAgreement() {
      uni.navigateTo({ url: '/pages/agreement/agreement' })
    },
    validate() {
      if (this.isRegister) {
        if (!/^[A-Za-z0-9_\u4e00-\u9fff]{2,20}$/.test(this.form.username)) {
          return '用户名需为 2-20 位中文、字母、数字或下划线'
        }
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.form.account)) {
          return '请输入有效的邮箱地址'
        }
      } else if (!this.form.account) {
        return '请输入用户名或邮箱'
      }
      if (this.form.password.length < 8) return '密码至少需要 8 位字符'
      if (this.isRegister && this.form.password !== this.form.confirmPassword) {
        return '两次输入的密码不一致'
      }
      if (!this.agreed) return '请先阅读并同意用户协议和隐私政策'
      return ''
    },
    async submit() {
      if (this.loading) return
      const errorMessage = this.validate()
      if (errorMessage) {
        uni.showToast({ title: errorMessage, icon: 'none' })
        return
      }
      this.loading = true
      try {
        const result = this.isRegister
          ? await authApi.register({
            username: this.form.username,
            email: this.form.account,
            password: this.form.password
          })
          : await authApi.login({
            account: this.form.account,
            password: this.form.password
          })
        saveAuth(result.token, result.user)
        uni.showToast({ title: this.isRegister ? '注册成功' : '登录成功', icon: 'success' })
        setTimeout(() => {
          uni.reLaunch({ url: '/pages/mine/mine' })
        }, 450)
      } catch (error) {
        uni.showToast({ title: error.message, icon: 'none' })
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.page {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  padding: 0 34rpx calc(60rpx + env(safe-area-inset-bottom));
  background: linear-gradient(155deg, #6f52ec 0, #8971f7 42%, #f6f7fb 42.1%);
}

.decoration {
  position: absolute;
  border: 2rpx solid rgba(255, 255, 255, 0.11);
  border-radius: 50%;
}

.decoration-one {
  top: -120rpx;
  right: -100rpx;
  width: 350rpx;
  height: 350rpx;
}

.decoration-two {
  top: 240rpx;
  left: -100rpx;
  width: 220rpx;
  height: 220rpx;
}

.top-bar {
  position: relative;
  z-index: 1;
  display: flex;
  height: 90rpx;
  align-items: center;
  justify-content: space-between;
  color: #fff;
}

.back,
.placeholder {
  display: flex;
  width: 62rpx;
  height: 62rpx;
  align-items: center;
  justify-content: center;
}

.back {
  font-size: 52rpx;
  font-weight: 300;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 20rpx;
}

.top-title {
  font-size: 29rpx;
  font-weight: 700;
}

.welcome {
  position: relative;
  z-index: 1;
  display: flex;
  height: 240rpx;
  align-items: center;
  color: #fff;
  flex-direction: column;
}

.mini-logo {
  display: flex;
  width: 72rpx;
  height: 72rpx;
  align-items: center;
  justify-content: center;
  color: #7357f6;
  font-size: 28rpx;
  font-weight: 900;
  background: #fff;
  border-radius: 23rpx;
}

.welcome-title {
  margin-top: 17rpx;
  font-size: 36rpx;
  font-weight: 800;
}

.welcome-desc {
  margin-top: 9rpx;
  color: rgba(255, 255, 255, 0.72);
  font-size: 21rpx;
}

.form-card {
  position: relative;
  z-index: 2;
  padding: 30rpx 34rpx 36rpx;
  background: #fff;
  border: 1rpx solid #ece9f5;
  border-radius: 34rpx;
  box-shadow: 0 24rpx 60rpx rgba(55, 40, 115, 0.14);
}

.mode-tabs {
  display: flex;
  height: 80rpx;
  margin-bottom: 28rpx;
  padding: 7rpx;
  background: #f3f1f8;
  border-radius: 22rpx;
}

.mode-tab {
  display: flex;
  width: 50%;
  align-items: center;
  justify-content: center;
  color: #9a96a6;
  font-size: 25rpx;
  font-weight: 700;
  border-radius: 17rpx;
}

.mode-tab.active {
  color: #6549e3;
  background: #fff;
  box-shadow: 0 5rpx 16rpx rgba(55, 44, 94, 0.08);
}

.field {
  margin-top: 22rpx;
}

.field-label {
  display: block;
  margin: 0 0 11rpx 6rpx;
  color: #4a465b;
  font-size: 23rpx;
  font-weight: 700;
}

.input {
  height: 90rpx;
  padding: 0 25rpx;
  color: #302d40;
  font-size: 25rpx;
  background: #f8f8fb;
  border: 1rpx solid #e8e6ee;
  border-radius: 22rpx;
}

.placeholder-color {
  color: #bbb7c4;
}

.agreement {
  display: flex;
  margin-top: 27rpx;
  align-items: center;
}

.checkbox {
  display: flex;
  width: 34rpx;
  height: 34rpx;
  margin-right: 11rpx;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20rpx;
  border: 2rpx solid #c9c5d2;
  border-radius: 10rpx;
}

.checkbox.checked {
  background: #7357f6;
  border-color: #7357f6;
}

.agreement-text,
.agreement-link {
  font-size: 21rpx;
}

.agreement-text {
  color: #8c8798;
}

.agreement-link {
  color: #7357f6;
}

.submit {
  display: flex;
  height: 92rpx;
  margin-top: 34rpx;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 27rpx;
  font-weight: 700;
  background: linear-gradient(135deg, #7357f6, #8f74fb);
  border-radius: 24rpx;
  box-shadow: 0 14rpx 30rpx rgba(115, 87, 246, 0.22);
}

.submit[disabled] {
  opacity: 0.65;
}

.switch-text {
  display: block;
  margin-top: 27rpx;
  color: #7357f6;
  font-size: 23rpx;
  text-align: center;
}
</style>
