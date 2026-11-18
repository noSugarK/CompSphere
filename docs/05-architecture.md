# 05 技术架构

**版本**：v1.6（2026-11-17）

v1.4：补无邮箱代建、证件登录与更正、事务 outbox；验证码受理与实际送达分离。

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
| 异步 | Celery | 5.x | 业务通知邮件、证书 PDF、导入任务；验证码也通过持久化 outbox 投递 |
| 定时 | django-celery-beat | | 状态提醒、清理 |
| 对象存储 | MinIO（开发/自建）/ S3 兼容 | | 报名材料、证书 PDF，私有桶 + 预签名 URL |
| 组织树 | django-treebeard | 2.x | Materialized Path，`organizations` 继承 `MP_Node`（v1.1，取代裸 parent_id 递归查询） |
| 导入导出 | django-import-export | 4.x | 获奖名单/人员 Excel；异步任务里直接调 `Resource` API，不走 admin 集成（v1.1） |
| 邮件 | Django email backend + SMTP | | 注册与找回密码验证码、审核结果通知；发信域名需配 SPF/DKIM，否则验证码邮件进垃圾箱等于注册不可用（v1.1，上线前置条件） |
| 字段加密 | cryptography（Fernet） | 42+ | 身份证/护照列加密，P0 交付；密钥 `FIELD_ENCRYPTION_KEY`，哈希 pepper 另用 `DOC_HASH_PEPPER`（v1.1） |
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
│   ├── profiles/               # user_profiles、人员信息审核、证件加解密
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

### 3.1 账号、证件与认证

- 自助注册走邮箱验证码，所属单位管理员可代建无邮箱学生账户。username 使用随机系统标识；代建/重置的临时密码强随机、短期有效（7 天），仅交付一次，不出现在日志、导出或 outbox，首次登录只允许改密/补齐资料。
- 登录显式选择 email/document；证件登录输入 type、country、number、password，以 HMAC 查当前绑定后验证 Argon2。身份证 CN 校验格式/校验位；护照按签发国校验，规范化去首尾空格、字母大写且保留前导零；不以格式正确代替实名核验。用户名/证件/密码错误统一 40105，按账号摘要+IP 限流。
- 首次证件绑定与已绑定更正分开。更正须单位/平台管理员审核，禁止自审和审核自己的证件；单位只处理本单位普通成员，涉及管理账户/争议由平台。批准事务内检查 identity_version 与唯一性后切换并释放旧号、递增 token_version；旧会话立即失效，旧证件不能再登录旧账号，历史报名不更改。
- 有已验证邮箱可自助找回；有当前有效主属单位的普通学生账户，也可由该单位管理员核验后重置，不区分代建/自助注册或是否绑定邮箱。转移完成后权限随当前主属单位切换，原代建单位不保留重置权。无归属单位且无法自助找回时，邮件联系平台管理员核验处理，不凭邮件内容直接重置。重置强制首次改密、撤销旧会话、留审计并通知；单位管理员不得重置管理账户，代建接口不得覆盖既有账户密码。重置 service 锁学生并校验提交的 primary_membership_id/affiliation_version，转移完成后旧单位请求失败；明文临时密码不进入任务或审计。
- Access 仅在前端内存，Refresh 为 HttpOnly/Secure/SameSite=Strict Cookie（Path=/api/v1/auth）；刷新/登出校验 Origin/CSRF。Refresh 7 天轮转拉黑旧值；登出拉黑 Refresh 和当前 Access jti，JWT 每次校验 token_version/账号状态；待改密会话严格限制为改密等必要端点。
- 发码 HTTP 路径不查询账号存在性：合法格式和限频通过后，一律原子写验证码请求及 outbox，返回 202 通用文案，不返回账户状态或投递状态；受理存储不可用才统一 503。任务端判断 purpose/账户条件并发送，不符合条件也走同一受理结果。
- 邮箱/用途 60 秒一次，IP 每小时 20 次；哈希用于验证，加密 code 仅供发送重试，发送完成/过期即清除。验证码 10 分钟、最多 5 次失败、行锁单次消费；重发使旧码失效。SMTP 超时 5 秒只影响任务重试/告警，不改变匿名请求响应。
- GET /me 返回用户、档案、grants 与 locale/theme，证件只显示类型/签发国/末四位；无邮箱通知优先站内，邮件仅送已验证邮箱。

### 3.2 文件流

上传：前端 → 后端鉴权与校验（大小/类型/扩展名三重）→ 私有桶暂存 → 返回 upload_id。Redis 用 24 小时有效的服务端记录绑定用户、报名与文件元数据；客户端不能提交任意 storage_key。首次提交/重提时确认暂存归属，按本轮 submission_no 写 registration_files（round_no 同值）；沿用旧附件须按 file_id 验证原报名与材料权限，复制本轮引用而不覆盖旧行。临时对象清理跳过所有历史文件引用，不只检查当前版本。
下载/预览：后端签发 15 分钟预签名 URL；管理端导出走 Celery 异步生成 + 通知链接。内部上传用 S3_ENDPOINT，签名用独立客户端连接 S3_PUBLIC_ENDPOINT，后者须可被浏览器访问；签名后禁止改写 host/path。私有桶不开放匿名访问；若采用浏览器直传，CORS 只允许 SITE_BASE_URL 对应 origin 和实际方法/请求头。

证件照复用媒体私有桶：multipart 经后端鉴权与图片解码/重编码后上传，单张 ≤ 5MB、解码后最多 2000 万像素；拒绝 SVG、动图与伪造 MIME。照片读取复用 profile:read 作用域检查，本人可访问自己的照片；签名链接有效期 5 分钟，鉴权响应 Cache-Control: no-store，不在公开名单返回照片 key/URL。对象替换/删除的事务顺序见 04 §8。

### 3.3 证书生成流

名单确认（roster → confirmed）→ 按 award_records 固定的审核通过 submission_no 及其学生队员（不包含教练，奖项无组织/单位类别）在事务内幂等创建 certificates(queued) → 同事务写 async_outbox → dispatcher 至少一次投递 Celery chord 并发生成 PDF（WeasyPrint 渲染 HTML 模板，字体/版式在 `templates/certificate/`）→ 生成 `qr_token` 指向 `/verify/{qr_token}` 公开页（Nginx 直连 Django，AllowAny 限流）→ 每张 generated 后置 issued 并通知对应成员 → 本名单全部证书 issued 后名单才进入 issued。
名单解锁递增 award_rosters.version，证书任务与回调必须匹配 roster_version，旧回调不能发放新版名单；旧获奖条目有证书引用时只退役并新建，不改写原条目。失败重试 3 次后置 failed 并告警，名单保留 confirmed；重试复用原行和编号，不重复建证。任务持有行锁复核状态，已 revoked 时停止；补发只允许相同获奖记录与成员，并使用新编号。

### 3.4 单位/队伍审核、准入与提交历史

- 当前赛季由平台 set_current 事务切换，锁定全局赛季配置并递增缓存版本；不接受普通用户 season 参数改变参赛上下文。提交/重提同事务复核当前赛季和许可，审核通过只校验原报名赛季仍 active 及许可有效，允许处理切换前待审事项。季许可审核/撤销与报名共用许可行锁，无许可时锁队伍并由部分唯一索引兜底。

- 学生单位交接取得本人/监护人授权，原单位转出后目标单位接收；事务按学生→主属关系→申请加锁，校验版本、双方范围、独立处理人、无当前队伍，结束旧关系并新增关系，递增 affiliation_version/token_version，失效原单位人员权限缓存。原创建单位仅保留来源审计，不决定重置权；平台代办仅替原单位核验转出。
- 赛季归属到实际举办场次，系列资料可跨赛季复用；赛季队伍绑定先锁 season 行再按现有场次→队伍→学生→报名顺序处理。同赛季其他赛事不能另建学生绑定绕过资格。

- 申请人/审核人、正式版本指针与 access_snapshot 由后端生成，不接受客户端指定；提案只接受业务字段白名单，复用原申请时再次校验同申请人及单位/队伍归属。
- 单位创建先保存申请，平台批准事务内创建组织树节点；队伍创建仅平台审核并原子建立首次赛季许可；资料/成员修改由所属单位管理员发起，另一名有权单位管理员或平台审核，禁止申请人自审。队伍申请包含完整提案，修改带 base_revision_id；仅批准时切换正式资料与成员，保留旧审核版本。
- 队员全平台唯一当前归属，由 team_members 的部分唯一索引兜底；本人可自主退队，普通管理变更仍须审核；入队检查全部未归档赛季同赛项绑定，原队回归允许普通审核，其他队伍仅平台特批。首次通过报名建立持久绑定，退队/驳回不删除。记录成员时间段与审计，不覆盖旧行；报名提交取已审核版本与当前有效成员交集。队伍管理写入仅单位管理员（范围内全部队伍）或平台可用；教练查询必须额外校验本单位，代报限本人负责队伍，无队伍资料/成员写权限；管理员交接仅变更角色并失效授权缓存，不建离职档案。
- submit/resubmit 按赛季→届次→队伍→赛季许可→报名加锁（所有入口统一此顺序），团队分支校验单位启用、队伍已审核版本/赛项身份、对应赛季 approved 许可、准入及所选学段资格，个人分支按个人资格校验后新建 registration_submissions（含当时审核模式与提交人所选学段）和本轮成员/文件，再切 current_submission_no。名单维护也先锁届次；队伍批准锁队伍再锁申请。历史快照按轮次读取，不从当前队员/档案重建。
- 报名驳回可修改重提（同一编号、新 submission_no），包括已通过报名经授权驳回；锁定名单或非作废证书存在时拒绝该动作。审核提交的 submission_no 与当前版本不符时返回 40906，防止旧页面审批新内容。
- allowlist 按本届「队号 + 稳定赛项代码」映射 team_id；预览记录导入摘要与版本，确认时重查权限、匹配及 team_access_version，禁止导入身份/成员资料并自动放行。通过名单公示与准入名单是独立资源。
- 特批换队事务按所有相关届次 ID 升序→队伍 ID 升序→学生账户→相关报名/申请顺序加锁（与报名/队伍写入采用相同相对顺序），再次校验权限、绑定版本、当前归属和全部受影响报名。原队待审取消/已通过驳回后才切换归属与绑定，锁定名单/有效证书按既有阻断规则处理；目标报名须新轮次重提，不回写任何旧快照。事务失败不释放旧绑定或部分入队。
- 当前报名是跨届历史只读摘要的授权入口；分页显式投影公开人员字段与历届结果，隔离历史附件/联系方式/证件/照片及内部意见，每次查询审计。团队相关基座/接口在里程碑 2 启用。

### 3.5 异步可靠性

业务写入与 outbox 记录使用同一事务；on_commit 仅作唤醒优化，不承担可靠投递。dispatcher 用 SKIP LOCKED/租约领取，投递失败按退避保留重试，崩溃租约过期可重领；成功标 dispatched。确认丢失可能重复投递，任务按 business_key/业务状态幂等，不宣称恰好一次。超阈值告警并保留失败记录供重放，定时对账 queued 证书与 outbox。payload 只存 ID、版本、locale，不含敏感正文。

### 3.6 高峰与削峰

报名提交 = 单事务多表写（registrations + members 快照 + files + approval 初始记录），数据库唯一索引兜底防重复；截止前流量靠 Nginx + Redis 限流（用户级 10 req/min）。第一版不引入消息队列削峰提交，Celery 只承担异步任务。

### 3.7 审计

Django middleware 标记请求上下文（actor/ip/request_id），service 层显式写 audit_log（关键动作清单见 PRD §3.8）；`detail` 存变更 diff，敏感值脱敏后入日志。

## 4. 前端架构

```
compsphere-web/
├── src/
│   ├── api/            # axios 实例 + 各域 API 模块
│   ├── stores/         # auth（token/grants）、app（locale/theme）、notifications
│   ├── locales/        # zh-CN.ts / en-US.ts，按业务域组织翻译键
│   ├── router/         # 静态路由 + 基于 grants 的动态路由守卫
│   ├── layouts/        # PortalLayout（赛事门户/个人事务）、AdminLayout（仅管理/审核权限）、BlankLayout（登录/验证页）
│   ├── views/
│   │   ├── public/     # 门户：赛事列表、详情、证书验证页
│   │   ├── participant/  # 我的报名、我的证书、档案
│   │   └── admin/        # 组织/人员/赛事/组别/审核/获奖/证书/统计/系统
│   ├── components/     # 通用：ProTable、FormBuilder(P1)、上传、审批流时间线
│   └── utils/          # perm.ts: hasPerm()；download.ts；format.ts
```

界面入口：学生/教练在门户及个人中心完成事务；具有管理/审核 grants 的账号才显示管理控制台入口，同一账号兼具权限时同时开放相应功能，不设身份切换栏。原型的 URL 演示账号仅供设计比较，正式权限来自 GET /me，不接受 URL 授权。

约定：API 层禁裸 axios；表格页统一 ProTable（分页/筛选/导出插槽）；`hasPerm` 指令 `v-perm="'approval:review_single'"` 控制按钮；路由 meta 声明所需权限。

### 4.1 语言与主题偏好

- 使用 vue-i18n，翻译键按业务域组织；后端将 zh-CN/en-US 分别映射到 Django zh-hans/en 翻译目录；Element Plus、路由标题、表单校验、空状态、错误提示与可访问名称同步切换，文档 lang 随语言更新。业务数据保持用户原文，系统通知使用收件人语言模板，入队时记录目标语言（未设置则中文）。
- 未登录默认中文，读取本地选择；登录后 GET /me 的 locale/theme 为准。切换立即应用并缓存，同时 PATCH /me/preferences，仅保存有限枚举；保存失败保留当前显示并提示偏好未同步。
- theme 存用户选择 light/dark/system，system 才监听 prefers-color-scheme；以语义令牌切换 Radix 与 Element Plus 主题，并同步原生控件 color-scheme。页面首次绘制前应用本地缓存，避免白屏闪烁；不为主题切换添加动画。

### 4.2 组件复用与后续 AI 助手

标准控件使用 Element Plus；只在真实跨页重复时封装业务组件。手动操作与 AI 建议共享同一业务表单、领域 API、校验与执行命令，不以 DOM 自动点击或任意脚本实现 AI 控制。AI 网关须使用当前 actor 调用已有作用域校验及业务 service；检索前按授权过滤数据。完整设计与接入前验收见 [11-AI 助手设计](11-ai-assistant.md)，当前尚无 AI 服务或正式 Vue 工程。

## 5. 环境与配置

- 配置全部环境变量注入（`django-environ`），仓库只提交 `.env.example`。
- 环境：dev（docker compose 全家桶）/ staging / prod；prod 至少：应用 2 worker、Postgres 独立、每日 `pg_dump` + 文件增量同步、30 天保留。
- 密钥：JWT SIGNING、SECRET_KEY、MinIO key、FIELD_ENCRYPTION_KEY / DOC_HASH_PEPPER 分环境独立，禁止入仓。
