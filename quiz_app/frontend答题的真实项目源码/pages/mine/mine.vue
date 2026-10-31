<template>
  <view class="page">
    <view class="profile-hero">
      <view class="safe-top"></view>
      <view class="glow glow-one"></view>
      <view class="glow glow-two"></view>

      <view class="top-bar">
        <text class="page-title">我的</text>
      </view>

      <view class="profile-row">
        <view class="avatar-wrap">
          <view class="avatar">{{ avatarText }}</view>
          <view v-if="user" class="online-dot"></view>
        </view>
        <view class="profile-copy">
          <text class="nickname">{{ user ? user.username : '尚未登录' }}</text>
          <text class="profile-slogan">{{ user ? user.email : '登录后同步学习记录与成就' }}</text>
          <view class="level-chip">LV.{{ level }} · {{ levelName }}</view>
        </view>
      </view>

    </view>

    <view class="content">
      <view class="overview-card">
        <view class="overview-item">
          <text class="overview-number">{{ stats.completed }}</text>
          <text class="overview-label">累计挑战</text>
        </view>
        <view class="overview-divider"></view>
        <view class="overview-item">
          <text class="overview-number">{{ stats.accuracy }}<text class="number-unit">%</text></text>
          <text class="overview-label">平均正确率</text>
        </view>
        <view class="overview-divider"></view>
        <view class="overview-item">
          <text class="overview-status" :class="{ checked: stats.today_completed }">
            {{ stats.today_completed ? '已打卡' : '待打卡' }}
          </text>
          <text class="overview-label">今日学习</text>
        </view>
      </view>

      <view v-if="!user" class="account-card">
        <view class="account-copy">
          <text class="account-title">开启专属学习档案</text>
          <text class="account-desc">注册或登录后，答题数据将按账号保存</text>
        </view>
        <view class="account-actions">
          <button class="login-button pressable" @tap="goAuth('login')">登录</button>
          <button class="register-button pressable" @tap="goAuth('register')">注册</button>
        </view>
      </view>

      <view class="section-title-row">
        <text class="section-title">学习成长</text>
        <text class="section-note">每一次练习都算数</text>
      </view>

      <view class="growth-card">
        <view class="growth-heading">
          <view class="growth-icon">✦</view>
          <view class="growth-copy">
            <text class="growth-title">距离下一等级</text>
            <text class="growth-desc">再完成 {{ remainingChallenges }} 次挑战即可升级</text>
          </view>
          <text class="growth-percent">{{ levelProgress }}%</text>
        </view>
        <view class="progress-track">
          <view class="progress-value" :style="{ width: levelProgress + '%' }"></view>
        </view>
        <view class="progress-meta">
          <text>LV.{{ level }}</text>
          <text>LV.{{ level + 1 }}</text>
        </view>
      </view>

      <view class="achievement-grid">
        <view class="achievement-card" :class="{ unlocked: stats.completed >= 1 }">
          <view class="achievement-icon">🌱</view>
          <text class="achievement-name">初次启程</text>
          <text class="achievement-desc">完成首次挑战</text>
        </view>
        <view class="achievement-card" :class="{ unlocked: stats.accuracy >= 80 }">
          <view class="achievement-icon">🏆</view>
          <text class="achievement-name">答题达人</text>
          <text class="achievement-desc">正确率达到 80%</text>
        </view>
      </view>

      <view class="menu-card">
        <template v-if="user">
          <view class="menu-item pressable" @tap="openAccountSettings">
            <view class="menu-icon blue">安</view>
            <view class="menu-copy">
              <text class="menu-title">账号与安全</text>
              <text class="menu-desc">管理登录状态与注销账号</text>
            </view>
            <text class="menu-arrow">›</text>
          </view>
          <view class="menu-line"></view>
        </template>
        <view class="menu-item pressable" @tap="goHome">
          <view class="menu-icon purple">⌁</view>
          <view class="menu-copy">
            <text class="menu-title">继续练习</text>
            <text class="menu-desc">去发现更多有趣题目</text>
          </view>
          <text class="menu-arrow">›</text>
        </view>
        <view class="menu-line"></view>
        <view class="menu-item pressable" @tap="openPrivacy">
          <view class="menu-icon green">盾</view>
          <view class="menu-copy">
            <text class="menu-title">隐私政策</text>
            <text class="menu-desc">查看个人信息处理规则</text>
          </view>
          <text class="menu-arrow">›</text>
        </view>
        <view class="menu-line"></view>
        <view class="menu-item pressable" @tap="openAgreement">
          <view class="menu-icon blue">约</view>
          <view class="menu-copy">
            <text class="menu-title">用户协议</text>
            <text class="menu-desc">查看产品使用规则</text>
          </view>
          <text class="menu-arrow">›</text>
        </view>
        <view class="menu-line"></view>
        <view class="menu-item pressable" @tap="showAbout">
          <view class="menu-icon yellow">i</view>
          <view class="menu-copy">
            <text class="menu-title">关于答题星球</text>
            <text class="menu-desc">让学习轻松一点</text>
          </view>
          <text class="menu-arrow">›</text>
        </view>
        <template v-if="user">
          <view class="menu-line"></view>
          <view class="menu-item pressable" @tap="confirmLogout">
            <view class="menu-icon red">退</view>
            <view class="menu-copy">
              <text class="menu-title">退出登录</text>
              <text class="menu-desc">退出当前账号</text>
            </view>
            <text class="menu-arrow">›</text>
          </view>
        </template>
      </view>

      <text class="footer-text">今天也在认真成长 · 金石速答</text>
    </view>

    <view class="tab-bar">
      <view class="tab-item pressable" @tap="goHome">
        <view class="home-icon">
          <view class="home-roof"></view>
          <view class="home-body"></view>
        </view>
        <text>首页</text>
      </view>
      <view class="tab-item is-active">
        <view class="user-icon">
          <view class="user-head"></view>
          <view class="user-body"></view>
        </view>
        <text>我的</text>
      </view>
    </view>
  </view>
</template>

<script>
import { authApi, quizApi } from '../../common/api.js'
import { clearAuth, getStoredUser, getToken } from '../../common/auth.js'

export default {
  data() {
    return {
      stats: {
        completed: 0,
        accuracy: 0,
        today_completed: false
      },
      loading: false,
      user: null
    }
  },
  computed: {
    level() {
      return Math.floor(this.stats.completed / 5) + 1
    },
    levelName() {
      if (this.level >= 5) return '知识探索家'
      if (this.level >= 3) return '进阶学习者'
      return '好奇新星'
    },
    levelProgress() {
      return Math.round((this.stats.completed % 5) / 5 * 100)
    },
    remainingChallenges() {
      const remaining = 5 - (this.stats.completed % 5)
      return remaining || 5
    },
    avatarText() {
      return this.user && this.user.username ? this.user.username.slice(0, 1) : '答'
    }
  },
  onLoad() {
    this.user = getStoredUser()
    this.loadStats()
  },
  onShow() {
    this.user = getStoredUser()
    this.refreshUser()
    this.loadStats()
  },
  methods: {
    async loadStats() {
      if (this.loading) return
      this.loading = true
      try {
        this.stats = await quizApi.getStats()
      } catch (error) {
        uni.showToast({ title: '学习数据暂未同步', icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    goHome() {
      uni.redirectTo({ url: '/pages/index/index' })
    },
    goAuth(mode) {
      uni.navigateTo({ url: '/pages/auth/auth?mode=' + mode })
    },
    async refreshUser() {
      if (!getToken()) {
        this.user = null
        return
      }
      try {
        const result = await authApi.getMe()
        this.user = result.user
        uni.setStorageSync('quiz_auth_user', result.user)
      } catch (error) {
        this.user = null
      }
    },
    openPrivacy() {
      uni.navigateTo({ url: '/pages/privacy/privacy' })
    },
    openAgreement() {
      uni.navigateTo({ url: '/pages/agreement/agreement' })
    },
    openAccountSettings() {
      uni.navigateTo({ url: '/pages/account/settings' })
    },
    confirmLogout() {
      uni.showModal({
        title: '退出登录',
        content: '确定要退出当前账号吗？',
        confirmText: '退出',
        confirmColor: '#e15c65',
        success: async (result) => {
          if (!result.confirm) return
          try {
            await authApi.logout()
          } catch (error) {
            // 即使服务器暂时不可用，也允许清除本机登录状态。
          }
          clearAuth()
          this.user = null
          await this.loadStats()
          uni.showToast({ title: '已退出登录', icon: 'none' })
        }
      })
    },
    showAbout() {
      uni.showModal({
        title: '金石速答',
        content: '每天进步一点点，让学习成为一件轻松、有成就感的事。',
        showCancel: false,
        confirmText: '知道了',
        confirmColor: '#7357f6'
      })
    }
  }
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  padding-bottom: calc(164rpx + env(safe-area-inset-bottom));
  background: #f6f7fb;
}

.profile-hero {
  position: relative;
  height: 430rpx;
  overflow: hidden;
  padding: 0 36rpx;
  color: #fff;
  background: linear-gradient(145deg, #7255f3 0%, #7c60f5 55%, #947dfb 100%);
  border-radius: 0 0 62rpx 62rpx;
}

.glow {
  position: absolute;
  background: rgba(255, 255, 255, 0.08);
  border: 2rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 50%;
}

.glow-one {
  top: -118rpx;
  right: -80rpx;
  width: 310rpx;
  height: 310rpx;
}

.glow-two {
  bottom: -140rpx;
  left: -80rpx;
  width: 260rpx;
  height: 260rpx;
}

.top-bar {
  position: relative;
  z-index: 1;
  display: flex;
  height: 96rpx;
  align-items: center;
  justify-content: space-between;
}

.page-title {
  font-size: 38rpx;
  font-weight: 800;
}

.profile-row {
  position: relative;
  z-index: 1;
  display: flex;
  margin-top: 35rpx;
  align-items: center;
}

.avatar-wrap {
  position: relative;
  margin-right: 30rpx;
}

.avatar {
  display: flex;
  width: 132rpx;
  height: 132rpx;
  align-items: center;
  justify-content: center;
  color: #7559ee;
  font-size: 46rpx;
  font-weight: 900;
  background: linear-gradient(145deg, #fff, #eeeaff);
  border: 8rpx solid rgba(255, 255, 255, 0.19);
  border-radius: 42rpx;
  box-shadow: 0 18rpx 40rpx rgba(48, 28, 124, 0.2);
}

.online-dot {
  position: absolute;
  right: -3rpx;
  bottom: -3rpx;
  width: 30rpx;
  height: 30rpx;
  background: #51ddaa;
  border: 7rpx solid #8065f1;
  border-radius: 50%;
}

.profile-copy,
.nickname,
.profile-slogan,
.overview-label,
.growth-title,
.growth-desc,
.achievement-name,
.achievement-desc,
.menu-title,
.menu-desc {
  display: block;
}

.profile-copy {
  flex: 1;
}

.nickname {
  font-size: 37rpx;
  font-weight: 800;
}

.profile-slogan {
  margin-top: 9rpx;
  color: rgba(255, 255, 255, 0.68);
  font-size: 22rpx;
}

.level-chip {
  display: inline-flex;
  margin-top: 18rpx;
  padding: 8rpx 17rpx;
  color: #ffe99f;
  font-size: 20rpx;
  font-weight: 700;
  background: rgba(45, 27, 119, 0.22);
  border-radius: 20rpx;
}

.content {
  padding: 0 32rpx;
}

.overview-card {
  position: relative;
  z-index: 2;
  display: flex;
  height: 150rpx;
  margin-top: -34rpx;
  align-items: center;
  justify-content: space-around;
  background: #fff;
  border: 1rpx solid #eeebf7;
  border-radius: 30rpx;
  box-shadow: 0 18rpx 46rpx rgba(51, 40, 93, 0.09);
}

.overview-item {
  display: flex;
  width: 31%;
  align-items: center;
  flex-direction: column;
}

.overview-number {
  color: #302c47;
  font-size: 39rpx;
  font-weight: 800;
}

.overview-status {
  color: #a29dac;
  font-size: 28rpx;
  font-weight: 800;
}

.overview-status.checked {
  color: #23b68a;
}

.number-unit {
  margin-left: 2rpx;
  font-size: 23rpx;
}

.overview-label {
  margin-top: 8rpx;
  color: #aaa6b8;
  font-size: 20rpx;
}

.overview-divider {
  width: 1rpx;
  height: 55rpx;
  background: #eceaf2;
}

.account-card {
  display: flex;
  margin-top: 24rpx;
  padding: 26rpx 25rpx;
  align-items: center;
  background: linear-gradient(135deg, #f0ecff, #faf9ff);
  border: 1rpx solid #e4ddff;
  border-radius: 26rpx;
}

.account-copy {
  flex: 1;
}

.account-title,
.account-desc {
  display: block;
}

.account-title {
  color: #46398a;
  font-size: 25rpx;
  font-weight: 800;
}

.account-desc {
  margin-top: 7rpx;
  color: #8e86ac;
  font-size: 18rpx;
}

.account-actions {
  display: flex;
  margin-left: 15rpx;
  gap: 10rpx;
}

.login-button,
.register-button {
  display: flex;
  width: 94rpx;
  height: 64rpx;
  padding: 0;
  align-items: center;
  justify-content: center;
  font-size: 21rpx;
  font-weight: 700;
  border-radius: 18rpx;
}

.login-button {
  color: #7357f6;
  background: #fff;
  border: 1rpx solid #dcd4ff;
}

.register-button {
  color: #fff;
  background: #7357f6;
}

.section-title-row {
  display: flex;
  margin: 46rpx 4rpx 24rpx;
  align-items: flex-end;
  justify-content: space-between;
}

.section-title {
  color: #302d43;
  font-size: 33rpx;
  font-weight: 800;
}

.section-note {
  color: #aaa6b8;
  font-size: 20rpx;
}

.growth-card {
  padding: 29rpx 28rpx 25rpx;
  background: linear-gradient(145deg, #fff 0%, #fbfaff 100%);
  border: 1rpx solid #ece8f8;
  border-radius: 28rpx;
  box-shadow: 0 12rpx 32rpx rgba(45, 37, 81, 0.045);
}

.growth-heading {
  display: flex;
  align-items: center;
}

.growth-icon {
  display: flex;
  width: 76rpx;
  height: 76rpx;
  margin-right: 20rpx;
  align-items: center;
  justify-content: center;
  color: #7357f6;
  font-size: 34rpx;
  background: #eeeaff;
  border-radius: 22rpx;
}

.growth-copy {
  flex: 1;
}

.growth-title {
  font-size: 27rpx;
  font-weight: 700;
}

.growth-desc {
  margin-top: 7rpx;
  color: #a29dac;
  font-size: 20rpx;
}

.growth-percent {
  color: #7357f6;
  font-size: 28rpx;
  font-weight: 800;
}

.progress-track {
  height: 13rpx;
  margin-top: 25rpx;
  overflow: hidden;
  background: #eeebf5;
  border-radius: 10rpx;
}

.progress-value {
  height: 100%;
  min-width: 10rpx;
  background: linear-gradient(90deg, #7357f6, #9a83ff);
  border-radius: 10rpx;
  transition: width 0.35s ease;
}

.progress-meta {
  display: flex;
  margin-top: 10rpx;
  justify-content: space-between;
  color: #b0acbd;
  font-size: 18rpx;
}

.achievement-grid {
  display: flex;
  margin-top: 22rpx;
  gap: 20rpx;
}

.achievement-card {
  position: relative;
  overflow: hidden;
  width: calc(50% - 10rpx);
  padding: 25rpx 22rpx;
  opacity: 0.55;
  background: #fff;
  border: 1rpx solid #ece9f2;
  border-radius: 25rpx;
}

.achievement-card.unlocked {
  opacity: 1;
  border-color: #e5defe;
  box-shadow: 0 10rpx 26rpx rgba(67, 50, 128, 0.05);
}

.achievement-icon {
  font-size: 38rpx;
}

.achievement-name {
  margin-top: 14rpx;
  font-size: 25rpx;
  font-weight: 700;
}

.achievement-desc {
  margin-top: 6rpx;
  color: #a9a5b4;
  font-size: 18rpx;
}

.menu-card {
  margin-top: 34rpx;
  padding: 0 24rpx;
  background: #fff;
  border: 1rpx solid #eceaf3;
  border-radius: 28rpx;
}

.menu-item {
  display: flex;
  min-height: 126rpx;
  align-items: center;
}

.menu-icon {
  display: flex;
  width: 70rpx;
  height: 70rpx;
  margin-right: 20rpx;
  align-items: center;
  justify-content: center;
  font-size: 29rpx;
  font-weight: 800;
  border-radius: 21rpx;
}

.menu-icon.purple {
  color: #7256f1;
  background: #eeeaff;
}

.menu-icon.blue {
  color: #4c7ee8;
  font-size: 22rpx;
  background: #eaf1ff;
}

.menu-icon.yellow {
  color: #dc9a22;
  background: #fff4d7;
}

.menu-icon.green {
  color: #239d7e;
  font-size: 22rpx;
  background: #e5f8f1;
}

.menu-icon.red {
  color: #d95762;
  font-size: 22rpx;
  background: #fff0f1;
}

.menu-copy {
  flex: 1;
}

.menu-title {
  font-size: 26rpx;
  font-weight: 700;
}

.menu-desc {
  margin-top: 7rpx;
  color: #aaa6b5;
  font-size: 19rpx;
}

.menu-arrow {
  color: #c6c2ce;
  font-size: 42rpx;
  font-weight: 300;
}

.menu-line {
  height: 1rpx;
  margin-left: 90rpx;
  background: #efedf3;
}

.footer-text {
  display: block;
  margin: 35rpx 0 10rpx;
  color: #bbb7c5;
  font-size: 19rpx;
  text-align: center;
}

.tab-bar {
  position: fixed;
  z-index: 20;
  right: 24rpx;
  bottom: 20rpx;
  left: 24rpx;
  display: flex;
  height: calc(104rpx + env(safe-area-inset-bottom));
  padding: 10rpx 88rpx env(safe-area-inset-bottom);
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.96);
  border: 1rpx solid rgba(226, 222, 239, 0.9);
  border-radius: 32rpx;
  box-shadow: 0 14rpx 44rpx rgba(48, 38, 88, 0.14);
}

.tab-item {
  display: flex;
  width: 96rpx;
  height: 82rpx;
  align-items: center;
  justify-content: center;
  color: #aaa6b8;
  font-size: 20rpx;
  flex-direction: column;
}

.tab-item.is-active {
  color: #7357f6;
  font-weight: 700;
}

.home-icon,
.user-icon {
  position: relative;
  width: 42rpx;
  height: 40rpx;
  margin-bottom: 5rpx;
}

.home-roof {
  position: absolute;
  top: 3rpx;
  left: 9rpx;
  width: 24rpx;
  height: 24rpx;
  border-top: 5rpx solid currentColor;
  border-left: 5rpx solid currentColor;
  border-radius: 4rpx 0 0;
  transform: rotate(45deg);
}

.home-body {
  position: absolute;
  right: 8rpx;
  bottom: 1rpx;
  left: 8rpx;
  height: 23rpx;
  background: currentColor;
  border-radius: 3rpx 3rpx 8rpx 8rpx;
}

.user-head {
  width: 17rpx;
  height: 17rpx;
  margin: 1rpx auto 3rpx;
  border: 4rpx solid currentColor;
  border-radius: 50%;
}

.user-body {
  width: 34rpx;
  height: 17rpx;
  margin: 0 auto;
  border: 4rpx solid currentColor;
  border-bottom: 0;
  border-radius: 22rpx 22rpx 4rpx 4rpx;
}
</style>
