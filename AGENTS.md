# 协作要求

适用于仓库全目录，AI 与开发人员共同遵守。

1. 修改代码前阅读 [CODING_STANDARDS.md](CODING_STANDARDS.md)；修改界面、样式或交互前同时阅读 [FRONTEND_DESIGN_GUIDELINES.md](FRONTEND_DESIGN_GUIDELINES.md)。
2. 业务变更按需读取 [文档索引](docs/README.md)：需求看 01，权限看 02，状态看 03，数据看 04，架构看 05，接口看 06，交付范围看 07；日志变更看 [DEVELOPMENT.md](DEVELOPMENT.md)。
3. 当前前后端均为占位，规范中的组件、工具链与命令是初始化目标。执行前确认文件和配置存在，报告实际验证结果。
4. 优先最小可用改动并复用现有实现；保留无关工作，不扩大重构范围。权限、状态、错误码和 schema 变化同步相应文档。
5. 文档冲突先核对 [审阅待办](docs/10-review-notes.md)，明确规则后同步修改；涉及权限边界、个人信息或交付范围的未决项，先向负责人确认。
6. 按改动完成检查；交付说明改了什么、验证结果及剩余问题。提交与 PR 遵循 [CONTRIBUTING.md](CONTRIBUTING.md)。

每条规则只在所属文档维护；本文仅保留阅读入口与协作流程。
