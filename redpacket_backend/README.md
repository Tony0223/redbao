# 红包群后台API（MVP第一版）

## 这一版做了什么

- 用户表、广告观看记录表、奖励规则配置表
- 看广告发金币的完整计算逻辑（对照你截图里的"低区收益配置"页实现：min/max值、插屏单独上限、游戏类广告单独上限、赐福规则）
- 两个核心接口：登录/建用户、上报看广告拿金币、查余额

## 这一版没做（后面再说）

- 真正的微信登录（现在 `/api/user/login` 直接收openid字符串，谁都能传假的冒充别人，**只能自己测试用，不能上线**）
- 后台管理界面（现在要改奖励规则，直接改数据库 `reward_configs` 表就行）
- 提现打款
- 高区/低区怎么划分用户的具体规则（现在所有新用户默认都是"低区"）

## 本地测试（在你Mac上跑起来看看）

```bash
cd redpacket_backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，填你本地或者宝塔上MySQL的真实账号密码

# 先在MySQL里建好这个空数据库（表结构由代码自动建，数据库本身要手动建一下）：
# mysql -u root -p -e "CREATE DATABASE redpacket CHARACTER SET utf8mb4;"

uvicorn app.main:app --reload --port 8000
```

启动后打开浏览器访问 `http://127.0.0.1:8000/docs`，会看到FastAPI自动生成的接口文档，可以直接在网页上点着测试，不用自己写curl命令。

## 接口速览

### 1. 登录/建用户
```
POST /api/user/login
Body: {"openid": "test123", "nickname": "测试"}
```
返回 `user_id`，App后续调用其他接口都要带上这个id。

### 2. 看广告拿金币
```
POST /api/ad/reward
Body: {"user_id": 1, "ad_type": "reward_video", "is_game_ad": false}
```
`ad_type` 可选值：`reward_video`（激励视频，红包群点红包用这个）、`feed`（信息流）、`interstitial`（插屏）、`banner`

### 3. 查余额
```
GET /api/user/{user_id}/balance
```

## 部署到宝塔服务器

1. 宝塔面板装好 Python项目管理器 插件（或者直接用Python版本管理装个3.10+的Python）
2. 把这个 `redpacket_backend` 文件夹上传到服务器（比如 `/www/wwwroot/redpacket-api`）
3. 宝塔终端里跟"本地测试"一样，建虚拟环境、装依赖、配置 `.env`
4. 生产环境不要用 `--reload`（那是开发模式），改用 Supervisor 常驻进程，跟你现有项目管理queue worker的方式一样：

   Supervisor 配置示例（宝塔的Supervisor管理器界面里新建）：
   ```
   程序名称: redpacket-api
   启动用户: www
   运行目录: /www/wwwroot/redpacket-api
   启动命令: /www/wwwroot/redpacket-api/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

5. 宝塔网站设置里配一个反向代理，把外部域名/端口转发到 `127.0.0.1:8000`（跟你现有项目配Nginx反代的做法一样）
6. 用微信小程序/APP要求接口必须是HTTPS，记得申请SSL证书（宝塔一键申请Let's Encrypt就行）

## 微信登录接入后要改的地方（AppID/AppSecret拿到手之后回来找我）

`app/routers/user.py` 里的 `login_or_create` 接口需要整个重写逻辑：
- App传的不再是openid字符串，而是微信登录SDK拿到的临时code
- 后端拿这个code + AppSecret去调微信的 `https://api.weixin.qq.com/sns/oauth2/access_token` 接口换真正的openid
- 换回来的openid才可信，才能用来查/建用户

7. HTTPS：复用现有 quiz-nginx 容器加了一份独立配置，证书用的是阿里云免费DV证书（记得3个月后要手动续期，不会自动续，建议你自己设个日历提醒）

8. 微信开放平台
   zhengtuoruanjian@126.com 
   密码 Ruanjian123
   
   AppID 和 AppSecret
   wx259037e95e377617
   057e4c99c793788512e3d17f0b94b027


9. 穿山甲
838239814@qq.com
Ruanjian123@

10. 注意
   活动结束前把补贴提现审完,避免用户因为"活动结束后才审核"拿不到补贴
