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
    lastAnalysis: 'prayash-last-analysis',   // last analysis result (no resume text)
    lastScore: 'prayash-last-score',         // last resume-strength score payload
    lastFilters: 'prayash-jm-filters',       // job-dashboard filter state
    resumesAnalyzed: 'prayash-resumes-analyzed', // device-local analyzed counter
    history: 'prayash-analysis-history',         // recent analysis summaries (never the resume text)
    sidebarCollapsed: 'prayash-sidebar-collapsed', // workspace sidebar collapse preference
    lastPage: 'prayash-last-page',               // last visited workspace page
    startPage: 'prayash-start-page',             // Settings: startup page preference
    density: 'prayash-card-density',             // Settings: comfortable / compact
    anim: 'prayash-anim',                        // Settings: animations on / reduced
    toastDuration: 'prayash-toast-duration',     // Settings: toast display time
  };
  const load = (key, fb) => { try { return localStorage.getItem(key) || fb; } catch { return fb; } };
  const save = (key, v) => { try { localStorage.setItem(key, v); } catch {} };
  /** JSON variants that never throw on malformed/corrupted values. */
  const loadJSON = (key, fb) => { try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : fb; } catch { return fb; } };
  const saveJSON = (key, v) => { try { localStorage.setItem(key, JSON.stringify(v)); } catch {} };

  // ─── DOM REFS & CSRF ───
  const $ = (s, p) => (p || document).querySelector(s);
  const $$ = (s, p) => Array.from((p || document).querySelectorAll(s));
  /** Escape user/API-controlled strings before inserting them via innerHTML. */
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
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
    // Toast duration preference (Settings). Explicit non-default durations
    // (e.g. the 6 s error toast) always win over the preference.
    const effectiveDuration = duration === 4000
      ? (Number(load(STORAGE.toastDuration, '4000')) || 4000)
      : duration;
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
    setTimeout(() => { el.classList.remove('toast--visible'); setTimeout(() => el.remove(), 300); }, effectiveDuration);
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
  prefersDarkMedia?.addEventListener('change', () => { if (themeMode === 'auto') { applyResolvedTheme(isSystemDark() ? 'dark' : 'light'); syncWpThemeIcon(); } });

  // ─── DISPLAY PREFERENCES (Settings) ───
  // Applied at boot so the chosen density/animation mode is active before the
  // first render. Scoped to html[data-*] attributes consumed by styles.css.
  (function applyDisplayPrefs() {
    if (load(STORAGE.density, 'comfortable') === 'compact') html.setAttribute('data-density', 'compact');
    if (load(STORAGE.anim, 'on') === 'off') html.setAttribute('data-anim', 'off');
  })();

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
  const navRight = $('[data-nav-right]');
  const navBackdrop = $('[data-nav-backdrop]');
  const navbar = $('.navbar');
  const closeMobileMenu = () => { navLinks?.classList.remove('is-open'); navRight?.classList.remove('is-open'); mobileToggle?.classList.remove('is-open'); mobileToggle?.setAttribute('aria-expanded', 'false'); navBackdrop?.classList.remove('is-visible'); navbar?.classList.remove('menu-open'); };
  mobileToggle?.addEventListener('click', () => { const o = navLinks?.classList.toggle('is-open'); navRight?.classList.toggle('is-open', o); mobileToggle?.classList.toggle('is-open'); mobileToggle?.setAttribute('aria-expanded', String(o)); navBackdrop?.classList.toggle('is-visible', o); navbar?.classList.toggle('menu-open', o); });
  navBackdrop?.addEventListener('click', closeMobileMenu);
  $$('.nav-link', navLinks).forEach(l => l.addEventListener('click', closeMobileMenu));

  // ─── USER MENU (signed-in account dropdown) ───
  const userMenu = $('[data-user-menu]');
  const userMenuToggle = $('[data-user-menu-toggle]');
  const closeUserMenu = () => {
    userMenu?.classList.remove('is-open');
    userMenuToggle?.setAttribute('aria-expanded', 'false');
  };
  userMenuToggle?.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = userMenu.classList.toggle('is-open');
    userMenuToggle.setAttribute('aria-expanded', String(open));
  });
  document.addEventListener('click', (e) => {
    if (userMenu && !userMenu.contains(e.target)) closeUserMenu();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeUserMenu();
  });

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
  // Legacy pathway text hooks. The current home-page hero has no data-hero-*
  // elements (its copy is static), so these safely no-op there.
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
  let restoringState = false; // true while re-hydrating the dashboard from localStorage
  const originalSubmitLabel = submitButton.textContent.trim();

  // ─── PATHWAYS ───
  const P = {
    student: { h: 'Turn your student experience into a confident career launch plan.', l: 'Use your resume, projects, and coursework to identify roles and skill priorities.', ai: 'Upload your student resume or paste a profile summary.', pt: 'Student path selected', pd: 'Start with standard mode for fast role alignment.', a: ['Run standard analysis and review top three role matches.', 'Pick one roadmap course and schedule weekly blocks.', 'Update one project bullet with stronger keywords.'], c: ['Student-ready roles', 'Project-to-job translation', 'Interview preparation'], cta: 'Start student assessment' },
    'job-seeker': { h: 'Focus your job search with clearer role fit.', l: 'Identify roles where your profile aligns and prioritize application actions.', ai: 'Upload your resume for top role matches and automation risk.', pt: 'Job-seeker path selected', pd: 'Use role similarity and risk indicators to focus your search.', a: ['Track requirements across 10 recent job postings.', 'Tailor your resume to your top matched role.', 'Use one roadmap item to close a skill gap.'], c: ['Role match clarity', 'Resume optimization', 'Application focus'], cta: 'Start job-search assessment' },
    'career-switcher': { h: 'Plan your career transition with transferable skill mapping.', l: 'See where your background overlaps with target roles.', ai: 'Upload your resume to uncover transferable strengths.', pt: 'Career-switcher path selected', pd: 'Combine targeted roles with proof projects and short-cycle gains.', a: ['Pick two transferable skills from your strongest role match.', 'Build one portfolio proof item.', 'Commit to a 4\u20138 week transition plan.'], c: ['Transferable strengths', 'Transition roadmap', 'Targeted training'], cta: 'Start transition assessment' },
    'new-workforce': { h: 'Get a clear first-career direction.', l: 'Use your early experience to identify entry-level roles.', ai: 'Upload your resume for approachable role options.', pt: 'New-workforce path selected', pd: 'One role focus, one milestone, one weekly routine.', a: ['Choose one target role and build your resume around it.', 'Take one beginner-friendly roadmap course.', 'Apply to entry-level opportunities weekly.'], c: ['Entry-level pathways', 'Beginner support', 'First-job strategy'], cta: 'Start first-career assessment' },
  };

  // ─── HELPERS ───
  const describeFile = (f) => f
    ? `Selected: ${f.name} (${Math.max(1, Math.round(f.size / 1024))} KB · ${fileKindLabel(f)})`
    : 'No file selected yet.';
  const fileKindLabel = (f) => {
    const ext = (f.name.split('.').pop() || '').toUpperCase();
    if (ext === 'PDF') return 'PDF document';
    if (ext === 'DOCX') return 'Word document';
    if (ext === 'TXT' || (f.type || '').startsWith('text/')) return 'Plain text';
    return f.type || 'Unknown type';
  };
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
    if (pathActions) pathActions.innerHTML = (c.a || []).map(x => `<div class="list-card"><div><strong>Action</strong><p>${esc(x)}</p></div></div>`).join('');
    pathButtons.forEach(b => b.classList.toggle('is-active', b.dataset.pathOption === k));
    renderCareerPathFlowchart(k);
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
    if (dashboardRoleBars) dashboardRoleBars.innerHTML = roles.slice(0, 3).map((r, i) => `<div class="motion-fade-up motion-stagger-${Math.min(i + 1, 5)}"><div class="inline-actions" style="justify-content: space-between;"><strong>${esc(r.job_role)}</strong><strong class="muted">${Math.round((r.similarity || 0) * 100)}%</strong></div><div class="bar"><span style="width: ${Math.round((r.similarity || 0) * 100)}%;"></span></div><p class="small-note">${esc(r.industry)} \u00B7 Risk ${Math.round((r.risk_score || 0) * 100)}%</p></div>`).join('');
  };
  const renderReasoning = (payload) => {
    if (!riskInsights) return;
    const r = payload.reasoning || {};
    const cards = [];
    if (r.summary) cards.push(`<div class="list-card pivot-card"><div><strong>Why this score</strong><p>${esc(r.summary)}</p></div></div>`);
    (r.risk_drivers || []).forEach((d, i) => cards.push(`<div class="list-card"><div><strong>Risk driver ${i + 1}</strong><p>${esc(d)}</p></div></div>`));
    if (r.skills_detected?.length) cards.push(`<div class="list-card"><div><strong>Skills</strong><p>${r.skills_detected.map(esc).join(', ')}</p></div></div>`);
    cards.push(`<div class="list-card"><div><strong>Confidence</strong><p>${esc(r.confidence_note || 'Local feature trace.')}</p></div></div>`);
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
    renderReportReskilling(payload); // Reports page: reskilling summary panel
    renderList(rolesList, roles, (r) => { const l = roleLinks(r); const role = esc(r.job_role); return `<div class="list-card pivot-card"><div><strong>${role}</strong><p>${esc(r.industry)} \u00B7 Risk ${Math.round((r.risk_score || 0) * 100)}%</p><div class="pill-row">${l.map(x => `<a class="button-ghost" href="${x.url}" target="_blank" rel="noreferrer">${x.label}</a>`).join('')}</div></div><span class="status-pill">${Math.round((r.similarity || 0) * 100)}%</span></div>`; });
    renderList(roadmapList, payload.roadmap || [], (c) => `<div class="roadmap-item"><div><strong>${esc(c.course)}</strong><p>${esc(c.skill)} \u00B7 ${esc(c.reason)}</p></div>${c.url ? `<a class="button-ghost" href="${c.url}" target="_blank" rel="noreferrer">Open</a>` : ''}</div>`);
    renderList(riasecList, Object.entries((payload.riasec && payload.riasec.scores) || {}), ([n, s]) => `<div class="list-card"><div><strong>${esc(n)}</strong></div><span class="status-pill">${esc(s)}</span></div>`);
    updateResumeScoreUI(payload); // animated Resume Strength meter (0→100)
    updateDashboardUI(jobsFromAnalysis(payload)); // job match dashboard cards
    updateRiskMeterFromPayload(payload); // career risk meter gauge
    updateSkillVisualization(payload); // skill bars
    updateAtsChecker(payload); // ATS compatibility checks
    renderRiskCards(payload); // workplace KPI cards
    renderPieCharts(payload); // workplace pie charts
    renderSkillGapChart(payload); // workplace skill gap chart
    renderStatistics(payload); // workplace statistics
    renderRiskGauge(payload); // workplace circular risk gauge
    renderReskillingMini(payload); // dashboard mini-roadmap (real roadmap data only)
    if (restoringState) {
      persistAnalysisState(payload, false); // re-save snapshot without counting a new analysis
    } else {
      persistAnalysisState(payload, true); // save reusable dashboard state (never the resume text)
      toast('Analysis complete!', 'success');
    }
    renderHistory(); // Analysis History page rows (summary only, no resume text)
  };

  /**
   * Persist a compact, privacy-safe snapshot of the analysis so the dashboard
   * restores after a refresh. The resume text itself is never stored.
   */  function persistAnalysisState(payload, countAsNew = true) {
    const roles = dedupeRoles(payload.top_roles || []);
    const snapshot = {      saved_at: new Date().toISOString(),      mode: payload.mode || activeMode,      risk_score: payload.risk_score || 0,      risk_label: payload.risk_label || '',      narrative: payload.cognitive_career_narrative || '',      reasoning: payload.reasoning || {},      top_roles: roles.slice(0, 8),      roadmap: (payload.roadmap || []).slice(0, 6),      riasec: payload.riasec || {},      guided_next_steps: payload.guided_next_steps || {},
      resumes_analyzed: countAsNew ? (Number(load(STORAGE.resumesAnalyzed, '0')) || 0) + 1 : (Number(load(STORAGE.resumesAnalyzed, '0')) || 0),
    };    saveJSON(STORAGE.lastAnalysis, snapshot);
    save(STORAGE.resumesAnalyzed, String(snapshot.resumes_analyzed));
    saveJSON(STORAGE.lastFilters, jmState);
    // Record a history entry only for genuinely new analyses (not re-saves
    // during state restore) so a page refresh never duplicates rows.
    if (countAsNew) {
      try {
        const hist = loadJSON(STORAGE.history, []);
        if (Array.isArray(hist)) {
          hist.unshift({
            saved_at: snapshot.saved_at,
            mode: snapshot.mode,
            risk_score: snapshot.risk_score,
            risk_label: snapshot.risk_label,
            skills: ((snapshot.reasoning || {}).skills_detected || []).length,
            roles: snapshot.top_roles.map((r) => ({ title: r.job_role, similarity: r.similarity, risk_score: r.risk_score })).slice(0, 3),
          });
          saveJSON(STORAGE.history, hist.slice(0, 10)); // keep the 10 most recent
        }
      } catch { /* history is best-effort */ }
    }
  }

  const renderError = (msg) => {
    hideProgress();
    openModal();
    const safeMsg = String(msg || 'Analysis failed.');
    if (resultBanner) { resultBanner.style.background = 'rgba(186,26,26,0.08)'; resultBanner.style.borderColor = 'rgba(186,26,26,0.35)'; resultBanner.style.color = 'var(--error)'; }
    if (modalTitle) modalTitle.textContent = 'Could not complete';
    if (modalRiskScore) modalRiskScore.textContent = '--';
    if (modalRiskLabel) modalRiskLabel.textContent = 'Error';
    if (modalMode) modalMode.textContent = `${activeMode === 'advanced' ? 'Advanced' : 'Standard'}`;
    if (resultStatus) resultStatus.textContent = 'Could not complete';
    if (narrative) narrative.textContent = safeMsg;
    if (rolesList) rolesList.innerHTML = '';
    if (roadmapList) roadmapList.innerHTML = '';
    if (riasecList) riasecList.innerHTML = '';
    if (dashboardRiskSummary) dashboardRiskSummary.textContent = safeMsg;
    if (dashboardRoleStatus) dashboardRoleStatus.textContent = 'Error';
    if (riskInsights) riskInsights.innerHTML = `<div class="list-card"><div><strong>Unavailable</strong><p>${esc(safeMsg)}</p></div></div>`;
    if (nextStepsStatus) nextStepsStatus.textContent = 'Unavailable';
    [nextStepsLearning, nextStepsJobs, nextStepsEducation, nextStepsSupport, modalNextSteps].forEach(c => { if (c) c.innerHTML = `<div class="list-card"><div><strong>Unavailable</strong><p>${esc(safeMsg)}</p></div></div>`; });
    toast(safeMsg, 'error', 6000);
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
          } catch (e) {
            // Parse errors on non-error frames are skipped; real failures rethrow
            if (e.message === 'Analysis failed' || (e instanceof SyntaxError) === false) throw e;
          }
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
  // ─── FILE VALIDATION (rule #9) ───
  // Single validator used by BOTH the Browse and drag-drop paths so a dropped
  // file behaves exactly like a browsed one. Extension checked against the
  // backend-supported set; size against config MAX_UPLOAD_SIZE (20 MB).
  const MAX_RESUME_BYTES = 20 * 1024 * 1024; // 20 MB — matches backend MAX_CONTENT_LENGTH
  const acceptResumeFile = (file) => {
    if (!file) return null;
    if (!ALLOWED_EXT.test(file.name)) {
      toast('Unsupported resume format.', 'warning');
      return null;
    }
    if (file.size > MAX_RESUME_BYTES) {
      toast('File is too large. Maximum size is 20 MB.', 'warning');
      return null;
    }
    return file;
  };

  /** Clear the selected resume (Remove file action) and reset the input. */
  const clearSelectedFile = () => {
    selectedFile = null;
    if (fileInput) fileInput.value = '';
    setUploadStatus('No file selected yet.');
    resumePreview?.classList.add('hidden');
    toast('Resume removed.', 'info', 2500);
  };

  // Remove-file buttons (workspace upload panel): unhide when a file is chosen.
  // syncRemoveFileButtons() is invoked at the END of the change/drop handlers
  // below, after selectedFile is updated, so visibility never lags a beat.
  const removeFileButtons = $$('[data-remove-file]');
  const syncRemoveFileButtons = () => {
    removeFileButtons.forEach((b) => { b.hidden = !selectedFile; });
  };
  removeFileButtons.forEach((b) => b.addEventListener('click', () => { clearSelectedFile(); syncRemoveFileButtons(); }));

  browseButton?.addEventListener('click', () => fileInput?.click());
  fileInput?.addEventListener('change', () => {
    selectedFile = acceptResumeFile(fileInput.files?.[0] || null);
    if (!selectedFile && fileInput) fileInput.value = ''; // rejected file must not linger in the input
    setUploadStatus(describeFile(selectedFile));
    dropZone?.classList.remove('is-dropped');
    if (selectedFile) {
      toast(`Resume selected: ${selectedFile.name}`, 'info', 3000);
      showResumePreview(selectedFile); // file preview viewer (metadata + TXT content)
    }
    syncRemoveFileButtons();
  });

  if (dropZone) {
    ['dragenter', 'dragover'].forEach(e => dropZone.addEventListener(e, ev => { ev.preventDefault(); dropZone.classList.add('is-dragover'); }));
    ['dragleave', 'drop'].forEach(e => dropZone.addEventListener(e, ev => { ev.preventDefault(); dropZone.classList.remove('is-dragover'); }));
    dropZone.addEventListener('drop', ev => {
      const f = acceptResumeFile(ev.dataTransfer?.files?.[0]);
      if (!f) return; // validator already toasted the reason
      const dt = new DataTransfer(); dt.items.add(f); fileInput.files = dt.files;
      selectedFile = f; setUploadStatus(describeFile(selectedFile));
      dropZone.classList.add('is-dropped'); setTimeout(() => dropZone.classList.remove('is-dropped'), 700);
      toast(`Dropped: ${f.name}`, 'info', 3000);
      showResumePreview(f);
      syncRemoveFileButtons();
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
      const w = window.open('', '_blank');
      if (!w) { toast('Allow pop-ups to export the report.', 'warning', 6000); return; }
      w.document.write(d.html); w.document.close(); w.print();
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

  // ==================================================================
  // ─── RESUME STRENGTH SCORE METER + JOB MATCH DASHBOARD (new) ───
  // Score meter animates 0→100 when /score_resume responds (local
  // heuristic fallback so the meter still works if the API is absent).
  // Job dashboard exposes: renderJobs / filterJobs / sortJobs / searchJobs
  // / updateDashboardUI, fed from the existing analysis response.
  // ==================================================================
  const scorePanel = $('[data-score-panel]');
  const scoreRing = $('[data-score-ring]');
  const scoreFinal = $('[data-score-final]');
  const scoreStatus = $('[data-score-status]');
  const scoreFeedback = $('[data-score-feedback]');
  const scoreSubs = {
    skill: $('[data-score-sub="skill"]'),
    experience: $('[data-score-sub="experience"]'),
    quality: $('[data-score-sub="quality"]'),
  };

  const jmGrid = $('[data-jm-grid]');
  const jmEmpty = $('[data-jm-empty]');
  const jmStatus = $('[data-jm-status]');
  const jmSearch = $('[data-jm-search]');
  const jmSort = $('[data-jm-sort]');
  const jmMatchChips = $$('[data-jm-filter-match]');
  const jmRiskChips = $$('[data-jm-filter-risk]');

  let jmJobs = [];
  const jmState = { match: 'all', risk: 'all', query: '', sort: 'match-desc' };
  let scoreAnimId = null;
  let lastAtsScore = null; // real ATS check score from the latest updateAtsChecker pass

  const clampScore = (v) => Math.max(0, Math.min(100, Math.round(Number(v) || 0)));
  const scoreTier = (s) => (s >= 70 ? 'good' : s >= 40 ? 'average' : 'low');
  const tierLabel = (s) => (s >= 70 ? 'Good' : s >= 40 ? 'Average' : 'Low');
  const tierColor = (s) => (s >= 70 ? '#22c55e' : s >= 40 ? '#eab308' : '#ef4444');
  const defaultFeedback = (s) =>
    s >= 80 ? 'Strong resume — fine-tune keywords and measurable results to stand out.'
    : s >= 70 ? 'Good resume — a few targeted improvements will lift it further.'
    : s >= 40 ? 'Good resume, needs improvement — clarify skills and quantify achievements.'
    : 'Resume needs work — add relevant skills, experience detail, and cleaner structure.';

  /**
   * Animated ring counter — interval-based, 0 → target with 20 ms ticks,
   * writing `${counter}/100` into the element. A previous run is cleared
   * first so repeated calls never stack intervals.
   */
  let scoreCounter = null;
  const animateCount = (el, to, stepMs = 20) => {
    if (!el) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { el.textContent = `${to}/100`; return; }
    if (scoreCounter) clearInterval(scoreCounter);
    let counter = 0;
    scoreCounter = setInterval(() => {
      el.textContent = `${counter}/100`;
      if (counter >= to) { clearInterval(scoreCounter); scoreCounter = null; }
      counter++;
    }, stepMs);
  };

  /** Render a score payload { final_score, skill_score, experience_score, quality_score, feedback }. */
  function displayResumeScore(scoreData) {
    if (!scoreData) return;
    saveJSON(STORAGE.lastScore, scoreData); // remembered so the meter restores after refresh
    const score = clampScore(scoreData.final_score);

    // Animated counter: 0 → final score, 20 ms ticks
    const scoreEl = document.getElementById('score') || scoreFinal;
    if (scoreEl) {
      if (scoreCounter) clearInterval(scoreCounter);
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        scoreEl.innerText = `${score}/100`;
      } else {
        let counter = 0;
        scoreCounter = setInterval(() => {
          scoreEl.innerText = `${counter}/100`;
          if (counter >= score) { clearInterval(scoreCounter); scoreCounter = null; }
          counter++;
        }, 20);
      }
    }

    // Ring fill + tier color (green / orange / red via CSS)
    if (scorePanel) scorePanel.dataset.scoreTier = scoreTier(score);
    if (scoreRing) scoreRing.style.setProperty('--rs-pct', String(score));

    // Sub-scores by ID (backward-compatible refs) + animated bars
    const subIds = { skill: 'skillScore', experience: 'expScore', quality: 'qualityScore' };
    Object.entries(scoreSubs).forEach(([k, el]) => {
      if (!el) return;
      const v = clampScore(scoreData[`${k}_score`]);
      const bar = $('.rs-sub__bar span', el);
      const val = document.getElementById(subIds[k]) || $('.rs-sub__value', el);
      if (bar) bar.style.width = `${v}%`;
      if (val) val.innerText = String(v);
    });

    // Feedback text below the meter
    const feedbackEl = document.getElementById('feedback') || scoreFeedback;
    if (feedbackEl) feedbackEl.innerText = scoreData.feedback || defaultFeedback(score);
    if (scoreStatus) scoreStatus.textContent = `${tierLabel(score)} score`;
  }

  /** Call /score_resume via the central apiCall wrapper; null on failure.
   *  Accepts both response shapes: the backend's { success, result: {...} }
   *  wrapper and a flat { final_score, ... } payload. */
  async function fetchResumeScore(resumeText) {
    const data = await apiCall('/score_resume', { resume_text: resumeText });
    const payload = data && data.result ? data.result : data;
    if (!payload || payload.final_score == null) return null; // endpoint missing → caller falls back
    displayResumeScore(payload);
    return payload;
  }

  /** Local heuristic fallback derived from the analysis payload. */
  const scoreFromAnalysis = (payload) => {
    const roles = dedupeRoles(payload.top_roles || []);
    const sim = roles.length ? roles.reduce((a, r) => a + (r.similarity || 0), 0) / roles.length : 0;
    const skills = ((payload.reasoning || {}).skills_detected || []).length;
    const skill_score = clampScore(35 + sim * 45 + skills * 5);
    const experience_score = clampScore(30 + (1 - (payload.risk_score || 0)) * 55);
    const quality_score = clampScore(skill_score * 0.6 + experience_score * 0.4);
    return { final_score: Math.round((skill_score + experience_score + quality_score) / 3), skill_score, experience_score, quality_score };
  };

  /** Fired by renderResults: API first, local fallback if the endpoint is unavailable. */
  function updateResumeScoreUI(payload) {
    if (!scorePanel || !payload) return;
    if (restoringState) return; // keep the real score restored from localStorage
    const text = $('[data-resume-text]')?.value || payload.cleaned_resume || '';
    if (scoreStatus) scoreStatus.textContent = 'Scoring...';
    if (String(text).trim().length >= 30) {
      fetchResumeScore(text).then((d) => { if (!d) displayResumeScore(scoreFromAnalysis(payload)); });
    } else {
      displayResumeScore(scoreFromAnalysis(payload));
    }
  }

  // ── Job Match Dashboard ──
  const RISK_RANK = { Low: 0, Medium: 1, High: 2 };
  const matchBand = (s) => (s > 80 ? 'high' : s >= 50 ? 'medium' : 'low');
  const riskFromScore = (v) => ((Number(v) || 0) > 0.66 ? 'High' : (Number(v) || 0) > 0.33 ? 'Medium' : 'Low');
  const normalizeRisk = (v) => {
    const s = String(v || '').toLowerCase();
    if (s.startsWith('high') || s === 'elevated') return 'High';
    if (s.startsWith('mod') || s.startsWith('med')) return 'Medium';
    return 'Low';
  };

  /** Map the existing analysis payload into job-card shape { title, score, skills, risk_level }.
   *  Per-role data: trait_chips (from the ML profile attributes) and job_board_links
   *  (Indeed/LinkedIn/Naukri) are added server-side by _enrich_top_roles. */
  const jobsFromAnalysis = (payload) => dedupeRoles(payload.top_roles || []).map((r) => ({
    title: r.job_role || 'Untitled role',
    score: clampScore((r.similarity || 0) * 100),
    skills: ((payload.reasoning || {}).skills_detected || []).slice(0, 4),
    trait_chips: r.trait_chips || null,
    job_board_links: r.job_board_links || null,
    risk_level: r.risk_label ? normalizeRisk(r.risk_label) : riskFromScore(r.risk_score),
    industry: r.industry || '',
  }));

  function filterJobs(jobs, state) {
    return jobs.filter((j) => {
      if (state.match !== 'all' && matchBand(j.score) !== state.match) return false;
      if (state.risk !== 'all' && normalizeRisk(j.risk_level) !== state.risk) return false;
      if (state.query) {
        const hay = `${j.title} ${j.industry || ''} ${(j.skills || []).join(' ')}`.toLowerCase();
        if (!hay.includes(state.query)) return false;
      }
      return true;
    });
  }

  function sortJobs(jobs, mode) {
    const arr = [...jobs];
    if (mode === 'risk-asc') arr.sort((a, b) => (RISK_RANK[normalizeRisk(a.risk_level)] || 3) - (RISK_RANK[normalizeRisk(b.risk_level)] || 3) || b.score - a.score);
    else arr.sort((a, b) => b.score - a.score);
    return arr;
  }

  function renderJobs(jobs) {
    // Container: #jobContainer (falls back to the data-attribute ref)
    const container = document.getElementById('jobContainer') || jmGrid;
    if (!container) return;
    container.innerHTML = '';

    if (!jobs.length) { jmEmpty?.classList.remove('hidden'); return; }
    if (jmEmpty) jmEmpty.classList.add('hidden');

    jobs.forEach(job => {
      const band = matchBand(job.score);
      const risk = normalizeRisk(job.risk_level);
      // Per-role chips (trait_chips / skills from the API) with the shared
      // analysis skill list as fallback.
      const chipSource = job.trait_chips || job.skills || (lastAnalysis ? (lastAnalysis.reasoning || {}).skills_detected : null) || [];
      const skills = chipSource.slice(0, 4).map((s) => `<span class="jm-skill">${esc(s)}</span>`).join('');
      // Per-role job-board links (Indeed / LinkedIn / Naukri)
      const links = (job.job_board_links || roleLinks(job)).map((l) => `<a class="button-ghost" href="${l.url}" target="_blank" rel="noreferrer noopener">${l.label}</a>`).join('');

      // Card is built per-job (createElement + appendChild) so it can be
      // styled/extended independently; styling via the .jm-card classes.
      const card = document.createElement('div');
      card.className = 'job-card jm-card';

      card.innerHTML = `
        <div class="jm-card__head">
          <div><h3 class="jm-card__title">${esc(job.title)}</h3><p class="jm-card__industry">${esc(job.industry || '')}</p></div>
          <span class="jm-card__match jm-match--${band}">${job.score}%</span>
        </div>
        <div class="jm-card__bar"><span style="width:${job.score}%;background:${tierColor(job.score)};"></span></div>
        <div class="jm-card__meta">
          <span>Match Score: ${job.score}%</span>
          <span>Risk: <span class="jm-risk jm-risk--${risk}">${risk}</span></span>
        </div>
        ${skills ? `<div class="jm-skills">${skills}</div>` : ''}
        ${links ? `<div class="jm-card__links">${links}</div>` : ''}
        <div class="jm-card__actions"><button type="button" class="button-ghost" data-job-details aria-haspopup="dialog">View Details</button></div>
      `;

      card.querySelector('[data-job-details]')?.addEventListener('click', () => openJobModal(job));
      container.appendChild(card);
    });
  }

  function searchJobs() {
    jmState.query = (jmSearch?.value || '').trim().toLowerCase();
    applyJmView();
  }

  const applyJmView = () => {
    renderJobs(sortJobs(filterJobs(jmJobs, jmState), jmState.sort));
    saveJSON(STORAGE.lastFilters, jmState); // remember selected filters across refreshes
  };

  /** Push a new job list into the dashboard (fired by renderResults). */
  function updateDashboardUI(jobs) {
    jmJobs = Array.isArray(jobs) ? jobs : [];
    updateChipCounts();
    applyJmView();
    if (jmStatus) jmStatus.textContent = jmJobs.length ? `${jmJobs.length} matches` : 'No matches';
  }

  /** Per-band job counts on the filter chips (e.g. "High > 80 · 3").
   *  Bands are computed against the full job list, ignoring the current
   *  selection, so the numbers stay meaningful while filtering. */
  function updateChipCounts() {
    const counts = { all: jmJobs.length, high: 0, medium: 0, low: 0, 'risk-all': jmJobs.length, Low: 0, Medium: 0, High: 0 };
    jmJobs.forEach((j) => {
      counts[matchBand(j.score)] = (counts[matchBand(j.score)] || 0) + 1;
      const r = normalizeRisk(j.risk_level);
      counts[r] = (counts[r] || 0) + 1;
    });
    $$('[data-chip-count]').forEach((el) => {
      const k = el.dataset.chipCount;
      if (counts[k] != null) el.textContent = String(counts[k]);
    });
  }

  jmSearch?.addEventListener('input', searchJobs);
  jmSort?.addEventListener('change', () => { jmState.sort = jmSort.value; applyJmView(); });
  jmMatchChips.forEach((chip) => chip.addEventListener('click', () => {
    jmMatchChips.forEach((c) => c.classList.toggle('is-active', c === chip));
    jmState.match = chip.dataset.jmFilterMatch || 'all';
    applyJmView();
  }));
  jmRiskChips.forEach((chip) => chip.addEventListener('click', () => {
    jmRiskChips.forEach((c) => c.classList.toggle('is-active', c === chip));
    jmState.risk = chip.dataset.jmFilterRisk || 'all';
    applyJmView();
  }));

  /**
   * Fetch job matches for a skill list from /match_jobs and render them.
   * Response shape: { jobs: [{ title, score, skills, risk_level }] }.
   * Falls back to the latest analysis-derived jobs when the endpoint is
   * unavailable, so the dashboard still populates.
   */
  function getJobs(skills) {
    apiCall('/match_jobs', { skills: skills })
      .then((data) => {
        const jobs = data && Array.isArray(data.jobs) ? data.jobs : null;
        if (jobs) {
          updateDashboardUI(jobs); // renders + keeps search/filter/sort state in sync
        } else if (jmJobs.length) {
          updateDashboardUI(jmJobs); // endpoint missing → reuse current match data
        } else {
          toast('No job matches available. Run an analysis first.', 'warning');
        }
      });
  }

  // ==================================================================
  // ─── UPLOAD → SCORE → JOBS → RISK PIPELINE (new) ───
  // Modular vanilla-JS functions: uploadResume / handleFileSelect /
  // handleFileDrop / animateScore / displayRiskLevel / updateRiskMeter /
  // getRiskColor / apiCall. (renderJobs / filterJobs / sortJobs / searchJobs
  // and the score meter live in the feature block above.)
  // Endpoint note: this backend exposes the full analysis at /api/upload
  // (no separate /upload_resume, /score_resume, /match_jobs or /predict_risk
  // routes yet), so the pipeline posts the file there once and feeds every
  // dashboard section from the response. /score_resume is still attempted
  // first by the meter with a local fallback, so new endpoints slot in
  // without further changes.
  // ==================================================================
  const upBtn = $('[data-upload-resume-btn]');
  const upInput = $('[data-upload-resume-input]');
  const upDropzone = $('[data-upload-dropzone]');
  const upDropStatus = $('[data-upload-drop-status]');
  const upStatus = $('[data-up-status]');
  const riskMeter = $('[data-riskmeter]');
  const riskMarker = $('[data-riskmeter-marker]');
  const riskLevel = $('[data-riskmeter-level]');
  const riskPct = $('[data-riskmeter-pct]');
  const riskMeterStatus = $('[data-riskmeter-status]');
  const riskMeterSummary = $('[data-riskmeter-summary]');

  /**
   * Centralized API wrapper (fetch-based).
   *   apiCall(url, data)           → JSON POST (Content-Type: application/json)
   *   apiCall(url, formData, true) → multipart POST for file uploads
   * Always resolves to parsed JSON, or { success: false, error: "Network error" }.
   * X-CSRFToken is attached automatically (Flask-WTF requires it on POST),
   * with one reactive token-refresh retry on CSRF rejection — mirrors apiPost.
   */
  async function apiCall(url, data = null, isFile = false) {
    try {
      const options = {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
      };
      if (isFile) {
        options.body = data; // FormData for file upload (browser sets multipart headers)
      } else {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(data);
      }
      let response = await fetch(url, options);
      if (response.status === 400) {
        // Possible CSRF rejection → refresh the token once and retry
        try {
          const cloned = response.clone();
          if (/csrf/i.test(await cloned.text())) {
            await refreshCsrfToken();
            response = await fetch(url, options);
          }
        } catch { /* ignore clone/parse errors */ }
      }
      const result = await response.json();
      return result;
    } catch (error) {
      console.error('API Error:', error);
      return { success: false, error: 'Network error' };
    }
  }

  // ── Step 1: Upload ──
  const ALLOWED_EXT = /\.(pdf|docx|txt)$/i;

  /**
   * Primary file-input handler: posts the raw file to /score_resume as
   * multipart FormData (field name "resume") and renders the returned
   * score payload { result: { final_score, skill_score, ... } }.
   * If /score_resume is unavailable (no result in response), it falls back
   * to uploadResume() → the full /api/upload analysis, which feeds the
   * score meter, job cards, and risk meter together.
   */
  /** Single-step scorer (kept for backward compatibility) — the full
   *  chained pipeline lives in processResume, which all entry points use. */
  function handleFileUpload(event) {
    processResume(event);
  }

  /**
   * Full chained pipeline (STEP 1 score → STEP 2 job match → STEP 3 risk).
   * Called by handleFileUpload for every upload; falls back to the single
   * /api/upload analysis when the granular endpoints are unavailable.
   * Note: apiCall resolves (never rejects) with { success:false, error } on
   * failure, so each step's result is checked explicitly instead of relying
   * on .catch alone — a failed /predict_risk must not paint a false green.
   */
  function processResume(event) {
    const file = event.target?.files?.[0];
    if (!file) { toast('No file selected', 'warning'); return; }
    const formData = new FormData();
    formData.append('resume', file);
    setStatus('Processing...');

    // STEP 1: SCORE
    apiCall('/score_resume', formData, true)
      .then((scoreData) => {
        if (!scoreData || !scoreData.result) throw new Error('Scoring unavailable');
        displayResumeScore(scoreData.result);
        // STEP 2: JOB MATCH — skills extracted by /score_resume
        return apiCall('/match_jobs', {
          skills: scoreData.result.skills || []
        });
      })
      .then((jobData) => {
        if (!jobData || !jobData.jobs) throw new Error('Job matching unavailable');
        renderJobs(jobData.jobs);
        if (jmStatus) jmStatus.textContent = `${jobData.jobs.length} matches`;
        // STEP 3: RISK ANALYSIS — reuse the uploaded file
        return apiCall('/predict_risk', formData, true);
      })
      .then((riskData) => {
        if (!riskData || !riskData.risk_level) throw new Error('Risk analysis unavailable');
        displayRiskLevel(riskData);
        setStatus('Complete');
        toast('Resume analyzed — score, jobs, and risk updated.', 'success');
      })
      .catch((err) => {
        console.error(err);
        // Granular endpoints unavailable → run the existing full analysis,
        // which feeds score meter, job cards, and risk meter in one response.
        setStatus('Processing via full analysis...');
        return uploadResume(file);
      });
  }

  /** Status text for the upload card (supports the legacy id="status"). */
  const setStatus = (msg) => {
    const el = document.getElementById('status') || upStatus;
    if (el) el.innerText = msg;
  };

  /** Backward-compatible alias — routes through the full pipeline. */
  function handleFileSelect(event) {
    processResume(event);
  }

  function handleFileDrop(event) {
    event.preventDefault();
    const file = event.dataTransfer?.files?.[0];
    if (!file) return;
    // Reuse the file-input pipeline path: synthesize an event-shaped object
    processResume({ target: { files: [file] } });
  }

  async function uploadResume(file) {
    if (!file) return;
    if (!ALLOWED_EXT.test(file.name)) { toast('Unsupported file type. Use PDF, DOCX or TXT.', 'warning'); return; }
    if (upStatus) upStatus.textContent = file.name;
    if (upDropStatus) upDropStatus.textContent = `Selected: ${file.name} (${Math.round(file.size / 1024)} KB)`;
    if (upDropzone) { upDropzone.classList.add('is-dropped'); setTimeout(() => upDropzone.classList.remove('is-dropped'), 700); }
    if (upStatus) upStatus.textContent = 'Uploading...';
    if (upBtn) upBtn.disabled = true;
    try {
      await uploadPipeline(file);
      if (upStatus) upStatus.textContent = 'Complete';
      toast('Resume analyzed — results updated below.', 'success');
    } catch (err) {
      if (upStatus) upStatus.textContent = 'Upload failed';
      renderError(err.message || 'Upload failed.');
    } finally {
      if (upBtn) upBtn.disabled = false;
    }
  }

  /** Send the file to the backend and drive every dashboard section. */
  async function uploadPipeline(file) {
    const fd = new FormData();
    fd.append('resume_file', file);
    fd.append('mode', activeMode);
    setBusy(true, 'Analyzing uploaded resume...');
    try {
      const p = await apiCall('/api/upload', fd, true); // multipart via central wrapper
      if (!p || !p.success) throw new Error((p && p.error) || 'Analysis failed.');
      resetStyles();
      renderResults(p); // feeds score meter, job cards, and risk meter hooks
    } finally {
      setBusy(false);
    }
  }

  // ── Step 2: Score animation alias (ring meter lives in the block above) ──
  function animateScore(value) { animateCount(scoreFinal, clampScore(value)); }

  // ── Step 4: Career risk meter ──
  const getRiskColor = (level) => (level === 'High' ? '#ef4444' : level === 'Medium' ? '#eab308' : '#22c55e');

  function updateRiskMeter(level, pct) {
    if (!riskMeter) return;
    const safePct = Math.max(0, Math.min(100, Math.round(Number(pct) || 0)));
    riskMeter.style.setProperty('--rk-color', getRiskColor(level));
    if (riskMarker) riskMarker.style.left = `${safePct}%`;
    if (riskLevel) riskLevel.textContent = `${level} risk`;
    if (riskPct) riskPct.textContent = `${safePct}% exposure`;
  }

  /**
   * Accepts { risk_level, explanation, level | label, score | pct } and
   * drives both the riskBox/riskExplain text and the animated gauge marker.
   * Keeps the exact text/color contract: "Risk Level: <level>",
   * High → red, Medium → orange, else green.
   */
  function displayRiskLevel(data) {
    if (!data) return;
    const level = normalizeRisk(data.risk_level || data.level || data.label || 'Low');

    // riskBox: "Risk Level: <level>" with explicit inline color per band
    const box = document.getElementById('riskBox') || riskLevel;
    if (box) {
      box.innerText = 'Risk Level: ' + level;
      if (level === 'High') box.style.color = 'red';
      else if (level === 'Medium') box.style.color = 'orange';
      else box.style.color = 'green';
    }

    // Explanation line under the meter
    const explain = document.getElementById('riskExplain') || riskMeterSummary;
    if (explain) explain.innerText = data.explanation || defaultRiskExplanation(level);

    // Animated gauge marker + % exposure
    let pct = null;
    if (data.pct != null) pct = data.pct;
    else if (data.score != null) pct = data.score * 100;
    updateRiskMeter(level, pct == null ? (level === 'High' ? 80 : level === 'Medium' ? 50 : 20) : pct);
    if (riskMeterStatus) riskMeterStatus.textContent = 'Live';
  }

  const defaultRiskExplanation = (level) => (
    level === 'High' ? 'High automation exposure — prioritize reskilling actions below.'
    : level === 'Medium' ? 'Moderate exposure — strengthen transferable skills to stay ahead.'
    : 'Low exposure — your profile is well positioned; keep skills current.'
  );

  /** Map the analysis payload onto the risk meter (called from renderResults). */
  function updateRiskMeterFromPayload(payload) {
    if (!riskMeter || !payload) return;
    const level = payload.risk_label ? normalizeRisk(payload.risk_label) : riskFromScore(payload.risk_score);
    const pct = Math.round((payload.risk_score || 0) * 100);
    updateRiskMeter(level, pct);
    if (riskMeterStatus) riskMeterStatus.textContent = 'Live';
    if (riskMeterSummary) riskMeterSummary.textContent = payload.cognitive_career_narrative || `Automation exposure is ${level.toLowerCase()} (${pct}%).`;
  }

  // ── Upload event bindings ──
  upBtn?.addEventListener('click', () => upInput?.click());
  upInput?.addEventListener('change', handleFileSelect);
  if (upDropzone) {
    ['dragenter', 'dragover'].forEach((e) => upDropzone.addEventListener(e, (ev) => { ev.preventDefault(); upDropzone.classList.add('is-dragover'); }));
    ['dragleave', 'drop'].forEach((e) => upDropzone.addEventListener(e, (ev) => { ev.preventDefault(); upDropzone.classList.remove('is-dragover'); }));
    upDropzone.addEventListener('drop', handleFileDrop);
  }

  /**
   * Restore safe, reusable dashboard state from localStorage after a refresh:
   * score meter, job filters, and the last analysis snapshot. The resume file
   * itself is never re-uploaded and its text is never stored.
   */
  function restoreSavedState() {
    // Score meter (real stored payload — no random regeneration)
    const savedScore = loadJSON(STORAGE.lastScore, null);
    if (savedScore && typeof savedScore.final_score === 'number' && scorePanel) {
      displayResumeScore(savedScore);
      if (scoreStatus) scoreStatus.textContent = 'Restored';
    }

    // Job dashboard filters (match band / risk / sort / search)
    const savedFilters = loadJSON(STORAGE.lastFilters, null);
    if (savedFilters && typeof savedFilters === 'object') {
      if (savedFilters.sort && jmSort && Array.from(jmSort.options).some((o) => o.value === savedFilters.sort)) jmSort.value = savedFilters.sort;
      jmState.sort = savedFilters.sort || jmState.sort;
      jmState.match = typeof savedFilters.match === 'string' ? savedFilters.match : 'all';
      jmState.risk = typeof savedFilters.risk === 'string' ? savedFilters.risk : 'all';
      jmState.query = typeof savedFilters.query === 'string' ? savedFilters.query : '';
      if (jmSearch && jmState.query) jmSearch.value = jmState.query;
      jmMatchChips.forEach((c) => c.classList.toggle('is-active', (c.dataset.jmFilterMatch || 'all') === jmState.match));
      jmRiskChips.forEach((c) => c.classList.toggle('is-active', (c.dataset.jmFilterRisk || 'all') === jmState.risk));
    }

    // Last analysis snapshot → dashboard cards, risk meter, pie charts,
    // skill gap chart, statistics and job cards.
    const snap = loadJSON(STORAGE.lastAnalysis, null);
    if (snap && typeof snap === 'object' && Array.isArray(snap.top_roles) && snap.top_roles.length) {
      restoringState = true;
      try {
        renderResults({
          mode: snap.mode,
          risk_score: snap.risk_score,
          risk_label: snap.risk_label,
          cognitive_career_narrative: snap.narrative,
          reasoning: snap.reasoning || {},
          top_roles: snap.top_roles,
          roadmap: snap.roadmap || [],
          riasec: snap.riasec || {},
          guided_next_steps: snap.guided_next_steps || {},
        });
      } finally {
        restoringState = false;
      }
      if (jmStatus) jmStatus.textContent = 'Restored';
    }
  }

  // ─── INIT ───
  // NOTE: setMode/renderPathway run at the END of the IIFE (next to
  // restoreSavedState). renderPathway → renderCareerPathFlowchart touches
  // consts declared further down (careerFlowContainer), so calling them here
  // threw a temporal-dead-zone ReferenceError that killed this whole script —
  // every later event binding never ran and the workspace appeared dead.

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
      // Skills already extracted by the completed analysis — reused when the
      // resume text is no longer around (PDF/DOCX upload, or page revisited
      // after a refresh). This is REAL data from the last run, not a guess.
      const analysisSkills = ((lastAnalysis || {}).reasoning || {}).skills_detected || [];

      if (resumeText.length < 20 && !analysisSkills.length) {
        toast('Run a resume analysis or paste resume text first (min 20 characters).', 'warning');
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
          target_role: targetRole,
          user_skills: analysisSkills
        });
        const data = await res.json();

        if (!data.success) {
          throw new Error(data.error || 'Analysis failed.');
        }

        renderSkillsGap(data.analysis);
        syncSkillMatchFromGap(data.analysis); // keep the Dashboard Skill Match card in step
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
            <h3 class="section-title">Skills Gap Analysis: ${esc(analysis.target_role)}</h3>
            <p class="section-subtitle">Comparing your resume against ${Number(analysis.total_required) || 0} required skills</p>
          </div>
          <div class="skills-gap-score" style="text-align:center;">
            <div class="skills-gap-ring" style="--pct: ${matchPct}; --color: ${matchColor};">
              <span class="skills-gap-ring__value">${matchPct}%</span>
            </div>
            <span style="font-size:0.78rem;font-weight:600;color:${matchColor};">${matchLabel}</span>
          </div>
        </div>

        <div class="skills-gap-grid">
          <div class="list-card" style="border-color: #22c55e44;">
            <div>
              <strong style="color:#22c55e;">✅ Matched Skills (${analysis.matched_count})</strong>
              ${analysis.matched_skills.length ? analysis.matched_skills.map(s => `<span class="chip" style="background:#22c55e22;color:#22c55e;margin:2px 4px 2px 0;">${esc(s)}</span>`).join('') : '<p style="color:var(--text-muted);margin-top:0.5rem;">No direct skill matches found.</p>'}
            </div>
          </div>
          <div class="list-card" style="border-color: #ef444444;">
            <div>
              <strong style="color:#ef4444;">❌ Missing Skills (${analysis.missing_count})</strong>
              ${analysis.missing_skills.length ? analysis.missing_skills.map(s => `<span class="chip" style="background:#ef444422;color:#ef4444;margin:2px 4px 2px 0;">${esc(s)}</span>`).join('') : '<p style="color:var(--text-muted);margin-top:0.5rem;">No missing skills — you\'re fully qualified!</p>'}
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
                    <strong>${esc(r.skill)}</strong>
                    <span class="status-pill ${r.priority === 'High' ? 'is-danger' : 'is-warm'}" style="margin-left:0.5rem;">${esc(r.priority)}</span>
                    <ul style="margin:0.5rem 0 0;padding-left:1.25rem;color:var(--text-muted);font-size:0.85rem;">
                      ${r.resources.map(res => `<li style="margin-bottom:0.25rem;">${esc(res)}</li>`).join('')}
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

  /** Push the completed skill-gap result into the Dashboard Skill Match card.
   *  Per Part B/E, Skill Match = matched required skills ÷ total required × 100
   *  — exactly what the backend just computed for the selected target role. */
  function syncSkillMatchFromGap(analysis) {
    if (!analysis || typeof analysis.match_percentage !== 'number') return;
    const pct = clampScore(analysis.match_percentage);
    updateRiskCardValue('skill-match', pct,
      pct >= 70 ? 'Strong' : pct >= 40 ? 'Average' : 'Low',
      pct >= 70 ? 'is-good' : pct >= 40 ? 'is-medium' : 'is-high');
  }

  // ─── SKILL VISUALIZATION ───
  const skillVizContainer = $('[data-skillviz-container]');
  const skillVizStatus = $('[data-skillviz-status]');

  function updateSkillVisualization(payload) {
    if (!skillVizContainer) return;
    // Category filter active → render through the filter-aware renderer
    if (typeof skillFilterCat === 'string' && skillFilterCat !== 'all' && !restoringState) {
      renderSkillVizFiltered();
      return;
    }
    const skills = ((payload.reasoning || {}).skills_detected || []);
    const roles = dedupeRoles(payload.top_roles || []);
    const sim = roles.length ? roles.reduce((a, r) => a + (r.similarity || 0), 0) / roles.length : 0;

    if (!skills.length) {
      skillVizContainer.innerHTML = '<div class="list-card is-placeholder"><div><strong>No skills detected</strong><p>Run an analysis to detect skills from your resume.</p></div></div>';
      if (skillVizStatus) skillVizStatus.textContent = 'No skills';
      return;
    }

    // Per-skill strength from the analysis: real percentage of resume skills
    // mapped to each role (trait_chips carry the share, e.g. "75% Python"),
    // falling back to role-similarity weighting when unavailable.
    const maxSim = Math.max(sim, 0.3);
    skillVizContainer.innerHTML = skills.slice(0, 8).map((skill, i) => {
      let pct = 0;
      const chip = roles.flatMap((r) => r.trait_chips || []).find((c) => typeof c === 'string' && c.toLowerCase().includes(String(skill).toLowerCase()));
      const chipMatch = chip && chip.match(/(\d{1,3})\s*%/);
      if (chipMatch) pct = clampScore(parseInt(chipMatch[1], 10));
      else pct = clampScore(Math.round((maxSim * 100) * (1 - i * 0.08)));
      const label = chipMatch ? chip.replace(/\s*\d{1,3}\s*%,?\s*/, '').trim() : '';
      const aria = label ? `${skill}: ${label} relevance ${pct}%` : `${skill}: relevance ${pct}%`;
      return `<div class="skill-viz-item" title="${esc(aria)}" aria-label="${esc(aria)}"><span class="skill-viz-item__name">${esc(skill)}</span><div class="skill-viz-item__bar"><span style="width:${pct}%;"></span></div><span class="skill-viz-item__value">${pct}%</span></div>`;
    }).join('');

    if (skillVizStatus) skillVizStatus.textContent = `${skills.length} skills`;
  }

  // ─── ATS RESUME CHECKER ───
  const atsRing = $('[data-ats-ring]');
  const atsScore = $('[data-ats-score]');
  const atsVerdict = $('[data-ats-verdict]');
  const atsStatus = $('[data-ats-status]');
  const atsChecksContainer = $('[data-ats-checks]');
  const atsSuggestions = $('[data-ats-suggestions]');

  const ATS_PATTERNS = {
    email: /[\w.+-]+@[\w-]+\.[\w.]+/,
    phone: /(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}/,
    skills: /\b(skills|technologies|tech stack|tools|proficiencies)\b/i,
    education: /\b(education|degree|bachelor|master|phd|university|college|school)\b/i,
    experience: /\b(experience|employment|work history|professional background)\b/i,
    projects: /\b(projects?|portfolio|github|repository)\b/i,
    keywords: /\b(python|javascript|java|c\+\+|sql|machine learning|data|analysis|management|leadership|communication|team|agile|scrum)\b/i,
  };

  function updateAtsChecker(payload) {
    if (restoringState) return; // ATS needs real resume text; never fake it from a snapshot
    const text = (payload.cleaned_resume || payload.resume_text || $('[data-resume-text]')?.value || '').trim();
    const detected = ((payload.reasoning || {}).skills_detected || []);
    // PDF/DOCX uploads are parsed server-side and the text is not returned,
    // so the full 8-point check is only possible when usable text exists.
    // Without text we run ONLY the checks the analysis data supports
    // (skills, keywords) and say so — no fake failures for contact fields.
    const hasText = text.length > 0;

    const results = hasText ? {
      email: ATS_PATTERNS.email.test(text),
      phone: ATS_PATTERNS.phone.test(text),
      skills: ATS_PATTERNS.skills.test(text) || detected.length > 0,
      education: ATS_PATTERNS.education.test(text),
      experience: ATS_PATTERNS.experience.test(text),
      projects: ATS_PATTERNS.projects.test(text),
      keywords: ATS_PATTERNS.keywords.test(text) || detected.length > 0,
      length: text.length >= 200,
    } : {
      skills: detected.length > 0,
      keywords: detected.length > 0,
    };

    const passed = Object.values(results).filter(Boolean).length;
    const total = Object.keys(results).length;
    const score = total ? Math.round((passed / total) * 100) : 0;
    lastAtsScore = total ? score : null; // consumed by renderRiskCards (real dashboard ATS card)

    // Update ring + score (--ats-pct is a bare 0-100 number; styles.css derives degrees)
    if (atsRing) atsRing.style.setProperty('--ats-pct', String(score));
    if (atsScore) atsScore.textContent = `${score}%`;
    if (atsVerdict) {
      atsVerdict.textContent = score >= 80 ? 'Good ATS compatibility' : score >= 60 ? 'Moderate — some improvements needed' : 'Low — significant improvements recommended';
    }
    if (atsStatus) atsStatus.textContent = hasText ? `${passed}/${total} checks` : `Partial — ${passed}/${total} checks (no text)`;

    // Update check items
    if (atsChecksContainer) {
      const labels = { email: 'Email address detected', phone: 'Phone number detected', skills: 'Skills section present', education: 'Education section present', experience: 'Experience section present', projects: 'Projects section present', keywords: 'Important keywords found', length: 'Adequate resume length' };
      atsChecksContainer.querySelectorAll('.ats-check').forEach(el => {
        const key = el.dataset.atsCheck;
        if (!key) return;
        const pass = results[key];
        el.classList.toggle('is-pass', pass);
        el.classList.toggle('is-fail', !pass);
        const icon = el.querySelector('.ats-check-icon');
        if (icon) icon.textContent = pass ? '✓' : '✗';
      });
    }

    // Suggestions (only for checks actually assessed)
    if (atsSuggestions) {
      const suggestionMap = { email: 'Add a professional email address.', phone: 'Include a phone number for contact.', skills: 'Add a dedicated Skills section listing your technical proficiencies.', education: 'Include an Education section with your degree and institution.', experience: 'Add an Experience section detailing your work history.', projects: 'Include a Projects section highlighting key work.', keywords: 'Incorporate industry-relevant keywords throughout your resume.', length: 'Expand your resume — aim for at least 200 characters of content.' };
      const missing = Object.entries(results).filter(([, v]) => !v).map(([k]) => k);
      const note = hasText ? '' : '<div class="ats-suggestion" style="border-left-color:var(--primary);">Basic ATS Compatibility Check — paste your resume text to run the full 8-point check (email, phone, sections, length).</div>';
      atsSuggestions.innerHTML = note + (missing.length
        ? missing.map(k => `<div class="ats-suggestion">${suggestionMap[k] || `Improve: ${k}`}</div>`).join('')
        : '<div class="ats-suggestion" style="border-left-color:#22c55e;">All checks passed — your resume has good ATS compatibility!</div>');
    }
  }

  // ─── CAREER PATH FLOWCHART ───
  const careerFlowContainer = $('[data-career-flow]');
  const careerPathStatus = $('[data-career-path-status]');

  const CAREER_PATHS = {
    student: [
      { title: 'Intern', desc: 'Gain practical experience through internships', badge: '0–6 mo', level: 'Entry', focus: ['Programming fundamentals', 'Git basics'], skills: ['Python', 'JavaScript', 'Git', 'SQL'], focusSkills: ['Docker', 'Unit testing', 'Cloud basics'] },
      { title: 'Junior Developer', desc: 'Entry-level role building foundational skills', badge: '1–2 yr', level: 'Entry', focus: ['Ship features with review', 'Testing habits'], skills: ['Python', 'JavaScript', 'Git', 'SQL', 'REST APIs'], focusSkills: ['Docker', 'CI/CD', 'System design basics'] },
      { title: 'Mid-Level Developer', desc: 'Independent contributor with growing expertise', badge: '3–5 yr', level: 'Mid', focus: ['Own modules end-to-end', 'Mentor interns'], skills: ['Python', 'JavaScript', 'REST APIs', 'Docker', 'CI/CD', 'PostgreSQL'], focusSkills: ['System design', 'Kubernetes', 'Observability'] },
      { title: 'Senior Developer', desc: 'Technical leadership and mentoring', badge: '5–8 yr', level: 'Senior', focus: ['Lead projects', 'Design reviews'], skills: ['System design', 'Docker', 'CI/CD', 'PostgreSQL', 'Cloud (AWS/Azure)'], focusSkills: ['Architecture governance', 'Stakeholder communication'] },
      { title: 'Specialized Role', desc: 'Domain expert or engineering manager', badge: '8+ yr', level: 'Lead', focus: ['Set technical direction', 'Grow the team'], skills: ['System design', 'Cloud (AWS/Azure)', 'Stakeholder communication'], focusSkills: ['Strategic planning', 'Budgeting & hiring'] },
    ],
    'job-seeker': [
      { title: 'Skill Assessment', desc: 'Identify transferable skills and gaps', badge: '1–2 wk', level: 'Entry', focus: ['Inventory your skills', 'Pick 1–2 targets'], skills: ['Self-assessment', 'Resume writing', 'LinkedIn'], focusSkills: ['Interview basics'] },
      { title: 'Targeted Applications', desc: 'Apply to roles matching your profile', badge: '2–4 wk', level: 'Entry', focus: ['Tailor each application', 'Track responses'], skills: ['Resume tailoring', 'Job-board search', 'Networking'], focusSkills: ['Cover-letter writing'] },
      { title: 'Interview Preparation', desc: 'Practice technical and behavioral questions', badge: '1–2 wk', level: 'Mid', focus: ['Daily practice blocks', 'Mock interviews'], skills: ['Data structures', 'Behavioral answers (STAR)'], focusSkills: ['System design', 'Negotiation basics'] },
      { title: 'Offer Negotiation', desc: 'Evaluate and negotiate compensation', badge: '1–2 wk', level: 'Mid', focus: ['Compare total compensation', 'Get it in writing'], skills: ['Salary research', 'Negotiation'], focusSkills: ['Counter-offer strategy'] },
      { title: 'Onboarding', desc: 'Transition smoothly into your new role', badge: '2–4 wk', level: 'Senior', focus: ['Learn the codebase', 'Build relationships'], skills: ['Codebase navigation', 'Team communication'], focusSkills: ['Domain knowledge'] },
    ],
    'career-switcher': [
      { title: 'Skills Mapping', desc: 'Map existing skills to target role', badge: '1–2 wk', level: 'Entry', focus: ['List transferable skills', 'Shortlist target roles'], skills: ['Transferable-skill analysis', 'Research'], focusSkills: ['Target-role fundamentals'] },
      { title: 'Gap Closing', desc: 'Learn missing skills via courses/projects', badge: '4–12 wk', level: 'Entry', focus: ['One skill at a time', 'Build as you learn'], skills: ['Target-role fundamentals', 'Project work'], focusSkills: ['Advanced tooling', 'Certifications'] },
      { title: 'Portfolio Building', desc: 'Build proof-of-work for new domain', badge: '4–8 wk', level: 'Mid', focus: ['2–3 solid projects', 'Document decisions'], skills: ['Project planning', 'Version control', 'Domain tools'], focusSkills: ['Case-study writing'] },
      { title: 'Transition Role', desc: 'Land a bridge role in the new field', badge: '2–6 mo', level: 'Mid', focus: ['Target bridge roles', 'Leverage your network'], skills: ['Interview skills', 'Networking', 'Domain tools'], focusSkills: ['Role-specific depth'] },
      { title: 'Full Transition', desc: 'Established in new career path', badge: '6+ mo', level: 'Senior', focus: ['Deepen expertise', 'Expand scope'], skills: ['Domain expertise', 'Professional network'], focusSkills: ['Specialization choice'] },
    ],
    'new-workforce': [
      { title: 'Foundation Building', desc: 'Develop core professional skills', badge: '0–3 mo', level: 'Entry', focus: ['Daily practice routine', 'Learn workplace tools'], skills: ['Communication', 'Office tools', 'Time management'], focusSkills: ['Industry terminology'] },
      { title: 'Entry-Level Role', desc: 'First professional position', badge: '3–6 mo', level: 'Entry', focus: ['Ask questions early', 'Find a mentor'], skills: ['Email etiquette', 'Teamwork', 'Basic Excel'], focusSkills: ['Role-specific tools'] },
      { title: 'Skill Expansion', desc: 'Broaden technical and soft skills', badge: '6–12 mo', level: 'Mid', focus: ['Cross-team projects', 'Short courses'], skills: ['Presentation skills', 'Data handling'], focusSkills: ['Project coordination'] },
      { title: 'Specialization', desc: 'Choose a focus area and deepen expertise', badge: '1–2 yr', level: 'Mid', focus: ['Pick a growing niche', 'Find stretch work'], skills: ['Niche technical skills', 'Stakeholder management'], focusSkills: ['Advanced certifications'] },
      { title: 'Career Growth', desc: 'Advance to mid-level responsibilities', badge: '2+ yr', level: 'Senior', focus: ['Lead small initiatives', 'Mentor newcomers'], skills: ['Leadership basics', 'Domain depth'], focusSkills: ['People management'] },
    ],
  };

  function renderCareerPathFlowchart(path) {
    if (!careerFlowContainer) return;
    const nodes = CAREER_PATHS[path] || CAREER_PATHS.student;

    careerFlowContainer.innerHTML = nodes.map((node, i) => `
      ${i > 0 ? '<div class="career-connector" aria-hidden="true"></div>' : ''}
      <div class="career-node" data-career-node="${i}" tabindex="0" role="button" aria-label="${esc(node.title)}: ${esc(node.desc)}">
        <span class="career-node__number">${i + 1}</span>
        <div class="career-node__body">
          <strong>${esc(node.title)}</strong>
          <p>${esc(node.desc)}</p>
        </div>
        <span class="career-node__badge">${esc(node.badge)}</span>
      </div>
    `).join('');

    if (careerPathStatus) careerPathStatus.textContent = nodes.length + ' stages';

    // Add click handlers — open the detail panel instead of a transient toast
    careerFlowContainer.querySelectorAll('.career-node').forEach(el => {
      const openNode = () => {
        const idx = parseInt(el.dataset.careerNode, 10);
        showCareerNodeDetail(nodes[idx], el);
      };
      el.addEventListener('click', openNode);
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          el.click();
        }
      });
    });
  }

  // ═══ CAREER PATH: NODE DETAIL PANEL ═══
  // Shows a clicked stage's description, level and skill chips. The
  // "skills you already have" column is computed against the last real
  // analysis (reasoning.skills_detected); with no analysis yet it shows an
  // honest empty state instead of invented data.
  function showCareerNodeDetail(node, el) {
    if (!node || !careerFlowContainer) return;
    let panel = document.getElementById('careerNodeDetail');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'careerNodeDetail';
      panel.className = 'career-node-detail';
      panel.setAttribute('role', 'region');
      panel.setAttribute('aria-live', 'polite');
      panel.setAttribute('aria-label', 'Selected career stage details');
      careerFlowContainer.insertAdjacentElement('afterend', panel);
    }
    // Highlight the selected node
    careerFlowContainer.querySelectorAll('.career-node').forEach((n) => n.classList.toggle('is-selected', n === el));

    const detected = lastAnalysis ? ((lastAnalysis.reasoning || {}).skills_detected || []).map((s) => String(s).toLowerCase()) : null;
    const chips = (list, cls, noDataText) => {
      if (!Array.isArray(list) || !list.length) return `<p class="career-detail__none">${esc(noDataText)}</p>`;
      return `<div class="career-detail__chips">${list.map((s) => `<span class="career-detail__chip ${cls}">${esc(s)}</span>`).join('')}</div>`;
    };

    let haveHtml;
    if (!detected) {
      haveHtml = '<p class="career-detail__none">Run a resume analysis to see which of these skills you already have.</p>';
    } else {
      const have = (node.skills || []).filter((s) => detected.includes(String(s).toLowerCase()));
      const learn = (node.skills || []).filter((s) => !detected.includes(String(s).toLowerCase()));
      haveHtml = `
        ${chips(have, 'is-have', '')}
        ${have.length ? '' : '<p class="career-detail__none">None of this stage\u2019s core skills were detected in your resume yet.</p>'}
        ${learn.length ? `<p class="career-detail__learn-label">Skills to learn for this stage</p>${chips(learn, 'is-learn', '')}` : ''}
      `;
    }

    panel.innerHTML = `
      <div class="career-node-detail__head">
        <div>
          <span class="career-detail__level">${esc(node.level || 'Career stage')}</span>
          <h3 class="career-node-detail__title">${esc(node.title)}</h3>
          <p class="career-node-detail__desc">${esc(node.desc)}</p>
        </div>
        <div class="career-node-detail__meta">
          <span class="career-detail__badge">${esc(node.badge || '')}</span>
          <button type="button" class="button-ghost" data-career-detail-close aria-label="Close details">&times;</button>
        </div>
      </div>
      ${node.focus && node.focus.length ? `<p class="career-detail__learn-label">What to focus on at this stage</p>${chips(node.focus, 'is-focus', '')}` : ''}
      <p class="career-detail__learn-label">Core skills for this stage</p>
      ${chips(node.skills, '', 'No skill list available for this stage.')}
      <p class="career-detail__learn-label">Skills you already have</p>
      ${haveHtml}
      ${node.focusSkills && node.focusSkills.length ? `<p class="career-detail__learn-label">Skills to develop next</p>${chips(node.focusSkills, 'is-learn', '')}` : ''}
    `;
    panel.querySelector('[data-career-detail-close]')?.addEventListener('click', () => {
      careerFlowContainer.querySelectorAll('.career-node').forEach((n) => n.classList.remove('is-selected'));
      panel.remove();
    });
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // ─── INTERVIEW QUESTION GENERATOR ───
  const interviewCategory = $('[data-interview-category]');
  const interviewDifficulty = $('[data-interview-difficulty]');
  const interviewGenerate = $('[data-interview-generate]');
  const interviewRegenerate = $('[data-interview-regenerate]');
  const interviewCard = $('[data-interview-card]');
  const interviewStatus = $('[data-interview-status]');

  const INTERVIEW_QUESTIONS = {
    python: {
      easy: [
        { q: 'What is the difference between a list and a tuple in Python?', hint: 'Think about mutability and syntax.' },
        { q: 'What are Python decorators?', hint: 'Functions that modify other functions.' },
        { q: 'Explain the difference between append() and extend() for lists.', hint: 'One adds a single element, the other adds multiple.' },
        { q: 'What is a dictionary in Python?', hint: 'Key-value pair data structure.' },
      ],
      medium: [
        { q: 'Explain the Global Interpreter Lock (GIL) and its impact on multi-threading.', hint: 'Consider how it affects CPU-bound vs I/O-bound tasks.' },
        { q: 'What is the difference between deep copy and shallow copy?', hint: 'Think about nested objects and references.' },
        { q: 'How does Python manage memory?', hint: 'Reference counting and garbage collection.' },
        { q: 'Explain the use of __init__ and __new__ methods.', hint: 'One initializes, the other creates the instance.' },
      ],
      hard: [
        { q: 'Implement a context manager using both class-based and decorator-based approaches.', hint: 'Consider __enter__/__exit__ and contextlib.' },
        { q: 'Explain the descriptor protocol with a practical example.', hint: '__get__, __set__, and __delete__ methods.' },
        { q: 'How would you optimize a CPU-bound Python application?', hint: 'Think about multiprocessing, C extensions, and profiling.' },
      ],
    },
    web: {
      easy: [
        { q: 'What is the difference between HTML and HTML5?', hint: 'Semantic elements and new APIs.' },
        { q: 'Explain the box model in CSS.', hint: 'Content, padding, border, margin.' },
        { q: 'What is responsive web design?', hint: 'Designs that adapt to different screen sizes.' },
      ],
      medium: [
        { q: 'Explain the event loop in JavaScript.', hint: 'Call stack, callback queue, and non-blocking I/O.' },
        { q: 'What is CORS and why is it important?', hint: 'Cross-origin resource sharing and browser security.' },
        { q: 'Compare let, const, and var in JavaScript.', hint: 'Scope, hoisting, and reassignment.' },
      ],
      hard: [
        { q: 'How does the browser rendering pipeline work?', hint: 'Parse, style, layout, paint, composite.' },
        { q: 'Explain the Virtual DOM and how React uses it.', hint: 'Diffing algorithms and efficient updates.' },
        { q: 'How would you optimize a web application for performance?', hint: 'Lighthouse, bundling, lazy loading, caching.' },
      ],
    },
    'ai-ml': {
      easy: [
        { q: 'What is the difference between supervised and unsupervised learning?', hint: 'Labeled vs unlabeled data.' },
        { q: 'What is overfitting?', hint: 'Model performs well on training but poorly on new data.' },
        { q: 'What is a neural network?', hint: 'Connected layers of neurons.' },
      ],
      medium: [
        { q: 'Explain the bias-variance tradeoff.', hint: 'Underfitting vs overfitting.' },
        { q: 'What is cross-validation and why is it used?', hint: 'Assessing model generalization.' },
        { q: 'Compare bagging and boosting.', hint: 'Random Forest vs AdaBoost/Gradient Boosting.' },
      ],
      hard: [
        { q: 'Explain backpropagation with the chain rule.', hint: 'Gradient computation through layers.' },
        { q: 'How does a Transformer architecture work?', hint: 'Self-attention mechanisms.' },
        { q: 'What is the vanishing gradient problem and how do you address it?', hint: 'Activation functions and residual connections.' },
      ],
    },
    database: {
      easy: [
        { q: 'What is the difference between SQL and NoSQL databases?', hint: 'Relational vs non-relational.' },
        { q: 'What is a primary key?', hint: 'Unique identifier for a record.' },
        { q: 'What is normalization?', hint: 'Reducing data redundancy.' },
      ],
      medium: [
        { q: 'Explain the difference between INNER JOIN and LEFT JOIN.', hint: 'Matching rows vs all rows from left table.' },
        { q: 'What are database indexes and how do they work?', hint: 'B-tree structures for fast lookups.' },
        { q: 'What is ACID compliance?', hint: 'Atomicity, Consistency, Isolation, Durability.' },
      ],
      hard: [
        { q: 'How would you optimize a slow-running query?', hint: 'EXPLAIN plan, indexes, query rewriting.' },
        { q: 'Explain database sharding vs replication.', hint: 'Horizontal partitioning vs copying data.' },
        { q: 'What is the CAP theorem?', hint: 'Consistency, Availability, Partition tolerance.' },
      ],
    },
    networking: {
      easy: [
        { q: 'What is the difference between TCP and UDP?', hint: 'Reliable vs fast delivery.' },
        { q: 'What is an IP address?', hint: 'Network device identifier.' },
        { q: 'What is DNS?', hint: 'Domain name to IP translation.' },
      ],
      medium: [
        { q: 'Explain the OSI model layers.', hint: 'Physical to Application layer.' },
        { q: 'What is a firewall?', hint: 'Network security system.' },
        { q: 'What is the difference between a router and a switch?', hint: 'Inter-network vs intra-network.' },
      ],
      hard: [
        { q: 'Explain how HTTPS works.', hint: 'TLS handshake, certificates, encryption.' },
        { q: 'What is a VPN and how does it work?', hint: 'Encrypted tunnel over public networks.' },
        { q: 'Explain BGP and its role in the internet.', hint: 'Routing between autonomous systems.' },
      ],
    },
    hr: {
      easy: [
        { q: 'Tell me about yourself.', hint: 'Keep it professional and relevant to the role.' },
        { q: 'Why do you want to work here?', hint: 'Research the company and align with values.' },
        { q: 'What are your strengths?', hint: 'Pick 2-3 relevant strengths with examples.' },
      ],
      medium: [
        { q: 'Describe a challenging situation and how you handled it.', hint: 'Use the STAR method.' },
        { q: 'Where do you see yourself in 5 years?', hint: 'Show ambition aligned with the role.' },
        { q: 'How do you handle conflict in a team?', hint: 'Focus on communication and resolution.' },
      ],
      hard: [
        { q: 'What is your greatest weakness?', hint: 'Be honest but show improvement efforts.' },
        { q: 'Why should we hire you over other candidates?', hint: 'Highlight unique value you bring.' },
        { q: 'Describe a time you failed and what you learned.', hint: 'Show growth mindset and resilience.' },
      ],
    },
  };

  let currentInterviewQuestion = null;
  // Cycle questions without repeating until the pool is exhausted (rule #37).
  let interviewPool = [];
  let interviewPoolIdx = 0;

  function nextQuestionFromPool(cat, diff) {
    const key = `${cat}:${diff}`;
    const bank = INTERVIEW_QUESTIONS[cat]?.[diff] || INTERVIEW_QUESTIONS.python.medium;
    if (interviewPool.key !== key || interviewPool.items?.length !== bank.length) {
      interviewPool = { key, items: bank.slice() };
      // Deterministic first pass — Fisher-Yates shuffle so repeats only
      // happen after every question in the pool has been shown once.
      for (let i = interviewPool.items.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [interviewPool.items[i], interviewPool.items[j]] = [interviewPool.items[j], interviewPool.items[i]];
      }
      interviewPoolIdx = 0;
    }
    if (interviewPoolIdx >= interviewPool.items.length) interviewPoolIdx = 0; // full cycle done — reshuffle order
    return interviewPool.items[interviewPoolIdx++];
  }

  /** Render a question with a hidden-by-default answer guide (rule #38). */
  function renderInterviewCard(item, cat, diff) {
    if (!interviewCard) return;
    interviewCard.innerHTML = `
      <div class="list-card interview-question">
        <div>
          <span class="interview-question__category">${esc(cat.replace('-', ' '))}</span>
          <span class="interview-question__difficulty interview-question__difficulty--${esc(diff)}">${esc(diff)}</span>
          <p class="interview-question__text">${esc(item.q)}</p>
          <button type="button" class="button-ghost interview-answer-toggle" data-answer-toggle aria-expanded="false">Show Answer Guide</button>
          <div class="interview-question__guide hidden" data-answer-guide>${item.hint ? `<p><strong>Guide:</strong> ${esc(item.hint)}</p>` : '<p>No guide available for this question.</p>'}</div>
        </div>
      </div>
    `;
    const toggle = interviewCard.querySelector('[data-answer-toggle]');
    const guide = interviewCard.querySelector('[data-answer-guide]');
    toggle?.addEventListener('click', () => {
      const open = guide.classList.toggle('hidden') === false;
      toggle.setAttribute('aria-expanded', String(open));
      toggle.textContent = open ? 'Hide Answer Guide' : 'Show Answer Guide';
    });
  }

  function generateInterviewQuestion() {
    if (!interviewCard) return null;
    const cat = interviewCategory?.value || 'python';
    const diff = interviewDifficulty?.value || 'medium';
    const q = nextQuestionFromPool(cat, diff);
    currentInterviewQuestion = q;
    renderInterviewCard(q, cat, diff);
    if (interviewStatus) interviewStatus.textContent = 'Generated';
    return q;
  }

  // Interview question navigation: keep a local run history so Prev/Next can
  // revisit already-generated questions (static bank, no extra requests).
  const interviewHistory = [];
  let interviewIndex = -1;
  const interviewNavTemplate = (item, cat, diff) => {
    const wrap = document.createElement('div');
    wrap.innerHTML = `<div class="list-card"><div><span class="interview-question__category">${esc(cat.replace('-', ' '))}</span><span class="interview-question__difficulty interview-question__difficulty--${esc(diff)}">${esc(diff)}</span></div></div>`;
    const holder = wrap.firstElementChild.firstElementChild;
    const text = document.createElement('p');
    text.className = 'interview-question__text';
    text.textContent = item.q;
    holder.appendChild(text);
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'button-ghost interview-answer-toggle';
    toggle.setAttribute('aria-expanded', 'false');
    toggle.textContent = 'Show Answer Guide';
    const guide = document.createElement('div');
    guide.className = 'interview-question__guide hidden';
    const guideP = document.createElement('p');
    guideP.innerHTML = `<strong>Guide:</strong> `;
    guideP.appendChild(document.createTextNode(item.hint || 'No guide available for this question.'));
    guide.appendChild(guideP);
    holder.appendChild(toggle);
    holder.appendChild(guide);
    toggle.addEventListener('click', () => {
      const open = guide.classList.toggle('hidden') === false;
      toggle.setAttribute('aria-expanded', String(open));
      toggle.textContent = open ? 'Hide Answer Guide' : 'Show Answer Guide';
    });
    return wrap.innerHTML;
  };
  function showInterviewAt(i) {
    if (!interviewCard || !interviewHistory.length) return;
    interviewIndex = Math.max(0, Math.min(interviewHistory.length - 1, i));
    const entry = interviewHistory[interviewIndex];
    interviewCard.innerHTML = interviewNavTemplate(entry.item, entry.cat, entry.diff);
    if (interviewStatus) interviewStatus.textContent = `Question ${interviewIndex + 1} of ${interviewHistory.length}`;
  }
  if (interviewGenerate) {
    interviewGenerate.addEventListener('click', () => {
      generateInterviewQuestion(); // existing renderer (also sets currentInterviewQuestion)
      if (currentInterviewQuestion) {
        const cat = interviewCategory?.value || 'python';
        const diff = interviewDifficulty?.value || 'medium';
        interviewHistory.push({ item: currentInterviewQuestion, cat, diff });
        interviewIndex = interviewHistory.length - 1;
        if (interviewStatus) interviewStatus.textContent = `Question ${interviewIndex + 1} of ${interviewHistory.length}`;
      }
    });
  }
  if (interviewRegenerate) {
    interviewRegenerate.addEventListener('click', () => {
      generateInterviewQuestion();
      if (currentInterviewQuestion) {
        const cat = interviewCategory?.value || 'python';
        const diff = interviewDifficulty?.value || 'medium';
        // Replace the current question in the run history, or start a new run
        // when Regenerate is pressed before any Generate (was a no-op entry).
        if (interviewIndex >= 0 && interviewIndex < interviewHistory.length) {
          interviewHistory[interviewIndex] = { item: currentInterviewQuestion, cat, diff };
        } else {
          interviewHistory.push({ item: currentInterviewQuestion, cat, diff });
          interviewIndex = interviewHistory.length - 1;
        }
        if (interviewStatus) interviewStatus.textContent = `Question ${interviewIndex + 1} of ${interviewHistory.length}`;
      }
    });
  }
  document.querySelector('[data-interview-next]')?.addEventListener('click', () => showInterviewAt(interviewIndex + 1));
  document.querySelector('[data-interview-prev]')?.addEventListener('click', () => showInterviewAt(interviewIndex - 1));
  document.querySelector('[data-interview-reset]')?.addEventListener('click', () => {
    interviewHistory.length = 0;
    interviewIndex = -1;
    if (interviewCard) interviewCard.innerHTML = '<div class="list-card is-placeholder"><div><strong>Ready to practice</strong><p>Select a category and click Generate to get started.</p></div></div>';
    if (interviewStatus) interviewStatus.textContent = 'Practice reset.';
  });
  if (interviewCategory) {
    interviewCategory.addEventListener('change', () => { if (currentInterviewQuestion) generateInterviewQuestion(); });
  }
  if (interviewDifficulty) {
    interviewDifficulty.addEventListener('change', () => { if (currentInterviewQuestion) generateInterviewQuestion(); });
  }

  // ─── RESUME PREVIEW (FileReader) ───
  const resumePreview = $('[data-resume-preview]');
  const resumePreviewInfo = $('[data-resume-preview-info]');
  const resumePreviewContent = $('[data-resume-preview-content]');
  const resumePreviewClose = $('[data-resume-preview-close]');

  function showResumePreview(file) {
    if (!resumePreview || !file) return;
    const sizeKB = Math.round(file.size / 1024);
    const ext = file.name.split('.').pop()?.toUpperCase() || file.type || 'Unknown';
    resumePreviewInfo.innerHTML = `<strong>${file.name}</strong> · ${sizeKB} KB · ${ext}`;
    resumePreviewContent.style.display = 'none';
    resumePreviewContent.textContent = '';
    resumePreview.classList.remove('hidden');

    // Only read TXT files directly in the browser
    if (file.type === 'text/plain' || /\.txt$/i.test(file.name)) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target?.result || '';
        resumePreviewContent.textContent = text.slice(0, 5000); // Limit preview
        resumePreviewContent.style.display = 'block';
      };
      reader.onerror = () => { resumePreviewContent.textContent = 'Could not read file content.'; resumePreviewContent.style.display = 'block'; };
      reader.readAsText(file);
    }
  }

  if (resumePreviewClose) {
    resumePreviewClose.addEventListener('click', () => {
      resumePreview?.classList.add('hidden');
    });
  }

  // The preview is opened from the file-input 'change' and dropzone 'drop'
  // handlers (see the Upload section), so it works on every page that has a
  // resume upload control. The old wrapper here reassigned handleFileSelect
  // *after* its listener was already registered — the preview call never ran.

  // ═══ DASHBOARD: SIDEBAR ═══
  const dashSidebar = $('[data-dash-sidebar]');
  const dashSidebarToggle = $('[data-dash-sidebar-toggle]');
  const dashSidebarBackdrop = $('[data-dash-sidebar-backdrop]');
  const dashSidebarCollapse = $('[data-dash-sidebar-collapse]');

  // ── Page-based navigation ──
  const DASH_PAGES = [
    'dashboard', 'resume-analysis', 'skill-extraction', 'skill-gap',
    'career-risk', 'job-matching', 'career-path', 'reskilling',
    'interview', 'ai-assistant', 'reports', 'history', 'profile', 'settings'
  ];
  let currentPage = 'dashboard';

  function navigateToSection(pageId) {
    if (!pageId || !DASH_PAGES.includes(pageId)) return;
    currentPage = pageId;
    save(STORAGE.lastPage, pageId); // remembered for the "last visited" startup option
    document.querySelectorAll('.dash-page').forEach(p => p.classList.toggle('is-active', p.dataset.page === pageId));
    document.querySelectorAll('.dash-nav-item').forEach(n => n.classList.toggle('is-active', n.dataset.pageTarget === pageId));
    const page = document.querySelector(`.dash-page[data-page="${pageId}"]`);
    if (page) {
      page.style.animation = 'none';
      void page.offsetWidth;
      page.style.animation = '';
    }
    // Update phase indicator
    const phaseIdx = DASH_PAGES.indexOf(pageId) + 1;
    document.querySelectorAll('.dash-phase-indicator').forEach(el => { el.textContent = `Phase ${phaseIdx} of ${DASH_PAGES.length}`; });
    // Back disabled on the first page, Next disabled on the last — the label is
    // derived from the SAME navigation state, never hardcoded (Part R).
    document.querySelectorAll('[data-phase-back]').forEach(btn => { btn.disabled = phaseIdx <= 1; });
    document.querySelectorAll('[data-phase-next]').forEach(btn => { btn.disabled = phaseIdx >= DASH_PAGES.length; });
    renderTopbarCrumbs(pageId); // breadcrumb: Dashboard / <page>
    // Refresh the History page from the server each time it is opened, so a
    // newly completed analysis (which the server has already recorded) shows
    // without a full page reload.
    if (pageId === 'history') loadServerHistory();
    // Close mobile sidebar if open
    if (window.innerWidth <= 900 && dashSidebar?.classList.contains('is-open')) toggleSidebar();
  }

  // Sidebar nav click handlers
  document.querySelectorAll('.dash-nav-item[data-page-target]').forEach(item => {
    item.addEventListener('click', e => {
      e.preventDefault();
      navigateToSection(item.dataset.pageTarget);
    });
  });

  // Phase navigation
  document.querySelectorAll('[data-phase-back]').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = DASH_PAGES.indexOf(currentPage);
      if (idx > 0) navigateToSection(DASH_PAGES[idx - 1]);
    });
  });
  document.querySelectorAll('[data-phase-next]').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = DASH_PAGES.indexOf(currentPage);
      if (idx < DASH_PAGES.length - 1) navigateToSection(DASH_PAGES[idx + 1]);
    });
  });

  // Analyze Resume button
  document.querySelectorAll('[data-dash-action="analyze"]').forEach(btn => {
    btn.addEventListener('click', () => navigateToSection('resume-analysis'));
  });

  // View Full Report button → Reports page (was dead: no listener)
  document.querySelectorAll('[data-dash-action="report"]').forEach(btn => {
    btn.addEventListener('click', () => navigateToSection('reports'));
  });

  // Notifications bell → acknowledgement toast (button previously did nothing)
  document.querySelectorAll('[data-dash-notifications]').forEach(btn => {
    btn.addEventListener('click', () => toast('No new notifications.', 'info', 3000));
  });

  // Skill-distribution filter (workspace dashboard) — re-renders the pie chart
  // with the selected skill category using the last analysis data.
  const SKILL_FILTER_KEYS = { all: 'All skills', technical: 'Technical skills', soft: 'Soft skills' };
  document.querySelectorAll('[data-skill-filter]').forEach(sel => {
    sel.addEventListener('change', () => {
      if (!lastAnalysis) { toast('Run an analysis first.', 'warning'); sel.value = 'all'; return; }
      const byCat = (lastAnalysis.skills && lastAnalysis.skills.by_category) || {};
      const cats = Object.keys(byCat);
      if (!cats.length) { toast('No categorized skills available.', 'info'); return; }
      const kind = sel.value;
      const picked = kind === 'all'
        ? cats
        : cats.filter((c) => (kind === 'soft' ? /soft|business/i : !/soft|business/i).test(c));
      const skillMap = {};
      picked.forEach((c) => (byCat[c] || []).forEach((s) => { skillMap[s] = (skillMap[s] || 0) + 1; }));
      const canvas = $('[data-skill-pie-chart]');
      drawPieChart(canvas, skillMap);
      const legend = $('[data-skill-pie-legend]');
      const entries = Object.entries(skillMap);
      const total = entries.reduce((a, [, v]) => a + v, 0) || 1;
      if (legend) {
        legend.innerHTML = entries.map(([s, v], i) => `<div class="chart-legend-row"><span class="chart-legend-item"><span class="chart-legend-dot" style="background:${PIE_COLORS[i % PIE_COLORS.length]};"></span>${esc(s)}</span><span class="chart-legend-pct">${Math.round((v / total) * 100)}%</span></div>`).join('')
          || '<span class="chart-legend-item">No skills in this category</span>';
      }
      const totalEl = document.querySelector('[data-skill-total]');
      if (totalEl) totalEl.textContent = String(entries.reduce((a, [, v]) => a + v, 0));
      void SKILL_FILTER_KEYS; // labels kept for future UI copy
    });
  });

  // Sidebar toggle
  function toggleSidebar() {
    if (!dashSidebar) return;
    const open = dashSidebar.classList.toggle('is-open');
    dashSidebarBackdrop?.classList.toggle('is-visible', open);
    if (dashSidebarToggle) dashSidebarToggle.setAttribute('aria-expanded', String(open));
  }
  if (dashSidebarToggle) dashSidebarToggle.addEventListener('click', toggleSidebar);
  if (dashSidebarBackdrop) dashSidebarBackdrop.addEventListener('click', () => dashSidebar?.classList.remove('is-open'));

  // Sidebar collapse (desktop)
  if (dashSidebarCollapse) {
    // Restore the saved collapse preference (workspace only)
    if (document.querySelector('[data-dash-layout]') && load(STORAGE.sidebarCollapsed, '0') === '1') {
      dashSidebar.classList.add('is-collapsed');
      dashSidebarCollapse.textContent = '▶';
      dashSidebarCollapse.setAttribute('aria-label', 'Expand sidebar');
    }
    dashSidebarCollapse.addEventListener('click', () => {
      dashSidebar.classList.toggle('is-collapsed');
      const collapsed = dashSidebar.classList.contains('is-collapsed');
      dashSidebarCollapse.textContent = collapsed ? '▶' : '◀';
      dashSidebarCollapse.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
      // Remember the preference so it survives a refresh
      if (document.querySelector('[data-dash-layout]')) {
        save(STORAGE.sidebarCollapsed, collapsed ? '1' : '0');
        const pref = document.querySelector('[data-dash-sidebar-collapsed-pref]');
        if (pref) pref.checked = collapsed;
      }
    });
  }

  // Sidebar nav active state on scroll — HOME PAGE ONLY.
  // This scroll-spy matched section ids (#welcome, #analysis …) that do not
  // exist on the workspace dashboard and re-ran on every scroll event,
  // overwriting the is-active state set by navigateToSection(). Both pages
  // share this bundle, so the spy disables itself inside the workspace layout.
  const dashNavItems = $$('.dash-nav-item');
  const dashSections = ['welcome', 'analysis', 'skills-gap', 'risk-meter', 'job-dashboard', 'statistics'];
  const updateDashNav = () => {
    if (document.querySelector('[data-dash-layout]')) return; // workspace: page-based nav owns is-active
    const scrollPos = window.scrollY + 120;
    let current = 'welcome';
    for (const id of dashSections) {
      const el = document.getElementById(id);
      if (el && el.offsetTop <= scrollPos) current = id;
    }
    dashNavItems.forEach(item => item.classList.toggle('is-active', item.getAttribute('href') === '#' + current));
  };
  window.addEventListener('scroll', updateDashNav, { passive: true });
  updateDashNav();

  // ═══ WORKPLACE: SKILLS GAP ═══
  // Note: skills-gap-role, skills-gap-form, skills-gap-submit, skills-gap-loading,
  // skills-gap-error, skills-gap-results are now the same IDs as the home page
  // since home and workplace are separate pages. The original handlers at lines
  // 1153-1285 will work for both pages. No duplicate handler needed.

  // ═══ WORKPLACE: AI CHAT ═══
  // Connected to the real chat API (routes/chat.py):
  //   POST /api/chat/conversations                        → create conversation
  //   POST /api/chat/conversations/<id>/messages          → { reply }
  // The previous handler posted to /api/chat, which does not exist.
  const wpChatForm = document.getElementById('wp-chat-form');
  const wpChatInput = document.getElementById('wp-chat-input');
  const wpChatMessages = document.getElementById('wp-chat-messages');
  let wpConversationId = null;

  const wpAppendMessage = (who, text) => {
    if (!wpChatMessages) return null;
    const card = document.createElement('div');
    card.className = 'list-card';
    const head = document.createElement('div');
    const name = document.createElement('strong');
    name.textContent = who;
    const body = document.createElement('p');
    body.textContent = text; // textContent — user/LLM text must never be injected as HTML
    head.appendChild(name);
    card.appendChild(head);
    card.appendChild(body);
    wpChatMessages.appendChild(card);
    wpChatMessages.scrollTop = wpChatMessages.scrollHeight;
    return card; // lets the caller update the card in place (e.g. Thinking... → reply)
  };

  let wpSending = false; // blocks double-send while a request is in flight
  /** Compact, privacy-safe analysis context for the workspace chat (Part K).
   *  Built ONLY from the last real analysis snapshot — no secrets, no resume
   *  text. Lets the assistant answer "What skills am I missing?" etc. from
   *  the user's actual results instead of generic advice. */
  const wpAnalysisContext = () => {
    if (!lastAnalysis) return '';
    const skills = ((lastAnalysis.reasoning || {}).skills_detected || []);
    const roles = dedupeRoles(lastAnalysis.top_roles || []).slice(0, 3);
    const learning = (lastAnalysis.roadmap || []).slice(0, 3)
      .map((c) => c.skill || c.course).filter(Boolean);
    const lines = [
      'User context (from their latest resume analysis in this workspace):',
      `- Automation risk: ${Math.round((lastAnalysis.risk_score || 0) * 100)}% (${lastAnalysis.risk_label || 'unknown'})`,
      skills.length ? `- Detected skills: ${skills.slice(0, 10).join(', ')}` : '',
      roles.length ? `- Top role matches: ${roles.map((r) => `${r.job_role} (${Math.round((r.similarity || 0) * 100)}% match)`).join('; ')}` : '',
      learning.length ? `- Recommended next learning: ${learning.join(', ')}` : '',
    ].filter(Boolean);
    return lines.join('\n');
  };
  async function wpSendChat(message) {
    if (wpSending) return; // ignore sends while the same request is processing
    wpSending = true;
    const sendBtn = wpChatForm?.querySelector('button[type="submit"]');
    if (sendBtn) sendBtn.disabled = true;
    wpAppendMessage('You', message);
    const thinking = wpAppendMessage('AI Assistant', 'Thinking...');
    try {
      // Lazily create a conversation the first time (chat API is per-user).
      if (!wpConversationId) {
        const created = await apiPost('/api/chat/conversations', { title: 'Workspace chat' });
        const d = await created.json();
        if (!d.success || !d.conversation?.id) throw new Error(d.error || 'Could not start a conversation.');
        wpConversationId = d.conversation.id;
      }
      const res = await apiPost(`/api/chat/conversations/${wpConversationId}/messages`, { message, context: wpAnalysisContext() });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'The assistant could not reply.');
      if (thinking?.querySelector('p')) thinking.querySelector('p').textContent = data.reply || 'Sorry, I could not process that.';
      else wpAppendMessage('AI Assistant', data.reply || 'Sorry, I could not process that.');
    } catch (err) {
      if (thinking?.querySelector('p')) thinking.querySelector('p').textContent = `Error: ${err.message || 'Unable to reach the AI assistant.'}`;
      else wpAppendMessage('Error', err.message || 'Unable to reach the AI assistant.');
    } finally {
      wpSending = false;
      if (sendBtn) sendBtn.disabled = false;
      wpChatInput?.focus();
    }
  }

  if (wpChatForm && wpChatInput) {
    wpChatForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const msg = wpChatInput.value.trim();
      if (!msg) return;
      wpChatInput.value = '';
      wpSendChat(msg);
    });
  }

  // Chat suggestions
  document.querySelectorAll('[data-chat-suggestion]').forEach(btn => {
    btn.addEventListener('click', () => {
      const prompt = btn.dataset.chatSuggestion;
      if (prompt) wpSendChat(prompt);
    });
  });

  // ═══ WORKPLACE: DASHBOARD NAV LINKS ═══
  // Delegated listener: also covers links rendered later (e.g. the
  // "View Details →" anchors inside dynamically rendered top-job cards).
  document.addEventListener('click', e => {
    const link = e.target.closest('[data-dash-nav-link]');
    if (!link) return;
    e.preventDefault();
    navigateToSection(link.dataset.dashNavLink);
  });

  // ═══ WORKPLACE: TOP JOBS RENDERING ═══
  function renderTopJobs() {
    const container = document.querySelector('[data-dash-top-jobs]');
    if (!container) return;
    const jobs = jmJobs.slice(0, 3);
    if (!jobs.length) {
      container.innerHTML = '<div class="list-card is-placeholder"><div><strong>No recommendations yet</strong><p>Run a resume analysis to see your top career matches.</p></div></div>';
      return;
    }
    container.innerHTML = jobs.map(job => `
      <div class="dash-job-card">
        <span class="dash-job-card__icon">💼</span>
        <div class="dash-job-card__body">
          <h4 class="dash-job-card__title">${esc(job.title)}</h4>
          <div class="dash-job-card__meta">
            <span class="dash-job-card__badge">${job.score}% Match</span>
            ${job.risk_level ? `<span class="dash-job-card__badge" style="background:rgba(251,191,36,0.12);color:#fbbf24;">${normalizeRisk(job.risk_level)} Risk</span>` : ''}
          </div>
          ${(job.skills || []).length ? `<div class="dash-job-card__skills">${job.skills.slice(0, 3).map(s => `<span class="dash-job-card__skill">${esc(s)}</span>`).join('')}</div>` : ''}
        </div>
        <a href="#" class="dash-job-card__cta" data-dash-nav-link="job-matching">View Details →</a>
      </div>
    `).join('');
  }

  // ═══ WORKPLACE: DASHBOARD MINI ROADMAP (real data only) ═══
  // The dashboard previously showed hard-coded sample stages even before any
  // analysis — replaced with an empty state until real roadmap data exists.
  function renderReskillingMini(payload) {
    const container = document.querySelector('[data-dash-roadmap-mini]');
    if (!container) return;
    const stages = (payload.roadmap || []).slice(0, 4);
    if (!stages.length) {
      container.innerHTML = '<div class="list-card is-placeholder"><div><strong>No reskilling plan yet</strong><p>Run a resume analysis to build your personalized learning roadmap.</p></div></div>';
      return;
    }
    container.innerHTML = stages.map((c, i) => `
      <div class="dash-roadmap-item">
        <span class="dash-roadmap-num">${i + 1}</span>
        <div><strong>${esc(c.course || 'Learning step')}</strong><p>${esc(c.skill || '')}${c.reason ? ` — ${esc(c.reason)}` : ''}</p></div>
        ${c.url ? `<a class="button-ghost" href="${esc(c.url)}" target="_blank" rel="noreferrer">Open</a>` : ''}
      </div>
    `).join('');
  }

  // Reports page "Reskilling Recommendations" panel — mirrors the learning
  // actions already computed by nextSteps() into the Reports grid.
  function renderReportReskilling(payload) {
    const container = document.querySelector('[data-report-reskilling]');
    if (!container) return;
    const g = payload.guided_next_steps || fallbackSteps(payload);
    const actions = (g.learning_actions || []).slice(0, 4);
    if (!actions.length) {
      container.innerHTML = '<div class="list-card is-placeholder"><div><strong>No reskilling actions yet</strong><p>Run an analysis to generate your learning plan.</p></div></div>';
      return;
    }
    container.innerHTML = actions.map((a) => `<div class="list-card"><div><strong>Learning action</strong><p>${esc(a)}</p></div></div>`).join('');
  }

  // ═══ WORKPLACE: CAREER PROFILE (Account → Profile page) ═══
  // Connected to the real backend: GET/POST /api/profile, backed by the
  // user_profiles table. Uses the existing form styles — no redesign.
  const PROFILE_FIELD_CAPS = {
    education: 120,
    occupation: 120,
    experience_level: 40,
    preferred_roles: 255,
    preferred_industry: 120,
    skills: 500,
    career_goal: 2000,
  };
  const profileForm = document.getElementById('career-profile-form');
  const profileSaveBtn = document.querySelector('[data-profile-save]');
  const profileStatus = document.querySelector('[data-profile-status]');

  async function loadCareerProfile() {
    if (!profileForm) return;
    try {
      const res = await fetch('/api/profile');
      if (!res.ok) return;
      const d = await res.json();
      if (!d.success || !d.profile) return;
      Object.entries(PROFILE_FIELD_CAPS).forEach(([field]) => {
        const el = profileForm.querySelector(`[data-profile-field="${field}"]`);
        if (el && d.profile[field] != null) el.value = d.profile[field];
      });
    } catch { /* profile stays empty — non-critical */ }
  }

  if (profileForm && profileSaveBtn) {
    profileForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {};
      Object.entries(PROFILE_FIELD_CAPS).forEach(([field, cap]) => {
        const el = profileForm.querySelector(`[data-profile-field="${field}"]`);
        const v = (el?.value || '').trim().slice(0, cap);
        if (v) payload[field] = v;
      });
      if (!Object.keys(payload).length) {
        if (profileStatus) profileStatus.textContent = 'Add at least one field before saving.';
        return;
      }
      const original = profileSaveBtn.textContent;
      profileSaveBtn.disabled = true;
      profileSaveBtn.textContent = 'Saving…';
      if (profileStatus) profileStatus.textContent = '';
      try {
        const res = await apiPost('/api/profile', payload);
        const d = await res.json();
        if (!d.success) throw new Error(d.error || 'Could not save your profile.');
        if (profileStatus) profileStatus.textContent = 'Saved ✓';
        toast('Career profile saved.', 'success');
      } catch (err) {
        if (profileStatus) profileStatus.textContent = err.message || 'Save failed.';
        toast(err.message || 'Could not save profile.', 'error');
      } finally {
        profileSaveBtn.disabled = false;
        profileSaveBtn.textContent = original;
      }
    });
    loadCareerProfile(); // populate the form on page load
  }

  // ═══ WORKPLACE: ANALYSIS HISTORY (server-backed) ═══
  // Loads the user's real analysis records from /api/history (the same
  // uploads table every completed analysis already writes to) and falls back
  // to device-local snapshots only when the server has nothing or is
  // unreachable. Deleting a server row uses DELETE /api/history/<id>.
  // `null` means "not loaded yet" so the local fallback renders until the
  // fetch resolves; `[]` means "loaded, genuinely empty".
  let serverHistory = null;
  let serverHistoryError = '';

  /** Fetch the server-side analysis history once, then re-render. */
  async function loadServerHistory() {
    const errEl = document.querySelector('[data-history-error]');
    try {
      const res = await fetch('/api/history?limit=30', { headers: { Accept: 'application/json' } });
      const data = await res.json().catch(() => null);
      if (res.ok && data && data.success) {
        serverHistory = Array.isArray(data.history) ? data.history : [];
        serverHistoryError = '';
      } else {
        serverHistory = null;
        serverHistoryError = (data && data.error) || 'Could not load your saved history.';
      }
    } catch {
      serverHistory = null;
      serverHistoryError = 'Could not reach the server — showing this device\u2019s history.';
    }
    if (errEl) {
      errEl.textContent = serverHistoryError;
      errEl.classList.toggle('hidden', !serverHistoryError);
    }
    renderHistory();
  }

  /** Render the server rows when present, otherwise the local snapshots. */
  function renderHistory() {
    const container = document.querySelector('[data-history-list]');
    if (!container) return;

    // Prefer the authoritative server rows.
    if (Array.isArray(serverHistory) && serverHistory.length) {
      container.innerHTML = '';
      serverHistory.forEach((entry) => {
        const riskLabel = entry.risk_label ? normalizeRisk(entry.risk_label) : riskFromScore(entry.risk_score);
        const riskPct = Math.round((Number(entry.risk_score) || 0) * 100);
        const when = entry.created_at ? new Date(entry.created_at) : null;
        const whenText = when && !Number.isNaN(when.getTime())
          ? when.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
          : 'Unknown date';
        const skillCount = (entry.skills || []).length;
        const card = document.createElement('div');
        card.className = 'list-card history-row';
        card.innerHTML = `
          <div>
            <strong>${esc(entry.filename || 'Resume analysis')} · ${esc(entry.mode || 'standard')} mode</strong>
            <p>${esc(whenText)} · Risk ${riskPct}% (${esc(riskLabel)})${skillCount ? ` · ${skillCount} skills` : ''}</p>
          </div>
          <span class="status-pill">Saved</span>
        `;
        const actions = document.createElement('div');
        actions.className = 'history-row__actions';
        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'button-ghost';
        delBtn.textContent = 'Delete';
        delBtn.setAttribute('aria-label', 'Delete this saved analysis');
        delBtn.addEventListener('click', async () => {
          // Two-step inline confirmation (no destructive action without intent)
          if (delBtn.dataset.confirming !== '1') {
            delBtn.dataset.confirming = '1';
            delBtn.textContent = 'Confirm?';
            setTimeout(() => { delBtn.dataset.confirming = '0'; delBtn.textContent = 'Delete'; }, 4000);
            return;
          }
          delBtn.disabled = true;
          try {
            const res = await fetch(`/api/history/${entry.id}`, {
              method: 'DELETE',
              headers: { 'X-CSRFToken': csrfToken },
            });
            if (!res.ok) throw new Error('delete failed');
            serverHistory = serverHistory.filter((r) => r.id !== entry.id);
            toast('History entry deleted.', 'info');
            renderHistory();
          } catch {
            delBtn.disabled = false;
            delBtn.dataset.confirming = '0';
            delBtn.textContent = 'Delete';
            toast('Could not delete that entry. Please try again.', 'error', 6000);
          }
        });
        actions.append(delBtn);
        card.appendChild(actions);
        container.appendChild(card);
      });
      return;
    }

    // Fallback: device-local snapshots (also shown before the fetch resolves).
    const hist = loadJSON(STORAGE.history, []);
    const entries = Array.isArray(hist) ? hist : [];
    if (!entries.length) {
      container.innerHTML = '<div class="list-card is-placeholder"><div><strong>No history yet</strong><p>Your analysis history will appear here after your first resume analysis.</p></div></div>';
      return;
    }
    container.innerHTML = '';
    entries.forEach((entry, idx) => {
      const riskLabel = entry.risk_label ? normalizeRisk(entry.risk_label) : riskFromScore(entry.risk_score);
      const riskPct = Math.round((Number(entry.risk_score) || 0) * 100);
      const when = entry.saved_at ? new Date(entry.saved_at) : null;
      const whenText = when && !Number.isNaN(when.getTime())
        ? when.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
        : 'Unknown date';
      const roleCount = (entry.roles || []).length;
      const topRole = roleCount ? entry.roles[0].title : '';
      const card = document.createElement('div');
      card.className = 'list-card history-row';
      card.innerHTML = `
        <div>
          <strong>Analysis · ${esc(entry.mode || 'standard')} mode</strong>
          <p>${esc(whenText)} · Risk ${riskPct}% (${esc(riskLabel)})${topRole ? ` · Top match: ${esc(topRole)}` : ''}</p>
        </div>
        <span class="status-pill">${roleCount ? `${roleCount}+ matches` : 'No matches'}</span>
      `;
      const actions = document.createElement('div');
      actions.className = 'history-row__actions';
      const viewBtn = document.createElement('button');
      viewBtn.type = 'button';
      viewBtn.className = 'button-ghost';
      viewBtn.textContent = 'View';
      viewBtn.setAttribute('aria-label', 'View the latest analysis in Reports');
      viewBtn.addEventListener('click', () => navigateToSection('reports'));
      const delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.className = 'button-ghost';
      delBtn.textContent = 'Delete';
      delBtn.setAttribute('aria-label', 'Delete this history entry');
      delBtn.addEventListener('click', () => {
        // Two-step inline confirmation (no destructive action without intent)
        if (delBtn.dataset.confirming !== '1') {
          delBtn.dataset.confirming = '1';
          delBtn.textContent = 'Confirm?';
          setTimeout(() => { delBtn.dataset.confirming = '0'; delBtn.textContent = 'Delete'; }, 4000);
          return;
        }
        const fresh = loadJSON(STORAGE.history, []);
        if (Array.isArray(fresh)) {
          fresh.splice(idx, 1); // idx is valid because the list re-renders after every change
          saveJSON(STORAGE.history, fresh);
        }
        toast('History entry deleted.', 'info');
        renderHistory();
      });
      actions.append(viewBtn, delBtn);
      card.appendChild(actions);
      container.appendChild(card);
    });
  }

  // ═══ WORKPLACE: TOPBAR BREADCRUMB ═══
  const DASH_PAGE_LABELS = {
    'dashboard': 'Dashboard', 'resume-analysis': 'Resume Analysis', 'skill-extraction': 'Skill Extraction',
    'skill-gap': 'Skill Gap Analysis', 'career-risk': 'Career Risk', 'job-matching': 'Job Matching',
    'career-path': 'Career Path', 'reskilling': 'Reskilling Roadmap', 'interview': 'Interview Preparation',
    'ai-assistant': 'AI Career Assistant', 'reports': 'Reports', 'history': 'History',
    'profile': 'Profile', 'settings': 'Settings',
  };
  function renderTopbarCrumbs(pageId) {
    const crumbs = document.querySelector('[data-dash-crumbs]');
    if (!crumbs) return;
    const label = DASH_PAGE_LABELS[pageId] || 'Dashboard';
    crumbs.innerHTML = pageId === 'dashboard'
      ? '<span class="dash-topbar__crumb-current">Dashboard</span>'
      : '<button type="button" class="dash-topbar__crumb-link" data-crumb-root>Dashboard</button><span class="dash-topbar__crumb-sep" aria-hidden="true">/</span><span class="dash-topbar__crumb-current">' + esc(label) + '</span>';
    const root = crumbs.querySelector('[data-crumb-root]');
    root?.addEventListener('click', () => navigateToSection('dashboard'));
  }

  // ═══ WORKSPACE: SETTINGS PREFERENCES SYNC ═══
  // The theme select drives the SAME auto/light/dark preference as the
  // existing toggles; the sidebar checkbox reuses the collapse button so the
  // persisted preference stays in one place.
  function initWorkspaceExtras() {
    if (!document.querySelector('[data-dash-layout]')) return; // workspace page only
    renderTopbarCrumbs(currentPage);
    renderHistory(); // instant local render; server rows replace it when they arrive
    loadServerHistory(); // authoritative /api/history rows (falls back to local on error)
    const themeSelect = document.querySelector('[data-dash-theme-mode]');
    if (themeSelect) {
      themeSelect.value = MODE_CYCLE.includes(themeMode) ? themeMode : 'auto';
      themeSelect.addEventListener('change', () => {
        themeMode = themeSelect.value;
        save(STORAGE.theme, themeMode);
        applyTheme(themeMode);
        syncWpThemeIcon();
        toast(`Theme set to ${MODE_LABELS[themeMode]}.`, 'info', 2500);
      });
    }
    const collapsedPref = document.querySelector('[data-dash-sidebar-collapsed-pref]');
    if (collapsedPref) {
      collapsedPref.checked = load(STORAGE.sidebarCollapsed, '0') === '1';
      collapsedPref.addEventListener('change', () => {
        if (!dashSidebar) return;
        if (collapsedPref.checked === dashSidebar.classList.contains('is-collapsed')) return;
        dashSidebarCollapse?.click(); // reuse the existing collapse handler (keeps persistence)
      });
    }

    // ─── Display preferences (density / animations) ───
    const densitySelect = document.querySelector('[data-dash-density]');
    if (densitySelect) {
      densitySelect.value = load(STORAGE.density, 'comfortable');
      densitySelect.addEventListener('change', () => {
        const v = densitySelect.value === 'compact' ? 'compact' : 'comfortable';
        save(STORAGE.density, v);
        if (v === 'compact') html.setAttribute('data-density', 'compact');
        else html.removeAttribute('data-density');
        toast(`Card density: ${v}.`, 'info', 2500);
      });
    }
    const animSelect = document.querySelector('[data-dash-anim]');
    if (animSelect) {
      animSelect.value = load(STORAGE.anim, 'on');
      animSelect.addEventListener('change', () => {
        const v = animSelect.value === 'off' ? 'off' : 'on';
        save(STORAGE.anim, v);
        if (v === 'off') html.setAttribute('data-anim', 'off');
        else html.removeAttribute('data-anim');
        toast(v === 'off' ? 'Animations reduced.' : 'Animations enabled.', 'info', 2500);
      });
    }
    const toastSel = document.querySelector('[data-dash-toast-duration]');
    if (toastSel) {
      toastSel.value = load(STORAGE.toastDuration, '4000');
      toastSel.addEventListener('change', () => {
        save(STORAGE.toastDuration, toastSel.value);
        toast('Notification timing updated.', 'info', Number(toastSel.value) || 4000);
      });
    }
    const startSel = document.querySelector('[data-dash-start-page]');
    if (startSel) {
      startSel.value = load(STORAGE.startPage, 'dashboard');
      startSel.addEventListener('change', () => {
        save(STORAGE.startPage, startSel.value);
        toast('Startup page saved.', 'info', 2500);
      });
    }
    const clearBtn = document.querySelector('[data-dash-clear-data]');
    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        if (clearBtn.dataset.confirming !== '1') {
          clearBtn.dataset.confirming = '1';
          clearBtn.textContent = 'Click again to confirm';
          setTimeout(() => { clearBtn.dataset.confirming = '0'; clearBtn.textContent = 'Clear analysis data'; }, 4000);
          return;
        }
        [STORAGE.lastAnalysis, STORAGE.lastScore, STORAGE.lastFilters, STORAGE.history, STORAGE.resumesAnalyzed, STORAGE.lastPage].forEach((k) => {
          try { localStorage.removeItem(k); } catch { /* ignore */ }
        });
        toast('Stored analysis data cleared.', 'success');
        setTimeout(() => window.location.reload(), 600);
      });
    }
  }

  // ─── STARTUP PAGE (Settings) ───
  // 'dashboard' shows the overview; 'last' reopens the last visited page;
  // any other value opens that page. Runs once after state restore.
  function restoreStartupPage() {
    if (!document.querySelector('[data-dash-layout]')) return;
    const pref = load(STORAGE.startPage, 'dashboard');
    const target = pref === 'last' ? (load(STORAGE.lastPage, 'dashboard') || 'dashboard') : pref;
    if (target && DASH_PAGES.includes(target)) navigateToSection(target);
  }

  // Hook into updateDashboardUI to also render top jobs
  const origUpdateDashboardUI = updateDashboardUI;
  updateDashboardUI = function(jobs) {
    origUpdateDashboardUI(jobs);
    renderTopJobs();
  };

  // ═══ WORKPLACE: THEME TOGGLE ═══
  // Cycles through the SAME auto/light/dark preference as the main theme
  // toggle (previously this button forced light/dark and permanently lost the
  // stored 'auto' mode). The icon mirrors the resolved theme.
  function syncWpThemeIcon() {
    const themeToggleWpIcon = document.querySelector('[data-dash-theme-toggle-wp]');
    if (themeToggleWpIcon) themeToggleWpIcon.textContent = html.getAttribute('data-theme') === 'dark' ? '🌙' : '☀️';
  }
  const themeToggleWp = document.querySelector('[data-dash-theme-toggle-wp]');
  if (themeToggleWp) {
    themeToggleWp.addEventListener('click', () => {
      themeMode = MODE_CYCLE[(MODE_CYCLE.indexOf(themeMode) + 1) % 3];
      save(STORAGE.theme, themeMode);
      applyTheme(themeMode);
      syncWpThemeIcon(); // keep the icon in step with the resolved theme
      toast(`Theme: ${MODE_LABELS[themeMode]}`, 'info', 2000);
    });
    syncWpThemeIcon();
  }

  // ═══ WORKPLACE: CTRL+K SEARCH ═══
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      const searchInput = document.querySelector('[data-dash-topbar-search]');
      if (searchInput) searchInput.focus();
    }
  });

  // ═══ DASHBOARD: ANIMATED COUNTERS ═══
  // Targets are passed in (renderStatistics) — reading them back from the
  // data-stat-value attribute is impossible because renderStatistics used to
  // overwrite that attribute with the value itself, which broke every
  // subsequent analysis update.
  function animateCounters() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    document.querySelectorAll('[data-stat-value]').forEach(el => {
      const target = Number(el.dataset.statTarget);
      if (!Number.isFinite(target)) return; // text-only stats (e.g. top missing skill)
      const suffix = el.dataset.statSuffix || '';
      const current = parseInt(el.textContent, 10) || 0;
      if (current === target) { el.textContent = String(target) + suffix; return; }
      const diff = target - current;
      const steps = Math.max(1, Math.min(30, Math.abs(diff)));
      const stepSize = diff / steps;
      let step = 0;
      const tick = () => {
        step++;
        el.textContent = Math.round(current + stepSize * step) + suffix;
        if (step < steps) requestAnimationFrame(tick);
        else el.textContent = target + suffix;
      };
      requestAnimationFrame(tick);
    });
  }

  // ═══ DASHBOARD: RISK CARDS ═══
  function renderRiskCards(payload) {
    const riskScore = Math.round((payload.risk_score || 0) * 100);
    const skills = ((payload.reasoning || {}).skills_detected || []);
    const roles = dedupeRoles(payload.top_roles || []);
    const avgSim = roles.length ? roles.reduce((a, r) => a + (r.similarity || 0), 0) / roles.length : 0;
    const skillMatch = clampScore(Math.round(avgSim * 100));
    // ATS card shows the REAL local ATS check result when one has run for
    // this analysis. With no usable text (PDF/DOCX upload) there is no
    // honest ATS number, so the card reports that instead of a guess.
    if (lastAtsScore == null) {
      const card = document.querySelector('[data-risk-card="job-compatibility"]');
      if (card) card.classList.add('is-dimmed');
      const numEl = document.querySelector('[data-risk-card-value="job-compatibility"]');
      const barEl = document.querySelector('[data-risk-card-bar="job-compatibility"]');
      const statusEl = document.querySelector('[data-risk-card-status="job-compatibility"]');
      if (numEl) numEl.textContent = '--';
      if (barEl) barEl.style.width = '0%';
      if (statusEl) { statusEl.textContent = 'Needs resume text'; statusEl.className = 'risk-card__status'; }
    } else {
      document.querySelector('[data-risk-card="job-compatibility"]')?.classList.remove('is-dimmed');
      updateRiskCardValue('job-compatibility', lastAtsScore, lastAtsScore >= 80 ? 'Strong' : lastAtsScore >= 60 ? 'Moderate' : 'Needs Work', lastAtsScore >= 80 ? 'is-good' : lastAtsScore >= 60 ? 'is-medium' : 'is-high');
    }
    const resumeScore = (typeof payload.final_score === 'number') ? payload.final_score
      : (lastAnalysis && typeof lastAnalysis.final_score === 'number') ? lastAnalysis.final_score
      : clampScore(50 + riskScore * 0.3);
    const jobCompat = clampScore(Math.round(skillMatch * 0.7 + resumeScore * 0.3));

    const cards = {
      'career-risk': { value: riskScore, status: riskScore > 66 ? 'High Risk' : riskScore > 33 ? 'Medium Risk' : 'Low Risk', cls: riskScore > 66 ? 'is-high' : riskScore > 33 ? 'is-medium' : 'is-good' },
      'resume-strength': { value: resumeScore, status: resumeScore >= 70 ? 'Strong' : resumeScore >= 40 ? 'Average' : 'Needs Work', cls: resumeScore >= 70 ? 'is-good' : resumeScore >= 40 ? 'is-medium' : 'is-high' },
      'skill-match': { value: skillMatch, status: skillMatch >= 70 ? 'Strong' : skillMatch >= 40 ? 'Average' : 'Low', cls: skillMatch >= 70 ? 'is-good' : skillMatch >= 40 ? 'is-medium' : 'is-high' },
    };

    Object.entries(cards).forEach(([key, data]) => {
      updateRiskCardValue(key, data.value, data.status, data.cls);
    });
  }

  /** Animate a dashboard risk-card to a new value and set its status/bars. */
  function updateRiskCardValue(key, value, status, cls) {
    const numEl = document.querySelector(`[data-risk-card-value="${key}"]`);
    const barEl = document.querySelector(`[data-risk-card-bar="${key}"]`);
    const statusEl = document.querySelector(`[data-risk-card-status="${key}"]`);
    if (numEl) {
      const current = parseInt(numEl.textContent, 10) || 0;
      const target = value;
      if (current !== target) {
        const diff = target - current;
        const steps = Math.max(1, Math.min(25, Math.abs(diff)));
        const stepSize = diff / steps;
        let step = 0;
        const tick = () => {
          step++;
          numEl.textContent = Math.round(current + stepSize * step);
          if (step < steps) requestAnimationFrame(tick);
          else numEl.textContent = String(target);
        };
        requestAnimationFrame(tick);
      }
    }
    if (barEl) barEl.style.width = `${value}%`;
    if (statusEl) { statusEl.textContent = status; statusEl.className = `risk-card__status ${cls}`; }
  }

  // ═══ DASHBOARD: PIE CHARTS (vanilla canvas) ═══
  const PIE_COLORS = ['#6366f1', '#22d3ee', '#a78bfa', '#4ade80', '#fb923c', '#f472b6', '#fbbf24', '#34d399'];

  function drawPieChart(canvas, dataMap) {
    if (!canvas || !canvas.getContext) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const w = rect.width, h = rect.height;
    const cx = w / 2, cy = h / 2;
    const radius = Math.min(cx, cy) - 10;
    const entries = Object.entries(dataMap);
    const total = entries.reduce((a, [, v]) => a + v, 0);
    if (!total) {
      ctx.beginPath(); ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,255,255,0.06)'; ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.3)'; ctx.font = '12px Inter, sans-serif'; ctx.textAlign = 'center';
      ctx.fillText('No data', cx, cy);
      return;
    }
    let angle = -Math.PI / 2;
    entries.forEach(([label, value], i) => {
      const slice = (value / total) * Math.PI * 2;
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, radius, angle, angle + slice); ctx.closePath();
      ctx.fillStyle = PIE_COLORS[i % PIE_COLORS.length]; ctx.fill();
      angle += slice;
    });
    // Donut hole
    ctx.beginPath(); ctx.arc(cx, cy, radius * 0.55, 0, Math.PI * 2);
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--surface-container-lowest').trim() || '#12132b';
    ctx.fill();
  }

  function renderPieCharts(payload) {
    const skills = ((payload.reasoning || {}).skills_detected || []);
    const roles = dedupeRoles(payload.top_roles || []);
    const skillMap = {}; skills.forEach(s => { skillMap[s] = (skillMap[s] || 0) + 1; });
    const catMap = {}; roles.forEach(r => { const cat = r.industry || 'Other'; catMap[cat] = (catMap[cat] || 0) + 1; });

    const skillCanvas = $('[data-skill-pie-chart]');
    const jobCanvas = $('[data-job-pie-chart]');
    drawPieChart(skillCanvas, skillMap);
    drawPieChart(jobCanvas, catMap);

    // Legends with percentages (matching reference)
    const skillLegend = $('[data-skill-pie-legend]');
    const jobLegend = $('[data-job-pie-legend]');
    const skillTotal = Object.values(skillMap).reduce((a, b) => a + b, 0);
    const catTotal = Object.values(catMap).reduce((a, b) => a + b, 0);
    if (skillLegend) skillLegend.innerHTML = Object.entries(skillMap).map(([s, v], i) => {
      const pct = Math.round((v / skillTotal) * 100);
      return `<div class="chart-legend-row"><span class="chart-legend-item"><span class="chart-legend-dot" style="background:${PIE_COLORS[i % PIE_COLORS.length]};"></span>${s}</span><span class="chart-legend-pct">${pct}%</span></div>`;
    }).join('');
    if (jobLegend) jobLegend.innerHTML = Object.entries(catMap).map(([c, v], i) => {
      const pct = Math.round((v / catTotal) * 100);
      return `<span class="chart-legend-item"><span class="chart-legend-dot" style="background:${PIE_COLORS[i % PIE_COLORS.length]};"></span>${c}</span>`;
    }).join('');

    // Donut center total
    const skillTotalEl = document.querySelector('[data-skill-total]');
    if (skillTotalEl) skillTotalEl.textContent = String(skills.length);
  }

  // ═══ DASHBOARD: RISK GAUGE ═══
  function renderRiskGauge(payload) {
    const riskScore = Math.round((payload.risk_score || 0) * 100);
    const level = payload.risk_label ? normalizeRisk(payload.risk_label) : riskFromScore(payload.risk_score);

    const gaugeValue = document.querySelector('[data-risk-gauge-value]');
    const gaugeLabel = document.querySelector('[data-risk-gauge-label]');
    const gaugeSummary = document.querySelector('[data-risk-gauge-summary]');
    const ring = document.querySelector('[data-risk-gauge] .risk-gauge__ring');

    if (gaugeValue) gaugeValue.textContent = `${riskScore}%`;
    if (gaugeLabel) {
      gaugeLabel.textContent = `${level} Risk`;
      gaugeLabel.style.color = level === 'High' ? '#f43f5e' : level === 'Medium' ? '#fbbf24' : '#4ade80';
    }
    if (ring) {
      // Animate the gauge fill based on risk score
      const deg = Math.round((riskScore / 100) * 360);
      const color = level === 'High' ? '#f43f5e' : level === 'Medium' ? '#fbbf24' : '#4ade80';
      ring.style.background = `conic-gradient(${color} 0deg ${deg}deg, rgba(255,255,255,0.06) ${deg}deg 360deg)`;
    }
    if (gaugeSummary) {
      gaugeSummary.textContent = payload.cognitive_career_narrative || `Your career has ${level.toLowerCase()} automation exposure. Reskilling can reduce this risk.`;
    }

    // Risk distribution percentages (derived from roles)
    const roles = dedupeRoles(payload.top_roles || []);
    let high = 0, medium = 0, low = 0;
    roles.forEach(r => {
      const rl = r.risk_label ? normalizeRisk(r.risk_label) : riskFromScore(r.risk_score);
      if (rl === 'High') high++;
      else if (rl === 'Medium') medium++;
      else low++;
    });
    const total = roles.length || 1;
    const pctHigh = document.querySelector('[data-risk-pct-high]');
    const pctMedium = document.querySelector('[data-risk-pct-medium]');
    const pctLow = document.querySelector('[data-risk-pct-low]');
    if (pctHigh) pctHigh.textContent = `${Math.round((high / total) * 100)}%`;
    if (pctMedium) pctMedium.textContent = `${Math.round((medium / total) * 100)}%`;
    if (pctLow) pctLow.textContent = `${Math.round((low / total) * 100)}%`;
  }

  // ═══ DASHBOARD: SKILL GAP BAR CHART (vanilla canvas) ═══
  function renderSkillGapChart(payload) {
    const canvas = $('[data-skill-gap-chart]');
    if (!canvas || !canvas.getContext) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const w = rect.width, h = rect.height;
    const padL = 120, padR = 60, padT = 20, padB = 30;
    const chartW = w - padL - padR, chartH = h - padT - padB;

    const skills = ((payload.reasoning || {}).skills_detected || []);
    const roles = dedupeRoles(payload.top_roles || []);
    const topRole = roles[0];
    const rawChips = topRole ? (topRole.trait_chips || []) : [];
    // trait_chips look like "75% Python" or "Python: 75%" — strip the
    // percentage prefix/suffix so the plain skill name remains.
    const requiredSkills = rawChips.map((c) => String(c).replace(/^\s*\d{1,3}\s*%\s*/, '').replace(/\s*:\s*\d{1,3}\s*%\s*$/, '').trim()).filter(Boolean).slice(0, 8);
    const userSkills = new Set(skills.map(s => String(s).toLowerCase()));

    if (!requiredSkills.length) {
      ctx.fillStyle = 'rgba(255,255,255,0.3)'; ctx.font = '14px Inter, sans-serif'; ctx.textAlign = 'center';
      ctx.fillText('Run an analysis to see skill gap chart', w / 2, h / 2);
      return;
    }

    const barH = Math.min(28, (chartH / requiredSkills.length) - 8);
    const gap = (chartH / requiredSkills.length) - barH;
    requiredSkills.forEach((skill, i) => {
      const y = padT + i * (barH + gap) + gap / 2;
      const has = userSkills.has(skill.toLowerCase());
      const color = has ? '#6366f1' : '#f43f5e';
      // Label
      ctx.fillStyle = 'rgba(228,225,240,0.8)'; ctx.font = '12px Inter, sans-serif'; ctx.textAlign = 'right';
      ctx.fillText(skill, padL - 10, y + barH / 2 + 4);
      // Bar bg
      ctx.fillStyle = 'rgba(255,255,255,0.05)';
      ctx.fillRect(padL, y, chartW, barH);
      // Bar fill (width based on match or fixed for missing)
      const barW = has ? chartW * 0.7 : chartW * 0.3;
      const grad = ctx.createLinearGradient(padL, 0, padL + barW, 0);
      grad.addColorStop(0, color); grad.addColorStop(1, has ? '#22d3ee' : '#fb7185');
      ctx.fillStyle = grad;
      ctx.fillRect(padL, y, barW, barH);
    });
  }

  // ═══ DASHBOARD: STATISTICS ═══
  function renderStatistics(payload) {
    const skills = ((payload.reasoning || {}).skills_detected || []);
    const roles = dedupeRoles(payload.top_roles || []);
    const riskScore = Math.round((payload.risk_score || 0) * 100);
    const topRole = roles[0];
    const requiredSkills = topRole ? (topRole.trait_chips || []) : [];
    const userSkills = new Set(skills.map(s => String(s).toLowerCase()));
    const missing = requiredSkills.filter(s => !userSkills.has(String(s).toLowerCase()));
    const analyzedCount = (Number(load(STORAGE.resumesAnalyzed, '0')) || 0) + (restoringState ? 0 : 1);

    // key → [display value, numeric target (null = text-only), suffix]
    const stats = {
      'total-resumes': [String(analyzedCount), analyzedCount, ''],
      'avg-risk': [`${riskScore}%`, riskScore, '%'],
      'total-jobs': [String(roles.length), roles.length, ''],
      'top-missing': [missing[0] || '—', null, ''],
    };

    Object.entries(stats).forEach(([key, [display, target, suffix]]) => {
      const el = document.querySelector(`[data-stat-value="${key}"]`);
      if (!el) return;
      if (target == null) {
        el.textContent = display; // text-only stat — no counter animation
      } else if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        el.textContent = display; // reduced motion: set the final value directly
      } else {
        el.dataset.statTarget = String(target); // animation target (never the lookup key)
        el.dataset.statSuffix = suffix;
        el.textContent = '0' + suffix; // restart from 0 so the counter animates
      }
    });
    animateCounters();
  }

  // ═══ DASHBOARD: TOPBAR SEARCH ═══
  // Filters the job-matching list AND opens that page so the results are
  // actually visible (previously it scrolled to a section id that does not
  // exist on the workspace dashboard). Input is debounced (performance rule).
  // Clearing the input also clears the filter (was stuck until page reload).
  const dashTopbarSearch = $('[data-dash-topbar-search]');
  if (dashTopbarSearch) {
    let topbarSearchTimer = null;
    let lastPushedQuery = null; // only navigate when the query text actually changes
    // ── Global search suggestions (rule #51) ──
    // One dropdown, three real data sources: navigation sections, current job
    // matches, and detected skills. Clicking a suggestion navigates; Enter
    // keeps the existing job-search behavior.
    let suggestBox = document.getElementById('dashSearchSuggest');
    const closeSuggest = () => { suggestBox?.classList.add('hidden'); dashTopbarSearch.setAttribute('aria-expanded', 'false'); };
    const buildSuggest = () => {
      if (suggestBox) return suggestBox;
      suggestBox = document.createElement('div');
      suggestBox.id = 'dashSearchSuggest';
      suggestBox.className = 'dash-search-suggest hidden';
      suggestBox.setAttribute('role', 'listbox');
      suggestBox.setAttribute('aria-label', 'Search suggestions');
      dashTopbarSearch.closest('.dash-topbar__search')?.appendChild(suggestBox);
      return suggestBox;
    };
    const renderSuggestions = (q) => {
      const box = buildSuggest();
      const ql = q.toLowerCase();
      const sectionHits = Object.entries(DASH_PAGE_LABELS)
        .filter(([, label]) => label.toLowerCase().includes(ql))
        .slice(0, 4)
        .map(([id, label]) => ({ icon: '🧭', label, sub: 'Section', go: () => { navigateToSection(id); closeSuggest(); } }));
      const jobHits = jmJobs.filter((j) => `${j.title} ${j.industry || ''}`.toLowerCase().includes(ql)).slice(0, 3)
        .map((j) => ({ icon: '💼', label: j.title, sub: `${j.score}% match`, go: () => { navigateToSection('job-matching'); closeSuggest(); } }));
      const skillHits = (((lastAnalysis || {}).reasoning || {}).skills_detected || []).filter((s) => String(s).toLowerCase().includes(ql)).slice(0, 3)
        .map((s) => ({ icon: '🧠', label: s, sub: 'Detected skill', go: () => { navigateToSection('skill-extraction'); closeSuggest(); } }));
      const hits = [...sectionHits, ...jobHits, ...skillHits];
      if (!hits.length) {
        box.innerHTML = '<div class="dash-search-suggest__empty">No matches found.</div>';
      } else {
        box.innerHTML = '';
        hits.forEach((h) => {
          const row = document.createElement('button');
          row.type = 'button';
          row.className = 'dash-search-suggest__item';
          row.setAttribute('role', 'option');
          const icon = document.createElement('span'); icon.className = 'dash-search-suggest__icon'; icon.textContent = h.icon;
          const labelEl = document.createElement('span'); labelEl.className = 'dash-search-suggest__label'; labelEl.textContent = h.label;
          const subEl = document.createElement('span'); subEl.className = 'dash-search-suggest__sub'; subEl.textContent = h.sub;
          row.append(icon, labelEl, subEl);
          row.addEventListener('click', h.go);
          box.appendChild(row); // textContent for user-visible strings (rule #59)
        });
      }
      box.classList.remove('hidden');
      dashTopbarSearch.setAttribute('aria-expanded', 'true');
    };
    dashTopbarSearch.addEventListener('input', () => {
      clearTimeout(topbarSearchTimer);
      const q = dashTopbarSearch.value.trim();
      if (q.length >= 2) renderSuggestions(q);
      else closeSuggest();
      topbarSearchTimer = setTimeout(() => {
        const ql = q.trim().toLowerCase();
        if (ql === lastPushedQuery) return;
        lastPushedQuery = ql;
        jmState.query = ql;
        applyJmView();
        if (ql) navigateToSection('job-matching');
      }, 250);
    });
    dashTopbarSearch.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { closeSuggest(); dashTopbarSearch.blur(); }
    });
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.dash-topbar__search')) closeSuggest();
    });
  }

  // ═══ DASHBOARD: HOOK INTO ANALYSIS FLOW ═══
  // Dashboard rendering calls are inside renderResults (line 429-432)

  // ═══ STATS CARD QUICK ACTIONS ═══
  // Dashboard stat cards deep-link into their sections (rule #5):
  // Skills Detected → Skill Extraction, Missing Skills → Skill Gap,
  // Job Matches → Job Matching, Career Risk → Career Risk page.
  const STAT_CARD_TARGETS = { 'total-resumes': 'skill-extraction', 'avg-risk': 'skill-gap', 'total-jobs': 'job-matching', 'top-missing': 'career-risk', 'roadmap-progress': 'reskilling' };
  document.querySelectorAll('.stats-grid .stat-card').forEach((card) => {
    const valueEl = card.querySelector('[data-stat-value]');
    const key = valueEl?.dataset.statValue;
    const target = key ? STAT_CARD_TARGETS[key] : null;
    if (!target) return;
    card.setAttribute('data-dash-goto', target);
    card.setAttribute('role', 'button');
    card.setAttribute('tabindex', '0');
    card.setAttribute('aria-label', `Open ${DASH_PAGE_LABELS[target] || target}`);
    const go = () => navigateToSection(target);
    card.addEventListener('click', go);
    card.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
  });

  // ═══ SKILL GAP: AUTO-RECALCULATE ON ROLE CHANGE ═══
  // Changing the target role after a successful analysis re-runs the existing
  // backend analysis for the new role — using the same resume text that
  // produced the last result. Requires text because the backend computes the
  // gap server-side (no resume text is ever stored).
  if (skillsGapRole && !skillsGapRole.dataset.autoRecalcBound) {
    skillsGapRole.dataset.autoRecalcBound = '1';
    skillsGapRole.addEventListener('change', () => {
      if (!skillsGapResults || skillsGapResults.classList.contains('hidden')) return; // nothing analyzed yet
      const resumeTextEl = document.querySelector('[data-resume-text]');
      const resumeText = resumeTextEl ? resumeTextEl.value.trim() : '';
      const analysisSkills = ((lastAnalysis || {}).reasoning || {}).skills_detected || [];
      if (resumeText.length < 20 && !analysisSkills.length) {
        toast('Run a resume analysis first to compare against this role.', 'info');
        return;
      }
      if (!skillsGapRole.value) return;
      skillsGapForm?.requestSubmit(); // reuse the existing validated submit path
    });
  }

  // ═══ DASHBOARD CARD NAVIGATION (quick actions) ═══
  // Dashboard cards and the hero buttons deep-link into their sections.
  // Cards are real buttons semantically (role=button + keyboard), satisfying
  // the "no dead cards" rule without restructuring the CSS.
  document.querySelectorAll('[data-dash-goto]').forEach((card) => {
    const go = () => navigateToSection(card.dataset.dashGoto);
    card.addEventListener('click', go);
    card.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); }
    });
  });

  // ═══ SKILL EXTRACTION: CATEGORY FILTERS ═══
  // Uses the REAL categorized skills from the analysis payload (skills.by_category
  // produced by resume_parser.extract_skills_from_text). No fabricated data:
  // with no categorization available the filter row shows an honest notice.
  const skillVizContainerEl = $('[data-skillviz-container]');
  let skillFilterCat = 'all';
  document.querySelectorAll('[data-skillcat]').forEach((chip) => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('[data-skillcat]').forEach((c) => c.classList.toggle('is-active', c === chip));
      skillFilterCat = chip.dataset.skillcat || 'all';
      if (lastAnalysis) renderSkillVizFiltered();
      else toast('Run a resume analysis first.', 'warning');
    });
  });

  /** Map backend category names (e.g. "programming_languages") to filter keys. */
  function skillCatMatches(categoryName, filterKey) {
    const c = String(categoryName || '').toLowerCase();
    switch (filterKey) {
      case 'technical': return !/soft|business|interpersonal/i.test(c);
      case 'soft': return /soft|business|interpersonal/i.test(c);
      case 'languages': return /language|programming/i.test(c) && !/human|spoken/i.test(c);
      case 'frameworks': return /framework|library/i.test(c);
      case 'databases': return /database|db|sql/i.test(c);
      case 'tools': return /tool|platform|devops|cloud/i.test(c);
      default: return true;
    }
  }

  /** Re-render the Skill Extraction bars for the selected category filter. */
  function renderSkillVizFiltered() {
    if (!skillVizContainerEl) return;
    const byCat = (lastAnalysis.skills && lastAnalysis.skills.by_category) || {};
    const cats = Object.keys(byCat);
    let skills = [];
    if (cats.length) {
      cats.forEach((c) => {
        if (skillCatMatches(c, skillFilterCat)) (byCat[c] || []).forEach((s) => skills.push(s));
      });
    }
    if (!skills.length) skills = ((lastAnalysis.reasoning || {}).skills_detected || []); // honest fallback
    if (!skills.length) {
      skillVizContainerEl.innerHTML = '<div class="list-card is-placeholder"><div><strong>No skills detected</strong><p>Run an analysis to detect skills from your resume.</p></div></div>';
      return;
    }
    const detected = new Set(((lastAnalysis.reasoning || {}).skills_detected || []).map((s) => String(s).toLowerCase()));
    const maxShow = 10;
    skillVizContainerEl.innerHTML = skills.slice(0, maxShow).map((skill) => {
      const pct = detected.has(String(skill).toLowerCase()) ? 100 : 70; // detected presence — not fabricated proficiency
      const label = detected.has(String(skill).toLowerCase()) ? 'Detected in your resume' : 'Listed in target skill set';
      return `<div class="skill-viz-item" aria-label="${esc(skill)}: ${esc(label)}"><span class="skill-viz-item__name">${esc(skill)}</span><div class="skill-viz-item__bar"><span style="width:${pct}%;"></span></div><span class="skill-viz-item__value">${esc(label)}</span></div>`;
    }).join('');
  }

  // ═══ RESKILLING ROADMAP: INTERACTIVE STAGES ═══
  // Clicking a stage shows the REAL missing/required skills for that band,
  // derived from the analysis roadmap items (course/skill/reason/url).
  document.querySelectorAll('[data-roadmap-stage]').forEach((stage) => {
    const open = () => showRoadmapStageDetail(stage.dataset.roadmapStage);
    stage.addEventListener('click', open);
    stage.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); }
    });
  });

  function showRoadmapStageDetail(stageKey) {
    const detail = document.querySelector('[data-roadmap-stage-detail]');
    if (!detail) return;
    document.querySelectorAll('[data-roadmap-stage]').forEach((s) => s.classList.toggle('is-selected', s.dataset.roadmapStage === stageKey));
    const payload = lastAnalysis || {};
    const items = payload.roadmap || [];
    const skills = ((payload.reasoning || {}).skills_detected || []).map((s) => String(s).toLowerCase());
    const missingSkills = () => {
      const roles = dedupeRoles(payload.top_roles || []);
      const topRole = roles[0];
      const chips = topRole ? (topRole.trait_chips || []) : [];
      return chips
        .map((c) => String(c).replace(/^\s*\d{1,3}\s*%\s*/, '').replace(/\s*:\s*\d{1,3}\s*%\s*$/, '').trim())
        .filter((s) => s && !skills.includes(s.toLowerCase()));
    };
    let rows = [];
    if (stageKey === 'foundation') {
      rows = items.slice(0, 2).map((c) => ({ title: c.course || c.skill || 'Foundation topic', note: c.reason || 'Core concept for your target role', url: c.url || '' }));
      if (!rows.length) rows = [{ title: 'Run an analysis first', note: 'Foundation skills come from your analysis roadmap.', url: '' }];
    } else if (stageKey === 'intermediate') {
      rows = items.slice(2, 4).map((c) => ({ title: c.course || c.skill || 'Core skill', note: c.reason || 'Important technical skill', url: c.url || '' }));
      if (!rows.length) rows = missingSkills().slice(0, 3).map((s) => ({ title: s, note: 'Missing skill — required by your top role match', url: '' }));
    } else if (stageKey === 'advanced') {
      rows = items.slice(4, 6).map((c) => ({ title: c.course || c.skill || 'Advanced topic', note: c.reason || 'Specialized skill for your target role', url: c.url || '' }));
      if (!rows.length) rows = missingSkills().slice(3, 6).map((s) => ({ title: s, from: 'Missing skill', note: 'Advanced requirement for your top role match', url: '' }));
    } else {
      rows = [
        { title: 'Build a portfolio project using your target-role skills', note: 'Apply 2–3 of the skills above in one project', url: '' },
        { title: 'Update your resume with the new skills', note: 'Add them to your Skills section with measurable results', url: '' },
        { title: 'Practice interviews', note: 'Use the Interview Preparation page for category-wise practice', url: '' },
      ];
    }
    detail.innerHTML = rows.map((r) => `<div class="list-card motion-fade-up"><div><strong>${esc(r.title)}</strong><p>${esc(r.note)}</p></div>${r.url ? `<a class="button-ghost" href="${esc(r.url)}" target="_blank" rel="noreferrer">Open</a>` : ''}</div>`).join('');
    detail.classList.remove('hidden');
    detail.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // ═══ RESKILLING ROADMAP: PERSISTENT PROGRESS (shared engine) ═══
  // Reuses window.RoadmapProgress (static/roadmap-progress.js) — the SAME
  // per-account progress store the /career page uses — so a roadmap completed
  // in either place stays in sync. Progress is name-keyed (stable when a
  // roadmap is regenerated) and persisted via /api/roadmap-progress.
  const RP = window.RoadmapProgress;
  const roadmapProgressList = document.querySelector('[data-roadmap-progress-list]');
  const roadmapProgressFill = document.querySelector('[data-roadmap-progress-fill]');
  const roadmapProgressCount = document.querySelector('[data-roadmap-progress-count]');
  const roadmapProgressSummary = document.querySelector('[data-roadmap-progress-summary]');

  /** Flatten the analysis roadmap into the named items the progress panel tracks. */
  function roadmapProgressItems() {
    const payload = lastAnalysis || {};
    return (payload.roadmap || [])
      .map((c) => ({ name: (c.course || c.skill || '').trim(), skill: c.skill || '', url: c.url || '', reason: c.reason || '' }))
      .filter((it) => it.name);
  }

  /** Target role used to scope progress: the top matched role from the analysis. */
  function roadmapProgressTargetRole() {
    const roles = dedupeRoles((lastAnalysis || {}).top_roles || []);
    return (roles[0] && roles[0].job_role) || 'default';
  }

  function renderRoadmapProgress() {
    if (!roadmapProgressList) return;
    const items = roadmapProgressItems();
    if (!items.length) {
      roadmapProgressList.innerHTML = '<div class="list-card is-placeholder"><div><strong>No roadmap items yet</strong><p>Run a resume analysis to generate your personalized learning roadmap.</p></div></div>';
      if (roadmapProgressFill) roadmapProgressFill.style.width = '0%';
      if (roadmapProgressCount) roadmapProgressCount.textContent = '0 of 0 complete';
      return;
    }
    const stats = RP ? RP.statsByKey(items) : { total: items.length, completed: 0, pct: 0 };
    if (roadmapProgressFill) roadmapProgressFill.style.width = `${stats.pct}%`;
    if (roadmapProgressCount) roadmapProgressCount.textContent = `${stats.completed} of ${stats.total} complete`;
    roadmapProgressList.innerHTML = '';
    items.forEach((item) => {
      const done = RP ? RP.isDone(item.name) : false;
      const row = document.createElement('div');
      row.className = 'list-card motion-fade-up';
      const body = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = item.name;
      if (done) title.style.textDecoration = 'line-through';
      body.appendChild(title);
      if (item.reason) {
        const note = document.createElement('p');
        note.textContent = item.reason;
        body.appendChild(note);
      }
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'button-ghost';
      btn.textContent = done ? 'Completed' : 'Mark done';
      btn.setAttribute('aria-pressed', done ? 'true' : 'false');
      btn.setAttribute('aria-label', `${done ? 'Mark not done' : 'Mark done'}: ${item.name}`);
      btn.addEventListener('click', () => {
        if (!RP) return;
        RP.toggleKey(item.name);
        toast(done ? 'Marked as not started.' : 'Marked as completed.', 'success', 2000);
        renderRoadmapProgress();
        updateRoadmapProgressDashboardCard();
      });
      const actions = document.createElement('div');
      actions.className = 'history-row__actions';
      if (item.url) {
        const link = document.createElement('a');
        link.className = 'button-ghost';
        link.href = item.url;
        link.target = '_blank';
        link.rel = 'noreferrer';
        link.textContent = 'Open';
        actions.appendChild(link);
      }
      actions.appendChild(btn);
      row.append(body, actions);
      roadmapProgressList.appendChild(row);
    });
  }

  /** Keep the Dashboard "Roadmap Progress" KPI in step with the panel. */
  function updateRoadmapProgressDashboardCard() {
    const items = roadmapProgressItems();
    const stats = RP ? RP.statsByKey(items) : { pct: 0, completed: 0, total: 0 };
    const el = document.querySelector('[data-stat-value="roadmap-progress"]');
    if (el) el.textContent = `${stats.pct}%`;
    const summaryEl = document.querySelector('[data-roadmap-progress-summary]');
    if (summaryEl) {
      summaryEl.textContent = stats.total
        ? `${stats.completed} of ${stats.total} roadmap items complete (${stats.pct}%). Saved to your account.`
        : 'Complete roadmap items to track your reskilling progress. Your progress is saved to your account.';
    }
  }

  // Load once on init (server is authoritative), then render the panel.
  if (RP && roadmapProgressList) {
    RP.configure(roadmapProgressTargetRole());
    RP.load().then(() => { renderRoadmapProgress(); updateRoadmapProgressDashboardCard(); });
  }

  const roadmapResetBtn = document.querySelector('[data-roadmap-progress-reset]');
  if (roadmapResetBtn) {
    roadmapResetBtn.addEventListener('click', () => {
      if (!RP) return;
      if (roadmapResetBtn.dataset.confirming !== '1') {
        roadmapResetBtn.dataset.confirming = '1';
        roadmapResetBtn.textContent = 'Confirm?';
        setTimeout(() => { roadmapResetBtn.dataset.confirming = '0'; roadmapResetBtn.textContent = 'Reset'; }, 4000);
        return;
      }
      RP.reset().then(() => {
        roadmapResetBtn.dataset.confirming = '0';
        roadmapResetBtn.textContent = 'Reset';
        renderRoadmapProgress();
        updateRoadmapProgressDashboardCard();
        toast('Roadmap progress reset.', 'info');
      });
    });
  }

  // Hook into analysis completion so the progress panel follows the latest
  // roadmap and its top matched role (no separate polling required).
  const _origRenderReskillingMini = renderReskillingMini;
  renderReskillingMini = function (payload) {
    _origRenderReskillingMini(payload);
    if (typeof RP !== 'undefined' && RP && roadmapProgressList) {
      const newRole = roadmapProgressTargetRole();
      const roleChanged = newRole && newRole !== RP.targetRole;
      RP.configure(newRole);
      if (roleChanged) {
        // Different target role than what was loaded at init → pull its saved
        // server progress before rendering, so progress never leaks across roles.
        RP.load().then(() => { renderRoadmapProgress(); updateRoadmapProgressDashboardCard(); });
      } else {
        renderRoadmapProgress();
        updateRoadmapProgressDashboardCard();
      }
    }
  };

  // ═══ CAREER PATH: PROFILE-DRIVEN RECOMMENDATIONS ═══
  // Turns the static journey map into a resume-personalized direction list by
  // reusing the SAME /api/career-paths data the assistant already serves (no
  // new backend, no duplicate logic). Falls back to detected skills when the
  // resume text is no longer in the form (PDF/DOCX uploads).
  const careerRecommendBtn = document.querySelector('[data-career-path-recommend]');
  const careerRecommendList = document.querySelector('[data-career-path-recommend-list]');
  if (careerRecommendBtn && careerRecommendList) {
    careerRecommendBtn.addEventListener('click', async () => {
      const resumeTextEl = document.querySelector('[data-resume-text]');
      const resumeText = resumeTextEl ? resumeTextEl.value.trim() : '';
      const analysisSkills = ((lastAnalysis || {}).reasoning || {}).skills_detected || [];
      const source = resumeText.length >= 20 ? resumeText : analysisSkills.join(', ');
      if (source.length < 20) {
        toast('Run a resume analysis or paste resume text first.', 'warning');
        return;
      }
      if (!lastAnalysis && resumeText.length < 20) {
        toast('Run a resume analysis first to get profile-based directions.', 'info');
        return;
      }
      careerRecommendBtn.disabled = true;
      const orig = careerRecommendBtn.textContent;
      careerRecommendBtn.textContent = 'Analyzing...';
      try {
        const res = await apiPost('/api/career-paths', { resume_text: source });
        const data = await res.json();
        if (!data.success || !Array.isArray(data.paths)) throw new Error(data.error || 'No recommendations.');
        renderCareerRecommendations(data.paths);
      } catch (err) {
        careerRecommendList.innerHTML = `<div class="list-card"><div><strong>Unavailable</strong><p>${esc(err.message || 'Could not load recommendations.')}</p></div></div>`;
        toast(err.message || 'Could not load recommendations.', 'error');
      } finally {
        careerRecommendBtn.disabled = false;
        careerRecommendBtn.textContent = orig;
      }
    });
  }

  /** Render ranked career paths with an explainable "why" line (no fake data). */
  function renderCareerRecommendations(paths) {
    if (!careerRecommendList) return;
    if (!paths.length) {
      careerRecommendList.innerHTML = '<div class="list-card is-placeholder"><div><strong>No matches found</strong><p>Add more skills to your resume and try again.</p></div></div>';
      return;
    }
    careerRecommendList.innerHTML = paths.slice(0, 6).map((p) => {
      const score = clampScore(Math.round(Number(p.score) || 0));
      const matched = p.matched_keywords != null && p.total_keywords != null ? `${p.matched_keywords}/${p.total_keywords} keywords` : '';
      const needed = (p.skills_needed || []).slice(0, 4);
      const why = p.description ? esc(p.description) : 'Aligned with the skills detected in your profile.';
      return `
        <div class="list-card motion-fade-up">
          <div>
            <strong>${esc(p.role || 'Career')}</strong>
            ${p.category ? `<span class="status-pill" style="margin-left:0.5rem;">${esc(p.category)}</span>` : ''}
            <p>${why}</p>
            ${needed.length ? `<div class="pill-row">${needed.map((s) => `<span class="career-detail__chip is-learn">${esc(s)}</span>`).join('')}</div>` : ''}
          </div>
          <span class="status-pill ${score >= 60 ? '' : 'is-warm'}">${score}%${matched ? ` · ${esc(matched)}` : ''}</span>
        </div>`;
    }).join('');
    toast('Profile-based recommendations ready.', 'success');
  }

  // ═══ JOB DETAILS MODAL ═══
  // Every job card gets a real View Details action: title, match, matched &
  // missing skills, risk, and job-board links — all from the analysis data.
  function openJobModal(job) {
    const modalEl = document.querySelector('[data-job-modal]');
    if (!modalEl || !job) return;
    const title = modalEl.querySelector('[data-job-modal-title]');
    const body = modalEl.querySelector('[data-job-modal-body]');
    const skills = (job.skills || (lastAnalysis ? (lastAnalysis.reasoning || {}).skills_detected : null) || []);
    const roles = lastAnalysis ? dedupeRoles(lastAnalysis.top_roles || []) : [];
    const role = roles.find((r) => (r.job_role || '').toLowerCase() === String(job.title).toLowerCase());
    const chips = role?.trait_chips || [];
    const detected = new Set(skills.map((s) => String(s).toLowerCase()));
    const matched = chips.map((c) => String(c).replace(/^\s*\d{1,3}\s*%\s*/, '').replace(/\s*:\s*\d{1,3}\s*%\s*$/, '').trim()).filter((s) => s && detected.has(s.toLowerCase()));
    const missing = chips.map((c) => String(c).replace(/^\s*\d{1,3}\s*%\s*/, '').replace(/\s*:\s*\d{1,3}\s*%\s*$/, '').trim()).filter((s) => s && !detected.has(s.toLowerCase()));
    const risk = normalizeRisk(job.risk_level);
    const riskColor = getRiskColor(risk);
    if (title) title.textContent = job.title || 'Role';
    if (body) {
      const links = (job.job_board_links || roleLinks(job)).map((l) => `<a class="button-ghost" href="${l.url}" target="_blank" rel="noreferrer noopener">${esc(l.label)}</a>`).join('');
      const chipRow = (list, cls) => list.length
        ? `<div class="job-modal__chips">${list.map((s) => `<span class="career-detail__chip ${cls}">${esc(s)}</span>`).join('')}</div>`
        : `<p class="career-detail__none">None detected.</p>`;
      body.innerHTML = `
        <div class="modal-kpis">
          <div class="kpi"><div class="kpi__label">Match</div><div class="kpi__value">${clampScore(job.score)}%</div></div>
          <div class="kpi"><div class="kpi__label">Risk</div><div class="kpi__value" style="color:${riskColor}">${esc(risk)}</div></div>
          <div class="kpi"><div class="kpi__label">Industry</div><div class="kpi__value">${esc(job.industry || '—')}</div></div>
        </div>
        <div class="summary-card" style="margin-top:1rem;"><h3 class="section-title" style="margin:0 0 0.5rem;">Matched skills (from your resume)</h3>${chipRow(matched, 'is-have')}</div>
        <div class="summary-card" style="margin-top:0.75rem;"><h3 class="section-title" style="margin:0 0 0.5rem;">Missing skills (to learn)</h3>${chipRow(missing, 'is-learn')}</div>
        ${links ? `<div class="inline-actions" style="margin-top:1rem;">${links}</div>` : ''}
      `;
    }
    modalEl.classList.remove('hidden');
    modalEl.classList.add('is-open');
    modalEl.setAttribute('aria-hidden', 'false');
  }
  function closeJobModal() {
    const modalEl = document.querySelector('[data-job-modal]');
    modalEl?.classList.add('hidden');
    modalEl?.classList.remove('is-open');
    modalEl?.setAttribute('aria-hidden', 'true');
  }
  document.querySelectorAll('[data-job-modal-close]').forEach((b) => b.addEventListener('click', closeJobModal));
  document.querySelector('[data-job-modal]')?.addEventListener('click', (e) => { if (e.target === e.currentTarget) closeJobModal(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeJobModal(); });

  // ═══ CAREER PATH: JOURNEY SELECTOR (workspace page) ═══
  // Lets the user switch journeys directly on the Career Path page; the
  // Start Here path cards (home page) stay in sync via renderPathway.
  const careerPathSelect = document.querySelector('[data-career-path-select]');
  careerPathSelect?.addEventListener('change', () => {
    const k = careerPathSelect.value || 'student';
    pathButtons.forEach((b) => b.classList.toggle('is-active', b.dataset.pathOption === k));
    activePath = k;
    save(STORAGE.path, k);
    renderCareerPathFlowchart(k);
  });

  // ═══ RESUME PREVIEW: OPEN FROM ANALYSIS (PDF/DOCX) ═══
  // File info is known at selection time; for PDF/DOCX the backend parses
  // the text server-side and does not return it, so show the honest note.
  const resumeTextEl = $('[data-resume-text]');
  resumeTextEl?.addEventListener('input', () => {
    if (!resumePreview || resumePreview.classList.contains('hidden')) return;
    const t = resumeTextEl.value.trim();
    if (t.length >= 30) {
      resumePreviewInfo.innerHTML = `<strong>Pasted resume text</strong> · ${t.length} characters`;
    }
  });

  // ─── GLOBAL EXPORTS ───
  // Expose the dashboard API on window so inline handlers like
  // onchange="processResume(event)" work (the file is wrapped in an IIFE).
  Object.assign(window, {
    apiCall, uploadResume, processResume,
    handleFileSelect, handleFileUpload, handleFileDrop,
    displayResumeScore, animateScore,
    renderJobs, getJobs, filterJobs, sortJobs, searchJobs, updateDashboardUI,
    displayRiskLevel, updateRiskMeter, getRiskColor,
    updateSkillVisualization, updateAtsChecker,
    renderCareerPathFlowchart, generateInterviewQuestion,
    showResumePreview,
    toggleSidebar, animateCounters, renderRiskCards, renderPieCharts, renderSkillGapChart, renderStatistics,
    navigateToSection, renderHistory, renderReskillingMini, renderTopbarCrumbs, showInterviewAt, renderReportReskilling, showCareerNodeDetail, restoreStartupPage,
    loadServerHistory,
  });

  // Restore saved dashboard state last, so every function and constant this
  // file declares (charts, colors, wrappers) exists by the time it runs.
  // Deferred init (see the INIT note above): mode + pathway first, then the
  // saved-state restore, then workspace extras.
  setMode(activeMode);
  renderPathway(activePath);
  try { restoreSavedState(); } catch (err) { console.warn('State restore skipped:', err); }
  initWorkspaceExtras(); // crumbs, history rows, Settings preference bindings
  restoreStartupPage(); // Settings → "Open on startup"

  console.log('Prayash UI ready');
  toast('Prayash ready. Press ? for shortcuts.', 'info', 5000);
})();
// ─── WELCOME CARD 3D TILT + SPOTLIGHT (home + performance heroes) ───
(function() {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  document.querySelectorAll('[data-tilt]').forEach((tiltEl) => {
    if (tiltEl.dataset.tiltBound) return;
    tiltEl.dataset.tiltBound = '1';
    const max = parseFloat(tiltEl.getAttribute('data-tilt-max')) || 6;
    let raf = null;
    tiltEl.addEventListener('mousemove', (e) => {
      const r = tiltEl.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width;
      const py = (e.clientY - r.top) / r.height;
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        tiltEl.style.setProperty('--rx', ((0.5 - py) * max).toFixed(2) + 'deg');
        tiltEl.style.setProperty('--ry', ((px - 0.5) * max).toFixed(2) + 'deg');
      });
    });
    tiltEl.addEventListener('mouseleave', () => {
      if (raf) cancelAnimationFrame(raf);
      tiltEl.style.setProperty('--rx', '0deg');
      tiltEl.style.setProperty('--ry', '0deg');
    });
  });
})();
