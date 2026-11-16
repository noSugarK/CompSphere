# compsphere-web（前端占位）

**技术栈**：Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router + Axios。结构约定见 [`../docs/05-architecture.md`](../docs/05-architecture.md) §4。

本目录当前为**占位**，尚未初始化代码。初始化：

```bash
npm create vite@latest . -- --template vue-ts
npm i element-plus pinia vue-router axios
npm i -D unplugin-auto-import unplugin-vue-components   # Element Plus 按需引入
```

目标结构：

```
frontend/
├── src/
│   ├── api/          # 各域 API 模块（禁止裸 axios 出 axios 实例文件）
│   ├── stores/       # auth(token+grants) / app / notifications
│   ├── router/       # 动态权限路由守卫
│   ├── layouts/      # AdminLayout / BlankLayout
│   ├── views/        # public / participant / admin
│   ├── components/   # ProTable、上传、审批时间线…
│   └── utils/        # perm.ts(hasPerm)、download.ts、format.ts
├── .env.development  # VITE_API_BASE=http://localhost:8000/api/v1
└── 构建入口见 ../docker/frontend.Dockerfile
```

## 开发约束提醒

- 按钮/菜单权限仅是 UX；一切以接口返回为准，安全边界在后端（docs/02 §5）。
- `v-perm="'approval:review_single'"` 指令统一控制，不散写 if。
- 错误码提示文案集中在 `utils/errors.ts` 映射（docs/06 §1.2 段位）。
