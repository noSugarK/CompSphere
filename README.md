# 竞云 CompSphere

面向学校、企业和赛事主办方的竞赛组织与报名管理平台。

核心流程：单位入驻 → 赛事配置 → 报名与审核 → 名单公示 → 获奖名单 → 证书发放。

**当前状态：设计阶段。** `backend/`、`frontend/` 仅有占位说明，Docker 配置为部署草案，尚不能启动完整应用，尚无已配置的 CI 或业务测试；已有数据库设计约束回归。

规划技术栈：Django + DRF、PostgreSQL、Redis/Celery、MinIO；Vue 3 + TypeScript + Element Plus。

| 入口 | 内容 |
| --- | --- |
| [文档索引](docs/README.md) | 需求、权限、状态机、数据库、架构、API 与任务拆解 |
| [编码规范](CODING_STANDARDS.md) | 格式、命名、分层与验证 |
| [前端设计规范](FRONTEND_DESIGN_GUIDELINES.md) | 配色、排版、布局、交互与无障碍 |
| [协作要求](AGENTS.md) | AI 与开发人员的阅读和执行规则 |
| [开发指南](DEVELOPMENT.md) | 日志与可观测性 |
| [贡献指南](CONTRIBUTING.md) | 提交、分支与 PR |
| [审阅待办](docs/10-review-notes.md) | 当前设计缺口与后续处理建议 |

数据库约束回归：设置 PostgreSQL 测试库的 PGHOST/PGPORT/PGUSER/PGDATABASE 后运行 `node scripts/check-schema.mjs`，要求 Node 与 psql；仅使用隔离测试库，执行后回滚。

初始化从 [W1 任务包](docs/07-task-breakdown.md#w1-基础设施--账号) 开始；部署前阅读 [部署指南](docker/README.md)。
