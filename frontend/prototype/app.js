/* PROTOTYPE ONLY: synthetic data and in-memory actions, no authentication or API.
 * The public portal serves students/coaches; permission grants expose admin tools. This is not the production Vue implementation.
 */
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const params = new URLSearchParams(location.search);
const state = {
  role: params.get('role') || 'visitor', lang: params.get('lang') || 'zh', theme: params.get('theme') || 'light',
  page: location.hash.slice(1) || (params.get('role') === 'reviewer' ? 'reviews' : ['org','event','platform'].includes(params.get('role')) ? 'dashboard' : 'portal'),
  competitionIndex: [0, 1, 2].includes(Number(params.get('competition'))) ? Number(params.get('competition')) : 0,
  editionSection: ['basics', 'rules', 'offerings', 'publish'].includes(params.get('section')) ? params.get('section') : 'basics',
  season: '2026-2027', // Platform configuration in this in-memory preview; URL cannot select it.
  seasonLicenses: ['1024A','1024B','1024C','1024D'].map(team => ({ team, season: '2026-2027', status: team === '1024C' ? 'submitted' : 'approved', applicant: '周老师', comment: team === '1024C' ? '' : '材料已核验' })),
  search: '', status: 'all', tab: 'all', reviewTab: 'current', form: {}, photo: '',
  registrations: [
    { id: 'REG-26-0082', team: '逐光机器人队', code: '1024A', event: 'V5RC', group: '高中组', count: 4, status: 'pending', date: '2026-11-17 09:32', unit: '海川实验学校', round: 1 },
    { id: 'REG-26-0081', team: '星河探索队', code: '1024B', event: 'VIQRC', group: '初中组', count: 3, status: 'approved', date: '2026-11-16 16:45', unit: '海川实验学校', round: 1 },
    { id: 'REG-26-0076', team: '源点科技队', code: '1024C', event: 'V5RC', group: '高中组', count: 4, status: 'returned', date: '2026-11-16 14:20', unit: '海川实验学校', round: 1 },
    { id: 'REG-26-0069', team: '远航机器人队', code: '1024D', event: 'VIQRC', group: '小学组', count: 3, status: 'approved', date: '2026-11-15 10:08', unit: '海川实验学校', round: 2 },
    { id: 'REG-26-0063', team: '启明星队', code: '1024E', event: 'V5RC', group: '初中组', count: 4, status: 'rejected', date: '2026-11-14 15:12', unit: '海川实验学校', round: 1 },
  ],
  teams: [
    { code: '1024A', name: '逐光机器人队', event: 'V5RC', captain: '林知远', coach: '陈老师', count: 4 },
    { code: '1024B', name: '星河探索队', event: 'VIQRC', captain: '许星遥', coach: '周老师', count: 3 },
    { code: '1024C', name: '源点科技队', event: 'V5RC', captain: '顾明澈', coach: '陈老师', count: 4 },
    { code: '1024D', name: '远航机器人队', event: 'VIQRC', captain: '程以安', coach: '周老师', count: 3 },
    { code: '1024E', name: '启明星队', event: 'V5RC', captain: '沈嘉言', coach: '陈老师', count: 4 },
  ],
  students: [
    { name: '林知远', code: 'S202601', group: '高中一年级', team: '1024A · V5RC', doc: 'id', last4: '0027', status: 'active' },
    { name: '唐星禾', code: 'S202606', group: '高中一年级', team: '1024A · V5RC', doc: 'id', last4: '0882', status: 'active' },
    { name: '陈予安', code: 'S202607', group: '高中一年级', team: '1024A · V5RC', doc: 'id', last4: '0518', status: 'active' },
    { name: '苏予宁', code: 'S202602', group: '高中一年级', team: '1024A · V5RC', doc: 'id', last4: '0416', status: 'active' },
    { name: '许星遥', code: 'S202603', group: '初中二年级', team: '1024B · VIQRC', doc: 'passport', last4: 'A018', status: 'active' },
    { name: '周沐言', code: 'S202604', group: '高中二年级', team: '', doc: 'id', last4: '0613', status: 'active' },
    { name: '顾明澈', code: 'S202605', group: '高中一年级', team: '1024C · V5RC', doc: 'id', last4: '0024', status: 'active' },
  ],
  bindings: [{ student: 'S202601', event: 'V5RC', team: '1024A', season: '2026-2027', version: 1 }],
  transferRequests: [],
  membershipAudit: [],
  requests: [
    { name: '逐光机器人队', title: ['队伍成员变更', 'Team member change'], applicant: '周老师', status: 'pending', date: '2026-11-17 10:24' },
    { name: '许星遥', title: ['证件信息更正', 'Document correction'], applicant: '学生本人', status: 'pending', date: '2026-11-17 09:48' },
    { name: '新芽机器人队', season: '2026-2027', proposal: {code:'1024F', name:'新芽机器人队', event:'V5RC'}, title: ['创建队伍', 'Create team'], applicant: '陈老师', status: 'pending', date: '2026-11-16 15:30' },
  ],
  history: [{ name: '林知远', action: ['加入逐光机器人队', 'Joined the team'], date: '2026-09-08 14:32', by: '陈老师' }],
};
const tr = (zh, en) => state.lang === 'zh' ? zh : en;
const labels = {
  demo: ['演示导航', 'Demo explorer'],
  discover: ['全部赛事', 'All competitions'], 'public-event': ['赛事详情', 'Competition detail'],
  membership: ['队伍与参赛资格', 'Team & eligibility'], transfers: ['特批换队', 'Transfer approvals'],
  edition: ['赛事配置', 'Competition setup'], history: ['历史档案', 'Historical records'],
  dashboard: ['工作台', 'Overview'], competitions: ['赛事中心', 'Competitions'], registrations: ['报名管理', 'Registrations'],
  reviews: ['报名审核', 'Registration review'], requests: ['资料审核', 'Change requests'], teams: ['队伍管理', 'Teams'],
  students: ['学生账户', 'Student accounts'], organizations: ['单位管理', 'Organizations'], awards: ['获奖名单', 'Awards'],
  certificates: ['证书中心', 'Certificates'], access: ['队伍准入', 'Team eligibility'], imports: ['导入与导出', 'Import & export'],
  notices: ['消息中心', 'Notifications'], audit: ['操作记录', 'Activity log'], settings: ['设置', 'Settings'],
  profile: ['个人档案', 'My profile'], roles: ['角色与授权', 'Roles & access'], registration: ['填写报名', 'Registration form'],
  competition: ['赛事详情', 'Competition detail'], portal: ['赛事门户', 'Discover'], login: ['登录账户', 'Sign in'], verify: ['证书验证', 'Verify certificate'],
};
const label = (key) => key === 'competitions' && can('competition:manage') ? tr('赛事管理', 'Competition management') : key === 'registrations' && !can('admin:access') ? tr('我的报名', 'My registrations') : key === 'teams' && !canManageTeams() ? tr('本单位队伍', 'Organization teams') : labels[key] ? tr(...labels[key]) : key;
const roles = { visitor: ['访客', 'Visitor'], org: ['单位管理员', 'Organization admin'], event: ['赛事管理员', 'Competition admin'], reviewer: ['赛事审核员', 'Reviewer'], coach: ['教练', 'Coach'], student: ['学生', 'Student'], platform: ['平台管理员', 'Platform admin'] };
const names = { visitor: '访客', org: '陈老师', event: '赛事管理员', reviewer: '审核员', coach: '陈老师', student: '林知远', platform: '平台管理员' };
const is = (...rolesToCheck) => rolesToCheck.includes(state.role);
const permissionsByRole = {
  visitor: [],
  student: ['membership:own','registration:write','certificate:own'],
  coach: ['team:read','registration:write'],
  org: ['admin:access','dashboard:read','history:read','team:read','team:manage','student:manage','request:review','registration:read','record:read'],
  event: ['admin:access','dashboard:read','history:read','competition:manage','registration:read','registration:review','certificate:manage','record:read'],
  reviewer: ['admin:access','history:read','registration:review'],
  platform: ['*'],
};
const can = (permission) => { const grants = state.permissions || permissionsByRole[state.role] || []; return grants.includes('*') || grants.includes(permission); };
const canManageTeams = () => can('team:manage');
const canReview = () => can('registration:review');
const iconPaths = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  trophy: '<path d="M8 3h8v6a4 4 0 0 1-8 0zM8 5H4v2a4 4 0 0 0 4 4m8-6h4v2a4 4 0 0 1-4 4M12 13v5m-4 3h8m-8-3h8"/>',
  team: '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3m1-16a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 5"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
  file: '<path d="M14 2H5v20h14V7zM14 2v6h5M8 12h8m-8 4h6"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9S4 17 4 12V6z"/><path d="m8 12 3 3 5-6"/>',
  chart: '<path d="M4 3v17h17M8 15v-4m5 4V7m5 8V4"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
  settings: '<path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8m-3-5h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6"/>',
  download: '<path d="M12 3v13m-5-5 5 5 5-5M4 15v6h16v-6"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  left: '<path d="m15 5-7 7 7 7"/>',
  plus: '<path d="M12 4v16M4 12h16"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18m-13 4h2m4 0h2"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
  building: '<path d="M4 21V5l8-3v19m0-13h8v13M2 21h20M7 7h2m-2 4h2m-2 4h2m7-3h2m-2 4h2"/>',
  globe: '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9 8a3 3 0 0 1 6 0c0 2-3 2-3 5m0 3v1"/>',
  lock: '<rect x="4" y="10" width="16" height="12" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 5v3"/>',
  pin: '<path d="M19 9c0 5-7 12-7 12S5 14 5 9a7 7 0 0 1 14 0z"/><circle cx="12" cy="9" r="2"/>',
  robot: '<rect x="3" y="7" width="18" height="13" rx="3"/><path d="M12 3v4M7 12h1m8 0h1m-9 4h8M1 11v5m22-5v5"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/>',
};
const icon = (name) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[name] || iconPaths.file}</svg>`;
const badge = (status) => {
  const map = { pending: ['待审核', 'Pending', 'amber'], approved: ['已通过', 'Approved', 'green'], returned: ['退回修改', 'Changes requested', 'red'], rejected: ['已驳回', 'Rejected', 'red'], draft: ['草稿', 'Draft', ''], withdrawn: ['已撤回', 'Withdrawn', ''], active: ['正常', 'Active', 'green'], enrolling: ['报名进行中', 'Registration open', 'blue'], upcoming: ['即将开放', 'Opening soon', ''], closed: ['已关闭', 'Closed', ''], issued: ['已发放', 'Issued', 'green'], processing: ['处理中', 'Processing', 'blue'] };
  const item = map[status] || [status, status, ''];
  return `<span class="tag ${item[2]}"><span class="dot"></span>${tr(item[0], item[1])}</span>`;
};
const btn = (text, action, style = '', symbol = '') => `<button type="button" class="button ${style}" data-action="${esc(action)}">${symbol ? icon(symbol) : ''}${text}</button>`;
const link = (text, page, style = '', symbol = '') => `<a href="#${page}" class="button ${style}">${symbol ? icon(symbol) : ''}${text}</a>`;
const field = (name, title, value = '', type = 'text', extra = '') => `<div class="field"><label for="${name}">${title}</label><input id="${name}" name="${name}" type="${type}" value="${esc(state.form[name] ?? value)}" ${extra}></div>`;
const selectField = (name, title, options, extra = '', selected = state.form[name]) => `<div class="field"><label for="${name}">${title}</label><select id="${name}" name="${name}" ${extra}>${options.map(([value, text]) => `<option value="${esc(value)}" ${selected === value ? 'selected' : ''}>${text}</option>`).join('')}</select></div>`;
const notice = (text, color = '') => `<div class="notice ${color}">${icon('shield')}<span>${text}</span></div>`;
const pageHead = (title, subtitle, actions = '') => `<div class="page-head"><div><h1 id="page-title" tabindex="-1">${title}</h1><p>${subtitle}</p></div><div class="actions">${actions}</div></div>`;
const panel = (title, body, action = '', bodyClass = '') => `<section class="panel"><div class="panel-head"><h2>${title}</h2>${action}</div><div class="panel-body ${bodyClass}">${body}</div></section>`;
const table = (caption, headers, rows, footer = true) => `<div class="table-region" role="region" aria-label="${esc(caption)}" tabindex="0"><table><caption class="sr-only">${caption}</caption><thead><tr>${headers.map((h) => `<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows.length ? rows.map((row) => `<tr>${row.map((cell, i) => i === 0 ? `<th scope="row">${cell}</th>` : `<td>${cell}</td>`).join('')}</tr>`).join('') : `<tr><td colspan="${headers.length}"><div class="empty">${icon('search')}<h2>${tr('没有找到相关记录', 'No matching records')}</h2><p>${tr('试试其他关键词，或清除筛选条件。', 'Try a different search or clear the filters.')}</p>${btn(tr('清除筛选', 'Clear filters'), 'clear-filters')}</div></td></tr>`}</tbody></table></div>${footer ? `<div class="table-footer"><span>${tr(`共 ${rows.length} 条记录`, `${rows.length} records`)} · ${tr('每页 10 条', '10 per page')}</span><div class="actions"><span class="page-number">1</span></div></div>` : ''}`;
const tabs = (items, selected = state.tab, action = 'tab') => `<nav class="tabs" aria-label="${tr('页面分类', 'Page categories')}">${items.map(([id, text]) => `<button class="tab ${selected === id ? 'active' : ''}" data-action="${action}:${id}" ${selected === id ? 'aria-current="page"' : ''}>${text}</button>`).join('')}</nav>`;
const filters = (placeholder = tr('搜索名称、编号', 'Search name or number'), statuses = false) => `<div class="filters"><label class="search-field"><span class="sr-only">${placeholder}</span>${icon('search')}<input type="search" id="search" placeholder="${placeholder}" value="${esc(state.search)}"></label>${statuses ? `<label class="field"><span class="sr-only">${tr('状态', 'Status')}</span><select id="filter-status"><option value="all">${tr('全部状态', 'All statuses')}</option>${['pending', 'approved', 'returned', 'rejected'].map((s) => `<option value="${s}" ${state.status === s ? 'selected' : ''}>${s === 'pending' ? tr('待审核', 'Pending') : s === 'approved' ? tr('已通过', 'Approved') : s === 'returned' ? tr('退回修改', 'Returned') : tr('已驳回', 'Rejected')}</option>`).join('')}</select></label>` : ''}</div>`;
const matchSearch = (row) => Object.values(row).join(' ').toLowerCase().includes(state.search.toLowerCase());
const empty = (title, text, action = '') => `<div class="empty">${icon('file')}<h2>${title}</h2><p>${text}</p>${action}</div>`;

function navigation() {
  return [
    ['dashboard','grid','dashboard:read'], ['teams','team','team:read'], ['students','user','student:manage'],
    ['organizations','building','platform:manage'], ['roles','shield','platform:manage'],
    ['requests','shield','request:review'], ['transfers','shield','platform:manage'],
    ['competitions','trophy',null], ['membership','team','membership:own'],
    ['reviews','shield','registration:review'], ['edition','calendar','competition:manage'],
    ['access','lock','competition:manage'], ['awards','trophy','competition:manage'],
    ['registrations','file',can('registration:write') ? 'registration:write' : 'registration:read'],
    ['certificates','file',can('certificate:own') ? 'certificate:own' : 'certificate:manage'],
    ['history','clock','history:read'], ['imports','upload','record:read'], ['audit','clock','record:read'],
  ].filter(([, , permission]) => permission === null || can(permission)).map(([id, symbol]) => [id, symbol]);
}
function controls() { return renderProductControls(); }
const brand = () => renderBrand();
function shell(content) { return renderAdminShell(content); }
function registrationRows(rows, review = false) {
  return table(tr('报名记录', 'Registrations'), [tr('队伍 / 报名编号', 'Team / Registration'), tr('赛项与组别', 'Event / Division'), tr('成员', 'Members'), tr('状态', 'Status'), tr('提交时间', 'Submitted'), tr('操作', 'Action')], rows.map((r) => [
    `${esc(r.team)}<span class="muted mono">${r.id}</span>`, `${r.event}<span class="muted">${esc(r.group)}</span>`, `${r.count} ${tr('人', 'students')}`, badge(r.status), `<span class="mono">${r.date}</span>`, btn(review ? tr('审核', 'Review') : tr('查看', 'View'), `registration-detail:${r.id}`, 'text small'),
  ]));
}
function dashboard() { return renderControlCenter(); }
const seasons = [{ id: '2026-2027', status: 'active' }, { id: '2027-2028', status: 'active' }, { id: '2025-2026', status: 'archived' }];
function currentSeasonContext() {
  return `<div class="current-season"><span class="season-indicator"></span><div><span class="technical-label">${tr('当前赛季', 'CURRENT SEASON')}</span><strong>${esc(state.season.replace('-', '–'))}</strong></div>${is('platform') ? btn(tr('管理赛季', 'Manage seasons'), 'manage-seasons', 'text small', 'settings') : ''}</div>`;
}
function seasonLicenseBadge(code) { const status = teamSeasonLicense(code)?.status; return status ? badge(status === 'submitted' ? 'pending' : 'approved') : `<span class="tag amber">${tr('未激活', 'Not activated')}</span>`; }
const teamSeasonLicense = (team, season = state.season) => state.seasonLicenses.find(r => r.team === team && r.season === season && ['submitted','approved'].includes(r.status));
function seasonRegistrationQueue() {
  return panel(tr('队伍赛季注册', 'Team season registrations'), table(tr('赛季许可申请', 'Season license requests'), [tr('队伍', 'Team'), tr('赛季', 'Season'), tr('状态', 'Status'), tr('申请人', 'Applicant'), tr('操作', 'Action')], state.seasonLicenses.map((r, i) => [r.team, r.season, badge(r.status === 'submitted' ? 'pending' : r.status), r.applicant, is('platform') && r.status === 'submitted' ? btn(tr('审核激活', 'Review activation'), `review-license:${i}`, 'text small') : r.status === 'submitted' && r.applicant === names[state.role] ? btn(tr('取消申请', 'Cancel request'), `cancel-license:${i}`, 'text small') : esc(r.comment || '—')]), false));
}
const eventNames = ['2026 VEX 机器人华东区域公开赛', '2026 青少年机器人创新挑战赛', '2026 VEX 校际邀请赛'];
function competitionCards() {
  const config = editionConfig();
  if (state.season !== '2026-2027') return empty(tr('本赛季暂无可见赛事', 'No visible competitions this season'), tr('赛事发布后将在这里展示。历史参赛档案仅授权管理员可查。', 'Published competitions will appear here. Historical participation records require administrator access.'));
  return `<div class="competition-grid">${eventNames.map((name, i) => ({name: i === 0 ? config.name : name, i})).filter(({name, i}) => name.toLowerCase().includes(state.search.toLowerCase()) && (state.tab !== 'open' || i !== 2) && (state.tab !== 'mine' || i < 2)).map(({name, i}) => `<article class="panel competition-card"><div class="competition-cover"><span><span class="small muted">2026–2027 · ROBOTICS</span><br><span class="event-symbol">${['VEX', 'YRIC', 'VEX'][i]}</span></span><span class="symbol-ring">${icon(i === 1 ? 'robot' : 'trophy')}</span></div><div class="card-content">${badge(i === 2 ? 'upcoming' : 'enrolling')}<h2>${esc(name)}</h2><p class="muted small">${tr('华东地区青少年科技教育协作中心', 'East China Youth STEM Education Center')}</p><div class="card-meta"><span>${icon('calendar')}${i === 0 ? config.start.slice(0, 10) : i === 2 ? '2026-12-12' : '2026-11-28'} — ${i === 0 ? config.end.slice(5, 10) : i === 2 ? '12-13' : '11-29'}</span><span>${icon('pin')}${i === 0 ? esc(config.venue) : i === 1 ? '杭州' : '上海'} · ${tr('线下赛事', 'In-person')}</span><span>${icon('team')}V5RC / VIQRC · ${tr('小学 / 初中 / 高中', 'Elementary / Middle / High school')}</span></div><div class="card-bottom"><span class="muted small">${tr('报名截止', 'Deadline')} ${i === 0 ? config.enrollEnd.slice(5, 10) : i === 2 ? '12-05' : '11-23'}</span>${btn(tr('查看赛事', 'View competition'), `open-competition:${i}`, 'small', 'arrow')}</div></div></article>`).join('')}</div>`;
}
function competitions() {
  if (can('competition:manage')) return renderCompetitionRegistry();
  return `<header class="catalogue-heading"><div><p class="eyebrow">COMPSPHERE / COMPETITIONS</p><h1 id="page-title" tabindex="-1">${tr('赛事中心', 'Competition center')}</h1><p class="muted">${tr('选择赛场，准备下一次出发。', 'Find your field. Prepare for what’s next.')}</p></div>${currentSeasonContext()}</header><div class="catalogue-tools">${tabs([['all', tr('全部赛事', 'All competitions')], ['open', tr('正在报名', 'Open')], ...(state.role !== 'visitor' ? [['mine', tr('本单位参与', 'My organization')]] : [])])}<search>${filters(tr('搜索赛事', 'Search competitions'))}</search>${is('platform') ? btn(tr('创建赛事', 'Create competition'), 'new-competition', 'primary', 'plus') : ''}</div>` + competitionCards();
}
function competitionDetail() { return renderPublicCompetitionDetail(); }

function registrations() {
  if (!can('admin:access')) return renderParticipantRegistrations();
  let rows = state.registrations.filter(matchSearch).filter((r) => state.status === 'all' || r.status === state.status);
  if (is('student', 'coach')) rows = rows.filter((r) => r.code === '1024A' || is('coach') && r.code === '1024C');
  return pageHead(is('student') ? tr('我的报名', 'My registrations') : label('registrations'), tr('查看本场提交、审核进度与历史版本。', 'Track submitted details, review progress and submission history.'), is('student', 'coach') ? link(tr('新增报名', 'New registration'), 'registration', 'primary', 'plus') : '') + `<section class="panel">${filters(tr('搜索队号、队伍或报名编号', 'Search team or registration ID'), true)}${registrationRows(rows)}</section>`;
}
function reviews() {
  const rows = state.registrations.filter(matchSearch).filter((r) => state.status === 'all' ? r.status === 'pending' : r.status === state.status);
  const pending = state.registrations.filter((r) => r.status === 'pending').length;
  return pageHead(tr('报名审核', 'Registration review'), tr('华东区域公开赛 · 2026 赛季', 'East China Regional Open · 2026 season'), '<span class="tag amber">' + pending + ' ' + tr('项待处理', 'pending') + '</span>') + '<section class="panel">' + filters(tr('搜索队伍或报名编号', 'Search teams or registration IDs'), true) + registrationRows(rows, true) + '</section>';
}
function registrationForm() {
  const current = state.registrations[0];
  const frozen = !['draft', 'returned', 'rejected'].includes(current.status);
  const disabled = frozen ? 'disabled' : '';
  return pageHead(tr('团队报名', 'Team registration'), `${eventNames[0]} · V5RC`, link(tr('返回报名列表', 'Back to registrations'), 'registrations')) + `<div class="steps"><span class="step active"><b>1</b>${tr('选择队伍与组别', 'Team & division')}</span><span class="step ${frozen ? 'active' : ''}"><b>2</b>${tr('参赛资料', 'Materials')}</span><span class="step ${frozen ? 'active' : ''}"><b>3</b>${tr('提交与审核', 'Submit & review')}</span></div>${notice(frozen ? tr(`本场报名已提交（第 ${current.round} 版），资料与成员已冻结。队伍档案后续变更不会修改本次提交。`, `Submission v${current.round} is frozen. Later team changes will not alter this registration.`) : tr('填写本场报名资料。学段由提交人选择，成员须来自已审核队伍。', 'Choose a division for this competition and use members from the approved team.'))}<form id="registration-form"><div class="cols"><section class="panel"><div class="form-section"><h2>${tr('队伍与参赛组别', 'Team & division')}</h2><div class="form-grid">${selectField('reg-team', tr('参赛队伍 *', 'Team *'), [['1024A', '1024A · V5RC · 逐光机器人队']], disabled)}${field('reg-revision', tr('已审核队伍版本', 'Approved team version'), tr('版本 3 · 2026-11-15 生效', 'Version 3 · Effective Nov 15'), 'text', 'disabled')}${selectField('reg-level', tr('本场学段 *', 'Declared school level *'), [['HS', tr('高中', 'High school')], ['MS', tr('初中', 'Middle school')]], disabled)}${selectField('reg-group', tr('参赛组别 *', 'Division *'), [['HS', tr('V5RC 高中组', 'V5RC High school')], ['MS', tr('V5RC 初中组', 'V5RC Middle school')]], disabled)}</div></div><div class="form-section"><h2>${tr('本场参赛成员', 'Students in this submission')}</h2>${table(tr('学生成员', 'Student roster'), [tr('姓名', 'Name'), tr('身份', 'Role'), tr('年级', 'Grade'), tr('本场状态', 'Submission')], ['林知远', '苏予宁', '唐星禾', '陈予安'].map((name, i) => [name, i === 0 ? tr('队长', 'Captain') : tr('队员', 'Member'), tr('高中一年级', 'Grade 10'), badge(frozen ? 'approved' : 'draft')]), false)}<p class="muted small" style="margin-top:14px">${tr('指导教练：陈老师。新增或换人请联系单位管理员审核队伍资料。', 'Coach: Ms. Chen. Ask your organization admin to approve team member changes.')}</p></div><div class="form-section"><h2>${tr('联系与材料', 'Contact & materials')}</h2><div class="form-grid">${field('reg-contact', tr('联系人 *', 'Contact name *'), '陈老师', 'text', `required autocomplete="name" ${disabled}`)}${field('reg-phone', tr('联系电话 *', 'Contact phone *'), '', 'tel', `required autocomplete="tel" placeholder="${tr('填写联系人电话', 'Enter contact phone')}" ${disabled}`)}<div class="span-2">${field('reg-project', tr('作品名称 *', 'Project title *'), '逐光 · 自主协作机器人', 'text', `required ${disabled}`)}</div><div class="span-2 upload-zone">${icon('upload')}<p>${tr('参赛授权与作品说明', 'Consent & project overview')}</p>${frozen ? '<p class="muted small">consent-demo.pdf · project-demo.pdf</p>' : `<label class="small muted">PDF / JPEG / PNG<input type="file" id="reg-files" multiple accept=".pdf,.jpg,.jpeg,.png"></label>`}</div></div></div><div class="form-foot"><label class="check"><input name="consent" type="checkbox" required ${frozen ? 'checked disabled' : state.form.consent ? 'checked' : ''}>${tr('已取得学生或监护人授权，并确认报名资料。', 'I have student / guardian consent and confirm the details.')}</label><div class="actions">${frozen ? current.status === 'pending' ? btn(tr('取消并修改', 'Cancel & edit'), 'cancel-registration', '', 'file') : badge(current.status) : `<button class="button primary" type="submit">${icon('check')}${tr('确认提交', 'Submit registration')}</button>`}</div></div></section><div class="stack">${panel(tr('提交摘要', 'Submission summary'), `<dl class="detail-grid"><div><dt>${tr('报名编号', 'Registration ID')}</dt><dd class="mono">${current.id}</dd></div><div><dt>${tr('当前状态', 'Status')}</dt><dd>${badge(current.status)}</dd></div><div><dt>${tr('赛项', 'Event')}</dt><dd>V5RC</dd></div><div><dt>${tr('参赛学生', 'Students')}</dt><dd>4 ${tr('人', 'students')}</dd></div></dl>`)}${panel(tr('报名须知', 'Before submitting'), `<p class="muted small">${tr('提交后资料与成员冻结。尚未审核可取消修改；已有审核决定则按退回或驳回流程修改重提。重提仍须在报名时间窗内。', 'Submission freezes the details and roster. Cancel to edit before review; after a decision, use the return or rejection process. Resubmission must be within the deadline.')}</p>`)}</div></div></form>`;
}

function teams() {
  if (!canManageTeams()) return renderParticipantTeams();
  return pageHead(label('teams'), tr('统一维护队伍档案、学生归属与成员变更。', 'Manage team records, student membership and changes.'), canManageTeams() ? btn(tr('创建队伍', 'Create team'), 'new-team', 'primary', 'plus') : `<span class="tag">${tr('本单位查看', 'Own organization · Read only')}</span>`) + `<section class="panel">${filters(tr('搜索队号或队伍名称', 'Search team number or name'))}${table(tr('本单位队伍', 'Organization teams'), [tr('队伍 / 队号', 'Team / Number'), tr('赛项', 'Event'), tr('队长', 'Captain'), tr('教练', 'Coach'), tr('成员', 'Members'), tr('本赛季许可', 'Season license'), tr('操作', 'Action')], state.teams.filter(matchSearch).map((t) => [`${t.name}<span class="muted mono">${t.code}</span>`, t.event, t.captain, t.coach, `${t.count} ${tr('人', 'students')}`, seasonLicenseBadge(t.code), btn(tr('查看', 'View'), `team-detail:${t.code}`, 'text small')]))}</section>`;
}
function students() {
  return pageHead(label('students'), tr('本单位学生账户。每名学生同时仅能归属一支队伍。', 'Students in your organization. Each student can belong to one current team.'), btn(tr('代建学生账户', 'Create student account'), 'new-student', 'primary', 'plus')) + `<section class="panel">${filters(tr('搜索姓名、学号或队号', 'Search name, student ID or team'))}${table(tr('学生账户', 'Student accounts'), [tr('学生', 'Student'), tr('年级', 'Grade'), tr('当前队伍', 'Current team'), tr('证件', 'Document'), tr('账户状态', 'Account'), tr('操作', 'Action')], state.students.filter(matchSearch).map((s, i) => [`<div class="person"><span class="avatar">${s.name.slice(0, 1)}</span><div>${s.name}<small>${s.code}</small></div></div>`, s.group, s.team || `<span class="muted">${tr('未加入队伍', 'No team')}</span>`, `${s.doc === 'id' ? tr('身份证', 'ID card') : tr('护照', 'Passport')} · ${s.last4}`, badge(s.status), btn(tr('查看档案', 'View profile'), `student-detail:${i}`, 'text small')]))}</section>`;
}
function requests() {
  return pageHead(label('requests'), tr('队伍资料、成员变更与证件更正申请。申请人不能自审。', 'Review team, membership and document changes. Applicants cannot review their own requests.')) + `<section class="panel">${filters()}${table(tr('资料审核', 'Change requests'), [tr('申请对象', 'Subject'), tr('申请类型', 'Type'), tr('申请人', 'Applicant'), tr('状态', 'Status'), tr('提交时间', 'Submitted'), tr('操作', 'Action')], state.requests.filter(matchSearch).map((r) => [r.name, tr(...r.title), r.applicant, badge(r.status), r.date, btn(tr('查看申请', 'View request'), `request-detail:${state.requests.indexOf(r)}`, 'text small')]))}</section>` + seasonRegistrationQueue();
}

function awards() {
  return pageHead(label('awards'), tr('2026 VEX 华东区域公开赛 · 仅学生参赛奖项', '2026 VEX East China Open · Student participation awards only'), btn(tr('导入获奖名单', 'Import awards'), 'import-awards', '', 'upload') + btn(tr('提交名单审核', 'Submit roster for approval'), 'submit-roster', 'primary', 'check')) + notice(tr('当前名单为编辑状态。确认后锁定，通过的报名版本将作为逐人发证依据。', 'This roster is editable. Confirmation locks it and fixes the approved registration version for issuing certificates.')) + `<section class="panel">${tabs([['all', 'V5RC · ' + tr('高中组', 'High school')], ['middle', 'V5RC · ' + tr('初中组', 'Middle school')], ['iq', 'VIQRC']])}${table(tr('学生获奖名单', 'Student awards'), [tr('队伍', 'Team'), tr('报名编号', 'Registration'), tr('奖项', 'Award'), tr('发证学生', 'Students'), tr('名单状态', 'Roster')], state.registrations.filter((r) => r.status === 'approved').map((r, i) => [r.team, `<span class="mono">${r.id}</span>`, tr(i ? '二等奖' : '一等奖', i ? 'Second prize' : 'First prize'), `${r.count} ${tr('人', 'students')}`, badge('draft')]))}</section>`;
}
function certificates() {
  if (is('org', 'coach')) return pageHead(label('certificates'), tr('证书仅发给参赛学生，教练与单位管理员不领取学生证书。', 'Certificates are issued only to participating students.')) + panel(tr('我的证书', 'My certificates'), empty(tr('暂无个人证书', 'No personal certificates'), tr('查看完整证书发放台请切换为赛事管理员预览。', 'Switch to the competition admin preview to explore certificate management.')));
  return pageHead(is('student') ? tr('我的证书', 'My certificates') : label('certificates'), tr('证书按本场审核通过版本的学生队员逐人发放。', 'Certificates are issued individually to students in the approved submission.'), is('event', 'platform') ? btn(tr('生成证书', 'Generate certificates'), 'generate-certificates', 'primary', 'file') : '') + `<div class="competition-grid">${[0, 1].map((i) => `<article class="panel"><div class="certificate"><div class="eyebrow">COMPSPHERE · 2026</div><div class="seal">${icon('trophy')}</div><h2>${tr('荣誉证书', 'CERTIFICATE')}</h2><p class="muted small">${tr('授予', 'Presented to')}</p><strong>${is('student') ? '林知远' : i ? '苏予宁' : '林知远'}</strong><p>${tr('机器人挑战赛 · 一等奖', 'Robotics Challenge · First prize')}</p><p class="muted small mono">CS-2026-0000${i + 1}</p></div><div class="card-content" style="padding:18px"><div class="actions" style="justify-content:space-between">${badge('issued')}${btn(tr('查看证书', 'View certificate'), `certificate-detail:${i}`, 'text small', 'arrow')}</div></div></article>`).join('')}</div>`;
}
function edition() { return renderEditionManager(); }
function historicalRecords() {
  return pageHead(label('history'), tr('关闭届次的报名和成员历史仅在授权管理范围内保留。', 'Closed edition registrations and member history are retained for authorized administrators.')) + notice(tr('按提交时单位和赛事范围读取，不因学生转队或当前单位变化而转移历史。', 'Access follows the original submission scope. Later team or organization changes do not transfer history.')) + '<section class="panel"><div class="panel-head"><h2>' + tr('2025 华东区域邀请赛', '2025 East China Invitational') + '</h2>' + badge('closed') + '</div>' + table(tr('历史参赛档案', 'Historical participation records'), [tr('队伍', 'Team'), tr('赛项与组别', 'Event / Division'), tr('历史学生成员', 'Students at submission'), tr('结果', 'Result'), tr('提交版本', 'Version')], [['1024A · 逐光机器人队', 'V5RC · ' + tr('高中组', 'High school'), '林知远 / 苏予宁 / 程以安', tr('二等奖', 'Second prize'), 'v2'], ['1024B · 星河探索队', 'VIQRC · ' + tr('初中组', 'Middle school'), '许星遥 / 杨知夏 / 周若澄', tr('一等奖', 'First prize'), 'v1']]) + '</section>';
}

function access() {
  return pageHead(label('access'), tr('高级别赛事可仅向指定队伍开放。准入不替代报名审核。', 'Restrict this edition to selected teams. Eligibility does not replace registration review.'), btn(tr('导入准入队伍', 'Import eligible teams'), 'import-allowlist', 'primary', 'upload')) + panel(tr('本届准入方式', 'Edition entry mode'), `<div class="form-grid">${selectField('access-mode', tr('报名范围', 'Entry mode'), [['allowlist', tr('仅名单内队伍', 'Allowlisted teams only')], ['open', tr('符合条件的队伍均可报名', 'Open to eligible teams')]])}<p class="muted small" style="align-self:end">${tr('按队号 + 稳定赛项识别队伍，成员变化不转移队伍资格。', 'Teams are identified by number + event. Qualification follows team identity.')}</p></div>`) + `<section class="panel"><div class="panel-head"><h2>${tr('准入队伍名单', 'Eligible teams')}</h2><span class="tag blue">5 ${tr('支队伍', 'teams')}</span></div>${table(tr('准入名单', 'Allowlist'), [tr('队号', 'Team number'), tr('赛项', 'Event'), tr('队伍名称', 'Team name'), tr('所属单位', 'Organization'), tr('来源', 'Source')], state.teams.map((t) => [t.code, t.event, t.name, '海川实验学校', tr('导入', 'Import')]))}</section>`;
}
function imports() {
  return pageHead(label('imports'), tr('先预览匹配结果，再确认导入；任务可在后台继续。', 'Preview matches before confirming imports. Tasks continue in the background.'), btn(tr('新建导入任务', 'New import'), 'import-students', 'primary', 'upload')) + `<div class="cols"><section class="panel"><div class="panel-head"><h2>${tr('最近任务', 'Recent jobs')}</h2></div>${table(tr('导入导出任务', 'Import and export jobs'), [tr('任务', 'Job'), tr('记录数', 'Records'), tr('结果', 'Result'), tr('创建时间', 'Created'), tr('操作', 'Action')], [[tr('学生账户导入', 'Student account import'), '24', badge('approved'), '2026-11-16 14:32', btn(tr('查看结果', 'View result'), 'import-result', 'text')], [tr('报名明细导出', 'Registration export'), '12', badge('approved'), '2026-11-16 10:08', btn(tr('下载演示清单', 'Download sample list'), 'download', 'text')]])}</section>${panel(tr('导入前检查', 'Before importing'), `<div class="timeline">${[[tr('下载对应模板', 'Get the correct template'), tr('保持表头与字段格式', 'Keep column names and formats')], [tr('上传并预览', 'Upload and preview'), tr('检查重复、未知队号与人员冲突', 'Check duplicate, unknown and conflicting entries')], [tr('确认后生效', 'Confirm changes'), tr('错误行单独处理，保留操作记录', 'Resolve errors separately with an audit trail')]].map(([a, b]) => `<div class="timeline-row"><span class="timeline-point"></span><div>${a}<p class="muted">${b}</p></div></div>`).join('')}</div>`)}</div>`;
}
function organizations() {
  return pageHead(label('organizations'), tr('单位先申请审核，通过后建立正式单位。', 'Organizations become active after their application is approved.'), btn(tr('发起单位申请', 'New organization request'), 'new-organization', 'primary', 'plus')) + `<section class="panel">${filters()}${table(tr('单位列表', 'Organizations'), [tr('单位名称', 'Organization'), tr('类型', 'Type'), tr('管理员', 'Admin'), tr('队伍', 'Teams'), tr('状态', 'Status'), tr('操作', 'Action')], [['海川实验学校', tr('学校', 'School'), '陈老师', '12', badge('active'), btn(tr('管理', 'Manage'), 'organization-detail', 'text')], ['远山科技教育中心', tr('企业', 'Enterprise'), '周老师', '8', badge('active'), btn(tr('管理', 'Manage'), 'organization-detail', 'text')], ['新知实验学校', tr('学校', 'School'), '—', '—', badge('pending'), btn(tr('审核申请', 'Review request'), 'organization-request', 'text')]])}</section>`;
}
function rolesPage() {
  return pageHead(label('roles'), tr('平台管理员分配管理角色，单位与赛事管理范围相互独立。', 'Platform admins grant management roles. Organization and competition scopes remain separate.'), btn(tr('分配角色', 'Grant role'), 'grant-role', 'primary', 'plus')) + `<section class="panel">${table(tr('管理授权', 'Management grants'), [tr('人员', 'Person'), tr('角色', 'Role'), tr('管理范围', 'Scope'), tr('授予时间', 'Granted'), tr('操作', 'Action')], [['陈老师', tr('单位管理员', 'Organization admin'), '海川实验学校', '2026-09-01', btn(tr('更换管理员', 'Replace admin'), 'replace-admin', 'text')], ['周老师', tr('赛事审核员', 'Reviewer'), eventNames[0], '2026-11-01', btn(tr('查看授权', 'View grant'), 'view-grant', 'text')]])}</section>`;
}
function profile() {
  return pageHead(label('profile'), tr('维护个人信息、证件照和账号安全。', 'Manage your details, document photo and account security.')) + `<div class="cols"><form id="profile-form" class="panel"><div class="form-section"><h2>${tr('证件照', 'Document photo')}</h2><div class="profile-photo"><div class="photo-box">${state.photo ? `<img src="${esc(state.photo)}" alt="${tr('本地证件照预览', 'Local document photo preview')}">` : icon('user')}</div><div class="photo-options"><label class="button">${icon('upload')}${tr('上传证件照', 'Upload photo')}<input type="file" id="photo-upload" class="sr-only" accept="image/jpeg,image/png"></label><p class="muted small">JPEG / PNG · ≤ 5MB · ${tr('建议 3:4', '3:4 recommended')}</p><p class="muted small">${tr('仅用于个人档案，不作为公开头像。', 'Private profile use; not your public avatar.')}</p>${state.photo ? btn(tr('删除照片', 'Remove photo'), 'remove-photo', 'text small') : ''}</div></div></div><div class="form-section"><h2>${tr('基本资料', 'Basic information')}</h2><div class="form-grid">${field('profile-name', tr('姓名', 'Name'), names[state.role], 'text', 'required autocomplete="name"')}${field('profile-birth', tr('出生日期', 'Date of birth'), '', 'date', 'autocomplete="bday"')}${field('profile-org', tr('所属单位', 'Organization'), '海川实验学校', 'text', 'disabled')}${field('profile-phone', tr('联系电话', 'Phone'), '', 'tel', 'autocomplete="tel"')}${field('profile-email', tr('邮箱（可选）', 'Email (optional)'), '', 'email', 'autocomplete="email"')}${selectField('profile-level', tr('学段（档案参考）', 'School level (reference)'), [['HS', tr('高中', 'High school')], ['MS', tr('初中', 'Middle school')], ['ES', tr('小学', 'Elementary school')]])}</div></div><div class="form-foot"><p class="muted small">${tr('证件号码更正需要管理员审核。', 'Document changes require administrator approval.')}</p><button class="button primary" type="submit">${tr('保存资料', 'Save profile')}</button></div></form><div class="stack">${panel(tr('证件信息', 'Identity document'), `<dl class="detail-grid"><div><dt>${tr('证件类型', 'Type')}</dt><dd>${tr('身份证', 'ID card')} · CN</dd></div><div><dt>${tr('号码末四位', 'Last four characters')}</dt><dd>0027</dd></div></dl><div class="divider"></div>${btn(tr('申请更正证件', 'Request correction'), 'identity-change', '', 'shield')}`)}${panel(tr('账号安全', 'Account security'), `<div class="mini-row"><span>${tr('登录密码', 'Password')}</span>${btn(tr('修改', 'Change'), 'change-password', 'text small')}</div><p class="muted small">${tr('支持邮箱或证件号 + 密码登录。', 'Sign in with email or document + password.')}</p>`)}</div></div>`;
}
function settings() {
  return pageHead(label('settings'), tr('选择适合你的语言与外观。', 'Choose your preferred language and appearance.')) + panel(tr('语言与外观', 'Language & appearance'), `<div class="mini-row"><div><h3>${tr('显示语言', 'Display language')}</h3><p class="muted small">${tr('业务数据保留原文。', 'User-entered data keeps its original language.')}</p></div><select id="settings-lang" aria-label="${tr('显示语言', 'Display language')}"><option value="zh" ${state.lang === 'zh' ? 'selected' : ''}>简体中文</option><option value="en" ${state.lang === 'en' ? 'selected' : ''}>English</option></select></div><div class="divider"></div><div class="mini-row"><div><h3>${tr('主题模式', 'Theme')}</h3><p class="muted small">${tr('支持浅色、深色或跟随系统。', 'Choose light, dark, or follow your system.')}</p></div><select id="settings-theme" aria-label="${tr('主题模式', 'Theme')}">${[['light', tr('浅色', 'Light')], ['dark', tr('深色', 'Dark')], ['system', tr('跟随系统', 'System')]].map(([id, text]) => `<option value="${id}" ${state.theme === id ? 'selected' : ''}>${text}</option>`).join('')}</select></div><div class="divider"></div><p class="muted small">${tr('设计预览中的变更仅保留在本次浏览中。', 'Changes in this design preview last for the current session only.')}</p>`);
}
function notices() {
  return pageHead(label('notices'), tr('查看报名、资料审核和系统通知。', 'Registration, review and account updates.')) + panel(tr('今天', 'Today'), [
    [tr('报名已通过', 'Registration approved'), tr('星河探索队已通过华东区域公开赛报名审核。', 'Star River passed registration review for the Regional Open.'), '09:42', 'registrations'],
    [tr('队伍变更待审核', 'Team change awaiting review'), tr('逐光机器人队提交了成员变更申请。', 'Chasing Light submitted a team member change request.'), '09:10', 'requests'],
    [tr('报名材料需要补充', 'Registration materials need attention'), tr('请在 11 月 23 日前补充授权材料并重新提交。', 'Add consent documents and resubmit before November 23.'), '08:32', 'registrations'],
  ].map(([title, detail, time, page]) => `<div class="task-row"><span class="task-icon">${icon('bell')}</span><div class="task-text"><h3>${title}</h3><p>${detail}</p></div><span class="muted small">${time}</span>${link(tr('查看', 'View'), navigation().some(([p]) => p === page) ? page : 'registrations', 'text small')}</div>`).join(''));
}
function audit() {
  return pageHead(label('audit'), tr('保留关键变更的操作人、对象、时间与结果。', 'A record of who changed what, when, and the result.')) + `<section class="panel">${filters()}${table(tr('操作记录', 'Activity log'), [tr('时间', 'Time'), tr('操作人', 'Actor'), tr('动作', 'Action'), tr('对象', 'Subject'), tr('结果', 'Result')], [['2026-11-17 10:24', '周老师', tr('提交队伍变更', 'Submitted team change'), '1024A · V5RC', badge('pending')], ['2026-11-17 09:42', tr('赛事审核员', 'Reviewer'), tr('通过报名', 'Approved registration'), 'REG-26-0081', badge('approved')], ['2026-11-17 09:10', '陈老师', tr('代建学生账户', 'Created student account'), 'S202605', badge('approved')]].filter(matchSearch))}</section>`;
}

function bindingConflict(student, team) {
  return state.bindings.find((b) => seasons.some((season) => season.id === b.season && season.status !== 'archived') && b.student === student.code && b.event === team.event && b.team !== team.code);
}
function membership() { return renderMembershipPage(); }
function transfers() {
  return pageHead(label('transfers'), tr('仅平台管理员可执行跨队特批。单位管理员不能解除赛季绑定。', 'Only platform admins can approve a restricted transfer. Organization admins cannot release season bindings.')) +
    notice(tr('批准时检查原队与目标队报名；旧报名取消/驳回并保留快照，锁定名单或有效证书须先处理。', 'Check source and target registrations before approval. Preserve old snapshots and resolve locked rosters or active certificates first.')) +
    `<section class="panel">${table(tr('换队申请', 'Transfer requests'), [tr('学生', 'Student'), tr('原队', 'Source'), tr('目标队', 'Target'), tr('状态', 'Status'), tr('申请人', 'Applicant'), tr('操作', 'Action')], state.transferRequests.map((r, i) => [r.student.name, `${r.from} · ${r.event}`, `${r.to} · ${r.event}`, badge(r.status), r.student.name, btn(tr('查看申请', 'Review request'), `membership-review:${i}`, 'text small')]))}</section>`;
}
function transferApplication() {
  const student = state.students.find((s) => s.code === 'S202601');
  const binding = state.bindings.find((b) => b.student === student.code);
  dialog(tr('向平台申请换队', 'Apply for platform transfer'), tr('此申请单独提交给平台管理员，普通单位审核不能代替。', 'This request goes to the platform administrator separately from organization review.'),
    `<form id="transfer-application" class="stack" style="gap:18px">${notice(`${binding.season} · ${binding.event} · ${tr('当前绑定', 'Bound team')} ${binding.team}`)}${selectField('transfer-target', tr('目标队伍', 'Target team'), state.teams.filter((t) => t.event === binding.event && t.code !== binding.team).map((t) => [t.code, `${t.code} · ${t.event} · ${t.name}`]))}<div class="field"><label for="transfer-reason">${tr('换队原因 *', 'Reason *')}</label><textarea id="transfer-reason" required rows="3"></textarea></div><p class="muted small">${tr('申请期间原归属及赛季绑定不变。批准后由平台执行入队，不会直接改写已提交报名。', 'Membership and eligibility stay unchanged while pending. The platform applies approved transfers without rewriting submitted snapshots.')}</p><button type="submit" class="button primary">${tr('提交换队申请', 'Submit transfer request')}</button></form>`);
}
function handleMembershipAction(actionString) {
  const [action, arg] = actionString.split(':');
  if (!action.startsWith('membership-')) return false;
  const student = state.students.find((s) => s.code === 'S202601');
  if (action === 'membership-leave') {
    dialog(tr('确认自主退队', 'Confirm leaving the team'), `${student.name} · ${student.team}`,
      `${notice(tr('退队后同赛季同赛项仍绑定原队，不能直接加入其他队伍。本场已提交阵容及历史保持原样。', 'Your original season binding remains. Leaving does not allow a different team or change submitted rosters.'), 'amber')}<div class="field"><label for="leave-reason">${tr('退队原因 *', 'Reason *')}</label><textarea id="leave-reason" rows="3" required></textarea></div>`,
      btn(tr('暂不退队', 'Keep membership'), 'close') + btn(tr('确认退队', 'Confirm leave'), 'membership-apply-leave', 'danger'));
    $('#drawer [data-action="close"]').setAttribute('autofocus', '');
  }
  if (action === 'membership-apply-leave') {
    if (!is('student') || !student.team) return true;
    const reason = $('#leave-reason').value.trim();
    if (!reason) { $('#leave-reason').reportValidity(); return true; }
    student.lastTeam = student.team.split(' · ')[0]; const oldTeam = state.teams.find((t) => t.code === student.lastTeam); if (oldTeam?.captain === student.name) oldTeam.captain = '—'; student.team = '';
    state.membershipAudit.push({ by: student.name, text: [`自主退出 ${student.lastTeam}；${reason}`, `Left ${student.lastTeam}; ${reason}`] });
    closeDialog(); render(); toast(tr('已退队。赛季绑定仍保留；可以申请回原队或向平台申请换队。', 'You left the team. Season binding is retained; rejoin the original team or request a platform transfer.'));
  }
  if (action === 'membership-cancel-request') { const request = state.transferRequests[Number(arg)]; if (is('student') && request.student.code === student.code && request.status === 'pending') { request.status = 'withdrawn'; render(); toast(tr('已撤回申请，保留历史；可以重新申请。', 'Request withdrawn and retained; you may apply again.')); } }
  if (action === 'membership-transfer') transferApplication();
  if (action === 'membership-rejoin') {
    const team = state.teams.find((t) => t.code === student.lastTeam);
    if (student.team || !team || bindingConflict(student, team)) { toast(tr('当前归属或参赛绑定已变化，请重新核对。', 'Your membership or eligibility changed; check again.')); return true; }
    if (state.requests.some((r) => r.status === 'pending' && r.memberChange?.index === state.students.indexOf(student))) { toast(tr('已有成员变更申请待处理。', 'A membership change is already pending.')); return true; }
    state.requests.push({ name: team.name, title: ['原队回归申请', 'Rejoin original team'], applicant: student.name, status: 'pending', date: '2026-11-17 15:00', memberChange: { index: state.students.indexOf(student), operation: 'join', team } });
    toast(tr('原队入队申请已提交，由单位审核即可，无需平台特批。', 'Rejoin request submitted for organization review; platform approval is not required.'));
  }
  if (action === 'membership-review') {
    if (!is('platform')) return true;
    const request = state.transferRequests[Number(arg)];
    const affected = state.registrations.filter((r) => r.event === request.event && [request.from, request.to].includes(r.code));
    dialog(tr('审核特批换队', 'Review special transfer'), `${request.student.name} · ${request.from} → ${request.to}`,
      `${notice(tr('批准会同时更新当前归属与赛季绑定。原队报名须更正；目标队已提交报名不会自动加人。', 'Approval updates membership and season eligibility together. Correct the source registration; target submissions are not automatically changed.'), 'amber')}<p>${esc(request.reason)}</p><div class="divider"></div>${table(tr('受影响报名', 'Affected registrations'), [tr('队伍', 'Team'), tr('编号', 'Registration'), tr('状态', 'Status')], affected.map((r) => [r.team, r.id, badge(r.status)]), false)}<div class="divider"></div><label class="check"><input type="checkbox" id="transfer-check">${tr('已核验学生授权、相关报名、准入及名单/证书状态', 'Verified consent, affected registrations, eligibility, roster and certificate state')}</label><div class="field" style="margin-top:16px"><label for="transfer-comment">${tr('审核意见 *', 'Review notes *')}</label><textarea id="transfer-comment" rows="3" required></textarea></div>`, request.status === 'pending' ? btn(tr('驳回', 'Reject'), `membership-reject:${arg}`, 'danger') + btn(tr('批准并执行换队', 'Approve & apply transfer'), `membership-approve:${arg}`, 'primary') : btn(tr('关闭', 'Close'), 'close'), true);
  }
  if (['membership-approve', 'membership-reject'].includes(action)) {
    if (!is('platform')) return true;
    const request = state.transferRequests[Number(arg)];
    const comment = $('#transfer-comment').value.trim();
    if (!comment) { $('#transfer-comment').reportValidity(); return true; }
    if (action === 'membership-reject') { request.status = 'rejected'; closeDialog(); render(); return true; }
    if (!$('#transfer-check').checked) { toast(tr('请先核验并勾选确认。', 'Verify the affected records and confirm first.')); return true; }
    const binding = state.bindings.find((b) => b.student === request.student.code && b.event === request.event && b.season === request.season);
    const team = state.teams.find((t) => t.code === request.to && t.event === request.event);
    if (!binding || state.bindings.some((b) => b.student === request.student.code && b.event === request.event && b.season !== request.season && b.team !== request.to && seasons.some((season) => season.id === b.season && season.status !== 'archived'))) { toast(tr('存在其他有效赛季的绑定，需要关联申请一并审核。', 'Other active season bindings require linked transfer approvals.')); return true; }
    if (!team || binding.version !== request.baseVersion || request.student.team !== request.baseMembership || request.status !== 'pending') { toast(tr('绑定或当前归属已变化，请重新提交申请。', 'The binding or membership changed. Submit a new request.')); return true; }
    for (const reg of state.registrations.filter((r) => r.code === request.from && r.event === request.event)) {
      if (reg.status === 'pending') reg.status = 'draft';
      else if (reg.status === 'approved') reg.status = 'rejected';
    }
    request.student.lastTeam = request.from;
    request.student.team = `${team.code} · ${team.event}`;
    for (const b of state.bindings.filter((b) => b.student === request.student.code && b.event === request.event && b.season === request.season)) { b.team = team.code; b.version += 1; }
    request.status = 'approved'; request.comment = comment;
    state.membershipAudit.push({ by: names[state.role], text: [`平台特批 ${request.from} → ${request.to}；${comment}`, `Platform transfer ${request.from} → ${request.to}; ${comment}`] });
    closeDialog(); render(); toast(tr('演示换队已执行，旧报名版本保留；目标报名需单独更正重提。', 'Sample transfer applied. Old submissions are retained; the target registration requires separate correction.'));
  }
  return true;
}
function handleMembershipForm(form) {
  if (form.id !== 'transfer-application') return false;
  const student = state.students.find((s) => s.code === 'S202601');
  const binding = state.bindings.find((b) => b.student === student.code);
  const target = $('#transfer-target').value;
  if (state.transferRequests.some((r) => r.student.code === student.code && r.status === 'pending')) { toast(tr('已有换队申请待平台处理。', 'A transfer request is already pending.')); return true; }
  state.transferRequests.push({ student, from: binding.team, to: target, season: binding.season, event: binding.event, reason: $('#transfer-reason').value.trim(), baseVersion: binding.version, baseMembership: student.team, status: 'pending' });
  closeDialog(); render(); toast(tr('已提交给平台管理员，原归属与赛季绑定尚未改变。', 'Submitted to the platform administrator. Membership and binding are unchanged.'));
  return true;
}

function publicLayout(content) { return renderPublicLayout(content); }
function portal() { return renderDiscovery(); }
function login() {
  const documentMode = state.tab !== 'email';
  return publicLayout(`<div class="login-grid"><section class="login-intro"><div class="eyebrow">WELCOME TO COMPSPHERE</div><h1 id="page-title" tabindex="-1">${tr('下一场挑战，<br>从这里开始。', 'Your next challenge<br>starts here.')}</h1><p class="muted" style="margin-top:22px">${tr('学生、教练与赛事组织者，共用一个清晰的竞赛空间。', 'One clear competition workspace for students, coaches and organizers.')}</p><div class="divider"></div><p class="muted small">${tr('单位代建账户可使用证件号和初始密码登录，无需绑定邮箱。', 'Organization-created student accounts can sign in with a document number and temporary password. No email required.')}</p></section><form id="login-form" class="panel login-card"><div class="demo-login-entry">${link(tr('免登录选择演示账号', 'Explore demo accounts without signing in'), 'demo', 'primary', 'arrow')}</div><h2>${tr('欢迎回来', 'Welcome back')}</h2><p class="muted small">${tr('登录你的竞云账户', 'Sign in to your CompSphere account')}</p>${tabs([['document', tr('证件登录', 'Document')], ['email', tr('邮箱登录', 'Email')]], documentMode ? 'document' : 'email')}${documentMode ? `<div class="form-grid">${selectField('login-document', tr('证件类型', 'Document type'), [['id', tr('身份证', 'ID card')], ['passport', tr('护照', 'Passport')]])}${selectField('login-country', tr('签发国', 'Issuing country'), [['CN', 'CN · 中国'], ['US', 'US · United States'], ['GB', 'GB · United Kingdom']])}</div>${field('login-number', tr('证件号码', 'Document number'), '', 'text', 'required autocomplete="username"')}` : field('login-email', tr('邮箱', 'Email'), '', 'email', 'required autocomplete="username"')}${field('login-password', tr('密码', 'Password'), '', 'password', 'required autocomplete="current-password"')}<div class="actions" style="justify-content:space-between"><span class="muted small">${tr('当前为演示登录，不验证真实凭据', 'Preview only; no real authentication')}</span>${btn(tr('忘记密码', 'Forgot password'), 'forgot-password', 'text small')}</div><button type="submit" class="button primary">${tr('登录', 'Sign in')}${icon('arrow')}</button><p class="muted small" style="margin-top:18px">${tr('没有账户？可自助邮箱注册或联系单位管理员。', 'Register with email, or ask your organization administrator.')}</p>${btn(tr('自助注册', 'Create account'), 'register-account', 'text small')}</form></div>`);
}
function verify() {
  return publicLayout(`${pageHead(tr('证书真伪验证', 'Verify a certificate'), tr('输入证书编号，查看最小有效性结果。', 'Enter a certificate number to check its validity.'))}<section class="panel" style="max-width:650px;margin:32px auto"><form id="verify-form" class="form-section"><h2>${tr('查询证书', 'Certificate lookup')}</h2>${field('verify-number', tr('证书编号', 'Certificate number'), '', 'text', 'required placeholder="CS-2026-00001"')}<button class="button primary" style="margin-top:18px" type="submit">${icon('shield')}${tr('验证证书', 'Verify')}</button></form><div id="verify-result"></div></section>`);
}

let dialogFocus;
function dialog(title, subtitle, body, footer = '', drawer = false) {
  const node = $('#drawer');
  if (!node.open) dialogFocus = document.activeElement;
  node.className = drawer ? 'drawer' : '';
  node.innerHTML = `<div class="dialog-head"><div><h2 id="dialog-title">${title}</h2><p>${subtitle}</p></div><button class="icon-button" data-action="close" aria-label="${tr('关闭', 'Close')}">${icon('close')}</button></div><div class="dialog-body">${body}</div>${footer ? `<div class="dialog-foot">${footer}</div>` : ''}`;
  if (!node.open) node.showModal();
}
function closeDialog() { $('#drawer').close(); }
function toast(text) { const node = $('#toast'); node.textContent = text; node.classList.add('visible'); clearTimeout(state.toastTimer); state.toastTimer = setTimeout(() => node.classList.remove('visible'), 3500); }
function registrationDetail(id) {
  const r = state.registrations.find((r) => r.id === id);
  state.selectedRegistration = id;
  const historyView = state.reviewTab === 'history';
  const body = `${tabs([['current', tr('本场报名', 'Current submission')], ['history', tr('历届队伍与队员', 'Team history')]], state.reviewTab, 'review-tab')}${historyView ? `${notice(tr('仅用于当前队伍审核的最小历史摘要，不包含历史证件、联系方式与附件。', 'Minimal history for reviewing this team only. Historical documents, contact data and attachments are excluded.'))}<h3>2025 · ${tr('华东区域邀请赛', 'East China Invitational')}</h3><p class="muted small">1024A · V5RC · ${tr('高中组 · 二等奖', 'High school · Second prize')}</p><div class="divider"></div>${table(tr('历史学生成员', 'Historical students'), [tr('学生', 'Student'), tr('身份', 'Role'), tr('当届年级', 'Grade then')], [['林知远', tr('队长', 'Captain'), tr('初中三年级', 'Grade 9')], ['苏予宁', tr('队员', 'Member'), tr('初中三年级', 'Grade 9')], ['程以安', tr('历史队员', 'Former member'), tr('高中一年级', 'Grade 10')]], false)}` : `${notice(tr('以下为提交时冻结的报名资料，后续队伍档案更新不影响本版。', 'These details were frozen on submission. Later team updates do not change them.'))}<div class="actions" style="justify-content:space-between"><h3>${r.team}</h3>${badge(r.status)}</div><dl class="detail-grid"><div><dt>${tr('队号与赛项', 'Team identity')}</dt><dd>${r.code} · ${r.event}</dd></div><div><dt>${tr('本场组别', 'Declared division')}</dt><dd>${r.group}</dd></div><div><dt>${tr('所属单位', 'Organization')}</dt><dd>${r.unit}</dd></div><div><dt>${tr('提交版本', 'Submission version')}</dt><dd>${tr('第', 'Version')} ${r.round} ${tr('版 · 单级审核', '· Single-stage review')}</dd></div></dl><div class="divider"></div><h3>${tr('本场学生队员', 'Students in this submission')}</h3>${table(tr('冻结成员', 'Frozen roster'), [tr('姓名', 'Name'), tr('身份', 'Role'), tr('年级', 'Grade'), ...(canReview() ? [tr('证件末四位', 'Document last 4')] : [])], ['林知远', '苏予宁', '唐星禾', '陈予安'].slice(0, r.count).map((name, i) => [name, i === 0 ? tr('队长', 'Captain') : tr('队员', 'Member'), tr('高中一年级', 'Grade 10'), ...(canReview() ? [['0027', '0416', '0024', 'A018'][i]] : [])]), false)}<div class="divider"></div><h3>${tr('提交材料', 'Submitted files')}</h3><div class="task-row">${icon('file')}<span>${tr('参赛授权材料.pdf', 'Participation consent.pdf')}</span><span class="muted small">1.2 MB</span></div><div class="task-row">${icon('file')}<span>${tr('作品说明.pdf', 'Project overview.pdf')}</span><span class="muted small">840 KB</span></div><div class="divider"></div><h3>${tr('审核记录', 'Review history')}</h3><div class="timeline-row"><span class="timeline-point"></span><div>${tr('提交报名', 'Registration submitted')}<p class="muted small">${r.date} · 陈老师 · v${r.round}</p></div></div>${canReview() ? `<div class="divider"></div><div class="field"><label for="review-comment">${tr('审核意见（退回或驳回时必填）', 'Review comment (required to return or reject)')}</label><textarea id="review-comment" rows="3" placeholder="${tr('请说明需要修改的内容与原因', 'Explain the required changes and reason')}"></textarea><p id="review-error" class="small" style="color:var(--color-danger)" role="alert"></p></div>` : ''}`}`;
  const actions = canReview() && !historyView ? r.status === 'pending' ? btn(tr('驳回', 'Reject'), `decision:rejected:${id}`, 'danger') + btn(tr('退回补正', 'Return'), `decision:returned:${id}`) + btn(tr('通过审核', 'Approve'), `decision:approved:${id}`, 'primary', 'check') : r.status === 'approved' ? btn(tr('驳回后更正', 'Reject for correction'), `decision:rejected:${id}`, 'danger') : '' : is('student', 'coach') && r.code === '1024A' && r.status === 'pending' ? btn(tr('取消并修改', 'Cancel & edit'), 'cancel-registration') : '';
  dialog(tr('报名详情', 'Registration detail'), `${id} · ${tr('提交版本', 'Version')} ${r.round}`, body, actions || btn(tr('关闭', 'Close'), 'close'), true);
}
function teamDetail(code) {
  const team = state.teams.find((t) => t.code === code);
  const students = state.students.filter((s) => s.team.startsWith(code));
  const responsible = team.coach === names[state.role];
  dialog(team.name, `${team.code} · ${team.event} · 海川实验学校`, `${panel(tr('赛季注册许可', 'Season license'), `<div class="mini-row"><strong>${state.season}</strong>${seasonLicenseBadge(code)}</div>${!teamSeasonLicense(code) && canManageTeams() ? btn(tr('申请赛季激活', 'Request season activation'), `apply-license:${code}`, 'primary') : `<p class="muted small">${tr('许可仅在本赛季有效，单场报名仍需审核。', 'Valid for this season only. Competition registration still requires review.')}</p>`}`)}${notice(tr('这是队伍正式档案。修改需由单位管理员发起并经审核生效；本场报名快照独立保留。', 'This is the approved team profile. Changes require an organization admin and approval; competition submissions stay unchanged.'))}<dl class="detail-grid"><div><dt>${tr('队长', 'Captain')}</dt><dd>${team.captain}</dd></div><div><dt>${tr('指导教练', 'Coach')}</dt><dd>${team.coach}</dd></div><div><dt>${tr('正式版本', 'Approved version')}</dt><dd>v3 · 2026-11-15</dd></div><div><dt>${tr('状态', 'Status')}</dt><dd>${badge('approved')}</dd></div></dl><div class="divider"></div>${canManageTeams() || responsible ? `<h3>${tr('当前学生成员', 'Current student members')}</h3>${table(tr('当前成员', 'Current members'), [tr('学生', 'Student'), tr('年级', 'Grade'), tr('归属', 'Membership')], students.map((s) => [s.name, s.group, badge('active')]), false)}<div class="divider"></div><h3>${tr('成员变更历史', 'Membership history')}</h3>${state.history.filter((h) => (h.team || '1024A') === code).map((h) => `<div class="mini-row"><div>${h.name} · ${tr(...h.action)}<p class="muted small">${h.by}</p></div><span class="small muted">${h.date}</span></div>`).join('')}` : `<p class="muted">${tr('本单位其他队伍仅展示概要，成员资料与报名需对应授权。', 'Other teams in your organization show summaries only. Member details and registrations require authorization.')}</p>`}`, canManageTeams() ? btn(tr('变更成员', 'Change members'), `edit-members:${code}`, '', 'team') + btn(tr('申请修改资料', 'Request profile change'), `edit-team:${code}`, 'primary', 'file') : btn(tr('关闭', 'Close'), 'close'), true);
}
function requestDetail(index) {
  const r = state.requests[index];
  const selfReview = r.applicant === names[state.role];
  dialog(tr(...r.title), `${r.name} · ${r.date}`, `${selfReview ? notice(r.title[0] === '创建队伍' ? tr('队伍创建仅由其他系统管理员审核，申请人不能自审。', 'Team creation requires a different platform administrator.') : tr('这是你提交的申请，不能自审。请由另一名单位管理员或平台管理员审核。', 'You submitted this request. Another authorized admin must review it.'), 'amber') : notice(tr('批准前请核对变更内容，已提交的赛事报名不会被回写。', 'Check the proposed changes before approval. Existing competition submissions remain unchanged.'))}<dl class="detail-grid"><div><dt>${tr('申请人', 'Applicant')}</dt><dd>${r.applicant}</dd></div><div><dt>${tr('申请状态', 'Status')}</dt><dd>${badge(r.status)}</dd></div></dl><div class="divider"></div>${r.title[0] === '创建队伍' ? `<dl class="detail-grid"><div><dt>${tr('注册赛季', 'Registration season')}</dt><dd>${esc(r.season)}</dd></div><div><dt>${tr('队号与赛项', 'Team identity')}</dt><dd>${esc(r.proposal?.code)} · ${esc(r.proposal?.event)}</dd></div></dl><p class="muted small">${tr('仅系统管理员可批准；同一事务创建队伍和本赛季许可。', 'Only platform admins may approve. Team creation and season licensing are atomic.')}</p>` : index === 1 ? `<h3>${tr('证件更正', 'Document correction')}</h3><div class="mini-row"><span class="muted">${tr('原证件', 'Current document')}</span><span>${tr('护照', 'Passport')} · US · A018</span></div><div class="mini-row"><span class="muted">${tr('拟更正证件', 'Proposed document')}</span><span>${tr('护照', 'Passport')} · US · B026</span></div><p class="muted small">${tr('批准后切换登录凭据、释放旧号码并使旧会话失效。完整号码不展示。', 'Approval changes sign-in credentials, releases the old number and invalidates sessions. Full numbers are never displayed.')}</p>` : `<h3>${tr('变更对比', 'Proposed changes')}</h3>${table(tr('申请差异', 'Request comparison'), [tr('字段', 'Field'), tr('当前版本', 'Current'), tr('申请版本', 'Proposed')], [[tr('队伍名称', 'Team name'), r.name, r.name], [tr('成员变化', 'Member changes'), '4 ' + tr('名学生', 'students'), tr('1 人退出，无新增成员', '1 leaving, no new members')]], false)}`}<div class="divider"></div><div class="field"><label for="request-comment">${tr('审核意见', 'Review comment')}</label><textarea id="request-comment" rows="3"></textarea></div>`, !selfReview && r.status === 'pending' && (r.title[0] !== '创建队伍' || is('platform')) ? btn(tr('驳回申请', 'Reject'), `request-decision:rejected:${index}`, 'danger') + btn(r.title[0] === '创建队伍' ? tr('批准创建及赛季注册', 'Approve team & season registration') : tr('批准变更', 'Approve'), `request-decision:approved:${index}`, 'primary') : btn(tr('关闭', 'Close'), 'close'), true);
}

function simpleForm(kind) {
  const configs = {
    'new-team': [tr('创建队伍申请', 'Create team request'), tr('申请由系统管理员审核，通过后建立队伍及当前赛季注册许可。', 'Platform approval creates the team and its current-season license.'), field('team-season', tr('注册赛季', 'Registration season'), state.season.replace('-', '–'), 'text', 'disabled') + field('team-code', tr('队号 *', 'Team number *'), '', 'text', 'required') + selectField('team-event', tr('稳定赛项 *', 'Event *'), [['V5RC', 'V5RC'], ['VIQRC', 'VIQRC']]) + field('team-name', tr('队伍名称 *', 'Team name *'), '', 'text', 'required')],
    'new-student': [tr('代建学生账户', 'Create student account'), tr('邮箱选填。初始密码首次登录后必须更改，不使用证件号码作密码。', 'Email is optional. A temporary password must be changed on first sign-in.'), field('student-name', tr('学生姓名 *', 'Student name *'), '', 'text', 'required autocomplete="name"') + selectField('student-doc', tr('证件类型 *', 'Document type *'), [['id', tr('身份证 · CN', 'ID card · CN')], ['passport', tr('护照', 'Passport')]]) + field('student-doc-number', tr('证件号码 *', 'Document number *'), '', 'text', 'required autocomplete="off"') + field('student-email', tr('邮箱（可选）', 'Email (optional)'), '', 'email', 'autocomplete="email"') + `<label class="check"><input type="checkbox" required>${tr('已取得学生 / 监护人代建授权', 'I have student / guardian authorization')}</label>`],
    'identity-change': [tr('申请更正证件', 'Request document correction'), tr('由所属单位或平台管理员审核，批准前旧证件仍有效。', 'Your organization or platform admin must approve the change. Your old document stays active until then.'), selectField('identity-type', tr('新证件类型', 'New document type'), [['id', tr('身份证', 'ID card')], ['passport', tr('护照', 'Passport')]]) + selectField('identity-country', tr('签发国', 'Issuing country'), [['CN', 'CN · 中国'], ['US', 'US · United States'], ['GB', 'GB · United Kingdom']]) + field('identity-number', tr('新证件号码 *', 'New document number *'), '', 'text', 'required autocomplete="off"')],
    'change-password': [tr('修改登录密码', 'Change password'), tr('修改后旧会话失效，需要重新登录。', 'Changing your password invalidates old sessions.'), field('password-old', tr('当前密码', 'Current password'), '', 'password', 'required autocomplete="current-password"') + field('password-new', tr('新密码', 'New password'), '', 'password', 'required minlength="8" autocomplete="new-password"')],
    'register-account': [tr('邮箱注册', 'Register with email'), tr('邮箱验证码自助注册；学生也可由单位管理员代建。', 'Sign up with an email code, or ask your organization admin to create a student account.'), field('signup-email', tr('邮箱', 'Email'), '', 'email', 'required autocomplete="email"') + field('signup-code', tr('邮箱验证码', 'Email verification code'), '', 'text', 'required autocomplete="one-time-code"') + btn(tr('获取演示验证码', 'Request demo code'), 'send-code', 'text small') + field('signup-password', tr('设置密码', 'Password'), '', 'password', 'required minlength="8" autocomplete="new-password"')],
    'forgot-password': [tr('找回密码', 'Recover password'), tr('有已验证邮箱可自助找回；也可联系当前主属单位核验重置。无归属单位且无法自助找回时，请通过平台配置的支持邮箱联系系统管理员。', 'Use your verified email or contact your current primary organization. Without either recovery option, contact platform support.'), field('reset-email', tr('已验证邮箱', 'Verified email'), '', 'email', 'required autocomplete="email"')],
    'new-competition': [tr('创建赛事申请', 'Create competition'), tr('赛事仅由平台管理员创建，再指定赛事管理员。', 'Platform admins create competitions and assign competition admins.'), field('event-season', tr('所属赛季', 'Season'), state.season.replace('-', '–'), 'text', 'disabled') + field('event-name', tr('赛事名称', 'Competition name'), '', 'text', 'required') + field('event-start', tr('比赛开始时间', 'Start date'), '', 'date', 'required')],
    'new-organization': [tr('单位入驻申请', 'Organization application'), tr('审核通过后才建立正式单位。', 'The organization becomes available after approval.'), field('org-name', tr('单位名称', 'Organization name'), '', 'text', 'required') + selectField('org-type', tr('单位类型', 'Type'), [['school', tr('学校', 'School')], ['enterprise', tr('企业', 'Enterprise')]]) + field('org-contact', tr('联系人', 'Contact'), '', 'text', 'required autocomplete="name"')],
    'replace-admin': [tr('更换单位管理员', 'Replace organization admin'), tr('撤销旧授权并授予新管理员，保留操作审计，不建立离职档案。', 'Revoke the old grant and assign a new admin. Audit the change without employment records.'), field('admin-current', tr('当前管理员', 'Current admin'), '陈老师', 'text', 'disabled') + field('admin-next', tr('新管理员账号', 'New admin account'), '', 'text', 'required')],
    'grant-role': [tr('分配管理角色', 'Grant a management role'), tr('指定人员、角色和管理范围。', 'Choose the person, role and scope.'), field('grant-user', tr('人员账户', 'Account'), '', 'text', 'required') + selectField('grant-role', tr('角色', 'Role'), [['org', tr('单位管理员', 'Organization admin')], ['event', tr('赛事管理员', 'Competition admin')], ['reviewer', tr('赛事审核员', 'Reviewer')]]) + field('grant-scope', tr('管理范围', 'Scope'), '', 'text', 'required')],
  };
  const config = configs[kind];
  dialog(config[0], config[1], `<form id="simple-form" data-kind="${kind}" class="stack" style="gap:18px">${config[2]}<div class="field"><label for="form-reason">${tr('说明 / 理由', 'Notes / reason')}</label><textarea id="form-reason" rows="2"></textarea></div><p class="muted small">${tr('仅设计演示：不会发送、保存或验证真实个人信息，请勿输入真实资料。', 'Design preview only: do not enter real personal information. Nothing is sent or stored.')}</p><button type="submit" class="button primary">${tr('确认', 'Confirm')}</button></form>`);
}
function memberForm(code) {
  state.memberTeam = code;
  const team = state.teams.find((t) => t.code === code);
  dialog(tr('申请变更队伍成员', 'Request member change'), `${code} · ${team.event} · ${team.name}`, `${notice(tr('普通入队须审核；自主退队不解除同赛季同赛项绑定，回原队可普通审核，加入其他队伍须平台特批。', 'Ordinary joins require approval. Leaving does not release season eligibility; another team requires platform approval.'), 'amber')}<form id="member-form" class="stack" style="gap:18px">${selectField('member-student', tr('学生', 'Student'), state.students.map((s, i) => [String(i), `${s.name} · ${s.team || tr('未入队', 'No team')}`]))}${selectField('member-action', tr('变更动作', 'Action'), [['join', tr('加入该队', 'Join this team')], ['leave', tr('退出该队', 'Leave this team')]])}<p id="member-error" role="alert" style="color:var(--color-danger)"></p><button class="button primary" type="submit">${tr('提交变更申请', 'Submit change request')}</button></form>`);
}
function importDialog(kind) {
  dialog(tr('导入预览', 'Import preview'), tr('先检查匹配结果，再确认写入。', 'Review the matched records before confirming.'), `<div class="upload-zone">${icon('upload')}<p>${tr('选择演示导入文件', 'Choose a sample import file')}</p><label class="small muted">CSV / XLSX<input type="file" id="import-file" accept=".csv,.xlsx"></label></div><div class="divider"></div>${notice(tr('演示预览：5 条匹配，1 条错误。错误行不会自动导入。', 'Sample preview: 5 matched, 1 error. Invalid rows will not be imported.'), 'amber')}${table(tr('匹配预览', 'Match preview'), [tr('队号', 'Team number'), tr('赛项', 'Event'), tr('结果', 'Result')], [['1024A', 'V5RC', badge('approved')], ['1024B', 'VIQRC', badge('approved')], ['9999X', 'V5RC', `<span class="tag red">${tr('队伍不存在', 'Unknown team')}</span>`]], false)}`, btn(tr('取消', 'Cancel'), 'close') + btn(tr('确认演示导入', 'Confirm sample import'), 'confirm-import', 'primary'));
}

function pageAllowed(page) {
  const shared = ['demo', 'competition', 'competitions', 'discover', 'public-event', 'portal', 'login', 'verify'];
  if (shared.includes(page)) return true;
  if (['profile','settings','notices'].includes(page)) return state.role !== 'visitor';
  if (page === 'registration') return can('registration:write');
  return navigation().some(([id]) => id === page);
}
function syncUrl() {
  const url = new URL(location.href);
  url.searchParams.delete('variant');
  url.searchParams.set('competition', state.competitionIndex || 0);
  for (const key of ['role', 'lang', 'theme', 'season']) url.searchParams.set(key, state[key]);
  url.hash = state.page;
  history.replaceState(null, '', url);
}
function applyTheme() {
  document.documentElement.dataset.theme = state.theme === 'system' ? matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light' : state.theme;
}
function render() {
  if (!roles[state.role]) state.role = 'visitor';
  if (state.page === 'dashboard' && is('reviewer')) state.page = 'reviews';
  if (state.page === 'dashboard' && !can('admin:access')) state.page = 'portal';
  applyTheme(); syncUrl(); document.documentElement.lang = state.lang === 'zh' ? 'zh-CN' : 'en';
  document.title = `${label(state.page)} · ${tr('竞云界面预览', 'CompSphere preview')}`;
  const pages = { demo: renderDemoExplorer, discover: competitions, 'public-event': competitionDetail, membership, transfers, edition, history: historicalRecords, dashboard, competitions, competition: competitionDetail, registrations, registration: registrationForm, reviews, teams, students, requests, awards, certificates, access, imports, organizations, roles: rolesPage, profile, settings, notices, audit, portal, login, verify };
  if (!pageAllowed(state.page)) {
    const body = pageHead(tr('暂无访问权限', 'Access unavailable'), tr('如需访问，请联系管理员分配相应权限。', 'Contact your administrator if you need access.')) + empty(tr('页面不在当前权限范围内', 'Outside your access scope'), '', link(tr('返回赛事门户', 'Back to competitions'), 'portal'));
    $('#app').innerHTML = can('admin:access') ? shell(body) : renderPublicLayout(body, true);
    syncAssistant();
    return;
  }
  const content = (pages[state.page] || dashboard)();
  $('#app').innerHTML = ['portal', 'login', 'verify', 'demo'].includes(state.page) ? content : can('admin:access') && !['discover','public-event'].includes(state.page) ? shell(content) : renderPublicLayout(content, true);
  revealEditionSection();
  syncAssistant();
}
function downloadSample() {
  const text = '\uFEFFteam_number,event,team_name,status\n' + state.registrations.map((r) => [r.code, r.event, r.team, r.status].join(',')).join('\n');
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'compsphere-demo.csv'; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
document.addEventListener('click', (event) => {
  if (event.target.closest('.skip')) { event.preventDefault(); $('#page-title')?.focus(); return; }
  const button = event.target.closest('[data-action]');
  if (!button) return;
  const [action, arg, arg2] = button.dataset.action.split(':');
  if (action === 'assistant') return openAssistant();
  if (action === 'assistant-minimize') return minimizeAssistant();
  if (action === 'assistant-clear') return clearAssistantConversation();
  if (action === 'assistant-example') { $('#assistant-question').value = arg === 'register' ? tr('我想报名比赛', 'Help me register') : arg === 'review' ? tr('帮我审核报名', 'Help me review registrations') : tr('这场赛事什么时候截止报名？', 'When does registration close?'); return sendAssistantMessage(); }
  if (action === 'open-competition') { state.competitionIndex = Number(arg); location.hash = can('admin:access') ? 'competition' : 'public-event'; render(); return; }
  if (handleOperationsAction(action, arg)) return;
  if (handleMembershipAction(button.dataset.action)) return;
  if (action === 'close') return closeDialog();
  if (action === 'menu') { const open = $('.shell').classList.toggle('menu-open'); button.setAttribute('aria-expanded', String(open)); return; }
  if (action === 'cycle-theme') { state.theme = ['light','dark','system'][(['light','dark','system'].indexOf(state.theme)+1)%3]; render(); return; }
  if (action === 'language') { state.lang = state.lang === 'zh' ? 'en' : 'zh'; render(); return; }
  if (action === 'tab') { state.tab = arg; render(); return; }
  if (action === 'clear-filters') { state.search = ''; state.status = 'all'; render(); return; }
  if (action === 'registration-detail') { state.reviewTab = 'current'; return registrationDetail(arg); }
  if (action === 'review-tab') { if (arg === 'history' && !canReview()) return toast(tr('历史审核视图仅向本场审核人员开放。', 'Historical review context is only available to reviewers.')); state.reviewTab = arg; return registrationDetail(state.selectedRegistration); }
  if (action === 'cancel-registration') { state.registrations[0].status = 'draft'; closeDialog(); location.hash = 'registration'; render(); return toast(tr('已取消本轮审核并保留原提交，现在可以编辑。', 'Review cancelled. The original submission is retained; you can now edit.')); }
  if (action === 'decision') {
    const reg = state.registrations.find(r => r.id === arg2);
    if (arg === 'approved' && teamSeasonLicense(reg.code, '2026-2027')?.status !== 'approved') return toast(tr('该队尚无本场所属赛季的有效许可，不能通过报名。', 'The team needs a valid license for this competition’s season.'));
    const comment = $('#review-comment').value.trim();
    if (arg !== 'approved' && !comment) { $('#review-error').textContent = tr('请填写审核意见。', 'Please provide a review comment.'); $('#review-comment').focus(); return; }
    dialog(tr('确认审核决定', 'Confirm review decision'), arg2, `${notice(tr('操作针对当前提交版本。驳回后可以修改重提，但不会延长报名截止时间。', 'This action applies to the current version. Rejected registrations may be resubmitted within the deadline.'))}<p>${tr('处理结果', 'Decision')}：${badge(arg)}</p>${comment ? `<p class="muted" style="margin-top:12px">${esc(comment)}</p>` : ''}`, btn(tr('返回检查', 'Back'), `registration-detail:${arg2}`) + btn(tr('确认', 'Confirm'), `apply-decision:${arg}:${arg2}`, arg === 'approved' ? 'primary' : 'danger')); return;
  }
  if (action === 'apply-decision') {
    const reg = state.registrations.find(r => r.id === arg2);
    if (arg === 'approved' && teamSeasonLicense(reg.code, '2026-2027')?.status !== 'approved') return toast(tr('赛季许可已失效，请重新核对。', 'The season license is no longer valid.'));  state.registrations.find((r) => r.id === arg2).status = arg; closeDialog(); render(); return toast(tr('审核结果已在演示中更新。', 'The sample review decision has been updated.')); }
  if (action === 'manage-seasons') {
    if (!is('platform')) return;
    dialog(tr('管理当前赛季', 'Manage current season'), tr('全平台生效，队伍需要分别申请新赛季许可。', 'Applies platform-wide. Teams need a separate license for each season.'), `<form id="season-management" class="stack">${selectField('current-season', tr('当前赛季', 'Current season'), seasons.filter(s => s.status === 'active').map(s => [s.id, s.id.replace('-', '–')]))}<p class="muted small">${tr('切换不迁移许可或归档旧赛季，旧报名继续留存。', 'Switching preserves old registrations and does not transfer licenses or archive the previous season.')}</p><button class="button primary" type="submit">${tr('确认切换当前赛季', 'Confirm current season')}</button></form>`);
    $('#current-season').value = state.season; return;
  }
  if (action === 'apply-license') {
    if (!canManageTeams()) return;
    const existing = teamSeasonLicense(arg);
    if (existing) return toast(tr('本赛季已有许可或待审申请。', 'A license or pending request already exists.'));
    dialog(tr('申请赛季激活', 'Request season activation'), `${arg} · ${state.season}`, `<p>${tr('沿用队伍正式档案，提交系统管理员审核。通过前不能报名本赛季赛事。', 'Use the approved team profile for platform review. Registration remains unavailable until approval.')}</p>`, btn(tr('取消', 'Cancel'), 'close') + btn(tr('提交激活申请', 'Submit activation'), `submit-license:${arg}`, 'primary')); return;
  }
  if (action === 'submit-license') {
    if (!canManageTeams() || teamSeasonLicense(arg)) return;
    state.seasonLicenses.push({team:arg, season:state.season, status:'submitted', applicant:names[state.role], comment:''}); closeDialog(); render(); toast(tr('已提交系统管理员审核。', 'Submitted for platform review.')); return;
  }
  if (action === 'cancel-license') { const r = state.seasonLicenses[Number(arg)]; if (!canManageTeams() || r.applicant !== names[state.role] || r.status !== 'submitted') return; r.status = 'withdrawn'; r.comment = tr('申请人取消', 'Cancelled by applicant'); render(); return; }
  if (action === 'review-license') {
    if (!is('platform')) return;
    const r = state.seasonLicenses[Number(arg)];
    dialog(tr('审核赛季激活', 'Review season activation'), `${r.team} · ${r.season}`, `<p>${tr('申请人', 'Applicant')}：${esc(r.applicant)}</p><div class="field"><label for="license-comment">${tr('审核意见 *', 'Review notes *')}</label><textarea id="license-comment" required rows="3"></textarea></div>`, btn(tr('驳回', 'Reject'), `decide-license:rejected:${arg}`, 'danger') + btn(tr('通过赛季注册', 'Approve season license'), `decide-license:approved:${arg}`, 'primary')); return;
  }
  if (action === 'decide-license') {
    if (!is('platform')) return;
    const r = state.seasonLicenses[Number(arg2)], comment = $('#license-comment').value.trim();
    if (r.status !== 'submitted' || r.applicant === names[state.role]) return toast(tr('申请已处理或不能自审。', 'Already reviewed, or self-review is not allowed.'));
    if (!comment) return $('#license-comment').reportValidity();
    r.status = arg; r.comment = comment; closeDialog(); render(); return;
  }
  if (action === 'team-detail') return teamDetail(arg);
  if (action === 'edit-members') return memberForm(arg);
  if (action === 'edit-team') { simpleForm('new-team'); const team = state.teams.find((t) => t.code === arg); $('#simple-form').dataset.kind = 'edit-team'; $('#dialog-title').textContent = tr('队伍资料变更申请', 'Team profile change'); $('#dialog-title').nextElementSibling.textContent = tr('资料变更由另一名有权单位管理员或平台审核，赛季许可不自动改变。', 'A different authorized organization admin or platform admin reviews profile changes. Season licenses remain separate.'); $('#team-season').closest('.field').remove(); $('#team-code').value = arg; $('#team-code').disabled = true; $('#team-event').value = team.event; $('#team-event').disabled = true; $('#team-name').value = team.name; return; }
  if (action === 'request-detail') return requestDetail(Number(arg));
  if (action === 'request-decision') {
    const candidate = state.requests[Number(arg2)];
    if (candidate.title[0] === '创建队伍' && !is('platform')) return toast(tr('队伍创建仅由系统管理员审核。', 'Only platform admins may approve team creation.'));
    if (candidate.title[0] === '创建队伍' && !$('#request-comment').value.trim()) return toast(tr('请填写创建审核意见。', 'Provide team creation review notes.'));
    if (candidate.title[0] === '创建队伍' && arg === 'approved' && candidate.applicant !== names[state.role] && candidate.proposal && candidate.status === 'pending') { const t = candidate.proposal; state.teams.push({ ...t, captain: '—', coach: '—', count: 0 }); state.seasonLicenses.push({ team: t.code, season: candidate.season, status: 'approved', applicant: candidate.applicant, comment: '创建审核通过' }); }
    if (arg === 'rejected' && !$('#request-comment').value.trim()) return toast(tr('驳回申请时请填写理由。', 'A reason is required to reject a request.'));
    const request = state.requests[Number(arg2)]; if (request.applicant === names[state.role]) return toast(tr('申请人不能自审。', 'Applicants cannot review their own requests.')); if (request.memberChange && arg === 'approved') { const { index, operation, team } = request.memberChange; const student = state.students[index]; if (operation === 'join' && bindingConflict(student, team)) return toast(tr('同赛季同赛项已绑定其他队伍，单位审核不能放行，请向平台申请换队。', 'This season binds the student to another team. Platform approval is required.')); if ((operation === 'join' && student.team) || (operation === 'leave' && !student.team.startsWith(team.code))) return toast(tr('成员归属已变化，请重新核对申请。', 'Membership changed; check the request again.')); } request.status = arg; request.comment = $('#request-comment').value.trim();
    if (request.memberChange && arg === 'approved') {
      const { index, team, operation } = request.memberChange;
      const student = state.students[index]; if (operation === 'leave') student.lastTeam = student.team.split(' · ')[0]; student.team = operation === 'join' ? `${team.code} · ${team.event}` : '';
      state.membershipAudit.push({ by: names[state.role], text: operation === 'join' ? [`审核加入 ${team.code}`, `Approved join ${team.code}`] : [`审核退出 ${team.code}`, `Approved leave ${team.code}`] }); state.history.push({ team: team.code, name: student.name, action: operation === 'join' ? [`加入 ${team.name}`, `Joined ${team.name}`] : [`退出 ${team.name}`, `Left ${team.name}`], date: '2026-11-17 14:30', by: names[state.role] });
    }
    closeDialog(); render(); return toast(tr('演示申请状态已更新。', 'The sample request status has been updated.'));
  }
  if (action === 'student-detail') { const s = state.students[Number(arg)]; dialog(s.name, s.code, `<dl class="detail-grid"><div><dt>${tr('当前队伍', 'Current team')}</dt><dd>${s.team || tr('未入队', 'No team')}</dd></div><div><dt>${tr('证件末四位', 'Document last 4')}</dt><dd>${s.last4}</dd></div><div><dt>${tr('年级', 'Grade')}</dt><dd>${s.group}</dd></div><div><dt>${tr('邮箱', 'Email')}</dt><dd>${tr('未绑定（单位代建）', 'Not bound (organization-created)')}</dd></div></dl><div class="divider"></div><p class="muted small">${tr('完整证件号码不展示。换队请在队伍成员变更中先退后入。', 'Full document numbers are never shown. Use the team change process to leave before joining another.')}</p>`, btn(tr('关闭', 'Close'), 'close') + btn(tr('核验后重置密码', 'Verified password reset'), 'reset-student')); return; }
  if (action === 'reset-student') { dialog(tr('核验后重置密码', 'Verified password reset'), tr('仅当前主属单位可核验重置普通学生账号，不受账户创建来源或邮箱影响。', 'Only the current primary organization can reset ordinary student accounts, regardless of account creator or email.'), `<div class="field"><label for="reset-reason">${tr('核验说明与理由', 'Verification and reason')}</label><textarea id="reset-reason" rows="3"></textarea></div>`, btn(tr('取消', 'Cancel'), 'close') + btn(tr('确认演示重置', 'Confirm sample reset'), 'finish-reset', 'danger')); return; }
  if (action === 'finish-reset') { if (!$('#reset-reason').value.trim()) return toast(tr('请先填写核验说明。', 'Provide verification notes first.')); closeDialog(); return toast(tr('演示重置完成。实际系统将一次性交付临时密码，并强制首次改密。', 'Sample reset complete. The real system delivers a one-time temporary password and forces a change.')); }
  if (['new-team', 'new-student', 'identity-change', 'change-password', 'forgot-password', 'register-account', 'new-competition', 'new-organization', 'replace-admin', 'grant-role'].includes(action)) return simpleForm(action);
  if (action.startsWith('import-') || action === 'import-result') return importDialog(action);
  if (action === 'confirm-import') { closeDialog(); return toast(tr('演示任务已创建，错误行保留待处理。', 'Sample job created. Invalid rows remain for resolution.')); }
  if (action === 'download') return downloadSample();
  if (action === 'send-code') return toast(tr('演示验证码：123456。未发送邮件。', 'Demo code: 123456. No email was sent.'));
  if (action === 'remove-photo') { if (state.photo) URL.revokeObjectURL(state.photo); state.photo = ''; return render(); }
  if (action === 'confirm-photo') { state.photo = state.photoCandidate; closeDialog(); render(); return toast(tr('已应用本地预览照片，刷新后清除。', 'Local photo preview applied. Refresh clears it.')); }
  if (action === 'competition-registrations') { location.hash = 'registrations'; return; }
  if (action === 'certificate-detail') { dialog(tr('学生荣誉证书', 'Student certificate'), `CS-2026-0000${Number(arg) + 1}`, `<div class="certificate"><div class="seal">${icon('trophy')}</div><h2>${tr('荣誉证书', 'CERTIFICATE')}</h2><strong>${is('student') ? '林知远' : Number(arg) ? '苏予宁' : '林知远'}</strong><p>${tr('2026 机器人挑战赛 · 一等奖', '2026 Robotics Challenge · First prize')}</p><p class="muted small">${tr('海川实验学校 · 逐光机器人队', 'Haichuan School · Chasing Light')}</p><p class="mono small">CS-2026-0000${Number(arg) + 1}</p></div>`, link(tr('验证证书', 'Verify certificate'), 'verify', '', 'shield')); return; }
  if (action === 'rules') { dialog(tr('赛事章程', 'Competition rules'), tr('设计预览 · 文件阅读器', 'Design preview · Document viewer'), `<h3>${eventNames[0]}</h3><div class="divider"></div><p>${tr('参赛对象：小学、初中及高中学生。队伍须完成资料审核，按开放赛项与组别报名，提交后本场资料冻结。', 'Open to elementary, middle and high school students. Use an approved team and available event / division. Submitted details are frozen.')}</p>`, btn(tr('关闭', 'Close'), 'close')); return; }
  if (action === 'submit-roster' || action === 'generate-certificates') { dialog(tr('确认名单操作', 'Confirm roster action'), tr('仅面向审核通过版本中的学生，不向教练或单位发奖。', 'Awards and certificates are for students in approved submissions only.'), notice(tr('名单确认后将锁定；学生证书逐人生成，任务可后台继续。', 'Confirmation locks the roster. Individual student certificate jobs run in the background.')), btn(tr('取消', 'Cancel'), 'close') + btn(tr('确认演示操作', 'Confirm sample action'), 'finish-job', 'primary')); return; }
  if (action === 'finish-job') { closeDialog(); return toast(tr('演示任务已进入处理中，可在证书中心查看。', 'Sample job queued. Check the certificate center.')); }
  if (action === 'organization-detail' || action === 'organization-request' || action === 'view-grant') { dialog(tr('单位信息', 'Organization information'), '海川实验学校', `<dl class="detail-grid"><div><dt>${tr('管理员', 'Administrator')}</dt><dd>陈老师</dd></div><div><dt>${tr('单位类型', 'Type')}</dt><dd>${tr('学校', 'School')}</dd></div><div><dt>${tr('队伍', 'Teams')}</dt><dd>12</dd></div><div><dt>${tr('学生', 'Students')}</dt><dd>86</dd></div></dl>`, btn(tr('关闭', 'Close'), 'close') + btn(tr('更换管理员', 'Replace administrator'), 'replace-admin', 'primary')); }
});
document.addEventListener('input', (event) => {
  if (event.target.name && event.target.type !== 'file') state.form[event.target.name] = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
  if (event.target.id === 'search') {
    const start = event.target.selectionStart; state.search = event.target.value; render(); $('#search').focus(); $('#search').setSelectionRange(start, start);
  }
});
document.addEventListener('change', (event) => {
  const { id, value } = event.target;
  if (id === 'theme-select' || id === 'settings-theme') { state.theme = value; render(); }
  if (id === 'settings-lang') { state.lang = value; render(); }
  if (id === 'filter-status') { state.status = value; render(); }
  if (id === 'access-mode') toast(tr('已切换预览准入模式；实际系统需确认并留审计。', 'Preview entry mode changed. The real system requires confirmation and auditing.'));
  if (id === 'photo-upload') {
    const file = event.target.files[0]; if (!file) return;
    if (!['image/jpeg', 'image/png'].includes(file.type) || file.size > 5 * 1024 * 1024) return toast(tr('请选择不超过 5MB 的 JPEG 或 PNG 图片。', 'Choose a JPEG or PNG image no larger than 5MB.'));
    state.photoCandidate = URL.createObjectURL(file);
    dialog(tr('确认照片', 'Confirm photo'), tr('本地预览，照片不会上传。保持原始比例。', 'Local preview only. The photo is not uploaded and keeps its aspect ratio.'), `<div class="photo-box" style="width:180px;margin:auto"><img src="${state.photoCandidate}" alt="${tr('待确认照片', 'Photo to confirm')}"></div><p class="muted small" style="margin-top:18px">${tr('正式上传流程将在实现时提供裁切，并移除 EXIF 信息。', 'The production upload flow will offer cropping and strip EXIF metadata.')}</p>`, btn(tr('取消', 'Cancel'), 'close') + btn(tr('使用此照片', 'Use photo'), 'confirm-photo', 'primary'));
  }
});
document.addEventListener('submit', (event) => {
  event.preventDefault(); const form = event.target;
  if (form.id === 'assistant-form') return sendAssistantMessage();
  if (handleOperationsForm(form)) return;
  if (handleMembershipForm(form)) return;
  if (form.id === 'registration-form') {
    if (state.season !== '2026-2027' || teamSeasonLicense('1024A', '2026-2027')?.status !== 'approved') return toast(tr('本场不属于当前赛季，或队伍尚未取得对应赛季许可。', 'This is not the current season, or the team has no approved season license.'));
    if (is('student')) { const student = state.students.find((s) => s.code === 'S202601'); if (!student.team.startsWith(state.registrations[0].code)) { toast(tr('你已不属于该队，不能重新提交原队报名。请由原队更正阵容，目标队另行报名。', 'You no longer belong to this team. Correct the source roster and register separately with the target team.')); return; } }
    const level = $('#reg-level').value, group = $('#reg-group').value;
    const offering = editionConfig().offerings.find(o => o.event === 'V5RC' && o.group === group && o.enabled);
    if (!offering) return toast(tr('所选组合已停用，请选择开放组别或联系赛事方。', 'This offering is disabled. Choose an open division or contact the organizer.'));
    if (state.registrations[0].count < offering.min || state.registrations[0].count > offering.max) return toast(tr(`学生人数须为 ${offering.min}–${offering.max} 人，请联系单位管理员核对阵容。`, `This offering requires ${offering.min}–${offering.max} students. Ask your organization administrator to check the roster.`));
    if (level !== group) { $('#reg-group').setCustomValidity(tr('本场学段须与所选组别一致。', 'School level must match the selected division.')); $('#reg-group').reportValidity(); $('#reg-group').setCustomValidity(''); return; }
    state.registrations[0].status = 'pending'; state.registrations[0].round += 1; render(); return toast(tr('报名已提交，新版本资料与成员已冻结。', 'Registration submitted. The new version is frozen.'));
  }
  if (form.id === 'profile-form') return toast(tr('资料已保存在本次演示会话中，未上传服务器。', 'Profile kept in this preview session only. Nothing was uploaded.'));
  if (form.id === 'login-form') { if (state.role === 'visitor') state.role = 'student'; location.hash = can('admin:access') ? 'dashboard' : 'portal'; return toast(tr('已进入演示账户，不创建真实登录会话。', 'Signed in to the sample account. No real session was created.')); }
  if (form.id === 'verify-form') {
    const valid = /^CS-2026-0000[12]$/.test($('#verify-number').value.trim());
    $('#verify-result').innerHTML = `<div class="form-section">${notice(valid ? tr('证书有效 · 演示验证结果', 'Valid certificate · Sample result') : tr('未找到该证书 · 可试用 CS-2026-00001', 'Certificate not found · Try CS-2026-00001'), valid ? 'green' : 'amber')}${valid ? `<dl class="detail-grid"><div><dt>${tr('持有人', 'Recipient')}</dt><dd>林**</dd></div><div><dt>${tr('奖项', 'Award')}</dt><dd>${tr('一等奖', 'First prize')}</dd></div><div><dt>${tr('赛项', 'Event')}</dt><dd>V5RC</dd></div><div><dt>${tr('签发日期', 'Issued')}</dt><dd>2026-10-20</dd></div></dl>` : ''}</div>`; return;
  }
  if (form.id === 'member-form') {
    const index = Number($('#member-student').value), student = state.students[index], operation = $('#member-action').value, team = state.teams.find((t) => t.code === state.memberTeam);
    if (operation === 'join' && student.team || operation === 'leave' && !student.team.startsWith(team.code)) { $('#member-error').textContent = operation === 'join' ? tr('该学生已有当前队伍，请先退队；退队不解除本届参赛绑定。', 'This student already has a current team. Leave first; edition restrictions still apply.') : tr('该学生不在当前队伍。', 'This student is not in this team.'); return; }
    if (operation === 'join' && bindingConflict(student, team)) { $('#member-error').textContent = tr('同赛季同赛项已绑定其他队伍。请向平台管理员申请换队；普通审核不能绕过。', 'The student is bound to another team in this edition. Apply to the platform administrator.'); return; }
    state.requests.push({ name: team.name, title: ['队伍成员变更', 'Team member change'], applicant: names[state.role], status: 'pending', date: '2026-11-17 14:20', memberChange: { index, operation, team } });
    closeDialog(); toast(tr('变更申请已提交。当前归属未改变，等待其他有权管理员审核。', 'Change request submitted. Membership stays unchanged until another authorized admin approves it.')); location.hash = 'requests'; render(); return;
  }
  if (form.id === 'season-management') { if (!is('platform')) return; state.season = $('#current-season').value; closeDialog(); render(); return toast(tr('演示当前赛季已切换；队伍许可不会自动继承。', 'Preview season changed. Team licenses are not inherited.')); }
  if (form.id === 'simple-form') {
    if (form.dataset.kind === 'new-team' && state.teams.some(t => t.code === $('#team-code').value && t.event === $('#team-event').value)) return toast(tr('队伍已存在，新赛季请申请激活。', 'This team exists. Apply for season activation.'));
    if (['new-team', 'edit-team'].includes(form.dataset.kind)) state.requests.push({ name: $('#team-name').value, season: state.season, proposal: { code: $('#team-code').value, event: $('#team-event').value, name: $('#team-name').value }, title: form.dataset.kind === 'new-team' ? ['创建队伍', 'Create team'] : ['队伍资料变更', 'Team profile change'], applicant: names[state.role], status: 'pending', date: '2026-11-17 14:20' });
    closeDialog(); render(); return toast(tr('演示操作已受理。不会创建真实账户、发送验证码或修改服务器数据。', 'Sample action accepted. No real accounts, emails or server data were created or changed.'));
  }
});
$('#drawer').addEventListener('close', () => { if (dialogFocus?.isConnected) dialogFocus.focus(); });
window.addEventListener('hashchange', () => { const isChatFocused = document.activeElement?.id === 'assistant-question'; closeDialog(); state.page = location.hash.slice(1) || 'dashboard'; state.search = ''; state.status = 'all'; state.tab = 'all'; render(); window.scrollTo(0, 0); if (!isChatFocused) $('#page-title')?.focus({ preventScroll: true }); });
window.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') { $('.shell')?.classList.remove('menu-open'); $('.mobile-menu')?.setAttribute('aria-expanded','false'); }
});
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if (state.theme === 'system') applyTheme(); });
render();
