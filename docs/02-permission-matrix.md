# 02 权限矩阵与 RBAC 作用域模型

**版本**：v1.6（2026-11-17）。本文档是后端 `permissions` / `roles` / `user_roles` 三表与 DRF Permission 类实现的唯一依据，开发前先对齐此表。

v1.4：补代建与证件审核、未审取消、关闭历史权限；赛事管理角色仅平台分配。

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
| `global` | — | 平台超级管理员全局生效；普通用户的本人操作使用 participant 基础授予，并强制对象归属检查 |
| `org` | `organizations.id` | 在该单位及其**全部子孙单位**内生效 |
| `competition` | `competitions.id` | 在该赛事的所有届次内生效 |
| `edition` | `competition_editions.id` | 仅在该届次内生效 |

**赛项不是第五种作用域（v1.1）**：`event:*` 与 `roster:publish` 一律在 `edition` 作用域判定，赛项只是届次下的配置对象。理由：作用域每加一层，`resolve_scope()` 的继承组合与测试矩阵都翻倍，而"同一届次内按赛项分派不同审核人"在当前需求中没有实例。若后续出现（例如 V5RC 与 VIQRC 由不同裁判组负责），扩展点是 `user_roles` 增加 `scope_type='event'`，届次级授予向下兼容，不影响已有数据。

**继承规则**（只向下继承，共三条，实现时集中在一个 `resolve_scope()` 函数里）：

1. 全局平台管理权限可覆盖所有作用域；普通用户的 `read_own/update_own` 等本人权限仍须校验对象归属。单位树与赛事是两条独立授权链，主办/承办/协办关系不传递管理权限。
2. `org` 作用域覆盖该组织的下级组织树（大学管理员可管学院），但**不**跨树。
3. `competition` 授予覆盖该赛事的全部 `edition`；届次授予不向上授权。创建赛事仅检查平台级 `competition:create`，创建后由平台指定赛事管理员，不要求尚不存在的赛事 scope。

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
| `user` | `create` `read` `update` `disable` `import` `export` `assign_role` `provision` `reset_student_password` |
| `profile` | `read_own` `update_own` `read` `update` `review` `request_identity_change` `review_identity_change` |
| `org` | `create` `read` `update` `disable` `manage_members` `approve_join` `apply_create` `review_create` `request_transfer` `release_transfer` `accept_transfer` `mediate_transfer` |
| `team` | `create` `read` `update` `dissolve` `manage_members` `review` `read_review_history` `leave_own` `request_transfer` `review_transfer` |
| `competition` | `create` `read` `update` `publish` `archive` `manage_admins` `manage_units` |
| `edition` | `create` `read` `update` `publish` `close` `manage_team_access` |
| `group` | `create` `read` `update` `enable_disable` |
| `registration` | `create` `read_own` `read` `update` `withdraw` `cancel_review` `delete_draft` `export` `read_history` |
| `approval` | `review_single` `review_org` `review_final` `batch_review` `read_records` `reject_approved` |
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
| `team:read` | — | ✅(本单位，非单位子树) | ✅(own org 树) | — | — | ✅ |
| `team:create/update/manage_members` | — | — | ✅(own org 树，统一管理全部队伍) | — | — | ✅ |
| `team:leave_own/request_transfer` | ✅(本人) | — | — | — | — | ✅(本人) |
| `team:review_transfer` | — | — | — | — | — | ✅(非自审) |
| `team:dissolve` | — | — | ✅(own org 树) | — | — | ✅ |
| `profile:read/update/review` | — | ✅(read, 本人负责队伍成员) | ✅(own org 树) | — | — | ✅ |
| `user:create/read` | — | — | ✅(own org 树) | — | — | ✅ |
| `user:export`（全局人员明细） | — | — | — | — | — | ✅ |
| `user:disable` / `user:assign_role` | — | — | — | — | — | ✅ |
| `user:provision/reset_student_password` | — | — | ✅(当前有效主属单位的普通学生) | — | — | ✅ |
| `profile:request_identity_change` | ✅(本人) | ✅(本人) | ✅(本人/单位普通成员) | ✅(本人) | ✅(本人) | ✅ |
| `profile:review_identity_change` | — | — | ✅(本单位普通成员，非自审) | — | — | ✅(非自审) |
| `registration:read_history` | — | — | ✅(本单位历史) | ✅(scoped) | ✅(scoped) | ✅ |
| `registration:cancel_review` | ✅(本人提交) | ✅(本人代报) | — | — | — | ✅(本人提交) |
| `user:import` / `profile 导入` | — | — | ✅(own org 树) | — | — | ✅ |
| `org:request_transfer` | ✅(本人) | — | ✅(学生授权) | — | — | ✅ |
| `org:release_transfer/accept_transfer` | — | — | ✅(分别限原/新单位，非自审) | — | — | ✅(接收须有效目标范围) |
| `org:mediate_transfer` | — | — | — | — | — | ✅(核验代办转出) |
| `org:apply_create` | ✅(本人申请) | ✅ | ✅ | ✅ | ✅ | ✅ |
| `org:create`（后台发起申请）/ `org:review_create` | — | — | — | — | — | ✅ |
| `team:review` | — | — | ✅(所属单位树，非自审) | — | — | ✅(非自审) |
| `org:read` | — | ✅(own org 树) | ✅(own org 树) | ✅(赛事关联单位) | ✅(同左) | ✅ |
| `org:update/disable/manage_members/approve_join` | — | — | ✅(own org 树) | — | — | ✅ |
| `season:read`（公开非草稿） | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `team:review_create/review_season_registration` | — | — | — | — | — | ✅(非自审) |
| `team:request_season_registration` | — | — | ✅(own org 树) | — | — | ✅ |
| `season:set_current` | — | — | — | — | — | ✅ |
| `season:create/update/activate/archive` | — | — | — | — | — | ✅ |
| `competition:create` | — | — | — | — | — | ✅ |
| `competition:read` | ✅(公开部分) | ✅ | ✅(本单位参与的) | ✅(scoped) | ✅(scoped) | ✅ |
| `competition:manage_admins` | — | — | — | — | — | ✅ |
| `competition:update/publish/archive/manage_units` | — | — | — | ✅(scoped) | — | ✅ |
| `edition:create/read/update/publish/close` | ✅(read 公开) | ✅(read 公开) | ✅(read, 参与的) | ✅(scoped) | ✅(read, scoped) | ✅ |
| `edition:manage_team_access` | — | — | — | ✅(scoped) | — | ✅ |
| `team:read_review_history` | — | — | — | ✅(当前报名届次) | ✅(当前报名届次) | ✅ |
| `group:create/read/update/enable_disable` | ✅(read 公开) | ✅(read 公开) | ✅(read) | ✅(scoped) | ✅(read, scoped) | ✅ |
| `event:create/read/update/enable_disable` | ✅(read 公开) | ✅(read 公开) | ✅(read) | ✅(scoped) | ✅(read, scoped) | ✅ |
| `registration:read/batch…` 见下注 | — | — | 部分 | ✅(scoped) | ✅(scoped) | ✅ |
| `registration:export`（报名明细） | — | — | — | ✅(scoped) | — | ✅ |
| `approval:reject_approved` | — | — | — | ✅(scoped) | ✅(scoped) | ✅ |
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

1. **管理角色分配仅平台管理员**：平台管理员可在有效目标作用域分配非平台角色；分配 `platform_admin` 仅现有超管可操作。创建账号时只自动分配受对象归属约束的 participant 基础角色，不开放客户端自选角色/作用域。
2. **作用域内用户可见性**：`org_admin` 的"own org 树"成员范围 = `organization_members` 中 org ∈ 自身子树且 left_at IS NULL。教练只读其有效所属单位的队伍概要，不随单位树向下扩展，也不读其他单位；教练只可代报本单位内 teams.coach_id = self 的队伍，不可创建队伍或修改正式队伍资料/成员，普通查看不开放其他队伍报名、敏感人员或附件。单位管理员统一管理其单位范围内全部队伍，管理变更仍须按申请流程批准。本人自主退队是例外；单位管理员不可绕过同赛季同赛项学生绑定，跨队特批仅平台管理员。本人回上次退出队伍走普通入队审核，不需要特批但仍核对所有有效绑定。
3. **驳回/退回后的编辑权**：报名被驳回或退回后，仅报名提交人本人（或团队报名的队长/教练，代报场景）可编辑重提，`org_admin` 只能查看不能代改。
4. **审核回避**：单位创建与队伍资料申请强制禁止申请人自审；队伍创建与赛季激活仅平台审核；资料/成员修改由其他有权单位管理员或平台处理。参赛学生不配置审核职责；为防角色误配，报名审核仍禁止本轮参赛成员及提交人审核自己的报名。participant 基础角色人人可持有，不能用是否持有该角色判断真实队员身份；以本轮成员快照判定。
5. **公开接口无需登录**：赛事/届次/赛项/组别的展示字段、证书二维码验证页、通过名单公示页。以 `permission_classes=[AllowAny]` + serializer 白名单字段实现，禁止复用管理端 serializer。
   - v1.1 收紧：白名单必须是**代码里的常量集合**，不是"serializer 上不声明就是私有"的默认排除。证件绑定后该字段在 `user_profiles` / `registration_members.snapshot_enc` 中都存在，任何人复用一个管理类 serializer 对外就会带出证件号；因此公开字段只允许从 `registration_members.public_info` 与届次/赛项/组别三张配置表读取，**不得**触及 `snapshot_enc`、`user_profiles.document_*`、`users.phone`。
6. **自定义角色**：`platform_admin` 可新建角色并勾选 permission 子集；内置 6 角色不可删除（`is_builtin` 标志），改权限需二次确认；平台级创建赛事、禁用账号、分配角色等权限只允许 platform_admin，全局本人角色不得扩为管理角色。
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

照片规则：本人可上传/替换/删除自己的证件照；其他人仅在具有 profile:read 且人员作用域匹配时读取，不能代改照片。read_own 的队友可见性不包含照片；公开名单和证书验证页不返回照片或对象 key。语言与主题偏好仅本人可改，不影响角色权限。

team:review 仅处理资料/成员变更，不包含创建与赛季激活。队伍资料审核人可凭 team:review 在本单位树内读取申请提案、版本差异及该队最小历史摘要；平台可代审。赛事 reviewer 不因此获得队伍资料变更的审批权。

赛事审核历史上下文：team:read_review_history 必须绑定本届已提交的 registration_id，再从该报名解析 team_id；还须具备该报名的 registration:read 与对应 approval:review_*。只返回该队其他届次的最小历史摘要（01 §3.6），不向上继承其他届次的读写权限，不接受任意 team_id 枚举、不导出全量历史。未授权或只有草稿的上下文返回 404，每次查询写审计。队号、赛项与归属不可通过普通资料修改迁移，历史按稳定 team_id 关联，队伍不能另建同名记录冒用历史。

单位管理员交接：由平台撤销旧 org_admin 授予并分配新管理员，权限按实时 grants/缓存失效立即更新，留存授权审计，不另建离职档案。人员退出单位后不再获得当前单位成员权限；历史报名按提交时的单位归属过滤，不随人员当前单位迁移。

关闭可见性：closed 届次仅管理历史入口可读，须 registration:read_history 并逐行按原届次/本单位范围过滤；read_own/公开 read 不能读取关闭后的业务历史。公开证书验证是独立最小结果接口，不继承赛事历史读取权。

证件与代建：profile:update/update_own 不允许直接修改已绑定证件；必须 request_identity_change → review_identity_change。审核者不能为申请人或证件所属人，单位管理者仅审核本单位普通账户，管理账号及跨单位争议由平台处理。单位重置限当前有效主属单位范围内的普通学生，不限制创建来源或邮箱绑定；次属单位、历史成员单位和原代建单位不能据旧关系重置。交接完成即切换权限，重置必须锁学生并核对 affiliation_version，防并发转移后的旧单位操作；已有账号加入新主属单位必须走授权交接，普通成员添加/导入不得绕过。赛事管理员分配/移除统一走平台授权接口，不能借 manage_admins 绕过 user:assign_role。

## 5. 前后端落地约定

- 后端：自研 `ScopedRolePermission`（当前不引入第三方策略引擎，参考入口见 09 文档 §2），viewset 声明 `required_perm` + scope 解析函数；禁止在 view 里手写角色字符串判断。
- 前端：登录后拉取当前用户的全部 grants（`GET /api/v1/me` 的 `grants` 字段），Pinia 存 `hasPerm(perm, scopeObj?)`；菜单/按钮级控制仅 UX，不作为安全边界——所有接口仍需后端校验。
- 矩阵变更流程：改本文件 → 同步 `permissions` seed → 评审 → 迁移。本文件与代码不一致时，以本文件为准修代码。
