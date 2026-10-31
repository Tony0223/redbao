<template>
  <view class="page">
	  <button @click="testRedPacket" style="margin-top:100rpx;">测试红包群</button>
	  <button @click="testDjx" style="margin-top:20rpx;">测试短剧SDK</button>
	  
    <view class="hero">
      <view class="safe-top"></view>
      <view class="hero-decoration decoration-one"></view>
      <view class="hero-decoration decoration-two"></view>

      <view class="navbar">
        <view>
          <text class="eyebrow">HELLO，学习者</text>
          <text class="headline">今天也要进步一点点</text>
        </view>
        <view class="avatar pressable" @tap="goMine">答</view>
      </view>

      <view class="daily-card pressable" @tap="startTopic(dailyTopic)">
        <view class="daily-main">
          <view class="daily-icon">⚡</view>
          <view class="daily-copy">
            <view class="daily-title-line">
              <text class="daily-title">每日挑战</text>
              <text v-if="stats.today_completed" class="done-tag">已完成</text>
            </view>
            <text class="daily-desc">5 道精选题 · 约 3 分钟</text>
          </view>
        </view>
        <view class="start-button">
          <text>{{ stats.today_completed ? '再来一次' : '开始答题' }}</text>
          <text class="arrow">›</text>
        </view>
      </view>
    </view>

    <view class="content">
      <view class="stats-card">
        <view class="stat-item">
          <text class="stat-number">{{ stats.completed }}</text>
          <text class="stat-label">完成挑战</text>
        </view>
        <view class="divider"></view>
        <view class="stat-item">
          <text class="stat-number">{{ stats.accuracy }}<text class="percent">%</text></text>
          <text class="stat-label">答题正确率</text>
        </view>
        <view class="divider"></view>
        <view class="stat-item">
          <text class="stat-number">{{ topicCount }}</text>
          <text class="stat-label">可选题库</text>
        </view>
      </view>

      <view class="section-heading">
        <view>
          <text class="section-title">专项练习</text>
          <text class="section-subtitle">选择感兴趣的题库开始挑战</text>
        </view>
        <text class="book-icon">✦</text>
      </view>

      <view v-if="loading" class="loading-card">
        <view class="loading-dot"></view>
        <text>正在加载题库...</text>
      </view>

      <view v-else class="topic-list">
        <view
          v-for="topic in practiceTopics"
          :key="topic.id"
          class="topic-card pressable"
          @tap="startTopic(topic)"
        >
          <view class="topic-icon" :style="{ backgroundColor: topic.color + '18' }">
            <text>{{ topic.icon }}</text>
          </view>
          <view class="topic-copy">
            <text class="topic-name">{{ topic.name }}</text>
            <text class="topic-desc">{{ topic.description }}</text>
            <view class="topic-meta">
              <text>{{ topic.question_count }} 道题</text>
              <text class="dot">·</text>
              <text>单选题</text>
            </view>
          </view>
          <view class="topic-arrow">›</view>
        </view>
      </view>

      <view class="tip-card">
        <view class="tip-icon">💡</view>
        <view>
          <text class="tip-title">学习小贴士</text>
          <text class="tip-text">每天坚持练习，知识会在不知不觉中积累起来。</text>
        </view>
      </view>
    </view>

    <view class="tab-bar">
      <view class="tab-item is-active">
        <view class="home-icon">
          <view class="home-roof"></view>
          <view class="home-body"></view>
        </view>
        <text>首页</text>
      </view>
      <view class="tab-item pressable" @tap="goMine">
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
import { quizApi } from '../../common/api.js'

export default {
  data() {
    return {
      topics: [],
      loading: true,
      stats: {
        completed: 0,
        accuracy: 0,
        today_completed: false
      }
    }
  },
  computed: {
    dailyTopic() {
      return this.topics.find((item) => item.id === 'daily') || {
        id: 'daily',
        name: '每日挑战'
      }
    },
    practiceTopics() {
      return this.topics.filter((item) => item.id !== 'daily')
    },
    topicCount() {
      return this.topics.length
    }
  },
  onLoad() {
    this.loadData()
  },
  onShow() {
    if (this.topics.length) {
      this.loadStats()
    }
  },
  methods: {
    async loadData() {
      this.loading = true
      try {
        const result = await quizApi.getTopics()
        this.topics = result.items || []
        await this.loadStats()
      } catch (error) {
        uni.showToast({ title: error.message, icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    async loadStats() {
      try {
        this.stats = await quizApi.getStats()
      } catch (error) {
        // 题库仍可使用时，不用统计接口错误打断用户。
      }
    },
    startTopic(topic) {
      if (!topic || !topic.id) return
      uni.navigateTo({
        url: '/pages/quiz/quiz?id=' + encodeURIComponent(topic.id) +
          '&name=' + encodeURIComponent(topic.name)
      })
    },
    goMine() {
      uni.redirectTo({ url: '/pages/mine/mine' })
    },
	
	testRedPacket() {
	    const redpacket = uni.requireNativePlugin('tonyapp-redpacket-native')
	    redpacket.openRedPacket({}, (res) => {
	      uni.showModal({ content: JSON.stringify(res) })
	    })
	  },
	  testDjx() {
	    const djx = uni.requireNativePlugin('tonyapp-djx-native')
	    djx.initAdSdkOnly({
	      siteId: '5878709',
	      appName: '短剧888'
	    }, (res) => {
	      uni.showModal({ content: JSON.stringify(res) })
	    })
 	  }
  }
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  padding-bottom: calc(164rpx + env(safe-area-inset-bottom));
}

.hero {
  position: relative;
  height: 570rpx;
  overflow: hidden;
  padding: 0 36rpx;
  color: #fff;
  background: linear-gradient(145deg, #7559f7 0%, #694fe6 52%, #836af7 100%);
  border-radius: 0 0 64rpx 64rpx;
}

.hero-decoration {
  position: absolute;
  border: 2rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 50%;
}

.decoration-one {
  width: 360rpx;
  height: 360rpx;
  right: -164rpx;
  top: -80rpx;
}

.decoration-two {
  width: 190rpx;
  height: 190rpx;
  left: -92rpx;
  bottom: 26rpx;
}

.navbar {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 34rpx;
}

.eyebrow,
.headline,
.daily-desc,
.section-title,
.section-subtitle,
.topic-name,
.topic-desc,
.tip-title,
.tip-text {
  display: block;
}

.eyebrow {
  margin-bottom: 10rpx;
  color: rgba(255, 255, 255, 0.68);
  font-size: 22rpx;
  font-weight: 600;
  letter-spacing: 2rpx;
}

.headline {
  font-size: 38rpx;
  font-weight: 700;
  letter-spacing: 1rpx;
}

.avatar {
  display: flex;
  width: 78rpx;
  height: 78rpx;
  align-items: center;
  justify-content: center;
  color: #7053ed;
  font-size: 28rpx;
  font-weight: 800;
  background: rgba(255, 255, 255, 0.94);
  border: 6rpx solid rgba(255, 255, 255, 0.2);
  border-radius: 50%;
}

.daily-card {
  position: relative;
  z-index: 1;
  margin-top: 56rpx;
  padding: 34rpx 32rpx 30rpx;
  color: #292344;
  background: #fff;
  border-radius: 30rpx;
  box-shadow: 0 24rpx 60rpx rgba(53, 34, 129, 0.24);
}

.daily-main,
.daily-title-line,
.start-button {
  display: flex;
  align-items: center;
}

.daily-icon {
  display: flex;
  width: 88rpx;
  height: 88rpx;
  margin-right: 24rpx;
  align-items: center;
  justify-content: center;
  font-size: 44rpx;
  background: linear-gradient(145deg, #fff4cf, #ffe797);
  border-radius: 26rpx;
}

.daily-copy {
  flex: 1;
}

.daily-title {
  font-size: 34rpx;
  font-weight: 700;
}

.done-tag {
  margin-left: 14rpx;
  padding: 5rpx 12rpx;
  color: #20a77f;
  font-size: 19rpx;
  background: #e5f8f1;
  border-radius: 20rpx;
}

.daily-desc {
  margin-top: 10rpx;
  color: #9994aa;
  font-size: 24rpx;
}

.start-button {
  height: 78rpx;
  margin-top: 30rpx;
  justify-content: center;
  color: #fff;
  font-size: 28rpx;
  font-weight: 600;
  background: linear-gradient(100deg, #7658f8, #8a6cff);
  border-radius: 22rpx;
}

.arrow {
  margin-left: 12rpx;
  font-size: 42rpx;
  font-weight: 300;
  line-height: 1;
}

.content {
  padding: 0 32rpx;
}

.stats-card {
  display: flex;
  height: 146rpx;
  margin-top: -10rpx;
  align-items: center;
  justify-content: space-around;
  background: #fff;
  border: 1rpx solid #efedf7;
  border-radius: 28rpx;
  box-shadow: 0 12rpx 36rpx rgba(37, 31, 73, 0.06);
}

.stat-item {
  display: flex;
  width: 31%;
  align-items: center;
  flex-direction: column;
}

.stat-number {
  color: #312d46;
  font-size: 37rpx;
  font-weight: 800;
}

.percent {
  margin-left: 2rpx;
  font-size: 23rpx;
}

.stat-label {
  margin-top: 9rpx;
  color: #aaa6b8;
  font-size: 21rpx;
}

.divider {
  width: 1rpx;
  height: 56rpx;
  background: #eceaf2;
}

.section-heading {
  display: flex;
  margin: 50rpx 4rpx 25rpx;
  align-items: center;
  justify-content: space-between;
}

.section-title {
  font-size: 34rpx;
  font-weight: 700;
}

.section-subtitle {
  margin-top: 8rpx;
  color: #a5a1b3;
  font-size: 22rpx;
}

.book-icon {
  color: #8064fa;
  font-size: 42rpx;
}

.loading-card {
  display: flex;
  height: 150rpx;
  align-items: center;
  justify-content: center;
  color: #9691a8;
  font-size: 25rpx;
  background: #fff;
  border-radius: 26rpx;
}

.loading-dot {
  width: 18rpx;
  height: 18rpx;
  margin-right: 14rpx;
  background: #795cf7;
  border-radius: 50%;
}

.topic-card {
  display: flex;
  min-height: 190rpx;
  margin-bottom: 22rpx;
  padding: 30rpx 24rpx;
  align-items: center;
  background: #fff;
  border: 1rpx solid #efedf5;
  border-radius: 28rpx;
  box-shadow: 0 12rpx 32rpx rgba(43, 35, 82, 0.045);
}

.topic-icon {
  display: flex;
  width: 94rpx;
  height: 94rpx;
  margin-right: 24rpx;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  font-size: 43rpx;
  border-radius: 28rpx;
}

.topic-copy {
  min-width: 0;
  flex: 1;
}

.topic-name {
  font-size: 30rpx;
  font-weight: 700;
}

.topic-desc {
  overflow: hidden;
  margin-top: 8rpx;
  color: #9f9aad;
  font-size: 22rpx;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topic-meta {
  display: flex;
  margin-top: 13rpx;
  color: #b2aebe;
  font-size: 20rpx;
}

.dot {
  margin: 0 10rpx;
}

.topic-arrow {
  margin-left: 12rpx;
  color: #c4c0ce;
  font-size: 46rpx;
  font-weight: 300;
}

.tip-card {
  display: flex;
  margin-top: 38rpx;
  padding: 26rpx;
  color: #6f5f32;
  background: #fff9e9;
  border: 1rpx solid #f7eccb;
  border-radius: 24rpx;
}

.tip-icon {
  margin-right: 18rpx;
  font-size: 34rpx;
}

.tip-title {
  font-size: 24rpx;
  font-weight: 700;
}

.tip-text {
  margin-top: 7rpx;
  color: #9d8d62;
  font-size: 21rpx;
  line-height: 1.5;
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
