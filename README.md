# 竞云 CompSphere

面向学校、企业和赛事主办方的竞赛组织与报名管理平台。

核心流程：单位入驻 → 赛事配置 → 报名与审核 → 名单公示 → 获奖名单 → 证书发放。

首期集中部署，交付队伍基础、赛季许可、个人/团队报名、单级审核与公示，包含固定模板导入、自动备份和可验证的人工恢复；证书后续交付，无固定上线日期。完整范围与门槛见 [PRD](docs/01-PRD.md) 和 [任务拆解](docs/07-task-breakdown.md)。

**当前状态：首批正式核心链路可运行。** 已建立Django/DRF与Vue/Element Plus工程，打通认证、作用域权限、队伍提案/许可、报名草稿/提交和单级审核，包含严格JSON校验、迁移和测试。完整首期仍有未完成项，见前后端README；Docker、邮件/文件、自动备份及生产TLS尚待验收。独立静态演示与Pages发布继续保留，正式应用有单独CI配置。

规划技术栈：Django + DRF、PostgreSQL、Redis/Celery、MinIO；Vue 3 + TypeScript + Element Plus。

| 入口 | 内容 |
| --- | --- |
| [后端运行与检查](backend/README.md) / [前端运行与检查](frontend/README.md) | 本地启动、真实核心能力、验证命令及未完成任务 |
| [界面演示](frontend/prototype/README.md) | 本地体验、模拟账号与 GitHub Pages 发布方式；独立于正式前后端 |
| [文档索引](docs/README.md) | 需求、权限、状态机、数据库、架构、API 与任务拆解 |
| [编码规范](CODING_STANDARDS.md) | 格式、命名、分层与验证 |
| [前端设计规范](FRONTEND_DESIGN_GUIDELINES.md) | 配色、排版、布局、交互与无障碍 |
| [协作要求](AGENTS.md) | AI 与开发人员的阅读和执行规则 |
| [开发指南](DEVELOPMENT.md) | 日志与可观测性 |
| [贡献指南](CONTRIBUTING.md) | 提交、分支与 PR |
| [审阅待办](docs/10-review-notes.md) | 当前设计缺口与后续处理建议 |

数据库约束回归：设置 PostgreSQL 测试库的 PGHOST/PGPORT/PGUSER/PGDATABASE 后运行 `node scripts/check-schema.mjs`，要求 Node 与 psql；仅使用隔离测试库，执行后回滚。

初始化从 [W1 任务包](docs/07-task-breakdown.md#w1-基础设施--账号) 开始；部署前阅读 [部署指南](docker/README.md)。
