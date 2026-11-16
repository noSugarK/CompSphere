# 02 权限矩阵与 RBAC 作用域模型

**版本**：v1.1（2026-11-16）。本文档是后端 `permissions` / `roles` / `user_roles` 三表与 DRF Permission 类实现的唯一依据，开发前先对齐此表。

v1.1 变更：新增 `roster:publish` 权限与 §4.7 公示可见性判定；落实「身份证必填」后修正 §4.5 公开序列器的字段口径；`drf-access` 引用修正。

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

**赛项不是第五种作用域（v1.1）**：`event:*` 与 `roster:publish` 一律在 `edition` 作用域判定，赛项只是届次下的配置对象。理由：作用域每加一层，`resolve_scope()` 的继承组合与测试矩阵都翻倍，而"同一届次内按赛项分派不同审核人"在当前需求中没有实例。若后续出现（例如 V5RC 与 VIQRC 由不同裁判组负责），扩展点是 `user_roles` 增加 `scope_type='event'`，届次级授予向下兼容，不影响已有数据。已记入 01 §9 待决。

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
| `roster` | `publish` `unpublish`（v1.1 新增，控制通过名单对外公示，见 §4.7） |
| `event` | `create` `read` `update` `enable_disable`（v1.1 新增，赛项管理，与 `group` 对称） |
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
| `event:create/read/update/enable_disable` | ✅(read 公开) | ✅(read 公开) | ✅(read) | ✅(scoped) | ✅(read, scoped) | ✅ |
| `registration:read/batch…` 见下注 | — | — | 部分 | ✅(scoped) | ✅(scoped) | ✅ |
| `registration:export` | — | — | ✅(本单位统计向) | ✅(scoped) | — | ✅ |
| `approval:review_single` | — | — | — | ✅(scoped) | ✅(scoped) | ✅ |
| `approval:review_org`（两级审核的初审） | — | — | ✅(own org 树成员报名) | ✅(scoped) | — | ✅ |
| `approval:review_final`（两级审核的复审） | — | — | — | ✅(scoped) | ✅(scoped, 若配置) | ✅ |
| `approval:batch_review` / `read_records` | — | — | ✅(own 初审范围) | ✅(scoped) | ✅(scoped) | ✅ |
| `roster:publish` / `unpublish`（v1.1） | — | — | — | ✅(scoped) | — | ✅ |
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
5. **公开接口无需登录**：赛事/届次/赛项/组别的展示字段、证书二维码验证页、通过名单公示页。以 `permission_classes=[AllowAny]` + serializer 白名单字段实现，禁止复用管理端 serializer。
   - v1.1 收紧：白名单必须是**代码里的常量集合**，不是"serializer 上不声明就是私有"的默认排除。身份证必填后该字段在 `user_profiles` / `registration_members.snapshot` 中都存在，任何人复用一个管理类 serializer 对外就会带出证件号；因此公开字段只允许从 `registration_members.public_info` 与届次/赛项/组别三张配置表读取，**不得**触及 `snapshot`、`user_profiles.id_number_*`、`users.phone`。
6. **自定义角色**：`platform_admin` 可新建角色并勾选 permission 子集；内置 6 角色不可删除（`is_builtin` 标志），可改权限但会全量影响持有者（界面二次确认）。
7. **通过名单公示的可见性判定（v1.1 新增）**：公开页每次请求按固定顺序判定，顺序不可调换。

   ```
   1) edition.status == 'published' 且 roster_published_at IS NOT NULL
        否 → 404（不是 403：未发布的公示页与不存在的页对外表现一致，避免暴露届次进度）
   2) roster_publication == 'none'  → 404（同上理由）
   3) roster_publication == 'login' → 要求已登录；未登录返回 401 + 登录入口
   4) 输出字段 = 请求字段 ∩ roster_publish_fields ∩ 服务端 PUBLIC_ALLOWED 常量
        （两次交集，前端传什么都不生效；PUBLIC_ALLOWED 不含任何证件与联系方式字段）
   5) 仅输出 status == 'approved' 的报名；未通过与已撤回者不出现
   ```

   - **`login` 档的语义必须写明**：只校验"是否登录"，不校验"与本场赛事有无关系"。它挡住的是匿名爬取，挡不住任意注册用户读取。若主办方真正想要的是"只有相关方可看"，应选 `none` 并改用管理端导出，而不是 `login`。界面选项说明按此措辞。
   - 公示页为高频匿名访问，走独立限流路径（与证书验证页同批，05 §3.2 / 06 §1.3）。

## 5. 前后端落地约定

- 后端：自研 `ScopedRolePermission`（不使用第三方权限库，理由见 09 文档 §3.1），viewset 声明 `required_perm` + scope 解析函数；禁止在 view 里手写角色字符串判断。
- 前端：登录后拉取当前用户的全部 grants（`GET /api/v1/me/grants/`），Pinia 存 `hasPerm(perm, scopeObj?)`；菜单/按钮级控制仅 UX，不作为安全边界——所有接口仍需后端校验。
- 矩阵变更流程：改本文件 → 同步 `permissions` seed → 评审 → 迁移。本文件与代码不一致时，以本文件为准修代码。
