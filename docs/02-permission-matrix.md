# 02 权限矩阵与 RBAC 作用域模型

**版本**：v1.0（2026-11-16）。本文档是后端 `permissions` / `roles` / `user_roles` 三表与 DRF Permission 类实现的唯一依据，开发前先对齐此表。

---

## 1. 作用域模型

一条角色授予 = **（用户, 角色, 作用域）** 三元组：

```sql
user_roles (
  user_id, role_id,
  scope_type,   -- 'global' | 'org' | 'competition' | 'edition'
  scope_id      -- global 时为 NULL
)
```

作用域语义：

| scope_type | scope_id 指向 | 含义 |
| --- | --- | --- |
| `global` | — | 全平台生效（仅平台超级管理员使用） |
| `org` | `organizations.id` | 在该单位及其**全部子孙单位**内生效 |
| `competition` | `competitions.id` | 在该赛事的所有届次内生效 |
| `edition` | `competition_editions.id` | 仅在该届次内生效 |

**继承规则**（只向下继承，共三条，实现时集中在一个 `resolve_scope()` 函数里）：

1. `global` ⊇ `org` ⊇ `competition` ⊇ `edition`：持有上位作用域的授予即拥有下位作用域内该角色的全部权限（超管天然可管理任何赛事）。
2. `org` 作用域覆盖该组织的下级组织树（大学管理员可管学院），但**不**跨树。
3. 赛事与其届次的绑定通过 `competition_id` 外键解析，届次级权限检查时先解析到赛事再判断是否有 `competition` 级授予。

**权限检查伪代码**（后端所有 API 的统一入口逻辑）：

```
has_perm(user, perm_code, scope_type, scope_id):
    for grant in user.grants:
        if perm_code in grant.role.permissions:
            if grant.scope is compatible(scope_type, scope_id):  # 按继承规则 1/2/3
                return True
    return False
```

## 2. Permission 清单（代码常量，role.permissions 引用其 code）

命名规则 `{resource}:{action}`。第一版全量清单（约 60 项）：

| 资源 | actions |
| --- | --- |
| `user` | `create` `read` `update` `disable` `import` `export` `assign_role` |
| `profile` | `read_own` `update_own` `read` `update` `review` |
| `org` | `create` `read` `update` `disable` `manage_members` `approve_join` |
| `team` | `create` `read` `update` `dissolve` `manage_members` |
| `competition` | `create` `read` `update` `publish` `archive` `manage_admins` `manage_units` |
| `edition` | `create` `read` `update` `publish` `close` |
| `group` | `create` `read` `update` `enable_disable` |
| `registration` | `create` `read_own` `read` `update` `withdraw` `delete_draft` `export` |
| `approval` | `review_single` `review_org` `review_final` `batch_review` `read_records` |
| `award` | `config` `read` `import` `manage_roster` `submit_roster` `approve_roster` `lock_roster` |
| `certificate` | `generate` `issue` `revoke` `reissue` `read_own` `read` |
| `notice` | `publish` `read_own` |
| `stats` | `read_platform` `read_competition` `read_org` |
| `audit` | `read` |
| `system` | `manage_roles` `manage_settings` `backup` |

## 3. 角色 × 权限矩阵

✅ = 拥有；✅(scope) = 拥有但受作用域限制；— = 无。

| permission | participant | team_coach | org_admin | competition_admin | reviewer | platform_admin |
| --- | --- | --- | --- | --- | --- | --- |
| `profile:read_own/update_own` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `registration:create/read_own/update/withdraw/delete_draft` | ✅ | ✅(代本队) | — | — | — | ✅ |
| `team:create/read/update/manage_members` | — | ✅(own org) | ✅(own org 树) | — | — | ✅ |
| `team:dissolve` | — | — | ✅(own org 树) | — | — | ✅ |
| `profile:read/update/review` | — | ✅(read, own org 成员) | ✅(own org 树) | — | — | ✅ |
| `user:create/read/export` | — | — | ✅(own org 树) | — | — | ✅ |
| `user:disable` / `user:assign_role` | — | — | — | — | — | ✅ |
| `user:import` / `profile 导入` | — | — | ✅(own org 树) | — | — | ✅ |
| `org:create` | — | — | — | — | — | ✅ |
| `org:read` | — | ✅(own org 树) | ✅(own org 树) | ✅(赛事关联单位) | ✅(同左) | ✅ |
| `org:update/disable/manage_members/approve_join` | — | — | ✅(own org 树) | — | — | ✅ |
| `competition:create` | — | — | — | ✅ | — | ✅ |
| `competition:read` | ✅(公开部分) | ✅ | ✅(本单位参与的) | ✅(scoped) | ✅(scoped) | ✅ |
| `competition:update/publish/archive/manage_admins/manage_units` | — | — | — | ✅(scoped) | — | ✅ |
| `edition:create/read/update/publish/close` | ✅(read 公开) | ✅(read 公开) | ✅(read, 参与的) | ✅(scoped) | ✅(read, scoped) | ✅ |
| `group:create/read/update/enable_disable` | ✅(read 公开) | ✅(read 公开) | ✅(read) | ✅(scoped) | ✅(read, scoped) | ✅ |
| `registration:read/batch…` 见下注 | — | — | 部分 | ✅(scoped) | ✅(scoped) | ✅ |
| `registration:export` | — | — | ✅(本单位统计向) | ✅(scoped) | — | ✅ |
| `approval:review_single` | — | — | — | ✅(scoped) | ✅(scoped) | ✅ |
| `approval:review_org`（两级审核的初审） | — | — | ✅(own org 树成员报名) | ✅(scoped) | — | ✅ |
| `approval:review_final`（两级审核的复审） | — | — | — | ✅(scoped) | ✅(scoped, 若配置) | ✅ |
| `approval:batch_review` / `read_records` | — | — | ✅(own 初审范围) | ✅(scoped) | ✅(scoped) | ✅ |
| `award:config/manage_roster/submit_roster` | — | — | — | ✅(scoped) | — | ✅ |
| `award:import/approve_roster/lock_roster` | — | — | — | ✅(scoped) | — | ✅ |
| `award:read` | ✅(自己的) | ✅(本队) | ✅(本单位获奖名单) | ✅(scoped) | ✅(scoped) | ✅ |
| `certificate:generate/issue/revoke/reissue` | — | — | — | ✅(scoped) | — | ✅ |
| `certificate:read_own` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `notice:publish` | — | — | ✅(本单位可见通知) | ✅(scoped 赛事通知) | — | ✅ |
| `stats:read_platform` | — | — | — | — | — | ✅ |
| `stats:read_competition` | — | — | — | ✅(scoped) | ✅(scoped) | ✅ |
| `stats:read_org` | — | ✅(本队) | ✅(own org 树) | — | — | ✅ |
| `audit:read` | — | — | ✅(本单位相关) | ✅(本赛事相关) | — | ✅ |
| `system:manage_roles/manage_settings/backup` | — | — | — | — | — | ✅ |

下注：`registration:read`（查看他人报名详情）仅 `org_admin`（本单位初审理由）、`competition_admin`/`reviewer`（scoped）、`platform_admin` 拥有；普通用户只能 `read_own`。教练可读取**本队**报名的详情（不含他人材料附件）。

## 4. 特殊规则（实现时必须处理）

1. **自己不能授予比自己大的权限**：`user:assign_role` 要求授予者持有目标角色且在目标作用域内也有该角色；`platform_admin` 授予仅超管可操作。
2. **作用域内用户可见性**：`org_admin` 的"own org 树"成员范围 = `organization_members` 中 org ∈ 自身子树；教练仅能管理 `teams.coach_id = self` 或本 org 下队伍（第一版取宽松口径：本 org 树内队伍）。
3. **退回修改的编辑权**：报名被退回后，仅报名提交人本人（或团队报名的队长/教练，代报场景）可编辑重提，`org_admin` 只能查看不能代改。
4. **审核回避**：第一版不做自动回避，审核人可审到自己作为成员的报名属已知接受项；日志必须完整。
5. **公开接口无需登录**：赛事/届次/组别的展示字段、证书二维码验证页。以 `permission_classes=[AllowAny]` + serializer 白名单字段实现，禁止复用管理端 serializer。
6. **自定义角色**：`platform_admin` 可新建角色并勾选 permission 子集；内置 6 角色不可删除（`is_builtin` 标志），可改权限但会全量影响持有者（界面二次确认）。

## 5. 前后端落地约定

- 后端：`drf-access` 或自研 `ScopedRolePermission`，viewset 声明 `required_perm` + scope 解析函数；禁止在 view 里手写角色字符串判断。
- 前端：登录后拉取当前用户的全部 grants（`GET /api/v1/me/grants/`），Pinia 存 `hasPerm(perm, scopeObj?)`；菜单/按钮级控制仅 UX，不作为安全边界——所有接口仍需后端校验。
- 矩阵变更流程：改本文件 → 同步 `permissions` seed → 评审 → 迁移。本文件与代码不一致时，以本文件为准修代码。
