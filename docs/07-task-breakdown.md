# 07 开发任务拆解

**版本**：v1.1（2026-11-16）。假设 1–2 名全栈开发，周 = 5 工作日。
拆分原则：每周结束都有可演示物；依赖方向 = 权限 → 组织/赛事 → 报名 → 获奖/证书。

v1.1 变更：新增日志基座、邮箱验证码、身份证加密、赛项/开放组合、公示名单、证书编号计数器等工作项，工期由 12 周增至 15 周（依据见文末「工期影响」）。

**编号约定**：`W1`…`W15` 是**任务包编号，不等于自然周**。一个任务包可以跨多周，多包也可在一周内并行。v1.1 只在 W1、W3、W4、W6、W7、W8 内部增加条目，未重排既有编号——其他文档引用的「W5 快照服务」「W8 交付」「W12 压测」等仍然有效。里程碑 1 实际占用 11 周，里程碑 2 从 W12 起（即第 12–15 周）。

---

## 里程碑 1：单级审核闭环（任务包 W1–W8，约 11 周）

目标：一个真实赛事从创建到证书发放全程可走通（`approval_mode=single`、固定报名表单、无队伍管理——个人报名先行）。

### W1 基础设施 + 账号

- [ ] backend 初始化：Django 5 + DRF + config 分层 settings（env）、Postgres/Redis/MinIO docker compose 联通
- [ ] **日志基座（v1.1 提前到 W1）**：structlog JSON 输出、`request_id` contextvars 中间件、请求完成日志、SQL 计时 wrapper 与慢查询阈值、脱敏过滤器（DEVELOPMENT.md §2）
- [ ] frontend 初始化：Vite + Vue3 + TS + Element Plus + Pinia + router + axios 拦截器、统一响应/错误码（06 §1）
- [ ] **样式令牌层（v1.1）**：Radix Colors 依赖 + `tokens.css` + Element Plus 变量映射 + 0.5px 边框兜底（DEVELOPMENT.md §4），先立骨架再写页面，否则后期逐页返工
- [ ] `core`：响应包裹、异常处理器、软删除 mixin、分页、审计 middleware 骨架
- [ ] accounts：注册/登录/JWT 轮转/密码重置 + **邮箱验证码**（`verification_codes` 表、发信、60s 限频、试错作废）
- [ ] **SMTP 打通（v1.1，上线前置）**：本地加 Mailpit 容器验证；生产发信域名的 SPF/DKIM 记录清单交运维
- 验收：容器一键起；注册→登录→me 返回 grants 空数组；**任一新接口都能在 stdout 看到带 request_id 的请求日志与 SQL 汇总**

### W2 RBAC 核心（全系统地基，值得多花时间）

- [ ] rbac app：roles/permissions/user_roles 表 + seed 脚本（6 内置角色 × 02 文档 permission 全清单，含 v1.1 新增 `event:*` / `roster:publish`）
- [ ] `ScopedRolePermission` + `resolve_scope()`（继承规则 1/2/3）+ 单元测试矩阵用例全覆盖
- [ ] `GET /me` 展开 grants；前端 `hasPerm()` + v-perm 指令 + 动态菜单
- [ ] 角色授予 API（含"自己不能授予比自己大的权限"校验）
- [ ] `rbac.denied` 埋点接入（403 排障主入口，DEVELOPMENT.md §2.5）
- 验收：测试用例：org_admin 管不了兄弟单位；edition 作用域 reviewer 只能审该届次

### W3 组织与人员

- [ ] orgs：CRUD、**treebeard 物化路径树**（v1.1，取代 parent_id 递归查询）、启停、入驻申请两步；成员管理 + 主属单位约束
- [ ] profiles：档案完善/修改、人员身份、参赛历史页（数据聚合查询）
- [ ] **身份证处理（v1.1，P0）**：Fernet 列加解密、pepper 哈希、18 位校验位验证、`uniq_profile_id_number` 查重、末四位展示工具函数、与日志脱敏联调
- [ ] 用户管理后台页（列表/禁用/角色分配 UI）
- 验收：超管建"大学→学院"树、导入 50 成员、学院管理员只见本树；同一身份证重复绑定被拒，且提示不泄露已有账号信息

### W4 赛事与届次

- [ ] competitions：CRUD、分类/级别、封面附件、publish/archive 状态机、主办/承办/协办单位
- [ ] editions：CRUD、时间窗、publish/close、派生状态计算（enrolling 等不入库）
- [ ] **events（v1.1 新增 app）**：赛项 CRUD + 状态、`competition_offerings` 开放组合 CRUD 与停用约束
- [ ] groups：组别（学段）CRUD + 状态 + **资格校验器**（学段/年级/年龄）
- [ ] competition_admins（写 user_roles + 展示表双写）
- [ ] 门户公开页：赛事列表/详情（AllowAny serializer 白名单）
- [ ] 管理端：赛项/组别/开放组合配置页，组合用矩阵视图（一眼看出哪些赛项在哪些学段开放）
- 验收：非管理员视角可浏览已发布赛事与届次；配置 VURC 仅开放大学组后，其他学段的队伍在报名页看不到该赛项

### W5 报名（上）

- [ ] registrations 模型与快照服务：`create_snapshot()`（成员 `snapshot` + `public_info` 双份 / 文件 / consent）
- [ ] 唯一索引防重复报名（按 `offering_id` 口径，04 §5）
- [ ] 业务校验全量：时间窗（组合级覆盖）、组合是否开放、赛项人数上下限、教练必填、材料必传、学段相符（42205）、身份证校验位（42206）、邮箱已验证（42208）
- [ ] `eligible-groups` 接口：按队伍/本人学段返回可选组别，杜绝用户自选
- [ ] 报名前端表单（个人）：按赛项动态显隐必填与材料上传
- [ ] 埋点 `registration.submitted`（DEVELOPMENT.md §2.5）
- 验收：并发脚本双提交同人同赛项同组别 → 仅一条成功

### W6 报名（下）与单级审核

- [ ] submit/withdraw/resubmit 全链路接 `transition()` + approval_records
- [ ] 文件上传（MinIO 预签名）+ 材料确认事务
- [ ] 审核台：筛选列表（届次/赛项/组别/单位/状态）、详情（时间线组件）、approve/reject/return（意见必填）、批量审核
- [ ] **成员字段分级 serializer（v1.1）**：`read_own` 只出本人与同队 `public_info`，证件字段按角色降为末四位或不显示（06 报名接口说明）。身份证必填后这是最高风险的越权点，必须本周完成并补测试
- [ ] notifications：站内消息 + Celery 邮件（结果/退回通知）
- 验收：一条报名走完 提交→退回→重提→通过 全过程且历史记录完整；**用队员 B 账号请求队员 A 的报名详情，断言响应体不含 A 的任何证件字段**

### W7 获奖名单与公示

- [ ] awards 配置（届次×赛项×组别；通用奖项 `offering_id` 为 NULL）+ quota 软校验
- [ ] roster：从 approved 报名挑选录入、`award_import_pending` 冲突处理流（batch_no 主匹配，姓名/id_hash 二次校验）
- [ ] **django-import-export 接入（v1.1）**：`Resource` 定义 + dry-run + 行级错误收集，绕过 admin 直接调 API
- [ ] 名单状态机 editing→under_approval→confirmed；unlock 带理由 + 审计
- [ ] **通过名单公示（v1.1 新增）**：届次级三档开关 + publish/unpublish、`/public/editions/{id}/roster` 只读接口（判定顺序 02 §4.7）、字段白名单两次交集、门户公示页（赛事→届次→赛项→组别下钻，队伍卡片显示队号/单位/成员姓名）
- 验收：导入含 3 类脏数据（不存在/重名/重复获奖）的 Excel，全部进待确认队列且可处置；公示页未发布时 404、`none` 档 404、unpublish 后立即不可见；白名单外字段即使前端传参也不返回

### W8 证书 + 看板收尾（里程碑 1 交付）

- [ ] certificates：queued→generated→issued 流水线（Celery + WeasyPrint 模板 + 中文字体入镜像）
- [ ] **编号计数器（v1.1）**：`certificate_sequences` 事务内 `SELECT ... FOR UPDATE` 取号，序号不回收；`serial_prefix` / `serial_no_seq` 写后不可变
- [ ] 二维码公开验证页 `/public/certificates/verify/{token}`（限流、脱敏）；**作废态按 03 §6.1 输出新证编号**
- [ ] 我的证书页（列表 + PDF 下载）；revoke/reissue（P0 简化版：作废 + 手动补发 + 回写 `supersedes_serial`）
- [ ] stats/dashboard P0 计数卡片（增加按赛项/组别维度）；audit-logs 查询页
- [ ] E2E 冒烟脚本（报名→审核→公示→名单→证书）；部署文档 v1
- 验收：**用真实流程演练一场校级比赛** —— 里程碑 1 完成的唯一标准

## 里程碑 2：队伍与两级审核（第 12–15 周，见下方工期影响）

- [ ] W12 队伍管理：teams/team_members（变动留痕）、**学段派生规则（04 §3）**、教练代报、团队报名打通（快照含全员）
- [ ] W13 两级审核：`two_stage` 状态机激活、org 初审工作台、step/round 审核记录、模式切换防护（存量单级报名不受影响）
- [ ] W14 Excel 完整导入导出中心（人员/报名/名单/统计，异步任务 + 文件下载）、赛项与组别停用约束、draft 清理任务
- [ ] W15 统计图表（Chart.js：单位/赛项/组别维度、通过率趋势）、性能压测报名截止场景（500 并发）、安全自查清单（越权用例库回归，**重点覆盖证件字段分级与公示页**）、staging 上线演练

## 工期影响（v1.1）

本轮新增项全部落在 P0，原 12 周无法吸收，实际增加约 3 周：

| 新增项 | 估时 | 落点 |
| --- | --- | --- |
| 日志基座（structlog + request_id + SQL 计时 + 脱敏） | 3 天 | W1，之后每周复用 |
| 邮箱验证码 + SMTP 打通 | 2 天 | W1 |
| 样式令牌层（Radix + Element Plus 映射 + 0.5px） | 1.5 天 | W1 |
| 身份证加解密 + 校验位 + 查重 + 脱敏 | 3 天 | W3 |
| 赛项 / 开放组合（app + 迁移 + 矩阵配置页） | 3 天 | W4 |
| 成员字段分级 serializer + 测试 | 1.5 天 | W6 |
| 通过名单公示（接口 + 门户页 + 判定顺序） | 3 天 | W7 |
| 证书编号计数器 + 作废链 | 1 天 | W8 |

**结论**：里程碑 1 从 8 周调整为 11 周，总周期 12 周变 15 周。若必须守住 12 周，砍的顺序建议是 W14 导出中心 → W15 统计图表 → 公示页面前端（接口先留），**不建议压缩日志基座与证件字段分级**：前者决定线上能否排障，后者决定"强制收集身份证"会不会演变成泄露事故。

## 贯穿事项

1. 每周合并前：`pytest`（后端 service 层覆盖率 ≥ 80%，重点 rbac/registration/awards）+ 状态机用例与 03 文档逐条对应。
2. 文档即代码：状态枚举、permission code、错误码三处常量单一来源（后端 `core/constants.py`），文档变更走 PR 评审。
3. 明确不做清单（防范围蔓延）：动态表单、支付、短信、评分、赛程——出现在任何 PR 描述里先拒绝。
4. P1 backlog（里程碑 2 后评审）：动态表单引擎、列加密复核、audit 分区、competition_admins 表合并、导出中心、限流精细化。
