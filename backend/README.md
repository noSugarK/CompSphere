# compsphere-server（后端占位）

**技术栈**：Django 5 + Django REST Framework + Celery + psycopg。详细架构见 [`../docs/05-architecture.md`](../docs/05-architecture.md)，模块划分见其中 §2。

本目录当前为**占位**，尚未初始化代码。初始化时按以下结构搭建：

```
backend/
├── config/                 # settings(env 分层)、urls、celery.py、wsgi/asgi
├── apps/
│   ├── accounts/  profiles/  orgs/  rbac/  teams/
│   ├── competitions/  groups/  registrations/
│   ├── awards/  certificates/  notifications/  stats/  audit/
├── core/                   # 响应包裹、StateMachine、ScopedRolePermission、软删除 mixin、幂等
├── scripts/                # seed：roles/permissions；一致性检查任务
├── manage.py
├── pyproject.toml          # 或 requirements/（base/dev/prod 三件套）
└── Dockerfile 入口见 ../docker/backend.Dockerfile
```

## 初始化命令（未来执行）

```bash
django-admin startproject config .
python -m venv .venv && .venv/bin/pip install -r requirements/dev.txt
.venv/bin/python manage.py startapp --parent=apps rbac   # 等 13 个 app
```

## 开发约束提醒

- 状态迁移必须走 `core.StateMachine.transition()`，禁止直接 update `status`（docs/03）。
- 权限检查必须走 `ScopedRolePermission`，禁止视图内手写角色字符串（docs/02 §5）。
- 常量单一来源：`core/constants.py` 的状态枚举 / permission code / 错误码与 docs 同步变更。
