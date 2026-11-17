# compsphere-server（后端占位）

**技术栈**：Django 5 + Django REST Framework + Celery + psycopg。详细架构见 [`../docs/05-architecture.md`](../docs/05-architecture.md)，模块划分见其中 §2。

本目录当前为**占位**，尚未初始化代码。初始化时按以下结构搭建：

```
backend/
├── config/                 # settings(env 分层)、urls、celery.py、wsgi/asgi
├── apps/
│   ├── accounts/  profiles/  orgs/  rbac/  teams/
│   ├── competitions/  events/  groups/  registrations/
│   ├── awards/  certificates/  notifications/  stats/  audit/
├── core/                   # 响应包裹、StateMachine、ScopedRolePermission、软删除 mixin、幂等
├── scripts/                # seed：roles/permissions；一致性检查任务
├── manage.py
├── requirements.txt        # 与现有 Dockerfile 依赖入口一致
├── pyproject.toml          # Ruff、mypy、pytest 等配置
└── Dockerfile 入口见 ../docker/backend.Dockerfile
```

## 初始化命令（未来执行）

```bash
python -m venv .venv
# 激活：Windows PowerShell 用 .\.venv\Scripts\Activate.ps1；POSIX 用 source .venv/bin/activate
# 先创建并锁定 requirements.txt，再安装；当前文件尚不存在
python -m pip install -r requirements.txt
django-admin startproject config .
# 为各 app 创建目标目录后初始化，例：
mkdir apps
mkdir apps/rbac
python manage.py startapp rbac apps/rbac
```

> startproject 只生成单文件 settings，后续按 05 文档拆为 config/settings/；在 apps/rbac/apps.py 中设置 name="apps.rbac" 并注册。

## 开发约束提醒

- 状态迁移必须走 `core.StateMachine.transition()`，禁止直接 update `status`（docs/03）。
- 权限检查必须走 `ScopedRolePermission`，禁止视图内手写角色字符串（docs/02 §5）。
- 常量单一来源：`core/constants.py` 的状态枚举 / permission code / 错误码与 docs 同步变更。
