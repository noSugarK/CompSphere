# 开发规范

**版本**：v1.1（2026-11-16）
**适用范围**：`backend/`、`frontend/`、`docker/`、`docs/` 全部代码与文案。
**分工**：提交、分支与 PR 评审流程见 [CONTRIBUTING.md](CONTRIBUTING.md)；本文规定代码怎么写、界面怎么做、日志怎么打。业务与架构以 `docs/01-09` 为准，界面与工程实践以本文为准；冲突时先改文档再改代码，不允许代码单方面偏离。

v1.1 变更：§2.5 补发链事件字段名对齐 03/04（`reissue_of` / `supersedes_serial`）；§11 拆为「已修复 / 仍开放」两段，记录本轮闭合的六项文档缺陷。

> 标注 **强制** 的条目在评审时逐条对照，不满足即打回；标注 **建议** 的条目可协商。

---

## 1. 后端代码规范

### 1.1 分层（强制）

沿用 05 文档约定，不得越层：

```
views（薄，只做 HTTP 语义与权限声明）
  -> serializers（校验、塑形，不写业务规则）
    -> services（业务规则、状态机、事务边界）
      -> models（存储、约束，不写业务分支）
```

- view 里禁止出现 `if request.user.role == ...` 之类的角色字符串判断，一律走 `ScopedRolePermission`（02 文档 §5）。
- 跨 app 写操作必须经 `apps/<x>/services.py`，禁止 import 其他 app 的 model 直接 `.save()`。
- 状态字段禁止 `obj.status = "approved"` 直接赋值后保存，必须 `transition(obj, action, actor, comment)`（03 文档全局规则 4）。

### 1.2 工具链

| 用途 | 工具 | 说明 |
| --- | --- | --- |
| 格式化 | `ruff format` | 唯一格式化器，不并行使用 black |
| Lint | `ruff check` | 配置入库 `pyproject.toml`，禁止 `# noqa` 不带规则码 |
| 类型 | `mypy` | `apps/*/services.py` 与 `core/` 为 strict；serializers/models 逐步收敛 |
| 迁移 | Django migrations | 迁移文件必须人工检查 `RunPython` 的数据影响后再提交 |
| 测试 | `pytest` + `pytest-django` | 禁用 `unittest` 风格的 setUp 写测试 |

**强制**：`pre-commit` 配置 ruff + mypy，本地钩子与 CI 同一份配置，避免「本地过 CI 挂」。

### 1.3 命名

- 模型类名用单数，表名 Django 默认。
- 状态常量集中在 `core/constants.py`，与 03 文档状态枚举一一对应；禁止在业务代码里出现裸状态字符串（07 文档「三处常量单一来源」）。
- 权限码字符串同样来自 `core/constants.py` 的 `PERMISSIONS`，与 02 文档 §2 清单同源。
- 布尔字段 `is_`/`has_` 前缀；时间字段 `_at` 后缀（`created_at`），日期 `_date`。
- 私有函数 `_` 前缀；不做「为将来可能用到」的抽象，出现第三次重复再提取。

### 1.4 数据库访问

- 禁止在循环里查询（N+1）。列表接口 serializer 需要关联字段时，view 上必须声明 `select_related`/`prefetch_related`。
- 写事务范围尽量小；「一次业务动作 = 一个 `transaction.atomic()`」放在 service 层，不放 view。
- 报名提交这类多表写（registrations + 成员快照 + files + approval 初始记录）必须在同一事务，且依赖唯一索引兜底（PRD §6 幂等要求）。
- 统计类查询只读走 `stats` app，禁止管理端页面在 view 里手写聚合 SQL。

### 1.5 异常与错误码

- 业务失败抛 `core.exceptions` 下的领域异常，由统一异常处理器映射为 06 文档 §1.2 的错误码段。
- 禁止 `except Exception: pass`；捕获后要么处理、要么记日志再抛，两者都没有就不要捕获。
- 面向用户的 `message` 用中文完整句，说明「发生了什么 + 用户能做什么」；技术细节写日志，不写进 message（防泄露内部结构与敏感字段）。

```python
# 反例：把内部信息抛给用户
raise ValidationError({"detail": f"IntegrityError: duplicate key ... batch_no=REG-12-3F9A21C7"})

# 正例：用户可读，细节入日志
log.warning("registration.duplicate", extra={"edition_id": 12, "user_id": 900, "batch_no": batch_no})
raise DuplicateRegistration(edition_id=12, group_id=3)   # -> 409 40901 "该组别你已报名，请勿重复提交"
```

### 1.6 注释与文档字符串

- 注释解释 **为什么**，尤其是绕开直觉的写法（例如「这里不加索引是因为写入远多于读取」）。
- 与状态机、权限、幂等相关的函数必须有 docstring，写明前置条件与副作用。
- 删除代码就删掉，不留注释掉的死代码。

---

## 2. 日志与可观测性（强制）

> 这一节是硬性要求：**任何新增 HTTP 接口、Celery 任务、数据库写路径，未接入本节规定的日志，PR 不予合并。** 目标是线上出问题时，凭 `request_id` 能把「谁在什么时候调了哪个接口、跑了哪些 SQL、慢在哪、错在哪」一次拉全。

### 2.1 基础约定

- 结构化日志。`structlog` 输出 JSON 到 stdout，由 Docker/Nginx 层收集，不在容器内写散落的自定义日志文件。
- 全链路以 `request_id` 为主键（06 文档响应包裹已含）。中间件在请求入口生成或采信上游 `X-Request-ID`，写入 contextvars，所有日志自动携带；Celery 任务通过 header 透传，保持任务与触发它的请求可关联。
- 级别语义：`DEBUG` 仅开发环境开启；`INFO` 记录业务动作与请求完成；`WARNING` 记录可自愈的异常（重试成功、脏数据进待确认队列）；`ERROR` 记录请求失败或需要人工介入，带完整堆栈。

### 2.2 HTTP/API 请求日志

中间件对每个 API 请求记录一条 `INFO` 完成日志（静态资源与健康检查除外）：

| 字段 | 说明 |
| --- | --- |
| `request_id` | 全链路标识 |
| `method` `path` `route` | 原始路径与路由模板（`/api/v1/editions/<id>/registrations`），后者便于聚合 |
| `status` | HTTP 状态码 |
| `duration_ms` | 服务端耗时（含 DB 与序列化） |
| `user_id` `org_id` | 认证后的主体；未认证为 `null` |
| `client_ip` | 取 `X-Forwarded-For` 首段，不信任直连 |
| `scope` | 权限检查命中的 `scope_type/scope_id`（403 排障关键） |
| `biz_code` | 06 文档业务错误码（失败时） |
| `idempotency_key` | 有则记录 |
| `req_bytes` `resp_bytes` | 只记大小，不记正文 |
| `queries` `queries_ms` | 本次请求 SQL 条数与总耗时 |
| `slow` | `duration_ms` 超阈值时置 true |

**不记录**请求体与响应体原文：含身份证、手机号、密码、token 的正文进日志即违反 PRD §5 合规要求。需要复现时按 §2.6 的调试开关临时开启。

4xx/5xx 额外记一条，5xx 带堆栈。健康检查 `/healthz`、静态资源、`/metrics` 不产生日志。

### 2.3 数据库读写日志

分三层，避免「全量 SQL 日志把磁盘写满」这种把需求做坏的情况：

1. **每个请求的 SQL 汇总**（始终开启）：条数、总耗时、最慢一条的耗时与表名，写入 §2.2 的 `queries`/`queries_ms`。
2. **慢查询明细**（始终开启）：单条超过阈值（默认 `200ms`，可经 `LOG_SLOW_QUERY_MS` 配）记 `WARNING`，含 `sql`、`params`、`duration_ms`、`request_id`、`stack_hint`。
3. **全量明细**（按环境）：开发环境默认全开（含参数）；预发/生产默认关闭，可按 §2.6 临时开启。

所有 SQL **报错**（含 `IntegrityError`、超时、死锁）无条件记 `ERROR`，带 SQL、参数（脱敏后）、`request_id`。写操作（INSERT/UPDATE/DELETE）无论快慢都记一条 `DEBUG` 级明细，生产不输出但可通过调试开关取到。

Celery 任务另记：`task_name`、`task_id`、`retry_no`、`duration_ms`、`result_state`；失败重试记 `WARNING`，三次后置 `failed` 记 `ERROR`（对应证书生成流水线，05 文档 §3.3）。

### 2.4 敏感信息脱敏（强制）

PRD §5 已要求「日志与错误信息不落敏感明文」，落地规则：

- 字段名命中 `password`、`token`、`secret`、`authorization`、`id_number`、`phone`、`email`、`birthday` 的值一律处理。
- 处理方式：密码与 token 完全丢弃（只记 `***`）；身份证号保留前 3 后 4；手机号保留前 3 后 4；邮箱只保留域名。
- SQL 参数经统一脱敏器过滤后才可入日志；开发环境全量明细可关闭脱敏，但该开关不得进生产配置。
- 审计日志 `audit_logs`（PRD §3.8，业务留痕）与技术日志分离：`audit_logs` 写数据库、永久保留、含导出字段清单；技术日志写 stdout、按保留期滚动。两者不可互相替代。

### 2.5 关键业务埋点

除自动的请求/SQL 日志，以下动作必须显式打点（`INFO`，带业务主键），用于线上还原流程：

| 事件名示例 | 触发点 |
| --- | --- |
| `auth.login.success` / `auth.login.failed` | 登录（失败记录原因，不记录密码） |
| `rbac.denied` | 权限检查未通过（含 `perm`、`scope`，安全排障主入口） |
| `registration.submitted` / `.withdrawn` / `.resubmitted` | 报名状态动作 |
| `registration.approved` / `.rejected` / `.returned` | 审核动作（含 actor 与 review_mode） |
| `roster.confirmed` / `.unlocked` | 名单锁定与解锁（解锁带 reason） |
| `certificate.generate.started` / `.succeeded` / `.failed` | 证书流水线（含 `batch_size`、`duration_ms`） |
| `certificate.revoked` / `.reissued` | 证书作废与补发（含 `reissue_of`、`supersedes_serial`） |
| `export.started` / `.finished` | 数据导出（含字段清单，对应 PRD §5 审计要求） |
| `import.row.conflict` | Excel 导入进待人工确认（含冲突类型，不含姓名原文） |
| `file.uploaded` / `file.url_signed` | 材料上传与预签名（记 key 与大小，不记内容） |

打点统一走 `core/logging.py` 提供的 `log.info("event.name", extra={...})`，事件名集中定义，禁止在业务代码里现编字符串。

### 2.6 排障开关（建议）

生产提供仅 `platform_admin` 可用、带有效期的调试通道：请求头 `X-Debug-Tracing: <短期令牌>` 命中时，对该请求启用全量 SQL 明细并随响应返回 `request_id`。避免为查一个问题而整体调高日志级别。

### 2.7 保留与轮转

- stdout 由 Docker `json-file` 驱动限制大小（`max-size: 50m`、`max-file: 5`），配置在 `docker-compose.yml`。
- `audit_logs` 按月分区列为 P1（07 文档 P1 backlog 已含 audit 分区）。
- 备份任务（docker/README）成功与失败都要打点，否则线上会出现「备份静默失败三个月」。

---

## 3. 前端代码规范

### 3.1 工具链与约定

`Vue 3.5` + `<script setup>` + TypeScript，ESLint + Prettier，`pnpm`。API 调用一律经 `src/api/` 模块，禁止组件内裸 axios（05 文档 §4）。

- 组件名多单词（`RegistrationDetail.vue`），页面按路由域放 `views/admin|participant|public/`。
- 类型来自后端 OpenAPI（drf-spectacular 生成）导出的 `openapi.json`，用 `openapi-typescript` 生成 `src/api/types.d.ts`，禁止手抄接口类型。
- 状态只在跨组件共享时进 Pinia；局部状态不留 store。
- 禁止 `any`（确需时 `unknown` + 收窄）；禁止 `!` 非空断言掩盖问题。

### 3.2 权限渲染

`v-perm="'approval:review_single'"` 与 `hasPerm(perm, scopeObj?)` 只用于 UX（隐藏入口），**不构成安全边界**，接口侧必须各自校验（02 文档 §5）。菜单与路由由 `GET /me` 返回的 grants 驱动，禁止前端硬编码角色名单。

---

## 4. 界面视觉规范

### 4.1 颜色：统一到 Radix Colors（强制）

页面内所有颜色必须来自 Radix Colors 的色阶，经 CSS 变量层引用。禁止出现十六进制字面量、`rgb()`、`rgba()`、`red`/`blue` 之类关键字，也不允许在组件里直接写 `var(--color-...)` 之外的颜色表达式。

**色板选择**（依官方配色规范）：

- 主色 `blue`（面向学校/企业后台的稳妥选择），中性色用与之自然搭配的 `slate`，语义色 `red`（错误）、`amber`（警告）、`green`（成功）。
- 灰阶不用于「背景层级混乱」的来源：同层元素同一步骤，跨层用相邻步骤，不跳步制造伪层级。

**步骤语义**（官方定义，本项目严格遵守）：

| 步骤 | 用途 |
| --- | --- |
| 1-2 | 应用背景、次级背景、条纹表格、卡片背景、侧栏背景 |
| 3 | 组件常态背景（按钮、输入框、菜单项） |
| 4 | 组件 hover 背景 |
| 5 | 组件 active/selected 背景 |
| 6 | 非交互元素边框与分隔线（侧栏、顶栏、卡片、提示条、分隔线） |
| 7 | 交互元素边框、聚焦环 |
| 8 | 交互元素 hover 边框、更强边框 |
| 9 | 实底背景（主按钮、强调块） |
| 10 | 实底背景 hover |
| 11 | 低对比文字（次要说明、表格单元格、图标） |
| 12 | 高对比文字（标题、主要正文、表单值） |

注意 11/12 在同色阶 2 号背景上分别保证 APCA Lc 60 / Lc 90 对比度，因此**正文优先落在 1-2 号背景上**；把 12 号文字放到 9 号实底上不属于规范用法。

**令牌层**（`src/styles/tokens.css`）：语义令牌而非色名令牌，组件只认语义令牌。

```css
:root {
  /* 背景 */
  --app-bg:            var(--slate-1);
  --bg-subtle:         var(--slate-2);
  --bg-raised:         var(--white-a1);
  --bg-hover:          var(--slate-4);
  --bg-selected:       var(--slate-5);

  /* 边框 */
  --border-subtle:     var(--slate-6);   /* 卡片、顶栏、分隔线 */
  --border-control:    var(--slate-7);   /* 输入框、按钮 */
  --border-strong:     var(--slate-8);   /* hover 边框、聚焦环 */

  /* 品牌 */
  --accent:            var(--blue-9);
  --accent-hover:      var(--blue-10);
  --accent-contrast:   var(--white);

  /* 文字 */
  --text-primary:      var(--slate-12);
  --text-secondary:    var(--slate-11);
  --text-disabled:     var(--slate-8);

  /* 语义 */
  --danger:            var(--red-9);
  --danger-bg:         var(--red-3);
  --danger-text:       var(--red-11);
  --warning:           var(--amber-9);
  --warning-bg:        var(--amber-3);
  --warning-text:      var(--amber-11);
  --success:           var(--green-9);
  --success-bg:        var(--green-3);
  --success-text:      var(--green-11);
}
```

暗色模式只改令牌映射（`--app-bg: var(--slate-1)` 在暗色下仍取 slate-1），不改组件。

**Element Plus 接入**（强制走这一步，不允许在 `.vue` 里用 `:deep()` 覆盖颜色）：

```css
.el-button--primary {
  --el-button-bg-color: var(--accent);
  --el-button-border-color: var(--accent);
  --el-button-hover-bg-color: var(--accent-hover);
  --el-button-hover-border-color: var(--accent-hover);
  --el-button-text-color: var(--accent-contrast);
}
:root {
  --el-border-color: var(--border-control);
  --el-border-color-light: var(--border-subtle);
  --el-text-color-primary: var(--text-primary);
  --el-text-color-regular: var(--text-secondary);
  --el-bg-color: var(--bg-raised);
  --el-fill-color-light: var(--bg-subtle);
  --el-color-primary: var(--accent);
  --el-border-width: 0.5px;
}
```

Element Plus 内部有多处硬编码 `1px`，需要在全局样式统一覆盖为 `0.5px`，覆盖点集中列在 `src/styles/element-overrides.css` 并加注释说明原因，不散落各处。

### 4.2 边框：0.5px（强制）

所有分隔线与组件边框基准 `0.5px`。注意 1x 屏（学校机房常见）会把 `0.5px` 舍入成 0 或 1px，导致线条时有时无：

```css
.hairline { border-bottom: 0.5px solid var(--border-subtle); }

/* 1x 屏兜底：用伪元素缩放出真半像素 */
@media (resolution: 1dppx) {
  .hairline { border-bottom: none; position: relative; }
  .hairline::after {
    content: ""; position: absolute; left: 0; right: 0; bottom: 0;
    height: 1px; background: var(--border-subtle);
    transform: scaleY(0.5); transform-origin: bottom;
  }
}
```

不加边框的场景比加边框的多：靠间距和背景色差能分层级时，不画线。一个视图内的分隔手段不超过两种（间距 + 一条线）。

### 4.3 圆角：同心圆（强制）

只在承载交互或需要视觉成组的元素上用圆角，不用圆角装饰文本块。

嵌套元素圆角按 **外圆角 = 内圆角 + 内边距** 取值，使两层弧度同心：

| 外层圆角 | 内边距 | 内层圆角 |
| --- | --- | --- |
| 8px | 4px | 4px |
| 12px | 8px | 4px |
| 12px | 4px | 8px |
| 16px | 8px | 8px |

只允许 `2px / 4px / 8px / 12px` 四档：

- `2px`：标签、徽标、表头单元格
- `4px`：输入框、按钮、下拉面板内选项
- `8px`：卡片、弹窗、下拉面板
- `12px`：大面积容器（页面主卡片）
- 圆形（`9999px`）仅用于头像与状态点，不用于按钮。

### 4.4 阴影（默认不用）

不用阴影表达层级。确需脱离背景时只允许一档，且必须极轻：

```css
--shadow-pop: 0 2px 8px -2px rgb(0 0 0 / 0.12);   /* 下拉、弹层、tooltip */
```

卡片、表格、区块一律用 `--border-subtle` 或背景色差区分，不加投影，不做 hover 抬升。

**禁止**：卡片/列表项左边缘的彩色竖条（`border-left: 3px solid var(--danger)` 这类）。状态表达改用：状态点（`6px` 圆形，语义色 9 号）+ 文字（语义色 11 号），或整行/标签的语义色 3 号背景。

### 4.5 光学对齐（强制）

像素居中不等于看起来居中，逐项处理：

- **图标 + 文字**：以文字的 x-height 与图标的视觉重心对齐，而非盒子中心。圆形/方形图标通常需向下微调 `0.5-1px`。
- **文本垂直居中**：用 `line-height` 控制，不靠 `padding` 猜。`13px` 文字配 `20px` 行高，容器高 `32px` 时上下各留 `6px`。
- **带边框容器**：内边距需减去边框宽度，保证与无边框版本光学等高。
- **纯大写/数字元素**（徽标、计数）：视觉中心偏上，需比几何中心下移 `1px`。
- **表格数字列**：右对齐 + `font-variant-numeric: tabular-nums`，让数位对齐。
- **成组间距**：一组元素之间的间距小于它与外部的间距，禁止「所有 gap 都 16px」。建议梯度 `4 / 8 / 12 / 16 / 24 / 32`。
- **图标按钮**：命中区不小于 `32x32`，图标本身 `16px`，两者中心重合，不靠外边距凑。

### 4.6 字号：不超过 4 档（强制）

管理后台信息密度优先，全站只用 4 档，最小 `12px`：

| 字号 | 行高 | 用途 |
| --- | --- | --- |
| `12px` | `18px` | 辅助说明、表格次要列、时间戳、图表刻度 |
| `13px` | `20px` | 正文、表格、表单标签与输入（默认字号） |
| `16px` | `24px` | 区块标题、卡片标题、页面内小标题 |
| `20px` | `28px` | 页面主标题、看板关键数字 |

层级不够时用 **字重、颜色步骤、间距** 补，不加新字号：

- 字重只允许 `400`（正文）与 `600`（标题、强调、数字），最多再加 `500`。
- 颜色只允许 `12`（主要）与 `11`（次要）两档文字，禁用 `9`、`10` 作正文色（那是实底背景用的）。
- 数字用 `600` + `tabular-nums` 提权重，比放大字号更有效。

单屏出现 3 种以上字号是危险信号，优先删掉一处（通常是不必要的区块标题）。

### 4.7 动效：默认无（强制）

不添加装饰性动画：不做进入时的淡入上滑、不做列表逐项动画、不做数字滚动、不做 hover 缩放、不做背景渐变流动。

必要反馈用统一参数，可交互元素的状态变化优先瞬时（无过渡），仅在需要柔化突兀感时加：

```css
transition: background-color 250ms ease-out, border-color 250ms ease-out;
```

- 只用 `ease-out`，不用 `ease-in-out`/自定义 `cubic-bezier`，不用 `ease-in`（进入慢，显得迟钝）。
- 基础时长 `250ms`；下拉/弹层展开 `200ms` 以内；不出现 `>250ms` 的过渡。
- 只对 `opacity`、`transform`、颜色属性做过渡，禁止对 `height`/`width`/`margin`/`box-shadow` 做动画。
- 全局遵守 `@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }`。

### 4.8 状态表达

同一含义全站同一表达，且不只靠颜色（色觉障碍可辨识）：

| 语义 | 表达 |
| --- | --- |
| 通过 / 生效 | 文字 `green-11` + 状态点 `green-9`，文案「已通过」 |
| 待处理 | 文字 `amber-11` + 点 `amber-9`，文案「待审核」 |
| 不通过 / 停用 | 文字 `red-11` + 点 `red-9`，文案「未通过」 |
| 中性 / 草稿 | 文字 `slate-11` + 点 `slate-8`，文案「草稿」 |

状态一定配文字，不做「只有色点，鼠标移上去才知含义」。

---

## 5. 界面文案规范

### 5.1 禁用中点分隔符（强制）

界面与文档标题、元信息一律不用 `·` 作分隔符。

```text
反例：竞云 · 综合竞赛管理平台      版本 v1.0 · 基址 /api/v1 · 格式 JSON
正例：综合竞赛管理平台              版本 v1.0（基址 /api/v1，JSON）
```

需要并列时用逗号、括号，或改用排版手段（分行、间距、字号、颜色步骤）。同理不用 `|` 堆叠、不用 `//`、`【】` 作装饰。

### 5.2 不写解释性冗余文本（强制）

界面上每一段文字都要通过「删掉它用户是否会做错」这一测试。默认删除：

- 页面顶部复述本页用途的说明段（「本页面用于管理赛事相关信息」）
- 分组标题下的解释性小字（「请填写以下信息，带 * 为必填」，必填已有星号）
- 按钮文案后的解释（「保存（保存后不可修改）」→ 不可逆时改为在确认步骤说明）
- tooltip 重复标签内容
- 空状态里的操作教学长文（一句话 + 一个按钮即可）
- 表单项下重复标签的提示（「手机号」下再写「请输入手机号」）

保留的说明文字只用于：字段含义不唯一（「年级指报名时所在年级」）、格式约束（「支持 xls/xlsx，单次不超过 5000 行」）、后果提示（「解锁后已签发证书需重新生成」）。

### 5.3 面向使用者说话（强制）

界面读者是学校教务、赛事主办方、教练和学生，不是开发者。数据模型名词不得直接泄漏到界面。

| 内部模型名 | 界面用词 | 说明 |
| --- | --- | --- |
| `competition` | 赛事 | |
| `edition` | 直接显示届次名称（「2026 年第一届」） | 界面上不出现「届次」二字；管理端筛选器列名用「年度/届」 |
| `group` | 组别 | |
| `registration` | 报名 | |
| `approval_record` | 审核记录 | |
| `roster` | 获奖名单 | |
| `organization` | 单位 | 不用「组织」（与赛事组织方混淆） |
| `scope` / `grant` | 管理范围 / 权限 | 不出现「作用域」「授予」 |
| `batch_no` | 报名编号 | 不用「流水号」「批次号」 |
| `snapshot` | 不出现（内部概念） | |
| `draft` | 草稿 | |
| `pending_review` | 待审核 | |
| `org_approved` | 待复审（两级审核时） | 不暴露 `org` 前缀 |
| `returned` | 已退回，可修改后重新提交 | 面向参赛者用完整句 |
| `rejected` | 未通过（管理端「已驳回」） | |
| `revoked` | 已作废 | |

用词规则：

- 术语全站唯一，一词到底，不做同义替换（「参赛」与「报名」、「审核」与「审批」不得混用）。
- 不自造词：「参赛主体」「审核流转链路」「数据看板驾驶舱」这类不加。
- 不过度口语：不写「搞定了」「走起」「亲」「啦」；不用感叹号；不用颜文字。
- 不写客服腔（「建议您…」→ 直接说需要什么）。
- 按钮用动词，不用「确定/提交」万能词：`提交报名`、`通过`、`生成证书`。取消按钮只在有破坏性风险的对话框里出现。
- 错误提示说明**下一步做什么**，不写「操作失败」「系统异常」。

```text
反例：提交失败，请联系管理员。
正例：报名已截止（2026-11-01 18:00），无法再提交。可参加下一届。

反例：当前状态 submitted 不允许动作 approve（需 org_approved）
正例：这条报名已通过，无需重复审核。
```

- 日期时间全站格式统一：`2026-11-16 14:30`（24 小时制，展示 Asia/Shanghai，存储 UTC，PRD 全局规则 5）。表格里同列同年可省年份，列头标注「（2026）」。
- 数字千分位；百分比保留一位小数（`98.4%`），不用 `0.984`。

---

## 6. 交互规范

### 6.1 减少需要用户判断的交互（强制）

每一次弹窗、每一次确认、每一个「要不要继续」都是把设计没想清楚的成本转嫁给用户。规则：

1. **可逆操作不确认**。改名、调整顺序、移出名单、撤回草稿直接执行，不弹「确定吗？」。
2. **不可逆操作把后果写在按钮旁边**，而不是弹一个「确认」让用户猜。`作废该证书` 需同时说明「作废后持证人下载的原证书失效」，确认即提交（一次点击完成，不叠两层）。
3. **二次确认只保留给真正危险的三类**：审核驳回（终止参赛者）、名单解锁（影响已签发证书）、批量通过（数量大、影响面广）。这三处确认对话框必须显示受影响条数，并要求填写理由（与 02/03 文档的「意见必填」合并为同一步，不额外多问一次）。
4. **默认值代替提问**。能推断的不询问：报名年份默认当前届、导出字段默认上次选择、筛选默认当前届。
5. **配置代替询问**。是否两级审核在届次配置里定好，不在每次审核时问。
6. **选项放在用户要做这件事的位置**。审核意见输入框就在审核按钮旁，不在列表页顶部放一个全局意见框。
7. **不做「要不要保存」这类问题**。表单要么自动保存草稿（报名场景即如此），要么提交时统一处理，不留手动保存按钮 + 离开拦截的组合。
8. **进度类反馈不阻塞**。批量生成证书、导入 Excel 提交后立即返回并给「处理中」状态与完成后的站内通知（PRD §3.6 已定通知机制），不做进度条 + 禁止离开。

### 6.2 按信息优先级组织界面（强制）

- 一屏只承担一个主任务，主操作只有一处，位置固定（列表页右上、详情页右上、表单底部右侧）。
- 表列按「用户为完成任务必须看到」排序，不是按数据库字段顺序。默认列不超过 7 项，其余进「显示列」；排序与筛选放在需要它的地方（表头，不是页面顶部工具条）。
- 状态计数（如「待审核 12」）作为筛选入口，而不是放在页面顶部当装饰卡片。
- 详情用抽屉/侧滑打开，不跳转新页面：审核场景需要在列表与详情间来回，高频路径优先最短。
- 一个页面里的分组不超过 3 层；出现 4 层缩进说明该拆页。
- 次要功能（模板下载、历史版本、批量清理）收进「更多」，不与主操作争抢注意力。

### 6.3 反馈与空状态

- 加载用骨架屏（保持布局尺寸，避免内容跳位），不转圈；超过 `250ms` 才显示。
- 空状态一句话说清「还没有什么」+ 一个动作按钮，不放插画、不放三段说明。
- 表单校验在失焦时提示，提交时聚焦到第一个错误项；不在用户输入中途报错。
- 提交成功后的提示只说结果并给出紧接着的去处（「已提交，可在「我的报名」查看」），不重复「成功」加感叹号。

---

## 7. 无障碍与可用性基线

- 全部交互可键盘完成，聚焦可见（`--border-strong` + 2px 外环，不做隐藏默认聚焦环又不自绘的半途方案）。
- 文字对比度不低于 WCAG AA（4.5:1，`12px` 小字同样适用）；按 §4.1 的步骤语义取色即天然满足。
- 状态不只靠颜色（§4.8）。
- 表格数字、日期列右对齐并启用 `tabular-nums`，便于纵向比较。
- 触控目标不小于 `32x32`（教练与学生可能在手机上报名）。

---

## 8. 性能与容量约束（对照 PRD §6）

- 列表接口必须分页，`page_size` 上限 100；禁止返回未分页的全量集合。
- 导出、导入、证书生成一律 Celery 异步，接口只返回任务标识；同步导出限制在 2000 行内。
- 报名提交接口 `P95 < 800ms` 为验收门槛（PRD §6），W12 压测 500 并发场景，压测脚本与结果入 `docs/`。
- 前端首屏 JS（gzip 后）预算 300KB；Element Plus 按需引入，不做全局引入。
- 图片/封面上传前端压缩到 500KB 以内再传；材料 ≤ 20MB（PRD §6）。
- 慢 SQL 阈值 200ms 触发告警日志（§2.3），每周看一次 top 慢查询并处理。

---

## 9. 禁止事项

以下写法在评审中直接打回，不需要讨论：

| 类别 | 禁止 |
| --- | --- |
| 日志 | 新增接口/任务/写路径无日志埋点；日志里出现密码、token、身份证、手机号明文；`except Exception: pass` |
| 权限 | view 里硬编码角色名；用前端隐藏代替后端校验；公开接口复用管理端 serializer（02 文档 §4.5） |
| 状态 | 直接给 `status` 赋值绕过 `transition()`；新增状态枚举不更新 03 文档 |
| 颜色 | 十六进制/`rgb()`/`rgba()` 字面量；`:deep()` 里覆盖组件库颜色；卡片左边缘彩色竖条；阴影表达层级 |
| 排版 | 超过 4 档字号；`<12px` 文字；非 0.5px 的边框基准；装饰性圆角；嵌套圆角不做同心处理 |
| 动效 | `>250ms` 过渡；`ease-in`/自定义曲线；装饰性进入动画；对布局属性做动画 |
| 文案 | 用 `·` 作分隔符；复述页面用途的说明段；内部模型名泄漏到界面（「届次」「作用域」「流水号」）；「操作失败」类无指引提示；感叹号与客服腔 |
| 交互 | 可逆操作的确认弹窗；两层以上「确认」；进度条阻塞页面；主操作多于一个 |
| 工程 | 提交 `.env`、密钥、`node_modules`、日志；已推送分支 force push；迁移不检查数据影响；循环内查询 |

提交与分支相关条款的完整版见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 10. 检查清单

### 提 PR 前自查（后端）

- [ ] 接口有 `required_perm` 声明，403 会记 `rbac.denied` 日志
- [ ] 请求日志、SQL 汇总日志在本地验证输出正常，`request_id` 可串联
- [ ] 敏感字段不出现在日志与错误 message 中
- [ ] 状态变更全部走 `transition()`，03 文档已同步
- [ ] 新常量来自 `core/constants.py`，无裸字符串
- [ ] service 层测试补齐，覆盖率达标
- [ ] 无 N+1，分页与筛选生效

### 提 PR 前自查（前端）

- [ ] 颜色全部经令牌，无硬编码色值
- [ ] 边框 `0.5px`，圆角取值属于 `2/4/8/12` 且嵌套同心
- [ ] 字号 ≤ 4 档，最小 `12px`，层级用字重/颜色/间距表达
- [ ] 无装饰性动画，必要过渡为 `250ms ease-out`
- [ ] 无卡片左彩条、无阴影层级
- [ ] 文案无 `·`、无解释性冗余、术语对齐 §5.3、无内部名词
- [ ] 确认弹窗仅出现在 §6.1 第 3 条列出的三处
- [ ] 键盘可达，对比度达标

### 上线前（每环境）

- [ ] 日志级别与慢查询阈值配置正确，生产关闭全量 SQL 明细
- [ ] 日志轮转上限已配（`max-size`/`max-file`）
- [ ] 备份任务成功与失败均有打点
- [ ] `.env` 与生产密钥不入库，`.env.example` 已同步新增变量

---

## 11. 文档待办

中点分隔符已于 2026-11-16 从全部文档清除。同日的 v1.1 修订中，以下缺陷已修复，此处只记录**仍然开放**的事项。

### 11.1 已修复（v1.1，2026-11-16）

| 位置 | 原问题 |
| --- | --- |
| 05 文档 §1 | 技术栈缺 Radix Colors、`django-treebeard`、`django-import-export`、cryptography、structlog、SMTP |
| 02 文档 §5 | 引用的 `drf-access` 包不存在，已改为「自研 `ScopedRolePermission`」 |
| 04 文档 §2 | `organizations.parent_id` 裸邻接表无法支撑高频子树查询，已改 treebeard 物化路径 |
| 04 文档 §6 | 证书编号依赖可变的自增主键，已引入 `certificate_sequences` 独立计数器 |
| 07 文档 | 排期未计入日志埋点，已加入 W1 并重估工期（12 周 → 15 周） |
| 03 文档 §6 | 补发后旧证验证页行为未定，已补 §6.1 |

### 11.2 仍开放

| 位置 | 事项 | 优先级 |
| --- | --- | --- |
| 工程 | `pre-commit`、ruff/mypy、ESLint/Prettier 配置与 CI 尚无实体文件：CONTRIBUTING.md 要求「CI 全绿」目前无处可绿，DEVELOPMENT 的强制项也无自动拦截 | 阻塞 W1 |
| 仓库 | 根目录无 README，公开仓库落地页只有一份 CONTRIBUTING 与 docs 索引 | 建议尽快 |
| 02 §1 | 若将来出现「同届次内按赛项分派审核人」需求，需扩 `scope_type='event'`（已记入 01 §9 待决） | 观察 |
| 01 §9 | 数据主体删除请求与记录永久保留的冲突口径待法务确认 | 上线前 |
| 01 §9 | 混合年龄队「取最高学段」需先用真实队伍数据复核 | 里程碑 1 内 |
| 05 §1 | 未列 `drf-spectacular` 版本基线，而前端类型由它导出的 `openapi.json` 生成（§3.1） | W1 |
| 部署 | 生产 SMTP 的发信域名、SPF/DKIM 由谁配置未落实；邮箱验证码是注册唯一通道，此项不定则里程碑 1 无法对外上线 | 阻塞交付 |
