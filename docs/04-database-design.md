# 04 数据库设计（字段级 DDL）

**版本**：v1.6（2026-11-17）。目标库 PostgreSQL 16，Django 5 迁移生成前的目标 schema。

v1.4：增加证件更正审批守卫、护照/代建账户、队号归属与赛项身份、提交轮次到证书的外键、事务 outbox。

> 2026-11-17 审阅：本 schema 尚无迁移实现；同届外键、逐人证书与个人信息规则已按产品确认修订，见 [审阅待办](10-review-notes.md)。文中的服务层不变式不能替代数据库约束。

> 2026-11-18 范围同步：队伍基础、逐赛季许可和团队报名进入首期；证书及复杂跨队特批表保留后续设计，不据此开放首期接口。首期不计算年龄资格，`competition_groups.age_min/age_max` 保持 NULL，配置接口拒绝启用年龄限制，不从证件生日派生年龄判定；使用私有在读证明人工核验。现有 registration_files 可按材料类型与提交轮次引用证明，不新增 AI 文件副本；AI 只能获得脱敏核验状态。授权引用/consent_snapshot 记录单位线下核验事实，不代表已实现线上监护签署。下列SQL为完整领域设计；首批已实现模型、技术字段及物理命名映射见§9，正式部署执行Django迁移，不重复执行本文建表SQL。

个人信息按 [01 §5](01-PRD.md#5-合规与个人信息保护) 长期保存，保留受控更正、停用和必要删除机制；普通CRUD仍禁止硬删除历史。特殊处置须评估证件绑定、成员/报名快照、文件、审计及备份的关联影响，按审定政策执行并留脱敏处置记录，不提供通用级联删除接口。导入暂存最长30天清理仍有效，与业务资料长期留存区分；服务器外备份及密钥恢复按部署指南验收。

约定：
- 字段以各表 DDL 为准；含 `is_deleted` 的业务表配套 `deleted_at`，两者一致更新。关系表使用业务唯一键或复合主键；成员退队用 `left_at`，审核/证书/审计历史不软删除。
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
  └─ competition_editions ── seasons
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
  id BIGSERIAL PRIMARY KEY,
  username VARCHAR(64) UNIQUE NOT NULL,             -- 系统生成账号标识，不使用证件明文
  email VARCHAR(255) UNIQUE,                        -- 代建账户可空，绑定/变更须验证
  email_verified_at TIMESTAMPTZ,
  phone VARCHAR(20),                               -- 可共用，仅联系方式
  password_hash VARCHAR(255) NOT NULL,
  account_source VARCHAR(16) NOT NULL DEFAULT 'self' CHECK (account_source IN ('self','org')),
  created_by BIGINT REFERENCES users(id),
  created_by_org_id BIGINT,
  must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
  initial_password_expires_at TIMESTAMPTZ,
  status VARCHAR(16) NOT NULL DEFAULT 'pending',
  token_version INTEGER NOT NULL DEFAULT 0,
  affiliation_version INTEGER NOT NULL DEFAULT 0 CHECK (affiliation_version >= 0),
  locale VARCHAR(10) NOT NULL DEFAULT 'zh-CN' CHECK (locale IN ('zh-CN','en-US')),
  theme VARCHAR(10) NOT NULL DEFAULT 'system' CHECK (theme IN ('light','dark','system')),
  last_login_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CHECK (account_source <> 'org' OR (created_by IS NOT NULL AND created_by_org_id IS NOT NULL)),
  CHECK (email IS NOT NULL OR email_verified_at IS NULL)
);

-- 邮箱验证码：一次性、限频、试错次数受限。手机号通道预留但第一版不启用。
CREATE TABLE verification_codes (
  id          BIGSERIAL PRIMARY KEY,
  channel     VARCHAR(16) NOT NULL,                  -- email（第一版仅此值）| sms（预留）
  target      VARCHAR(255) NOT NULL,                 -- 邮箱或手机号
  delivery_secret_enc BYTEA,                     -- 仅投递重试期间保留的加密验证码，成功/过期后清除
  code_hash   VARCHAR(255) NOT NULL,                 -- 不存明文验证码
  purpose     VARCHAR(24) NOT NULL,                  -- register|reset_password|change_email
  expires_at  TIMESTAMPTZ NOT NULL,                  -- 默认 10 分钟
  attempts    INT NOT NULL DEFAULT 0,                -- 第 5 次校验失败即作废
  consumed_at TIMESTAMPTZ,
  client_ip   INET,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_vcode_lookup ON verification_codes(channel, target, purpose, consumed_at);

CREATE TABLE user_profiles (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  real_name VARCHAR(64) NOT NULL,
  gender VARCHAR(10),
  photo_storage_key VARCHAR(512),
  birth_date DATE,
  document_type VARCHAR(16),                       -- id_card / passport，二选一
  document_country CHAR(2),                        -- 身份证 CN；护照为签发国 ISO 两位码
  document_number_enc BYTEA,
  document_hash VARCHAR(64),                       -- HMAC(type|country|规范化号码)，当前绑定唯一
  document_last4 VARCHAR(4),
  identity_version INTEGER NOT NULL DEFAULT 0,
  identity_change_request_id BIGINT,
  student_no VARCHAR(64),
  staff_no VARCHAR(64),
  person_type VARCHAR(16) NOT NULL DEFAULT 'participant',
  school_level VARCHAR(8),                         -- 资料记录，不自动决定本场组别
  grade VARCHAR(32),
  title VARCHAR(64),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CHECK (
    (document_type IS NULL AND document_country IS NULL AND document_number_enc IS NULL AND document_hash IS NULL AND document_last4 IS NULL) OR
    (document_type IS NOT NULL AND document_country IS NOT NULL AND document_number_enc IS NOT NULL AND document_hash IS NOT NULL AND document_last4 IS NOT NULL
      AND document_type IN ('id_card','passport') AND document_country ~ '^[A-Z]{2}$'
      AND (document_type <> 'id_card' OR document_country = 'CN'))
  )
);
CREATE UNIQUE INDEX uniq_profile_document ON user_profiles(document_hash);
-- 注销不自动释放当前绑定；已批准更正会原子释放旧绑定，历史快照不变。
CREATE TABLE identity_change_requests (
  id BIGSERIAL PRIMARY KEY,
  resubmission_of BIGINT REFERENCES identity_change_requests(id) ON DELETE RESTRICT,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  base_identity_version INTEGER NOT NULL,
  old_document_hash VARCHAR(64),
  new_document_type VARCHAR(16) NOT NULL CHECK (new_document_type IN ('id_card','passport')),
  new_document_country CHAR(2) NOT NULL CHECK (new_document_country ~ '^[A-Z]{2}$'),
  new_document_number_enc BYTEA NOT NULL,
  new_document_hash VARCHAR(64) NOT NULL,
  new_document_last4 VARCHAR(4) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','submitted','approved','returned','rejected','withdrawn')),
  submitted_by BIGINT NOT NULL REFERENCES users(id),
  reviewer_id BIGINT REFERENCES users(id),
  comment TEXT,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (new_document_type <> 'id_card' OR new_document_country = 'CN'),
  CHECK (reviewer_id IS NULL OR (reviewer_id <> submitted_by AND reviewer_id <> user_id)),
  CHECK (status NOT IN ('approved','returned','rejected') OR (reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL)),
  CHECK (status NOT IN ('returned','rejected') OR NULLIF(btrim(comment),'') IS NOT NULL)
);
CREATE UNIQUE INDEX uniq_pending_identity_change ON identity_change_requests(user_id) WHERE status IN ('draft','submitted');
ALTER TABLE user_profiles ADD FOREIGN KEY (identity_change_request_id) REFERENCES identity_change_requests(id) ON DELETE RESTRICT;

CREATE FUNCTION guard_profile_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    NEW.identity_version := CASE WHEN NEW.document_hash IS NULL THEN 0 ELSE 1 END;
    NEW.identity_change_request_id := NULL;
    RETURN NEW;
  END IF;
  IF NEW.user_id <> OLD.user_id THEN
    RAISE EXCEPTION 'Profile owner is immutable' USING ERRCODE = '55000';
  END IF;
  IF ROW(NEW.document_type,NEW.document_country,NEW.document_hash,NEW.document_last4)
     IS NOT DISTINCT FROM ROW(OLD.document_type,OLD.document_country,OLD.document_hash,OLD.document_last4) THEN
    IF NEW.identity_version <> OLD.identity_version OR NEW.identity_change_request_id IS DISTINCT FROM OLD.identity_change_request_id THEN
      RAISE EXCEPTION 'Identity metadata requires an approved change' USING ERRCODE = '55000';
    END IF;
    RETURN NEW; -- 相同身份的密文可随密钥轮换重加密
  END IF;
  IF OLD.document_hash IS NULL AND NEW.document_hash IS NOT NULL THEN
    NEW.identity_version := OLD.identity_version + 1;
    NEW.identity_change_request_id := NULL;
    RETURN NEW;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM identity_change_requests r WHERE r.id = NEW.identity_change_request_id
      AND r.user_id = OLD.user_id AND r.status = 'approved' AND r.base_identity_version = OLD.identity_version
      AND r.old_document_hash IS NOT DISTINCT FROM OLD.document_hash
      AND ROW(r.new_document_type,r.new_document_country,r.new_document_hash,r.new_document_last4,r.new_document_number_enc)
          IS NOT DISTINCT FROM ROW(NEW.document_type,NEW.document_country,NEW.document_hash,NEW.document_last4,NEW.document_number_enc)
  ) THEN
    RAISE EXCEPTION 'Identity change requires matching approved request' USING ERRCODE = '55000';
  END IF;
  NEW.identity_version := OLD.identity_version + 1;
  RETURN NEW;
END;
$$;
CREATE TRIGGER profile_identity_guard BEFORE INSERT OR UPDATE ON user_profiles
  FOR EACH ROW EXECUTE FUNCTION guard_profile_identity();

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
  logo_url    VARCHAR(512),
  contact_info JSONB,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ,
  is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE UNIQUE INDEX uniq_org_path ON organizations(path);
-- 子树查询前缀匹配必须用 text_pattern_ops，否则 B-tree 不支持 LIKE 'x%'
CREATE INDEX idx_org_path_prefix ON organizations(path varchar_pattern_ops);
-- Django PositiveIntegerField 在 PostgreSQL 会生成非负 CHECK，列出以保持 DDL 与 makemigrations 一致
ALTER TABLE organizations ADD CONSTRAINT org_depth_nonneg CHECK (depth >= 0);
ALTER TABLE organizations ADD CONSTRAINT org_numchild_nonneg CHECK (numchild >= 0);

ALTER TABLE users ADD FOREIGN KEY (created_by_org_id) REFERENCES organizations(id) ON DELETE RESTRICT;

CREATE TABLE org_creation_requests (
  id BIGSERIAL PRIMARY KEY,
  resubmission_of BIGINT REFERENCES org_creation_requests(id) ON DELETE RESTRICT,
  requested_parent_id BIGINT REFERENCES organizations(id) ON DELETE RESTRICT,
  proposal_enc BYTEA NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','submitted','approved','returned','rejected','withdrawn')),
  submitted_by BIGINT NOT NULL REFERENCES users(id),
  reviewer_id BIGINT REFERENCES users(id),
  comment TEXT,
  reviewed_at TIMESTAMPTZ,
  result_org_id BIGINT UNIQUE REFERENCES organizations(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (reviewer_id IS NULL OR reviewer_id <> submitted_by),
  CHECK ((status = 'approved') = (result_org_id IS NOT NULL)),
  CHECK (status NOT IN ('approved','returned','rejected') OR (reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL)),
  CHECK (status NOT IN ('returned','rejected') OR NULLIF(btrim(comment),'') IS NOT NULL)
);
-- 通过前不建正式单位；批准事务内建节点并回填 result_org_id，申请留存不软删。

CREATE TABLE organization_members (
  id           BIGSERIAL PRIMARY KEY,
  org_id       BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  member_role  VARCHAR(16) NOT NULL DEFAULT 'member',   -- member|student|teacher|employee|external
  is_primary   BOOLEAN NOT NULL DEFAULT FALSE,          -- 主属单位（唯一部分索引）
  joined_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  left_at      TIMESTAMPTZ,                        -- 平台成员关系结束时间，不是离职信息
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (id, user_id, org_id),
  CHECK (left_at IS NULL OR left_at >= joined_at)
);
CREATE UNIQUE INDEX uniq_current_org_member ON organization_members(org_id,user_id) WHERE left_at IS NULL;
CREATE UNIQUE INDEX idx_org_member_primary
  ON organization_members(user_id) WHERE is_primary AND left_at IS NULL;

CREATE TABLE org_transfer_requests (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  from_org_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  to_org_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  source_membership_id BIGINT NOT NULL,
  base_affiliation_version INTEGER NOT NULL CHECK (base_affiliation_version >= 0),
  submitted_by BIGINT NOT NULL REFERENCES users(id),
  authorization_ref VARCHAR(512), -- 本人/监护授权凭据，私有引用，不记录证件正文
  consented_at TIMESTAMPTZ,
  reason TEXT NOT NULL CHECK (NULLIF(btrim(reason),'') IS NOT NULL),
  status VARCHAR(24) NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','awaiting_source','awaiting_target','completed','rejected','withdrawn')),
  source_reviewer_id BIGINT REFERENCES users(id),
  source_reviewed_at TIMESTAMPTZ,
  target_reviewer_id BIGINT REFERENCES users(id),
  target_reviewed_at TIMESTAMPTZ,
  platform_release_by BIGINT REFERENCES users(id),
  platform_release_reason TEXT,
  rejected_by BIGINT REFERENCES users(id),
  comment TEXT,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (from_org_id <> to_org_id),
  CHECK (status IN ('draft','withdrawn') OR (NULLIF(btrim(authorization_ref),'') IS NOT NULL AND consented_at IS NOT NULL)),
  CHECK (source_reviewer_id IS NULL OR (source_reviewer_id <> submitted_by AND source_reviewer_id <> user_id)),
  CHECK (target_reviewer_id IS NULL OR (target_reviewer_id <> submitted_by AND target_reviewer_id <> user_id)),
  CHECK (source_reviewer_id IS NULL OR target_reviewer_id IS NULL OR source_reviewer_id <> target_reviewer_id),
  CHECK (status NOT IN ('awaiting_target','completed') OR (source_reviewer_id IS NOT NULL AND source_reviewed_at IS NOT NULL)),
  CHECK (status <> 'completed' OR (target_reviewer_id IS NOT NULL AND target_reviewed_at IS NOT NULL AND completed_at IS NOT NULL)),
  CHECK (status <> 'rejected' OR (rejected_by IS NOT NULL AND NULLIF(btrim(comment),'') IS NOT NULL)),
  CHECK (platform_release_by IS NULL OR (source_reviewer_id IS NOT NULL AND source_reviewer_id = platform_release_by AND NULLIF(btrim(platform_release_reason),'') IS NOT NULL)),
  FOREIGN KEY (source_membership_id,user_id,from_org_id) REFERENCES organization_members(id,user_id,org_id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX uniq_pending_org_transfer ON org_transfer_requests(user_id)
  WHERE status IN ('draft','awaiting_source','awaiting_target');

CREATE TABLE roles (
  id          BIGSERIAL PRIMARY KEY,
  code        VARCHAR(32) UNIQUE NOT NULL,      -- participant|team_coach|org_admin|competition_admin|reviewer|platform_admin|自定义
  name        VARCHAR(64) NOT NULL,
  is_builtin  BOOLEAN NOT NULL DEFAULT FALSE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ,
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
  UNIQUE NULLS NOT DISTINCT (user_id, role_id, scope_type, scope_id),
  CHECK (scope_type IN ('global', 'org', 'competition', 'edition')),
  CHECK ((scope_type = 'global' AND scope_id IS NULL) OR (scope_type <> 'global' AND scope_id IS NOT NULL))
);
CREATE INDEX idx_user_roles_user ON user_roles(user_id);
-- scope_id 不做跨表外键（多态），完整性由服务层 + 定期一致性任务保证
```

## 3. 队伍

```sql
CREATE TABLE event_types (
  code VARCHAR(16) PRIMARY KEY,                     -- 跨届稳定赛项代码，平台维护
  name VARCHAR(64) NOT NULL
);
CREATE TABLE team_numbers (
  id BIGSERIAL PRIMARY KEY,
  code VARCHAR(32) UNIQUE NOT NULL,
  org_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  UNIQUE (id, org_id)
);

CREATE TABLE teams (
  id          BIGSERIAL PRIMARY KEY,
  team_number_id BIGINT NOT NULL,
  event_code VARCHAR(16) NOT NULL REFERENCES event_types(code) ON DELETE RESTRICT,
  name        VARCHAR(128) NOT NULL,
  org_id      BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  coach_id    BIGINT REFERENCES users(id) ON DELETE SET NULL,
  captain_id  BIGINT REFERENCES users(id) ON DELETE SET NULL,
  membership_version INTEGER NOT NULL DEFAULT 1 CHECK (membership_version >= 1), -- 自主退队/成员变更递增
  approved_revision_id BIGINT,              -- 当前生效的已审核队伍申请；批准创建时填入
  status       VARCHAR(16) NOT NULL DEFAULT 'active',   -- active|disbanded
  remark      TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ,
  is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
);
ALTER TABLE teams ADD UNIQUE (team_number_id, event_code);
ALTER TABLE teams ADD FOREIGN KEY (team_number_id, org_id) REFERENCES team_numbers(id, org_id) ON DELETE RESTRICT;

CREATE TABLE team_change_requests (
  id BIGSERIAL PRIMARY KEY,
  resubmission_of BIGINT REFERENCES team_change_requests(id) ON DELETE RESTRICT,
  team_id BIGINT REFERENCES teams(id) ON DELETE RESTRICT, -- 创建批准时回填
  org_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  team_code VARCHAR(32) NOT NULL,
  event_code VARCHAR(16) NOT NULL REFERENCES event_types(code) ON DELETE RESTRICT,
  request_kind VARCHAR(16) NOT NULL CHECK (request_kind IN ('create','update')),
  registration_season_id BIGINT, -- 创建申请必须指定注册赛季，修改不改变许可
  CHECK (request_kind <> 'create' OR registration_season_id IS NOT NULL),
  base_revision_id BIGINT,
  base_membership_version INTEGER NOT NULL DEFAULT 1 CHECK (base_membership_version >= 1),
  proposal_enc BYTEA NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','submitted','approved','returned','rejected','withdrawn')),
  submitted_by BIGINT NOT NULL REFERENCES users(id),
  reviewer_id BIGINT REFERENCES users(id),
  comment TEXT,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (id, team_id),
  CHECK (reviewer_id IS NULL OR reviewer_id <> submitted_by),
  CHECK ((request_kind = 'create' AND base_revision_id IS NULL) OR
         (request_kind = 'update' AND team_id IS NOT NULL AND base_revision_id IS NOT NULL)),
  CHECK (status <> 'approved' OR (team_id IS NOT NULL AND reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL)),
  CHECK (status NOT IN ('returned','rejected') OR
         (reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL AND NULLIF(btrim(comment),'') IS NOT NULL)),
  FOREIGN KEY (base_revision_id, team_id) REFERENCES team_change_requests(id, team_id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX uniq_team_pending_change ON team_change_requests(team_id)
  WHERE request_kind = 'update' AND status IN ('draft','submitted');
CREATE UNIQUE INDEX uniq_team_pending_code ON team_change_requests(team_code, event_code)
  WHERE status IN ('draft','submitted');
ALTER TABLE teams ADD UNIQUE (id, org_id, event_code);
ALTER TABLE team_change_requests ADD CONSTRAINT team_request_org_fk
  FOREIGN KEY (team_id, org_id, event_code) REFERENCES teams(id, org_id, event_code) ON DELETE RESTRICT;
ALTER TABLE teams ADD CONSTRAINT team_current_revision_fk
  FOREIGN KEY (approved_revision_id, id) REFERENCES team_change_requests(id, team_id) ON DELETE RESTRICT;

CREATE TABLE team_members (
  id         BIGSERIAL PRIMARY KEY,
  team_id    BIGINT NOT NULL REFERENCES teams(id) ON DELETE RESTRICT,
  user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  role       VARCHAR(16) NOT NULL DEFAULT 'member' CHECK (role IN ('captain','member')), -- 学生队员
  joined_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  left_at    TIMESTAMPTZ,                               -- 成员变动留痕，不删行
  UNIQUE (team_id, user_id, joined_at),
  CHECK (left_at IS NULL OR left_at >= joined_at)
);
CREATE UNIQUE INDEX uniq_current_team_member ON team_members(user_id) WHERE left_at IS NULL;
```

队伍身份与版本：队号由 team_numbers 唯一归属一个单位；teams 以 team_number_id × event_code 唯一。赛项类型由 event_types 跨届稳定维护，普通资料修改不能更换该身份。报名校验团队赛项与本届赛项一致。

提交人自行选择本场学段/组别，selected_school_level 和所选 offering 冻结在提交轮次；不按队伍成员最高学段自动派生。队伍档案更新仅在资料审核批准后生效，可用于其他比赛，任何本场已提交快照都不跟随更新。空队不能提交团队报名。

## 4. 赛事 / 届次 / 组别

```sql
CREATE TABLE seasons (
  id BIGSERIAL PRIMARY KEY,
  code VARCHAR(32) UNIQUE NOT NULL,
  name VARCHAR(64) NOT NULL,
  starts_on DATE NOT NULL,
  ends_on DATE NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','archived')),
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (starts_on <= ends_on),
  CHECK (NOT is_default OR status = 'active')
);
CREATE UNIQUE INDEX uniq_default_season ON seasons(is_default) WHERE is_default;
ALTER TABLE team_change_requests ADD FOREIGN KEY (registration_season_id) REFERENCES seasons(id) ON DELETE RESTRICT;

-- 队伍稳定身份跨赛季保留；每次申请独立留档，拒绝后创建关联新申请。
CREATE TABLE team_season_registrations (
  id BIGSERIAL PRIMARY KEY,
  team_id BIGINT NOT NULL REFERENCES teams(id) ON DELETE RESTRICT,
  season_id BIGINT NOT NULL REFERENCES seasons(id) ON DELETE RESTRICT,
  resubmission_of BIGINT REFERENCES team_season_registrations(id) ON DELETE RESTRICT,
  status VARCHAR(16) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','submitted','approved','rejected','withdrawn','revoked')),
  proposal_enc BYTEA NOT NULL,
  submitted_by BIGINT NOT NULL REFERENCES users(id),
  reviewer_id BIGINT REFERENCES users(id),
  reviewed_at TIMESTAMPTZ,
  comment TEXT,
  revoked_by BIGINT REFERENCES users(id),
  revoked_at TIMESTAMPTZ,
  revoke_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (reviewer_id IS NULL OR reviewer_id <> submitted_by),
  CHECK (status NOT IN ('approved','rejected','revoked') OR (reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL AND NULLIF(btrim(comment),'') IS NOT NULL)),
  CHECK (status <> 'revoked' OR (revoked_by IS NOT NULL AND revoked_at IS NOT NULL AND NULLIF(btrim(revoke_reason),'') IS NOT NULL))
);
CREATE UNIQUE INDEX uniq_live_team_season_registration ON team_season_registrations(team_id,season_id)
  WHERE status IN ('draft','submitted','approved');

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
  deleted_at TIMESTAMPTZ,
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
  season_id      BIGINT NOT NULL REFERENCES seasons(id) ON DELETE RESTRICT,
  competition_id BIGINT NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
  edition_no     INT NOT NULL,                -- 第几届
  year           INT NOT NULL,
  name           VARCHAR(128) NOT NULL,       -- '2026 第五届 VEX 机器人公开赛'
  enroll_start   TIMESTAMPTZ,
  enroll_end     TIMESTAMPTZ,
  event_start    TIMESTAMPTZ,
  event_end      TIMESTAMPTZ,
  team_entry_mode VARCHAR(16) NOT NULL DEFAULT 'open' CHECK (team_entry_mode IN ('open', 'allowlist')),
  team_access_version INTEGER NOT NULL DEFAULT 1 CHECK (team_access_version >= 1),
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
  deleted_at TIMESTAMPTZ,
  is_deleted     BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (competition_id, year, edition_no)
);

-- 赛项：机器人平台/项目，与组别并列（v1.1 新增）
CREATE TABLE competition_events (
  id           BIGSERIAL PRIMARY KEY,
  edition_id   BIGINT NOT NULL REFERENCES competition_editions(id) ON DELETE CASCADE,
  code         VARCHAR(16) NOT NULL REFERENCES event_types(code) ON DELETE RESTRICT, -- 稳定赛项类型
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
  deleted_at TIMESTAMPTZ,
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
  deleted_at TIMESTAMPTZ,
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
  deleted_at TIMESTAMPTZ,
  is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (edition_id, event_id, group_id)
);
CREATE INDEX idx_offering_edition ON competition_offerings(edition_id, status) WHERE NOT is_deleted;

CREATE TABLE edition_team_allowlist (
  id BIGSERIAL PRIMARY KEY,
  edition_id BIGINT NOT NULL REFERENCES competition_editions(id) ON DELETE RESTRICT,
  team_id BIGINT NOT NULL REFERENCES teams(id) ON DELETE RESTRICT,
  status VARCHAR(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
  source VARCHAR(16) NOT NULL CHECK (source IN ('manual', 'import')),
  created_by BIGINT NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (edition_id, team_id)
);

-- 服务层不变式（无法用外键表达，由报名校验与每日一致性任务共同保证）：
--   防重复以 offering 为单位（01 §3.6），不等价于 team × event 唯一。
--   同学段可配置多个组别，队伍学段也可变化；资格校验与重复报名约束分别处理。
--   用户选择所选 offering 的学段/组别并冻结到本轮；校验声明与组别配置一致。
--   profile.school_level 只作参考，不用于全队最高学段自动筛选。
--   同届关系由 §7.1 复合外键兜底；服务层仍校验状态、软删除与资格。
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
  contact_email        VARCHAR(255),               -- 可空；通知邮件只发送到已验证账户邮箱
  form_data            JSONB NOT NULL DEFAULT '{}',  -- 固定字段集（决策：动态表单 P1 后此列扩展）
  consent_snapshot     JSONB NOT NULL DEFAULT '{}',  -- 政策版本、同意时间、操作人、覆盖成员、监护授权凭据引用
  status               VARCHAR(20) NOT NULL DEFAULT 'draft',
    -- draft|submitted|org_approved|org_returned|org_rejected|
    -- pending_review|returned|rejected|approved|withdrawn（03 文档 §1）
  approved_submission_no INTEGER,                -- 当前审核通过的轮次，驳回时清空
  current_submission_no INTEGER,                  -- 最近一次不可变提交；首次提交前 NULL
  return_round         INT NOT NULL DEFAULT 0,       -- 退回轮次
  submitted_at         TIMESTAMPTZ,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ,
  is_deleted           BOOLEAN NOT NULL DEFAULT FALSE,
  CHECK ((individual_user_id IS NOT NULL) <> (team_id IS NOT NULL)),  -- 二选一
  CHECK (enrollment_kind IN ('individual', 'team')),
  CHECK ((enrollment_kind = 'individual') = (individual_user_id IS NOT NULL))
);
-- 防重复报名：同队同赛项同组别唯一。
-- 排除 draft（草稿可并存多份）与 withdrawn（撤回后可重新报名）；
-- rejected/org_rejected 仍占用本条报名的唯一位置：修改同一报名再 resubmit，保留编号和历史；不允许另建报名绕过驳回记录。
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
CREATE INDEX idx_reg_team_history ON registrations(team_id, submitted_at DESC, id) WHERE team_id IS NOT NULL AND NOT is_deleted;
-- 公示名单与审核台的主查询路径：按 届次×开放组合×状态 取 approved
CREATE INDEX idx_reg_offering_status
  ON registrations(offering_id, status) WHERE NOT is_deleted;
CREATE INDEX idx_reg_offering ON registrations(offering_id) WHERE NOT is_deleted;

CREATE TABLE registration_submissions (
  registration_id BIGINT NOT NULL REFERENCES registrations(id) ON DELETE RESTRICT,
  submission_no INTEGER NOT NULL CHECK (submission_no >= 1),
  team_id BIGINT REFERENCES teams(id) ON DELETE RESTRICT,
  team_revision_id BIGINT,
  approval_mode VARCHAR(16) NOT NULL DEFAULT 'single' CHECK (approval_mode IN ('single','two_stage')),
  selected_school_level VARCHAR(8),               -- 提交人选择并冻结，不按全队最高学段派生
  snapshot_enc BYTEA NOT NULL,              -- 本轮表单/队伍信息/同意项完整快照
  access_snapshot JSONB NOT NULL DEFAULT '{}', -- 服务端记录 season_id、赛季许可申请 ID/结论及单场准入判定
  submitted_by BIGINT NOT NULL REFERENCES users(id),
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  cancelled_at TIMESTAMPTZ,                        -- 主动取消保留原提交，仅添加取消元数据
  PRIMARY KEY (registration_id, submission_no),
  CHECK ((team_id IS NULL) = (team_revision_id IS NULL)),
  FOREIGN KEY (team_revision_id, team_id) REFERENCES team_change_requests(id, team_id) ON DELETE RESTRICT
);
ALTER TABLE registrations ADD UNIQUE (id, team_id);
ALTER TABLE registration_submissions ADD CONSTRAINT submission_registration_team_fk
  FOREIGN KEY (registration_id, team_id) REFERENCES registrations(id, team_id) ON DELETE RESTRICT;
ALTER TABLE registrations ADD CONSTRAINT registration_current_submission_fk
  FOREIGN KEY (id, current_submission_no) REFERENCES registration_submissions(registration_id, submission_no) ON DELETE RESTRICT;
ALTER TABLE registrations ADD CONSTRAINT registration_approved_submission_fk
  FOREIGN KEY (id, approved_submission_no) REFERENCES registration_submissions(registration_id, submission_no) ON DELETE RESTRICT;
ALTER TABLE registrations ADD CONSTRAINT approved_submission_check CHECK (
  status <> 'approved' OR (approved_submission_no IS NOT NULL AND current_submission_no IS NOT NULL AND approved_submission_no = current_submission_no)
);

CREATE TABLE registration_members (
  id              BIGSERIAL PRIMARY KEY,
  registration_id BIGINT NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  user_id         BIGINT REFERENCES users(id) ON DELETE SET NULL,  -- 快照源，删号不影响
  -- 完整快照加密保存；公开查询显式投影 public_info，不读取 snapshot_enc。
  submission_no INTEGER NOT NULL DEFAULT 1, -- 对应不可变报名轮次，历史成员行不覆盖
  snapshot_enc    BYTEA NOT NULL,        -- 完整快照整体 Fernet 加密，含联系方式与必要证件信息
  public_info     JSONB NOT NULL,        -- 白名单子集 {real_name, role, school_level, grade}，公示名单只读此列
  document_hash  VARCHAR(64),           -- 参赛成员必填，教练可空；不可对外输出
  role            VARCHAR(16) NOT NULL DEFAULT 'member',            -- captain|member|coach
  sort_order      INT NOT NULL DEFAULT 0,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_reg_members_reg ON registration_members(registration_id);
ALTER TABLE registration_members ADD CONSTRAINT member_submission_fk FOREIGN KEY (registration_id, submission_no)
  REFERENCES registration_submissions(registration_id, submission_no) ON DELETE RESTRICT;
CREATE UNIQUE INDEX uniq_registration_member_user ON registration_members(registration_id, submission_no, user_id) WHERE user_id IS NOT NULL;
CREATE UNIQUE INDEX uniq_registration_member_identity ON registration_members(registration_id, submission_no, document_hash) WHERE document_hash IS NOT NULL;

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

ALTER TABLE registration_files ADD CONSTRAINT file_submission_fk FOREIGN KEY (registration_id, round_no)
  REFERENCES registration_submissions(registration_id, submission_no) ON DELETE RESTRICT;

CREATE TABLE approval_records (
  id              BIGSERIAL PRIMARY KEY,
  registration_id BIGINT NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  submission_no INTEGER NOT NULL DEFAULT 1, -- 操作针对的具体提交版本
  step            VARCHAR(16) NOT NULL,    -- org|final|revoke（对应模式）
  round_no        INT NOT NULL DEFAULT 1,
  action          VARCHAR(16) NOT NULL,    -- approve|reject|return|withdraw|cancel_review（reject 也可作用于 approved）
  from_status     VARCHAR(20) NOT NULL,
  to_status       VARCHAR(20) NOT NULL,
  comment         TEXT,                    -- reject/return 必填（服务层校验）
  actor_id        BIGINT NOT NULL REFERENCES users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_approval_reg ON approval_records(registration_id);
ALTER TABLE approval_records ADD CONSTRAINT approval_submission_fk FOREIGN KEY (registration_id, submission_no)
  REFERENCES registration_submissions(registration_id, submission_no) ON DELETE RESTRICT;
-- 审核记录与文件同样"永久保留"：无 is_deleted

-- 同赛季同赛项学生绑定：跨组别唯一，退队/驳回不删除。
ALTER TABLE teams ADD UNIQUE (id, event_code);
CREATE TABLE season_student_team_bindings (
  season_id BIGINT NOT NULL REFERENCES seasons(id) ON DELETE RESTRICT,
  event_code VARCHAR(16) NOT NULL REFERENCES event_types(code) ON DELETE RESTRICT,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  original_team_id BIGINT NOT NULL,
  current_team_id BIGINT NOT NULL,
  source_registration_id BIGINT NOT NULL,
  source_submission_no INTEGER NOT NULL,
  binding_version INTEGER NOT NULL DEFAULT 1 CHECK (binding_version >= 1),
  last_transfer_request_id BIGINT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (season_id, event_code, user_id),
  FOREIGN KEY (original_team_id, event_code) REFERENCES teams(id, event_code) ON DELETE RESTRICT,
  FOREIGN KEY (current_team_id, event_code) REFERENCES teams(id, event_code) ON DELETE RESTRICT,
  FOREIGN KEY (source_registration_id, source_submission_no)
    REFERENCES registration_submissions(registration_id, submission_no) ON DELETE RESTRICT
);
CREATE TABLE team_transfer_requests (
  id BIGSERIAL PRIMARY KEY,
  resubmission_of BIGINT REFERENCES team_transfer_requests(id) ON DELETE RESTRICT,
  season_id BIGINT NOT NULL,
  event_code VARCHAR(16) NOT NULL,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  from_team_id BIGINT NOT NULL,
  to_team_id BIGINT NOT NULL,
  base_binding_version INTEGER NOT NULL CHECK (base_binding_version >= 1),
  base_membership_id BIGINT REFERENCES team_members(id) ON DELETE RESTRICT, -- 无当前关系时为空，由服务校验最近退队记录
  status VARCHAR(16) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','submitted','approved','rejected','withdrawn')),
  reason TEXT NOT NULL CHECK (NULLIF(btrim(reason),'') IS NOT NULL),
  submitted_by BIGINT NOT NULL REFERENCES users(id),
  reviewer_id BIGINT REFERENCES users(id),
  comment TEXT,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (from_team_id <> to_team_id),
  CHECK (reviewer_id IS NULL OR (reviewer_id <> submitted_by AND reviewer_id <> user_id)),
  CHECK (status NOT IN ('approved','rejected') OR (reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL)),
  CHECK (status <> 'rejected' OR NULLIF(btrim(comment),'') IS NOT NULL),
  FOREIGN KEY (season_id, event_code, user_id) REFERENCES season_student_team_bindings(season_id, event_code, user_id) ON DELETE RESTRICT,
  FOREIGN KEY (from_team_id, event_code) REFERENCES teams(id, event_code) ON DELETE RESTRICT,
  FOREIGN KEY (to_team_id, event_code) REFERENCES teams(id, event_code) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX uniq_pending_team_transfer ON team_transfer_requests(season_id,event_code,user_id)
  WHERE status IN ('draft','submitted');
ALTER TABLE season_student_team_bindings ADD FOREIGN KEY (last_transfer_request_id) REFERENCES team_transfer_requests(id) ON DELETE RESTRICT;

CREATE FUNCTION guard_season_team_binding() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Participation binding history cannot be deleted' USING ERRCODE = '55000'; END IF;
  IF TG_OP = 'INSERT' THEN
    IF NOT EXISTS (SELECT 1 FROM registrations r JOIN competition_editions e ON e.id=r.edition_id JOIN registration_members m ON m.registration_id=r.id AND m.submission_no=NEW.source_submission_no AND m.user_id=NEW.user_id AND m.role <> 'coach' WHERE r.id=NEW.source_registration_id AND r.team_id=NEW.current_team_id AND r.status='approved' AND r.approved_submission_no=NEW.source_submission_no AND e.season_id=NEW.season_id) THEN
      RAISE EXCEPTION 'Source must be an approved student submission from the same season and team' USING ERRCODE='23514';
    END IF;
    IF NEW.original_team_id <> NEW.current_team_id OR NEW.last_transfer_request_id IS NOT NULL THEN
      RAISE EXCEPTION 'Initial binding must use original team' USING ERRCODE = '55000';
    END IF;
    NEW.binding_version := 1;
    RETURN NEW;
  END IF;
  IF ROW(NEW.season_id,NEW.event_code,NEW.user_id,NEW.original_team_id,NEW.source_registration_id,NEW.source_submission_no)
     IS DISTINCT FROM ROW(OLD.season_id,OLD.event_code,OLD.user_id,OLD.original_team_id,OLD.source_registration_id,OLD.source_submission_no) THEN
    RAISE EXCEPTION 'Original participation binding is immutable' USING ERRCODE = '55000';
  END IF;
  IF NEW.current_team_id = OLD.current_team_id THEN
    IF NEW.binding_version <> OLD.binding_version OR NEW.last_transfer_request_id IS DISTINCT FROM OLD.last_transfer_request_id THEN
      RAISE EXCEPTION 'Binding metadata requires approved transfer' USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM team_transfer_requests r WHERE r.id = NEW.last_transfer_request_id
    AND r.status = 'approved' AND r.season_id = OLD.season_id AND r.event_code = OLD.event_code AND r.user_id = OLD.user_id
    AND r.base_binding_version = OLD.binding_version AND r.from_team_id = OLD.current_team_id AND r.to_team_id = NEW.current_team_id) THEN
    RAISE EXCEPTION 'Team transfer requires matching approved request' USING ERRCODE = '55000';
  END IF;
  NEW.binding_version := OLD.binding_version + 1;
  RETURN NEW;
END;
$$;
CREATE TRIGGER season_team_binding_guard BEFORE INSERT OR UPDATE OR DELETE ON season_student_team_bindings
  FOR EACH ROW EXECUTE FUNCTION guard_season_team_binding();

-- 晋级准入可关联来源轮次，阵容取该轮学生快照，导入名单自身不自动授予新成员资格。
ALTER TABLE edition_team_allowlist ADD COLUMN qualification_registration_id BIGINT;
ALTER TABLE edition_team_allowlist ADD COLUMN qualification_submission_no INTEGER;
ALTER TABLE edition_team_allowlist ADD CHECK ((qualification_registration_id IS NULL) = (qualification_submission_no IS NULL));
ALTER TABLE edition_team_allowlist ADD FOREIGN KEY (qualification_registration_id,qualification_submission_no)
  REFERENCES registration_submissions(registration_id,submission_no) ON DELETE RESTRICT;
```

## 6. 奖项 / 获奖名单 / 证书

```sql
CREATE TABLE awards (
  id          BIGSERIAL PRIMARY KEY,
  edition_id  BIGINT NOT NULL REFERENCES competition_editions(id) ON DELETE CASCADE,
  offering_id BIGINT REFERENCES competition_offerings(id) ON DELETE CASCADE,
    -- NULL = 届次通用奖项（面向参赛学生的届次通用奖等，无单位/组织/教练奖，不落到具体赛项×组别）
  rank_level  VARCHAR(16) NOT NULL,          -- first|second|third|excellence|custom
  name        VARCHAR(64) NOT NULL,          -- '一等奖'
  quota       INT,                           -- 名额（软限制，服务层校验）
  sort_order  INT NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ,
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
  version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1), -- 解锁编辑递增，异步回调必须匹配
  lock_note    TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE NULLS NOT DISTINCT (edition_id, offering_id)
);

CREATE TABLE award_records (
  id              BIGSERIAL PRIMARY KEY,
  edition_id      BIGINT NOT NULL REFERENCES competition_editions(id) ON DELETE RESTRICT,
  roster_id       BIGINT NOT NULL REFERENCES award_rosters(id) ON DELETE CASCADE,
  award_id        BIGINT NOT NULL REFERENCES awards(id) ON DELETE RESTRICT,
  registration_id BIGINT NOT NULL REFERENCES registrations(id) ON DELETE RESTRICT,  -- 必须 approved，获奖对象仅学生参赛成果
  submission_no INTEGER NOT NULL DEFAULT 1,        -- 固定获奖所依据的审核通过轮次
  recipient_kind  VARCHAR(16) NOT NULL,      -- individual|team（冗余自报名）
  batch_no        VARCHAR(40) NOT NULL,      -- 冗余自报名，导入对账用
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ,
  is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
  FOREIGN KEY (registration_id, submission_no) REFERENCES registration_submissions(registration_id, submission_no) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX uniq_current_award_registration ON award_records(roster_id, registration_id) WHERE NOT is_deleted;

CREATE TABLE award_import_pending (
  id           BIGSERIAL PRIMARY KEY,
  roster_id    BIGINT NOT NULL REFERENCES award_rosters(id) ON DELETE CASCADE,
  batch_no     VARCHAR(40),
  raw_row_enc  BYTEA,                        -- 原始行整体 Fernet 加密；处置后清空
  expires_at   TIMESTAMPTZ NOT NULL,         -- 最长 30 天；过期清除密文并标为 rejected
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
  serial_prefix VARCHAR(16) UNIQUE NOT NULL, -- 'CS-0012'，建届次时生成一次后不可变
  next_no      BIGINT NOT NULL DEFAULT 1
);

CREATE TABLE certificates (
  id             BIGSERIAL PRIMARY KEY,
  serial_no      VARCHAR(40) UNIQUE NOT NULL,   -- {serial_prefix}-{5位补零}，如 CS-0012-00345
  serial_prefix  VARCHAR(16) NOT NULL,          -- 冻结自 certificate_sequences，不随届次变更
  serial_no_seq  BIGINT NOT NULL,               -- 冻结的序号；与 serial_no 一并成为不可变历史事实
  award_record_id BIGINT NOT NULL REFERENCES award_records(id) ON DELETE RESTRICT,
  edition_id     BIGINT NOT NULL REFERENCES competition_editions(id) ON DELETE RESTRICT,
  registration_id BIGINT NOT NULL REFERENCES registrations(id) ON DELETE RESTRICT,
  recipient_member_id BIGINT NOT NULL REFERENCES registration_members(id) ON DELETE RESTRICT,
  submission_no INTEGER NOT NULL DEFAULT 1,
  roster_version INTEGER NOT NULL DEFAULT 1,       -- 排队时冻结名单版本，旧回调不得发放新版名单
  display_name   VARCHAR(64) NOT NULL,          -- 报名成员姓名快照，团队也逐人发证
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
-- 每个获奖记录的每位参赛成员至多一张非作废证书，失败任务重试复用原行。
CREATE UNIQUE INDEX uniq_cert_active_per_member
  ON certificates(award_record_id, recipient_member_id) WHERE status <> 'revoked';
CREATE UNIQUE INDEX uniq_cert_reissue_once ON certificates(reissue_of) WHERE reissue_of IS NOT NULL;
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
  deleted_at TIMESTAMPTZ,
  is_deleted     BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE notice_reads (
  notice_id BIGINT NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
  user_id   BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  read_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (notice_id, user_id)
);

CREATE TABLE async_outbox (
  id BIGSERIAL PRIMARY KEY,
  topic VARCHAR(64) NOT NULL,                       -- 由后端允许清单生成
  business_key VARCHAR(128) UNIQUE NOT NULL,
  payload JSONB NOT NULL,                          -- 仅业务 ID/版本/locale，不放密码、验证码或证件
  status VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','dispatched','failed')),
  attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  lease_until TIMESTAMPTZ,
  dispatched_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_outbox_pending ON async_outbox(next_attempt_at) WHERE status = 'pending';

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

### 7.1 同届约束与写入规则

以下 DDL 与前面的建表语句一起执行；Django 初始化时以迁移显式保留复合外键。

```sql
ALTER TABLE competition_events ADD UNIQUE (id, edition_id);
ALTER TABLE competition_groups ADD UNIQUE (id, edition_id);
ALTER TABLE competition_offerings ADD UNIQUE (id, edition_id);
ALTER TABLE registrations ADD UNIQUE (id, edition_id);
ALTER TABLE awards ADD UNIQUE (id, edition_id);
ALTER TABLE award_rosters ADD UNIQUE (id, edition_id);
ALTER TABLE award_records ADD UNIQUE (id, edition_id);
ALTER TABLE award_records ADD UNIQUE (id, registration_id, submission_no);
ALTER TABLE registration_members ADD UNIQUE (id, registration_id, submission_no);
ALTER TABLE certificates ADD UNIQUE (id, award_record_id, recipient_member_id);

ALTER TABLE competition_offerings
  ADD CONSTRAINT offering_event_edition_fk FOREIGN KEY (event_id, edition_id)
    REFERENCES competition_events(id, edition_id) ON DELETE CASCADE,
  ADD CONSTRAINT offering_group_edition_fk FOREIGN KEY (group_id, edition_id)
    REFERENCES competition_groups(id, edition_id) ON DELETE CASCADE;
ALTER TABLE registrations
  ADD CONSTRAINT registration_offering_edition_fk FOREIGN KEY (offering_id, edition_id)
    REFERENCES competition_offerings(id, edition_id) ON DELETE RESTRICT;
ALTER TABLE awards
  ADD CONSTRAINT award_offering_edition_fk FOREIGN KEY (offering_id, edition_id)
    REFERENCES competition_offerings(id, edition_id) ON DELETE RESTRICT;
ALTER TABLE award_rosters
  ADD CONSTRAINT roster_offering_edition_fk FOREIGN KEY (offering_id, edition_id)
    REFERENCES competition_offerings(id, edition_id) ON DELETE RESTRICT;
ALTER TABLE award_records
  ADD CONSTRAINT record_roster_edition_fk FOREIGN KEY (roster_id, edition_id)
    REFERENCES award_rosters(id, edition_id) ON DELETE RESTRICT,
  ADD CONSTRAINT record_award_edition_fk FOREIGN KEY (award_id, edition_id)
    REFERENCES awards(id, edition_id) ON DELETE RESTRICT,
  ADD CONSTRAINT record_registration_edition_fk FOREIGN KEY (registration_id, edition_id)
    REFERENCES registrations(id, edition_id) ON DELETE RESTRICT;
ALTER TABLE certificates
  ADD CONSTRAINT certificate_record_edition_fk FOREIGN KEY (award_record_id, edition_id)
    REFERENCES award_records(id, edition_id) ON DELETE RESTRICT,
  ADD CONSTRAINT certificate_registration_fk FOREIGN KEY (award_record_id, registration_id, submission_no)
    REFERENCES award_records(id, registration_id, submission_no) ON DELETE RESTRICT,
  ADD CONSTRAINT certificate_member_registration_fk FOREIGN KEY (recipient_member_id, registration_id, submission_no)
    REFERENCES registration_members(id, registration_id, submission_no) ON DELETE RESTRICT,
  ADD CONSTRAINT certificate_reissue_recipient_fk FOREIGN KEY (reissue_of, award_record_id, recipient_member_id)
    REFERENCES certificates(id, award_record_id, recipient_member_id) ON DELETE RESTRICT;
```

- 队员只允许学生，教练不写入 team_members；队员全平台同时只有一条 left_at IS NULL 的归属；本人可自主退队，普通管理员入退队仍走批准流程；当前归属释放不删除同赛季同赛项绑定，回上次退出队伍可普通入队，跨队须平台特批。批准时锁相关队伍、按 user_id 升序锁学生账户，复查当前归属；唯一索引兜底并发入队，冲突返回 40908。入退队写 joined_at/left_at 并关联申请 ID、操作人和理由到审计，不覆盖旧关系；管理员发起的待审退队不释放归属。解散队伍时同事务结束当前成员关系并审计，历史快照保留。
- 首次通过团队报名时为每位学生写同赛季同赛项绑定；来源提交必须是本队已通过版本且包含本人，其场次必须归属该赛季，服务层校验。关闭届次不删绑定，入队仅检查所有未归档赛季的相同赛项绑定；一人多证不自动合并。原队回归仍校验最近退出队伍及全部有效绑定，平台批准换队会改变允许返回的队伍，不能借反复退队回避。guard_season_team_binding 只守卫绑定写入，不代替平台权限、当前成员关系或报名更正校验。
- 平台特批事务需同时校验并切换全部受影响的未归档赛季绑定；多赛季逐季生成关联申请并统一审核执行，缺少任一必要批准即整体拒绝，不改写已归档绑定；原队报名取消/驳回并在重提时排除该学生，目标队已提交报名须另行更正，旧快照保留。已有锁定名单/非作废证书按原规则阻断；全部绑定版本和成员关系校验失败整体回滚。学生自主退队时若为队长则清空 captain_id（由单位管理员另行配置），同步递增队伍成员版本、使旧队伍变更申请失效，提交服务取审核成员与当前有效成员交集，不得重新带回已退队学生。
- 队伍修改批准时同一事务先锁正式队伍再锁申请，创建申请批准时锁申请，检查申请人/审核人分离、有效单位、成员、base_revision_id 与 base_membership_version；只有 approved 提案能成为正式版本。resubmission_of 只允许关联同申请人、同单位/队伍的原申请，服务层校验，不能借复制他人申请读取提案。创建批准前 team_id/result_org_id 为空，不建立可用主数据。
- 每次报名提交在同一事务按赛季→届次→队伍→赛季许可→报名顺序加锁，创建新 submission_no、对应成员/文件行，再切换 current_submission_no；团队绑定该队当时已审核版本。历史成员/文件/审核记录不可覆盖或物理删除，工作副本变化不更新旧提交，证书始终引用旧成员行。
- 队伍准入模式/名单变更均递增 team_access_version，导入预览及确认绑定该版本；确认过期返回 40906。
- 队伍准入按 edition_id + team_id 读取 active 行；名单变更和报名提交/重提/批准共用届次行锁，避免并发撤销与检查竞态。open/allowlist 是服务层条件，外键不会自动校验准入状态。
- 获奖写入 service 必须取 status=approved 且 approved_submission_no=current_submission_no 的明确轮次，冻结到 award_records.submission_no；公示、发奖、统计只取该通过轮次的成员，历史视图才读取全部轮次。
- 证件更正批准事务内锁申请与档案，校验审核权限/非自审、base_identity_version、唯一性，再将请求置 approved 并更新档案，旧绑定在事务提交时释放；同事务递增 users.token_version。guard_profile_identity 阻止绕开批准申请的号码/类型/国家变更；仅相同身份的密文重加密不触发更正。
- 获奖写入 service 在同一事务锁定名单、奖项和报名，校验奖项与名单的 offering 相同（含同时为 NULL）；具体组合名单只接收该 offering 的 approved 报名，通用名单可接收本届任一组合。
- 上述外键保证同届；组合匹配、审核状态与锁定态是额外业务校验，不能因外键存在而省略。已被引用的赛事配置和报名归属不再改挂，只能作废后重建；操作均走 service。
- 带 is_deleted 的表同时维护 deleted_at；有过提交的报名软删除不影响管理历史查询，历史查询须显式包含软删除记录并按范围鉴权；历史表禁止应用层硬删除，DDL 的删除策略仅用于外键防护，不授权业务删除。

- 学生单位交接仅在原/目标双方核验和学生授权完成后生效；普通成员 CRUD/导入不得直接改主属关系。完成事务锁 users 与当前主属关系，核对 base_affiliation_version、原单位、无当前队伍，结束旧关系并追加新关系，递增 affiliation_version/token_version；新旧关系更新和 completed 状态同一事务，失败回滚。原创建单位仅为来源审计，重置权按当前有效主属单位及其管理范围实时查询。重置和交接共用学生行锁，旧单位的过期重置请求 40906/40301。
- 队伍创建仅平台审核并原子建立该赛季 approved 许可；team_season_registrations 审核/撤销仅平台，原提案与结论不覆盖，驳回/撤回后复制关联新行，关联须同队同赛季。提交/重提仅当前 active 赛季且存在该队 approved 许可；审批通过复核原赛季 active 与许可。创建/激活审核、许可撤销与报名共用锁序，撤销不改写历史但阻断新提交与存量通过。
- 场次的 season_id 首次提交后不可改挂；提交、重提、批准和赛季归档统一按 season→场次顺序加锁并复核 active 状态，避免归档竞态。归档前校验无未完成赛事/待审报名；团队批准报名先建立 season_student_team_bindings，跨赛事跨组别共用唯一键。赛季归档仅停止未来入队限制，不删绑定。晋级来源轮次必须属于目标场次同一赛季，服务层复核。

## 8. 设计说明与遗留项

1. **多态 scope_id**（user_roles / notices.audience_id）未做数据库外键，完整性依赖服务层与每日一致性检查任务——这是灵活性换保证成本，明确接受。
2. **敏感副本**：报名提交快照、成员快照、单位/队伍申请提案及 raw_row_enc 都使用 Fernet；快照仅在授权 service 内解密再按白名单输出。导入原始文件同样加密后存私有桶，和待确认密文一起在处置完成或最长 30 天后清除；按日任务保留脱敏冲突摘要，删除文件/密文也记审计。密钥轮换覆盖所有密文字段，备份恢复同时恢复对应版本密钥。

   **证件** 存 document_type/country + document_number_enc + document_hash；类型/签发国与规范化号码共同参与 HMAC-SHA256，不把护照号码当身份证。当前绑定唯一，批准更正后旧号释放；历史申请及报名中的旧证件摘要不再占用唯一索引。
   - 方案取应用层 Fernet（`cryptography` 库），不选 pgcrypto。理由：数据库密文随 `pg_dump` 一起备份恢复，不依赖扩展存在；密钥轮换可在应用层做重加密任务，不需停机执行 SQL 迁移。
   - 密钥走 `FIELD_ENCRYPTION_KEY` 环境变量，禁止入仓；hash 的 pepper 单独一个变量（`DOC_HASH_PEPPER`），轮换 pepper 需重算全表 hash，属破坏性变更。
   - 任何 API 不回传证件明文，日志只记末四位（DEVELOPMENT.md §2.3）；公示名单物理上读不到该列（`registration_members.public_info` 白名单）。
3. **赛项与组别正交**（v1.1）：不合并成「组别」一列的复合值，因为评奖、公示、名额、时间窗都按二者之一独立聚合（「大学组全部赛项通过率」与「V5RC 各组别通过率」是两个真实报表需求）。合并会让每类统计都要拆字符串。
4. **`competition_offerings` 的删除策略**：赛项或组别被删则其组合行级联删除，但 registrations 引用 offering 为 `RESTRICT`——已有报名的组合无法被删除，只能停用（`status=disabled`）。这是有意的：不允许因为清理配置而连带影响报名数据。
5. `competition_admins` 冗余表问题见 §4 注释，P1 合并。
6. **organizations 不设 parent_id 冗余列**（v1.1）：树关系只由 `path` 表达，父级用 `get_parent()` 截断得出。保留父指针就会与 `competition_admins` 犯同一个错——两处事实源、一个更新漏了就不一致。
7. **证书编号不可变**：见 §6 certificate_sequences；在建 queued 行的事务内取号，提交后不回收，渲染失败只重试原行。事务整体回滚时该号未对外出现，可随事务回滚；无需另建独立取号事务。
8. 大表预估（百万级前无需分区）：`registrations`、`registration_members`、`audit_logs`。`audit_logs` 上一年热表，P1 考虑按月分区。
9. JSONB 使用原则：只用于**配置快照与低频筛选**（材料要求、成员快照、form_data）；高频筛选列一律实体列 + B-tree。公示字段拆成 `public_info` 与加密 `snapshot_enc` 两列，是因为白名单过滤必须发生在数据库读取层，而不是取回整行再在 Python 里删字段——后者一旦有人写了 `SELECT *` 就泄露。
10. 证件照对象使用 profiles/{user_id}/{uuid}.jpg，上传经授权，先读尺寸并限制最多 2000 万像素，再完整解码；透明图铺白底，统一重编码 JPEG 并剥离 EXIF；数据库只保存 key。替换时先上传新对象，事务内锁定本人档案并更新引用，提交后删除旧对象；失败回收新对象，孤儿对象由定时任务延迟清理（跳过最近 24 小时对象并复核引用，避免误删上传中的对象）。删除同样先清引用再提交后删对象，失败重试。签名链接短期有效且须重新鉴权，公开 serializer 不包含 key 或照片链接。照片不默认进入报名快照或证书。

## 9. 首批ORM实施映射

首批迁移覆盖认证、邮箱验证码、RBAC、单位基础读取、赛事基础读取、队伍提案/许可及报名审核核心；完整领域设计中的单位申请/交接、证件更正、文件、奖项/证书等表并未全部实现。85项SQL设计约束测试通过不等于ORM已实现全部设计；已实现部分另在真实PG16运行迁移和API/并发反例，未完成清单见backend/README。

| 位置 | 首批物理实现与原因 |
| --- | --- |
| `verification_codes` | accounts/0003按§2建立验证码表及idx_vcode_lookup，另加attempts≤5检查约束；code_hash为带随机salt的HMAC-SHA256，delivery_secret_enc仅短期Fernet密文；消费与失败次数更新使用行锁。outbox payload仅ID和locale |
| `registrations` | 新增`version`（正整数，初值1，乐观并发控制）、`draft_enc BYTEA NOT NULL`（Fernet加密工作副本）、`selected_school_level VARCHAR(8) NULL`（草稿声明学段）；contact/form/consent旧列保留占位，不写敏感工作副本，服务层从draft_enc投影 |
| `api_idempotency_records` | 新增id主键、actor_id用户外键、key VARCHAR(128)、action VARCHAR(160)、request_hash VARCHAR(64)、可空result JSONB、created_at；唯一(actor_id,key,action)。result仅存业务对象引用，缓存命中仍重新鉴权，不持有联系人或模型正文 |
| `role_permissions`、`registration_submissions`、`season_student_team_bindings` | 使用自增bigint代理主键id以适配Django关系；原复合业务键保留唯一约束，复合外键继续引用该唯一键，不能因代理主键取消防重复 |
| 外键命名 | Django关系字段在数据库中默认附加`_id`，例如submitted_by_id/reviewer_id/granted_by_id/created_by_id/actor_id；API仍使用12契约字段名。users.password映射既有password_hash，last_login映射last_login_at，稳定赛项外键显式映射event_code |
| PostgreSQL专用约束 | registrations/0002_postgresql_integrity增加同届/同队/同轮复合引用、审核通过轮次守卫、submission/member/approval历史不可变触发器；取消仅可补充取消元数据。SQLite跳过这些PG专项，不作为生产并发验证 |

实际物理列及可逆迁移以backend/apps/*/migrations及backend/core/migrations为部署入口。技术映射不授予额外权限，不新增AI数据库访问；后续实现其余领域前仍须补齐相应模型/迁移及原设计约束反例。
11. 统计不做预聚合物化视图（P0 数据量下实时 count + Redis 短缓存足够），P1 再上汇总表。
