(() => {
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  let csrfToken = csrfMeta ? csrfMeta.getAttribute('content') || '' : '';
  const list = document.querySelector('[data-applications-list]');
  const statusEl = document.querySelector('[data-applications-status]');
  const err = document.querySelector('[data-applications-error]');
  const emptyEl = document.querySelector('[data-applications-empty]');
  const statuses = window.PRAYASH_APPLICATION_STATUSES || ['Bookmarked', 'Applying', 'Applied', 'Interviewing', 'Accepted', 'Rejected'];

  const text = (el, value) => { if (el) el.textContent = value; };
  const show = (el, on) => { if (el) el.hidden = !on; };

  const withCsrf = async (url, options) => {
    const headers = Object.assign({ 'X-CSRFToken': csrfToken }, options.headers || {});
    let res = await fetch(url, Object.assign({}, options, { headers }));
    if (res.status === 400) {
      const cloned = res.clone();
      const body = await cloned.text();
      if (/csrf/i.test(body)) {
        const tokenRes = await fetch('/api/csrf-token');
        const tokenData = await tokenRes.json();
        if (tokenData.csrf_token) {
          csrfToken = tokenData.csrf_token;
          if (csrfMeta) csrfMeta.setAttribute('content', csrfToken);
          headers['X-CSRFToken'] = csrfToken;
          res = await fetch(url, Object.assign({}, options, { headers }));
        }
      }
    }
    return res;
  };

  const loadVersions = async () => {
    const res = await fetch('/api/resume-versions');
    if (!res.ok) return [];
    const data = await res.json();
    return data.resume_versions || [];
  };

  const patchApplication = async (id, payload) => {
    const res = await withCsrf(`/api/applications/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    let data = {};
    try {
      data = await res.json();
    } catch (parseError) {
      throw new Error('Could not update that saved job. Check your connection and try again.');
    }
    if (!res.ok || !data.success) throw new Error(data.error || 'Could not update that saved job.');
    return data.application;
  };

  const render = (applications, versions) => {
    if (!list) return;
    list.replaceChildren();
    show(emptyEl, applications.length === 0);
    applications.forEach((item) => {
      const li = document.createElement('li');
      li.className = 'evidence-item';
      const job = item.job || {};
      const heading = document.createElement('h2');
      heading.className = 'section-title';
      heading.textContent = job.title || 'Saved job';
      const meta = document.createElement('p');
      meta.className = 'small-note';
      meta.textContent = job.company ? job.company : 'No company recorded';
      const comparison = document.createElement('p');
      comparison.className = 'small-note';
      if (item.comparison_available && item.target_job_match_id) {
        const link = document.createElement('a');
        link.href = '/workspace/job-match';
        link.textContent = 'Open comparison';
        comparison.append(link);
      } else {
        comparison.textContent = 'The linked comparison is no longer available. The saved job row was kept.';
      }
      const statusLabel = document.createElement('label');
      statusLabel.setAttribute('for', `application-status-${item.id}`);
      statusLabel.textContent = 'Status';
      const statusSelect = document.createElement('select');
      statusSelect.id = `application-status-${item.id}`;
      statuses.forEach((name) => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        if (name === item.status) option.selected = true;
        statusSelect.append(option);
      });
      const followLabel = document.createElement('label');
      followLabel.setAttribute('for', `application-follow-${item.id}`);
      followLabel.textContent = 'Follow-up date';
      const follow = document.createElement('input');
      follow.id = `application-follow-${item.id}`;
      follow.type = 'date';
      follow.value = item.follow_up_date || '';
      const resumeLabel = document.createElement('label');
      resumeLabel.setAttribute('for', `application-resume-${item.id}`);
      resumeLabel.textContent = 'Attached resume version';
      const resumeSelect = document.createElement('select');
      resumeSelect.id = `application-resume-${item.id}`;
      const none = document.createElement('option');
      none.value = '';
      none.textContent = 'None';
      resumeSelect.append(none);
      versions.forEach((version) => {
        const option = document.createElement('option');
        option.value = String(version.id);
        option.textContent = `Resume: ${version.name} · Version: ${version.id}`;
        if (item.resume_version_id === version.id) option.selected = true;
        resumeSelect.append(option);
      });
      const notesLabel = document.createElement('label');
      notesLabel.setAttribute('for', `application-notes-${item.id}`);
      notesLabel.textContent = 'Notes';
      const notes = document.createElement('textarea');
      notes.id = `application-notes-${item.id}`;
      notes.rows = 3;
      notes.maxLength = 4000;
      notes.value = item.notes || '';
      const applied = document.createElement('button');
      applied.type = 'button';
      applied.className = 'button';
      applied.textContent = 'Mark applied';
      const save = document.createElement('button');
      save.type = 'button';
      save.className = 'button-outline';
      save.textContent = 'Save changes';
      const update = async (payload) => {
        show(err, false);
        try {
          await patchApplication(item.id, payload);
          text(statusEl, 'Saved job updated.');
        } catch (error) {
          text(err, error.message);
          show(err, true);
        }
      };
      statusSelect.addEventListener('change', () => update({ status: statusSelect.value }));
      applied.addEventListener('click', () => {
        statusSelect.value = 'Applied';
        update({ status: 'Applied' });
      });
      save.addEventListener('click', () => update({
        notes: notes.value,
        follow_up_date: follow.value || null,
        resume_version_id: resumeSelect.value ? Number(resumeSelect.value) : null,
      }));
      li.append(
        heading, meta, comparison,
        statusLabel, statusSelect,
        followLabel, follow,
        resumeLabel, resumeSelect,
        notesLabel, notes,
        applied, save,
      );
      list.append(li);
    });
  };

  const boot = async () => {
    try {
      const [appsRes, versions] = await Promise.all([fetch('/api/applications'), loadVersions()]);
      if (!appsRes.ok) throw new Error('Could not load saved jobs.');
      const data = await appsRes.json();
      render(data.applications || [], versions);
      text(statusEl, (data.applications || []).length ? 'Saved jobs loaded.' : 'No saved jobs yet.');
    } catch (error) {
      text(err, error.message);
      show(err, true);
    }
  };

  boot();
})();
