# 05 技术架构

**版本**：v1.0（2026-11-16）

---

## 1. 技术栈

| 层次 | 选型 | 版本基线 | 说明 |
| --- | --- | --- | --- |
| 前端框架 | Vue 3 + TypeScript | Vue 3.5 / TS 5.x | Composition API + `<script setup>` |
| 构建 | Vite | 6.x | |
| UI | Element Plus | 2.x | 管理后台组件库 |
| 状态 | Pinia | 2.x | 用户会话、grants、菜单 |
| 路由 | Vue Router | 4.x | 动态权限路由 |
| HTTP | Axios | 1.x | 统一拦截器（token 刷新、错误码） |
| 后端 | Django | 5.x | 模块化单体 |
| API | Django REST Framework | 3.15+ | 视图 + Serializer 为主 |
| 认证 | djangorestframework-simplejwt | 最新 | Access 30min + Refresh 7d 轮转 |
| 数据库 | PostgreSQL | 16 | |
| 缓存/队列 | Redis | 7.x | 验证码、限流、Celery broker |
| 异步 | Celery | 5.x | 邮件、证书 PDF、导入任务 |
| 定时 | django-celery-beat | | 状态提醒、清理 |
| 对象存储 | MinIO（开发/自建）/ S3 兼容 | | 报名材料、证书 PDF，私有桶 + 预签名 URL |
| 反向代理 | Nginx | | 静态资源、路由到 gunicorn |
| WSGI | gunicorn + uvicorn worker | | 部署 ASGI 亦可，第一版 WSGI 足够 |
| 部署 | Docker Compose | | 单机起步，见 docker/README.md |

**不引入**：微服务、GraphQL、Kafka、前端 SSR、ORM 之外的 raw SQL 框架。

## 2. 后端模块划分（Django apps）

模块化单体：一个 Django 项目，按业务域分 app，app 间只允许通过 service 层函数调用（禁止跨 app 直接 import model 做写操作），为将来拆分留边界。

```
compsphere-server/
├── config/                     # settings、urls、celery、asgi/wsgi
├── apps/
│   ├── accounts/               # users、auth、JWT、验证码、账号状态
│   ├── profiles/               # user_profiles、人员信息审核
│   ├── orgs/                   # organizations、members、入驻申请
│   ├── rbac/                   # roles、permissions、user_roles、ScopedRolePermission 核心
│   ├── teams/                  # teams、team_members
│   ├── competitions/           # competitions、editions、competition_organizations、admins
│   ├── groups/                 # competition_groups、材料要求校验器
│   ├── registrations/          # 报名、快照、文件、状态机、审核
│   ├── awards/                 # awards、rosters、records、Excel 导入
│   ├── certificates/           # 模板、PDF 生成、二维码、公开验证
│   ├── notifications/          # notices、inbox、邮件发送
│   ├── stats/                  # 统计看板（只读聚合）
│   └── audit/                  # audit_logs 写入 middleware + 查询
├── core/                       # 公共：分页、异常、响应格式、软删除 mixin、transition()、幂等
└── scripts/                    # seed（roles/permissions）、一致性检查、备份
```

分层约定：**views（薄）→ serializers（校验/塑形）→ services（业务规则、状态机、事务）→ models（存储）**。跨 app 调用走 `apps/<x>/services.py`。

关键公共组件（core）：

1. `StateMachine`：03 文档迁移表的代码化（每个域一个声明式迁移字典），`transition(obj, action, actor, comment)` 内部完成校验、更新、写 approval_records/audit_logs、发信号。
2. `ScopedRolePermission`：02 文档 §5 的统一权限类。
3. `SoftDeleteModel` mixin + 默认 manager 过滤 `is_deleted`。
4. 统一响应：`{code, message, data, request_id}`，业务错误码见 06 文档。
5. 幂等：`Idempotency-Key` 头支持（报名提交、证书生成）。

## 3. 关键横切设计

### 3.1 认证流

- 注册：手机号/邮箱 + Redis 验证码（60s 限频）→ 创建 `users(status=pending)` → 首登强制完善档案。
- 登录：密码 → SimpleJWT 双 token；前端 401 时静默 refresh。
- `GET /api/v1/me/` 返回 user + profile + **grants 列表**（角色×作用域展开），前端据此渲染菜单与按钮。

### 3.2 文件流

上传：前端 → 后端鉴权与校验（大小/类型/扩展名三重）→ 转存 MinIO（key：`{edition_id}/{registration_id or tmp}/{uuid}.{ext}`）→ 返回 storage_key；文件确认在报名提交事务内写 `registration_files`。
下载/预览：后端签发 15 分钟预签名 URL；管理端导出走 Celery 异步生成 + 通知链接。

### 3.3 证书生成流

名单确认（roster → confirmed）→ 逐条建 `certificates(queued)` → Celery chord 并发生成 PDF（WeasyPrint 渲染 HTML 模板，字体/版式在 `templates/certificate/`）→ 生成 `qr_token` 指向 `/verify/{qr_token}` 公开页（Nginx 直连 Django，AllowAny 限流）→ 全部 generated 后自动 issued → 通知持证人。
失败重试 3 次后置 `failed` 并进告警日志。

### 3.4 高峰与削峰

报名提交 = 单事务多表写（registrations + members 快照 + files + approval 初始记录），数据库唯一索引兜底防重复；截止前流量靠 Nginx + Redis 限流（用户级 10 req/min）。第一版不引入消息队列削峰提交，Celery 只承担异步任务。

### 3.5 审计

Django middleware 标记请求上下文（actor/ip/request_id），service 层显式写 audit_log（关键动作清单见 PRD §3.8）；`detail` 存变更 diff，敏感值脱敏后入日志。

## 4. 前端架构

```
compsphere-web/
├── src/
│   ├── api/            # axios 实例 + 各域 API 模块
│   ├── stores/         # auth（token/grants）、app、notifications
│   ├── router/         # 静态路由 + 基于 grants 的动态路由守卫
│   ├── layouts/        # AdminLayout（菜单）、BlankLayout（登录/验证页）
│   ├── views/
│   │   ├── public/     # 门户：赛事列表、详情、证书验证页
│   │   ├── participant/  # 我的报名、我的证书、档案
│   │   └── admin/        # 组织/人员/赛事/组别/审核/获奖/证书/统计/系统
│   ├── components/     # 通用：ProTable、FormBuilder(P1)、上传、审批流时间线
│   └── utils/          # perm.ts: hasPerm()；download.ts；format.ts
```

约定：API 层禁裸 axios；表格页统一 ProTable（分页/筛选/导出插槽）；`hasPerm` 指令 `v-perm="'approval:review_single'"` 控制按钮；路由 meta 声明所需权限。

## 5. 环境与配置

- 配置全部环境变量注入（`django-environ`），仓库只提交 `.env.example`。
- 环境：dev（docker compose 全家桶）/ staging / prod；prod 至少：应用 2 worker、Postgres 独立、每日 `pg_dump` + 文件增量同步、30 天保留。
- 密钥：JWT SIGNING、SECRET_KEY、MinIO key、pgcrypto key 分环境独立，禁止入仓。
