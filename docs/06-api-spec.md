# 06 API 规范与端点草案

**版本**：v1.1（2026-11-16）。基址 `/api/v1`，格式 JSON，认证 `Authorization: Bearer <access_token>`。

v1.1 变更：错误码表补 42205-42208 与 40904、新增发码与公示接口、报名筛选加 `event` 参数、明确成员字段分级。

> 本文是约定 + 端点目录草案；正式 OpenAPI schema 随开发在 backend 内用 drf-spectacular 生成，以生成结果为准，本文冲突时更新本文。

---

## 1. 通用约定

### 1.1 响应包裹

```jsonc
// 成功
{ "code": 0, "message": "ok", "data": { }, "request_id": "..." }
// 分页 data
{ "code": 0, "data": { "items": [], "page": 1, "page_size": 20, "total": 138 } }
// 失败（HTTP 状态码同步语义：400/401/403/404/409/422/429/500）
{ "code": 40301, "message": "无该赛事的审核权限", "data": null, "request_id": "..." }
```

### 1.2 业务错误码段

| 段 | 域 | 示例 |
| --- | --- | --- |
| 401xx | 认证 | 40101 token 过期、40102 验证码错误或已失效、40103 验证码发送过频、40104 邮箱未验证 |
| 403xx | 权限 | 40301 作用域内无权限、40302 角色冲突 |
| 404xx | 资源 | 40401 不存在或无权查看（合并防枚举）；公示名单未发布也返回本码，不返回 403（02 §4.7） |
| 409xx | 冲突/状态 | 40901 重复报名、40902 非法状态迁移、40903 名单已锁定、40904 证件号已绑定其他账号 |
| 422xx | 校验 | 42201 赛项人数不符、42202 材料缺失、42203 时间窗外、42204 年级或年龄不符、42205 学段与组别不符、42206 身份证号校验位错误、42207 赛项与组别组合未开放、42208 缺少指导教师 |
| 429xx | 限流 | 42901 请求过频 |

错误码三处同步（07「文档即代码」）：本表 ↔ `core/constants.py` ↔ 前端 `utils/errors.ts` 文案映射。新增校验分支必须先在此登记，代码里出现未登记的码视为缺陷。v1.1 起 `42204` 由「对象/年级限制」改为「年级或年龄限制」——原 `target_audience`（参赛对象多选）随组别收敛为学段而删除。

### 1.3 其他

- 筛选：`?status=&group_id=&org_id=&search=&ordering=-created_at`；时间范围 `?created_after=&created_before=`（ISO8601 UTC）。
- 写接口支持 `Idempotency-Key` 头（报名提交、证书批量生成必填）。
- 软删除资源默认不返回；`?include_deleted=1` 仅管理端权限可用。
- 公开接口（无需登录）：`/public/*` 前缀 + serializer 白名单（02 文档 §4.5）。

## 2. 端点目录

### accounts / me

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | `/auth/register` | 注册（email + code，v1.1 起不含手机号验证） | 公开 |
| POST | `/auth/verify-code/send` | 发邮箱验证码（body: `email`, `purpose`）；60s 限频 | 公开 |
| POST | `/auth/login` / `/auth/refresh` / `/auth/logout` | JWT | 公开/登录 |
| POST | `/auth/password/reset/*` | 发码/重置（复用 verify-code 通道） | 公开 |
| GET | `/me` | 当前用户 + profile + grants | 登录 |
| PATCH | `/me/profile` | 完善/修改本人档案（含身份证号，服务端加密落库） | 登录 |

发码接口只返回"已发送"，不区分邮箱是否已注册（防账号枚举，与 40401 同一口径）；`purpose` 参与验证码绑定，register 的码不能用于 reset。

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
| GET/POST | `/orgs`；GET/PATCH `/orgs/{id}`；POST `/orgs/{id}/disable` | 单位 CRUD（`org:*`） |
| GET/POST | `/orgs/{id}/members`；PATCH/DELETE `/org-members/{id}` | 成员管理（`org:manage_members`） |
| POST | `/orgs/join-requests`；POST `/orgs/join-requests/{id}/approve|reject` | 入驻申请 |
| GET | `/orgs/{id}/stats` | 参赛/获奖统计 |

### 队伍（里程碑 2）

`/teams` CRUD + `/teams/{id}/members`（add/remove/set-captain）+ `/teams/{id}/registrations`（参赛历史）。权限 `team:*`。

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
| GET | `/editions/{id}/eligible-groups?team_id=` | 该队伍或本人有资格的组别，报名页据此渲染选项，不给自选（v1.1） |
| GET | `/public/competitions` `/public/editions/{id}` | 门户公开列表/详情 |
| GET | `/public/editions/{id}/roster?event=&group=` | 通过名单公示页（`AllowAny`；判定顺序见 02 §4.7） |
| POST | `/editions/{id}/roster/publish` `/unpublish` | 发布/下架公示名单（`roster:publish`，v1.1） |
| PATCH | `/editions/{id}/roster-publication` | 设置公示档位与字段白名单（`roster:publish`） |

### 报名与审核

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET/POST | `/editions/{edition_id}/registrations` | 我的报名列表 / 新建（draft 或直接 submit） | `registration:create` |
| GET | `/registrations/{id}` | 详情（成员、文件、审核记录）；成员字段按查看者身份分级，见下方说明 | read_own / read scoped |
| PATCH | `/registrations/{id}` | 编辑（仅 draft / returned） | 提交人 |
| POST | `/registrations/{id}/submit` `/resubmit` `/withdraw` | 状态动作（03 §1） | 提交人 |
| DELETE | `/registrations/{id}` | 删除草稿 | `delete_draft` |
| POST | `/registrations/{id}/files` | 上传材料（multipart → storage_key） | 提交人 |
| GET | `/registrations?edition=&group=&org=&status=` | 管理列表 | `registration:read` |
| POST | `/registrations/{id}/approval` | body: `{action: approve|reject|return, comment}` | `approval:review_*` |
| POST | `/registrations/batch-approval` | body: `{ids[], action, comment}` | `approval:batch_review` |
| GET | `/registrations/{id}/approval-records` | 审核历史 | `approval:read_records` |
| POST | `/registrations/export` | 异步导出（审计含字段清单） | `registration:export` |

**成员字段分级（v1.1，身份证必填后新增）**：`read_own` 只能拿到本人那一条成员的 `real_name` / `role` / `school_level` / `grade`，**拿不到同队其他人的任何快照字段**——团队报名的 `registration_members.snapshot` 含全部成员的身份证号密文与哈希，若整体返回给提交人就构成越权泄露。分级由 serializer 依据查看者与每条成员记录的关系裁剪，不依赖前端不显示。

| 查看者 | 可见成员范围 | 证件字段 |
| --- | --- | --- |
| 报名提交人 / 队长（`read_own`） | 本人 + 同队成员的 `public_info` | 不可见 |
| 教练（本队） | 本队全部成员 `public_info` | 不可见 |
| `org_admin`（本单位初审理由） | 本单位成员完整快照 | 末四位 |
| `competition_admin` / `reviewer`（scoped） | 该届次全部完整快照 | 末四位，需 `registration:read` |
| 明文 | 仅 `platform_admin` 且单独走审计的动作 | — |

`GET /registrations?edition=&event=&group=&org=&status=`：管理列表新增 `event` 与 `group` 两个筛选参数（v1.1，原先只有 group）。

### 奖项 / 名单 / 证书

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/editions/{id}/awards`；PATCH/DELETE `/awards/{id}` | `award:config` |
| GET | `/editions/{id}/groups/{gid}/roster`；PUT 条目增删 `/roster/records` | 名单维护（从 approved 报名挑选） |
| POST | `/roster/import`（异步，batch_no 主匹配）→ GET `/roster/import-pending` → POST `/import-pending/{id}/resolve` | 导入与人工确认 |
| POST | `/roster/submit` `/approve` `/reject` `/unlock` | 名单状态机动作 |
| POST | `/certificates/generate` | 批量生成（幂等键）；GET `/certificates?...` 列表；POST `/certificates/{id}/revoke|reissue` |
| GET | `/me/certificates` | 我的证书（预签名 PDF） |
| GET | `/verify/{qr_token}` | 公开验证（Nginx 独立限流路径；脱敏最小字段 + 有效性） |

### 通知 / 统计 / 审计 / 系统

`/notices` CRUD+publish；`/me/notifications` + `/read`；`/stats/dashboard`（P0 计数）与 `/stats/registrations?dim=group|org`（P1 图表）；`/audit-logs?actor=&resource=&date=`（`audit:read`）；`/roles` `/permissions`（`system:manage_roles`）。

## 3. 关键接口请求示例

报名提交（团队）：

```jsonc
POST /api/v1/editions/12/registrations   // Idempotency-Key: uuid
{
  "group_id": 3,
  "enrollment_kind": "team",
  "team_id": 88,
  "coach_user_id": 45,
  "contact": { "name": "李四", "phone": "138...", "email": "..." },
  "form_data": { "project_title": "…" },
  "consents": { "id_number_usage": true },
  "submit": true
}
→ 201 { "id": 900, "batch_no": "REG-12-3F9A21C7", "status": "pending_review" }
```

非法迁移返回：`409 40902 {message: "当前状态 submitted 不允许动作 approve（需 org_approved）"}`。
