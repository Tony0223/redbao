<script>
import { PRIVACY_AGREED_KEY } from './common/auth.js'

export default {
  globalData: {
    privacyAgreed: false
  },
  onLaunch: function () {
    // 启动时最先读取同意状态；所有 SDK/网络初始化必须放到同意之后。
    let agreed = Boolean(uni.getStorageSync(PRIVACY_AGREED_KEY))
    // Android 原生 template 弹窗在 JS 生命周期之前完成同意，
    // 将原生状态同步到业务层，避免再次显示 Vue 弹窗。
    // #ifdef APP-PLUS
    try {
      if (plus.runtime && plus.runtime.isAgreePrivacy && plus.runtime.isAgreePrivacy()) {
        agreed = true
        uni.setStorageSync(PRIVACY_AGREED_KEY, true)
      }
    } catch (e) {
      // 运行环境尚未准备好时，以本地状态为准；原生弹窗仍会阻断启动。
    }
    // #endif
    this.globalData.privacyAgreed = agreed
    if (this.globalData.privacyAgreed) {
      console.log('答题星球启动')
    }
  }
}
</script>

<style>
page {
  min-height: 100%;
  background: #f6f7fb;
  color: #25253a;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
}

view,
text,
button {
  box-sizing: border-box;
}

button::after {
  border: none;
}

.safe-top {
  height: var(--status-bar-height);
}

.pressable {
  transition: transform 0.16s ease, opacity 0.16s ease;
}

.pressable:active {
  transform: scale(0.98);
  opacity: 0.88;
}
</style>
