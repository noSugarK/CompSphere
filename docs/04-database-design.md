# 04 数据库设计（字段级 DDL）

**版本**：v1.0（2026-11-16）。目标库 PostgreSQL 16，Django 5 迁移生成前的目标 schema。

约定：
- 所有表含 `id BIGSERIAL PRIMARY KEY`、`created_at TIMESTAMPTZ NOT NULL DEFAULT now()`、`updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`、`is_deleted BOOLEAN NOT NULL DEFAULT FALSE`（软删除，见 PRD §4.3）。
- 金额用 `NUMERIC(10,2)`；时间一律 `TIMESTAMPTZ`（UTC）。
- 外键删除策略：主数据 restrict，关系表 cascade。
- Django 层面用 `uuid7`/snowflake 可选；第一版主键用自增 + 对外暴露 `public_code`（业务流水号）避免遍历。

---

## 1. ER 总览

```
users ── user_profiles
  │        organization_members ── organizations(parent_id 树)
  └─ user_roles ── roles ── role_permissions ── permissions
teams ── team_members ── users
competitions ── competition_organizations ── organizations
  ├─ competition_admins ── users
  └─ competition_editions ── competition_groups
                              ├─ registrations ── registration_members / registration_files
                              │                    └─ approval_records
                              ├─ awards ── award_rosters / award_records ── certificates
                              └─ notices
audit_logs（独立）
```

## 2. 用户与组织

```sql
CREATE TABLE users (
  id            BIGSERIAL PRIMARY KEY,
  username      VARCHAR(64) UNIQUE NOT NULL,
  email         VARCHAR(255) UNIQUE,
  phone         VARCHAR(20) UNIQUE,
  password_hash VARCHAR(255) NOT NULL,          -- Argon2
  status        VARCHAR(16) NOT NULL DEFAULT 'active',  -- active|disabled|pending
  last_login_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE user_profiles (
  id            BIGSERIAL PRIMARY KEY,
  user_id       BIGINT UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  real_name     VARCHAR(64),
  gender        VARCHAR(10),                    -- male|female|other|unknown
  avatar_url    VARCHAR(512),
  birth_date    DATE,
  id_number_enc BYTEA,                          -- 身份证号（加密列，按需收集；未收集为 NULL）
  id_number_hash VARCHAR(64),                   -- SHA-256，用于导入匹配（不存明文）
  student_no    VARCHAR(64),                    -- 学号
  staff_no      VARCHAR(64),                    -- 工号
  person_type   VARCHAR(16) NOT NULL DEFAULT 'participant',  -- participant|coach|staff
  major         VARCHAR(128),
  grade         VARCHAR(32),                    -- '2023' / '大一' / '硕士1年级'…
  title         VARCHAR(64),                    -- 职务/职称
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE organizations (
  id          BIGSERIAL PRIMARY KEY,
  code        VARCHAR(32) UNIQUE NOT NULL,      -- 单位编码
  name        VARCHAR(128) NOT NULL,
  org_type    VARCHAR(16) NOT NULL,             -- school|college|enterprise|association|host|organizer|other
  parent_id   BIGINT REFERENCES organizations(id) ON DELETE RESTRICT,
  status      VARCHAR(16) NOT NULL DEFAULT 'active',   -- active|suspended
  join_request_status VARCHAR(16) DEFAULT 'approved',  -- pending|approved|rejected（入驻申请）
  logo_url    VARCHAR(512),
  contact_info JSONB,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX idx_org_parent ON organizations(parent_id) WHERE NOT is_deleted;

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
  status      VARCHAR(16) NOT NULL DEFAULT 'active',    -- active|disbanded
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
  name           VARCHAR(128) NOT NULL,       -- '2026 年第一届全国大学生科技创新竞赛'
  enroll_start   TIMESTAMPTZ,
  enroll_end     TIMESTAMPTZ,
  event_start    TIMESTAMPTZ,
  event_end      TIMESTAMPTZ,
  approval_mode  VARCHAR(16) NOT NULL DEFAULT 'single',  -- single|two_stage
  status         VARCHAR(16) NOT NULL DEFAULT 'draft',   -- draft|published|closed
  notice         TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted     BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (competition_id, year, edition_no)
);

CREATE TABLE competition_groups (
  id                  BIGSERIAL PRIMARY KEY,
  edition_id          BIGINT NOT NULL REFERENCES competition_editions(id) ON DELETE CASCADE,
  name                VARCHAR(64) NOT NULL,          -- 本科组/研究生组/企业组…
  enrollment_type     VARCHAR(16) NOT NULL,          -- individual|team|both
  target_audience     JSONB,                         -- ["student","teacher","enterprise_staff"]
  grade_limits        JSONB,                         -- ["大一","大二"] / 年级代码，NULL=不限
  major_limits        JSONB,                         -- 专业限制（第一版仅提示校验）
  min_members         INT NOT NULL DEFAULT 1,
  max_members         INT NOT NULL DEFAULT 1,
  coach_required      BOOLEAN NOT NULL DEFAULT FALSE,
  material_requirements JSONB NOT NULL DEFAULT '[]', -- [{key,label,required,formats,max_mb}]
  fee                 NUMERIC(10,2) NOT NULL DEFAULT 0,
  fee_note            VARCHAR(255),
  status              VARCHAR(16) NOT NULL DEFAULT 'enabled',  -- enabled|disabled
  sort_order          INT NOT NULL DEFAULT 0,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted          BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (edition_id, name),
  CHECK (min_members >= 1 AND max_members >= min_members)
);
```

## 5. 报名与审核

```sql
CREATE TABLE registrations (
  id                   BIGSERIAL PRIMARY KEY,
  batch_no             VARCHAR(40) UNIQUE NOT NULL,  -- 报名流水号 REG-{edition_id}-{8位随机}，导入匹配主键
  edition_id           BIGINT NOT NULL REFERENCES competition_editions(id) ON DELETE RESTRICT,
  group_id             BIGINT NOT NULL REFERENCES competition_groups(id) ON DELETE RESTRICT,
  enrollment_kind      VARCHAR(16) NOT NULL,         -- individual|team（提交时按组别规则落定）
  individual_user_id   BIGINT REFERENCES users(id) ON DELETE RESTRICT,
  team_id              BIGINT REFERENCES teams(id) ON DELETE RESTRICT,
  submitted_by         BIGINT NOT NULL REFERENCES users(id),  -- 本人/队长/代报教练
  coach_user_id        BIGINT REFERENCES users(id),           -- 指导教师（快照 + 引用）
  contact_name         VARCHAR(64),
  contact_phone        VARCHAR(20),
  contact_email        VARCHAR(255),
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
-- 防重复报名：同人同届次（个人报名）唯一。
-- 排除 draft（草稿可并存多份）与 withdrawn（撤回后可重新报名）；
-- rejected 不排除 → 被驳回者不能再次提交，这是有意的第一版口径，若产品要求"驳回可重报"则把 rejected 一并加入排除列表。
CREATE UNIQUE INDEX uniq_reg_individual
  ON registrations(edition_id, individual_user_id)
  WHERE enrollment_kind = 'individual'
    AND status NOT IN ('draft','withdrawn') AND NOT is_deleted;
-- 防重复报名：同队同届次唯一（同上口径）
CREATE UNIQUE INDEX uniq_reg_team
  ON registrations(edition_id, team_id)
  WHERE enrollment_kind = 'team'
    AND status NOT IN ('draft','withdrawn') AND NOT is_deleted;
CREATE INDEX idx_reg_edition_status ON registrations(edition_id, status) WHERE NOT is_deleted;
CREATE INDEX idx_reg_group ON registrations(group_id) WHERE NOT is_deleted;

CREATE TABLE registration_members (
  id              BIGSERIAL PRIMARY KEY,
  registration_id BIGINT NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  user_id         BIGINT REFERENCES users(id) ON DELETE SET NULL,  -- 快照源，删号不影响
  snapshot        JSONB NOT NULL,   -- {real_name, id_number_hash, student_no, org_id, org_name, grade, major, phone}
  role            VARCHAR(16) NOT NULL DEFAULT 'member',            -- captain|member|coach
  sort_order      INT NOT NULL DEFAULT 0,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_reg_members_reg ON registration_members(registration_id);

CREATE TABLE registration_files (
  id              BIGSERIAL PRIMARY KEY,
  registration_id BIGINT NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  material_key    VARCHAR(64) NOT NULL,    -- 对应组别 material_requirements[].key
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
  id         BIGSERIAL PRIMARY KEY,
  edition_id BIGINT NOT NULL REFERENCES competition_editions(id) ON DELETE CASCADE,
  group_id   BIGINT REFERENCES competition_groups(id) ON DELETE CASCADE,  -- NULL=届次通用奖项
  rank_level VARCHAR(16) NOT NULL,          -- first|second|third|excellence|custom
  name       VARCHAR(64) NOT NULL,          -- '一等奖'
  quota      INT,                           -- 名额（软限制，服务层校验）
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (edition_id, group_id, name)
);

CREATE TABLE award_rosters (
  id           BIGSERIAL PRIMARY KEY,
  edition_id   BIGINT NOT NULL REFERENCES competition_editions(id) ON DELETE CASCADE,
  group_id     BIGINT NOT NULL REFERENCES competition_groups(id) ON DELETE CASCADE,
  status       VARCHAR(20) NOT NULL DEFAULT 'editing',
    -- editing|under_approval|confirmed|issued（03 文档 §5）
  submitted_by BIGINT REFERENCES users(id),
  approved_by  BIGINT REFERENCES users(id),
  approved_at  TIMESTAMPTZ,
  lock_note    TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (edition_id, group_id)
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

CREATE TABLE certificates (
  id             BIGSERIAL PRIMARY KEY,
  serial_no      VARCHAR(40) UNIQUE NOT NULL,   -- CS-{届次ID四位补零}-{序号}，如 CS-0012-00345（PRD §3.7）
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
  reissue_of     BIGINT REFERENCES certificates(id),
  generated_at   TIMESTAMPTZ,
  issued_at      TIMESTAMPTZ,
  revoked_at     TIMESTAMPTZ,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- 一个获奖记录至多一张有效证书
CREATE UNIQUE INDEX uniq_cert_active_per_award
  ON certificates(award_record_id) WHERE status <> 'revoked';
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
2. **身份证号** 存 `id_number_enc`（pgcrypto/AES，密钥走环境变量）+ `id_number_hash`（导入匹配）；任何 API 不回传明文，日志不记录。列加密方案 P1 复核（也可应用层 Fernet）。
3. `competition_admins` 冗余表问题见 §4 注释，P1 合并。
4. 大表预估（百万级前无需分区）：`registrations`、`registration_members`、`audit_logs`。`audit_logs` 上一年热表，P1 考虑按月分区。
5. JSONB 使用原则：只用于**配置快照与低频筛选**（材料要求、成员快照、form_data）；高频筛选列一律实体列 + B-tree。
6. 统计不做预聚合物化视图（P0 数据量下实时 count + Redis 短缓存足够），P1 再上汇总表。
