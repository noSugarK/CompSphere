# 05 技术架构

**版本**：v1.3（2026-11-17）

v1.1 变更：技术栈补 treebeard / import-export / cryptography / structlog / Radix Colors / SMTP；app 划分新增 `events`；认证流改为邮箱验证码，并写明发码失败不可静默返回成功。

---

> 2026-11-17 审阅：版本表为选型草案，初始化前核对官方维护状态和兼容矩阵并锁定版本；未决项见 [审阅待办](10-review-notes.md)。编码与样式分别以根目录两份规范为准。

## 1. 技术栈

| 层次 | 选型 | 版本基线 | 说明 |
| --- | --- | --- | --- |
| 前端框架 | Vue 3 + TypeScript | Vue 3.5 / TS 5.x | Composition API + `<script setup>` |
| 构建 | Vite | 6.x | |
| UI | Element Plus + Radix Colors | 2.x / 1.x | 管理后台组件库；颜色全站取自 Radix 色阶经 CSS 令牌层引用（FRONTEND_DESIGN_GUIDELINES.md §1），不沿用组件库默认配色 |
| 状态 | Pinia | 2.x | 用户会话、grants、菜单 |
| 路由 | Vue Router | 4.x | 动态权限路由 |
| 国际化 | vue-i18n | 初始化锁定兼容版本 | zh-CN / en-US；同步 Element Plus 语言包 |
| HTTP | Axios | 1.x | 统一拦截器（token 刷新、错误码） |
| 后端 | Django | 5.x | 模块化单体 |
| API | Django REST Framework | 3.15+ | 视图 + Serializer 为主 |
| 认证 | djangorestframework-simplejwt | 最新 | Access 30min + Refresh 7d 轮转 |
| 数据库 | PostgreSQL | 16 | |
| 缓存/队列 | Redis | 7.x | 验证码、限流、Celery broker |
| 异步 | Celery | 5.x | 业务通知邮件、证书 PDF、导入任务；验证码邮件同步发送 |
| 定时 | django-celery-beat | | 状态提醒、清理 |
| 对象存储 | MinIO（开发/自建）/ S3 兼容 | | 报名材料、证书 PDF，私有桶 + 预签名 URL |
| 组织树 | django-treebeard | 2.x | Materialized Path，`organizations` 继承 `MP_Node`（v1.1，取代裸 parent_id 递归查询） |
| 导入导出 | django-import-export | 4.x | 获奖名单/人员 Excel；异步任务里直接调 `Resource` API，不走 admin 集成（v1.1） |
| 邮件 | Django email backend + SMTP | | 注册与找回密码验证码、审核结果通知；发信域名需配 SPF/DKIM，否则验证码邮件进垃圾箱等于注册不可用（v1.1，上线前置条件） |
| 字段加密 | cryptography（Fernet） | 42+ | 身份证号列加密，P0 交付；密钥 `FIELD_ENCRYPTION_KEY`，哈希 pepper 另用 `ID_HASH_PEPPER`（v1.1） |
| 日志 | structlog | 24+ | JSON 输出 stdout，`request_id` 贯穿；SQL 耗时经 `connection.execute_wrapper` 采集（DEVELOPMENT.md §2） |
| 反向代理 | Nginx | | 静态资源、路由到 gunicorn |
| WSGI | gunicorn | | 第一版 WSGI；确需 ASGI 时另行配置 worker |
| 部署 | Docker Compose | | 单机起步，见 docker/README.md |

**不引入**：微服务、GraphQL、Kafka、前端 SSR、ORM 之外的 raw SQL 框架。

## 2. 后端模块划分（Django apps）

模块化单体：一个 Django 项目，按业务域分 app，app 间只允许通过 service 层函数调用（禁止跨 app 直接 import model 做写操作），为将来拆分留边界。

```
compsphere-server/
├── config/                     # settings、urls、celery、asgi/wsgi
├── apps/
│   ├── accounts/               # users、auth、JWT、邮箱验证码、账号状态
│   ├── profiles/               # user_profiles、人员信息审核、身份证加解密
│   ├── orgs/                   # organizations（treebeard 树）、members、单位创建审核申请
│   ├── rbac/                   # roles、permissions、user_roles、ScopedRolePermission 核心
│   ├── teams/                  # 队伍正式资料、变更申请/已审核版本、成员历史
│   ├── competitions/           # competitions、editions、competition_organizations、admins
│   ├── events/                 # competition_events（赛项）+ competition_offerings（开放组合）
│   ├── groups/                 # competition_groups（组别/学段）+ 赛项材料要求校验器
│   ├── registrations/          # 报名、快照、文件、状态机、审核、公示名单只读视图
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

- 注册：邮箱 + 验证码（`verification_codes` 存哈希，10 分钟有效、60 秒限发 1 封、试错 5 次作废）→ 创建 `users(status=pending)` → 首登完善基本档案；作为参赛成员提交前补齐证件并加密落库→ 完善后置 `active`。短信通道本期不提供（P2），手机号只作必填联系方式，不作为身份凭证。
- 登录：密码 → SimpleJWT 双 token。Access 仅存前端内存，Refresh 存 HttpOnly Cookie（生产 Secure、SameSite=Strict、Path=/api/v1/auth）；刷新/登出校验 Origin 与 CSRF token，GET 不改变会话。前端 401 只合并刷新一次，失败转登录，不在 localStorage 保存 token。
- 找回密码：邮箱验证码重置，与注册复用同一发码链路（`purpose` 区分）。
- 验证码邮件同步调用 SMTP，超时 5 秒；仅在 SMTP 接受后返回 200，失败返回 503 并使该码失效；200 不保证收件箱送达。普通业务通知仍走 Celery。对不符合目的条件的邮箱返回相同通用文案，避免以业务响应枚举账号。
- 发码按邮箱/用途 60 秒一封，IP 每小时最多 20 次（含被抑制的请求）；Redis 原子限频。验证码用途隔离，数据库只存哈希，校验与 attempts/consumed_at 在行锁事务内完成，最多试错 5 次且只能成功消费一次；重发使旧码失效。
- Refresh 7 天轮转并拉黑旧值；登出拉黑该 Refresh 和当前 Access jti（Redis 保留至过期），清除 Cookie。JWT 携带 users.token_version，密码重置/禁用递增版本，Access/Refresh 每次认证校验版本及账号状态，旧 token 立即失效。并发刷新由前端合并，重放旧 Refresh 返回 401。
- `GET /api/v1/me/` 返回 user + profile + **grants 列表**（角色×作用域展开），前端据此渲染菜单与按钮。

### 3.2 文件流

上传：前端 → 后端鉴权与校验（大小/类型/扩展名三重）→ 私有桶暂存 → 返回 upload_id。Redis 用 24 小时有效的服务端记录绑定用户、报名与文件元数据；客户端不能提交任意 storage_key。首次提交/重提时确认暂存归属，按本轮 submission_no 写 registration_files（round_no 同值）；沿用旧附件须按 file_id 验证原报名与材料权限，复制本轮引用而不覆盖旧行。临时对象清理跳过所有历史文件引用，不只检查当前版本。
下载/预览：后端签发 15 分钟预签名 URL；管理端导出走 Celery 异步生成 + 通知链接。内部上传用 S3_ENDPOINT，签名用独立客户端连接 S3_PUBLIC_ENDPOINT，后者须可被浏览器访问；签名后禁止改写 host/path。私有桶不开放匿名访问；若采用浏览器直传，CORS 只允许 SITE_BASE_URL 对应 origin 和实际方法/请求头。

证件照复用媒体私有桶：multipart 经后端鉴权与图片解码/重编码后上传，单张 ≤ 5MB、解码后最多 2000 万像素；拒绝 SVG、动图与伪造 MIME。照片读取复用 profile:read 作用域检查，本人可访问自己的照片；签名链接有效期 5 分钟，鉴权响应 Cache-Control: no-store，不在公开名单返回照片 key/URL。对象替换/删除的事务顺序见 04 §8。

### 3.3 证书生成流

名单确认（roster → confirmed）→ 按冻结报名成员（排除 coach）在事务内幂等创建 certificates(queued) → 事务提交后派发任务 → Celery chord 并发生成 PDF（WeasyPrint 渲染 HTML 模板，字体/版式在 `templates/certificate/`）→ 生成 `qr_token` 指向 `/verify/{qr_token}` 公开页（Nginx 直连 Django，AllowAny 限流）→ 每张 generated 后置 issued 并通知对应成员 → 本名单全部证书 issued 后名单才进入 issued。
失败重试 3 次后置 failed 并告警，名单保留 confirmed；重试复用原行和编号，不重复建证。任务持有行锁复核状态，已 revoked 时停止；补发只允许相同获奖记录与成员，并使用新编号。

### 3.4 单位/队伍审核、准入与提交历史

- 申请人/审核人、正式版本指针与 access_snapshot 由后端生成，不接受客户端指定；提案只接受业务字段白名单，复用原申请时再次校验同申请人及单位/队伍归属。
- 单位创建先保存申请，平台批准事务内创建组织树节点；队伍创建/修改由所属单位管理员审核、平台可代审，禁止申请人自审。队伍申请包含完整提案，修改带 base_revision_id；仅批准时切换正式资料与成员，保留旧审核版本。
- submit/resubmit 锁定届次、队伍、报名（所有入口统一此顺序），团队分支校验单位启用、队伍已审核版本、准入及资格，个人分支按个人资格校验后新建 registration_submissions 和本轮成员/文件，再切 current_submission_no。名单维护也先锁届次；队伍批准锁队伍再锁申请。历史快照按轮次读取，不从当前队员/档案重建。
- 报名驳回可修改重提（同一编号、新 submission_no），包括已通过报名经授权驳回；锁定名单或非作废证书存在时拒绝该动作。审核提交的 submission_no 与当前版本不符时返回 40906，防止旧页面审批新内容。
- allowlist 按本届正式队伍编号映射 team_id；预览记录导入摘要与版本，确认时重查权限、匹配及 team_access_version，禁止导入身份/成员资料并自动放行。通过名单公示与准入名单是独立资源。
- 当前报名是跨届历史只读摘要的授权入口；分页显式投影公开人员字段与历届结果，隔离历史附件/联系方式/证件/照片及内部意见，每次查询审计。团队相关基座/接口在里程碑 2 启用。

### 3.5 高峰与削峰

报名提交 = 单事务多表写（registrations + members 快照 + files + approval 初始记录），数据库唯一索引兜底防重复；截止前流量靠 Nginx + Redis 限流（用户级 10 req/min）。第一版不引入消息队列削峰提交，Celery 只承担异步任务。

### 3.6 审计

Django middleware 标记请求上下文（actor/ip/request_id），service 层显式写 audit_log（关键动作清单见 PRD §3.8）；`detail` 存变更 diff，敏感值脱敏后入日志。

## 4. 前端架构

```
compsphere-web/
├── src/
│   ├── api/            # axios 实例 + 各域 API 模块
│   ├── stores/         # auth（token/grants）、app（locale/theme）、notifications
│   ├── locales/        # zh-CN.ts / en-US.ts，按业务域组织翻译键
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

### 4.1 语言与主题偏好

- 使用 vue-i18n，翻译键按业务域组织；后端将 zh-CN/en-US 分别映射到 Django zh-hans/en 翻译目录；Element Plus、路由标题、表单校验、空状态、错误提示与可访问名称同步切换，文档 lang 随语言更新。业务数据保持用户原文，系统通知使用收件人语言模板，入队时记录目标语言（未设置则中文）。
- 未登录默认中文，读取本地选择；登录后 GET /me 的 locale/theme 为准。切换立即应用并缓存，同时 PATCH /me/preferences，仅保存有限枚举；保存失败保留当前显示并提示偏好未同步。
- theme 存用户选择 light/dark/system，system 才监听 prefers-color-scheme；以语义令牌切换 Radix 与 Element Plus 主题，并同步原生控件 color-scheme。页面首次绘制前应用本地缓存，避免白屏闪烁；不为主题切换添加动画。

## 5. 环境与配置

- 配置全部环境变量注入（`django-environ`），仓库只提交 `.env.example`。
- 环境：dev（docker compose 全家桶）/ staging / prod；prod 至少：应用 2 worker、Postgres 独立、每日 `pg_dump` + 文件增量同步、30 天保留。
- 密钥：JWT SIGNING、SECRET_KEY、MinIO key、FIELD_ENCRYPTION_KEY / ID_HASH_PEPPER 分环境独立，禁止入仓。
