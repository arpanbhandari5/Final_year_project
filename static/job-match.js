(() => {
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  let csrfToken = csrfMeta ? csrfMeta.getAttribute('content') || '' : '';
  const form = document.querySelector('[data-job-match-form]');
  const uploadForm = document.querySelector('[data-resume-upload-form]');
  const err = document.querySelector('[data-job-error]');
  const reqList = document.querySelector('[data-req-list]');
  const evidenceList = document.querySelector('[data-evidence-map]');
  const incompleteList = document.querySelector('[data-incomplete-list]');
  const countsEl = document.querySelector('[data-job-counts]');
  const emptyEl = document.querySelector('[data-job-empty]');
  const sourceValueEl = document.querySelector('[data-evidence-source-value]');
  const versionSelect = document.getElementById('resume-version');
  const deleteBtn = document.querySelector('[data-delete-match]');
  const saveBtn = document.querySelector('[data-save-application]');
  const saveStatus = document.querySelector('[data-save-application-status]');
  const dialog = document.querySelector('[data-delete-dialog]');
  const statusEl = document.querySelector('[data-job-status]');
  const analyzeBtn = document.querySelector('[data-analyze-button]');
  let currentMatchId = null;
  let lastFocus = null;

  const STATUS_MARK = {
    matched: 'M',
    partial: 'P',
    'not evidenced': 'N',
    review: 'R',
  };

  const text = (el, value) => { if (el) el.textContent = value; };
  const show = (el, on) => { if (el) el.hidden = !on; };

  const setBusy = (busy, message) => {
    if (form) form.setAttribute('aria-busy', busy ? 'true' : 'false');
    if (analyzeBtn) analyzeBtn.disabled = Boolean(busy);
    text(statusEl, message);
  };

  const friendlyError = (res, data) => {
    const raw = (data && data.error) || '';
    if (res && res.status === 404 && /resume version/i.test(raw)) {
      return 'The selected evidence source is no longer available. Choose another owned source. Another source was not substituted.';
    }
    if (res && res.status === 401) {
      return 'Sign in again to continue. No other account’s comparison was shown.';
    }
    if (res && res.status >= 500) {
      return 'The comparison could not be completed. Try again from this page.';
    }
    if (raw) return raw;
    return 'Could not complete this comparison.';
  };

  const withCsrf = async (url, options) => {
    const headers = Object.assign({ 'X-CSRFToken': csrfToken }, options.headers || {});
    let res = await fetch(url, Object.assign({}, options, { headers }));
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
          res = await fetch(url, Object.assign({}, options, { headers }));
        }
      }
    }
    return res;
  };

  const api = (url, method, body) => withCsrf(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  const selectedSource = () => {
    const checked = document.querySelector('input[name="evidence_source"]:checked');
    return checked ? checked.value : 'profile';
  };

  const statusBadge = (status) => {
    const wrap = document.createElement('p');
    wrap.className = 'tjm-status-line';
    const mark = document.createElement('span');
    mark.className = 'tjm-status-mark';
    mark.setAttribute('aria-hidden', 'true');
    mark.textContent = STATUS_MARK[status] || '?';
    const label = document.createElement('span');
    label.className = 'tjm-status-label';
    label.textContent = status || 'review';
    wrap.append(mark, label);
    return wrap;
  };

  const requirementCard = (row, { includeEvidence }) => {
    const li = document.createElement('li');
    li.className = 'evidence-item tjm-req';
    li.dataset.status = row.status || 'review';
    const title = document.createElement('strong');
    title.textContent = row.requirement || 'Requirement';
    const priority = document.createElement('p');
    priority.className = 'small-note';
    priority.textContent = row.priority === 'preferred' ? 'Preferred' : 'Required';
    const badge = statusBadge(row.status);
    const explanation = document.createElement('p');
    explanation.className = 'small-note';
    if (row.status === 'not evidenced') {
      explanation.textContent = 'Not evidenced in the selected source. ' + (row.why || '');
    } else {
      explanation.textContent = row.why || '';
    }
    li.append(title, priority, badge, explanation);
    if (row.source_line) {
      const provenance = document.createElement('p');
      provenance.className = 'small-note';
      provenance.textContent = `Identified from: ${row.source_line}`;
      li.append(provenance);
    }
    if (includeEvidence) {
      if (row.supporting_evidence) {
        const excerpt = document.createElement('blockquote');
        excerpt.className = 'tjm-excerpt';
        excerpt.textContent = row.supporting_evidence;
        li.append(excerpt);
      } else {
        const none = document.createElement('p');
        none.className = 'small-note';
        none.textContent = 'There is not enough saved evidence to compare this requirement yet.';
        li.append(none);
      }
    }
    return li;
  };

  const render = (data) => {
    currentMatchId = data.id || null;
    const result = data.result || {};
    const requirements = result.requirements || [];
    const counts = result.counts || {};
    const sourceLabel = data.evidence_source_label || result.evidence_source_label || 'Current evidence profile';
    text(sourceValueEl, sourceLabel);
    text(countsEl, `Matched ${counts.matched || 0} · Partial ${counts.partial || 0} · Not evidenced ${counts['not evidenced'] || 0} · Review ${counts.review || 0}`);
    const jobBits = [data.title, data.company, data.location].filter(Boolean).join(' · ');
    const compared = document.querySelector('[data-compared-job]');
    if (jobBits) {
      text(compared, `Comparing: ${jobBits}`);
      show(compared, true);
    }
    show(deleteBtn, Boolean(currentMatchId));
    show(saveBtn, Boolean(currentMatchId));
    const emptyNote = result.empty_extraction_note || '';
    if (emptyNote) {
      text(emptyEl, emptyNote);
      show(emptyEl, true);
    } else {
      text(emptyEl, '');
      show(emptyEl, false);
    }
    if (reqList) {
      reqList.replaceChildren();
      requirements.forEach((row) => reqList.append(requirementCard(row, { includeEvidence: false })));
    }
    if (evidenceList) {
      evidenceList.replaceChildren();
      requirements.filter((row) => row.status === 'matched' || row.status === 'partial').forEach((row) => {
        const li = document.createElement('li');
        li.className = 'evidence-item';
        const details = document.createElement('details');
        const summary = document.createElement('summary');
        summary.textContent = `${row.requirement || 'Requirement'} · ${row.status}`;
        const excerpt = document.createElement('p');
        excerpt.textContent = row.supporting_evidence || 'There is not enough saved evidence to compare this requirement yet.';
        const meta = document.createElement('p');
        meta.className = 'small-note';
        meta.textContent = [row.priority, row.evidence_section, row.evidence_source_label || sourceLabel, row.why].filter(Boolean).join(' · ');
        details.append(summary, excerpt, meta);
        li.append(details);
        evidenceList.append(li);
      });
    }
    if (incompleteList) {
      incompleteList.replaceChildren();
      requirements.filter((row) => row.status === 'not evidenced' || row.status === 'review').forEach((row) => {
        incompleteList.append(requirementCard(row, { includeEvidence: false }));
      });
    }
    show(document.querySelector('[data-empty-supported]'), !(evidenceList && evidenceList.children.length));
    show(document.querySelector('[data-empty-incomplete]'), !(incompleteList && incompleteList.children.length));
    const action = result.next_action || {};
    const gapEl = document.querySelector('[data-job-gap]');
    if (action.gap) {
      text(gapEl, `Gap: ${action.gap}`);
      show(gapEl, true);
    } else {
      text(gapEl, '');
      show(gapEl, false);
    }
    text(document.querySelector('[data-job-action-title]'), action.title || 'No action yet');
    text(document.querySelector('[data-job-action-body]'), action.description || '');
    text(statusEl, 'Comparison complete. Review requirements, evidence, and the next action.');
  };

  const loadVersions = async () => {
    if (!versionSelect) return;
    const res = await fetch('/api/resume-versions');
    if (!res.ok) return;
    const data = await res.json();
    const versions = data.resume_versions || [];
    versionSelect.replaceChildren();
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = versions.length ? 'Select a resume version' : 'No owned resume versions yet';
    versionSelect.append(placeholder);
    versions.forEach((item) => {
      const option = document.createElement('option');
      option.value = String(item.id);
      option.textContent = `Resume: ${item.name} · Version: ${item.id} · ${item.created_at || ''}`;
      versionSelect.append(option);
    });
  };

  const closeDialog = () => {
    show(dialog, false);
    if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
  };

  if (form) {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      show(err, false);
      setBusy(true, 'Comparing the job description with the selected evidence source.');
      try {
        const payload = {
          title: document.getElementById('job-title').value,
          company: document.getElementById('job-company').value,
          location: document.getElementById('job-location').value,
          description: document.getElementById('job-description').value,
          evidence_source: selectedSource(),
        };
        if (payload.evidence_source === 'resume_version') {
          payload.resume_version_id = versionSelect ? versionSelect.value : '';
        }
        const res = await api('/api/target-job-match', 'POST', payload);
        let data = {};
        try { data = await res.json(); } catch (parseError) { data = {}; }
        if (!res.ok || !data.success) throw Object.assign(new Error(friendlyError(res, data)), { handled: true });
        render(data);
      } catch (error) {
        text(err, error.handled ? error.message : friendlyError(null, {}));
        show(err, true);
        text(statusEl, 'Comparison could not be completed.');
      } finally {
        setBusy(false, statusEl ? statusEl.textContent : 'Ready.');
        if (analyzeBtn) analyzeBtn.focus();
      }
    });
  }

  if (uploadForm) {
    uploadForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      show(err, false);
      const fileInput = document.getElementById('job-resume-file');
      if (!fileInput || !fileInput.files || !fileInput.files[0]) {
        text(err, 'Choose a resume file first.');
        show(err, true);
        return;
      }
      const body = new FormData();
      body.append('resume_file', fileInput.files[0]);
      body.append('name', fileInput.files[0].name);
      setBusy(true, 'Storing the uploaded resume as an owned version.');
      try {
        const res = await withCsrf('/api/resume-versions', { method: 'POST', body });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error || 'Could not store that resume version.');
        await loadVersions();
        const created = data.resume_version || {};
        if (versionSelect && created.id) {
          versionSelect.value = String(created.id);
          const resumeRadio = document.querySelector('input[name="evidence_source"][value="resume_version"]');
          if (resumeRadio) resumeRadio.checked = true;
        }
        text(sourceValueEl, `Resume: ${created.name || 'uploaded'} · Version: ${created.id}`);
        text(statusEl, 'Resume version stored. It is now selectable as evidence.');
      } catch (error) {
        text(err, error.message);
        show(err, true);
      } finally {
        if (analyzeBtn) analyzeBtn.disabled = false;
        if (form) form.setAttribute('aria-busy', 'false');
      }
    });
  }

  if (deleteBtn && dialog) {
    deleteBtn.addEventListener('click', () => {
      lastFocus = deleteBtn;
      show(dialog, true);
      const confirm = dialog.querySelector('[data-confirm-delete]');
      if (confirm) confirm.focus();
    });
    dialog.querySelector('[data-cancel-delete]').addEventListener('click', closeDialog);
    dialog.querySelector('[data-confirm-delete]').addEventListener('click', async () => {
      if (!currentMatchId) return;
      const res = await api(`/api/target-job-match/${currentMatchId}`, 'DELETE', {});
      const data = await res.json();
      if (res.ok && data.success) {
        currentMatchId = null;
        closeDialog();
        show(deleteBtn, false);
        show(saveBtn, false);
        if (reqList) reqList.replaceChildren();
        if (evidenceList) evidenceList.replaceChildren();
        if (incompleteList) incompleteList.replaceChildren();
        text(document.querySelector('[data-job-action-title]'), 'No action yet');
        text(document.querySelector('[data-job-action-body]'), 'Comparison deleted. Resume evidence was not removed.');
        text(statusEl, 'Comparison deleted.');
      }
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && dialog && !dialog.hidden) {
        event.preventDefault();
        closeDialog();
      }
    });
  }

  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      if (!currentMatchId) return;
      show(err, false);
      saveBtn.disabled = true;
      try {
        const res = await api(`/api/target-job-match/${currentMatchId}/save-application`, 'POST', {});
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error || 'Could not save this job.');
        const label = data.created ? 'Saved as Bookmarked.' : 'This job was already on your list. The comparison link was updated.';
        text(saveStatus, `${label} This list records jobs you chose to track and what you did next. It is not an ATS score or a prediction that you will be hired.`);
        show(saveStatus, true);
        text(statusEl, 'Job saved to your application list.');
      } catch (error) {
        text(err, error.message || 'Could not save this job. Check your connection and try again.');
        show(err, true);
      } finally {
        saveBtn.disabled = false;
      }
    });
  }

  loadVersions();
})();
