# 03 状态机设计

**版本**：v1.6（2026-11-17）。所有状态迁移必须由服务层 `transition(obj, action, actor)` 统一校验，禁止直接 update 状态字段。状态值即数据库 `status` 列的取值，命名 snake_case。

v1.1 变更：报名提交前置条件加入赛项/组合/学段校验；§4 拆为赛项与组别两套并补组合级停用；§5 名单单位改为「届次×赛项×组别」；新增 §6.1 作废证书验证页语义、§9 名单公示。

---

## 1. 报名状态机（核心）

审核模式在届次配置为 single/two_stage，每次提交时冻结到 registration_submissions.approval_mode；本轮待审期间不受届次配置变化影响，重新提交才采用当时配置。submit/resubmit 的目标态按新轮次冻结的模式决定（single → pending_review，two_stage → submitted），下表按该模式阅读。两种模式共用一张状态表，`two_stage` 仅多经过初审态。里程碑 1 只启用 `single`，但状态枚举与迁移表一次定死，避免以后改数据字典。

### 1.1 状态枚举

| 状态 | 含义 | 适用模式 |
| --- | --- | --- |
| `draft` | 草稿，未提交 | 通用 |
| `submitted` | 已提交，等待初审 | two_stage |
| `org_approved` | 单位初审通过，等待赛事复审 | two_stage |
| `org_returned` | 初审退回修改 | two_stage |
| `org_rejected` | 初审本轮不通过，可修改重提 | two_stage |
| `pending_review` | 待赛事审核 | single |
| `returned` | 退回修改，可重提 | single（two_stage 的复审退回直接进 `returned` 重走初审） |
| `rejected` | 本轮不通过，可修改重提 | 通用 |
| `approved` | 审核通过 | 通用 |
| `withdrawn` | 参赛者撤回 | 通用（仅未通过前） |

### 1.2 迁移表（single 模式）

| 当前态 | 动作 | 目标态 | 执行角色 | 前置条件 |
| --- | --- | --- | --- | --- |
| `draft` | submit | `pending_review` | 提交人（本人/队长/代报教练） | 时间窗内、组合开放；团队报名校验单位/队伍已审核及当前准入模式、学段及材料全过；创建不可变提交版本 |
| `draft` | delete | （软删） | 提交人 | 保留已有提交历史；清理任务仅处理从未提交的草稿 |
| `pending_review` | cancel_review | `draft` | 本轮提交人 | 本轮尚无审核决定、届次未关闭（重提仍须在报名时间窗内）；保留并标记原提交已取消，回工作副本 |
| `pending_review` | approve | `approved` | `approval:review_single` | 审核意见可空；禁止本轮学生成员/提交人自审；设置 approved_submission_no=current_submission_no |
| `pending_review` | return | `returned` | 同上 | 意见必填 |
| `pending_review` | reject | `rejected` | 同上 | 意见必填 |
| `pending_review` | withdraw | `withdrawn` | 提交人 | 未出结果前 |
| `returned` | resubmit | `pending_review` | 提交人 | 截止前；保留审核历史；重提次数不限但每次留痕 |
| `returned` | withdraw | `withdrawn` | 提交人 | — |
| `approved` | reject | `rejected` | approval:reject_approved（本届赛事审核权限） | 意见必填；名单未锁定且无非作废证书，保留原提交版本 |
| `rejected` | resubmit | `pending_review` | 原有编辑权人 | 修改同一报名，截止前且按当前资格/准入校验；新建提交轮次 |
| 终态 `withdrawn` | — | — | — | 不可再迁移 |

### 1.3 迁移表（two_stage 模式，里程碑 2 启用）

```
draft ─submit→ submitted ─org_approve→ org_approved ─final_approve→ approved
  ↑               │ org_return ↓↑ resubmit        │ final_return ↓ → returned（重走初审）
  └─ returned/org_returned ──┘                   │ final_reject ↓ → rejected
       submitted ─org_reject→ org_rejected           │
       submitted 尚无本轮审核决定可 cancel_review → draft（保留原提交）
       org_approved 已经有人审核，不能主动取消修改
```

要点：初审驳回进 org_rejected，复审驳回进 rejected；两者均允许修改后 resubmit → submitted。复审退回进 returned，修改后重提同样**从初审重新走**（`resubmit → submitted`）；审核记录 `approval_records` 完整保留每一轮每一步（含 step='org'|'final'、轮次 round_no）。

### 1.4 时间窗规则

- 本场提交后（含 approved）资料/成员/学段/材料均冻结；队伍档案可经独立审核更新用于其他比赛，本场快照保持原样。
- cancel_review 只允许当前 pending_review/submitted 且本轮无 approve/reject/return 决定，锁定同一报名与审核动作串行竞争；取消先提交则后到审核返回 40906。已审核或 approved 必须先由审核员驳回再改。取消后下一次 submit 新建轮次，不覆盖旧版。
- 驳回时清空 approved_submission_no，并作废未锁定名单中该轮的待定获奖条目（保留历史），新轮次需重新评奖；有锁定名单/非作废证书时先按解锁作废流程处理。
- 个人报名按现有资格规则执行；团队已审核版本、成员冻结及赛季许可在首期启用，准入名单与复杂跨队特批仍在里程碑2。首期不校验年龄，声明学段/年级条件与在读证明材料按PRD核验。证书相关阻断仅在后续证书能力启用后产生，不能据此要求首期交付证书。
- 每次 submit/resubmit 新建 registration_submissions 并冻结本轮成员/文件；returned/rejected/org_returned/org_rejected 只编辑工作副本，不更新历史提交，审核必须指明当前 submission_no，过期操作返回 40906。
- two_stage 同样允许 approved → reject → rejected（approval:reject_approved），重提回到 submitted，重走初审；rejected/org_rejected 均不是终态，仍使用原报名编号。驳回后不自动清除原提交记录或取消唯一性占用。
- 已通过报名被驳回后立即退出通过名单；截止后允许驳回但不自动延长重提窗口，主办方如允许补正须先调整有效报名时间窗。
- 提交/重提/撤回仅在 `enroll_start ≤ now ≤ enroll_end` 内允许；已 `pending_review` 的存量报名在截止后仍可被审核。
- 截止时 `draft` 状态报名不自动作废（仅从未提交的草稿可在 30 天后清理，已有提交历史永久保留，P1）。

## 1.5 赛季与单位交接

- 队伍赛季注册 draft→submitted→approved/rejected；submitted 尚未审核可 withdrawn，驳回/撤回后复制关联新草稿重提；approved 可由平台说明理由后 revoked。仅平台审核且不得自审，队伍×赛季同时最多一个草稿/待审/有效许可。
- 当前赛季只由平台 set_current 切换到 active，普通查询不可改变。切换不迁移许可或结束旧赛季，旧待审仍可审核，新提交/重提只准当前赛季。
- 赛季 draft→active→archived（仅平台管理；归档前无未完成赛事/待审报名，归档后禁止提交、重提及审批通过）；日期独立配置，可跨年/并行。单场赛事关闭不释放赛季绑定；赛季归档保留绑定历史，后续入队不再以该赛季限制。
- 单位转移 draft→awaiting_source→awaiting_target→completed；原/新单位分别审核转出与接收，未完成可取消，任一方可驳回；仅 completed 原子切换主属关系与重置权限。每次处理核对 base_affiliation_version，过期 40906。平台可核验代办原单位转出，不能跳过新单位接收。
- 单位转移不改当前/历史报名或赛季绑定，仍在队时先退队；不能以转学绕过串队限制。

## 2. 赛事状态机

`draft`（草稿）→ `published`（已发布）→ `archived`（已归档）。

| 动作 | 迁移 | 角色 | 约束 |
| --- | --- | --- | --- |
| publish | draft→published | competition_admin | 至少 1 个草稿或已发布届次通过发布清单；门户还需该届次已发布且位于当前赛季 |
| archive | published→archived | competition_admin | 无进行中的报名/审核 |
| unarchive | archived→published | platform_admin | 应急通道，留审计 |

赛事级不显示"报名中"——报名中/报名结束是**届次**属性（由时间窗 + 届次状态推导），避免两级状态打架。

## 3. 届次状态机

| 状态 | 含义 | 迁移 |
| --- | --- | --- |
| `draft` | 配置中 | create/edit |
| `published` | 已发布（对外可见） | 时间窗推导子状态：未开始 / `enrolling` 报名中 / `enroll_ended` 报名结束 / 进行中 / `finished` 已结束 |
| `closed` | 关闭（获奖名单锁定 + 证书发放完成后手动关闭） | 仅从 finished 进入；closed 后业务写入冻结，历史仅管理端按权限读取，普通门户/本人业务历史隐藏；证书补发/作废与必要公示下架仍可进行 |

`enrolling` 等由 `now` 与时间窗计算得出（存储上只有 `draft/published/closed`，派生状态不入库，防止定时器忘推状态）。

已接入届次发布门槛：赛季为 active、赛事未归档、名称与场地齐全、时间有序且报名尚未截止、有实际开放组合、审核/准入/材料规则受当前实现支持。两级发布不隐式修改对方状态。发布写入会在事务中重新校验；清单预览不持锁，不能代替写入校验。

## 4. 赛项与组别状态机

两者同为 `enabled` ⇄ `disabled`，约束相同：已有非 `draft` 报名时禁止删除（只可停用）；停用后不可新提交，但存量照常审核与公示。

**组合级停用与整体停用的区别（v1.1）**：停用某个「赛项×组别」组合（`competition_offerings.status=disabled`）只关闭该组合的报名入口，赛项与组别本身仍可被其他组合使用；停用赛项或组别则连带使其全部组合不可报名。判定顺序：赛项启用 ∧ 组别启用 ∧ 组合开放，三者任一不满足即拒绝提交（42207）。

## 5. 获奖名单状态机

名单以 **届次 × 赛项 × 组别**（即 `offering_id`）为单位聚合（表 `award_rosters`，见 04 文档新增表）；通用奖项名单的 `offering_id` 为 NULL，以届次为单位。

```
editing ─submit→ under_approval ─approve→ confirmed ─auto(本名单全部证书已发放)→ issued
                    │ reject ↓
                    └→ editing（保留修改痕迹）
confirmed/issued ─unlock(reason)→ editing   # 仅 competition_admin，留审计，该名单所有非 revoked 证书需先作废（含 queued/generated/failed），并使旧生成任务失效
```

- `confirmed` 起名单锁定，获奖记录禁止增删改；`award_records` 没有独立 status 字段。部分生成失败时名单留在 confirmed，只重试失败成员；全部目标证书 issued 后名单才进 issued，空名单不可提交。
- 导入的"待人工确认"行不进入名单状态机，单独放 `award_import_pending` 表处理。

## 6. 证书状态机

```
queued（生成请求已持久化，等待投递/执行） → generated（PDF 就绪） → issued（已发放，持有人可见）
queued/generated/issued/failed → revoked（作废，issued 的验证页显示无效）
issued → reissue 动作 → 旧证 revoked + 新证 queued（reissue_of 指向旧证）
queued → failed（渲染或上传失败，重试耗尽）
failed → queued（显式重试，复用原证书行与编号）
```

约束：一个「award_record × recipient_member_id」同时最多 1 张非 revoked 证书；获奖仅面向学生，成员取报名冻结学生名单，队长/member 均发证，coach 不获奖或发证。重试复用证书行和编号，补发新建行；每张原证只允许一个直接后继。`revoke` 需理由；issued、queued、generated、failed 均可作废，生成任务锁定证书并复核状态，避免作废后回写生效。

### 6.1 作废证书在公开验证页的表现（v1.1 补定）

持证人可能在签发后已下载 PDF，事后作废会让那张 PDF 变成无法解释的死链。因此 `revoked` 证书**仍可被验证页解析**（token 不作废、不 404），只是结论不同：

| 场景 | 验证页输出 |
| --- | --- |
| `issued` | 有效 + 编号、姓名脱敏、赛事/赛项/组别/奖项、签发日期 |
| `revoked` 且已补发 | 已作废 + **新证编号**（读 `supersedes_serial`），不展示新证详情 |
| `revoked` 且纯作废 | 已作废，不显示原因（原因含内部信息，仅管理端可见） |
| queued / generated / failed | 404，不展示未签发证书 |
| token 不存在 | 无效证书编号（与"已作废"分文案，便于区分录入错误与真作废） |

- `supersedes_serial` 在 reissue 事务内回写旧证，只写一次。
- 补发新证取**新序号**，不复用旧序号（04 §6 计数器不回收）。
- 验证页对 `revoked` 永久可查，与审核记录、证书行"永久保留"口径一致。

## 7. 辅助状态

- 用户账号：`pending` → `active`（完成档案）；`active` ⇄ `disabled`（仅 platform_admin）。
- 单位运行状态 active ⇄ suspended；新建申请与正式单位分开，只有审核通过才创建正式单位。
- 单位/队伍/证件申请共用流程：draft → submitted → approved / returned / rejected，submitted 尚无审核决定时可 cancel-and-edit：原申请置 withdrawn，复制关联新 draft 返回新 ID。submitted 后提案锁定；returned/rejected/withdrawn 均保留，重提新建申请。审核意见在退回/驳回时必填，审核人不得为申请人。
- 单位创建由平台审核；队伍由单位管理员统一管理，创建及赛季激活仅平台审核，资料/成员修改由另一名有权单位管理员或平台审核，禁止自审；教练不修改队伍资料或成员。队伍创建批准时建正式队伍并绑定首个已审核申请；修改批准时比较 base_revision_id 与当前版本，一致才原子替换，否则 40906。一个正式队伍只允许一份 draft/submitted 变更申请。
- 证件更正：submitted → approved 时校验 base_identity_version、新证件唯一性及审核范围，禁止申请人/证件所属人自审；事务内切换当前绑定并释放旧号、递增会话版本。退回/驳回/取消不改变当前证件。
- 本人 leave_own 立即结束当前成员关系，普通管理员入退队变更仍须批准；全平台仅一支当前队伍。退队不改本场快照，也不解除首次通过时的同赛季同赛项绑定；原队回归可普通申请入队，其他队伍须平台特批。并发归属冲突 40908，绑定冲突 40909。
- 特批换队申请：draft→submitted→approved/rejected；未审可取消留档。仅平台审核且禁止自审；批准并原子执行归属及绑定变更，先取消/驳回受影响原队报名，有锁定名单/证书则阻断，目标队报名另行重提。无审核通过就不得更改绑定；失败整体回滚。
- 队伍运行状态 active ⇄ disbanded 独立于资料版本；解散按既有权限执行。成员 joined_at/left_at 在普通变更批准、本人自主退队或平台特批执行时更新；解散时同事务结束当前成员关系并审计，旧成员关系和旧提案不删除；修改待审不阻断按旧审核版本报名。
- 准入名单 active ⇄ revoked，按届次管理；变更与提交/重提/批准使用同一届次行锁。名单移除不自动迁移报名状态，批准前重新确认准入。

## 8. 定时器与派生规则汇总

| 触发 | 行为 | 实现 |
| --- | --- | --- |
| 每 5 分钟 | 届次报名窗开关（纯派生，无需写库） | 前端/API 动态计算 |
| enroll_end 后 1h | 给未审完的报名的审核人发提醒 | Celery beat |
| roster confirmed | 自动排队批量生成证书 | 业务事务写 outbox → dispatcher → Celery |
| 每日 | 清理从未提交的超期 draft 报名（30 天） | Celery beat（P1） |
| 每分钟 | outbox 待投/租约超期记录补投，失败告警 | 持久化事件 + 幂等消费，不依赖 on_commit 成功 |

## 9. 名单公示（非状态机，v1.1）

公示不是新状态，而是届次上的可逆开关 + 时间戳（`roster_publication` / `roster_published_at`）。理由：「通过队伍」随审核进度实时变化，做成状态机就得每次审核后重新发布一遍。

- `publish`：写 `roster_published_at=now()`，要求 `edition.status='published'` 且 `roster_publication != 'none'`；由 `roster:publish`（届次作用域）执行，写审计。
- `unpublish`：由 `roster:unpublish` 执行，清空 `roster_published_at`，公开页立即返回 404（判定顺序见 02 §4.7），用于发现名单有误时快速下架。
- 已公示内容随 `registrations.status` 实时变化：某报名被驳回后自动从公开页消失，不需重新发布——这是选"开关而非状态"的直接收益。
- 档位变更（`open`→`login`→`none`）不通知持证人；已流出的公示截图无法撤回，需在主办方说明中写明。
