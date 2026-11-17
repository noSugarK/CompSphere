# compsphere-web（前端占位）

**技术栈**：Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router + Axios + vue-i18n。结构约定见 [`../docs/05-architecture.md`](../docs/05-architecture.md) §4。

正式前端当前为**占位**，尚未初始化。独立界面设计预览见 [prototype/README.md](prototype/README.md)，运行 `node frontend/prototype/server.mjs` 后打开 <http://127.0.0.1:4173>；原型不连接真实业务，可单独发布 GitHub Pages。后续 `src/` 构建正式 Vue 应用并接入 Django API，部署方式见 [部署指南](../docker/README.md)，演示继续保留且不参与正式构建。

初始化正式工程时保留 prototype 目录。初始化前先将本说明临时移出目录，避免 Vite 对非空目录的覆盖提示；完成后恢复说明并保留生成的脚本信息。使用 npm，与现有 Dockerfile 保持一致：

```bash
npm create vite@latest . -- --template vue-ts
npm i element-plus pinia vue-router axios vue-i18n
npm i -D unplugin-auto-import unplugin-vue-components   # Element Plus 按需引入
```

目标结构：

```
frontend/
├── src/
│   ├── api/          # 各域 API 模块（禁止裸 axios 出 axios 实例文件）
│   ├── stores/       # auth(token+grants) / app(locale+theme) / notifications
│   ├── locales/      # zh-CN.ts / en-US.ts
│   ├── router/       # 动态权限路由守卫
│   ├── layouts/      # PortalLayout / AdminLayout / BlankLayout
│   ├── views/        # public / participant / admin
│   ├── components/   # ProTable、上传、审批时间线…
│   └── utils/        # perm.ts(hasPerm)、download.ts、format.ts
├── .env.development  # VITE_API_BASE=http://localhost:8000/api/v1
└── 构建入口见 ../docker/frontend.Dockerfile
```

编码遵循 [CODING_STANDARDS.md](../CODING_STANDARDS.md)，界面遵循 [FRONTEND_DESIGN_GUIDELINES.md](../FRONTEND_DESIGN_GUIDELINES.md)。

## 开发约束提醒

- 按钮/菜单权限仅是 UX；一切以接口返回为准，安全边界在后端（docs/02 §5）。
- `v-perm="'approval:review_single'"` 指令统一控制，不散写 if。
- 错误码提示文案集中在 `utils/errors.ts` 映射（docs/06 §1.2 段位）。
