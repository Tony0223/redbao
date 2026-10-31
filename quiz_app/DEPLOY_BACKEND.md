# 答题星球后端部署

后端部署栈全部由 Docker Compose 管理：

- `db`：MySQL 8.4，保存业务数据。
- `backend`：FastAPI + SQLAlchemy + Alembic。
- `nginx`：开放 80/443，通过 Docker 内网访问 `backend:8000`。
- `certbot`：每 12 小时检查一次证书续期。

前端 APP 不部署到服务器。打包前把接口根地址配置为 API 的 HTTPS 域名。

示例域名为 `api.example.com`，服务器目录为 `/opt/quiz_app`，请替换为真实值。

## 1. 阿里云准备

1. 给 API 域名添加 A 记录，指向 ECS 公网 IP。
2. 安全组开放 TCP 80、443；TCP 22 建议只允许管理员 IP。
3. 不要开放 3306 和 8000。
4. 中国大陆 ECS 使用域名提供服务时，请提前完成 ICP 备案。
5. 如果宿主机已经运行 Nginx 或 Apache，需要先处理 80/443 端口冲突。

检查端口：

```bash
sudo ss -lntp | grep -E ':80|:443|:3306|:8000'
```

## 2. 上传项目

```bash
sudo mkdir -p /opt/quiz_app
sudo chown -R "$USER":"$USER" /opt/quiz_app
cd /opt/quiz_app
```

通过 Git、SCP 或其他方式，把完整项目上传到 `/opt/quiz_app`。

最终至少应包含：

```text
/opt/quiz_app/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── alembic.ini
│   └── alembic/
└── deploy/
    ├── nginx/
    │   ├── start-nginx.sh
    │   ├── quiz-api-http.conf.template
    │   └── quiz-api-https.conf.template
    └── certbot/
        ├── conf/
        └── www/
```

## 3. 配置环境变量

```bash
cd /opt/quiz_app
cp .env.example .env
chmod 600 .env
```

生成两个不同的数据库密码：

```bash
openssl rand -base64 36
openssl rand -base64 36
```

编辑 `.env`：

```dotenv
MYSQL_ROOT_PASSWORD=替换为第一个随机密码
MYSQL_DATABASE=quiz_app
MYSQL_USER=quiz_app
MYSQL_PASSWORD=替换为第二个随机密码

APP_TIMEZONE=Asia/Shanghai
MYSQL_HOST_PORT=3306

API_DOMAIN=api.example.com
CERTBOT_EMAIL=你的邮箱@example.com

CORS_ORIGINS=*
```

`API_DOMAIN` 只填写域名，不要包含 `http://`、`https://` 或路径。

MySQL 官方镜像只会在数据卷第一次初始化时创建用户和密码。数据库已经运行后，不要只修改
`.env` 中的密码，否则应用密码和 MySQL 内部密码会不一致。

## 4. 启动全部容器

```bash
cd /opt/quiz_app

docker compose config
docker compose pull db nginx certbot
docker compose build backend
docker compose up -d
docker compose ps
```

第一次启动时还没有 HTTPS 证书，Nginx 会自动使用 HTTP 配置，不会因为证书文件不存在而启动失败。

查看日志：

```bash
docker compose logs --tail=100 db
docker compose logs --tail=100 backend
docker compose logs --tail=100 nginx
docker compose logs --tail=100 certbot
```

容器启动时，API 会先运行：

```text
alembic upgrade head
```

首次执行会在 MySQL 中创建 `alembic_version` 和 `quiz_results` 表。

测试 HTTP：

```bash
curl http://api.example.com/health
curl http://api.example.com/api/topics
```

也可以直接从 Docker 内部检查 API：

```bash
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
```

## 5. 第一次申请 HTTPS 证书

确认以下条件全部满足：

- 域名已经解析到当前 ECS 公网 IP。
- 阿里云安全组已经开放 80。
- `http://api.example.com/health` 可以访问。
- `.env` 中的域名和邮箱已经填写正确。

执行一次首次申请：

```bash
cd /opt/quiz_app

docker compose run --rm --entrypoint /bin/sh certbot -c '
certbot certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  --email "$CERTBOT_EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d "$API_DOMAIN"
'
```

证书成功后会保存在宿主机：

```text
deploy/certbot/conf/live/你的域名/fullchain.pem
deploy/certbot/conf/live/你的域名/privkey.pem
```

Nginx 每 60 秒检查一次证书变化，发现证书后会自动生成 HTTPS 配置并 reload。也可以立即重启：

```bash
docker compose restart nginx
```

测试 HTTPS：

```bash
curl -I http://api.example.com/health
curl https://api.example.com/health
curl https://api.example.com/api/topics
```

HTTP 请求应跳转到 HTTPS，健康检查应返回：

```json
{"status":"ok"}
```

## 6. 证书自动续期

`certbot` 容器常驻运行，每 12 小时执行：

```text
certbot renew --webroot --webroot-path /var/www/certbot
```

证书内容变化后，Nginx 容器会在 60 秒内自动 reload，不需要宿主机 Crontab。

手动测试续期：

```bash
docker compose run --rm --entrypoint certbot certbot \
  renew \
  --webroot \
  --webroot-path /var/www/certbot \
  --dry-run
```

## 7. APP 接口地址

打包 APP 前，将前端接口根地址改为：

```js
export const BASE_URL = 'https://api.example.com'
```

不要在正式 APP 中使用服务器 IP、`127.0.0.1`、HTTP 或 8000 端口。

## 8. 更新后端

```bash
cd /opt/quiz_app
git pull
docker compose up -d --build backend
docker compose logs --tail=100 backend
curl https://api.example.com/health
```

如果 Compose、Nginx 或 Certbot 配置也有变化：

```bash
docker compose up -d --build
```

以后修改 SQLAlchemy 模型时，在开发环境生成并检查迁移文件：

```bash
cd backend
alembic revision --autogenerate -m "说明本次表结构变化"
alembic upgrade head
```

将迁移文件提交到 `backend/alembic/versions/`。线上 API 容器重建时会自动运行迁移。

## 9. 查看状态和日志

```bash
docker compose ps
docker compose logs -f --tail=200
docker compose logs -f backend
docker compose logs -f nginx
docker compose logs -f certbot
docker stats quiz-backend quiz-db quiz-nginx quiz-certbot
```

进入 MySQL：

```bash
docker compose exec db sh -c 'exec mysql -u"$MYSQL_USER" -p "$MYSQL_DATABASE"'
```

## 10. 数据库备份和恢复

备份：

```bash
mkdir -p backups
docker compose exec -T db sh -c 'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers "$MYSQL_DATABASE"' > backups/quiz_app.sql
```

恢复会写入数据库，执行前确认备份文件和目标数据库正确：

```bash
docker compose exec -T db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' < backups/quiz_app.sql
```

`docker compose down` 不会删除 MySQL 数据。

不要执行：

```bash
docker compose down -v
```

`-v` 会删除 MySQL 数据卷。
