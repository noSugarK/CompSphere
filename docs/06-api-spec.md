# 06 API 规范与端点草案

**版本**：v1.3（2026-11-17）。基址 `/api/v1`，格式 JSON，认证 `Authorization: Bearer <access_token>`。

v1.1 变更：错误码表补 42205-42208 与 40904、新增发码与公示接口、报名筛选加 `event` 参数、明确成员字段分级。

> 本文是接口设计约定与端点草案。实现后用 drf-spectacular 导出 OpenAPI；差异需确认是实现缺陷还是契约变更，再同步代码、本文与生成结果，不能以生成结果自动覆盖需求。

---

## 1. 通用约定

### 1.1 响应包裹

```jsonc
// 成功
{ "code": 0, "message": "ok", "data": { }, "request_id": "..." }
// 分页 data
{ "code": 0, "message": "ok", "data": { "items": [], "page": 1, "page_size": 20, "total": 138 }, "request_id": "..." }
// 失败（HTTP 状态码同步语义：400/401/403/404/409/422/429/500）
{ "code": 40301, "message": "无该赛事的审核权限", "data": null, "request_id": "..." }
```

### 1.2 业务错误码段

| 段 | 域 | 示例 |
| --- | --- | --- |
| 401xx | 认证 | 40101 token 过期、40102 验证码错误或已失效、40104 邮箱未验证 |
| 403xx | 权限 | 40301 作用域内无权限、40302 角色冲突、40303 不得审核自己提交的申请 |
| 404xx | 资源 | 40401 不存在或无权查看（合并防枚举）；公示名单未发布也返回本码，不返回 403（02 §4.7） |
| 409xx | 冲突/状态 | 40901 重复报名、40902 非法状态迁移、40903 名单已锁定、40904 证件号已绑定其他账号、40905 幂等键与请求不一致、40906 提交/队伍版本已过期、40907 单位/队伍编号或名称冲突 |
| 422xx | 校验 | 42201 赛项人数不符、42202 材料缺失、42203 时间窗外、42204 年级或年龄不符、42205 学段与组别不符、42206 身份证号校验位错误、42207 赛项与组别组合未开放、42208 缺少指导教师、42209 不支持的语言或主题、42210 照片格式/内容无效、42211 队伍未通过资料审核、42212 不在本届队伍准入名单、42213 单位未通过创建审核 |
| 429xx | 限流 | 42901 请求过频（含验证码频率限制；返回 Retry-After） |

错误码三处同步（07「文档即代码」）：本表 ↔ `core/constants.py` ↔ 前端 `utils/errors.ts` 文案映射。新增校验分支必须先在此登记，代码里出现未登记的码视为缺陷。v1.1 起 `42204` 由「对象/年级限制」改为「年级或年龄限制」——原 `target_audience`（参赛对象多选）随组别收敛为学段而删除。

照片上传超过 5MB 返回 HTTP 413 / 41301，解码后像素超限或伪造图片返回 422 / 42210。照片读取和偏好响应使用 Cache-Control: no-store。

SMTP 发送失败返回 HTTP 503 / 50301；Cookie 与 token 生命周期见 05 §3.1。历史 40103 不再用于限流，未实现前统一为 42901。

### 1.3 其他

- 语言使用 Accept-Language，支持 zh-CN / en-US（接受 zh/en 简写），未支持时回退 zh-CN；message 与字段校验提示随请求语言变化，code/status/字段名保持稳定。错误可附 params 供前端按 code 翻译，未知 code 使用本地通用提示与 request_id；语言切换不改变错误码。

- 筛选：`?status=&group_id=&org_id=&search=&ordering=-created_at`；时间范围 `?created_after=&created_before=`（ISO8601 UTC）。
- 报名提交、证书批量生成必填 `Idempotency-Key`，按用户+路由隔离并绑定请求体摘要；同键同体返回原结果，同键异体返回 40905，缓存至少 24 小时；超期由数据库唯一约束兜底。
- 软删除资源默认不返回；`?include_deleted=1` 仅管理端权限可用。
- 门户接口使用 `/public/*` 前缀及 serializer 白名单；公示仍按档位校验登录。公开验证页统一为站点根 `/verify/{qr_token}`，不再另设 /public/certificates/verify 别名。

## 2. 端点目录

### accounts / me

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | `/auth/register` | 注册（email + code，v1.1 起不含手机号验证） | 公开 |
| POST | `/auth/verify-code/send` | 发邮箱验证码（body: `email`, `purpose`）；60s 限频 | 公开 |
| POST | `/auth/login` / `/auth/refresh` / `/auth/logout` | 登录返回 access + 设置 refresh Cookie；刷新轮转；登出清除 Cookie | 公开/会话校验 |
| POST | `/auth/password/reset/*` | 发码/重置（复用 verify-code 通道） | 公开 |
| GET | `/me` | 当前用户 + profile + grants + locale/theme；不直接返回私有照片 key | 登录 |
| PATCH | `/me/preferences` | body: locale / theme，允许部分更新；未知值 42209 | 登录，仅本人 |
| PUT/DELETE | `/me/photo` | multipart 单个 file 上传/替换证件照；DELETE 清除引用与对象 | 登录，仅本人 |
| GET | `/me/photo` / `/profiles/{id}/photo` | 鉴权后返回 photo_url（5 分钟有效）与 expires_at；无照片 404 | 本人 / profile:read + 人员作用域 |
| PATCH | `/me/profile` | 完善/修改本人档案（含身份证号，服务端加密落库） | 登录 |

发码正常响应统一为「若邮箱符合条件，验证码将发送，请检查收件箱」，不区分是否已注册。可发邮箱同步 SMTP 接受后返回 200（不保证投递），发送失败返回 503；限流返回 429 + Retry-After。`purpose` 绑定验证码，register 的码不能用于 reset；单次消费、重发失效与 IP/邮箱限频见 05 §3.1。

### 用户与人员（管理）

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET/POST | `/users`；GET/PATCH/POST(disable) `/users/{id}` | 账号管理 | `user:*` |
| GET | `/users/{id}/roles` POST/DELETE 同 | 角色授予（body: role, scope_type, scope_id） | `user:assign_role` |
| GET/PATCH | `/profiles/{id}`；POST `/profiles/{id}/review` | 人员档案与审核 | `profile:*` |
| POST | `/profiles/import`（异步）/ GET `/exports/{id}` | Excel 导入导出 | `user:import/export` |

### 组织

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/orgs` / `/orgs/{id}`；PATCH `/orgs/{id}`；POST `/orgs/{id}/disable` | 正式单位查询/维护；POST /orgs 改为发起申请，不直接建立单位 |
| GET/POST | `/orgs/{id}/members`；PATCH/DELETE `/org-members/{id}` | 成员管理（`org:manage_members`） |
| GET/POST | `/org-creation-requests`；GET/PATCH `/org-creation-requests/{id}` | 申请人只读写本人申请，平台有 org:review_create 可查看审核队列；创建用 org:apply_create，草稿含建议父级和单位资料 |
| POST | `/org-creation-requests/{id}/submit|withdraw|resubmit` | resubmit 复制原被驳回/退回申请为新草稿，以 resubmission_of 关联原记录并返回新 ID，原申请留存；仅申请人 |
| POST | `/org-creation-requests/{id}/review` | approve/reject/return + comment；org:review_create，仅平台且禁止自审，通过后返回 result_org_id |
| POST | `/orgs/join-requests`；POST `/orgs/join-requests/{id}/approve|reject` | 已存在单位的成员加入申请，不替代单位创建审核 |
| GET | `/orgs/{id}/stats` | 参赛/获奖统计 |

### 队伍（里程碑 2）

正式队伍只读接口为 GET /teams、/teams/{id}、/teams/{id}/members；GET /teams/{id}/registrations 返回权限内历史摘要。创建/编辑/改成员统一发起申请，不能 PATCH 正式资料立即生效。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/team-change-requests`；GET/PATCH `/team-change-requests/{id}` | 申请人查看本人提案，有 team:review 者查看权限内审核队列；kind=create/update，修改须带 base_revision_id；team:create/update/manage_members 与单位范围校验 |
| POST | `/team-change-requests/{id}/submit|withdraw|resubmit` | 申请人操作；resubmit 复制被驳回/退回提案为新草稿，以 resubmission_of 关联原记录并返回新 ID，保持旧提案与审核记录 |
| POST | `/team-change-requests/{id}/review` | approve/reject/return + comment；team:review，单位树内或平台代审，禁止自审，旧版本冲突 40906 |
| GET | `/team-change-requests/{id}/review-context` | 申请提案、与生效版本的差异及分页历史摘要；team:review + 单位范围，不扩展赛事附件权限 |

### 赛事 / 届次 / 赛项 / 组别

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/competitions`；GET/PATCH `/competitions/{id}` | `competition:*` |
| POST | `/competitions/{id}/publish` `/archive` | 状态动作 |
| PUT | `/competitions/{id}/units` | 主办/承办/协办设置（`competition:manage_units`） |
| GET/POST | `/competitions/{id}/admins`；DELETE `/admins/{user_id}` | `competition:manage_admins` |
| GET/POST | `/competitions/{id}/editions`；GET/PATCH `/editions/{id}` | `edition:*` |
| POST | `/editions/{id}/publish` `/close`；PUT `/editions/{id}/approval-mode` | 状态与审核模式配置 |
| GET/POST | `/editions/{id}/events`；PATCH/DELETE `/events/{id}`；POST `/events/{id}/enable|disable` | 赛项（`event:*`，v1.1） |
| GET/POST | `/editions/{id}/groups`；PATCH/DELETE `/groups/{id}`；POST `/groups/{id}/enable|disable` | 组别（`group:*`） |
| GET/POST | `/editions/{id}/offerings`；PATCH/DELETE `/offerings/{id}` | 开放组合（v1.1）。已有报名的组合不可删除，服务层按 offering_id 的 RESTRICT 返回冲突，只能停用 |
| GET/PUT | `/editions/{id}/team-access` | 查看/设置 team_entry_mode 与 team_access_version；写入须带当前版本，权限 edition:manage_team_access（里程碑 2） |
| GET/POST | `/editions/{id}/team-allowlist`；DELETE `/editions/{id}/team-allowlist/{team_id}` | 名单查询/增补/撤销（标 revoked）；edition:manage_team_access，不公开全量 |
| POST | `/editions/{id}/team-allowlist/import-preview` / `/import-confirm` | 按队伍编号预览匹配与错误，返回预览令牌及 team_access_version；确认校验版本并事务写入，只导入已明确匹配的队伍，不自动创建队伍；权限同上 |
| GET | `/editions/{id}/eligible-groups?team_id=` | 该队伍或本人有资格的组别，报名页据此渲染选项，不给自选（v1.1） |
| GET | `/public/competitions` `/public/editions/{id}` | 门户公开列表/详情 |
| GET | `/public/editions/{id}/roster?event=&group=` | 通过名单公示页（`AllowAny`；判定顺序见 02 §4.7） |
| POST | `/editions/{id}/roster/publish` `/unpublish` | 发布/下架公示名单（发布用 `roster:publish`，下架用 `roster:unpublish`，v1.1） |
| PATCH | `/editions/{id}/roster-publication` | 设置公示档位与字段白名单（`roster:publish`） |

### 报名与审核

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET/POST | `/editions/{edition_id}/registrations` | 我的报名列表 / 新建（draft 或直接 submit） | `registration:create` |
| GET | `/registrations/{id}` | 详情（成员、文件、审核记录）；成员字段按查看者身份分级，见下方说明 | read_own / read scoped |
| PATCH | `/registrations/{id}` | 编辑工作副本（draft / returned / org_returned / rejected / org_rejected），不覆盖已提交版本 | 提交人 |
| POST | `/registrations/{id}/submit` `/resubmit` `/withdraw` | 状态动作（03 §1） | 提交人 |
| DELETE | `/registrations/{id}` | 删除草稿 | `delete_draft` |
| POST | `/registrations/{id}/files` | 上传暂存材料（multipart → upload_id），归属/过期校验后在 submit/resubmit 建本轮文件引用 | 提交人 |
| GET | `/registrations?edition=&group=&org=&status=` | 管理列表 | `registration:read` |
| POST | `/registrations/{id}/approval` | body: `{action: approve|reject|return, comment, submission_no}`；已 approved 执行 reject 额外需 approval:reject_approved，并受名单锁定/证书限制 | `approval:review_*` |
| POST | `/registrations/batch-approval` | body: `{items:[{id,submission_no}], action, comment}`；逐项检查版本与权限，已通过报名的批量驳回也需 reject_approved | `approval:batch_review` |
| GET | `/registrations/{id}/team-review-context` | 本场快照、关联队伍资料版本、分页历届各提交轮次摘要与历史队员；仅团队报名，按 02 历史上下文规则鉴权并审计 | registration:read + approval:review_* + team:read_review_history |
| GET | `/registrations/{id}/submissions` / `/submissions/{no}` | 分页提交历史/单版快照，按当前报名同等归属与字段权限裁剪，不返回其他队员敏感字段 | read_own / read scoped |
| GET | `/registrations/{id}/approval-records` | 审核历史 | `approval:read_records` |
| POST | `/registrations/export` | 异步导出（审计含字段清单） | `registration:export` |

**成员字段分级**：read_own 可读取本人和同队成员 public_info，不能读取 snapshot_enc、证件密文或哈希。管理端按范围授权后解密快照，按字段白名单输出必要内容；完整证件号对所有角色都不返回，最多末四位。

| 查看者 | 可见成员范围 | 证件字段 |
| --- | --- | --- |
| 报名提交人 / 队长（`read_own`） | 本人 + 同队成员的 `public_info` | 不可见 |
| 教练（本队） | 本队全部成员 `public_info` | 不可见 |
| `org_admin`（本单位初审理由） | 本单位成员完整快照 | 末四位 |
| `competition_admin` / `reviewer`（scoped） | 该届次全部完整快照 | 末四位，需 `registration:read` |
| `platform_admin` | 管理范围内的字段白名单 | 最多末四位，无明文例外 |

`GET /registrations?edition=&event=&group=&org=&status=`：管理列表新增 `event` 与 `group` 两个筛选参数（v1.1，原先只有 group）。

### 奖项 / 名单 / 证书

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/editions/{id}/awards`；PATCH/DELETE `/awards/{id}` | `award:config` |
| GET | `/editions/{id}/rosters?offering_id=`；PUT 条目增删 `/roster/records` | 按开放组合查询；不传 offering_id 时为届次通用名单，条目仅从 approved 报名挑选 |
| POST | `/roster/import`（异步，batch_no 主匹配）→ GET `/roster/import-pending` → POST `/import-pending/{id}/resolve` | 导入与人工确认 |
| POST | `/roster/submit` `/approve` `/reject` `/unlock` | 名单状态机动作 |
| POST | `/certificates/generate` | 批量生成（幂等键）；GET `/certificates?...` 列表；POST `/certificates/{id}/revoke|reissue` |
| GET | `/me/certificates` | 仅 recipient_member_id 对应本人且已 issued 的证书，返回短期预签名 PDF；完整证件号不输出 |
| GET | `/verify/{qr_token}` | 公开验证（Nginx 独立限流路径；脱敏最小字段 + 有效性） |

### 通知 / 统计 / 审计 / 系统

`/notices` CRUD+publish；`/me/notifications` + `/read`；`/stats/dashboard`（P0 计数）与 `/stats/registrations?dim=group|org`（P1 图表）；`/audit-logs?actor=&resource=&date=`（`audit:read`）；`/roles` `/permissions`（`system:manage_roles`）。

报名版本规则：GET /registrations/{id} 的审核资料来自 current_submission_no 对应不可变提交；可编辑工作副本仅向有编辑权的人返回。PATCH 不修改旧提交。resubmit 在同一报名编号下新增轮次，rejected/org_rejected 也允许该动作；所有校验按当前时间窗、队伍版本与准入执行。审核请求须带 submission_no，过期 40906。

偏好示例：PATCH /me/preferences，body 为 {"locale":"en-US","theme":"dark"}，成功 data 返回已保存的两个字段；GET /me 同步返回它们。照片只接受文件上传，不接受客户端提交任意 storage_key 或外部 URL；后端生成并保存 key，响应返回鉴权签名链接，不将链接存入数据库。

## 3. 关键接口请求示例

报名提交（团队）：

```jsonc
POST /api/v1/editions/12/registrations   // Idempotency-Key: uuid
{
  "offering_id": 7,
  "enrollment_kind": "team",
  "team_id": 88,
  "coach_user_id": 45,
  "contact": { "name": "李四", "phone": "138...", "email": "..." },
  "form_data": { "project_title": "…" },
  "consents": { "id_number_usage": true },
  "submit": true
}
→ 201 { "code": 0, "message": "ok", "data": { "id": 900, "batch_no": "REG-12-3F9A21C7", "status": "pending_review" }, "request_id": "..." }
```

非法迁移返回 HTTP 409，包裹内 `code=40902`，例如 `message="这条报名还需单位初审，暂时无法复审。"`；内部状态诊断写入日志。
