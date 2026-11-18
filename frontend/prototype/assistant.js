/* One tab's in-memory preview session. No model, browser storage or business writes. */
const assistantSession = {
  messages: [],
  draft: '',
  isOpen: false,
  actor: '',
  lang: '',
  hasUnread: false,
};

function syncAssistant() {
  const actor = JSON.stringify([state.role, state.permissions || permissionsByRole[state.role]]);
  const root = $('#assistant-root');
  const hasActorChanged = assistantSession.actor !== actor;
  if (hasActorChanged) {
    assistantSession.messages = [];
    assistantSession.draft = '';
    assistantSession.actor = actor;
    if (root.dataset.mounted) renderAssistantConversation();
  }
  // The route renderer owns #app; this sibling stays mounted across navigation.
  if (root.dataset.mounted && assistantSession.lang === state.lang && !hasActorChanged) return;
  assistantSession.lang = state.lang;
  root.dataset.mounted = 'true';
  root.innerHTML = `<button type="button" id="assistant-ball" class="assistant-ball" data-action="assistant" aria-label="${tr('打开 AI 助手', 'Open AI assistant')}" aria-controls="assistant-panel" aria-expanded="${assistantSession.isOpen}"><span aria-hidden="true">AI</span></button><dialog id="assistant-panel" class="assistant-panel" aria-labelledby="assistant-title" closedby="closerequest"><header class="assistant-header"><span class="assistant-avatar" aria-hidden="true">AI</span><div><h2 id="assistant-title">${tr('竞云助手', 'CompSphere assistant')}</h2><span>${tr('与你一起完成赛事事务', 'Your competition companion')}</span></div><button type="button" class="icon-button" data-action="assistant-reset" aria-label="${tr('复位位置', 'Reset position')}" title="${tr('复位位置', 'Reset position')}">${icon('left')}</button><button type="button" class="button text small" data-action="assistant-clear">${tr('清空', 'Clear')}</button><button type="button" class="icon-button" data-action="assistant-minimize" aria-label="${tr('收起助手', 'Minimize assistant')}">${icon('close')}</button></header><div id="assistant-messages" class="assistant-messages" role="log" aria-label="${tr('对话记录', 'Conversation')}" aria-live="polite" aria-relevant="additions text"></div><button type="button" class="button small assistant-latest" id="assistant-latest" data-action="assistant-latest" hidden>${tr('回到最新消息', 'Latest messages')}</button><div class="assistant-suggestions">${btn(tr('赛事信息', 'Competition info'), 'assistant-example:details', 'small')}${can('registration:write') ? btn(tr('帮我报名', 'Help me register'), 'assistant-example:register', 'small') : ''}${canReview() ? btn(tr('辅助审核', 'Help me review'), 'assistant-example:review', 'small') : ''}</div><form id="assistant-form" class="assistant-composer"><label class="sr-only" for="assistant-question">${tr('发送消息', 'Send a message')}</label><textarea id="assistant-question" rows="2" maxlength="2000" required placeholder="${tr('问赛事，或告诉我你想做什么…', 'Ask about a competition or a task…')}" autofocus></textarea><button type="submit" id="assistant-send" class="icon-button" disabled aria-label="${tr('发送消息', 'Send message')}">${icon('arrow')}</button></form><footer class="assistant-footnote">${tr('交互预览 · 对话仅在本页保留，刷新即清空', 'Interaction preview · Refresh clears this conversation')}</footer></dialog>`;
  $('#assistant-question').value = assistantSession.draft;
  $('#assistant-send').disabled = !assistantSession.draft.trim();
  $('#assistant-messages').addEventListener('scroll', updateAssistantScroll);
  window.demoMotion?.mountAssistant();
  renderAssistantConversation();
  if (assistantSession.isOpen) $('#assistant-panel').show();
  $('#assistant-panel').addEventListener('close', (event) => {
    // A queued close event can arrive after the same dialog has already reopened.
    if (event.currentTarget.open) return;
    assistantSession.isOpen = false;
    $('#assistant-ball').setAttribute('aria-expanded', 'false');
  });
}

function isAssistantAtLatest(log) {
  return log.scrollHeight - log.scrollTop - log.clientHeight <= 48;
}

function updateAssistantScroll() {
  const log = $('#assistant-messages');
  const button = $('#assistant-latest');
  if (!log || !button) return;
  const atLatest = isAssistantAtLatest(log);
  if (atLatest) assistantSession.hasUnread = false;
  button.hidden = atLatest || !assistantSession.messages.length;
  button.textContent = assistantSession.hasUnread
    ? tr('有新消息 · 回到最新', 'New messages · Latest')
    : tr('回到最新消息', 'Latest messages');
}

function scrollAssistantToLatest() {
  const log = $('#assistant-messages');
  log.scrollTop = log.scrollHeight;
  updateAssistantScroll();
}

function renderAssistantConversation(isNewMessage = false, forceLatest = false) {
  const log = $('#assistant-messages');
  if (!log) return;
  const follow = forceLatest || isAssistantAtLatest(log);
  const count = Number(log.dataset.count || 0);
  if (!assistantSession.messages.length) {
    log.innerHTML = `<div class="assistant-empty"><span class="assistant-avatar" aria-hidden="true">AI</span><h3>${tr('有什么可以帮你？', 'How can I help?')}</h3><p>${tr('查询赛事信息，或让我带你完成报名与审核。', 'Ask about a competition, or let me guide you through registration and review.')}</p></div>`;
    log.dataset.count = '0';
    assistantSession.hasUnread = false;
  } else if (assistantSession.messages.length > count) {
    if (!count) log.innerHTML = '';
    const added = assistantSession.messages.slice(count);
    log.insertAdjacentHTML(
      'beforeend',
      added
        .map(
          (message) =>
            `<article class="assistant-message ${message.role === 'user' ? 'from-user' : 'from-assistant'}"><span>${message.role === 'user' ? tr('你', 'You') : tr('竞云助手', 'Assistant')}</span><p>${esc(message.text)}</p>${message.action ? `<details class="assistant-action" data-status="${message.action.status}"><summary>${icon(message.action.status === 'done' ? 'check' : 'lock')}<span>${esc(message.action.label)}</span><small>${message.action.status === 'done' ? tr('已定位', 'Opened') : tr('未执行', 'Not executed')}</small></summary><p>${tr('复用原页面和表单校验；没有提交报名或作出审核决定。', 'Uses the existing page and form validation. No registration or review decision was submitted.')}</p></details>` : ''}</article>`,
        )
        .join(''),
    );
    log.dataset.count = String(assistantSession.messages.length);
    if (isNewMessage) {
      window.demoMotion?.enter([...log.querySelectorAll('.assistant-message')].slice(count));
      if (!follow) assistantSession.hasUnread = true;
    }
  }
  if (follow) log.scrollTop = log.scrollHeight;
  updateAssistantScroll();
}

function openAssistant() {
  syncAssistant();
  const panel = $('#assistant-panel');
  if (assistantSession.isOpen) return minimizeAssistant();
  assistantSession.isOpen = true;
  // Intentionally outside the top layer: business modals must take priority.
  if (!panel.open) panel.show();
  window.demoMotion?.show(panel);
  $('#assistant-ball').setAttribute('aria-expanded', 'true');
  $('#assistant-question').focus();
}

function minimizeAssistant() {
  assistantSession.isOpen = false;
  const panel = $('#assistant-panel');
  const finish = () => {
    if (!assistantSession.isOpen) {
      panel.close();
      $('#assistant-ball').focus();
    }
  };
  if (window.demoMotion) window.demoMotion.hide(panel, finish);
  else finish();
  $('#assistant-ball').setAttribute('aria-expanded', 'false');
}

function clearAssistantConversation() {
  assistantSession.messages = [];
  assistantSession.draft = '';
  $('#assistant-question').value = '';
  $('#assistant-send').disabled = true;
  renderAssistantConversation();
  $('#assistant-question').focus();
}

function assistantPlan(question) {
  if (/审核|审批|review|approve/i.test(question)) {
    if (!canReview())
      return {
        text: tr(
          '当前账号没有报名审核权限，我不能读取审核队列或内部审核资料。',
          'Your account cannot review registrations. I cannot access review queues or internal review data.',
        ),
      };
    return {
      command: 'review',
      text: tr(
        '已打开授权范围内的报名审核队列。请核验本轮资料后作出决定；当前预览不会自动通过或驳回。',
        'Opened the authorized review queue. Verify the current submission before deciding; this preview never approves or rejects automatically.',
      ),
    };
  }
  if (/我的报名|my registrations/i.test(question)) {
    if (!pageAllowed('registrations'))
      return { text: tr('请先登录后查看本人报名。', 'Sign in to view your registrations.') };
    return {
      command: 'registrations',
      text: tr('已打开你有权访问的报名记录。', 'Opened the registration records available to you.'),
    };
  }
  if (
    /报名|register|registration/i.test(question) &&
    !/截止|时间|何时|when|deadline|close/i.test(question)
  ) {
    if (state.role === 'visitor')
      return {
        command: 'login',
        text: tr(
          '已打开登录页。登录后我才能使用你的报名权限。',
          'Opened sign-in. Sign in before I can use your registration permissions.',
        ),
      };
    if (!can('registration:write'))
      return {
        text: tr(
          '当前账号没有报名提交权限，不能借用管理权限代替参赛者报名。',
          'Your account cannot submit registrations or borrow administrator privileges.',
        ),
      };
    const group = /高中|high school/i.test(question)
      ? 'HS'
      : /初中|middle school/i.test(question)
        ? 'MS'
        : undefined;
    const frozen = !['draft', 'returned', 'rejected'].includes(state.registrations[0].status);
    return {
      command: 'register',
      group,
      text: frozen
        ? tr(
            '已打开报名表。当前报名已提交，资料被冻结，我没有修改它；如需更正，请使用表单中的“取消并修改”或原审核流程。',
            'Opened the registration form. The submitted data is frozen and unchanged. Use Cancel & edit or the original review workflow to correct it.',
          )
        : group
          ? tr(
              `已打开报名表，并将学段与组别选为${divisionName(group)}。请补全材料并核对后提交。`,
              `Opened the registration form and selected ${divisionName(group)}. Complete the materials and verify before submitting.`,
            )
          : tr(
              '已打开报名表。你可以继续在表单中选择组别、补全材料；提交仍使用原有校验。',
              'Opened the registration form. Choose a division and complete the materials; submission uses the existing validation.',
            ),
    };
  }
  if (/赛事|比赛|截止|competition|deadline|when/i.test(question)) {
    if (state.season !== '2026-2027')
      return {
        text: tr('当前赛季暂无可见赛事。', 'No visible competitions in the current season.'),
      };
    const config = editionConfig();
    // Public-field projection only. Never serialize state, rosters or user profiles.
    return {
      command: /打开|带我|进入|open|go to/i.test(question) ? 'details' : undefined,
      text: tr(
        `${config.name}\n报名截止：${config.enrollEnd.replace('T', ' ')}（北京时间）\n地点：${config.venue}`,
        `${config.name}\nRegistration closes: ${config.enrollEnd.replace('T', ' ')} (Asia/Shanghai)\nVenue: ${config.venue}`,
      ),
    };
  }
  return {
    text: tr(
      '我可以查询可见赛事，打开报名表、选择组别，或带你进入有权访问的审核队列。你想先做哪一项？',
      'I can explain visible competitions, open registration forms, choose divisions or navigate to authorized reviews. What would you like to do?',
    ),
  };
}

function executeAssistantCommand(plan) {
  const routes = {
    register: 'registration',
    review: 'reviews',
    registrations: 'registrations',
    details: 'public-event',
    login: 'login',
  };
  const target = routes[plan.command];
  if (!target || !pageAllowed(target)) return false;
  if (
    (plan.command === 'register' && !can('registration:write')) ||
    (plan.command === 'review' && !canReview())
  )
    return false;
  if (plan.group && ['draft', 'returned', 'rejected'].includes(state.registrations[0].status)) {
    if (
      !editionConfig().offerings.some(
        (o) => o.event === 'V5RC' && o.group === plan.group && o.enabled,
      )
    )
      return false;
    state.form['reg-level'] = plan.group;
    state.form['reg-group'] = plan.group;
  }
  state.competitionIndex = 0;
  if (location.hash === `#${target}`) {
    state.page = target;
    render();
  } else location.hash = target;
  return true;
}

function sendAssistantMessage() {
  syncAssistant();
  const input = $('#assistant-question');
  const question = input.value.trim();
  if (!question) return;
  assistantSession.messages.push({ role: 'user', text: question });
  const plan = assistantPlan(question);
  const didExecute = plan.command ? executeAssistantCommand(plan) : false;
  if (plan.command && !didExecute)
    plan.text = tr(
      '当前权限或报名组合已变化，未执行操作。请核对后重试。',
      'Permissions or offerings changed. No action was performed; check and retry.',
    );
  const actionLabels = {
    register: tr('打开报名表', 'Open registration'),
    review: tr('打开审核队列', 'Open reviews'),
    registrations: tr('查看报名记录', 'View registrations'),
    details: tr('打开赛事详情', 'Open competition'),
    login: tr('打开登录页', 'Open sign-in'),
  };
  assistantSession.messages.push({
    role: 'assistant',
    text: plan.text,
    action: plan.command
      ? { label: actionLabels[plan.command], status: didExecute ? 'done' : 'blocked' }
      : undefined,
  });
  assistantSession.draft = '';
  input.value = '';
  $('#assistant-send').disabled = true;
  renderAssistantConversation(true, true);
  input.focus();
}

document.addEventListener('input', (event) => {
  if (event.target.id === 'assistant-question') {
    assistantSession.draft = event.target.value;
    $('#assistant-send').disabled = !event.target.value.trim();
  }
});
document.addEventListener('keydown', (event) => {
  if (event.target.id !== 'assistant-question') return;
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    sendAssistantMessage();
  }
  if (event.key === 'Escape' && !$('#drawer').open) minimizeAssistant();
});
