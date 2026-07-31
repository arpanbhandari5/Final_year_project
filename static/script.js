/**
 * Prayash — Frontend Intelligence
 * Features: SSE progress, toasts, keyboard shortcuts, password meter,
 *           SW update, export, comparison, state persistence
 */
(() => {
  'use strict';

  // ─── STATE PERSISTENCE ───
  const STORAGE = {
    theme: 'prayash-theme-mode',
    mode: 'prayash-analysis-mode',
    path: 'prayash-active-path',
    pwaDismissed: 'prayash-pwa-dismissed',
  };
  const load = (key, fb) => { try { return localStorage.getItem(key) || fb; } catch { return fb; } };
  const save = (key, v) => { try { localStorage.setItem(key, v); } catch {} };

  // ─── DOM REFS & CSRF ───
  const $ = (s, p) => (p || document).querySelector(s);
  const $$ = (s, p) => Array.from((p || document).querySelectorAll(s));
  const html = document.documentElement;
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  let csrfToken = csrfMeta?.getAttribute('content') || '';

  /** Fetch a fresh CSRF token and update both the variable and the <meta> tag */
  const refreshCsrfToken = async () => {
    try {
      const res = await fetch('/api/csrf-token');
      if (!res.ok) return;
      const d = await res.json();
      if (d.csrf_token) {
        csrfToken = d.csrf_token;
        if (csrfMeta) csrfMeta.setAttribute('content', csrfToken);
      }
    } catch { /* silently fail — next request will trigger reactive retry */ }
  };

  /** Proactive refresh every 50 minutes (buffer before 60 min expiry) */
  const CSRF_REFRESH_MS = 50 * 60 * 1000;
  setInterval(refreshCsrfToken, CSRF_REFRESH_MS);

  /**
   * POST helper that auto-includes the CSRF token.
   * If the server responds with 400 and the body mentions "CSRF",
   * the token is refreshed and the request is retried once automatically.
   */
  const apiPost = async (url, body, isRetry = false) => {
    const headers = { 'X-CSRFToken': csrfToken };
    const opts = { method: 'POST', headers };
    if (body instanceof FormData) {
      opts.body = body;
    } else {
      headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);
    if (res.status === 400 && !isRetry) {
      const cloned = res.clone();
      try {
        const text = await cloned.text();
        if (/csrf/i.test(text)) {
          await refreshCsrfToken();
          return apiPost(url, body, true);
        }
      } catch { /* ignore clone/parse errors */ }
    }
    return res;
  };

  // ─── TOAST SYSTEM ───
  const toastContainer = $('[data-toast-container]');
  const toast = (message, type = 'info', duration = 4000) => {
    if (!toastContainer) return;
    const icons = { success: '\u2713', error: '\u2715', warning: '\u26A0', info: '\u2139' };
    const el = document.createElement('div');
    el.className = `toast toast--${type}`;
    el.setAttribute('role', 'alert');
    const iconSpan = document.createElement('span');
    iconSpan.className = 'toast__icon';
    iconSpan.textContent = icons[type] || '\u2139';
    const msgSpan = document.createElement('span');
    msgSpan.className = 'toast__msg';
    msgSpan.textContent = message;
    const closeBtn = document.createElement('button');
    closeBtn.className = 'toast__close';
    closeBtn.setAttribute('aria-label', 'Dismiss');
    closeBtn.textContent = '\u00D7';
    closeBtn.addEventListener('click', () => el.remove());
    el.append(iconSpan, msgSpan, closeBtn);
    toastContainer.appendChild(el);
    requestAnimationFrame(() => el.classList.add('toast--visible'));
    setTimeout(() => { el.classList.remove('toast--visible'); setTimeout(() => el.remove(), 300); }, duration);
  };

  // ─── KEYBOARD SHORTCUTS ───
  const shortcutsPanel = $('[data-shortcuts-panel]');
  const SHORTCUTS = [
    { key: '?', label: 'Toggle this help' },
    { key: 'E', label: 'Focus resume text area' },
    { key: 'R', label: 'Run analysis' },
    { key: 'M', label: 'Toggle mode (Standard/Advanced)' },
    { key: 'C', label: 'Open comparison mode' },
    { key: 'Esc', label: 'Close modal / panel' },
  ];
  const renderShortcuts = () => {
    if (!shortcutsPanel) return;
    shortcutsPanel.innerHTML = `<div class="shortcuts__header"><strong>Keyboard Shortcuts</strong><button class="shortcuts__close" data-shortcuts-close aria-label="Close">&times;</button></div><div class="shortcuts__list">${SHORTCUTS.map(s => `<div class="shortcuts__row"><kbd>${s.key}</kbd><span>${s.label}</span></div>`).join('')}</div>`;
    shortcutsPanel.querySelector('[data-shortcuts-close]').addEventListener('click', () => shortcutsPanel.classList.remove('shortcuts--visible'));
  };

  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) {
      if (e.key === 'Escape') { closeModal(); closeComparison(); shortcutsPanel?.classList.remove('shortcuts--visible'); }
      return;
    }
    switch (e.key) {
      case '?': e.preventDefault(); shortcutsPanel?.classList.toggle('shortcuts--visible'); break;
      case 'E': case 'e': e.preventDefault(); $('[data-resume-text]')?.focus(); break;
      case 'R': case 'r': e.preventDefault(); $('[data-assess-button]')?.click(); break;
      case 'M': case 'm': e.preventDefault(); setMode({ standard: 'advanced', advanced: 'standard' }[activeMode] || 'standard'); break;
      case 'C': case 'c': e.preventDefault(); toggleComparison(); break;
      case 'Escape': closeModal(); closeComparison(); shortcutsPanel?.classList.remove('shortcuts--visible'); break;
    }
  });

  // ─── SW UPDATE ───
  const swUpdateBanner = $('[data-sw-update]');
  const swUpdateBtn = $('[data-sw-update-btn]');
  let swRegistration = null;
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/static/sw.js').then(reg => {
        swRegistration = reg;
        reg.addEventListener('updatefound', () => {
          const inst = reg.installing;
          inst?.addEventListener('statechange', () => {
            if (inst.state === 'installed' && navigator.serviceWorker.controller) {
              swUpdateBanner?.classList.remove('hidden');
              toast('A new version is available. Refresh to update.', 'info', 8000);
            }
          });
        });
      }).catch(() => {});
    });
    swUpdateBtn?.addEventListener('click', () => { swRegistration?.waiting?.postMessage({ type: 'SKIP_WAITING' }); window.location.reload(); });
    let refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => { if (!refreshing) { refreshing = true; window.location.reload(); } });
  }

  // ─── DARK MODE ───
  const themeToggle = $('[data-theme-toggle]');
  const themeModeLabel = $('[data-theme-mode-label]');
  const prefersDarkMedia = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  const isSystemDark = () => prefersDarkMedia?.matches || false;
  const MODE_CYCLE = ['auto', 'light', 'dark'];
  const MODE_LABELS = { auto: 'Auto', light: 'Light', dark: 'Dark' };
  let themeMode = load(STORAGE.theme, 'auto');
  if (!MODE_CYCLE.includes(themeMode)) themeMode = 'auto';
  const applyTheme = (mode) => { applyResolvedTheme(mode === 'auto' ? (isSystemDark() ? 'dark' : 'light') : mode); updateToggleUI(mode); };
  const applyResolvedTheme = (r) => html.setAttribute('data-theme', r);
  const updateToggleUI = (mode) => {
    themeToggle?.setAttribute('aria-label', `Theme: ${MODE_LABELS[mode]}. Click to cycle.`);
    if (themeModeLabel) themeModeLabel.textContent = MODE_LABELS[mode];
    $$('.theme-toggle-icon').forEach(icon => { icon.style.display = icon.getAttribute('data-icon') === mode ? 'inline' : 'none'; });
  };
  applyTheme(themeMode);
  if (themeModeLabel) themeModeLabel.textContent = MODE_LABELS[themeMode];
  themeToggle?.addEventListener('click', () => { themeMode = MODE_CYCLE[(MODE_CYCLE.indexOf(themeMode) + 1) % 3]; save(STORAGE.theme, themeMode); applyTheme(themeMode); });
  prefersDarkMedia?.addEventListener('change', () => { if (themeMode === 'auto') applyResolvedTheme(isSystemDark() ? 'dark' : 'light'); });

  // ─── PWA INSTALL ───
  let deferredPrompt = null;
  const installBanner = $('[data-pwa-install-banner]');
  const installButton = $('[data-pwa-install-button]');
  const dismissButton = $('[data-pwa-dismiss]');
  window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferredPrompt = e; if (installBanner && !load(STORAGE.pwaDismissed, null)) installBanner.classList.remove('hidden'); });
  installButton?.addEventListener('click', () => { deferredPrompt?.prompt(); deferredPrompt?.userChoice.then(() => { deferredPrompt = null; installBanner?.classList.add('hidden'); }); });
  dismissButton?.addEventListener('click', () => { installBanner?.classList.add('hidden'); save(STORAGE.pwaDismissed, '1'); });

  // ─── MOBILE MENU ───
  const mobileToggle = $('[data-mobile-menu]');
  const navLinks = $('[data-nav-links]');
  const navBackdrop = $('[data-nav-backdrop]');
  const navbar = $('.navbar');
  const closeMobileMenu = () => { navLinks?.classList.remove('is-open'); mobileToggle?.classList.remove('is-open'); mobileToggle?.setAttribute('aria-expanded', 'false'); navBackdrop?.classList.remove('is-visible'); navbar?.classList.remove('menu-open'); };
  mobileToggle?.addEventListener('click', () => { const o = navLinks?.classList.toggle('is-open'); mobileToggle?.classList.toggle('is-open'); mobileToggle?.setAttribute('aria-expanded', String(o)); navBackdrop?.classList.toggle('is-visible', o); navbar?.classList.toggle('menu-open', o); });
  navBackdrop?.addEventListener('click', closeMobileMenu);
  $$('.nav-link', navLinks).forEach(l => l.addEventListener('click', closeMobileMenu));

  renderShortcuts();

  // ==================================================================
  // ─── ANALYSIS APP ───
  // ==================================================================

  const form = $('[data-analysis-form]');
  const modeButtons = $$('[data-mode]');
  const modeInput = $('[data-mode-input]');
  const browseButton = $('[data-browse-button]');
  const fileInput = $('[data-file-input]');
  const dropZone = $('[data-drop-zone]');
  const submitButton = $('[data-assess-button]');
  const exportButton = $('[data-export-button]');
  const modal = $('[data-result-modal]');
  const modalTitle = $('[data-modal-title]');
  const modalRiskScore = $('[data-modal-risk-score]');
  const modalRiskLabel = $('[data-modal-risk-label]');
  const modalMode = $('[data-modal-mode]');
  const modalCloseButtons = $$('[data-modal-close]');
  const resultBanner = $('[data-result-banner]');
  const resultStatus = $('[data-result-status]');
  const narrative = $('[data-narrative]');
  const rolesList = $('[data-roles-list]');
  const roadmapList = $('[data-roadmap-list]');
  const riasecList = $('[data-riasec-list]');
  const uploadStatus = $('[data-upload-status]');
  const dashboardRiskRing = $('[data-risk-ring]');
  const dashboardRiskScore = $('[data-risk-score-display]');
  const dashboardRiskLabel = $('[data-risk-label-display]');
  const dashboardRiskSummary = $('[data-risk-summary]');
  const dashboardRoleStatus = $('[data-role-status]');
  const dashboardRoleBars = $('[data-role-bars]');
  const riskInsights = $('[data-risk-insights]');
  const nextStepsStatus = $('[data-next-steps-status]');
  const nextStepsLearning = $('[data-next-learning]');
  const nextStepsJobs = $('[data-next-jobs]');
  const nextStepsEducation = $('[data-next-education]');
  const nextStepsSupport = $('[data-next-support]');
  const modalNextSteps = $('[data-modal-next-steps]');
  const progressBar = $('[data-progress-bar]');
  const progressStatus = $('[data-progress-status]');
  const progressPercent = $('[data-progress-percent]');
  const comparePanel = $('[data-compare-panel]');
  const compareToggle = $('[data-compare-toggle]');
  const compareTextA = $('[data-compare-text-a]');
  const compareTextB = $('[data-compare-text-b]');
  const compareRun = $('[data-compare-run]');
  const compareResults = $('[data-compare-results]');
  const passwordInput = $('[data-password-input]');
  const strengthBar = $('[data-strength-bar]');
  const strengthLabel = $('[data-strength-label]');
  const pathButtons = $$('[data-path-option]');
  const pathTitle = $('[data-path-title]');
  const pathDescription = $('[data-path-description]');
  const pathActions = $('[data-path-actions]');
  const heroTitle = $('[data-hero-title]');
  const heroLead = $('[data-hero-lead]');
  const heroActions = $('[data-hero-actions]');
  const heroPrimaryLink = $('[data-hero-primary-link]');
  const analysisIntro = $('[data-analysis-intro]');

  if (!form || !submitButton) return;

  // ─── STATE ───
  let activeMode = load(STORAGE.mode, 'standard');
  let activePath = load(STORAGE.path, 'student');
  let selectedFile = null;
  let lastAnalysis = null;
  const originalSubmitLabel = submitButton.textContent.trim();

  // ─── PATHWAYS ───
  const P = {
    student: { h: 'Turn your student experience into a confident career launch plan.', l: 'Use your resume, projects, and coursework to identify roles and skill priorities.', ai: 'Upload your student resume or paste a profile summary.', pt: 'Student path selected', pd: 'Start with standard mode for fast role alignment.', a: ['Run standard analysis and review top three role matches.', 'Pick one roadmap course and schedule weekly blocks.', 'Update one project bullet with stronger keywords.'], c: ['Student-ready roles', 'Project-to-job translation', 'Interview preparation'], cta: 'Start student assessment' },
    'job-seeker': { h: 'Focus your job search with clearer role fit.', l: 'Identify roles where your profile aligns and prioritize application actions.', ai: 'Upload your resume for top role matches and automation risk.', pt: 'Job-seeker path selected', pd: 'Use role similarity and risk indicators to focus your search.', a: ['Track requirements across 10 recent job postings.', 'Tailor your resume to your top matched role.', 'Use one roadmap item to close a skill gap.'], c: ['Role match clarity', 'Resume optimization', 'Application focus'], cta: 'Start job-search assessment' },
    'career-switcher': { h: 'Plan your career transition with transferable skill mapping.', l: 'See where your background overlaps with target roles.', ai: 'Upload your resume to uncover transferable strengths.', pt: 'Career-switcher path selected', pd: 'Combine targeted roles with proof projects and short-cycle gains.', a: ['Pick two transferable skills from your strongest role match.', 'Build one portfolio proof item.', 'Commit to a 4\u20138 week transition plan.'], c: ['Transferable strengths', 'Transition roadmap', 'Targeted training'], cta: 'Start transition assessment' },
    'new-workforce': { h: 'Get a clear first-career direction.', l: 'Use your early experience to identify entry-level roles.', ai: 'Upload your resume for approachable role options.', pt: 'New-workforce path selected', pd: 'One role focus, one milestone, one weekly routine.', a: ['Choose one target role and build your resume around it.', 'Take one beginner-friendly roadmap course.', 'Apply to entry-level opportunities weekly.'], c: ['Entry-level pathways', 'Beginner support', 'First-job strategy'], cta: 'Start first-career assessment' },
  };

  // ─── HELPERS ───
  const describeFile = (f) => f ? `Selected file: ${f.name}` : 'No file selected yet.';
  const key = (r) => `${(r?.job_role || '').trim().toLowerCase()}::${(r?.industry || '').trim().toLowerCase()}`;
  const dedupeRoles = (roles) => {
    const m = new Map();
    (roles || []).forEach(r => { const k = key(r); const c = m.get(k); if (!c || (r.similarity || 0) > (c.similarity || 0)) m.set(k, r); });
    return Array.from(m.values()).sort((a, b) => (b.similarity || 0) - (a.similarity || 0));
  };
  const roleLinks = (role) => { const q = encodeURIComponent(role?.job_role || 'career'); return [{ label: 'Indeed', url: `https://www.indeed.com/jobs?q=${q}` }, { label: 'LinkedIn', url: `https://www.linkedin.com/jobs/search/?keywords=${q}` }, { label: 'Naukri', url: `https://www.naukri.com/${encodeURIComponent((role?.job_role || 'career').toLowerCase().replace(/\s+/g, '-'))}-jobs` }]; };
  const setUploadStatus = (m) => { if (uploadStatus) uploadStatus.textContent = m; };

  // ─── SSE PROGRESS BAR ───
  const updateProgress = (pct, status) => {
    if (progressBar) { progressBar.style.setProperty('--progress', `${Math.max(0, Math.min(100, pct))}%`); progressBar.classList.add('progress-bar--active'); }
    if (progressStatus) progressStatus.textContent = status || 'Processing...';
    if (progressPercent) progressPercent.textContent = `${pct}%`;
  };
  const hideProgress = () => { progressBar?.classList.remove('progress-bar--active'); if (progressStatus) progressStatus.textContent = ''; if (progressPercent) progressPercent.textContent = ''; };

  // ─── MODAL ───
  const openModal = () => { modal?.classList.remove('hidden'); modal?.classList.add('is-open'); modal?.setAttribute('aria-hidden', 'false'); };
  const closeModal = () => { modal?.classList.remove('is-open'); modal?.classList.add('hidden'); modal?.setAttribute('aria-hidden', 'true'); hideProgress(); };
  modalCloseButtons.forEach(b => b.addEventListener('click', closeModal));
  modal?.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

  // ─── SET MODE ───
  const setMode = (mode) => {
    activeMode = mode;
    if (modeInput) modeInput.value = mode;
    modeButtons.forEach(b => b.classList.toggle('is-active', b.dataset.mode === mode));
    save(STORAGE.mode, mode);
    [dashboardRiskRing, dashboardRiskScore, dashboardRiskLabel, dashboardRoleBars, resultBanner].forEach(el => { if (!el) return; el.classList.remove('motion-fade-up', 'motion-stagger-1', 'motion-stagger-2', 'motion-stagger-3'); void el.offsetWidth; el.classList.add('motion-fade-up'); });
  };

  // ─── BUSY ───
  const setBusy = (busy, message) => {
    submitButton.disabled = busy;
    if (browseButton) browseButton.disabled = busy;
    modeButtons.forEach(b => { b.disabled = busy; });
    submitButton.textContent = busy ? 'Analyzing...' : originalSubmitLabel;
    if (busy) {
      openModal();
      if (modalTitle) modalTitle.textContent = message || 'Analyzing...';
      if (modalMode) modalMode.textContent = `${activeMode === 'advanced' ? 'Advanced' : 'Standard'} mode`;
      if (modalRiskScore) modalRiskScore.textContent = 'Processing...';
      if (modalRiskLabel) modalRiskLabel.textContent = 'In progress';
      if (resultStatus) resultStatus.textContent = message || 'Analyzing...';
      if (narrative) narrative.textContent = 'Processing resume in memory...';
      if (dashboardRiskSummary) dashboardRiskSummary.textContent = 'Processing prediction...';
    }
  };

  // ─── RENDER HELPERS ───
  const renderList = (c, items, fn) => { if (c) c.innerHTML = (items || []).map(fn).join(''); };
  const simpleSteps = (c, items, heading) => {
    if (!c) return;
    const safe = (items || []).filter(Boolean);
    if (!safe.length) { c.innerHTML = '<div class="list-card"><div><strong>No actions yet</strong><p>Run analysis to generate next steps.</p></div></div>'; return; }
    c.innerHTML = safe.map(i => `<div class="list-card motion-fade-up"><div><strong>${heading}</strong><p>${i}</p></div></div>`).join('');
  };
  const fallbackSteps = (payload) => {
    const band = (payload.risk_label || 'Moderate').toLowerCase();
    const top = dedupeRoles(payload.top_roles || []).slice(0, 2);
    const road = payload.roadmap || [];
    const learn = road.slice(0, 3).map(i => `Start '${i.course}' and focus on ${i.skill || 'core skill'} this week.`);
    if (!learn.length) learn.push('Pick one high-impact skill gap and schedule three practice sessions.');
    const job = top.length ? [...top.map(r => `Save 10 postings for ${r.job_role} and track requirements.`), 'Update resume summary with matched role keywords.'] : ['Collect 10 postings and list repeated skills.', 'Tailor resume headline for one target role.'];
    const edu = [band === 'elevated' ? 'Prioritize digital and analytical skills.' : band === 'low' ? 'Deepen specialization.' : 'Build adjacent skills.', 'Compare certificates vs credentials.', 'Set a 4\u201312 week timeline.'];
    return { learning_actions: learn, job_search_actions: job, education_training_actions: edu, support_resources: ['Review methodology.', 'Review privacy.', 'Use advanced mode.'] };
  };
  const nextSteps = (payload) => {
    const g = payload.guided_next_steps || fallbackSteps(payload);
    simpleSteps(nextStepsLearning, g.learning_actions, 'Learning');
    simpleSteps(nextStepsJobs, g.job_search_actions, 'Job search');
    simpleSteps(nextStepsEducation, g.education_training_actions, 'Training');
    simpleSteps(nextStepsSupport, g.support_resources, 'Support');
    if (nextStepsStatus) nextStepsStatus.textContent = 'Updated';
    if (modalNextSteps) simpleSteps(modalNextSteps, [...(g.learning_actions || []).slice(0, 1), ...(g.job_search_actions || []).slice(0, 1), ...(g.education_training_actions || []).slice(0, 1)], 'Next');
  };

  // ─── PATHWAY ───
  const renderPathway = (k) => {
    const c = P[k] || P.student;
    activePath = k; save(STORAGE.path, k);
    if (heroTitle) heroTitle.textContent = c.h;
    if (heroLead) heroLead.textContent = c.l;
    if (analysisIntro) analysisIntro.textContent = c.ai;
    if (pathTitle) pathTitle.textContent = c.pt;
    if (pathDescription) pathDescription.textContent = c.pd;
    if (heroPrimaryLink) heroPrimaryLink.textContent = c.cta;
    if (heroActions) heroActions.innerHTML = (c.c || []).map(x => `<span class="chip">${x}</span>`).join('');
    if (pathActions) pathActions.innerHTML = (c.a || []).map(x => `<div class="list-card"><div><strong>Action</strong><p>${x}</p></div></div>`).join('');
    pathButtons.forEach(b => b.classList.toggle('is-active', b.dataset.pathOption === k));
  };

  // ─── DASHBOARD ───
  const resetStyles = () => { if (!resultBanner) return; resultBanner.style.background = ''; resultBanner.style.borderColor = ''; resultBanner.style.color = ''; };
  const updateDashboard = (payload) => {
    const roles = dedupeRoles(payload.top_roles || []);
    if (dashboardRiskRing) dashboardRiskRing.style.setProperty('--score', `${Math.max(0.05, Math.min(0.95, payload.risk_score || 0))}`);
    if (dashboardRiskScore) dashboardRiskScore.textContent = `${Math.round((payload.risk_score || 0) * 100)}%`;
    if (dashboardRiskLabel) dashboardRiskLabel.textContent = payload.risk_label ? `${payload.risk_label} risk` : 'Risk';
    if (dashboardRiskSummary) dashboardRiskSummary.textContent = payload.cognitive_career_narrative || 'Prediction ready.';
    if (dashboardRoleStatus) dashboardRoleStatus.textContent = roles.length ? 'Live' : 'No matches';
    if (dashboardRoleBars) dashboardRoleBars.innerHTML = roles.slice(0, 3).map((r, i) => `<div class="motion-fade-up motion-stagger-${Math.min(i + 1, 5)}"><div class="inline-actions" style="justify-content: space-between;"><strong>${r.job_role}</strong><strong class="muted">${Math.round((r.similarity || 0) * 100)}%</strong></div><div class="bar"><span style="width: ${Math.round((r.similarity || 0) * 100)}%;"></span></div><p class="small-note">${r.industry} \u00B7 Risk ${Math.round((r.risk_score || 0) * 100)}%</p></div>`).join('');
  };
  const renderReasoning = (payload) => {
    if (!riskInsights) return;
    const r = payload.reasoning || {};
    const cards = [];
    if (r.summary) cards.push(`<div class="list-card pivot-card"><div><strong>Why this score</strong><p>${r.summary}</p></div></div>`);
    (r.risk_drivers || []).forEach((d, i) => cards.push(`<div class="list-card"><div><strong>Risk driver ${i + 1}</strong><p>${d}</p></div></div>`));
    if (r.skills_detected?.length) cards.push(`<div class="list-card"><div><strong>Skills</strong><p>${r.skills_detected.join(', ')}</p></div></div>`);
    cards.push(`<div class="list-card"><div><strong>Confidence</strong><p>${r.confidence_note || 'Local feature trace.'}</p></div></div>`);
    riskInsights.innerHTML = cards.join('');
  };

  // ─── RENDER RESULTS ───
  const renderResults = (payload) => {
    lastAnalysis = payload;
    const roles = dedupeRoles(payload.top_roles || []);
    if (modalTitle) modalTitle.textContent = payload.mode === 'advanced' ? 'Deep AI narrative' : 'Analysis complete';
    if (modalRiskScore) modalRiskScore.textContent = `${Math.round((payload.risk_score || 0) * 100)}%`;
    if (modalRiskLabel) modalRiskLabel.textContent = payload.risk_label ? `${payload.risk_label} risk` : 'Risk';
    if (modalMode) modalMode.textContent = `${payload.mode === 'advanced' ? 'Advanced' : 'Standard'} mode`;
    if (resultStatus) resultStatus.textContent = payload.mode === 'advanced' ? 'Deep AI narrative' : 'Analysis complete';
    if (narrative) narrative.textContent = payload.cognitive_career_narrative || '';
    updateDashboard(payload);
    renderReasoning(payload);
    nextSteps(payload);
    renderList(rolesList, roles, (r) => { const l = roleLinks(r); return `<div class="list-card pivot-card"><div><strong>${r.job_role}</strong><p>${r.industry} \u00B7 Risk ${Math.round((r.risk_score || 0) * 100)}%</p><div class="pill-row">${l.map(x => `<a class="button-ghost" href="${x.url}" target="_blank" rel="noreferrer">${x.label}</a>`).join('')}</div></div><span class="status-pill">${Math.round((r.similarity || 0) * 100)}%</span></div>`; });
    renderList(roadmapList, payload.roadmap || [], (c) => `<div class="roadmap-item"><div><strong>${c.course}</strong><p>${c.skill} \u00B7 ${c.reason}</p></div>${c.url ? `<a class="button-ghost" href="${c.url}" target="_blank" rel="noreferrer">Open</a>` : ''}</div>`);
    renderList(riasecList, Object.entries(payload.riasec?.scores || {}), ([n, s]) => `<div class="list-card"><div><strong>${n}</strong></div><span class="status-pill">${s}</span></div>`);
    toast('Analysis complete!', 'success');
  };

  const renderError = (msg) => {
    hideProgress();
    openModal();
    if (resultBanner) { resultBanner.style.background = 'rgba(186,26,26,0.08)'; resultBanner.style.borderColor = 'rgba(186,26,26,0.35)'; resultBanner.style.color = 'var(--error)'; }
    if (modalTitle) modalTitle.textContent = 'Could not complete';
    if (modalRiskScore) modalRiskScore.textContent = '--';
    if (modalRiskLabel) modalRiskLabel.textContent = 'Error';
    if (modalMode) modalMode.textContent = `${activeMode === 'advanced' ? 'Advanced' : 'Standard'}`;
    if (resultStatus) resultStatus.textContent = 'Could not complete';
    if (narrative) narrative.textContent = msg;
    if (rolesList) rolesList.innerHTML = '';
    if (roadmapList) roadmapList.innerHTML = '';
    if (riasecList) riasecList.innerHTML = '';
    if (dashboardRiskSummary) dashboardRiskSummary.textContent = msg;
    if (dashboardRoleStatus) dashboardRoleStatus.textContent = 'Error';
    if (riskInsights) riskInsights.innerHTML = `<div class="list-card"><div><strong>Unavailable</strong><p>${msg}</p></div></div>`;
    if (nextStepsStatus) nextStepsStatus.textContent = 'Unavailable';
    [nextStepsLearning, nextStepsJobs, nextStepsEducation, nextStepsSupport, modalNextSteps].forEach(c => { if (c) c.innerHTML = `<div class="list-card"><div><strong>Unavailable</strong><p>${msg}</p></div></div>`; });
    toast(msg, 'error', 6000);
  };

  // ─── SSE STREAMING ───
  const streamAnalysis = async (text) => {
    const url = `/api/analyze-stream?text=${encodeURIComponent(text)}&mode=${activeMode}`;
    if (text.length > 1800) {
      // URL too long, fallback to POST
      const fd = new FormData();
      fd.set('resume_text', text);
      fd.set('mode', activeMode);
      return submitStandard(fd);
    }
    setBusy(true, `Running ${activeMode} analysis...`);
    updateProgress(0, 'Starting...');
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to start streaming');
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const d = JSON.parse(line.slice(6));
            if (d.step === 'error') throw new Error(d.data?.error || 'Analysis failed');
            if (d.percent >= 0) updateProgress(d.percent, d.status);
            if (d.step === 'complete' && d.data) { resetStyles(); renderResults(d.data); setBusy(false); return d.data; }
          } catch (e) { if (e.message === 'Analysis failed') throw e; }
        }
      }
      throw new Error('Stream ended without completion');
    } catch (error) {
      renderError(error.message || 'Analysis failed.');
      setBusy(false);
      throw error;
    }
  };

  // ─── SUBMIT ───
  const submitStandard = async (formData) => {
    setBusy(true, `Running ${activeMode} analysis...`);
    try {
      const res = await apiPost('/api/upload', formData);
      const p = await res.json();
      if (!res.ok || !p.success) throw new Error(p.error || 'Analysis failed.');
      resetStyles();
      renderResults(p);
    } catch (error) {
      renderError(error.message || 'Analysis failed.');
    } finally { setBusy(false); }
  };

  // ─── EVENT BINDINGS ───
  modeButtons.forEach(b => b.addEventListener('click', () => setMode(b.dataset.mode)));
  pathButtons.forEach(b => b.addEventListener('click', () => renderPathway(b.dataset.pathOption || 'student')));
  browseButton?.addEventListener('click', () => fileInput?.click());
  fileInput?.addEventListener('change', () => { selectedFile = fileInput.files?.[0] || null; setUploadStatus(describeFile(selectedFile)); dropZone?.classList.remove('is-dropped'); if (selectedFile) toast(`File: ${selectedFile.name}`, 'info', 3000); });

  if (dropZone) {
    ['dragenter', 'dragover'].forEach(e => dropZone.addEventListener(e, ev => { ev.preventDefault(); dropZone.classList.add('is-dragover'); }));
    ['dragleave', 'drop'].forEach(e => dropZone.addEventListener(e, ev => { ev.preventDefault(); dropZone.classList.remove('is-dragover'); }));
    dropZone.addEventListener('drop', ev => {
      const f = ev.dataTransfer?.files?.[0]; if (!f) return;
      const dt = new DataTransfer(); dt.items.add(f); fileInput.files = dt.files;
      selectedFile = f; setUploadStatus(describeFile(selectedFile));
      dropZone.classList.add('is-dropped'); setTimeout(() => dropZone.classList.remove('is-dropped'), 700);
      toast(`Dropped: ${f.name}`, 'info', 3000);
    });
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    if (selectedFile && !fd.get('resume_file')) fd.set('resume_file', selectedFile);
    fd.set('mode', activeMode);
    const text = (fd.get('resume_text') || '').toString().trim();
    if (!(fileInput?.files?.length > 0) && !text) { renderError('Add resume text or a file.'); return; }
    if (activeMode === 'advanced' && text) await streamAnalysis(text);
    else await submitStandard(fd);
  });

  // ─── EXPORT ───
  exportButton?.addEventListener('click', async () => {
    if (!lastAnalysis) { toast('Run analysis first.', 'warning'); return; }
    try {
      const res = await apiPost('/api/export', { analysis: lastAnalysis });
      const d = await res.json();
      if (!d.success) throw new Error(d.error);
      const w = window.open('', '_blank'); w.document.write(d.html); w.document.close(); w.print();
      toast('Report opened for printing.', 'success');
    } catch (err) { toast('Export: ' + err.message, 'error'); }
  });

  // ─── PASSWORD STRENGTH ───
  let pwTimer = null;
  passwordInput?.addEventListener('input', () => {
    clearTimeout(pwTimer);
    const pw = passwordInput.value;
    if (!pw) { if (strengthBar) { strengthBar.style.setProperty('--pw-width', '0%'); strengthBar.style.setProperty('--pw-color', 'var(--error)'); } if (strengthLabel) strengthLabel.textContent = ''; return; }
    pwTimer = setTimeout(async () => {
      try {
        const res = await apiPost('/api/check-password', { password: pw });
        const d = await res.json();
        if (strengthBar) { strengthBar.style.setProperty('--pw-width', d.width); strengthBar.style.setProperty('--pw-color', d.color); }
        if (strengthLabel) { strengthLabel.textContent = d.label; strengthLabel.style.color = d.color; }
      } catch {}
    }, 300);
  });

  // ─── COMPARISON ───
  const toggleComparison = () => {
    if (!comparePanel) return;
    comparePanel.classList.toggle('compare-panel--visible');
    if (comparePanel.classList.contains('compare-panel--visible')) compareToggle?.classList.add('is-active');
    else { compareToggle?.classList.remove('is-active'); compareResults?.classList.add('hidden'); }
  };
  const closeComparison = () => { comparePanel?.classList.remove('compare-panel--visible'); compareToggle?.classList.remove('is-active'); compareResults?.classList.add('hidden'); };
  compareToggle?.addEventListener('click', toggleComparison);
  compareRun?.addEventListener('click', async () => {
    const a = compareTextA?.value.trim(); const b = compareTextB?.value.trim();
    if (!a || !b) { toast('Both texts required.', 'warning'); return; }
    compareRun.disabled = true; compareRun.textContent = 'Comparing...';
    compareResults?.classList.add('hidden');
    try {
      const res = await apiPost('/api/compare', { text_a: a, text_b: b, mode: activeMode });
      const d = await res.json();
      if (!d.success) throw new Error(d.error);
      if (compareResults) {
        compareResults.innerHTML = `<div class="compare-result-grid"><div class="compare-col"><h4>A</h4><div class="kpi"><div class="kpi__label">Risk</div><div class="kpi__value">${Math.round(d.risk_a * 100)}%</div></div><div class="kpi"><div class="kpi__label">Band</div><div class="kpi__value">${d.label_a}</div></div></div><div class="compare-vs"><span>VS</span><div class="compare-delta">\u0394 ${Math.round(d.risk_delta * 100)}%</div></div><div class="compare-col"><h4>B</h4><div class="kpi"><div class="kpi__label">Risk</div><div class="kpi__value">${Math.round(d.risk_b * 100)}%</div></div><div class="kpi"><div class="kpi__label">Band</div><div class="kpi__value">${d.label_b}</div></div></div></div>`;
        compareResults.classList.remove('hidden');
      }
      toast('Comparison complete!', 'success');
    } catch (err) { toast('Compare: ' + err.message, 'error'); }
    finally { compareRun.disabled = false; compareRun.textContent = 'Compare'; }
  });

  // ─── INIT ───
  setMode(activeMode);
  renderPathway(activePath);

  // ─── SCROLL REVEAL ───
  const REVEAL_SEL = '.feature-card, .insight-card, .method-card, .form-card, .section-card, .glass-card, .privacy-card, .contact-card, .dashboard-grid > div, .page-hero__grid > div, .hero__grid > div, .hero__grid > .hero-panel';
  const initReveal = () => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const dirs = ['', '', '', '--left', '--right', '--scale'];
    document.querySelectorAll(REVEAL_SEL).forEach(el => { if (el.closest('.result-modal')) return; el.classList.add('reveal' + dirs[Math.floor(Math.random() * dirs.length)]); });
    const obs = new IntersectionObserver(entries => { entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('is-visible'); obs.unobserve(e.target); } }); }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    document.querySelectorAll('.reveal').forEach(el => obs.observe(el));
  };
  const initStagger = () => { document.querySelectorAll('.feature-grid, .insight-grid, .method-grid, .partnership-grid, .dashboard-grid, .hero__grid, .page-hero__grid').forEach(g => { g.querySelectorAll(':scope > .reveal').forEach((c, i) => c.classList.add('reveal--stagger-' + ((i % 5) + 1))); }); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => { initReveal(); initStagger(); });
  else { initReveal(); initStagger(); }

  // ─── SKILLS GAP ANALYSIS ───
  const skillsGapSection = document.getElementById('skills-gap-section');
  const skillsGapRole = document.getElementById('skills-gap-role');
  const skillsGapForm = document.getElementById('skills-gap-form');
  const skillsGapButton = document.getElementById('skills-gap-submit');
  const skillsGapResults = document.getElementById('skills-gap-results');
  const skillsGapLoading = document.getElementById('skills-gap-loading');
  const skillsGapError = document.getElementById('skills-gap-error');

  // Populate roles dropdown on load
  if (skillsGapRole) {
    fetch('/api/skills-gap/roles')
      .then(r => r.json())
      .then(data => {
        if (data.success && data.roles) {
          data.roles.forEach(role => {
            const opt = document.createElement('option');
            opt.value = role;
            opt.textContent = role;
            skillsGapRole.appendChild(opt);
          });
        }
      })
      .catch(() => {});
  }

  // Handle skill gap form submission
  if (skillsGapForm) {
    skillsGapForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const resumeTextEl = document.querySelector('[data-resume-text]');
      const resumeText = resumeTextEl ? resumeTextEl.value.trim() : '';
      const targetRole = skillsGapRole ? skillsGapRole.value : '';

      if (!resumeText || resumeText.length < 20) {
        toast('Please enter resume text first (min 20 characters).', 'warning');
        return;
      }
      if (!targetRole) {
        toast('Please select a target role.', 'warning');
        return;
      }

      if (skillsGapButton) skillsGapButton.disabled = true;
      if (skillsGapButton) skillsGapButton.textContent = 'Analyzing...';
      if (skillsGapLoading) skillsGapLoading.classList.remove('hidden');
      if (skillsGapResults) skillsGapResults.classList.add('hidden');
      if (skillsGapError) skillsGapError.classList.add('hidden');

      try {
        const res = await apiPost('/api/skills-gap/analyze', {
          resume_text: resumeText,
          target_role: targetRole
        });
        const data = await res.json();

        if (!data.success) {
          throw new Error(data.error || 'Analysis failed.');
        }

        renderSkillsGap(data.analysis);
      } catch (err) {
        if (skillsGapError) {
          skillsGapError.textContent = err.message || 'Failed to analyze skills gap.';
          skillsGapError.classList.remove('hidden');
        }
        toast(err.message || 'Analysis failed.', 'error');
      } finally {
        if (skillsGapButton) skillsGapButton.disabled = false;
        if (skillsGapButton) skillsGapButton.textContent = 'Analyze Skills Gap';
        if (skillsGapLoading) skillsGapLoading.classList.add('hidden');
      }
    });
  }

  // Render skills gap results
  function renderSkillsGap(analysis) {
    if (!skillsGapResults) return;
    
    const matchPct = analysis.match_percentage || 0;
    const matchColor = matchPct >= 70 ? '#22c55e' : matchPct >= 40 ? '#eab308' : '#ef4444';
    const matchLabel = matchPct >= 70 ? 'Strong Match' : matchPct >= 40 ? 'Partial Match' : 'Low Match';

    skillsGapResults.innerHTML = `
      <div class="skills-gap-result">
        <div class="skills-gap-header">
          <div>
            <h3 class="section-title">Skills Gap Analysis: ${analysis.target_role}</h3>
            <p class="section-subtitle">Comparing your resume against ${analysis.total_required} required skills</p>
          </div>
          <div class="skills-gap-score" style="text-align:center;">
            <div class="skills-gap-ring" style="--pct: ${matchPct}%; --color: ${matchColor};">
              <span class="skills-gap-ring__value">${matchPct}%</span>
            </div>
            <span style="font-size:0.78rem;font-weight:600;color:${matchColor};">${matchLabel}</span>
          </div>
        </div>

        <div class="skills-gap-grid">
          <div class="list-card" style="border-color: #22c55e44;">
            <div>
              <strong style="color:#22c55e;">✅ Matched Skills (${analysis.matched_count})</strong>
              ${analysis.matched_skills.length ? analysis.matched_skills.map(s => `<span class="chip" style="background:#22c55e22;color:#22c55e;margin:2px 4px 2px 0;">${s}</span>`).join('') : '<p style="color:var(--text-muted);margin-top:0.5rem;">No direct skill matches found.</p>'}
            </div>
          </div>
          <div class="list-card" style="border-color: #ef444444;">
            <div>
              <strong style="color:#ef4444;">❌ Missing Skills (${analysis.missing_count})</strong>
              ${analysis.missing_skills.length ? analysis.missing_skills.map(s => `<span class="chip" style="background:#ef444422;color:#ef4444;margin:2px 4px 2px 0;">${s}</span>`).join('') : '<p style="color:var(--text-muted);margin-top:0.5rem;">No missing skills — you\'re fully qualified!</p>'}
            </div>
          </div>
        </div>

        ${analysis.recommendations && analysis.recommendations.length ? `
          <div class="skills-gap-recommendations" style="margin-top:1.5rem;">
            <h4 class="section-title" style="font-size:1.1rem;">📚 Learning Recommendations</h4>
            <div class="skills-gap-recs-grid" style="display:grid;gap:0.75rem;margin-top:0.75rem;">
              ${analysis.recommendations.map(r => `
                <div class="list-card motion-fade-up">
                  <div>
                    <strong>${r.skill}</strong>
                    <span class="status-pill ${r.priority === 'High' ? 'is-danger' : 'is-warm'}" style="margin-left:0.5rem;">${r.priority}</span>
                    <ul style="margin:0.5rem 0 0;padding-left:1.25rem;color:var(--text-muted);font-size:0.85rem;">
                      ${r.resources.map(res => `<li style="margin-bottom:0.25rem;">${res}</li>`).join('')}
                    </ul>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}
      </div>
    `;
    skillsGapResults.classList.remove('hidden');
    toast('Skills gap analysis complete!', 'success');
  }

  console.log('Prayash UI ready');
  toast('Prayash ready. Press <strong>?</strong> for shortcuts.', 'info', 5000);
})();
