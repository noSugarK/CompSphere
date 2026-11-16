# 07 开发任务拆解

**版本**：v1.0（2026-11-16）。假设 1–2 名全栈开发，周 = 5 工作日。
拆分原则：每周结束都有可演示物；依赖方向 = 权限 → 组织/赛事 → 报名 → 获奖/证书。

---

## 里程碑 1：单级审核闭环（第 1–8 周）

目标：一个真实赛事从创建到证书发放全程可走通（`approval_mode=single`、固定报名表单、无队伍管理——个人报名先行）。

### W1 基础设施 + 账号

- [ ] backend 初始化：Django 5 + DRF + config 分层 settings（env）、Postgres/Redis/MinIO docker compose 联通
- [ ] frontend 初始化：Vite + Vue3 + TS + Element Plus + Pinia + router + axios 拦截器、统一响应/错误码（06 §1）
- [ ] `core`：响应包裹、异常处理器、软删除 mixin、分页、审计 middleware 骨架
- [ ] accounts：注册/登录/JWT 轮转/验证码（Redis）/密码重置
- 验收：容器一键起；注册→登录→me 返回 grants 空数组

### W2 RBAC 核心（全系统地基，值得多花时间）

- [ ] rbac app：roles/permissions/user_roles 表 + seed 脚本（6 内置角色 × 02 文档 permission 全清单）
- [ ] `ScopedRolePermission` + `resolve_scope()`（继承规则 1/2/3）+ 单元测试矩阵用例全覆盖
- [ ] `GET /me` 展开 grants；前端 `hasPerm()` + v-perm 指令 + 动态菜单
- [ ] 角色授予 API（含"自己不能授予比自己大的权限"校验）
- 验收：测试用例：org_admin 管不了兄弟单位；edition 作用域 reviewer 只能审该届次

### W3 组织与人员

- [ ] orgs：CRUD、parent 树、启停、入驻申请两步；成员管理 + 主属单位约束
- [ ] profiles：档案完善/修改、人员身份、参赛历史页（数据聚合查询）
- [ ] 用户管理后台页（列表/禁用/角色分配 UI）
- 验收：超管建"大学→学院"树、导入 50 成员、学院管理员只见本树

### W4 赛事与届次

- [ ] competitions：CRUD、分类/级别、封面附件、publish/archive 状态机、主办/承办/协办单位
- [ ] editions：CRUD、时间窗、publish/close、派生状态计算（enrolling 等不入库）
- [ ] competition_admins（写 user_roles + 展示表双写）
- [ ] 门户公开页：赛事列表/详情（AllowAny serializer 白名单）
- 验收：非管理员视角可浏览已发布赛事与届次

### W5 组别与报名（上）

- [ ] groups：配置全字段 + material_requirements JSON 校验器
- [ ] registrations 模型与快照服务：`create_snapshot()`（成员/文件/consent）、唯一索引防重复报名、全部业务校验（时间窗/对象/年级/人数/材料，错误码 422xx）
- [ ] 报名前端表单（个人）：按组别动态显隐必填与材料上传
- 验收：并发脚本双提交同人同组别 → 仅一条成功

### W6 报名（下）与单级审核

- [ ] submit/withdraw/resubmit 全链路接 `transition()` + approval_records
- [ ] 文件上传（MinIO 预签名）+ 材料确认事务
- [ ] 审核台：筛选列表、详情（时间线组件）、approve/reject/return（意见必填）、批量审核
- [ ] notifications：站内消息 + Celery 邮件（结果/退回通知）
- 验收：一条报名走完 提交→退回→重提→通过 全过程且历史记录完整

### W7 获奖名单

- [ ] awards 配置（届次×组别）+ quota 软校验
- [ ] roster：从 approved 报名挑选录入、`award_import_pending` 冲突处理流（batch_no 主匹配，姓名/id_hash 二次校验）
- [ ] 名单状态机 editing→under_approval→confirmed；unlock 带理由 + 审计
- 验收：导入含 3 类脏数据（不存在/重名/重复获奖）的 Excel，全部进待确认队列且可处置

### W8 证书 + 看板收尾（里程碑 1 交付）

- [ ] certificates：queued→generated→issued 流水线（Celery + WeasyPrint 模板 + 中文字体入镜像）
- [ ] 二维码公开验证页 `/public/certificates/verify/{token}`（限流、脱敏）
- [ ] 我的证书页（列表 + PDF 下载）；revoke/reissue（P0 简化版：作废 + 手动补发）
- [ ] stats/dashboard P0 计数卡片；audit-logs 查询页
- [ ] E2E 冒烟脚本（报名→审核→名单→证书）；部署文档 v1
- 验收：**用真实流程演练一场校级比赛** —— 里程碑 1 完成的唯一标准

## 里程碑 2：队伍与两级审核（第 9–12 周）

- [ ] W9 队伍管理：teams/team_members（变动留痕）、教练代报、团队报名打通（快照含全员）
- [ ] W10 两级审核：`two_stage` 状态机激活、org 初审工作台、step/round 审核记录、模式切换防护（存量单级报名不受影响）
- [ ] W11 Excel 完整导入导出中心（人员/报名/名单/统计，异步任务 + 文件下载）、组别停用约束、draft 清理任务
- [ ] W12 统计图表（Chart.js：单位/组别维度、通过率趋势）、性能压测报名截止场景（500 并发）、安全自查清单（越权用例库回归）、staging 上线演练

## 贯穿事项

1. 每周合并前：`pytest`（后端 service 层覆盖率 ≥ 80%，重点 rbac/registration/awards）+ 状态机用例与 03 文档逐条对应。
2. 文档即代码：状态枚举、permission code、错误码三处常量单一来源（后端 `core/constants.py`），文档变更走 PR 评审。
3. 明确不做清单（防范围蔓延）：动态表单、支付、短信、评分、赛程——出现在任何 PR 描述里先拒绝。
4. P1 backlog（里程碑 2 后评审）：动态表单引擎、列加密复核、audit 分区、competition_admins 表合并、导出中心、限流精细化。
