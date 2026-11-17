# 08 部署指南（Docker Compose）

当前是部署草案：前后端与依赖尚未初始化，命令须在完成 W1 后演练。Compose 为单机部署，更新可能短暂中断。以下 shell 示例使用 Bash；备份重定向不直接复制到旧版 Windows PowerShell，以免二进制转码。

## 1. 配置与首次部署

- 复制 `.env.example` 为 `.env`，填写数据库、SMTP、加密密钥与 S3 凭据；DATABASE_URL 的密码须与 POSTGRES_PASSWORD 一致并 URL 编码。
- `MINIO_IMAGE` 必填已核验的 release tag/digest，确认镜像包含 curl（ready 健康检查所需）；生产其他镜像也固定版本/digest。
- backend、worker、beat 使用相同 APP_ENV/settings；生产 APP_ENV=prod、DEBUG=false，SMTP 域名完成 SPF/DKIM。
- S3_ENDPOINT 为容器内部地址，S3_PUBLIC_ENDPOINT 为浏览器可达地址；签名前用独立客户端，不能改写已签名链接。生产使用独立 HTTPS 对象存储域名。
- Nginx 是直连公网入口，覆盖转发 IP 头；若前置 CDN/负载均衡，先配置可信代理网段再调整真实 IP 解析。/healthz/ 必须覆盖应用依赖就绪状态。

```bash
cp .env.example .env
# 编辑 .env 并检查所有占位值；下列命令不会补全密钥
# 先只验证配置，避免直接启动缺代码的服务
docker compose config --quiet
docker compose build
docker compose up -d postgres redis minio
# 先执行下方 mc 建桶步骤，再启动应用（避免依赖桶的健康检查阻塞）
# 后端入口已内置 migrate + seed；seed 必须幂等
docker compose up -d
docker compose exec backend python manage.py createsuperuser
```

安装并锁定主机 MinIO Client（mc）的版本，配置别名后创建私有桶；不要假设 server 镜像内含 mc：

```bash
# 凭据从受保护的 shell 环境提供；mc 配置目录权限仅限运维账号
mc alias set local http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb --ignore-existing "local/$S3_BUCKET_MEDIA" "local/$S3_BUCKET_CERTS"
mc anonymous set none "local/$S3_BUCKET_MEDIA"
mc anonymous set none "local/$S3_BUCKET_CERTS"
```

## 2. 更新

```bash
git pull
docker compose build backend frontend celery_worker celery_beat
# 在维护窗口停止写入与异步任务；随后迁移，避免并发旧写入
docker compose stop nginx celery_worker celery_beat backend
docker compose run --rm --no-deps backend python manage.py migrate --noinput
docker compose up -d
```

破坏性变更拆成加列、回填、切读写、删旧；失败时保留维护状态，按该版本的回退方案处置，不直接用旧代码连接不兼容 schema。

## 3. 一致性备份与恢复

维护窗口暂停入口与后台任务后，同批次备份数据库和两桶；避免把 pg_dump 与不同时刻的文件快照拼接。以下使用默认数据库名，若已修改则同步替换。

```bash
set -eu
backup_dir="backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
docker compose stop nginx celery_worker celery_beat backend
docker compose exec -T postgres pg_dump -U compsphere -Fc compsphere > "$backup_dir/database.dump"
mc mirror "local/$S3_BUCKET_MEDIA" "$backup_dir/media/"
mc mirror "local/$S3_BUCKET_CERTS" "$backup_dir/certs/"
docker compose up -d
# remote 预先用 mc alias set 指向异地 S3；该桶先由运维创建
mc mirror "$backup_dir/" "remote/compsphere-backup/$(basename "$backup_dir")/"
```

备份任一步失败须告警，检查完整性后再恢复写入；保留 30 天，确认异地副本存在。加密密钥和 pepper 单独安全备份，不放入同一个公开可读备份目录。

恢复到隔离环境的空数据库与空私有桶，使用同批次 dump/media/certs（禁止直接覆盖生产）：

```bash
docker compose exec -T postgres pg_restore -U compsphere -d compsphere --exit-on-error --no-owner < "$backup_dir/database.dump"
mc mirror "$backup_dir/media/" "local/$S3_BUCKET_MEDIA"
mc mirror "$backup_dir/certs/" "local/$S3_BUCKET_CERTS"
```

恢复同批次加密密钥后，抽查报名、证书、文件哈希与解密，再演练切换；只有演练通过才算备份可用。

## 4. 上线检查

- HTTPS、私有桶、关闭数据库/对象存储控制台公网映射；Django admin 限内网/IP 白名单。
- `.env` 与 mc 凭据配置仅运维可读；真实值不入仓，应用 S3 使用独立最小权限账号。
- Compose 日志轮转 50MB×5；Redis 配置 noeviction 和容量告警；公示与验证页限流并禁缓存。
- 监控 /healthz/、队列积压、邮件失败、备份结果和磁盘；验证签名 URL 可在浏览器下载。

## 5. 本地开发

启动 postgres/redis/minio 后，在主机虚拟环境安装 backend/requirements.txt 并运行 Django；前端使用 npm ci、npm run dev。主机运行时将 DATABASE_URL、Redis、S3 内部地址改为主机可达地址；Redis 默认未映射端口，需本地 override 绑定 127.0.0.1:6379。虚拟环境激活方式见 backend/README。
