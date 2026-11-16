# 08 部署指南（Docker Compose）

**适用**：单机 staging/小规模生产。拓扑与端口见根目录 `docker-compose.yml`。

---

## 1. 服务清单

| 服务 | 镜像 | 端口（宿主） | 说明 |
| --- | --- | --- | --- |
| nginx | nginx:1.27-alpine | 80 | 唯一对外入口 |
| frontend | docker/frontend.Dockerfile | 内部 80 | 多阶段构建的 Vue SPA 静态站点 |
| backend | docker/backend.Dockerfile | 内部 8000 | Django（gunicorn） |
| celery_worker / celery_beat | 同 backend 镜像 | — | 邮件/证书/导入/定时任务 |
| postgres | postgres:16-alpine | 127.0.0.1:5432（仅开发） | 卷 pgdata |
| redis | redis:7-alpine | 内部 6379 | 卷 redisdata，AOF 开启 |
| minio | minio/minio | 127.0.0.1:9000/9001（仅开发） | 卷 miniodata |

## 2. 首次部署

```bash
git clone <repo> && cd CompSphere
cp .env.example .env          # 填所有 CHANGE_ME/空值，SECRET_KEY: openssl rand -hex 32
docker compose build
docker compose up -d
docker compose exec backend python manage.py createsuperuser
docker compose exec minio sh -c 'mc alias set local http://localhost:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD && mc mb -p local/compsphere-media local/compsphere-certs'
```

> backend 容器启动命令内置 `migrate + seed_rbac`，首次起来即带 6 内置角色与权限表。
> 依赖 backend/ 与 frontend/ 代码初始化后本流程才可跑通（当前两目录为占位）。

## 3. 发布更新

```bash
git pull
docker compose build backend frontend
docker compose run --rm backend python manage.py migrate --noinput   # 先迁移
docker compose up -d                                                  # 再滚动替换
docker compose restart celery_worker celery_beat
```

迁移规则：破坏性变更（删列/改类型）必须拆成 加列→回填→切读写→删旧 多步发布，禁止单步上线。

## 4. 备份与恢复

```bash
# 每日 cron（宿主）：
docker compose exec -T postgres pg_dump -U compsphere -Fc compsphere > backup_$(date +%F).dump
# 文件：minio-client mirror 到异机/对象存储；保留 30 天
mc mirror --overwrite pgbackup/ remote:compsphere-backup/
# 恢复：
docker compose exec -T postgres pg_restore -U compsphere -d compsphere --clean < backup.dump
```

证书 PDF 与报名材料在 MinIO 桶内，数据库恢复后文件必须同源恢复（storage_key 一致）；两桶都纳入备份。

## 5. 生产加固清单

- [ ] Postgres/Redis/MinIO 端口映射全部移除（当前绑定 127.0.0.1 仅限开发机便利）。
- [ ] Nginx 上 443 + 证书，80 仅 301；删除 `/django-admin/` 公网段或加 IP 白名单。
- [ ] `.env` 权限 600，不入仓（.gitignore 已排除）；密钥轮换记录在运维台账。
- [ ] 应用日志接 Loki/文件轮转；`audit_logs` 只进数据库不进应用日志。
- [ ] Redis 设 maxmemory + noeviction 保护 Celery 队列。
- [ ] 监控：`/healthz/` 外部探活 + Celery 队列长度告警 + 磁盘（pgdata/miniodata）告警。
- [ ] 备份异地一份，并**演练过恢复**才算存在。

## 6. 本地开发（不用 Docker 后端）

```bash
docker compose up -d postgres redis minio
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements/dev.txt
.venv/bin/python manage.py runserver 8000
cd frontend && npm run dev      # VITE_API_BASE=http://localhost:8000/api/v1
```
