<template>
  <view class="page">
    <view class="planet planet-one"></view>
    <view class="planet planet-two"></view>
    <view class="brand">
      <view class="logo">答</view>
      <text class="brand-name">金石速答</text>
      <text class="brand-desc">让每一次学习都清楚、安心</text>
    </view>

    <view class="mask">
      <view class="dialog">
        <view class="shield">✓</view>
        <text class="title">隐私保护提示</text>
        <text class="content">
          欢迎使用金石速答！在使用前，请你仔细阅读并充分理解
          <text class="link" @tap.stop="openAgreement">《用户协议》</text>和
          <text class="link" @tap.stop="openPrivacy">《隐私政策》</text>。
          我们将按照政策说明处理必要的账号信息和学习记录。只有在你同意后，应用才会进入首页并发起网络请求。
        </text>
        <button class="agree-button pressable" @tap="agree">同意并继续</button>
        <button class="decline-button pressable" @tap="decline">不同意并退出 APP</button>
      </view>
    </view>
  </view>
</template>

<script>
import { PRIVACY_AGREED_KEY } from '../../common/auth.js'

export default {
  onLoad() {
    let agreed = Boolean(uni.getStorageSync(PRIVACY_AGREED_KEY))
    // Android 使用 DCloud 原生 template 隐私弹窗。原生弹窗在进入
    // Vue 页面前完成同意，这里只同步状态，不再显示第二个弹窗。
    // #ifdef APP-PLUS
    try {
      if (plus.runtime && plus.runtime.isAgreePrivacy && plus.runtime.isAgreePrivacy()) {
        agreed = true
        uni.setStorageSync(PRIVACY_AGREED_KEY, true)
      }
    } catch (e) {}
    // #endif
    if (agreed) {
      this.enterApp()
    }
  },
  methods: {
    openPrivacy() {
      uni.navigateTo({ url: '/pages/privacy/privacy?from=consent' })
    },
    openAgreement() {
      uni.navigateTo({ url: '/pages/agreement/agreement?from=consent' })
    },
    agree() {
      // 自定义弹窗仅用于 H5/非 App 运行环境；在 App 中同步 DCloud
      // 原生隐私状态，保证所有原生 SDK 只在同意后运行。
      // #ifdef APP-PLUS
      if (plus.runtime && plus.runtime.agreePrivacy) plus.runtime.agreePrivacy()
      // #endif
      uni.setStorageSync(PRIVACY_AGREED_KEY, true)
      const app = getApp()
      if (app && app.globalData) app.globalData.privacyAgreed = true
      this.enterApp()
    },
    enterApp() {
      uni.reLaunch({ url: '/pages/index/index' })
    },
    decline() {
      // #ifdef APP-PLUS
      if (plus.runtime && plus.runtime.disagreePrivacy) plus.runtime.disagreePrivacy()
      plus.runtime.quit()
      // #endif
      // #ifndef APP-PLUS
      uni.showModal({
        title: '暂时无法继续',
        content: '你尚未同意隐私政策，请关闭当前页面；同意后才可使用应用。',
        showCancel: false,
        confirmText: '知道了'
      })
      // #endif
    }
  }
}
</script>

<style scoped>
.page {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  background: linear-gradient(155deg, #7255f3 0%, #907af8 100%);
}

.planet {
  position: absolute;
  border: 2rpx solid rgba(255, 255, 255, 0.13);
  border-radius: 50%;
}

.planet-one {
  top: -120rpx;
  right: -150rpx;
  width: 480rpx;
  height: 480rpx;
}

.planet-two {
  bottom: 100rpx;
  left: -180rpx;
  width: 360rpx;
  height: 360rpx;
}

.brand {
  position: relative;
  z-index: 1;
  display: flex;
  padding-top: calc(var(--status-bar-height) + 100rpx);
  align-items: center;
  color: #fff;
  flex-direction: column;
}

.logo {
  display: flex;
  width: 116rpx;
  height: 116rpx;
  align-items: center;
  justify-content: center;
  color: #7559ee;
  font-size: 44rpx;
  font-weight: 900;
  background: #fff;
  border-radius: 38rpx;
  box-shadow: 0 18rpx 46rpx rgba(43, 26, 111, 0.25);
}

.brand-name {
  margin-top: 22rpx;
  font-size: 39rpx;
  font-weight: 800;
}

.brand-desc {
  margin-top: 10rpx;
  color: rgba(255, 255, 255, 0.7);
  font-size: 22rpx;
}

.mask {
  position: absolute;
  z-index: 5;
  right: 0;
  bottom: 0;
  left: 0;
  display: flex;
  min-height: 72vh;
  padding: 40rpx 32rpx calc(42rpx + env(safe-area-inset-bottom));
  align-items: flex-end;
  background: linear-gradient(180deg, rgba(32, 21, 76, 0), rgba(32, 21, 76, 0.3));
}

.dialog {
  width: 100%;
  padding: 42rpx 38rpx 30rpx;
  background: #fff;
  border-radius: 38rpx;
  box-shadow: 0 28rpx 80rpx rgba(33, 21, 83, 0.28);
}

.shield {
  display: flex;
  width: 64rpx;
  height: 64rpx;
  margin-bottom: 22rpx;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 29rpx;
  font-weight: 800;
  background: linear-gradient(145deg, #7357f6, #9a82ff);
  border-radius: 21rpx 21rpx 26rpx 26rpx;
}

.title {
  display: block;
  color: #29263c;
  font-size: 36rpx;
  font-weight: 800;
}

.content {
  display: block;
  margin-top: 24rpx;
  color: #6e6a7e;
  font-size: 25rpx;
  line-height: 1.85;
}

.link {
  color: #7357f6;
  font-weight: 700;
}

.agree-button,
.decline-button {
  display: flex;
  height: 92rpx;
  align-items: center;
  justify-content: center;
  font-size: 27rpx;
  border-radius: 26rpx;
}

.agree-button {
  margin-top: 34rpx;
  color: #fff;
  font-weight: 700;
  background: linear-gradient(135deg, #7357f6, #8e73fb);
  box-shadow: 0 14rpx 32rpx rgba(115, 87, 246, 0.22);
}

.decline-button {
  margin-top: 12rpx;
  color: #9b97a7;
  background: transparent;
}
</style>
