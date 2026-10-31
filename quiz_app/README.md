# 答题星球

一个带“首页 / 我的”双入口的移动端答题 APP。后端使用 Python + FastAPI，前端使用 uni-app + Vue2，可编译到 H5、微信小程序、Android 和 iOS。

## 已实现功能

- 首页：每日挑战、专项题库、完成次数和正确率
- 我的：个人学习数据、等级进度、学习成就和今日打卡状态
- 账号：邮箱注册、用户名/邮箱登录、30 天登录会话与退出登录
- 隐私：首次启动同意拦截、App 内政策详情页和公网政策页面
- 合规：登录/注册均需确认用户协议和隐私政策；账号与安全页支持验证密码后注销账号
- 答题页：单选判题、对错反馈、答案解析、上下题切换
- 成绩页内展示：分数、正确率、答对/答错数、答题用时
- 后端：题库列表、题目、判题、成绩保存、学习统计
- MySQL 存储答题记录，首次启动自动建表

项目主要页面：

1. `pages/privacy/consent`：首次启动隐私确认（同意前不进入业务页）
2. `pages/index/index`：题库首页
3. `pages/mine/mine`：我的学习主页与账号入口
4. `pages/quiz/quiz`：答题及答题结果
5. `pages/auth/auth`：登录与注册
6. `pages/privacy/privacy`：App 内隐私政策
7. `pages/agreement/agreement`：App 内用户协议
8. `pages/account/settings`：账号与安全及注销账号

## 1. 使用 Docker Compose 启动后端

生产环境使用 MySQL 8.4，详细步骤见 [DEPLOY_BACKEND.md](DEPLOY_BACKEND.md)。本地安装 Docker 后：

```bash
cp .env.example .env
# 修改 .env 中的两个数据库密码
docker compose up -d --build
```

启动后可访问：

- API 根地址：`https://你在 .env 中配置的 API_DOMAIN`
- Swagger 接口文档：`https://你在 .env 中配置的 API_DOMAIN/docs`

API 的 8000 端口只在 Docker 内网开放，公网统一通过 Nginx 的 80/443 访问。

运行测试：

```bash
cd quiz_app/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m unittest -v test_main.py
```

## 2. 启动 uni-app Vue2 前端

1. 打开 HBuilderX。
2. 选择“文件 → 打开目录”，打开 `quiz_app/frontend`。
3. 选择“运行 → 运行到浏览器”即可进行 H5 调试。
4. 也可以选择运行到微信开发者工具或 App 基座。

`main.js` 使用的是 Vue2 的 `new Vue()` 初始化方式，不是 Vue3 Composition API。

## 接口地址说明

接口地址集中配置在 `frontend/common/api.js`：

```js
export const BASE_URL = 'http://127.0.0.1:8000'
```

- H5 在本机调试：保持 `127.0.0.1` 即可。
- Android 模拟器：一般改成 `http://10.0.2.2:8000`。
- 手机真机：改成电脑局域网 IP，例如 `http://192.168.1.10:8000`，并确保手机和电脑在同一 Wi-Fi。
- 正式 APP：改成 API HTTPS 域名，例如 `https://api.example.com`。
- 微信小程序上线前，需要在小程序后台配置合法的 HTTPS request 域名。

## 后端主要接口

| 方法 | 地址 | 用途 |
| --- | --- | --- |
| GET | `/api/topics` | 获取题库列表 |
| GET | `/api/topics/{id}/questions` | 获取题目（不包含答案） |
| POST | `/api/answers` | 提交单题答案并获取解析 |
| POST | `/api/results` | 保存一次答题成绩 |
| GET | `/api/stats` | 获取累计学习统计 |
| POST | `/api/auth/register` | 注册并获取登录令牌 |
| POST | `/api/auth/login` | 用户名或邮箱登录 |
| GET | `/api/auth/me` | 获取当前账号 |
| POST | `/api/auth/logout` | 退出当前登录会话 |
| DELETE | `/api/auth/account` | 验证当前密码并注销账号，删除账号及关联学习记录 |
| GET | `/privacy` | 应用商店可填写的公网隐私政策页面 |
| GET | `/agreement` | 应用商店可填写的公网用户协议页面 |

题目数据目前放在 `backend/main.py` 的 `QUESTIONS` 中，可直接增加或改成后台管理/数据库题库。

登录用户的答题记录和统计按账号隔离；未登录用户仍可体验答题。密码使用 PBKDF2-SHA256 加盐哈希保存，数据库不保存原始密码。

## 隐私政策上线前检查

正式隐私协议已同步到以下两个文件，后续协议更新时请同时维护：

- App 内页面：`frontend/pages/privacy/privacy.vue`
- 公网网页：`backend/privacy_policy.html`

正式协议已同步到 App 内页面和公网页面。隐私政策保留第三方广告 SDK（穿山甲/GroMore）的广告服务相关信息及其设备标识、广告投放与效果统计说明；当前版本不包含消息推送功能。部署后公网地址为 `https://你的 API 域名/privacy` 和 `https://你的 API 域名/agreement`；以当前配置为例是 `https://zero-start.online/privacy`、`https://zero-start.online/agreement`。应用商店后台填写的网页内容应与 App 内页面一致。

## 隐私合规打包要求

- 使用 HBuilderX 3.2.15 或更高版本重新云打包，`androidPrivacy.json` 必须保持 `prompt: "template"`。
- `manifest.json` 已关闭 `uniStatistics`，并将 `app-plus.modules` 置空；在 HBuilderX 可视化界面确认未勾选 Push、Statistic、Maps、Geolocation、OAuth、Payment、Share、Camera、Record 等未使用模块。
- 必须全新安装重新打包的 APK 后再做隐私检测；旧 APK 仍会包含旧版本的 OAID/广告 SDK 配置。
- 检测报告中应确认：用户点击原生“同意并继续”前，不调用设备标识、OAID、网络业务请求或第三方 SDK；同意后才进入首页并开始请求。


## APP 打包前，把接口地址改成：

  export const BASE_URL = 'https://zero-start.online'

## 以后更新后端：

  cd /www/quiz_app
  docker compose up -d --build backend
  docker compose logs --tail=100 backend
  curl https://zero-start.online/health

## 日常查看：

  docker compose ps
  docker compose logs -f --tail=200

## 数据库备份：

  mkdir -p backups

  docker compose exec -T db sh -c \
    'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers "$MYSQL_DATABASE"' \
    > backups/quiz_app_$(date +%F).sql

## 注意不要执行：

docker compose down -v

这会删除 MySQL 数据卷。

日志中出现的公网陌生 IP 请求、favicon.ico 404 都很常见，不影响部署结果。HEAD / 返回 405 是因为 FastAPI 根接口只支持 GET，也不影响 APP 调
用。
