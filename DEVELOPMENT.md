# 开发指南

代码规则见 [CODING_STANDARDS.md](CODING_STANDARDS.md)，界面规则见 [FRONTEND_DESIGN_GUIDELINES.md](FRONTEND_DESIGN_GUIDELINES.md)，协作流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。本文仅维护日志约定，避免重复。

## 1. 当前状态

前后端已实现首批核心链路；实际覆盖和验证边界见各工程README及 [审阅待办](docs/10-review-notes.md)。以下为日志要求，并非所有观测项均已实现。

## 2. 日志与可观测性

### 2.1 输出与关联

- structlog 输出 JSON 到 stdout；技术日志与数据库 `audit_logs` 分开，分别用于排障与业务留痕。
- 服务端生成 `request_id`；仅采信受信代理提供且通过长度/格式校验的请求标识。写入响应和日志上下文，经 Celery headers 透传。
- 客户端 IP 仅从受信代理链解析；当前 Nginx 追加的 `X-Forwarded-For` 首项可由客户端伪造，后端不得直接采信。
- INFO 记录请求完成与业务动作，WARNING 记录慢查询/重试，ERROR 记录异常并带堆栈。DEBUG 仅本地默认启用。

### 2.2 请求与数据库

| 日志 | 必需内容 |
| --- | --- |
| 请求完成 | request_id、method、路由模板、status、duration_ms、user_id、权限 scope、biz_code、queries、queries_ms |
| SQL 汇总 | 查询数量、总耗时、最慢耗时；通过 `connection.execute_wrapper` 采集 |
| 慢 SQL/异常 | request_id、耗时、表名、操作类型、参数化 SQL 模板；默认慢阈值 200ms |
| Celery | request_id、task_name、task_id、retry_no、duration_ms、result_state |

静态资源和健康检查跳过请求日志。生产关闭全量 SQL 明细；仅在本地用合成数据启用 `LOG_SQL_ALL`。异常记录一次，避免中间件与 service 重复堆栈。

### 2.3 敏感数据

- 不记录请求/响应正文、认证头、密码、验证码、token、预签名 URL 或绑定 SQL 参数；SQL 模板也须移除字面量。
- 证件最多末四位，手机号保留前 3 后 4，邮箱仅域名；哈希、密文也不向前端或日志输出。
- 错误消息面向用户，技术细节留在日志。开发环境同样遵守脱敏要求。
- 审计记录操作人、对象、范围、动作、理由和导出字段清单；变更 diff 按字段白名单过滤。

### 2.4 业务事件

新增接口、任务和写路径接入统一日志；关键动作使用集中定义的事件名：

| 事件前缀 | 动作 |
| --- | --- |
| `role.grant` / `role.revoke` / `team.member` | 管理员交接授权撤销/授予，成员 joined/left、自主退队、赛季绑定建立及平台特批换队申请/审核/执行；记录范围、旧/新队伍、申请 ID、操作者、时间与理由，不记录离职履历 |
| `auth.login` / `rbac.denied` | 登录结果、权限拒绝 |
| `competition.created` | 平台创建赛事草稿；仅记录操作者与赛事 ID，不记录表单正文 |
| `edition.created` | 创建届次草稿；记录届次、赛事及赛季 ID，不记录表单正文 |
| `event.created` | 创建届次赛项，记录赛项和届次 ID，不记录表单正文 |
| `season.created` / `season.activated` / `season.current_changed` | 平台创建、激活、切换赛季；切换另记原赛季 ID |
| `registration` | submitted、cancelled、withdrawn、resubmitted、approved、rejected、returned（均带 submission_no） |
| `org.transfer` / `season` | 交接 submitted/released/accepted/mediated/rejected/withdrawn/completed；记录双方单位、申请、归属版本；赛季创建/激活/归档及当前切换，队伍赛季注册申请/审核/撤销（带 team_id、season_id、申请 ID），绑定事件带 season_id |
| `org.request` / `team.request` | submitted、cancelled、approved、rejected、returned；申请 ID、base_revision_id、审核人及理由摘要 |
| `account.provision` / `account.reset` / `identity.change` | 代建、核验重置、证件申请/取消/审核/应用；仅记对象 ID、版本和理由，禁止临时密码/证件内容 |
| `outbox` | 领取、投递、重试、失败、重放；business_key、版本、次数与结果，不记 payload 敏感内容 |
| `roster` | confirmed、unlocked、published、unpublished |
| `edition.team_access` / `team.history` | 准入模式与名单导入/变更、审核历史上下文读取（actor、当前报名、team_id） |
| `certificate` | generate.started/succeeded/failed、revoked、reissued |
| `import` / `export` / `file` | 冲突、任务结果、上传与签名行为 |

附业务主键、actor 与 request_id；补发事件携带 `reissue_of`/`supersedes_serial`，不含个人信息原文。

### 2.5 运维与验收

- `LOG_SLOW_QUERY_MS=200`、`LOG_SLOW_REQUEST_MS=800`、生产 `LOG_SQL_ALL=false`；变量定义见 `.env.example`。
- Compose 已配置 json-file 日志轮转（每文件 50MB、最多 5 个）；部署时确认日志驱动生效。
- 备份成功与失败都记录结果；上线前完成异地备份和恢复演练。
- 验收：一次请求可关联到 SQL 汇总和异步任务；越权/异常路径有记录；日志不含敏感样本原文。
