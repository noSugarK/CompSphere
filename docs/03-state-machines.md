# 03 状态机设计

**版本**：v1.1（2026-11-16）。所有状态迁移必须由服务层 `transition(obj, action, actor)` 统一校验，禁止直接 update 状态字段。状态值即数据库 `status` 列的取值，命名 snake_case。

v1.1 变更：报名提交前置条件加入赛项/组合/学段校验；§4 拆为赛项与组别两套并补组合级停用；§5 名单单位改为「届次×赛项×组别」；新增 §6.1 作废证书验证页语义、§9 名单公示。

---

## 1. 报名状态机（核心）

审核模式为**届次级配置** `approval_mode ∈ {single, two_stage}`。两种模式共用一张状态表，`two_stage` 仅多经过初审态。里程碑 1 只启用 `single`，但状态枚举与迁移表一次定死，避免以后改数据字典。

### 1.1 状态枚举

| 状态 | 含义 | 适用模式 |
| --- | --- | --- |
| `draft` | 草稿，未提交 | 通用 |
| `submitted` | 已提交，等待初审 | two_stage |
| `org_approved` | 单位初审通过，等待赛事复审 | two_stage |
| `org_returned` | 初审退回修改 | two_stage |
| `org_rejected` | 初审驳回（终止） | two_stage |
| `pending_review` | 待赛事审核 | single |
| `returned` | 退回修改（终止前可重提） | single（two_stage 的复审退回直接进 `returned` 重走初审） |
| `rejected` | 驳回（终止） | 通用 |
| `approved` | 审核通过 | 通用 |
| `withdrawn` | 参赛者撤回 | 通用（仅未通过前） |

### 1.2 迁移表（single 模式）

| 当前态 | 动作 | 目标态 | 执行角色 | 前置条件 |
| --- | --- | --- | --- | --- |
| `draft` | submit | `pending_review` | 提交人（本人/队长/代报教练） | 时间窗内、赛项与组别均启用、该「赛项×组别」组合已开放、学段相符、校验全过 |
| `draft` | delete | （软删） | 提交人 | — |
| `pending_review` | approve | `approved` | `approval:review_single` | 审核意见可空 |
| `pending_review` | return | `returned` | 同上 | 意见必填 |
| `pending_review` | reject | `rejected` | 同上 | 意见必填 |
| `pending_review` | withdraw | `withdrawn` | 提交人 | 未出结果前 |
| `returned` | resubmit | `pending_review` | 提交人 | 截止前；保留审核历史；重提次数不限但每次留痕 |
| `returned` | withdraw | `withdrawn` | 提交人 | — |
| `approved` | revoke_approval | `pending_review` | `competition_admin` | 仅限名单未锁定前，需理由，写日志 |
| 终态 `rejected/withdrawn` | — | — | — | 不可再迁移 |

### 1.3 迁移表（two_stage 模式，里程碑 2 启用）

```
draft ─submit→ submitted ─org_approve→ org_approved ─final_approve→ approved
  ↑               │ org_return ↓↑ resubmit        │ final_return ↓ → returned（重走初审）
  └─ returned/org_returned ──┘                   │ final_reject ↓ → rejected
       submitted ─org_reject→ rejected           │
       提交人在 submitted/org_approved 可 withdraw → withdrawn
```

要点：复审退回后进 `returned`，修改后重提**从初审重新走**（`resubmit → submitted`）；审核记录 `approval_records` 完整保留每一轮每一步（含 step='org'|'final'、轮次 round_no）。

### 1.4 时间窗规则

- 提交/重提/撤回仅在 `enroll_start ≤ now ≤ enroll_end` 内允许；已 `pending_review` 的存量报名在截止后仍可被审核。
- 截止时 `draft` 状态报名不自动作废（保留 30 天后定时清理，P1）。

## 2. 赛事状态机

`draft`（草稿）→ `published`（已发布）→ `archived`（已归档）。

| 动作 | 迁移 | 角色 | 约束 |
| --- | --- | --- | --- |
| publish | draft→published | competition_admin | 至少 1 个届次，且至少 1 个「赛项×组别」组合处于开放状态 |
| archive | published→archived | competition_admin | 无进行中的报名/审核 |
| unarchive | archived→published | platform_admin | 应急通道，留审计 |

赛事级不显示"报名中"——报名中/报名结束是**届次**属性（由时间窗 + 届次状态推导），避免两级状态打架。

## 3. 届次状态机

| 状态 | 含义 | 迁移 |
| --- | --- | --- |
| `draft` | 配置中 | create/edit |
| `published` | 已发布（对外可见） | 时间窗推导子状态：未开始 / `enrolling` 报名中 / `enroll_ended` 报名结束 / 进行中 / `finished` 已结束 |
| `closed` | 关闭（获奖名单锁定 + 证书发放完成后手动关闭） | 仅从 finished 进入；closed 后除证书补发/作废外全冻结 |

`enrolling` 等由 `now` 与时间窗计算得出（存储上只有 `draft/published/closed`，派生状态不入库，防止定时器忘推状态）。

## 4. 赛项与组别状态机

两者同为 `enabled` ⇄ `disabled`，约束相同：已有非 `draft` 报名时禁止删除（只可停用）；停用后不可新提交，但存量照常审核与公示。

**组合级停用与整体停用的区别（v1.1）**：停用某个「赛项×组别」组合（`competition_offerings.status=disabled`）只关闭该组合的报名入口，赛项与组别本身仍可被其他组合使用；停用赛项或组别则连带使其全部组合不可报名。判定顺序：赛项启用 ∧ 组别启用 ∧ 组合开放，三者任一不满足即拒绝提交（42207）。

## 5. 获奖名单状态机

名单以 **届次 × 赛项 × 组别**（即 `offering_id`）为单位聚合（表 `award_rosters`，见 04 文档新增表）；通用奖项名单的 `offering_id` 为 NULL，以届次为单位。

```
editing ─submit→ under_approval ─approve→ confirmed ─auto(首批证书生成完成)→ issued
                    │ reject ↓
                    └→ editing（保留修改痕迹）
confirmed/issued ─unlock(reason)→ editing   # 仅 competition_admin，留审计，证书若已 issued 需先全部作废
```

- `confirmed` 起名单锁定，个人获奖记录 `award_records.status` 不再可变。
- 导入的"待人工确认"行不进入名单状态机，单独放 `award_import_pending` 表处理。

## 6. 证书状态机

```
queued（Celery 任务已排） → generated（PDF 就绪） → issued（已发放，持有人可见）
issued → revoked（作废，验证页显示无效）
issued → reissue 动作 → 旧证 revoked + 新证 queued（reissue_of 指向旧证）
generated → failed（渲染错误，可重试）
```

约束：一个 `award_record` 同时最多 1 张非 `revoked` 证书（部分唯一索引）；`revoke` 需理由并通知持证人。

### 6.1 作废证书在公开验证页的表现（v1.1 补定）

持证人可能在签发后已下载 PDF，事后作废会让那张 PDF 变成无法解释的死链。因此 `revoked` 证书**仍可被验证页解析**（token 不作废、不 404），只是结论不同：

| 场景 | 验证页输出 |
| --- | --- |
| `issued` | 有效 + 编号、姓名脱敏、赛事/赛项/组别/奖项、签发日期 |
| `revoked` 且已补发 | 已作废 + **新证编号**（读 `supersedes_serial`），不展示新证详情 |
| `revoked` 且纯作废 | 已作废，不显示原因（原因含内部信息，仅管理端可见） |
| token 不存在 | 无效证书编号（与"已作废"分文案，便于区分录入错误与真作废） |

- `supersedes_serial` 在 reissue 事务内回写旧证，只写一次。
- 补发新证取**新序号**，不复用旧序号（04 §6 计数器不回收）。
- 验证页对 `revoked` 永久可查，与审核记录、证书行"永久保留"口径一致。

## 7. 辅助状态

- 用户账号：`active` ⇄ `disabled`（platform_admin / org_admin 按权限矩阵）。
- 组织：`active` ⇄ `suspended`；入驻申请：`pending → approved / rejected`。
- 队伍：`active` ⇄ `disbanded`；成员变动以 `team_members.joined_at/left_at` 表达，不删行。

## 8. 定时器与派生规则汇总

| 触发 | 行为 | 实现 |
| --- | --- | --- |
| 每 5 分钟 | 届次报名窗开关（纯派生，无需写库） | 前端/API 动态计算 |
| enroll_end 后 1h | 给未审完的报名的审核人发提醒 | Celery beat |
| roster confirmed | 自动排队批量生成证书 | Django signal → Celery |
| 每日 | 清理超期 draft 报名（30 天） | Celery beat（P1） |
| 每日 | 队伍学段与存量 approved 报名组别不一致清单 | Celery beat，仅产出告警供主办方核对，不自动改数据、不阻断操作（04 §3 规则 3） |

## 9. 名单公示（非状态机，v1.1）

公示不是新状态，而是届次上的可逆开关 + 时间戳（`roster_publication` / `roster_published_at`）。理由：「通过队伍」随审核进度实时变化，做成状态机就得每次审核后重新发布一遍。

- `publish`：写 `roster_published_at=now()`，要求 `edition.status='published'` 且 `roster_publication != 'none'`；由 `roster:publish`（届次作用域）执行，写审计。
- `unpublish`：清空 `roster_published_at`，公开页立即返回 404（判定顺序见 02 §4.7），用于发现名单有误时快速下架。
- 已公示内容随 `registrations.status` 实时变化：某报名被 `revoke_approval` 撤回后自动从公开页消失，不需重新发布——这是选"开关而非状态"的直接收益。
- 档位变更（`open`→`login`→`none`）不通知持证人；已流出的公示截图无法撤回，需在主办方说明中写明。
