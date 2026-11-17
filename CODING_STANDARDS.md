# 编码规范

适用于全部源码；提交与评审见 [CONTRIBUTING.md](CONTRIBUTING.md)，视觉与交互见 [前端设计规范](FRONTEND_DESIGN_GUIDELINES.md)。工具配置落地后作为格式细节的执行依据，变更配置时同步本文。

## 1. 格式与命名

- 文件统一 UTF-8、LF、末尾换行，清除行尾空白；基础设置见 .editorconfig 与 .gitattributes。
- Python：4 空格缩进、行宽 88，由 Ruff 格式化；模块/函数/变量用 `snake_case`，类用 `PascalCase`，常量用 `UPPER_SNAKE_CASE`。
- Vue/TypeScript/CSS/JSON：2 空格缩进；Prettier 统一单引号、分号与行宽 100。Vue 组件文件用多单词 `PascalCase.vue`，函数/变量用 `camelCase`，类型用 `PascalCase`。
- 布尔值用 `is`/`has` 等含义明确的前缀；时间字段用 `_at`，日期用 `_date`。接口字段保留后端命名，避免逐层转换。
- 注释解释原因；权限、状态迁移和幂等函数说明前置条件与副作用。优先现有实现和标准库，按真实重复提取公共逻辑。

## 2. 后端

- 分层：views 处理 HTTP 与权限声明，serializers 校验输入/塑形，services 承载业务与事务，models 承载存储约束；跨 app 写操作调用对方 service。
- 权限统一走 `ScopedRolePermission`，同时校验对象归属与查询范围；状态变更走 `transition()`。这些组件在初始化阶段实现，当前尚不存在。
- 状态、权限码、错误码集中在 `core/constants.py`；分别与 `docs/02`、`03`、`06` 同步，角色为数据库配置。
- 一次业务动作一个短事务；并发唯一性由数据库约束兜底。Celery 派发放在事务提交后，任务可重试且幂等。
- 列表分页（每页最多 100 条）；关联查询使用 `select_related`/`prefetch_related`，避免循环查询。
- 业务异常交给统一处理器；错误提示给出可执行的下一步并支持 zh-CN / en-US，错误码与参数保持稳定。敏感信息、SQL 和堆栈只按 [日志规范](DEVELOPMENT.md#2-日志与可观测性) 处理。
- schema 按 `docs/04` 显式设置表名、索引和约束；迁移人工检查数据影响。时间存 UTC，展示 Asia/Shanghai。

## 3. 前端

- Vue 3 Composition API + TypeScript 的 script setup；使用 npm，并提交 `package-lock.json`，与现有 Dockerfile 保持一致。
- API 请求集中在 `src/api/`，共用 Axios 实例处理认证、刷新和错误；组件调用领域 API 函数。
- 接口类型从 drf-spectacular 导出的 OpenAPI 生成；外部未知数据用 `unknown` 并校验，避免 `any` 和用非空断言掩盖缺失值。
- 局部状态留组件，跨页面共享状态才进 Pinia；菜单、路由与按钮按 grants 渲染，安全校验由后端执行。
- 用户可见文案放 src/locales/，使用 vue-i18n 的业务域翻译键；同步 Element Plus 语言包。保留用户填写的原文，禁止拼接翻译句子或以服务器中文 message 作为唯一显示来源。
- 业务样式使用语义令牌；Element Plus 主题映射集中在 `src/styles/`，细则见前端设计规范。

## 4. 验证与交付

- 初始化时落地 Ruff、mypy、pytest/pytest-django、ESLint、Prettier、vue-tsc，以及对应 pre-commit/CI 配置；当前仓库尚无这些配置。
- 修改业务逻辑补有意义的测试，优先覆盖越权、状态迁移、并发重复提交、敏感字段与任务重试；核心 service 层覆盖率目标 ≥ 80%。
- 按改动运行格式、静态检查、测试与构建；记录实际结果及未验证项。文档改动检查链接与跨文档一致性即可。
- 环境变量只提交 `.env.example`；密钥、个人信息样本与生成物不入仓。接口、依赖、业务规则变化同步相应文档。
