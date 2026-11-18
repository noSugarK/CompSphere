/* In-memory design preview. These controls do not implement server authorization. */
function sampleOfferings() {
  return [
    { event: 'V5RC', group: 'HS', min: 3, max: 5, materials: 'project', enabled: true },
    { event: 'V5RC', group: 'MS', min: 3, max: 5, materials: 'project', enabled: true },
    { event: 'VIQRC', group: 'ES', min: 2, max: 4, materials: 'consent', enabled: true },
  ];
}
function editionConfig() {
  return (state.editionConfig ||= {
    name: eventNames[0],
    venue: '上海青少年科技活动中心',
    enrollStart: '2026-11-01T09:00',
    enrollEnd: '2026-11-23T18:00',
    start: '2026-11-28T09:00',
    end: '2026-11-29T18:00',
    review: 'single',
    publication: 'none',
    published: false,
    offerings: sampleOfferings(),
  });
}
const divisionName = (group) =>
  ({
    HS: tr('高中组', 'High school'),
    MS: tr('初中组', 'Middle school'),
    ES: tr('小学组', 'Elementary school'),
  })[group];
const materialName = (value) =>
  value === 'project'
    ? tr('参赛授权、作品说明', 'Consent, project overview')
    : tr('参赛授权', 'Participation consent');
function editionChecks(config = editionConfig()) {
  return [
    [
      tr('赛事名称与地点', 'Competition title & venue'),
      Boolean(config.name.trim() && config.venue.trim()),
      'basics',
    ],
    [
      tr('报名与比赛时间', 'Registration & competition dates'),
      Boolean(
        config.enrollStart &&
        config.enrollEnd &&
        config.start &&
        config.end &&
        config.enrollStart < config.enrollEnd &&
        config.enrollEnd <= config.start &&
        config.start < config.end,
      ),
      'basics',
    ],
    [
      tr('至少一个开放组合', 'At least one open offering'),
      config.offerings.some((o) => o.enabled),
      'offerings',
    ],
    [
      tr('组合人数与唯一性', 'Offering sizes & uniqueness'),
      config.offerings.every(
        (o) => Number.isInteger(o.min) && o.min > 0 && Number.isInteger(o.max) && o.max >= o.min,
      ) &&
        new Set(config.offerings.map((o) => `${o.event}:${o.group}`)).size ===
          config.offerings.length,
      'offerings',
    ],
  ];
}
function renderPublicCompetitionDetail() {
  const index = state.competitionIndex || 0;
  const config =
    index === 0
      ? editionConfig()
      : {
          name: eventNames[index],
          venue: index === 1 ? tr('杭州', 'Hangzhou') : tr('上海', 'Shanghai'),
          enrollStart: '2026-11-01T09:00',
          enrollEnd: index === 2 ? '2026-12-05T18:00' : '2026-11-23T18:00',
          start: index === 2 ? '2026-12-12T09:00' : '2026-11-28T09:00',
          end: index === 2 ? '2026-12-13T18:00' : '2026-11-29T18:00',
          offerings: sampleOfferings(),
        };
  const offerings = config.offerings.filter((o) => o.enabled);
  const date = (value) => value.replace('T', ' ');
  return `<header class="public-event-heading"><a href="#discover">${icon('left')}${tr('全部赛事', 'All competitions')}</a><span class="technical-label">2026–2027 / ROBOTICS</span><h1 id="page-title" tabindex="-1">${esc(config.name)}</h1><div class="spotlight-meta"><span>${icon('pin')}${esc(config.venue)}</span><span>${icon('calendar')}${config.start.slice(0, 10)} — ${config.end.slice(0, 10)}</span></div></header><div class="cols"><div class="stack">${panel(
    tr('报名开放组合', 'Available offerings'),
    offerings.length
      ? table(
          tr('赛项与组别', 'Events & divisions'),
          [
            tr('赛项 / 组别', 'Event / Division'),
            tr('学生人数', 'Students'),
            tr('必交材料', 'Required files'),
          ],
          offerings.map((o) => [
            `<strong>${o.event}</strong><span class="muted">${divisionName(o.group)}</span>`,
            `${o.min}–${o.max}`,
            materialName(o.materials),
          ]),
          false,
        )
      : notice(tr('当前没有开放的报名组合。', 'No registration offerings are currently open.')),
  )}${panel(tr('参赛须知', 'Before registering'), `<ul class="rule-list"><li>${tr('队伍须完成资料审核和所属赛季注册许可。', 'Teams need approved profiles and season licenses.')}</li><li>${tr('按本场开放组合选择学段与组别，准备对应材料。', 'Choose an available division and prepare its required files.')}</li><li>${tr('提交后资料与成员冻结，审核进度在我的报名中查看。', 'Submissions freeze details and members. Follow progress in My registrations.')}</li></ul>`)}${
    index === 0 && config.published
      ? panel(
          tr('通过名单公示', 'Approved roster'),
          config.publication === 'login' && state.role === 'visitor'
            ? notice(
                tr(
                  '本名单对所有登录用户开放，请先登录。',
                  'This roster is available to all signed-in users. Sign in first.',
                ),
              )
            : table(
                tr('审核通过名单', 'Approved entries'),
                [tr('队号', 'Team number'), tr('赛项', 'Event'), tr('组别', 'Division')],
                state.registrations
                  .filter((r) => r.status === 'approved')
                  .map((r) => [r.code, r.event, r.group]),
                false,
              ),
        )
      : ''
  }</div><aside class="stack">${panel(tr('报名本场赛事', 'Register for this edition'), `<dl class="event-deadlines"><div><dt>${tr('报名开始', 'Registration opens')}</dt><dd>${date(config.enrollStart)}</dd></div><div><dt>${tr('报名截止', 'Registration closes')}</dt><dd>${date(config.enrollEnd)}</dd></div></dl><p class="form-hint">${tr('北京时间 · Asia/Shanghai', 'All times in Asia/Shanghai')}</p>${index !== 0 ? notice(tr('该赛事为只读预览；报名交互请体验华东区域公开赛。', 'Read-only preview. Try the Regional Open registration workflow.')) : !offerings.length ? notice(tr('报名暂未开放，请联系赛事方。', 'Registration is closed. Contact the organizer.')) : state.role === 'visitor' ? link(tr('登录后报名', 'Sign in to register'), 'login', 'primary', 'arrow') : can('registration:write') ? link(tr('填写报名', 'Register a team'), 'registration', 'primary', 'arrow') : can('competition:manage') ? link(tr('配置本场赛事', 'Configure competition'), 'edition', 'primary', 'settings') : canReview() ? link(tr('审核本场报名', 'Review submissions'), 'reviews', 'primary', 'shield') : link(tr('查看报名记录', 'View registrations'), 'registrations', '', 'arrow')}`)}</aside></div>`;
}
function renderCompetitionRegistry() {
  const config = editionConfig();
  if (state.season !== '2026-2027')
    return (
      pageHead(
        tr('赛事管理', 'Competition management'),
        tr('按当前赛季管理赛事。', 'Manage competitions in the current season.'),
      ) +
      currentSeasonContext() +
      empty(
        tr('本赛季暂无赛事', 'No competitions this season'),
        tr(
          '此预览的可编辑样例属于 2026–2027 赛季。',
          'The editable sample belongs to the 2026–2027 season.',
        ),
      )
    );
  return `<div class="registry-head"><div><p class="eyebrow">COMPETITION DIRECTORY</p><h1 id="page-title" tabindex="-1">${tr('赛事管理', 'Competition management')}</h1><p class="muted">${tr('从配置到发证，按赛事跟进每一项工作。', 'Manage each competition from setup to certificates.')}</p></div>${currentSeasonContext()}</div>
    <section class="registry-focus"><div><span class="technical-label">${tr('当前管理赛事', 'CURRENT COMPETITION')} / 01</span><h2>${esc(config.name)}</h2><div class="spotlight-meta"><span>${icon('calendar')}${config.start.slice(0, 10)} — ${config.end.slice(5, 10)}</span><span>${icon('pin')}${esc(config.venue)}</span></div></div><div class="registry-focus-action"><span class="tag">${tr('已发布 · 报名中', 'Published · Registration open')}</span>${link(tr('管理本场赛事', 'Manage competition'), 'edition', 'primary', 'arrow')}</div></section>
    <div class="registry-section-head"><h2>${tr('本场工作', 'Competition operations')}</h2><span class="muted">${tr('2026–2027 赛季', '2026–2027 season')}</span></div>
    <div class="operation-links">${[
      [
        'edition',
        'settings',
        tr('赛事配置', 'Competition setup'),
        tr('时间、报名规则与开放组合', 'Dates, rules and offerings'),
      ],
      [
        'reviews',
        'shield',
        tr('报名审核', 'Registration review'),
        tr('核验本轮冻结资料与成员', 'Review frozen submissions and members'),
      ],
      [
        'access',
        'lock',
        tr('队伍准入', 'Team eligibility'),
        tr('维护本场参赛准入名单', 'Manage this edition’s eligible teams'),
      ],
      [
        'awards',
        'trophy',
        tr('获奖名单', 'Award rosters'),
        tr('评奖、确认与锁定名单', 'Prepare, confirm and lock rosters'),
      ],
      [
        'certificates',
        'file',
        tr('证书发放', 'Certificates'),
        tr('逐人生成、发放与失败重试', 'Issue per student and retry failures'),
      ],
    ]
      .map(
        ([page, symbol, title, desc], i) =>
          `<a href="#${page}" class="operation-link"><span class="operation-index">0${i + 1}</span>${icon(symbol)}<div><h3>${title}</h3><p>${desc}</p></div>${icon('arrow')}</a>`,
      )
      .join('')}</div>
    <div class="registry-section-head"><h2>${tr('其他赛事', 'Other competitions')}</h2>${link(tr('浏览赛事门户', 'Browse portal'), 'portal', 'text', 'arrow')}</div>
    ${notice(tr('其余赛事仅提供门户预览。本次可编辑的管理样例为华东区域公开赛。', 'Other competitions are portal previews. The East China Regional Open is the editable management example.'))}`;
}
function editionInput(id, title, value, type = 'text', extra = '') {
  return field(`op-${id}`, title, value, type, `${extra} data-edition-field="${id}"`);
}
function renderEditionManager() {
  const config = editionConfig();
  const draft = (state.editionDraft ||= structuredClone(config));
  const selected = state.editionSection || 'basics';
  const sections = [
    ['basics', tr('基本信息', 'Overview')],
    ['rules', tr('报名规则', 'Registration rules')],
    ['offerings', tr('赛项与组别', 'Events & divisions')],
    ['publish', tr('发布检查', 'Publication')],
  ];
  const checks = editionChecks(draft);
  const failed = checks.filter(([, passed]) => !passed).length;
  let body;
  if (selected === 'basics')
    body =
      panel(
        tr('赛事基本信息', 'Competition details'),
        `<div class="form-grid">${editionInput('name', tr('赛事名称 *', 'Competition title *'), draft.name, 'text', 'required maxlength="100"')}${editionInput('venue', tr('比赛地点 *', 'Venue *'), draft.venue, 'text', 'required maxlength="100"')}<div class="field"><label>${tr('所属赛季', 'Season')}</label><p class="locked-value">${icon('lock')}2026–2027</p><small class="muted">${tr('已有报名提交，赛季不可更改。', 'Locked after the first submission.')}</small></div><div class="field"><label>${tr('赛事管理人员', 'Competition administrators')}</label><p class="locked-value">${tr('赛事管理员', 'Competition admin')}</p><small class="muted">${tr('仅平台管理员分配管理角色。', 'Only platform admins assign management roles.')}</small></div></div>`,
      ) +
      panel(
        tr('报名与比赛时间', 'Dates & deadlines'),
        `<p class="form-hint">${tr('以下时间均为北京时间（Asia/Shanghai）。报名截止须不晚于比赛开始。', 'All times use Asia/Shanghai. Registration must close before the competition starts.')}</p><div class="form-grid">${editionInput('enrollStart', tr('报名开始 *', 'Registration opens *'), draft.enrollStart, 'datetime-local', 'required')}${editionInput('enrollEnd', tr('报名截止 *', 'Registration closes *'), draft.enrollEnd, 'datetime-local', 'required')}${editionInput('start', tr('比赛开始 *', 'Competition starts *'), draft.start, 'datetime-local', 'required')}${editionInput('end', tr('比赛结束 *', 'Competition ends *'), draft.end, 'datetime-local', 'required')}</div>`,
      );
  if (selected === 'rules')
    body =
      panel(
        tr('报名审核方式', 'Review workflow'),
        `<fieldset class="choice-set"><legend class="sr-only">${tr('选择审核方式', 'Choose review workflow')}</legend>${[
          [
            'single',
            tr('单级审核', 'Single-stage review'),
            tr('提交报名 → 赛事审核 → 审核结果', 'Submission → Competition review → Result'),
          ],
          [
            'two_stage',
            tr('两级审核', 'Two-stage review'),
            tr('提交报名 → 单位初审 → 赛事复审', 'Submission → Organization review → Final review'),
          ],
        ]
          .map(
            ([value, title, desc]) =>
              `<label class="choice-row"><input type="radio" name="op-review" data-edition-field="review" value="${value}" ${draft.review === value ? 'checked' : ''}><span><strong>${title}</strong><small>${desc}</small></span></label>`,
          )
          .join(
            '',
          )}</fieldset><p class="form-hint">${tr('变更只对下一次提交生效。已提交报名保留当轮审核模式和资料快照。', 'Changes apply to the next submission. Existing submissions retain their review mode and snapshot.')}</p>`,
      ) +
      panel(
        tr('提交与更正规则', 'Submission & correction'),
        `<ul class="rule-list"><li>${tr('队伍须持本赛季有效许可，并满足本场准入要求。', 'Teams need a valid season license and edition eligibility.')}</li><li>${tr('提交人选择学段与开放组别；提交后资料、成员及材料冻结。', 'Choose an available school level and division. Submission freezes details, members and files.')}</li><li>${tr('本轮未审可取消修改；已通过须先驳回，再在有效时间窗内重提。', 'Cancel an unreviewed submission to edit. Approved entries must be rejected before resubmission within the registration window.')}</li></ul>`,
      );
  if (selected === 'offerings')
    body = `<section class="panel"><div class="panel-head"><div><h2>${tr('开放报名组合', 'Registration offerings')}</h2><p class="form-hint">${tr('赛项与组别分别管理，只有开放的组合允许报名。停用不影响存量审核。', 'Events and divisions are independent. Only open combinations accept submissions; existing reviews continue.')}</p></div>${btn(tr('添加组合', 'Add offering'), 'offering-edit:new', '', 'plus')}</div>${table(
      tr('开放组合', 'Offerings'),
      [
        tr('赛项 / 组别', 'Event / Division'),
        tr('学生人数', 'Students'),
        tr('必交材料', 'Required files'),
        tr('状态', 'Status'),
        tr('操作', 'Actions'),
      ],
      draft.offerings.map((o, i) => [
        `<strong>${o.event}</strong><span class="muted">${divisionName(o.group)}</span>`,
        `${o.min}–${o.max}`,
        materialName(o.materials),
        `<span class="tag ${o.enabled ? 'green' : ''}">${o.enabled ? tr('开放报名', 'Open') : tr('已停用', 'Disabled')}</span>`,
        `<div class="actions">${btn(tr('编辑', 'Edit'), `offering-edit:${i}`, 'text small')}${btn(o.enabled ? tr('停用', 'Disable') : tr('启用', 'Enable'), `offering-toggle:${i}`, 'text small')}</div>`,
      ]),
      false,
    )}<div class="offering-foot">${icon('shield')}${tr('已有提交的组合保留记录，通过停用关闭新报名。', 'Keep offerings with submissions; disable them to close new registrations.')}</div></section>`;
  if (selected === 'publish')
    body =
      panel(
        tr('配置完整性', 'Configuration checks'),
        `<div class="publication-status"><span class="check-emblem ${failed ? 'incomplete' : ''}">${icon(failed ? 'file' : 'check')}</span><div><h3>${failed ? tr(`${failed} 项配置需要补全`, `${failed} checks need attention`) : tr('当前配置通过检查', 'Configuration checks passed')}</h3><p>${tr('保存配置后生效；修改不会覆盖既有提交快照。', 'Save to apply. Existing submission snapshots are retained.')}</p></div></div><div class="checklist">${checks.map(([title, passed, section]) => `<div class="checklist-row"><span class="check-symbol ${passed ? 'passed' : ''}">${icon(passed ? 'check' : 'close')}</span><strong>${title}</strong><span>${passed ? tr('已完成', 'Ready') : tr('待完善', 'Incomplete')}</span>${btn(tr('检查配置', 'Inspect'), `edition-section:${section}`, 'text small')}</div>`).join('')}</div>`,
      ) +
      panel(
        tr('通过名单公示', 'Approved roster publication'),
        `<div class="field"><label for="op-publication">${tr('可见范围', 'Visibility')}</label><select id="op-publication" data-edition-field="publication">${[
          ['none', tr('不公示', 'Private')],
          ['login', tr('所有登录用户可见', 'All signed-in users')],
          ['open', tr('公开可见', 'Public')],
        ]
          .map(
            ([value, title]) =>
              `<option value="${value}" ${draft.publication === value ? 'selected' : ''}>${title}</option>`,
          )
          .join(
            '',
          )}</select></div><p class="form-hint">${tr('公示仅包含审核通过名单。获奖名单需单独确认，不与通过名单混用。', 'Publication includes approved entries. Award rosters require separate confirmation.')}</p><div class="publication-actions"><span class="tag ${config.published ? 'green' : ''}">${config.published ? tr('名单已公示', 'Roster published') : tr('名单未公示', 'Roster private')}</span>${config.published ? btn(tr('下架公示', 'Unpublish roster'), 'edition-unpublish') : btn(tr('公示通过名单', 'Publish approved roster'), 'edition-publish', '', 'globe')}</div>`,
      );
  return `<div class="edition-back">${link(tr('赛事管理', 'Competitions'), 'competitions', 'text small', 'left')}<span>/</span><span>${tr('本场配置', 'Edition setup')}</span></div><header class="edition-heading"><div><p class="eyebrow">EDITION / 2026 EAST CHINA</p><h1 id="page-title" tabindex="-1">${esc(config.name)}</h1><div class="actions"><span class="tag green">${tr('已发布', 'Published')}</span><span class="muted">2026–2027 · ${tr('上海', 'Shanghai')} · V5RC / VIQRC</span></div></div>${btn(tr('预览赛事门户', 'Preview portal'), 'open-competition:0', '', 'arrow')}</header>
    <nav class="edition-nav" aria-label="${tr('赛事配置分区', 'Competition setup sections')}">${sections.map(([id, title], i) => `<button type="button" data-action="edition-section:${id}" ${selected === id ? 'aria-current="page"' : ''}><span>0${i + 1}</span>${title}</button>`).join('')}</nav>
    <div class="edition-layout"><form id="edition-form" class="edition-panels">${body}<p id="edition-error" role="alert" class="edition-error"></p><footer class="edition-save"><span id="edition-save-status" role="status">${state.editionDirty ? tr('有未保存的修改', 'Unsaved changes') : tr('配置已保存到本次预览', 'Saved in this preview')}</span><button class="button primary" type="submit">${icon('check')}${tr('保存配置', 'Save configuration')}</button></footer></form><aside class="edition-aside"><span class="technical-label">${tr('本场工作流', 'EDITION WORKFLOW')}</span><ol><li class="current">${tr('配置与发布', 'Setup & publication')}</li><li>${link(tr('报名与审核', 'Registration & review'), 'reviews', 'text small')}</li><li>${link(tr('获奖名单确认', 'Confirm awards'), 'awards', 'text small')}</li><li>${link(tr('逐人发放证书', 'Issue certificates'), 'certificates', 'text small')}</li></ol><div class="aside-note">${icon('lock')}<p>${tr('关闭赛事前须锁定获奖名单，并完成证书发放。当前样例尚有待审报名，不能关闭。', 'Lock award rosters and issue certificates before closing. This sample still has pending reviews.')}</p></div></aside></div>`;
}
function editOffering(value) {
  const draft = state.editionDraft;
  const index = value === 'new' ? -1 : Number(value);
  const offering =
    index < 0
      ? { event: 'V5RC', group: 'HS', min: 3, max: 5, materials: 'project' }
      : draft.offerings[index];
  if (!offering) return;
  state.offeringIndex = index;
  for (const key of ['offering-min', 'offering-max']) delete state.form[key];
  const choose = (id, title, options, selected) => selectField(id, title, options, '', selected);
  dialog(
    tr(index < 0 ? '添加报名组合' : '编辑报名组合', index < 0 ? 'Add offering' : 'Edit offering'),
    tr('同一赛项与组别只能配置一次。', 'Each event and division combination must be unique.'),
    `<form id="offering-form" class="stack">${choose(
      'offering-event',
      tr('赛项', 'Event'),
      [
        ['V5RC', 'V5RC'],
        ['VIQRC', 'VIQRC'],
      ],
      offering.event,
    )}${choose(
      'offering-group',
      tr('组别', 'Division'),
      ['ES', 'MS', 'HS'].map((id) => [id, divisionName(id)]),
      offering.group,
    )}<div class="form-grid">${field('offering-min', tr('最少学生人数 *', 'Minimum students *'), offering.min, 'number', 'min="1" max="99" required')}${field('offering-max', tr('最多学生人数 *', 'Maximum students *'), offering.max, 'number', 'min="1" max="99" required')}</div>${choose(
      'offering-materials',
      tr('必交材料', 'Required files'),
      [
        ['consent', materialName('consent')],
        ['project', materialName('project')],
      ],
      offering.materials,
    )}<p id="offering-error" role="alert" class="edition-error"></p><button type="submit" class="button primary">${tr('应用组合', 'Apply offering')}</button></form>`,
  );
}
function handleOperationsAction(action, arg) {
  if (
    ![
      'edition-section',
      'offering-edit',
      'offering-toggle',
      'edition-publish',
      'edition-unpublish',
      'edition-confirm-publish',
    ].includes(action)
  )
    return false;
  if (!can('competition:manage')) return true;
  const draft = (state.editionDraft ||= structuredClone(editionConfig()));
  if (action === 'edition-section') {
    state.editionSection = arg;
    render();
    $(`[data-action="edition-section:${arg}"]`)?.focus();
  }
  if (action === 'offering-edit') editOffering(arg);
  if (action === 'offering-toggle' && draft.offerings[Number(arg)]) {
    draft.offerings[Number(arg)].enabled = !draft.offerings[Number(arg)].enabled;
    state.editionDirty = true;
    render();
  }
  if (action === 'edition-publish') {
    if (state.editionDirty) {
      toast(tr('请先保存配置，再公示名单。', 'Save configuration before publishing.'));
      return true;
    }
    if (draft.publication === 'none') {
      toast(tr('请先选择可见范围并保存。', 'Choose and save a visibility scope first.'));
      return true;
    }
    dialog(
      tr('公示通过名单', 'Publish approved roster'),
      tr('仅公示本场已通过的报名。', 'Only approved entries in this edition are published.'),
      notice(
        draft.publication === 'login'
          ? tr(
              '所有登录用户均可查看，不限本单位或参赛者。',
              'Every signed-in user can view this roster.',
            )
          : tr('任何访客均可查看通过名单。', 'Every visitor can view the approved roster.'),
      ),
      btn(tr('取消', 'Cancel'), 'close') +
        btn(tr('确认公示', 'Publish roster'), 'edition-confirm-publish', 'primary'),
    );
  }
  if (
    action === 'edition-confirm-publish' &&
    (state.editionDirty ||
      editionConfig().publication === 'none' ||
      editionChecks().some(([, passed]) => !passed))
  ) {
    toast(
      tr(
        '请先保存完整配置并选择公示范围。',
        'Save valid configuration and choose visibility first.',
      ),
    );
    return true;
  }
  if (action === 'edition-confirm-publish' || action === 'edition-unpublish') {
    editionConfig().published = action === 'edition-confirm-publish';
    draft.published = editionConfig().published;
    closeDialog();
    render();
    toast(tr('本次预览的公示状态已更新。', 'Publication updated in this preview.'));
  }
  return true;
}
function handleOperationsForm(form) {
  if (!['edition-form', 'offering-form'].includes(form.id)) return false;
  if (!can('competition:manage')) return true;
  if (form.id === 'edition-form') {
    const failed = editionChecks(state.editionDraft).filter(([, passed]) => !passed);
    if (failed.length) {
      $('#edition-error').textContent =
        tr('请完善：', 'Complete: ') + failed.map(([title]) => title).join('、');
      $('#edition-error').scrollIntoView({ block: 'center' });
      return true;
    }
    if (state.editionDraft.publication === 'none') state.editionDraft.published = false;
    state.editionConfig = structuredClone(state.editionDraft);
    state.editionDirty = false;
    render();
    toast(tr('配置已保存在本次预览中，刷新后重置。', 'Saved in this preview. Refresh resets it.'));
  } else {
    const offering = {
      event: $('#offering-event').value,
      group: $('#offering-group').value,
      min: Number($('#offering-min').value),
      max: Number($('#offering-max').value),
      materials: $('#offering-materials').value,
      enabled:
        state.offeringIndex < 0 ? true : state.editionDraft.offerings[state.offeringIndex].enabled,
    };
    const duplicate = state.editionDraft.offerings.some(
      (o, i) =>
        i !== state.offeringIndex && o.event === offering.event && o.group === offering.group,
    );
    if (duplicate || offering.min > offering.max) {
      $('#offering-error').textContent = duplicate
        ? tr(
            '该赛项与组别已存在，请编辑原组合。',
            'This combination exists. Edit the existing offering.',
          )
        : tr('最多人数不能少于最少人数。', 'Maximum cannot be less than minimum.');
      return true;
    }
    if (state.offeringIndex < 0) state.editionDraft.offerings.push(offering);
    else state.editionDraft.offerings[state.offeringIndex] = offering;
    state.editionDirty = true;
    closeDialog();
    render();
  }
  return true;
}
function revealEditionSection() {
  const nav = $('.edition-nav');
  const current = $('.edition-nav [aria-current="page"]');
  if (!nav?.getBoundingClientRect || !current) return;
  const edge = nav.getBoundingClientRect();
  const item = current.getBoundingClientRect();
  if (item.right > edge.right) nav.scrollLeft += item.right - edge.right + 16;
  else if (item.left < edge.left) nav.scrollLeft -= edge.left - item.left + 16;
}
document.addEventListener('input', (event) => {
  const key = event.target.dataset.editionField;
  if (!key || !can('competition:manage')) return;
  state.editionDraft[key] = event.target.value;
  state.editionDirty = true;
  $('#edition-save-status').textContent = tr('有未保存的修改', 'Unsaved changes');
});
