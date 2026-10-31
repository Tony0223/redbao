<template>
  <view class="page">
    <view class="article">
      <text class="main-title">金石速答用户协议</text>
      <text class="meta">生效日期：2026年09月01日</text>
      <text class="meta">开发者：济南正拓网络科技有限公司</text>

      <text class="paragraph">欢迎使用“金石速答”。请在注册、登录或使用本应用前认真阅读本协议及《隐私政策》。当你勾选并同意本协议后，即表示你已理解并接受本协议内容。</text>

      <text class="heading">一、服务内容</text>
      <text class="paragraph">本应用提供题库浏览、在线答题、答案解析、成绩记录和学习统计等服务。具体功能以应用实际提供的内容为准。</text>

      <text class="heading">二、账号注册与使用</text>
      <text class="paragraph">1. 你可以使用用户名、邮箱和密码注册账号，也可以在未登录状态下体验部分答题功能。</text>
      <text class="paragraph">2. 你应提供真实、合法、有效的信息，妥善保管账号和密码，并对账号下的操作负责。</text>
      <text class="paragraph">3. 不得利用本应用从事违法活动、干扰服务运行、侵害他人权益或批量抓取、篡改题库内容。</text>

      <text class="heading">三、知识产权</text>
      <text class="paragraph">本应用的软件、界面、文字、题目编排及相关内容的合法权益归开发者或相应权利人所有。未经许可，不得复制、传播、出售或用于其他商业用途。</text>

      <text class="heading">四、服务变更与中断</text>
      <text class="paragraph">我们会尽力保障服务稳定，但因设备、网络、系统维护、不可抗力等原因，服务可能短时中断。涉及用户重要权益的规则发生重大变化时，我们会通过应用内提示等合理方式告知。</text>

      <text class="heading">五、账号注销</text>
      <text class="paragraph">登录后可进入【我的－账号与安全－注销账号】，阅读注销说明、输入当前密码并确认注销。注销完成后账号不可恢复，账号资料、登录会话及关联学习记录将被删除。</text>

      <text class="heading">六、未成年人保护</text>
      <text class="paragraph">未成年人应在监护人指导和同意下使用本应用。监护人应帮助未成年人理解本协议和《隐私政策》。</text>

      <text class="heading">七、联系我们</text>
      <text class="paragraph">如对本协议有疑问，可发送邮件至 privacy@zero-start.online。我们将在收到反馈后十五个工作日内处理。</text>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 26rpx 26rpx calc(70rpx + env(safe-area-inset-bottom));
  background: #f6f7fb;
}

.main-title,
.meta,
.heading,
.paragraph {
  display: block;
}

.article {
  margin-top: 22rpx;
  padding: 42rpx 34rpx;
  background: #fff;
  border: 1rpx solid #eceaf3;
  border-radius: 28rpx;
}

.main-title {
  margin-bottom: 20rpx;
  color: #2c293e;
  font-size: 38rpx;
  font-weight: 900;
  text-align: center;
}

.meta {
  margin-top: 6rpx;
  color: #aaa6b5;
  font-size: 20rpx;
  text-align: center;
}

.heading {
  margin-top: 39rpx;
  color: #332f48;
  font-size: 29rpx;
  font-weight: 800;
}

.paragraph {
  margin-top: 17rpx;
  color: #656174;
  font-size: 24rpx;
  line-height: 1.85;
  text-align: justify;
}
</style>
