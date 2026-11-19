# 首期开发联调契约

版本：2026-11-18。本文将 [06](06-api-spec.md) 的首批开发接口具体化，供前后端并行实现；权限仍以02、状态以03、数据以04为准。接口存在不等于已实现，实际覆盖与验证必须记录在各工程README。首期全部任务范围仍见07，本文不是范围缩减。

## 1. 通用规则与运行时校验

- 基址 `/api/v1`，路径不带尾斜线。公开JSON的ID/版本为1至9007199254740991的安全整数，日期为YYYY-MM-DD，时间为带时区ISO8601，语言 `zh-CN|en-US`，主题 `light|dark|system`。
- 成功响应 `{code:0,message:string,data:T,request_id:string}`；失败为 `{code:number,message:string,data:null,request_id:string,errors?:Record<string,string[]>}`。列表data固定为 `{items:T[],page:integer,page_size:integer,total:integer}`，page从1开始，默认page_size=20，最大100。
- 所有JSON边界做运行时校验：请求体必须是对象；类型/必填/枚举/长度/数值范围/嵌套结构/跨字段约束均检查。拒绝未知可写字段，不能默默接受status、actor、scope或reviewer等客户端伪造字段。前端以unknown接收响应，使用运行时schema校验包裹和data后才进入store/组件，不以TS断言代替校验。
- 非法JSON、未知字段及结构错误返回HTTP400/code40001，并提供安全的字段错误；合法结构但违反业务规则沿用06中的409/422码。无效响应不得展示为成功，前端显示本地通用错误与可用request_id；日志不保存原响应体。
- 更新工作副本须带当前version（若实体使用base_revision_id/base_membership_version/submission_no则按对应字段），冲突返回40906。幂等键缺失/格式无效返回40001，同键异体40905；提交/重提使用Idempotency-Key并绑定actor、动作、对象和规范化参数。
- 无认证40101，登录失败统一40105，无权写入40301，无权查看对象按40401防枚举，自审40303，状态不允许40902。每次查询与写入重新鉴权，不信任前端隐藏或已下发工具列表。
- OpenAPI由后端drf-spectacular导出到 `docs/openapi.json`；前端生成类型，不手写第二份接口类型事实源。运行时schema须与生成类型交叉校验并用真实响应联调。未实现端点不返回模拟成功。

## 2. 认证与当前用户

`POST /auth/login`：邮箱请求 `{login_type:"email",email,password}`；证件请求 `{login_type:"document",document_type:"id_card"|"passport",document_country,document_number,password}`。两种分支严格互斥，密码不出现在URL或日志。

邮箱最长255字符，证件号码最长32字符，密码输入最长256字符；新密码至少12字符并通过后端密码策略，前端长度检查不代替后端策略。

成功data为 `{access:string,expires_in:1800}`，同时设置Refresh Cookie：HttpOnly、生产Secure、SameSite=Strict、Path=/api/v1/auth；access仅前端内存保存。登录后前端GET /me。`GET /auth/csrf` 返回data `{csrf_token:string}`并设置CSRF Cookie，用于刷新/登出的X-CSRFToken；该引导端点不授予业务权限。

`POST /auth/refresh` 请求空对象，使用Refresh Cookie、同源Origin和CSRF校验，轮转Refresh并返回同结构access。`POST /auth/logout` 请求空对象，清理Refresh并撤销当前会话，data=null。无Refresh时不泄露账号信息。不得把refresh token放入JSON、localStorage或模型上下文。

`GET /me` data：

```json
{
  "user":{"id":1,"username":"system-generated","email":null,"must_change_password":false},
  "profile":{"real_name":"示例姓名","person_type":"participant","school_level":"HS","grade":"高一"},
  "grants":[{"role":"participant","scope_type":"global","scope_id":null,"permissions":["registration:create","registration:read_own"]}],
  "locale":"zh-CN",
  "theme":"system"
}
```

profile可为null；邮箱仅本人/me返回，公开接口不返回。grants只由后端生成，global的scope_id必须null，其他scope为正整数；participant的global仍仅限本人，不等于全库权限。

`PATCH /me/preferences`：非空对象，只接受locale/theme，返回保存后的两字段。`POST /auth/password/change`：`{old_password,new_password}`，校验密码策略、原子递增token_version并换发会话；改密前受限会话只能访问/me、改密及登出等必要路径。

### 2.1 邮箱验证码、注册与找回

- `POST /auth/verify-code/send`：严格请求`{email,purpose}`，purpose仅register/reset_password，邮箱最长255字符并去首尾空格、转小写。合法且未超限请求统一HTTP202，data=null，message为“如符合条件，验证码将发送，请检查收件箱”。HTTP受理阶段不查询账号存在性，只原子建立verification_codes及outbox记录；不返回验证码、投递状态、账号状态或邮箱是否存在。默认同邮箱同用途60秒一次、IP每小时20次；超限42901并有Retry-After，受理存储不可用统一50301。
- `POST /auth/register`：严格请求`{email,password,verification_code,real_name}`，verification_code为6位ASCII数字字符串（保留前导零），real_name去首尾空格后1–64字符；密码12–256字符并通过既有Django策略。成功HTTP201，data=`{id,status:"active"}`；创建已验证邮箱账号、最小participant档案及本人基础grants，不接收角色、作用域或单位ID，不自动赋予管理权或归属。注册后显式登录，不能借注册覆盖已有账号。
- `POST /auth/password/reset`：严格请求`{email,verification_code,new_password}`，密码策略同上。验证码错误、过期、超次、用途不符或已消费均HTTP401/code40102，不返回账号是否存在；有效核验成功统一HTTP202/data=null。对匹配的已验证有效账号原子改密、递增token_version并清除must_change_password，不自动登录，不重置管理角色或单位归属。
- 验证码默认10分钟有效、最多5次失败、只消费一次；行锁使并发注册/重置只有一次成功。失败计数必须在返回错误后仍持久化，不能因抛异常而回滚。重发使同邮箱同用途旧码失效，注册码不可用于重置，已封禁或删除账号不能通过找回恢复启用。
- 仅保存验证码hash，供发送重试的明文只以Fernet密文短期保留。outbox payload仅含verification_code_id及locale，不包含验证码、密码或邮箱；发送任务读取记录后判断是否应发送，注册仅向未被占用邮箱发送，找回仅向已验证且有效账号发送；所有条件在异步侧判断，不改变HTTP受理语义。送达、过期、不符合发送条件或消费后清除投递密文。
- 邮件投递器只处理 `auth.verification` 和 `registration.notice_mail`，使用可过期租约、有限指数退避和稳定 Message-ID。邮件被 backend 接受后终结；无资格/失效请求正常跳过，队列同样标记 `dispatched` 表示已处理、日志区分 `skipped`，不等于送达。失败保留 pending 以便重试，耗尽后 failed 并记录脱敏告警；不承诺恰好一次。
- 报名变更、站内消息及符合条件的邮件任务同事务写入。邮件只向活跃提交人的已验证邮箱发送，载荷仅含消息 ID 与入队时的 locale；投递前重新校验账号、邮箱验证时间及消息可见性。邮箱已撤销验证、入队后重新验证、报名删除或届次关闭时跳过；正文只引导登录消息中心，不含报名资料、审核意见或登录凭据。不回填旧消息或补发旧报名占位事件。
- 邮件采用已配置SMTP，开发/测试可使用仅进程内locmem backend，不提供读取验证码/邮箱内容的公开调试端点，不打印验证码、正文或收件地址。真实发信配置及SPF/DKIM仍需单独验收；前端只显示已受理，不能显示邮件已送达。

## 3. 公开赛事与作用域内基础查询

- `GET /seasons/current`：data为 `{id,name,start_date,end_date,status}` 或null；无当前赛季不允许新报名。
- `GET /public/competitions`：分页Competition；对象字段 `{id,public_code,name,summary,status,editions:Edition[]}`，只含当前赛季已发布内容。
- `GET /public/editions/{id}`：Edition `{id,competition_id,season_id,name,status,approval_mode:"single",enroll_start,enroll_end,start_date,end_date,venue,offerings:Offering[]}`。不得暴露草稿、关闭历史或内部材料。
- Offering `{id,event_id,event_code,event_name,group_id,group_name,school_level,enrollment_type,min_members,max_members,require_coach,required_materials:string[],is_enabled}`；school_level可为null，enrollment_type=`individual|team|both`，人数为非负整数且min≤max。首期年龄字段不参与判定。
- `GET /orgs`：作用域内分页 `{id,name,path,status}`；`GET /orgs/{id}/members`：作用域内分页 `{id,user_id,real_name,person_type,school_level,grade}`。不可作为普通用户枚举全库学生的接口。
- `GET /teams`：当前权限内分页Team；普通队员只通过本人归属获取本队，教练仅本单位概要、负责队伍的允许详情，单位管理员按单位树。
- Team `{id,team_code,event_code,name,org_id,coach_id,captain_id,approved_revision_id,membership_version,status,members:Member[],season_registrations:SeasonRegistration[]}`。成员白名单 `{user_id,real_name,role,school_level,grade}`，不含证件/联系方式；概览可省略members，详情需重新鉴权。

## 4. 队伍审核与赛季许可

`POST /team-change-requests` 严格请求：

```json
{
  "request_kind":"create",
  "org_id":1,
  "team_code":"1024A",
  "event_code":"V5RC",
  "registration_season_id":1,
  "proposal":{"name":"示例队伍","coach_id":2,"captain_id":3,"members":[{"user_id":3,"role":"captain"}]}
}
```

update分支必须提供team_id/base_revision_id/base_membership_version，不允许变更所属单位或稳定赛项；create分支不可伪造team_id或base_revision_id。成员不能重复，队长必须在成员中，成员/教练归属及身份由后端验证；存储提案加密。返回Request `{id,request_kind,team_id,org_id,status,submitted_by,base_revision_id,base_membership_version,registration_season_id,proposal,comment}`，可空字段明确输出null。

`GET /team-change-requests`：申请人自己的提案或当前审核权限队列，分页；`GET /team-change-requests/{id}`同等范围；`POST /{id}/submit`空对象；`POST /{id}/review`请求 `{action:"approve"|"reject"|"return",comment:string}`，拒绝/退回理由必填。创建仅平台非自审，通过时原子建队及对应赛季许可；修改由另一名有权单位管理员或平台审核，版本过期40906，正式资料仅通过后更新。

`GET/POST /team-season-registrations`：创建请求 `{team_id,season_id}`，返回SeasonRegistration `{id,team_id,season_id,status,submitted_by,reviewer_id,comment}`。`POST /{id}/submit`空对象，`POST /{id}/review`请求 `{action:"approve"|"reject",comment}`，平台非自审，所有版本/当前赛季/唯一许可约束遵循03/04。

## 5. 报名草稿、提交与审核

`POST /editions/{id}/registrations`创建草稿，body：

```json
{
  "offering_id":1,
  "enrollment_kind":"team",
  "team_id":1,
  "coach_user_id":2,
  "selected_school_level":"HS",
  "contact":{"name":"联系人","phone":"示例联系电话","email":null},
  "form_data":{"project_title":"示例作品"},
  "consents":{"document_usage":true},
  "submit":false
}
```

individual分支不可提供team_id，由认证actor确定individual_user_id；team分支仅本人/队长或负责教练可按原权限代报。contact/name/phone上限64/20、email为有效邮箱或null；project_title上限200。所有申请人、单位、状态、成员快照与轮次由后端决定。`submit:true`同时进行同一事务的提交并要求幂等键。

Registration固定字段 `{id,batch_no,edition_id,offering_id,enrollment_kind,team_id,individual_user_id,org_id,submitted_by,status,current_submission_no,approved_submission_no,version,selected_school_level,coach_user_id,contact,form_data,consents,members,files,approval_records,can_edit}`。无权读取的敏感字段不返回；前端schema要允许权限投影省略contact/form_data/consents，而不能要求服务端为通过校验泄露字段。版本和身份字段只读。非编辑者不读取未提交草稿；已有轮次的审核投影从冻结快照读取offering/coach/学段等提交字段，不混入后续草稿。

- `GET /editions/{id}/registrations`：本人/负责队伍列表；`GET /registrations`：有权管理队列，支持edition/status/org筛选。分页且查询侧限域。
- `GET/PATCH /registrations/{id}`：PATCH只接受草稿字段及version；submitted/approved不可修改，返回40902。GET非编辑者返回当前提交的权限投影，不能返回工作副本敏感字段。
- `POST /registrations/{id}/submit|resubmit`：`{version}`＋幂等键。校验窗口、当前active赛季、队伍版本/许可、人数/教练/材料、组别，新增不可变轮次及成员/材料快照。
- `POST /registrations/{id}/cancel-review|withdraw`：`{version}`。cancel-review仅当前轮无审核决定，保留取消轮次再回草稿；withdraw遵循时间窗，均不删除历史。
- `POST /registrations/{id}/approval`：`{action:"approve"|"reject"|"return",comment,submission_no}`，与取消串行，禁止提交人及本轮学生成员自审；过期轮次40906。审核员必须同时有对象读取及相应审批权限；approved后驳回额外校验reject_approved和锁定规则。
- `GET /registrations/{id}/submissions` 与 `/registrations/{id}/submissions/{no}`：分页轮次/单轮摘要，返回原组合、赛项/组别名、声明学段、时间及冻结成员白名单，不返回其他表单字段；`GET /registrations/{id}/approval-records`：分页 `{id,submission_no,action,comment,reviewer_id,created_at}`，action包括approve/reject/return及留痕用withdraw/cancel_review，后两者不因此获得审批权。
- `POST /registrations/{id}/files`：multipart字段file/material_type；只允许原业务材料上传。暂存upload_id归属、大小、白名单、过期及恶意文件校验通过后才能在提交时建立引用，不接受任意storage_key或URL。

## 6. AI回传JSON与动作隔离

模型输出必须先通过服务端严格schema，禁止仅JSON.parse后执行；拒绝未知字段、重复键、非有限数、过深或超大JSON。首批结构为：

```json
{"kind":"answer","text":"经过授权与脱敏的回答"}
```

或

```json
{"kind":"tool_proposal","tool":"registration.open","arguments":{"registration_id":1}}
```

或

```json
{"kind":"tool_proposal","tool":"registration.update_draft","arguments":{"registration_id":1,"version":1,"fields":{"selected_school_level":"HS"}}}
```

kind为判别字段；answer文本1–4000字符；arguments按每个工具独立schema，字段枚举/ID/长度严格校验，不允许任意route、URL、SQL、脚本或字段patch。工具schema不能包含用户token、actor或数据库凭据。新增工具先定义schema和授权映射，再开放，不能使用任意字符串透传工具。

schema通过仅表示结构有效，之后仍逐次校验工具白名单∩当前用户权限∩对象范围∩业务状态；用户确认不能代替鉴权。前端只接收后端校验后的动作回执并再次做运行时校验，模型原始输出不得直接控制组件。首批实际模型调用保持关闭，开发可对纯校验器和权限检查使用合成输入；供应商/预算未定不开放真实模型端点。

## 7. 并行开发和验收

- 后端负责backend/及生成OpenAPI；前端负责frontend/正式工程，保留prototype/不迁移模拟权限；集成负责人维护本契约及根目录CI/部署，不交叉覆盖。
- 必验：前后端运行时schema拒绝错误结构；认证/撤权；单位与届次越权；禁止自审；提交与取消/审核版本竞争；幂等同键异体；冻结快照；AI非法JSON/未知工具/参数注入不执行。用真实HTTP响应联调，不只依赖mock。
- 不把SQLite或浏览器桩测试称为PostgreSQL16并发验证；尚未实现的首期任务继续保留未完成状态，不以脚手架、种子数据或静态演示代替真实交付。
