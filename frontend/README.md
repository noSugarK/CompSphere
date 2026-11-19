# compsphere-web

正式Vue 3 + TypeScript工程，复用Element Plus业务组件，使用Pinia、Vue Router、Axios、vue-i18n及Zod。锁定版本与可用命令见package.json/package-lock.json，接口见[开发契约](../docs/12-development-contract.md)。独立[静态演示](prototype/README.md)继续保留，不连接正式API，也不参与正式构建。

## 开发与检查

在仓库根目录执行：

```powershell
npm ci --prefix frontend
npm run api:generate --prefix frontend
npm run dev --prefix frontend -- --port 5174 --strictPort
```

后端先在127.0.0.1:8000运行，SITE_BASE_URL设置为实际前端origin（上例http://127.0.0.1:5174），开发服务将/api与/healthz代理至后端。使用后端显式创建的账号登录，无默认密码或前端假登录。生产由同源Nginx代理；开发服务只绑定本机。

```powershell
npm run lint --prefix frontend
npm run format:check --prefix frontend
npm run typecheck --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
```

api:generate从后端导出的docs/openapi.json生成src/api/generated.d.ts，不手工编辑；Zod运行时schema与生成类型交叉校验。HTTP响应以unknown进入结构校验，非法包裹/字段/枚举/ID/日期不会进入store。请求及AI提案也有独立严格schema；schema通过不代替服务端逐次授权。

## 当前实现

- 邮箱/证件登录、内存Access、Refresh Cookie/CSRF、单飞刷新、过期清理、账号切换旧请求隔离；无localStorage/sessionStorage token。
- 邮箱验证码注册与找回：严格校验6位ASCII验证码，保留前导零，注册后显式登录，重置不自动登录；202仅显示通用受理文案。发送成功按60秒契约冷却，真实429按有效Retry-After反馈；失败保留输入并定位字段，密码及验证码仅成功后清除。
- 中英及浅/深/system主题，门户赛事/详情、队伍概要、队伍提案/审核、赛季许可、报名草稿/提交/冻结/取消修改与单级审核页面，前端权限路由和按钮控制。
- Element Plus表单/表格/确认和状态反馈；加载/空/失败可重试，日期固定Asia/Shanghai；窄屏可操作，复杂批量仍以桌面为主。
- 消息中心参考静态演示的顶栏铃铛、日期分组和「查看」动作，读取真实报名进度，支持分页和标为已读。
- 赛事管理参考静态演示的目录和创建弹窗，展示权限内赛事；只有平台管理员可保存私有草稿。
- 路由外AI悬浮入口仅显示未接入状态及最小页面标识，不调用模型、采集DOM/图片/附件或伪造业务成功。

本轮是核心链路，不代表完整首期已交付。代建、组织入驻、正式赛事配置、固定模板导入、材料安全上传、获奖/公示、通用公告和自动备份等尚待后续实现；验证码及已启用的报名邮件实际送达取决于后端投递器及SMTP配置，HTTP成功不能证明邮件送达。证书、复杂跨队特批和两级审核为后续范围。必交材料仍受后端校验，不能用当前无材料联调场次替代真实赛事验收。

## 验证与依赖边界

2026-11-19运行typecheck、ESLint、Prettier、38项Vitest及生产构建通过；session竞态测试覆盖旧请求401不以新账号重放、共享刷新完成后其他等待者切账号时不重放、旧刷新失败不清新会话、失败登出清理。浏览器验证真实验证码202受理提示/倒计时、注册/找回入口和375×600无页面横向溢出，注册/改密成功通过本地HTTP及进程内邮件联调。此前生产依赖npm audit --omit=dev无已知告警；开发工具链仍有picomatch传递依赖ReDoS告警，当次官方注册表无修复版本，不使用虚假override掩盖，开发服务不得开放公网；本轮未变更依赖或重跑审计。Docker、生产TLS、真实SMTP、真实材料上传和完整首期仍需独立验收。
