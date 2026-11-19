# 06 API 规范与端点草案

**版本**：v1.6（2026-11-17）。基址 `/api/v1`，格式 JSON，认证 `Authorization: Bearer <access_token>`。

v1.1 变更：错误码表补 42205-42208 与 40904、新增发码与公示接口、报名筛选加 `event` 参数、明确成员字段分级。

> 本文是接口设计约定与端点草案。实现后用 drf-spectacular 导出 OpenAPI；差异需确认是实现缺陷还是契约变更，再同步代码、本文与生成结果，不能以生成结果自动覆盖需求。

---

## 1. 通用约定

首批并行开发的字段、JSON运行时校验、版本与AI回传schema见 [12-开发联调契约](12-development-contract.md)。该契约具体化本文，不扩大权限或首期范围。40001用于非法JSON、未知字段及结构校验失败（HTTP400），响应可附安全的errors字段；不能将类型断言视为运行时校验。

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
| 400xx | 结构校验 | 40001 非法JSON、未知字段、类型/枚举/范围或结构不符；不回显敏感原值 |
| 401xx | 认证 | 40101 token 过期、40102 验证码错误或已失效、40104 邮箱未验证（仅邮箱相关操作）、40105 登录凭证无效 |
| 403xx | 权限 | 40301 作用域内无权限、40302 角色冲突、40303 不得自审、40304 须先修改初始/重置密码 |
| 404xx | 资源 | 40401 不存在或无权查看（合并防枚举）；公示名单未发布也返回本码，不返回 403（02 §4.7） |
| 409xx | 冲突/状态 | 40901 重复报名、40902 非法状态迁移、40903 名单已锁定、40904 所选证件已有当前绑定、40905 幂等键与请求不一致、40906 提交/队伍版本已过期、40907 单位标识或队号×赛项身份冲突、40908 队员已有当前队伍（须先退队）、40909 同赛季同赛项已绑定其他队伍（须平台特批）、40910 队伍未获对应赛季注册许可、40911 非当前赛季或当前赛季未开放 |
| 422xx | 校验 | 42201 赛项人数不符、42202 材料缺失、42203 时间窗外、42204 年级或年龄不符、42205 所选学段与组别不符、42206 证件类型/签发国/号码格式错误、42207 赛项与组别组合未开放、42208 缺少指导教师、42209 不支持的语言或主题、42210 照片格式/内容无效、42211 队伍未通过资料审核、42212 不在本届队伍准入名单、42213 单位未通过创建审核 |
| 429xx | 限流 | 42901 请求过频（含验证码频率限制；返回 Retry-After） |

错误码三处同步（07「文档即代码」）：本表 ↔ `core/constants.py` ↔ 前端 `utils/errors.ts` 文案映射。新增校验分支必须先在此登记，代码里出现未登记的码视为缺陷。v1.1 起 `42204` 由「对象/年级限制」改为「年级或年龄限制」——原 `target_audience`（参赛对象多选）随组别收敛为学段而删除。

照片上传超过 5MB 返回 HTTP 413 / 41301，解码后像素超限或伪造图片返回 422 / 42210。照片读取和偏好响应使用 Cache-Control: no-store。

验证码受理存储不可用返回 HTTP 503 / 50301；SMTP 失败只影响任务重试，不向匿名请求区分账号存在性。Cookie 与 token 生命周期见 05 §3.1。历史 40103 不再用于限流，未实现前统一为 42901。

### 1.3 其他

- 首期接口交付以 [01](01-PRD.md) 和 [07](07-task-breakdown.md) 为准：队伍基础/赛季许可/团队报名和固定模板学生/队伍/成员导入前移；证书、复杂跨队特批及两级审核端点为后续草案，首期不注册可执行路由。不提供自助注销接口。首期年龄限制字段只读预留为NULL，配置拒绝启用、报名不执行年龄判定；42204保留年级及未来年龄语义，当前不返回年龄失败分支。在读证明复用已授权的材料上传/查看接口，AI不可读取原件。

- 认证与授权遵循 [02 §5](02-permission-matrix.md#5-前后端落地约定)：前端检查路由和操作权限，后端对每次受保护请求独立鉴权；AI 工具适用同一接口与对象权限，不设置绕过授权的内部 AI 接口。工具名、对象 ID 和用户确认均不能代替授权；公开接口仍按显式可见范围返回最小字段。

- 语言使用 Accept-Language，支持 zh-CN / en-US（接受 zh/en 简写），未支持时回退 zh-CN；message 与字段校验提示随请求语言变化，code/status/字段名保持稳定。错误可附 params 供前端按 code 翻译，未知 code 使用本地通用提示与 request_id；语言切换不改变错误码。

- 筛选：`?status=&group_id=&org_id=&search=&ordering=-created_at`；时间范围 `?created_after=&created_before=`（ISO8601 UTC）。
- 报名提交、证书批量生成必填 `Idempotency-Key`，按用户+路由隔离并绑定请求体摘要；同键同体返回原结果，同键异体返回 40905，缓存至少 24 小时；超期由数据库唯一约束兜底。
- 软删除资源默认不返回；`?include_deleted=1` 仅管理端权限可用。
- 门户接口使用 `/public/*` 前缀及 serializer 白名单；公示仍按档位校验登录。公开验证页统一为站点根 `/verify/{qr_token}`，不再另设 /public/certificates/verify 别名。

## 2. 端点目录

### accounts / me

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | /auth/register | 自助邮箱验证码注册 | 公开 |
| POST | /auth/verify-code/send | 合法请求统一 202；DB/outbox 同事务受理，限流 429 | 公开 |
| POST | /auth/login | login_type=email 或 document；后者含 document_type/country/number/password，错误统一 40105 | 公开 |
| POST | /auth/refresh / /auth/logout | Cookie 轮转/清理，版本与 CSRF 校验 | 会话 |
| POST | /auth/password/change | 临时密码登录后强制改密，更新 token_version 并换发会话 | 本人（含受限会话） |
| POST | /auth/password/reset | 已验证邮箱验证码 + 新密码；受理不枚举账户 | 公开，验证凭据 |
| GET | /me | user/profile/grants/locale/theme，证件仅类型/签发国/末四位 | 登录 |
| PATCH | /me/preferences | locale/theme 部分更新 | 本人 |
| PATCH | /me/profile | 普通资料更新，已绑定证件字段不能直接修改 | 本人 |
| POST | /me/document | 仅首次绑定（当前未绑定），类型/签发国/号码二选一证件 | 本人 |
| PUT/DELETE | /me/photo | 本人照片上传/替换/删除 | 本人 |
| GET | /me/photo / /profiles/{id}/photo | 5 分钟签名，照片权限不因队友关系开放 | 本人 / profile:read + 范围 |

验证码响应统一「如符合条件，验证码将发送，请检查收件箱」，不返回账户/投递状态；所有地址都经同一受理流程，任务端判断是否发送。邮箱找回仅适用于已验证邮箱，无邮箱代建账户走管理员核验重置。初始/重置密码只交付一次，重试创建请求不能返回原密码；遗失时走受控重置。

### 代建与证件更正

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | /orgs/{id}/student-accounts | 必须有效单位、有效身份证或护照、学生/监护授权；邮箱可空；服务器生成 username/随机临时密码，必须首次改密 | user:provision + 单位范围 |
| POST | /users/{id}/reset-student-password | 核验凭据+理由+primary_membership_id+affiliation_version；当前有效主属单位普通学生，无创建来源/邮箱限制；管理账户由平台处理 | user:reset_student_password |
| GET/POST | /identity-change-requests；GET/PATCH /identity-change-requests/{id} | 本人/单位代提；服务器冻结 base_identity_version、旧绑定及新证件密文，只有草稿能编辑 | profile:request_identity_change + 范围 |
| POST | /identity-change-requests/{id}/submit / /cancel-and-edit | 未审可取消：保留 withdrawn 原申请，原子复制关联草稿；已审不能此路撤销 | 原申请人 |
| POST | /identity-change-requests/{id}/review | 所属单位管理员或平台管理员审核（单位仅限本范围普通成员），禁止申请人/证件本人自审；approve 原子切换并释放旧号，冲突 40904/40906 | profile:review_identity_change + 范围 |

登录示例：{ "login_type":"document", "document_type":"passport", "document_country":"US", "document_number":"…", "password":"…" }。护照号码含前导零时保留。所有密码/证件/验证码仅请求体传输并禁止日志；代建/重置响应 Cache-Control: no-store，已有证件不得静默接管账号或覆盖密码。

### 用户与人员（管理）

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET/POST | `/users`；GET/PATCH/POST(disable) `/users/{id}` | 账号管理；不增加离职档案 | `user:*` |
| GET | `/users/{id}/roles` POST/DELETE 同 | 角色授予/撤销（body: role, scope_type, scope_id）；单位管理员交接由平台执行并使旧权限缓存失效，记录审计 | `user:assign_role` |
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

未审单位/队伍申请另提供 POST /{request-resource}/{id}/cancel-and-edit：锁申请，确认无审核决定，原记录置 withdrawn 并复制关联 draft 返回新 ID；审批先提交则取消返回 40906，不覆盖已审核申请。

### 学生单位交接（P0）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | /org-transfer-requests | 本人/获授权管理员发起：目标单位、来源主属关系、base_affiliation_version、本人/监护授权引用和理由；各方只能读所属范围 |
| POST | /org-transfer-requests/{id}/release | 原单位核验转出，org:release_transfer，禁止自审；通过后仍保留原归属 |
| POST | /org-transfer-requests/{id}/accept | 目标单位接收，org:accept_transfer；锁学生及版本，无当前队伍才原子切换主属关系/权限，不继承历史管理角色 |
| POST | /org-transfer-requests/{id}/reject / /cancel | 驳回或未完成时取消，保留申请和已发生处理记录 |
| POST | /org-transfer-requests/{id}/mediate-release | 平台核验代办转出，org:mediate_transfer，核验凭据及理由必填；仍等待新单位接收 |
| GET | /public/support | 运营配置的联系邮箱；无归属且无法自助找回时展示联系入口，不返回用户存在性或直接重置 |

### 队伍（首期基础能力，复杂跨队特批后续）

教练列表及详情仅返回有效所属单位的队伍概要，不包含其他单位或其子单位队伍；成员详情和报名仅本人负责队伍可按权限读取；不授予队伍提案的编辑或审核权。单位管理员统一管理本单位范围内全部队伍，创建/资料/成员变更仅单位管理员或平台发起申请。本人可自主退队，管理员发起的普通入退队仍走审核；回到上次退出队伍可普通入队审核，跨队需检查所有未归档赛季同赛项绑定，受限时必须平台特批。新队提交/批准复查唯一归属及绑定，分别返回 40908/40909。

正式队伍只读接口为 GET /teams、/teams/{id}、/teams/{id}/members；GET /teams/{id}/registrations 返回权限内历史摘要。创建/编辑/改成员统一发起申请，不能 PATCH 正式资料立即生效。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/team-change-requests`；GET/PATCH `/team-change-requests/{id}` | 申请人查看本人提案，创建队列仅 team:review_create；修改队列用 team:review；kind=create/update，创建必填 registration_season_id，修改须带 base_revision_id 和 base_membership_version；team:create/update/manage_members 与单位范围校验，仅单位管理员或平台；教练无写权限 |
| POST | `/team-change-requests/{id}/submit|withdraw|resubmit` | 申请人操作；resubmit 复制被驳回/退回提案为新草稿，以 resubmission_of 关联原记录并返回新 ID，保持旧提案与审核记录 |
| POST | `/team-change-requests/{id}/review` | approve/reject/return + comment；创建仅 team:review_create（平台）；修改用 team:review，单位树内或平台代审，禁止自审，旧版本冲突 40906 |
| GET | `/team-change-requests/{id}/review-context` | 申请提案、与生效版本的差异及分页历史摘要；创建仅 team:review_create，修改 team:review + 单位范围，不扩展赛事附件权限 |

### 自主退队与特批换队（里程碑 2）

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | `/me/team-membership/leave` | body: membership_id、reason；结束本人当前关系、保留最近退队和全部历史；不解除赛季绑定，不改报名快照 | team:leave_own |
| GET | `/me/team-eligibility?team_id=` | 是否已有当前队伍、最近退出队伍、全部有效赛季绑定与是否需特批；不泄露其他学生资料 | 本人 |
| GET/POST/PATCH | `/team-transfer-requests` / `/{id}` | 本人查看/提交目标队伍、来源归属版本、涉及赛季和理由；只可编辑草稿，不接受客户端指定审批状态 | team:request_transfer |
| POST | `/team-transfer-requests/{id}/submit` / `/cancel-and-edit` | 未审可取消并保留原记录；不能直接申请即生效 | 原申请人 |
| POST | `/team-transfer-requests/{id}/review` | approve/reject + comment、base_version；平台批准并执行入队/绑定切换，禁止自审，校验全部关联报名和锁定态；多有效赛季按季关联申请一并批准，已归档绑定不改；旧快照保留 | team:review_transfer，仅平台 |

### 赛季 / 赛事 / 场次 / 赛项 / 组别

GET /seasons/current 返回当前赛季；POST /seasons/{id}/set-current 仅 season:set_current（平台），目标须 active，无当前则返回未开放状态。GET /public/competitions 只列当前赛季公开赛事，普通 season_id/season=all 参数拒绝，不修改全局当前值。管理历史接口独立按范围接收 season_id。POST/PATCH /seasons 与 activate/archive 仅平台权限；已有提交的场次不可改挂赛季，归档须无未完成赛事和待审报名。切换不复制队伍许可、不迁移历史或自动归档旧赛季。

已接入的赛季管理接口：`GET /seasons?page=&page_size=` 仅平台分页查看全部状态；`POST /seasons` 接收 `code`（1–32 位大写英文字母、数字或连字符，首位须字母或数字）、`name`（1–64 字符）、`start_date` 和 `end_date`（ISO 日期，起日不晚于止日），返回 201 草稿。`POST /seasons/{id}/activate` 和 `POST /seasons/{id}/set-current` 接受空对象，均返回 `id/code/name/start_date/end_date/status/is_default`；激活不自动选为当前，重复设置同一当前赛季无额外副作用。编辑及安全归档待接入。

GET/POST /team-season-registrations、GET /{id}、POST /{id}/submit|cancel|resubmit：team:request_season_registration + 本单位范围；resubmit 复制关联新申请。POST /{id}/review（approve/reject）与 /revoke 仅 team:review_season_registration（平台，非自审，理由必填）；首次创建审核原子创建队伍及许可。提交/重提校验当前 active 赛季，审批通过校验原报名赛季 active 和对应许可，均不以赛事 allowlist 替代许可。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/competitions?page=&page_size=` | 管理目录：平台读取全部未删除赛事；拥有赛事作用域 `competition:read` 的账号只读该赛事，届次、单位和个人授权不向上扩大。 |
| POST | `/competitions` | 仅平台 `competition:create`。字段 `name`（1–128 字符）、`summary`（可空字符串，最多 2000 字符）；201 返回 `id/public_code/name/summary/status`，服务端生成编号并固定 `draft`，不建届次、不授权、不发布。 |
| GET/PATCH | `/competitions/{id}` | `competition:*`（详情及编辑待接入） |
| POST | `/competitions/{id}/publish` `/archive` | 状态动作 |
| PUT | `/competitions/{id}/units` | 主办/承办/协办设置（`competition:manage_units`） |
| GET/POST | `/competitions/{id}/admins`；DELETE `/admins/{user_id}` | `competition:manage_admins` + user:assign_role；仅平台，查询以外操作不得由赛事管理员直接授权 |
| GET | `/competitions/{id}/editions?page=&page_size=` | 平台与具备 `edition:read` 的赛事级账号可分页查看该赛事全部届次；届次授权只返回其直接获授的届次。无可授权范围时 404。 |
| POST | `/competitions/{id}/editions` | 平台或具有该赛事作用域 `edition:create` 的账号创建草稿；届次授权不能创建其他届次。 |
| GET | `/competitions/{id}/edition-seasons?page=&page_size=` | 同创建权限；返回可选赛季，平台可选 active/draft，受委派的赛事管理员仅可选 active。 |
| GET/PATCH | `/editions/{id}` | `edition:*`（详情及编辑待接入） |
| POST | `/editions/{id}/publish` `/close`；PUT `/editions/{id}/approval-mode` | 状态与审核模式配置 |
| GET/POST | `/editions/{id}/events`；PATCH/DELETE `/events/{id}`；POST `/events/{id}/enable|disable` | 赛项（`event:*`，v1.1） |
| GET/POST | `/editions/{id}/groups`；PATCH/DELETE `/groups/{id}`；POST `/groups/{id}/enable|disable` | 组别（`group:*`） |
| GET/POST | `/editions/{id}/offerings`；PATCH/DELETE `/offerings/{id}` | 开放组合（v1.1）。已有报名的组合不可删除，服务层按 offering_id 的 RESTRICT 返回冲突，只能停用 |
| GET/PUT | `/editions/{id}/team-access` | 查看/设置 team_entry_mode 与 team_access_version；写入须带当前版本，权限 edition:manage_team_access（里程碑 2） |
| GET/POST | `/editions/{id}/team-allowlist`；DELETE `/editions/{id}/team-allowlist/{team_id}` | 名单查询/增补/撤销（标 revoked）；edition:manage_team_access，不公开全量 |
| POST | `/editions/{id}/team-allowlist/import-preview` / `/import-confirm` | 按队号+稳定赛项代码预览匹配与错误，返回预览令牌及 team_access_version；确认校验版本并事务写入，只导入已明确匹配的队伍，不自动创建队伍；权限同上 |
| GET | `/editions/{id}/available-offerings?team_id=` | 按赛项/开放组合返回可选学段组别，用户选择；不按全队最高学段自动筛选，提交仍须校验组别已配置条件 |
| GET | `/public/competitions` `/public/editions/{id}` | 门户公开列表/详情 |
| GET | `/public/editions/{id}/roster?event=&group=` | 通过名单公示页（`AllowAny`；判定顺序见 02 §4.7） |
| POST | `/editions/{id}/roster/publish` `/unpublish` | 发布/下架公示名单（发布用 `roster:publish`，下架用 `roster:unpublish`，v1.1） |
| PATCH | `/editions/{id}/roster-publication` | 设置公示档位与字段白名单（`roster:publish`） |

创建届次接受 `season_id`、`year`（1–9999）、`edition_no`（1–9999）、`name`、`venue` 及 `enroll_start`、`enroll_end`、`start_date`、`end_date`。四项时间要么均携带 UTC 偏移，要么均使用无偏移的本地时间并显式提交 `time_zone: "Asia/Shanghai"`，后端拒绝历史时区切换时不存在或有歧义的时间。报名开始 < 报名结束 ≤ 比赛开始 < 比赛结束；赛事或赛季已归档时拒绝。返回 201 和私有草稿，默认单级审核、不创建开放组合、不发布。

### 报名与审核

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET/POST | `/editions/{edition_id}/registrations` | 我的报名列表 / 新建（draft 或直接 submit） | `registration:create` |
| GET | `/registrations/{id}` | 详情（成员、文件、审核记录）；成员字段按查看者身份分级，见下方说明 | read_own / read scoped |
| PATCH | `/registrations/{id}` | 编辑工作副本（draft / returned / org_returned / rejected / org_rejected），不覆盖已提交版本 | 提交人 |
| POST | `/registrations/{id}/submit` `/resubmit` `/withdraw` `/cancel-review` | 状态动作（03 §1）；cancel-review 仅本轮未审，保留并标记取消旧提交，回同一报名的可编辑草稿 | 提交人 |
| DELETE | `/registrations/{id}` | 软删除草稿，不删除已有提交/成员/材料历史 | `delete_draft` |
| POST | `/registrations/{id}/files` | 上传暂存材料（multipart → upload_id），归属/过期校验后在 submit/resubmit 建本轮文件引用 | 提交人 |
| GET | `/registrations?edition=&group=&org=&status=` | 管理列表 | `registration:read` |
| POST | `/registrations/{id}/approval` | body: `{action: approve|reject|return, comment, submission_no}`；已 approved 执行 reject 额外需 approval:reject_approved，并受名单锁定/证书限制；所有审核动作禁止本轮学生成员及提交人自审 | `approval:review_*` |
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
| GET/POST | `/editions/{id}/awards`；PATCH/DELETE `/awards/{id}` | `award:config`，仅学生参赛奖项，不提供单位/组织/教练获奖通道 |
| GET | `/editions/{id}/rosters?offering_id=`；PUT 条目增删 `/roster/records` | 按开放组合查询；不传 offering_id 时为届次通用名单，条目仅从 approved 报名挑选 |
| POST | `/roster/import`（异步，batch_no 主匹配）→ GET `/roster/import-pending` → POST `/import-pending/{id}/resolve` | 导入与人工确认 |
| POST | `/roster/submit` `/approve` `/reject` `/unlock` | 名单状态机动作 |
| POST | `/certificates/generate` | 批量生成（幂等键）；GET `/certificates?...` 列表；POST `/certificates/{id}/revoke|reissue` |
| GET | `/me/certificates` | 仅 recipient_member_id 对应本人、届次未 closed 且已 issued 的证书，返回短期预签名 PDF；完整证件号不输出 |
| GET | `/verify/{qr_token}` | 公开验证（Nginx 独立限流路径；脱敏最小字段 + 有效性） |

关闭可见性：closed 的门户、公示、read_own/普通队伍历史入口均 404；GET /admin/editions/{id}/registrations 与对应 submissions 历史仅 registration:read_history，仍逐行检查原届次/单位范围。公开证书验证仍仅返回有效性等最小字段，不开放完整历史。

### 通知 / 统计 / 审计 / 系统

`GET /me/notifications?page=&page_size=` 分页列出登录账号收到的报名消息，最新在前。每条包含 `id`、`registration_id`、`submission_no`、`kind`（`submitted` / `approved` / `rejected` / `returned`）、`created_at` 与可空 `read_at`；不返回报名资料或审核意见。`POST /me/notifications/{id}/read` 接受空对象，返回更新后的消息，重复请求保留第一次已读时间；不可见或不存在返回 40401。已关闭届次或已删除报名的消息不展示，查看原报名仍需通过报名接口的权限检查。

规划接口：`/notices` CRUD+publish；`/stats/dashboard`（P0 计数）与 `/stats/registrations?dim=group|org`（P1 图表）；`/audit-logs?actor=&resource=&date=`（`audit:read`）；`/roles` `/permissions`（`system:manage_roles`）。

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
  "selected_school_level": "HS",
  "consents": { "document_usage": true },
  "submit": true
}
→ 201 { "code": 0, "message": "ok", "data": { "id": 900, "batch_no": "REG-12-3F9A21C7", "status": "pending_review" }, "request_id": "..." }
```

非法迁移返回 HTTP 409，包裹内 `code=40902`，例如 `message="这条报名还需单位初审，暂时无法复审。"`；内部状态诊断写入日志。
