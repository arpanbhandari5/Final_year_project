(() => {
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  let csrfToken = csrfMeta ? csrfMeta.getAttribute('content') || '' : '';
  const statusEl = document.querySelector('[data-workspace-status]');
  const goalForm = document.querySelector('[data-goal-form]');
  const evidenceForm = document.querySelector('[data-evidence-form]');
  const occupationSelect = document.getElementById('goal-occupation');
  const alternativeSelect = document.getElementById('goal-alternative');
  const evidenceList = document.querySelector('[data-evidence-list]');

  const text = (el, value) => { if (el) el.textContent = value; };
  const show = (el, on) => { if (el) el.hidden = !on; };

  const api = async (url, method, body) => {
    const headers = { 'X-CSRFToken': csrfToken };
    const opts = { method, headers };
    if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    let res = await fetch(url, opts);
    if (res.status === 400) {
      const cloned = res.clone();
      const t = await cloned.text();
      if (/csrf/i.test(t)) {
        const tokenRes = await fetch('/api/csrf-token');
        const tokenData = await tokenRes.json();
        if (tokenData.csrf_token) {
          csrfToken = tokenData.csrf_token;
          if (csrfMeta) csrfMeta.setAttribute('content', csrfToken);
          headers['X-CSRFToken'] = csrfToken;
          res = await fetch(url, opts);
        }
      }
    }
    return res;
  };

  const fillOccupations = async () => {
    const res = await fetch('/api/occupations/selectable');
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || 'Could not load occupations.');
    const fillSelect = (select, includeBlank) => {
      if (!select) return;
      select.replaceChildren();
      if (includeBlank) {
        const blank = document.createElement('option');
        blank.value = '';
        blank.textContent = 'None';
        select.append(blank);
      }
      (data.occupations || []).forEach((item) => {
        const option = document.createElement('option');
        option.value = item.occupation_code;
        option.textContent = `${item.occupation_title} (${item.occupation_code})`;
        select.append(option);
      });
    };
    fillSelect(occupationSelect, false);
    fillSelect(alternativeSelect, true);
  };

  const renderEvidence = (skills) => {
    if (!evidenceList) return;
    evidenceList.replaceChildren();
    skills.forEach((item) => {
      const li = document.createElement('li');
      li.className = 'evidence-item';
      const title = document.createElement('strong');
      title.textContent = item.skill || 'Skill';
      const excerpt = document.createElement('p');
      excerpt.textContent = item.evidence_span || 'No excerpt yet.';
      const meta = document.createElement('p');
      meta.className = 'small-note';
      meta.textContent = `Source: ${item.source_section || 'resume'} · Status: ${item.status || 'needs_review'}`;
      const edit = document.createElement('button');
      edit.type = 'button';
      edit.className = 'button-ghost';
      edit.textContent = 'Confirm';
      edit.setAttribute('aria-label', `Confirm ${item.skill || 'skill'} evidence`);
      edit.addEventListener('click', async () => {
        await api('/api/evidence-profile/correct', 'PATCH', {
          action: 'edit',
          skill_id: item.id,
          skill: item.skill,
          evidence_span: item.evidence_span,
          status: 'confirmed',
        });
        await refresh(true);
      });
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'button-ghost';
      remove.textContent = 'Remove';
      remove.setAttribute('aria-label', `Remove ${item.skill || 'skill'} evidence`);
      remove.addEventListener('click', async () => {
        await api('/api/evidence-profile/correct', 'PATCH', { action: 'delete', skill_id: item.id });
        await refresh(true);
      });
      li.append(title, excerpt, meta, edit, remove);
      evidenceList.append(li);
    });
  };

  const renderLoop = (data) => {
    const goal = data.goal;
    const skills = (data.profile && data.profile.extracted_skills) || [];
    const gap = data.gap || {};
    const action = data.action || {};
    text(statusEl, goal ? `Goal: ${goal.target_role}` : 'Logged in. Set a career goal to continue.');
    show(document.querySelector('[data-goal-empty]'), !goal);
    const summary = document.querySelector('[data-goal-summary]');
    if (goal) {
      show(summary, true);
      text(summary, `${goal.target_role}${goal.target_occupation_code ? ` (${goal.target_occupation_code})` : ''} · ${goal.immediate_goal || 'No immediate goal'} · ${goal.time_per_week || 0} hours/week`);
      if (occupationSelect && goal.target_occupation_code) occupationSelect.value = goal.target_occupation_code;
      if (document.getElementById('goal-location')) document.getElementById('goal-location').value = goal.geography || '';
      if (document.getElementById('goal-seniority')) document.getElementById('goal-seniority').value = goal.seniority || '';
      if (document.getElementById('goal-time')) document.getElementById('goal-time').value = goal.time_per_week || '';
      if (document.getElementById('goal-immediate') && goal.immediate_goal) document.getElementById('goal-immediate').value = goal.immediate_goal;
    } else {
      show(summary, false);
    }
    text(document.querySelector('[data-evidence-summary]'), skills.length ? `${skills.length} skill${skills.length === 1 ? '' : 's'} stored` : 'No skills stored yet.');
    renderEvidence(skills);
    const join = (items) => (items && items.length ? items.join(', ') : '—');
    text(document.querySelector('[data-gap-strong]'), join(gap.strong_evidence));
    text(document.querySelector('[data-gap-review]'), join(gap.needs_review));
    text(document.querySelector('[data-gap-missing]'), join(gap.not_evidenced));
    text(document.querySelector('[data-gap-summary]'), gap.mapped_role ? `Compared with ${gap.mapped_role} skill requirements.` : 'Save a goal and evidence to see the main gap.');
    const rec = data.recommendation || action;
    const hasAction = Boolean(rec && rec.title);
    show(document.querySelector('[data-action-empty]'), !hasAction);
    show(document.querySelector('[data-action-card]'), hasAction);
    text(document.querySelector('[data-action-title]'), rec.title || '');
    text(document.querySelector('[data-action-body]'), rec.description || '');
    text(document.querySelector('[data-action-status]'), action.status ? `Status: ${action.status}` : '');
    window.__workspaceActionId = action.id;
  };

  const refresh = async (persist) => {
    const res = persist ? await api('/api/actions/refresh', 'POST', {}) : await fetch('/api/workspace-loop');
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || 'Workspace failed to load.');
    renderLoop(data);
    return data;
  };

  if (goalForm) {
    goalForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const err = document.querySelector('[data-goal-error]');
      show(err, false);
      try {
        const res = await api('/api/career-goal', 'POST', {
          target_occupation_code: occupationSelect.value,
          alternative_occupation_code: alternativeSelect ? alternativeSelect.value : '',
          geography: document.getElementById('goal-location').value,
          seniority: document.getElementById('goal-seniority').value,
          time_per_week: document.getElementById('goal-time').value,
          immediate_goal: document.getElementById('goal-immediate').value,
        });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error || 'Could not save goal.');
        await refresh(true);
      } catch (error) {
        text(err, error.message);
        show(err, true);
      }
    });
  }
  const deleteBtn = document.querySelector('[data-delete-goal]');
  if (deleteBtn) {
    deleteBtn.addEventListener('click', async () => {
      await api('/api/career-goal', 'DELETE');
      await refresh(true);
    });
  }
  if (evidenceForm) {
    evidenceForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const err = document.querySelector('[data-evidence-error]');
      show(err, false);
      try {
        const res = await api('/api/evidence-profile/correct', 'PATCH', {
          action: 'add',
          skill: document.getElementById('evidence-skill').value,
          evidence_span: document.getElementById('evidence-span').value,
          status: 'user-added',
        });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error || 'Could not add evidence.');
        evidenceForm.reset();
        await refresh(true);
      } catch (error) {
        text(err, error.message);
        show(err, true);
      }
    });
  }
  const patchAction = async (status) => {
    if (!window.__workspaceActionId) {
      await refresh(true);
    }
    if (!window.__workspaceActionId) return;
    await api(`/api/actions/${window.__workspaceActionId}`, 'PATCH', { status });
    await refresh(true);
  };
  document.querySelector('[data-start-action]')?.addEventListener('click', () => patchAction('in_progress'));
  document.querySelector('[data-complete-action]')?.addEventListener('click', () => patchAction('completed'));
  document.querySelector('[data-review-action]')?.addEventListener('click', () => patchAction('needs_review'));
  document.querySelector('[data-refresh-action]')?.addEventListener('click', () => refresh(true));

  fillOccupations().then(() => refresh(false)).catch((error) => {
    text(statusEl, error.message || 'Workspace could not load.');
  });
})();
