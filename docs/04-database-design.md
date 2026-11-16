# 04 数据库设计（字段级 DDL）

**版本**：v1.1（2026-11-16）。目标库 PostgreSQL 16，Django 5 迁移生成前的目标 schema。

v1.1 变更（对齐产品确认）：新增赛项维度 `competition_events` 与开放组合 `competition_offerings`，赛项与组别并列，报名/奖项/名单以「届次×赛项×组别」为单位；组别改为学段（ES/MS/HS/U）并移除专业限制；身份证号由「按需收集」改为参赛者必填且 P0 列加密；注册主键改邮箱验证码，新增 `verification_codes`；新增届次级名单公示开关；组织树改 treebeard 物化路径；证书编号引入独立计数器。

约定：
- 所有表含 `id BIGSERIAL PRIMARY KEY`、`created_at TIMESTAMPTZ NOT NULL DEFAULT now()`、`updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`、`is_deleted BOOLEAN NOT NULL DEFAULT FALSE`（软删除，见 PRD §4.3）。
- 金额用 `NUMERIC(10,2)`；时间一律 `TIMESTAMPTZ`（UTC）。
- 外键删除策略：主数据 restrict，关系表 cascade。
- Django 层面用 `uuid7`/snowflake 可选；第一版主键用自增 + 对外暴露 `public_code`（业务流水号）避免遍历。

---

## 1. ER 总览

```
users ── user_profiles
  │        organization_members ── organizations(物化路径树)
  └─ user_roles ── roles ── role_permissions ── permissions
teams ── team_members ── users
competitions ── competition_organizations ── organizations
  ├─ competition_admins ── users
  └─ competition_editions
        ├─ competition_events（赛项：VURC / V5RC / VIQRC / VAIMRC / VGORC）
        ├─ competition_groups（组别：ES / MS / HS / U）
        ├─ competition_offerings（届次开放组合：event × group）
        ├─ registrations ── registration_members / registration_files
        │                     └─ approval_records
        ├─ awards ── award_rosters / award_records ── certificates
        └─ notices
audit_logs（独立）
```

**赛项与组别是并列两个维度**（v1.1 调整）。一条报名 = 一个赛项 + 一个组别，例如「V5RC × 高中组」。二者不可自由组合：VURC 仅设大学组、VEX GO 仅设小学组，因此引入 `competition_offerings` 声明本届实际开放的组合，报名校验、奖项配置、获奖名单、公示名单全部以「届次 × 赛项 × 组别」为单位。

## 2. 用户与组织

```sql
CREATE TABLE users (
  id            BIGSERIAL PRIMARY KEY,
  username      VARCHAR(64) UNIQUE NOT NULL,
  email         VARCHAR(255) UNIQUE NOT NULL,        -- 注册主键，必须已验证
  email_verified_at TIMESTAMPTZ,                     -- 未验证不得提交报名（服务层校验）
  phone         VARCHAR(20) UNIQUE,                  -- 必填联系字段，不验证真伪（短信 P2）
  phone_verified_at TIMESTAMPTZ,                     -- 第一版恒为 NULL，预留
  password_hash VARCHAR(255) NOT NULL,               -- Argon2
  status        VARCHAR(16) NOT NULL DEFAULT 'pending',  -- active|disabled|pending
  last_login_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted    BOOLEAN NOT NULL DEFAULT FALSE
);

-- 邮箱验证码：一次性、限频、试错次数受限。手机号通道预留但第一版不启用。
CREATE TABLE verification_codes (
  id          BIGSERIAL PRIMARY KEY,
  channel     VARCHAR(16) NOT NULL,                  -- email（第一版仅此值）| sms（预留）
  target      VARCHAR(255) NOT NULL,                 -- 邮箱或手机号
  code_hash   VARCHAR(255) NOT NULL,                 -- 不存明文验证码
  purpose     VARCHAR(24) NOT NULL,                  -- register|reset_password|change_email
  expires_at  TIMESTAMPTZ NOT NULL,                  -- 默认 10 分钟
  attempts    INT NOT NULL DEFAULT 0,                -- 超过 5 次作废
  consumed_at TIMESTAMPTZ,
  client_ip   INET,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_vcode_lookup ON verification_codes(channel, target, purpose, consumed_at);

CREATE TABLE user_profiles (
  id            BIGSERIAL PRIMARY KEY,
  user_id       BIGINT UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  real_name     VARCHAR(64) NOT NULL,
  gender        VARCHAR(10),                         -- male|female|other|unknown
  avatar_url    VARCHAR(512),
  birth_date    DATE,
  id_number_enc BYTEA NOT NULL,                      -- 身份证号密文：参赛者必填（v1.1 由按需收集改为强制）
  id_number_hash VARCHAR(64) NOT NULL,               -- SHA-256(pepper)，跨表匹配与防重复报名唯一依据
  id_number_last4 VARCHAR(4),                        -- 冗余末四位，供人工核对与界面显示，不含完整号码
  student_no    VARCHAR(64),                         -- 学号
  staff_no      VARCHAR(64),                         -- 工号
  person_type   VARCHAR(16) NOT NULL DEFAULT 'participant',  -- participant|coach|staff
  school_level  VARCHAR(8),                          -- ES|MS|HS|U（组别资格校验依据，见 §4）
  grade         VARCHAR(32),                         -- 年级标签，如 '高一' / '大一'
  major         VARCHAR(128),                        -- 保留字段，不再作为报名限制条件（v1.1）
  title         VARCHAR(64),                         -- 职务/职称
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted    BOOLEAN NOT NULL DEFAULT FALSE
);
-- 同一身份证只对应一个账号，杜绝一人多号重复报名。
-- 软删除账号的哈希仍占用（列加密后无法用明文 UNIQUE，故用哈希做部分唯一索引）。
CREATE UNIQUE INDEX uniq_profile_id_number ON user_profiles(id_number_hash) WHERE NOT is_deleted;

CREATE TABLE organizations (
  id          BIGSERIAL PRIMARY KEY,
  code        VARCHAR(32) UNIQUE NOT NULL,      -- 单位编码
  name        VARCHAR(128) NOT NULL,
  org_type    VARCHAR(16) NOT NULL,             -- school|college|enterprise|association|host|organizer|other
  -- 树结构：django-treebeard Materialized Path（v1.1 取代裸 parent_id）
  -- path 为定长编码串，取某单位全部子孙 = path LIKE '00010002%' 单条索引扫描，
  -- 而裸 parent_id 需递归 CTE；权限解析（02 §4.2）每请求都跑子树查询，故必须走物化路径。
  -- 不保留 parent_id 列：父级由 path 截断得出（get_parent()）。双写父指针会与本表
  -- competition_admins 犯同一个错（见 §8.5 技术债），treebeard 的 move() 只更新 path。
  path        VARCHAR(255) NOT NULL,         -- treebeard MP_Node: CharField(max_length=255, unique=True)，steplen=4，故最多 63 层
  depth       INTEGER NOT NULL,              -- PositiveIntegerField，无默认值：由 path 长度推导，插入时必须显式写
  numchild    INTEGER NOT NULL DEFAULT 0,    -- PositiveIntegerField(default=0)
  status      VARCHAR(16) NOT NULL DEFAULT 'active',   -- active|suspended
  join_request_status VARCHAR(16) DEFAULT 'approved',  -- pending|approved|rejected（入驻申请）
  logo_url    VARCHAR(512),
  contact_info JSONB,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE UNIQUE INDEX uniq_org_path ON organizations(path);
-- 子树查询前缀匹配必须用 text_pattern_ops，否则 B-tree 不支持 LIKE 'x%'
CREATE INDEX idx_org_path_prefix ON organizations(path varchar_pattern_ops);
-- Django PositiveIntegerField 在 PostgreSQL 会生成非负 CHECK，列出以保持 DDL 与 makemigrations 一致
ALTER TABLE organizations ADD CONSTRAINT org_depth_nonneg CHECK (depth >= 0);
ALTER TABLE organizations ADD CONSTRAINT org_numchild_nonneg CHECK (numchild >= 0);

CREATE TABLE organization_members (
  id           BIGSERIAL PRIMARY KEY,
  org_id       BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  member_role  VARCHAR(16) NOT NULL DEFAULT 'member',   -- member|student|teacher|employee|external
  is_primary   BOOLEAN NOT NULL DEFAULT FALSE,          -- 主属单位（唯一部分索引）
  joined_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  left_at      TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (org_id, user_id)
);
CREATE UNIQUE INDEX idx_org_member_primary
  ON organization_members(user_id) WHERE is_primary AND left_at IS NULL;

CREATE TABLE roles (
  id          BIGSERIAL PRIMARY KEY,
  code        VARCHAR(32) UNIQUE NOT NULL,      -- participant|team_coach|org_admin|competition_admin|reviewer|platform_admin|自定义
  name        VARCHAR(64) NOT NULL,
  is_builtin  BOOLEAN NOT NULL DEFAULT FALSE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE permissions (
  id          BIGSERIAL PRIMARY KEY,
  code        VARCHAR(64) UNIQUE NOT NULL,      -- 'registration:read' …（02 文档 §2）
  name        VARCHAR(64) NOT NULL,
  resource    VARCHAR(32) NOT NULL,
  action      VARCHAR(32) NOT NULL
);

CREATE TABLE role_permissions (
  role_id       BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  permission_id BIGINT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
  PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE user_roles (
  id         BIGSERIAL PRIMARY KEY,
  user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role_id    BIGINT NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
  scope_type VARCHAR(16) NOT NULL,              -- global|org|competition|edition
  scope_id   BIGINT,                            -- global 时 NULL
  granted_by BIGINT REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, role_id, scope_type, scope_id),
  CHECK ((scope_type = 'global' AND scope_id IS NULL) OR (scope_type <> 'global' AND scope_id IS NOT NULL))
);
CREATE INDEX idx_user_roles_user ON user_roles(user_id);
-- scope_id 不做跨表外键（多态），完整性由服务层 + 定期一致性任务保证
```

## 3. 队伍

```sql
CREATE TABLE teams (
  id          BIGSERIAL PRIMARY KEY,
  code        VARCHAR(32) UNIQUE NOT NULL,
  name        VARCHAR(128) NOT NULL,
  org_id      BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  coach_id    BIGINT REFERENCES users(id) ON DELETE SET NULL,
  captain_id  BIGINT REFERENCES users(id) ON DELETE SET NULL,
  -- 学段：决定该队可报名哪个组别（一队只属一个组别）。
  -- 由成员档案 school_level 派生后落库，不让用户自选：报名校验、组别归属、
  -- 公示名单分组三处都要用它，每次查询重算成员代价过高。
  school_level VARCHAR(8) NOT NULL,          -- ES|MS|HS|U
  level_source VARCHAR(16) NOT NULL DEFAULT 'derived',  -- derived|manual（管理员纠正混合年龄队）
  status       VARCHAR(16) NOT NULL DEFAULT 'active',   -- active|disbanded
  remark      TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
);
-- 同单位队伍名唯一（软删除后名称可复用，故用部分唯一索引代替表级 UNIQUE）
CREATE UNIQUE INDEX uniq_team_name_per_org ON teams(org_id, name) WHERE NOT is_deleted;

CREATE TABLE team_members (
  id         BIGSERIAL PRIMARY KEY,
  team_id    BIGINT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role       VARCHAR(16) NOT NULL DEFAULT 'member',     -- captain|member
  joined_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  left_at    TIMESTAMPTZ,                               -- 成员变动留痕，不删行
  UNIQUE (team_id, user_id, joined_at)
);
CREATE INDEX idx_team_members_user ON team_members(user_id) WHERE left_at IS NULL;
```

学段派生规则（服务层，不属于状态机）：

1. **计算**：取在队成员（`left_at IS NULL`）中最高的 `school_level`，顺序 `U > HS > MS > ES`（混合年龄队按高年级归类）。
2. **成员增减后重算并直接落库**。已提交的报名**不受影响**——报名在提交时冻结成员快照与其所属组别（全局规则 1「快照原则」），换人不回溯。因此这里不设"学段变了就拦截成员变更"的规则：那既无数据完整性收益，又把配置层的不一致转嫁成对用户操作的阻断。
3. 重算导致队伍学段与其存量 `approved` 报名的组别不一致时，由每日一致性任务产出告警清单交主办方判断（多为跨学年正常升级，不需要处置），不阻断任何操作。
4. `level_source='manual'` 时跳过重算，仅 `platform_admin` / `competition_admin` 可设，写审计日志。
5. 队伍无在队成员时学段不可确定，禁止空队提交报名（须先加成员）；此校验发生在报名提交，不发生在成员维护。

## 4. 赛事 / 届次 / 组别

```sql
CREATE TABLE competitions (
  id          BIGSERIAL PRIMARY KEY,
  public_code VARCHAR(32) UNIQUE NOT NULL,
  name        VARCHAR(128) NOT NULL,
  category    VARCHAR(32),                    -- 学科|科技|创新创业|体育|艺术|其他
  level       VARCHAR(16),                    -- school|province|national|international
  summary     TEXT,
  cover_url   VARCHAR(512),
  charter_url VARCHAR(512),                   -- 章程附件
  attachments JSONB,                          -- [{name,url,size}]
  status      VARCHAR(16) NOT NULL DEFAULT 'draft',   -- draft|published|archived
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE competition_organizations (
  id              BIGSERIAL PRIMARY KEY,
  competition_id  BIGINT NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
  org_id          BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  role_type       VARCHAR(16) NOT NULL,        -- host|organizer|co_organizer|sponsor
  display_order   INT NOT NULL DEFAULT 0,
  UNIQUE (competition_id, org_id, role_type)
);

CREATE TABLE competition_admins (
  id              BIGSERIAL PRIMARY KEY,
  competition_id  BIGINT NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
  user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  granted_by      BIGINT REFERENCES users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (competition_id, user_id)
);
-- 注：competition_admins 与 user_roles(role=competition_admin, scope=competition) 二选一存储会造成双写。
-- 决策：user_roles 为唯一权限事实源；本表保留作"展示用名单"冗余，由服务层同步（P1 可合并删除本表）。

CREATE TABLE competition_editions (
  id             BIGSERIAL PRIMARY KEY,
  competition_id BIGINT NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
  edition_no     INT NOT NULL,                -- 第几届
  year           INT NOT NULL,
  name           VARCHAR(128) NOT NULL,       -- '2026 第五届 VEX 机器人公开赛'
  enroll_start   TIMESTAMPTZ,
  enroll_end     TIMESTAMPTZ,
  event_start    TIMESTAMPTZ,
  event_end      TIMESTAMPTZ,
  approval_mode  VARCHAR(16) NOT NULL DEFAULT 'single',  -- single|two_stage
  -- 通过名单公示（v1.1 新增，02 §4.7 定义可见性判定顺序）
  roster_publication   VARCHAR(16) NOT NULL DEFAULT 'open',
    -- open 完全公开 | login 需登录 | none 不公示
  roster_publish_fields JSONB NOT NULL DEFAULT
    '["team_code","org_name","member_names","event","group","award"]',
    -- 白名单列，服务端求交集，永不接受证件/联系方式字段（01 §5）
  roster_published_at  TIMESTAMPTZ,           -- 未设置则即使 open 也不公示（需主办方主动发布）
  status         VARCHAR(16) NOT NULL DEFAULT 'draft',   -- draft|published|closed
  notice         TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted     BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (competition_id, year, edition_no)
);

-- 赛项：机器人平台/项目，与组别并列（v1.1 新增）
CREATE TABLE competition_events (
  id           BIGSERIAL PRIMARY KEY,
  edition_id   BIGINT NOT NULL REFERENCES competition_editions(id) ON DELETE CASCADE,
  code         VARCHAR(16) NOT NULL,          -- VURC|V5RC|VIQRC|VAIMRC|VGORC|custom
  name         VARCHAR(64) NOT NULL,          -- 显示名，如 'VEX V5 机器人竞赛'
  short_name   VARCHAR(32),
  description  TEXT,
  robot_kind   VARCHAR(32),                   -- vex123|vexiq|vexgo|vexai|other（仅用于分组展示，不参与校验）
  min_members  INT NOT NULL DEFAULT 1,        -- 队伍人数约束在赛项：平台决定规模上限
  max_members  INT NOT NULL DEFAULT 3,
  coach_required       BOOLEAN NOT NULL DEFAULT TRUE,
  material_requirements JSONB NOT NULL DEFAULT '[]',  -- [{key,label,required,formats,max_mb}]
  fee          NUMERIC(10,2) NOT NULL DEFAULT 0,
  fee_note     VARCHAR(255),
  status       VARCHAR(16) NOT NULL DEFAULT 'enabled',  -- enabled|disabled
  sort_order   INT NOT NULL DEFAULT 0,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted   BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (edition_id, code),
  CHECK (min_members >= 1 AND max_members >= min_members)
);

-- 组别：学段，与赛项并列。资格限制只来自学段/年级，不再有专业限制（v1.1）
CREATE TABLE competition_groups (
  id                  BIGSERIAL PRIMARY KEY,
  edition_id          BIGINT NOT NULL REFERENCES competition_editions(id) ON DELETE CASCADE,
  code                VARCHAR(8) NOT NULL,           -- ES|MS|HS|U|custom
  name                VARCHAR(64) NOT NULL,          -- 小学组/中学组/高中组/大学组
  school_level        VARCHAR(8),                    -- 对应档案 school_level，NULL=不限
  enrollment_type     VARCHAR(16) NOT NULL DEFAULT 'team',  -- individual|team|both
  age_min             SMALLINT,                      -- 年龄下限（周岁），可选
  age_max             SMALLINT,                      -- 年龄上限（周岁），可选
  grade_limits        JSONB,                         -- 年级标签数组，NULL=不限（学段之下的细化）
  status              VARCHAR(16) NOT NULL DEFAULT 'enabled',  -- enabled|disabled
  sort_order          INT NOT NULL DEFAULT 0,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted          BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (edition_id, code)
);
-- 说明：v1.1 从组别移除 major_limits（专业限制，产品确认不需要）、min/max_members、
-- coach_required、material_requirements、fee —— 这些由赛项决定，因同一学段打不同赛项时
-- 队伍规模与材料要求本就不同。grade_limits 保留在组别（学段内的年级细化）。

-- 届次开放的「赛项 × 组别」组合（v1.1 新增）
-- 存在理由：组合不是任意的。VURC 只设大学组，VGORC 只设小学组，
-- 若无此表则要么在代码里硬编码矩阵（换赛事即失效），要么放任非法组合被报名。
CREATE TABLE competition_offerings (
  id          BIGSERIAL PRIMARY KEY,
  edition_id  BIGINT NOT NULL REFERENCES competition_editions(id) ON DELETE CASCADE,
  event_id    BIGINT NOT NULL REFERENCES competition_events(id) ON DELETE CASCADE,
  group_id    BIGINT NOT NULL REFERENCES competition_groups(id) ON DELETE CASCADE,
  quota       INT,                              -- 该组合名额上限（软限制，NULL=不限）
  enroll_start TIMESTAMPTZ,                    -- 可覆盖届次时间窗（分组错峰报名），NULL=继承届次
  enroll_end   TIMESTAMPTZ,
  status      VARCHAR(16) NOT NULL DEFAULT 'enabled',   -- enabled|disabled
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (edition_id, event_id, group_id)
);
CREATE INDEX idx_offering_edition ON competition_offerings(edition_id, status) WHERE NOT is_deleted;

-- 服务层不变式（无法用外键表达，由报名校验与每日一致性任务共同保证）：
--   一支队伍的学段唯一（teams.school_level，见 §3），因此 team × event 天然只对应一个组别。
--   uniq_reg_team 建在 offering_id 上，等价于建在 (edition, team, event) 上，
--   不会出现"同一队同一赛项被拆成两个组别各报一次"。
--   校验：registration.offering_id 所属 group 的 school_level 必须等于 team.school_level
--   （比 school_level 而非 group.code：code 允许 custom 值，school_level 才是资格字段）。
--   不一致时拒绝提交（错误码 42205）。报名界面不提供"自选组别"，组别由队伍决定
--   （个人报名则由本人档案 school_level 决定），见 01 §3.5a。
--   group.school_level 为 NULL 表示该组别不限学段，此时跳过本条校验（供非 VEX 类赛事使用）。
--   offering 自身保证 group 属于同一 edition，故无需再校验届次一致性。
```

## 5. 报名与审核

```sql
CREATE TABLE registrations (
  id                   BIGSERIAL PRIMARY KEY,
  batch_no             VARCHAR(40) UNIQUE NOT NULL,  -- 报名编号 REG-{edition_id}-{8位随机}，导入匹配主键
  edition_id           BIGINT NOT NULL REFERENCES competition_editions(id) ON DELETE RESTRICT,
  offering_id          BIGINT NOT NULL REFERENCES competition_offerings(id) ON DELETE RESTRICT,
    -- 报名必须落在已开放的「赛项×组别」组合上，替代原先单独引用 group_id：
    -- 这样非法组合（VURC×小学组）在数据库层就无法写入，不依赖服务层校验。
    -- 不再冗余 event_id/group_id 两列：二者由 offering_id 函数决定，冗余会引入漂移，
    -- 而下面的防重复唯一索引正依赖它们——事实源只能有一个。按赛项/组别筛选走 JOIN
    -- competition_offerings（该表每届次仅数十行，索引命中后成本可忽略）。
  enrollment_kind      VARCHAR(16) NOT NULL,         -- individual|team（提交时按赛项/组别规则落定）
  individual_user_id   BIGINT REFERENCES users(id) ON DELETE RESTRICT,
  team_id              BIGINT REFERENCES teams(id) ON DELETE RESTRICT,
  org_id               BIGINT REFERENCES organizations(id) ON DELETE RESTRICT,  -- 参赛单位快照源（公示名单需要）
  submitted_by         BIGINT NOT NULL REFERENCES users(id),  -- 本人/队长/代报教练
  coach_user_id        BIGINT REFERENCES users(id),           -- 指导教师（快照 + 引用）
  contact_name         VARCHAR(64),
  contact_phone        VARCHAR(20) NOT NULL,
  contact_email        VARCHAR(255) NOT NULL,
  form_data            JSONB NOT NULL DEFAULT '{}',  -- 固定字段集（决策：动态表单 P1 后此列扩展）
  consent_snapshot     JSONB NOT NULL DEFAULT '{}',  -- 同意项快照 {id_number:true,...}
  status               VARCHAR(20) NOT NULL DEFAULT 'draft',
    -- draft|submitted|org_approved|org_returned|org_rejected|
    -- pending_review|returned|rejected|approved|withdrawn（03 文档 §1）
  return_round         INT NOT NULL DEFAULT 0,       -- 退回轮次
  submitted_at         TIMESTAMPTZ,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted           BOOLEAN NOT NULL DEFAULT FALSE,
  CHECK ((individual_user_id IS NOT NULL) <> (team_id IS NOT NULL)),  -- 二选一
  CHECK ((enrollment_kind = 'individual') = (individual_user_id IS NOT NULL))
);
-- 防重复报名：同队同赛项同组别唯一。
-- 排除 draft（草稿可并存多份）与 withdrawn（撤回后可重新报名）；
-- rejected 不排除 → 被驳回者不能再次提交，这是有意的第一版口径，若产品要求"驳回可重报"则把 rejected 一并加入排除列表。
CREATE UNIQUE INDEX uniq_reg_team
  ON registrations(edition_id, team_id, offering_id)
  WHERE enrollment_kind = 'team'
    AND status NOT IN ('draft','withdrawn') AND NOT is_deleted;
-- 个人报名：同一人在同一赛项同一组别只能报一次，但可跨赛项分别报名（VEX 常见多报）。
CREATE UNIQUE INDEX uniq_reg_individual
  ON registrations(edition_id, individual_user_id, offering_id)
  WHERE enrollment_kind = 'individual'
    AND status NOT IN ('draft','withdrawn') AND NOT is_deleted;
CREATE INDEX idx_reg_edition_status ON registrations(edition_id, status) WHERE NOT is_deleted;
-- 公示名单与审核台的主查询路径：按 届次×开放组合×状态 取 approved
CREATE INDEX idx_reg_offering_status
  ON registrations(offering_id, status) WHERE NOT is_deleted;
CREATE INDEX idx_reg_offering ON registrations(offering_id) WHERE NOT is_deleted;

CREATE TABLE registration_members (
  id              BIGSERIAL PRIMARY KEY,
  registration_id BIGINT NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  user_id         BIGINT REFERENCES users(id) ON DELETE SET NULL,  -- 快照源，删号不影响
  -- 快照含证件信息，按敏感等级分列存放：公示查询只取 _public 列，
  -- 避免整表 JSONB 被 SELECT * 带出（v1.1 结构化，替代原先塞在 snapshot 里）
  snapshot        JSONB NOT NULL,        -- 完整快照（仅具备 profile:read 者经服务层过滤后可见）
  public_info     JSONB NOT NULL,        -- 白名单子集 {real_name, role, school_level, grade}，公示名单只读此列
  id_number_hash  VARCHAR(64),           -- 跨报名查重（同人在同队重复出现）
  role            VARCHAR(16) NOT NULL DEFAULT 'member',            -- captain|member|coach
  sort_order      INT NOT NULL DEFAULT 0,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_reg_members_reg ON registration_members(registration_id);

CREATE TABLE registration_files (
  id              BIGSERIAL PRIMARY KEY,
  registration_id BIGINT NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  material_key    VARCHAR(64) NOT NULL,    -- 对应赛项 material_requirements[].key（v1.1：材料要求由赛项决定，非组别）
  file_name       VARCHAR(255) NOT NULL,
  storage_key     VARCHAR(512) NOT NULL,   -- MinIO object key（私有桶）
  size_bytes      BIGINT NOT NULL,
  mime_type       VARCHAR(128),
  sha256          VARCHAR(64),
  round_no        INT NOT NULL DEFAULT 1,  -- 重提轮次，历史文件保留
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by      BIGINT REFERENCES users(id)
);

CREATE TABLE approval_records (
  id              BIGSERIAL PRIMARY KEY,
  registration_id BIGINT NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  step            VARCHAR(16) NOT NULL,    -- org|final|revoke（对应模式）
  round_no        INT NOT NULL DEFAULT 1,
  action          VARCHAR(16) NOT NULL,    -- approve|reject|return|withdraw|revoke_approval
  from_status     VARCHAR(20) NOT NULL,
  to_status       VARCHAR(20) NOT NULL,
  comment         TEXT,                    -- reject/return 必填（服务层校验）
  actor_id        BIGINT NOT NULL REFERENCES users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_approval_reg ON approval_records(registration_id);
-- 审核记录与文件同样"永久保留"：无 is_deleted
```

## 6. 奖项 / 获奖名单 / 证书

```sql
CREATE TABLE awards (
  id          BIGSERIAL PRIMARY KEY,
  edition_id  BIGINT NOT NULL REFERENCES competition_editions(id) ON DELETE CASCADE,
  offering_id BIGINT REFERENCES competition_offerings(id) ON DELETE CASCADE,
    -- NULL = 届次通用奖项（最佳组织奖、优秀教练奖等，不落到具体赛项×组别）
  rank_level  VARCHAR(16) NOT NULL,          -- first|second|third|excellence|custom
  name        VARCHAR(64) NOT NULL,          -- '一等奖'
  quota       INT,                           -- 名额（软限制，服务层校验）
  sort_order  INT NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
  -- PG16 `NULLS NOT DISTINCT`：通用奖项的 offering_id 为 NULL，默认 UNIQUE 会把 NULL
  -- 视为互不相等，导致同名通用奖项可重复插入。必须显式声明（v1.1）
  UNIQUE NULLS NOT DISTINCT (edition_id, offering_id, name)
);

CREATE TABLE award_rosters (
  id          BIGSERIAL PRIMARY KEY,
  edition_id  BIGINT NOT NULL REFERENCES competition_editions(id) ON DELETE CASCADE,
  offering_id BIGINT REFERENCES competition_offerings(id) ON DELETE CASCADE,
    -- NULL = 届次通用奖项名单；获奖以「赛项×组别」为单位评奖，故与 awards 同口径
  status      VARCHAR(20) NOT NULL DEFAULT 'editing',
    -- editing|under_approval|confirmed|issued（03 文档 §5）
  submitted_by BIGINT REFERENCES users(id),
  approved_by  BIGINT REFERENCES users(id),
  approved_at  TIMESTAMPTZ,
  lock_note    TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE NULLS NOT DISTINCT (edition_id, offering_id)
);

CREATE TABLE award_records (
  id              BIGSERIAL PRIMARY KEY,
  roster_id       BIGINT NOT NULL REFERENCES award_rosters(id) ON DELETE CASCADE,
  award_id        BIGINT NOT NULL REFERENCES awards(id) ON DELETE RESTRICT,
  registration_id BIGINT NOT NULL REFERENCES registrations(id) ON DELETE RESTRICT,  -- 必须 approved
  recipient_kind  VARCHAR(16) NOT NULL,      -- individual|team（冗余自报名）
  batch_no        VARCHAR(40) NOT NULL,      -- 冗余自报名，导入对账用
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (roster_id, registration_id)       -- 同名单内一条报名只得一个奖
);

CREATE TABLE award_import_pending (
  id           BIGSERIAL PRIMARY KEY,
  roster_id    BIGINT NOT NULL REFERENCES award_rosters(id) ON DELETE CASCADE,
  batch_no     VARCHAR(40),
  raw_row      JSONB NOT NULL,               -- Excel 原始行
  conflict     VARCHAR(32) NOT NULL,         -- not_found|dup|name_mismatch|id_mismatch|already_awarded
  resolved_by  BIGINT REFERENCES users(id),
  resolved_at  TIMESTAMPTZ,
  resolution   VARCHAR(16),                  -- accepted|rejected
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 证书编号计数器：与自增主键解耦（修 §11 遗留项）
-- 原方案 CS-{届次ID四位补零}-{序号} 的序号若取自 certificates.id 或届次主键，
-- 则「届次合并 / 数据迁移 / 补发作废导致 id 跳号」都会让新证编号含义漂移，
-- 而已签发的证书编号必须永久稳定。序号只增不减、永不复用，取号后即使证书
-- 生成失败也不回收该号（宁可跳号，不可重号）。
CREATE TABLE certificate_sequences (
  edition_id   BIGINT PRIMARY KEY REFERENCES competition_editions(id) ON DELETE RESTRICT,
  serial_prefix VARCHAR(16) NOT NULL,      -- 'CS-0012'，建届次时生成一次后不可变
  next_no      BIGINT NOT NULL DEFAULT 1
);

CREATE TABLE certificates (
  id             BIGSERIAL PRIMARY KEY,
  serial_no      VARCHAR(40) UNIQUE NOT NULL,   -- CS-{prefix}-{5位补零}，如 CS-0012-00345
  serial_prefix  VARCHAR(16) NOT NULL,          -- 冻结自 certificate_sequences，不随届次变更
  serial_no_seq  BIGINT NOT NULL,               -- 冻结的序号；与 serial_no 一并成为不可变历史事实
  award_record_id BIGINT NOT NULL REFERENCES award_records(id) ON DELETE RESTRICT,
  edition_id     BIGINT NOT NULL REFERENCES competition_editions(id) ON DELETE RESTRICT,
  holder_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
  display_name   VARCHAR(64) NOT NULL,          -- 快照（team 获奖显示队名）
  recipient_kind VARCHAR(16) NOT NULL,
  template_id    VARCHAR(32) NOT NULL DEFAULT 'default',
  pdf_storage_key VARCHAR(512),
  qr_token       VARCHAR(64) UNIQUE NOT NULL,   -- 验证页 URL token，不可遍历
  status         VARCHAR(16) NOT NULL DEFAULT 'queued',
    -- queued|generated|issued|revoked|failed（03 文档 §6）
  revoke_reason  TEXT,
  reissue_of     BIGINT REFERENCES certificates(id),  -- 补发链：指向被作废的原证
  supersedes_serial VARCHAR(40),                        -- 原证作废后对外公示的新证编号（03 §6.1）
  generated_at   TIMESTAMPTZ,
  issued_at      TIMESTAMPTZ,
  revoked_at     TIMESTAMPTZ,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- serial_prefix / serial_no_seq / serial_no 一经写入即为历史事实，服务层禁止 UPDATE；
  -- 由触发器或只读属性保证，补发只能新建行 + 写 reissue_of
  UNIQUE (serial_prefix, serial_no_seq)
);
-- 一个获奖记录至多一张有效证书
CREATE UNIQUE INDEX uniq_cert_active_per_award
  ON certificates(award_record_id) WHERE status <> 'revoked';
-- 取号在事务内 SELECT ... FOR UPDATE，并发批量生成不会重号
```

## 7. 通知与日志

```sql
CREATE TABLE notices (
  id             BIGSERIAL PRIMARY KEY,
  title          VARCHAR(200) NOT NULL,
  body           TEXT NOT NULL,
  channel        VARCHAR(16) NOT NULL DEFAULT 'inbox',   -- inbox|email（第一版）
  audience_type  VARCHAR(16) NOT NULL,   -- all|org|competition|edition|users
  audience_id    BIGINT,
  target_user_ids BIGINT[],              -- audience_type='users'
  published_by   BIGINT NOT NULL REFERENCES users(id),
  published_at   TIMESTAMPTZ,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted     BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE notice_reads (
  notice_id BIGINT NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
  user_id   BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  read_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (notice_id, user_id)
);

CREATE TABLE audit_logs (
  id          BIGSERIAL PRIMARY KEY,
  actor_id    BIGINT REFERENCES users(id),
  action      VARCHAR(48) NOT NULL,      -- 'approval.approve' 'cert.revoke' 'roster.import' 'data.export'…
  resource    VARCHAR(32) NOT NULL,
  resource_id VARCHAR(64),
  scope       JSONB,                     -- {edition_id: 3} 便于按赛事过滤
  detail      JSONB,                     -- 变更摘要/导出字段清单/理由
  ip          INET,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_actor_time ON audit_logs(actor_id, created_at);
CREATE INDEX idx_audit_resource ON audit_logs(resource, resource_id);
```

## 8. 设计说明与遗留项

1. **多态 scope_id**（user_roles / notices.audience_id）未做数据库外键，完整性依赖服务层与每日一致性检查任务——这是灵活性换保证成本，明确接受。
2. **身份证号** 存 `id_number_enc`（密文）+ `id_number_hash`（加 pepper 的 SHA-256，用于匹配与查重，不可逆）。加密在 P0 落地（v1.1 决策，原 P1 提级），因为本系统强制全员收集证件号，明文入库的风险与「按需收集」时不是一个量级：
   - 方案取应用层 Fernet（`cryptography` 库），不选 pgcrypto。理由：数据库密文随 `pg_dump` 一起备份恢复，不依赖扩展存在；密钥轮换可在应用层做重加密任务，不需停机执行 SQL 迁移。
   - 密钥走 `FIELD_ENCRYPTION_KEY` 环境变量，禁止入仓；hash 的 pepper 单独一个变量（`ID_HASH_PEPPER`），轮换 pepper 需重算全表 hash，属破坏性变更。
   - 任何 API 不回传明文，日志只记末四位（DEVELOPMENT.md §2.4）；公示名单物理上读不到该列（`registration_members.public_info` 白名单）。
3. **赛项与组别正交**（v1.1）：不合并成「组别」一列的复合值，因为评奖、公示、名额、时间窗都按二者之一独立聚合（「大学组全部赛项通过率」与「V5RC 各组别通过率」是两个真实报表需求）。合并会让每类统计都要拆字符串。
4. **`competition_offerings` 的删除策略**：赛项或组别被删则其组合行级联删除，但 registrations 引用 offering 为 `RESTRICT`——已有报名的组合无法被删除，只能停用（`status=disabled`）。这是有意的：不允许因为清理配置而连带影响报名数据。
5. `competition_admins` 冗余表问题见 §4 注释，P1 合并。
6. **organizations 不设 parent_id 冗余列**（v1.1）：树关系只由 `path` 表达，父级用 `get_parent()` 截断得出。保留父指针就会与 `competition_admins` 犯同一个错——两处事实源、一个更新漏了就不一致。
7. **证书编号不可变**（v1.1）：见 §6 `certificate_sequences`，序号取号后不回收、不随届次主键变化。
8. 大表预估（百万级前无需分区）：`registrations`、`registration_members`、`audit_logs`。`audit_logs` 上一年热表，P1 考虑按月分区。
9. JSONB 使用原则：只用于**配置快照与低频筛选**（材料要求、成员快照、form_data）；高频筛选列一律实体列 + B-tree。公示字段拆成 `public_info` 与 `snapshot` 两列，是因为白名单过滤必须发生在数据库读取层，而不是取回整行再在 Python 里删字段——后者一旦有人写了 `SELECT *` 就泄露。
10. 统计不做预聚合物化视图（P0 数据量下实时 count + Redis 短缓存足够），P1 再上汇总表。
