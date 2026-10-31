<template>
  <view class="page">
    <view class="top-area">
      <view class="safe-top"></view>
      <view class="nav-bar">
        <view class="back-button pressable" @tap="goBack">‹</view>
        <text class="nav-title">{{ topicName }}</text>
        <view class="counter">{{ finished ? questions.length : currentIndex + 1 }}/{{ questions.length || 5 }}</view>
      </view>

      <view v-if="!finished" class="progress-wrap">
        <view class="progress-info">
          <text>答题进度</text>
          <text>{{ progressPercent }}%</text>
        </view>
        <view class="progress-track">
          <view class="progress-bar" :style="{ width: progressPercent + '%' }"></view>
        </view>
      </view>
    </view>

    <view v-if="loading" class="state-page">
      <view class="spinner"></view>
      <text class="state-title">题目准备中</text>
      <text class="state-desc">马上开始今天的挑战</text>
    </view>

    <view v-else-if="loadError" class="state-page">
      <view class="state-emoji">📡</view>
      <text class="state-title">题目加载失败</text>
      <text class="state-desc">{{ loadError }}</text>
      <button class="primary-button short-button" @tap="loadQuestions">重新加载</button>
    </view>

    <view v-else-if="finished" class="result-page">
      <view class="result-glow glow-left"></view>
      <view class="result-glow glow-right"></view>
      <view class="result-card">
        <view class="medal-wrap">
          <view class="medal-rays">✦</view>
          <view class="medal">{{ resultEmoji }}</view>
        </view>
        <text class="result-title">{{ resultTitle }}</text>
        <text class="result-subtitle">本次挑战已完成，继续保持学习的节奏</text>

        <view class="score-ring">
          <view class="score-inner">
            <text class="score-number">{{ score }}</text>
            <text class="score-total">/ {{ questions.length }}</text>
          </view>
        </view>
        <text class="accuracy-text">正确率 {{ accuracy }}%</text>

        <view class="result-stats">
          <view class="result-stat">
            <text class="result-stat-icon success">✓</text>
            <text class="result-stat-value">{{ score }}</text>
            <text class="result-stat-label">答对</text>
          </view>
          <view class="result-stat-separator"></view>
          <view class="result-stat">
            <text class="result-stat-icon error">×</text>
            <text class="result-stat-value">{{ questions.length - score }}</text>
            <text class="result-stat-label">答错</text>
          </view>
          <view class="result-stat-separator"></view>
          <view class="result-stat">
            <text class="result-stat-icon time">◷</text>
            <text class="result-stat-value">{{ durationText }}</text>
            <text class="result-stat-label">用时</text>
          </view>
        </view>
      </view>

      <button class="primary-button" @tap="restart">再答一次</button>
      <button class="secondary-button" @tap="goHome">返回首页</button>
    </view>

    <view v-else-if="currentQuestion" class="quiz-content">
      <view class="question-card">
        <view class="question-meta">
          <text class="type-tag">单选题</text>
          <text class="question-number">QUESTION {{ padNumber(currentIndex + 1) }}</text>
        </view>
        <text class="question-title">{{ currentQuestion.title }}</text>
      </view>

      <view class="options-list">
        <view
          v-for="(option, index) in currentQuestion.options"
          :key="index"
          class="option pressable"
          :class="optionClass(index)"
          @tap="selectAnswer(index)"
        >
          <view class="option-letter">{{ letters[index] }}</view>
          <text class="option-text">{{ option }}</text>
          <view v-if="answerResult && index === answerResult.correct_answer" class="status-icon correct-icon">✓</view>
          <view
            v-else-if="answerResult && index === selectedAnswer && !answerResult.correct"
            class="status-icon wrong-icon"
          >×</view>
        </view>
      </view>

      <view v-if="checking" class="checking-tip">
        <view class="mini-spinner"></view>
        <text>正在核对答案...</text>
      </view>

      <view v-if="answerResult" class="explanation-card" :class="answerResult.correct ? 'correct-card' : 'wrong-card'">
        <view class="explanation-heading">
          <view class="heading-icon">{{ answerResult.correct ? '✓' : '!' }}</view>
          <text>{{ answerResult.correct ? '回答正确' : '回答错误' }}</text>
        </view>
        <text class="explanation-title">答案解析</text>
        <text class="explanation-text">{{ answerResult.explanation }}</text>
      </view>

      <view class="bottom-space"></view>
      <view class="action-bar">
        <button
          class="previous-button"
          :disabled="currentIndex === 0"
          @tap="previousQuestion"
        >上一题</button>
        <button
          class="next-button"
          :class="{ disabled: !answerResult }"
          :disabled="!answerResult"
          @tap="nextQuestion"
        >
          {{ currentIndex === questions.length - 1 ? '完成答题' : '下一题' }}
          <text class="button-arrow">›</text>
        </button>
      </view>
    </view>
  </view>
</template>

<script>
import { quizApi } from '../../common/api.js'

export default {
  data() {
    return {
      topicId: 'daily',
      topicName: '每日挑战',
      questions: [],
      currentIndex: 0,
      selectedAnswer: null,
      answerResult: null,
      answers: {},
      loading: true,
      checking: false,
      loadError: '',
      finished: false,
      startedAt: Date.now(),
      durationSeconds: 0,
      letters: ['A', 'B', 'C', 'D', 'E', 'F']
    }
  },
  computed: {
    currentQuestion() {
      return this.questions[this.currentIndex] || null
    },
    progressPercent() {
      if (!this.questions.length) return 0
      return Math.round(((this.currentIndex + (this.answerResult ? 1 : 0)) / this.questions.length) * 100)
    },
    score() {
      return Object.keys(this.answers).filter((key) => this.answers[key].correct).length
    },
    accuracy() {
      if (!this.questions.length) return 0
      return Math.round(this.score * 100 / this.questions.length)
    },
    resultTitle() {
      if (this.accuracy === 100) return '太棒了，全部答对！'
      if (this.accuracy >= 80) return '表现优秀！'
      if (this.accuracy >= 60) return '挑战完成！'
      return '继续加油！'
    },
    resultEmoji() {
      if (this.accuracy >= 80) return '🏆'
      if (this.accuracy >= 60) return '🎉'
      return '💪'
    },
    durationText() {
      if (this.durationSeconds < 60) return this.durationSeconds + '秒'
      return Math.floor(this.durationSeconds / 60) + '分' + (this.durationSeconds % 60) + '秒'
    }
  },
  onLoad(options) {
    this.topicId = options.id ? decodeURIComponent(options.id) : 'daily'
    this.topicName = options.name ? decodeURIComponent(options.name) : '每日挑战'
    this.loadQuestions()
  },
  methods: {
    async loadQuestions() {
      this.loading = true
      this.loadError = ''
      try {
        const result = await quizApi.getQuestions(this.topicId)
        this.questions = result.items || []
        this.topicName = result.topic.name
        this.resetQuiz()
      } catch (error) {
        this.loadError = error.message
      } finally {
        this.loading = false
      }
    },
    resetQuiz() {
      this.currentIndex = 0
      this.selectedAnswer = null
      this.answerResult = null
      this.answers = {}
      this.finished = false
      this.startedAt = Date.now()
      this.durationSeconds = 0
    },
    async selectAnswer(index) {
      if (this.answerResult || this.checking) return
      this.selectedAnswer = index
      this.checking = true
      try {
        const result = await quizApi.checkAnswer(this.currentQuestion.id, index)
        this.answerResult = result
        this.$set(this.answers, this.currentQuestion.id, {
          selected: index,
          correct: result.correct,
          result: result
        })
        if (result.correct) {
          uni.vibrateShort({ success: function () {} })
        }
      } catch (error) {
        this.selectedAnswer = null
        uni.showToast({ title: error.message, icon: 'none' })
      } finally {
        this.checking = false
      }
    },
    optionClass(index) {
      if (this.answerResult) {
        if (index === this.answerResult.correct_answer) return 'is-correct'
        if (index === this.selectedAnswer && !this.answerResult.correct) return 'is-wrong'
      }
      if (index === this.selectedAnswer) return 'is-selected'
      return ''
    },
    previousQuestion() {
      if (this.currentIndex === 0) return
      this.currentIndex -= 1
      this.restoreAnswer()
    },
    nextQuestion() {
      if (!this.answerResult) return
      if (this.currentIndex === this.questions.length - 1) {
        this.completeQuiz()
        return
      }
      this.currentIndex += 1
      this.restoreAnswer()
    },
    restoreAnswer() {
      const saved = this.answers[this.currentQuestion.id]
      this.selectedAnswer = saved ? saved.selected : null
      this.answerResult = saved ? saved.result : null
    },
    async completeQuiz() {
      this.durationSeconds = Math.max(1, Math.round((Date.now() - this.startedAt) / 1000))
      this.finished = true
      try {
        await quizApi.saveResult({
          topic_id: this.topicId,
          correct_count: this.score,
          total_count: this.questions.length,
          duration_seconds: this.durationSeconds
        })
      } catch (error) {
        uni.showToast({ title: '成绩暂未同步', icon: 'none' })
      }
    },
    restart() {
      this.resetQuiz()
    },
    goBack() {
      uni.navigateBack({
        fail: () => uni.reLaunch({ url: '/pages/index/index' })
      })
    },
    goHome() {
      uni.reLaunch({ url: '/pages/index/index' })
    },
    padNumber(value) {
      return value < 10 ? '0' + value : String(value)
    }
  }
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f6f7fb;
}

.top-area {
  padding: 0 32rpx 34rpx;
  color: #fff;
  background: linear-gradient(135deg, #7255f3, #8267f8);
  border-radius: 0 0 42rpx 42rpx;
  box-shadow: 0 14rpx 32rpx rgba(103, 75, 225, 0.18);
}

.nav-bar {
  display: flex;
  height: 96rpx;
  align-items: center;
  justify-content: space-between;
}

.back-button {
  display: flex;
  width: 66rpx;
  height: 66rpx;
  align-items: center;
  justify-content: center;
  font-size: 58rpx;
  font-weight: 200;
  line-height: 1;
  background: rgba(255, 255, 255, 0.14);
  border-radius: 20rpx;
}

.nav-title {
  max-width: 390rpx;
  overflow: hidden;
  font-size: 30rpx;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.counter {
  min-width: 66rpx;
  color: rgba(255, 255, 255, 0.82);
  font-size: 24rpx;
  text-align: right;
}

.progress-wrap {
  margin-top: 8rpx;
}

.progress-info {
  display: flex;
  margin-bottom: 14rpx;
  justify-content: space-between;
  color: rgba(255, 255, 255, 0.72);
  font-size: 21rpx;
}

.progress-track {
  height: 12rpx;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.18);
  border-radius: 8rpx;
}

.progress-bar {
  height: 100%;
  background: #fff;
  border-radius: 8rpx;
  transition: width 0.3s ease;
}

.state-page {
  display: flex;
  min-height: 650rpx;
  padding: 90rpx 50rpx;
  align-items: center;
  flex-direction: column;
  justify-content: center;
  text-align: center;
}

.spinner,
.mini-spinner {
  border-style: solid;
  border-color: #dfdaf8;
  border-top-color: #775af4;
  border-radius: 50%;
  animation: rotate 0.8s linear infinite;
}

.spinner {
  width: 62rpx;
  height: 62rpx;
  margin-bottom: 30rpx;
  border-width: 6rpx;
}

.mini-spinner {
  width: 28rpx;
  height: 28rpx;
  margin-right: 14rpx;
  border-width: 4rpx;
}

@keyframes rotate {
  to { transform: rotate(360deg); }
}

.state-emoji {
  margin-bottom: 24rpx;
  font-size: 74rpx;
}

.state-title,
.state-desc {
  display: block;
}

.state-title {
  color: #302c45;
  font-size: 32rpx;
  font-weight: 700;
}

.state-desc {
  margin-top: 14rpx;
  color: #aaa5b8;
  font-size: 24rpx;
  line-height: 1.6;
}

.quiz-content {
  padding: 34rpx 30rpx 0;
}

.question-card {
  padding: 34rpx 32rpx 40rpx;
  background: #fff;
  border: 1rpx solid #eeecf5;
  border-radius: 30rpx;
  box-shadow: 0 14rpx 40rpx rgba(47, 39, 91, 0.055);
}

.question-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.type-tag {
  padding: 8rpx 18rpx;
  color: #7357ee;
  font-size: 21rpx;
  font-weight: 600;
  background: #efebff;
  border-radius: 24rpx;
}

.question-number {
  color: #c0bccb;
  font-size: 19rpx;
  font-weight: 600;
  letter-spacing: 1rpx;
}

.question-title {
  display: block;
  margin-top: 34rpx;
  color: #29263b;
  font-size: 35rpx;
  font-weight: 700;
  line-height: 1.55;
}

.options-list {
  margin-top: 28rpx;
}

.option {
  display: flex;
  min-height: 104rpx;
  margin-bottom: 20rpx;
  padding: 20rpx 22rpx;
  align-items: center;
  background: #fff;
  border: 3rpx solid transparent;
  border-radius: 25rpx;
  box-shadow: 0 8rpx 28rpx rgba(46, 37, 86, 0.045);
}

.option-letter {
  display: flex;
  width: 58rpx;
  height: 58rpx;
  margin-right: 20rpx;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  color: #756f84;
  font-size: 24rpx;
  font-weight: 700;
  background: #f3f2f7;
  border-radius: 18rpx;
}

.option-text {
  flex: 1;
  color: #4a465b;
  font-size: 28rpx;
  line-height: 1.45;
}

.option.is-selected {
  background: #f6f3ff;
  border-color: #8065f4;
}

.option.is-selected .option-letter {
  color: #fff;
  background: #7b60f3;
}

.option.is-correct {
  background: #effbf7;
  border-color: #35ba8e;
}

.option.is-correct .option-letter {
  color: #fff;
  background: #2db58a;
}

.option.is-wrong {
  background: #fff2f4;
  border-color: #ff7182;
}

.option.is-wrong .option-letter {
  color: #fff;
  background: #ff6579;
}

.status-icon {
  display: flex;
  width: 43rpx;
  height: 43rpx;
  margin-left: 15rpx;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 27rpx;
  font-weight: 700;
  border-radius: 50%;
}

.correct-icon {
  background: #2db58a;
}

.wrong-icon {
  background: #ff6579;
}

.checking-tip {
  display: flex;
  padding: 18rpx 4rpx;
  align-items: center;
  justify-content: center;
  color: #8e899c;
  font-size: 23rpx;
}

.explanation-card {
  margin-top: 30rpx;
  padding: 28rpx;
  border-radius: 24rpx;
}

.correct-card {
  color: #277b63;
  background: #ebfaf4;
  border: 1rpx solid #d0f1e5;
}

.wrong-card {
  color: #a14e5c;
  background: #fff1f3;
  border: 1rpx solid #ffd9df;
}

.explanation-heading {
  display: flex;
  align-items: center;
  font-size: 27rpx;
  font-weight: 700;
}

.heading-icon {
  display: flex;
  width: 40rpx;
  height: 40rpx;
  margin-right: 12rpx;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 22rpx;
  border-radius: 50%;
}

.correct-card .heading-icon { background: #2db58a; }
.wrong-card .heading-icon { background: #ff6579; }

.explanation-title,
.explanation-text {
  display: block;
}

.explanation-title {
  margin-top: 24rpx;
  font-size: 22rpx;
  font-weight: 700;
}

.explanation-text {
  margin-top: 8rpx;
  color: #716d7e;
  font-size: 24rpx;
  line-height: 1.65;
}

.bottom-space {
  height: 170rpx;
}

.action-bar {
  position: fixed;
  z-index: 10;
  right: 0;
  bottom: 0;
  left: 0;
  display: flex;
  padding: 22rpx 30rpx calc(22rpx + env(safe-area-inset-bottom));
  background: rgba(255, 255, 255, 0.96);
  border-top: 1rpx solid #eeecf3;
}

.previous-button,
.next-button,
.primary-button,
.secondary-button {
  display: flex;
  height: 86rpx;
  margin: 0;
  align-items: center;
  justify-content: center;
  font-size: 27rpx;
  font-weight: 600;
  border-radius: 23rpx;
}

.previous-button {
  width: 190rpx;
  margin-right: 20rpx;
  color: #696477;
  background: #f0eef5;
}

.previous-button[disabled] {
  color: #c5c1cc;
  background: #f4f3f7;
}

.next-button {
  flex: 1;
  color: #fff;
  background: linear-gradient(100deg, #7357f4, #896bff);
  box-shadow: 0 10rpx 25rpx rgba(112, 80, 236, 0.22);
}

.next-button.disabled {
  color: #aaa5b8;
  background: #e4e1eb;
  box-shadow: none;
}

.button-arrow {
  margin-left: 12rpx;
  font-size: 39rpx;
  font-weight: 300;
}

.result-page {
  position: relative;
  overflow: hidden;
  min-height: calc(100vh - 150rpx);
  padding: 42rpx 32rpx calc(48rpx + env(safe-area-inset-bottom));
}

.result-glow {
  position: absolute;
  width: 240rpx;
  height: 240rpx;
  background: rgba(124, 92, 248, 0.07);
  border-radius: 50%;
}

.glow-left {
  left: -130rpx;
  top: 100rpx;
}

.glow-right {
  right: -120rpx;
  top: 430rpx;
}

.result-card {
  position: relative;
  padding: 40rpx 28rpx 34rpx;
  text-align: center;
  background: #fff;
  border: 1rpx solid #eeebf7;
  border-radius: 34rpx;
  box-shadow: 0 20rpx 60rpx rgba(54, 43, 102, 0.08);
}

.medal-wrap {
  position: relative;
  display: flex;
  width: 138rpx;
  height: 138rpx;
  margin: 0 auto;
  align-items: center;
  justify-content: center;
}

.medal {
  position: relative;
  z-index: 1;
  font-size: 82rpx;
}

.medal-rays {
  position: absolute;
  color: #f5cb53;
  font-size: 137rpx;
  line-height: 1;
  opacity: 0.23;
}

.result-title,
.result-subtitle,
.accuracy-text,
.result-stat-value,
.result-stat-label {
  display: block;
}

.result-title {
  margin-top: 16rpx;
  color: #2c2940;
  font-size: 38rpx;
  font-weight: 800;
}

.result-subtitle {
  margin-top: 13rpx;
  color: #aaa5b7;
  font-size: 22rpx;
}

.score-ring {
  display: flex;
  width: 208rpx;
  height: 208rpx;
  margin: 36rpx auto 0;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #7358f1, #9479ff);
  border: 15rpx solid #eeeaff;
  border-radius: 50%;
  box-shadow: 0 12rpx 30rpx rgba(116, 83, 240, 0.2);
}

.score-inner {
  display: flex;
  align-items: baseline;
  color: #fff;
}

.score-number {
  font-size: 72rpx;
  font-weight: 800;
}

.score-total {
  margin-left: 7rpx;
  color: rgba(255, 255, 255, 0.76);
  font-size: 27rpx;
}

.accuracy-text {
  margin-top: 18rpx;
  color: #7659ef;
  font-size: 25rpx;
  font-weight: 600;
}

.result-stats {
  display: flex;
  margin-top: 38rpx;
  padding: 28rpx 8rpx 4rpx;
  align-items: center;
  justify-content: space-around;
  border-top: 1rpx solid #efedf4;
}

.result-stat {
  display: flex;
  width: 29%;
  align-items: center;
  flex-direction: column;
}

.result-stat-icon {
  display: flex;
  width: 42rpx;
  height: 42rpx;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 24rpx;
  border-radius: 50%;
}

.result-stat-icon.success { background: #2db58a; }
.result-stat-icon.error { background: #ff6579; }
.result-stat-icon.time { background: #ffad48; }

.result-stat-value {
  margin-top: 11rpx;
  color: #3b374d;
  font-size: 26rpx;
  font-weight: 700;
}

.result-stat-label {
  margin-top: 5rpx;
  color: #aaa6b5;
  font-size: 19rpx;
}

.result-stat-separator {
  width: 1rpx;
  height: 72rpx;
  background: #efedf3;
}

.primary-button,
.secondary-button {
  width: 100%;
}

.primary-button {
  margin-top: 32rpx;
  color: #fff;
  background: linear-gradient(100deg, #7256f3, #8c6fff);
  box-shadow: 0 12rpx 28rpx rgba(112, 80, 236, 0.2);
}

.secondary-button {
  margin-top: 18rpx;
  color: #696477;
  background: #eae8f0;
}

.short-button {
  width: 260rpx;
}
</style>
