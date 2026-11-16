# 06 API 规范与端点草案

**版本**：v1.0（2026-11-16）。基址 `/api/v1`，格式 JSON，认证 `Authorization: Bearer <access_token>`。

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
| 401xx | 认证 | 40101 token 过期、40102 验证码错误 |
| 403xx | 权限 | 40301 作用域内无权限、40302 角色冲突 |
| 404xx | 资源 | 40401 不存在或无权查看（合并防枚举） |
| 409xx | 冲突/状态 | 40901 重复报名、40902 非法状态迁移、40903 名单已锁定 |
| 422xx | 校验 | 42201 组别人数不符、42202 材料缺失、42203 时间窗外、42204 对象/年级限制 |
| 429xx | 限流 | 42901 请求过频 |

### 1.3 其他

- 筛选：`?status=&group_id=&org_id=&search=&ordering=-created_at`；时间范围 `?created_after=&created_before=`（ISO8601 UTC）。
- 写接口支持 `Idempotency-Key` 头（报名提交、证书批量生成必填）。
- 软删除资源默认不返回；`?include_deleted=1` 仅管理端权限可用。
- 公开接口（无需登录）：`/public/*` 前缀 + serializer 白名单（02 文档 §4.5）。

## 2. 端点目录

### accounts / me

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | `/auth/register` | 注册（phone/email + code） | 公开 |
| POST | `/auth/login` / `/auth/refresh` / `/auth/logout` | JWT | 公开/登录 |
| POST | `/auth/password/reset/*` | 发码/重置 | 公开 |
| GET | `/me` | 当前用户 + profile + grants | 登录 |
| PATCH | `/me/profile` | 完善/修改本人档案 | 登录 |

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

### 赛事 / 届次 / 组别

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/competitions`；GET/PATCH `/competitions/{id}` | `competition:*` |
| POST | `/competitions/{id}/publish` `/archive` | 状态动作 |
| PUT | `/competitions/{id}/units` | 主办/承办/协办设置（`competition:manage_units`） |
| GET/POST | `/competitions/{id}/admins`；DELETE `/admins/{user_id}` | `competition:manage_admins` |
| GET/POST | `/competitions/{id}/editions`；GET/PATCH `/editions/{id}` | `edition:*` |
| POST | `/editions/{id}/publish` `/close`；PUT `/editions/{id}/approval-mode` | 状态与审核模式配置 |
| GET/POST | `/editions/{id}/groups`；PATCH/DELETE `/groups/{id}`；POST `/groups/{id}/enable|disable` | `group:*` |
| GET | `/public/competitions` `/public/editions/{id}` | 门户公开列表/详情 |

### 报名与审核

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET/POST | `/editions/{edition_id}/registrations` | 我的报名列表 / 新建（draft 或直接 submit） | `registration:create` |
| GET | `/registrations/{id}` | 详情（含成员快照、文件、审核记录） | read_own / read scoped |
| PATCH | `/registrations/{id}` | 编辑（仅 draft / returned） | 提交人 |
| POST | `/registrations/{id}/submit` `/resubmit` `/withdraw` | 状态动作（03 §1） | 提交人 |
| DELETE | `/registrations/{id}` | 删除草稿 | `delete_draft` |
| POST | `/registrations/{id}/files` | 上传材料（multipart → storage_key） | 提交人 |
| GET | `/registrations?edition=&group=&org=&status=` | 管理列表 | `registration:read` |
| POST | `/registrations/{id}/approval` | body: `{action: approve|reject|return, comment}` | `approval:review_*` |
| POST | `/registrations/batch-approval` | body: `{ids[], action, comment}` | `approval:batch_review` |
| GET | `/registrations/{id}/approval-records` | 审核历史 | `approval:read_records` |
| POST | `/registrations/export` | 异步导出（审计含字段清单） | `registration:export` |

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
