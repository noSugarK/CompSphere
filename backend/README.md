# compsphere-server

正式Django 5.2 + DRF工程，首批联调契约见 [12](../docs/12-development-contract.md)。当前是一条可运行的核心链路，不代表07首期全部任务已完成；原静态演示保持独立。

## 本地运行

使用Python3.12，在backend目录执行：

```powershell
uv venv .venv --python 3.12
uv pip sync requirements.txt --python .venv/Scripts/python.exe
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py seed_rbac
.venv/Scripts/python.exe manage.py seed_development
.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

种子运行前通过环境变量显式设置强密码COMPSPHERE_DEV_PASSWORD；无默认密码、不打印密码、不覆盖已有账号、不在生产运行。合成账号为platform、manager、coach、student、reviewer、organizer、outsider加@dev.example。包含两个单位、当前active赛季、公开场次、已审队伍和赛季许可。

默认dev settings；未设DATABASE_URL时仅以SQLite进行单进程开发。真实PostgreSQL验证需设置DATABASE_URL到隔离PG16。dev限流缓存为单进程内存，prod为Redis。dev专用随机签名/加密密钥保存在已忽略的.development-secrets.json，不能删除后继续使用原数据库，也不能用于生产。

SITE_BASE_URL必须是实际前端origin，例如http://127.0.0.1:5174；刷新/登出校验精确Origin和CSRF。Access仅前端内存，Refresh为HttpOnly/SameSite=Strict Cookie，生产Secure。生产使用config.settings.prod并显式配置数据库、Redis、强签名密钥、Fernet及独立pepper，弱占位值阻止启动。TLS受信代理及首次管理员初始化见[部署指南](../docker/README.md)。

## 当前可用

- 邮箱/已绑定证件密码登录，实时账号状态与token_version鉴权、Refresh轮转/黑名单、CSRF/Origin、登出撤销、强制改密和偏好。
- 邮箱验证码注册/找回：匿名受理不查账号存在性，严格请求校验、限频、验证码用途隔离/单次消费/失败次数，注册仅赋本人participant权限，找回撤销旧会话。
- 验证码和报名邮件复用outbox租约领取、过期回收、有限重试和稳定Message-ID；开发/测试使用进程内locmem邮件，不打印验证码、邮件正文或收件地址。
- 数据驱动RBAC与作用域查询：公开赛事/届次、当前赛季、权限内单位/成员/队伍。
- 赛事管理目录仅展示赛事作用域内资源；平台管理员可创建私有赛事草稿，服务端生成编号并记录审计，不自动建届次或发布。
- 平台赛季API含分页、建草稿、激活、串行切换当前赛季；切换保留旧赛季及其许可和记录，不自动归档。
- 届次API支持作用域内分页与建草稿：平台可选非归档赛季，赛事级管理员只可选已激活赛季；时间使用明确偏移或声明Asia/Shanghai，届次级权限不扩到兄弟届次。
- 已有草稿可部分更新名称、地点和时间；不变更赛季和编号，拒绝导致已有开放组合时间失效的修改。
- 草稿届次的赛项可按稳定赛项类型配置人数和教练要求，已发布届次只允许启停，不能覆盖既有规则。数据迁移补齐VEX字典，不覆盖已有名称。
- 届次组别支持草稿增删改及草稿/已发布启停，已被组合引用时不可删除，不接收年龄规则。
- 已实现显式赛项×组别组合：同届校验、草稿配置、草稿/已发布启停；有报名记录不能删除，停用不改写存量报名。
- 草稿组合可单独覆盖报名起止和软名额。空边界继承届次；公开详情返回有效窗口；发布要求至少一个已启用、未截止的有效组合，报名不以软名额作为硬性拒绝条件。
- 报名可选组合接口分页返回当前有效窗口内的选项；选队后验证代报权、队伍版本、本季许可及稳定赛项，但不替提交人判断学段。
- 赛事与届次分别发布，发布事务重新校验赛季、时间窗、开放组合和当前支持的报名规则；不发布无法上传的必交材料配置。
- 加密队伍提案、非自审创建/修改审核、成员唯一归属、赛季注册/审核；创建批准原子建立队伍和许可。
- 个人/团队报名草稿、版本冲突、幂等提交、不可变轮次及成员、单级审核、取消修改/撤回、历史投影及赛季绑定。
- 管理队列提供分页摘要和作用域内筛选选项，按当前冻结轮次识别赛项与组别；成员和联系方式不从列表返回。升级 `registrations.0003` 前备份并停写，用原 `FIELD_ENCRYPTION_KEY` 从既有快照回填组合引用；迁移会锁定提交表，无效历史会使迁移回滚。
- 提交轮次列表与单轮详情按原报名作用域读取冻结组合、时间与成员白名单，不解密或返回联系方式和其他表单字段。
- 批量审核逐条复用单条待审核守卫、轮次锁、审计与通知，每批最多 20 条，逐条提交并返回冲突/失败码；已通过结果的更正仍走单条流程。
- 报名提交与单级审核结果同事务生成提交人站内消息，并为活跃且邮箱已验证的提交人入队中英邮件；无邮箱仍保留站内消息。本人分页、幂等标记已读，不回填历史消息或补发旧邮件。
- 严格JSON/嵌套serializer校验、统一响应、request_id脱敏日志、审计和事务outbox入队；AI仅独立纯JSON校验器，无模型路由/网络调用/数据库工具。
- PG专用迁移保留同届/同队/同轮复合外键及不可变历史触发器。ORM技术字段差异按04的实施说明阅读。

## 检查与接口导出

```powershell
.venv/Scripts/ruff.exe check .
.venv/Scripts/ruff.exe format --check .
.venv/Scripts/mypy.exe apps core config
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe manage.py spectacular --format openapi-json --file ../docs/openapi.json --validate --fail-on-warn
```

TEST_DATABASE_URL让pytest创建独立PG测试库，账号需有创建测试库权限；不要指向真实资料库。默认SQLite跳过PG行锁/触发器专项。已在隔离PG16.15实际迁移并验证API/越权/冻结投影/JSON/AI/CSRF及并发双提交，数量以最终运行输出为准。OpenAPI由后端导出供前端生成类型，不直接编辑生成文件。

## 未完成项

首期仍需代建、证件更正、组织入驻/单位交接、正式赛事配置及规则变更版本、固定模板导入、在读证明/附件安全上传及私有存储、获奖/公示、通用公告、自动备份/恢复及高峰容量验收。队伍其他有权负责人与重要赛事变更的通知也未接通。

生产验证码和报名邮件需要运行Celery worker和单实例beat（config.settings.prod）；beat每15秒分别检查两个主题，每主题每批最多20封，5次尝试，30秒起指数退避，租约至少60秒。SMTP网络调用在数据库事务之外，崩溃可能导致重复邮件，不承诺恰好一次；旧报名占位事件不消费。配置EMAIL_*、SITE_BASE_URL和CODE_*见.env.example，真实SMTP、SPF/DKIM与Redis/Celery进程恢复仍需部署验收，HTTP成功不代表送达。

安全上传端点未实现所以不注册；要求必交材料的报名以42202阻止，不返回虚假upload_id。证书、复杂跨队特批、两级审核为后续能力。500并发、RPO/RTO、MinIO、Docker整套部署及生产TLS仍须独立验收。
