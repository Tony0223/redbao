<template>
  <view class="page">
    <view class="article">
      <text class="main-title">金石速答隐私政策</text>
      <text class="meta">更新及生效日期：2026年09月02日</text>
      <text class="meta">开发者：济南正拓网络科技有限公司</text>

      <text class="paragraph">欢迎使用“金石速答”。为了向你提供必要的题库、答题、账号及学习统计服务，我们将根据你使用的功能处理相关个人信息。本政策说明本应用如何处理个人信息。请在使用前认真阅读；只有在你点击“同意并继续”后，应用才会进入业务页面、初始化相关组件并发起网络请求。</text>

      <text class="heading">一、我们处理的信息</text>
      <text class="subheading">1. 账号信息</text>
      <text class="paragraph">注册账号时，你主动提供用户名、邮箱和密码。用户名和邮箱用于创建账号、登录及展示账号资料；密码仅以加盐哈希值保存，我们不会保存你的明文密码。不登录也可以体验部分答题功能。</text>
      <text class="subheading">2. 学习记录</text>
      <text class="paragraph">当你答题时，我们记录题库类型、答对数量、题目总数、答题用时和记录时间，用于保存成绩、计算正确率和展示学习进度。</text>
      <text class="subheading">3. 网络、设备及运行信息</text>
      <text class="paragraph">服务器在网络通信过程中会接收 IP 地址、请求时间等必要网络日志，用于传输数据、保障服务安全和排查故障。</text>
      <text class="paragraph">本应用基于 DCloud uni-app（5+ App）开发。仅在你同意本政策后，DCloud App 引擎可能处理设备品牌、型号、操作系统版本、网络状态、设备标识符（包括 Android ID、DEVICE_ID、IMEI、IMSI、OAID）以及应用启动和异常日志，用于保障基础运行、统计分析和定位崩溃问题。详情可查看 DCloud App 引擎隐私政策：https://dcloud.io/license/appprivacy.html。</text>

      <text class="heading">二、权限及第三方 SDK</text>
      <text class="paragraph">1. 网络权限：用于加载题库、提交答题结果、注册登录及同步学习记录。</text>
      <text class="paragraph">2. DCloud uni-app App 引擎：提供跨平台应用运行能力，处理范围和用途见本政策第一条第 3 项。</text>
      <text class="subheading">3. 广告服务相关信息</text>
      <text class="paragraph">本应用接入第三方广告 SDK（穿山甲/GroMore），其可能收集设备标识信息用于广告投放与效果统计，具体请参阅第三方 SDK 隐私政策。</text>
      <text class="paragraph">本应用仅申请网络权限，用于加载题库、提交答题结果、注册登录及同步学习记录；不会主动申请定位、通讯录、短信、相机或麦克风权限。</text>

      <text class="heading">三、信息的使用、共享和公开披露</text>
      <text class="paragraph">我们仅将信息用于提供账号、答题、成绩统计、服务安全和故障排查。除为实现上述功能所必需、取得你的单独同意或法律法规另有要求外，我们不会向其他公司、组织或个人共享、转让或公开披露你的个人信息，也不会出售个人信息。</text>

      <text class="heading">四、保存与保护</text>
      <text class="paragraph">账号资料和学习记录保存在中国境内的服务端，并仅在提供服务所需期限内保存。我们采用 HTTPS 传输、密码加盐哈希、访问控制等措施保护信息。法律法规另有保存要求的，从其规定。</text>

      <text class="heading">五、你的权利</text>
      <text class="paragraph">1. 查询：登录后可在【我的】查看账号资料和学习统计。</text>
      <text class="paragraph">2. 删除及注销：登录后进入【我的－账号与安全－注销账号】，阅读注销后果、输入当前密码并确认即可立即提交注销。完成后账号资料、全部登录会话及关联学习记录会被删除，账号无法恢复。</text>
      <text class="paragraph">3. 撤回同意：你可以停止使用并卸载应用；如已注册账号，可先按上述入口注销。撤回同意不影响撤回前基于你同意进行的信息处理。</text>

      <text class="heading">六、未成年人保护</text>
      <text class="paragraph">未成年人应在监护人指导和同意下使用本应用。若监护人发现未成年人未经同意向我们提供了个人信息，请通过本政策所列方式联系我们处理。</text>

      <text class="heading">七、政策更新</text>
      <text class="paragraph">本政策发生重大变化时，我们会通过启动提示或应用内显著方式告知，并在需要时重新取得你的同意。</text>

      <text class="heading">八、联系我们</text>
      <text class="paragraph">如对本政策或个人信息处理有疑问、意见或投诉，请发送邮件至 privacy@zero-start.online。我们将在收到反馈后十五个工作日内处理。</text>
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
.subheading,
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

.subheading {
  margin-top: 25rpx;
  color: #484358;
  font-size: 25rpx;
  font-weight: 700;
}

.paragraph {
  margin-top: 17rpx;
  color: #656174;
  font-size: 24rpx;
  line-height: 1.85;
  text-align: justify;
}
</style>
