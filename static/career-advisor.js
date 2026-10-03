/* =========================================================
   AI CAREER ADVISOR — CONNECTED FRONTEND
   Wiring: /api/upload → /score_resume → /predict_risk →
   /match_jobs → /api/skills-gap/* → /api/career-paths →
   /api/learning-roadmap → /api/career-chat
   One analysis feeds every page. No fake/random results.
========================================================= */
(() => {
  'use strict';

  /* ── STATE ─────────────────────────────────────────── */
  const state = {
    file: null,
    resumeText: '',
    resumeScore: null,       // {final_score, skill_score, experience_score, quality_score, feedback, ...}
    analysis: null,          // /api/upload full analysis
    risk: null,              // {risk_level, risk_score(0-1), explanation}
    skills: [],              // flat skill list (from analysis.skills.all_skills)
    skillsByCategory: {},    // backend categorization
    skillGap: null,          // skills-gap analysis result
    targetRole: '',
    roles: [],               // available roles from backend
    jobs: [],                // match_jobs result
    careerPaths: [],         // career-paths result
    roadmap: null,           // learning-roadmap result
    sessionId: '',
    busy: false,
    history: [],
    currentQuestion: null,
    askedQuestions: new Set(),
  };

  const $ = (id) => document.getElementById(id);
  const byId = $;

  /* ── HELPERS ───────────────────────────────────────── */
  function esc(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function setText(id, value) {
    const el = $(id);
    if (el) el.textContent = value ?? '--';
  }

  function fmtPct(value, digits = 0) {
    const n = Number(value);
    if (!Number.isFinite(n)) return '--';
    return `${(n * (digits === 0 && n <= 1 ? 100 : 1)).toFixed(digits)}%`;
  }

  function riskColor(level) {
    const l = String(level || '').toLowerCase();
    if (l.startsWith('elev') || l.startsWith('high')) return 'var(--error, #e5484d)';
    if (l.startsWith('moderate') || l.startsWith('medium')) return '#f5a623';
    return '#2fbf71';
  }

  function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content || '';
  }

  async function apiPost(url, body, isForm = false) {
    const headers = { 'X-CSRFToken': getCsrfToken() };
    if (!isForm) headers['Content-Type'] = 'application/json';
    const res = await fetch(url, {
      method: 'POST',
      headers,
      body: isForm ? body : JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.success === false) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }
    return data;
  }

  async function apiGet(url) {
    const res = await fetch(url, { headers: { 'X-CSRFToken': getCsrfToken() } });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.success === false) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }
    return data;
  }

  function setLoading(button, loading, busyLabel) {
    if (!button) return;
    if (loading) {
      button.dataset.originalText = button.textContent;
      button.textContent = busyLabel || 'Working…';
      button.disabled = true;
    } else {
      button.textContent = button.dataset.originalText || button.textContent;
      button.disabled = false;
    }
  }

  /* ── TOASTS ────────────────────────────────────────── */
  function showToast(message, type = 'info') {
    const container = $('advisorToastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `advisor-toast advisor-toast--${type}`;
    toast.setAttribute('role', 'status');
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.classList.add('advisor-toast--out');
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  /* ── INITIALIZATION ────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', initializeApp);

  function initializeApp() {
    if (!document.querySelector('.app .sidebar')) return;

    try { restoreState(); } catch (err) { console.warn('State restore skipped:', err); }
    applySidebarPreference();

    initializeNavigation();
    initializeResumeUpload();
    initializeTabs();
    initializeSkillFilters();
    initializeTargetRole();
    initializeJobControls();
    initializeInterview();
    initializeChat();
    initializeTheme();
    initializeSettings();
    initializeGlobalSearch();
    initializeModal();

    renderApplication();
    loadRoles();
  }

  /* ── NAVIGATION ────────────────────────────────────── */
  function initializeNavigation() {
    document.querySelectorAll('.nav-item[data-page]').forEach((button) => {
      button.addEventListener('click', () => goToPage(button.dataset.page));
    });

    // Clickable dashboard cards + hero CTA
    document.querySelectorAll('[data-page]:not(.nav-item)').forEach((element) => {
      element.addEventListener('click', () => {
        goToPage(element.dataset.page);
        const tab = element.dataset.subtab;
        if (tab) activateTab(tab);
      });
    });

    $('menuBtn')?.addEventListener('click', () => toggleMobileSidebar(true));
    $('advisorBackdrop')?.addEventListener('click', () => toggleMobileSidebar(false));
    $('sidebarCollapse')?.addEventListener('click', toggleDesktopSidebar);
  }

  function toggleMobileSidebar(open) {
    $('sidebar')?.classList.toggle('open', open);
    const backdrop = $('advisorBackdrop');
    if (backdrop) backdrop.hidden = !open || window.innerWidth > 720;
  }

  // If the viewport crosses the mobile boundary while the drawer is open,
  // drop the overlay so it never lingers on desktop.
  window.addEventListener('resize', () => {
    if (window.innerWidth > 720) {
      const backdrop = $('advisorBackdrop');
      if (backdrop) backdrop.hidden = true;
    }
  }, { passive: true });

  function toggleDesktopSidebar() {
    const app = document.querySelector('.app');
    const collapsed = app?.classList.toggle('sidebar-collapsed');
    localStorage.setItem('careerSidebarCollapsed', collapsed ? '1' : '0');
    const toggle = $('sidebarToggle');
    if (toggle) toggle.checked = Boolean(collapsed);
    const button = $('sidebarCollapse');
    if (button) button.textContent = collapsed ? '▶' : '◀';
  }

  function applySidebarPreference() {
    if (localStorage.getItem('careerSidebarCollapsed') === '1') {
      document.querySelector('.app')?.classList.add('sidebar-collapsed');
      const toggle = $('sidebarToggle');
      if (toggle) toggle.checked = true;
      const button = $('sidebarCollapse');
      if (button) button.textContent = '▶';
    }
    if (localStorage.getItem('careerAnimations') === 'off') {
      document.body.classList.add('no-anim');
      const toggle = $('animationsToggle');
      if (toggle) toggle.checked = false;
    }
  }

  function goToPage(pageId) {
    if (!pageId) return;
    document.querySelectorAll('.page').forEach((page) => page.classList.remove('active'));
    $(pageId)?.classList.add('active');
    document.querySelectorAll('.nav-item').forEach((item) => {
      item.classList.toggle('active', item.dataset.page === pageId);
    });
    toggleMobileSidebar(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function activateTab(tabId) {
    const button = document.querySelector(`.tab[data-tab="${tabId}"]`);
    if (button) button.click();
  }

  /* ── RESUME UPLOAD ─────────────────────────────────── */
  const ALLOWED_EXTENSIONS = ['txt', 'pdf', 'docx'];
  const MAX_FILE_BYTES = 20 * 1024 * 1024; // matches backend MAX_CONTENT_LENGTH

  function initializeResumeUpload() {
    const input = $('resumeInput');
    const uploadBox = $('uploadBox');

    input?.addEventListener('change', (event) => {
      handleFileSelection(event.target.files?.[0]);
    });

    if (uploadBox) {
      ['dragover', 'dragenter'].forEach((evt) => {
        uploadBox.addEventListener(evt, (e) => {
          e.preventDefault();
          uploadBox.classList.add('drag-over');
        });
      });
      ['dragleave', 'drop'].forEach((evt) => {
        uploadBox.addEventListener(evt, (e) => {
          e.preventDefault();
          uploadBox.classList.remove('drag-over');
        });
      });
      uploadBox.addEventListener('drop', (e) => {
        handleFileSelection(e.dataTransfer?.files?.[0]);
      });
    }

    $('analyzeBtn')?.addEventListener('click', analyzeResume);
    $('removeFileBtn')?.addEventListener('click', removeSelectedFile);
  }

  function handleFileSelection(file) {
    if (!file) return;

    const extension = file.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(extension)) {
      showToast(`Unsupported file type ".${extension}". Use TXT, PDF or DOCX.`, 'error');
      return;
    }
    if (file.size === 0) {
      showToast('That file is empty.', 'error');
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      showToast('File too large. Maximum size is 20 MB.', 'error');
      return;
    }

    state.file = file;
    renderFileInfo();
    $('resumePreview').textContent =
      `${file.name}\n\nPreview is available for TXT files. PDF/DOCX text is extracted by the backend during analysis.`;

    if (extension === 'txt') {
      const reader = new FileReader();
      reader.onload = (e) => {
        state.resumeText = String(e.target?.result || '');
        $('resumePreview').textContent = state.resumeText || 'No text found in file.';
      };
      reader.readAsText(file);
    } else {
      state.resumeText = '';
    }

    if ($('analyzeBtn')) $('analyzeBtn').disabled = false;
    if ($('removeFileBtn')) $('removeFileBtn').disabled = false;
    showToast('Resume selected.', 'success');
  }

  function renderFileInfo() {
    const info = $('fileInfo');
    if (!info) return;
    if (!state.file) {
      info.textContent = 'No resume selected.';
      return;
    }
    const sizeKB = (state.file.size / 1024).toFixed(1);
    info.textContent = `${state.file.name} • ${sizeKB} KB • ${state.file.type || 'Document'}`;
  }

  function removeSelectedFile() {
    state.file = null;
    state.resumeText = '';
    const input = $('resumeInput');
    if (input) input.value = '';
    renderFileInfo();
    if ($('analyzeBtn')) $('analyzeBtn').disabled = true;
    if ($('removeFileBtn')) $('removeFileBtn').disabled = true;
    $('resumePreview').textContent = 'Resume preview will appear here.';
    showToast('File removed.', 'info');
  }

  /* ── ANALYSIS PIPELINE (connected to backend) ──────── */
  async function extractResumeText(file) {
    // TXT was already read client-side.
    if (state.resumeText && state.resumeText.length >= 20) return state.resumeText;

    // PDF/DOCX: use the existing backend extractor
    // (/api/career-chat/context returns the extracted plain text).
    const form = new FormData();
    form.append('file', file);
    const data = await apiPost('/api/career-chat/context', form, true);
    if (!data.text || data.text.length < 20) {
      throw new Error('Could not extract readable text from that file.');
    }
    state.resumeText = data.text;
    $('resumePreview').textContent = data.text;
    return data.text;
  }

  async function analyzeResume() {
    if (state.busy) return;
    if (!state.file) {
      showToast('Please select a resume first.', 'warning');
      return;
    }

    const button = $('analyzeBtn');
    state.busy = true;
    setLoading(button, true, 'Analyzing…');
    showToast('Analyzing your resume…', 'info');

    try {
      const text = await extractResumeText(state.file);

      // 1) Full analysis (risk + roles + skills + roadmap narrative)
      const form = new FormData();
      form.append('resume_file', state.file);
      form.append('mode', 'standard');
      const analysis = await apiPost('/api/upload', form, true);
      state.analysis = analysis;
      state.skills = analysis.skills?.all_skills || [];
      state.skillsByCategory = analysis.skills?.by_category || {};

      // 2) Independent scorers run in parallel; one failure must not kill the rest.
      const [scoreRes, riskRes, jobsRes, pathsRes, roadmapRes] = await Promise.allSettled([
        apiPost('/score_resume', { resume_text: text }),
        apiPost('/predict_risk', { resume_text: text }),
        apiPost('/match_jobs', { resume_text: text }),
        apiPost('/api/career-paths', { resume_text: text }),
        apiPost('/api/learning-roadmap', { resume_text: text }),
      ]);

      state.resumeScore = scoreRes.status === 'fulfilled' ? scoreRes.value.result : null;
      state.risk = riskRes.status === 'fulfilled' ? riskRes.value : null;
      state.jobs = jobsRes.status === 'fulfilled' ? jobsRes.value.jobs || [] : [];
      state.careerPaths = pathsRes.status === 'fulfilled' ? pathsRes.value.paths || [] : [];
      state.roadmap = roadmapRes.status === 'fulfilled' ? roadmapRes.value.roadmap || [] : null;

      if (state.risk) showToast(`Risk analysis: ${state.risk.risk_level} exposure.`, 'info');

      // 3) Skill gap against the selected target role
      await runSkillGapAnalysis();

      saveHistoryEntry();
      saveState();
      renderApplication();
      showToast('Resume analysis completed.', 'success');
      goToPage('dashboard');
    } catch (error) {
      console.error('Analysis failed:', error);
      showToast(error.message || 'Analysis failed. Please try again.', 'error');
    } finally {
      state.busy = false;
      setLoading(button, false);
    }
  }

  async function runSkillGapAnalysis() {
    if (!state.resumeText || !state.targetRole) return;
    try {
      const data = await apiPost('/api/skills-gap/analyze', {
        resume_text: state.resumeText,
        target_role: state.targetRole,
      });
      state.skillGap = data.analysis;
    } catch (error) {
      console.warn('Skill gap analysis failed:', error);
      state.skillGap = null;
    }
  }

  /* ── ATS (backend checklist via /score_resume) ─────── */
  function renderATS() {
    const container = $('atsResults');
    if (!container) return;

    if (!state.resumeScore) {
      container.innerHTML = '<p>Analyze a resume to run the ATS check.</p>';
      return;
    }

    const strengths = state.resumeScore.strengths || [];
    const improvements = state.resumeScore.improvements || [];
    const rows = [
      ...strengths.map((label) => ({ passed: true, label })),
      ...improvements.map((label) => ({ passed: false, label })),
    ];

    container.innerHTML = `
      <p><strong>ATS compatibility score: ${esc(state.resumeScore.quality_score ?? '--')}/100</strong></p>
      ${rows.length
        ? rows.map((check) => `
          <div class="skill-row">
            <strong>${check.passed ? '✓' : '✕'} ${esc(check.label)}</strong>
          </div>`).join('')
        : '<p>No checklist data available.</p>'}
    `;
  }

  /* ── SKILL GAP ─────────────────────────────────────── */
  function initializeTargetRole() {
    const select = $('targetRole');
    select?.addEventListener('change', async (event) => {
      state.targetRole = event.target.value;
      if (state.resumeText) {
        setLoading(event.target, true, 'Calculating…');
        await runSkillGapAnalysis();
        renderSkillGap();
        setLoading(event.target, false);
        saveState();
      }
    });
  }

  async function loadRoles() {
    try {
      const data = await apiGet('/api/skills-gap/roles');
      state.roles = data.roles || [];
    } catch (error) {
      // Not logged in or endpoint unavailable — keep the static fallback options.
      console.warn('Could not load roles:', error);
      return;
    }
    const select = $('targetRole');
    if (!select || !state.roles.length) return;
    const current = state.targetRole;
    select.innerHTML = state.roles
      .map((role) => `<option value="${esc(role)}">${esc(role)}</option>`)
      .join('');
    if (current && state.roles.includes(current)) select.value = current;
  }

  function renderSkillGap() {
    const result = state.skillGap;
    const analyzed = Boolean(state.resumeText);

    if (!analyzed) {
      setText('gapPercentage', '--');
      setText('matchedCount', '--');
      setText('missingCount', '--');
      setText('requiredCount', '--');
      renderChips('matchedSkills', [], 'Select a target career after analyzing your resume.');
      renderChips('missingSkills', [], 'Select a target career after analyzing your resume.');
      setText('dashSkillMatch', '--');
      renderDashboardGap();
      return;
    }

    if (!result) {
      setText('gapPercentage', '--');
      setText('matchedCount', '--');
      setText('missingCount', '--');
      setText('requiredCount', '--');
      renderChips('matchedSkills', [], 'Select a target career to compare.');
      renderChips('missingSkills', [], 'Select a target career to compare.');
      setText('dashSkillMatch', '--');
      renderDashboardGap();
      return;
    }

    const matched = result.matched_skills || [];
    const missing = result.missing_skills || [];
    const required = (result.current_skills || []).concat(matched, missing);

    setText('gapPercentage', `${result.match_percentage ?? 0}%`);
    setText('matchedCount', matched.length);
    setText('missingCount', missing.length);
    setText('requiredCount', required.length);

    renderChips('matchedSkills', matched, 'No matched skills yet.');
    renderChips('missingSkills', missing, 'All required skills are covered.');
    renderSkillsToLearn(missing);

    setText('dashSkillMatch', `${result.match_percentage ?? 0}%`);
    renderDashboardGap();
  }

  function renderSkillsToLearn(missing) {
    const container = $('skillsToLearn');
    if (!container) return;
    if (!missing || !missing.length) {
      container.innerHTML = '<p>No missing skills — your profile covers this role.</p>';
      return;
    }
    const recs = state.skillGap?.recommendations || [];
    container.innerHTML = recs.length
      ? recs.map((rec) => `
        <details class="learn-entry">
          <summary>${esc(rec.skill)} <small>Priority: ${esc(rec.priority || 'Medium')}</small></summary>
          ${(rec.resources || []).length
            ? `<ul>${rec.resources.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>`
            : '<p>No learning resources available yet.</p>'}
        </details>`).join('')
      : missing.map((skill) => `<p>• ${esc(skill)}</p>`).join('');
  }

  function renderDashboardGap() {
    const container = $('dashboardGap');
    if (!container) return;
    if (!state.skillGap) {
      container.innerHTML = '<p>Analyze a resume and select a target role to see your skill gap.</p>';
      return;
    }
    const pct = state.skillGap.match_percentage ?? 0;
    container.innerHTML = `
      <div class="skill-row">
        <header>
          <span>Current Match</span>
          <strong>${esc(pct)}%</strong>
        </header>
        <div class="progress"><div style="width:${Number(pct) || 0}%"></div></div>
      </div>
      <p>${esc((state.skillGap.missing_skills || []).length)} required skills still missing.</p>
    `;
  }

  /* ── RISK ──────────────────────────────────────────── */
  function renderRisk() {
    const circleSmall = $('riskCircle');
    const circleLarge = $('careerRiskCircle');
    const risk = state.risk;

    const color = risk ? riskColor(risk.risk_level) : 'var(--surface-container, rgba(255,255,255,0.08))';
    const pct = risk ? Math.round((risk.risk_score ?? 0) * 100) : null;

    [circleSmall, circleLarge].forEach((circle) => {
      if (!circle) return;
      if (pct === null) {
        circle.style.background = '';
        return;
      }
      circle.style.background =
        `radial-gradient(closest-side, var(--surface-container-low, #171e2e) 74%, transparent 75% 100%),` +
        `conic-gradient(${color} ${pct}%, var(--surface-container, rgba(255,255,255,0.08)) 0)`;
    });

    if (!risk) {
      setText('dashRisk', '--');
      setText('careerRiskScore', '--');
      setText('careerRiskLevel', 'Not analyzed');
      setText('riskCircleValue', '--');
      setText('riskDescription', 'Analyze a resume to calculate risk.');
      const breakdown = $('riskBreakdown');
      if (breakdown) breakdown.innerHTML = '<p>No risk analysis available.</p>';
      const factors = $('riskFactors');
      if (factors) factors.innerHTML = '<p>No risk analysis available.</p>';
      const recs = $('riskRecommendations');
      if (recs) recs.innerHTML = '<p>No risk analysis available.</p>';
      return;
    }

    const level = risk.risk_level || '--';
    setText('dashRisk', level);
    setText('careerRiskScore', `${pct}%`);
    setText('careerRiskLevel', `${level} Risk`);
    setText('riskCircleValue', `${pct}%`);
    setText('riskDescription', risk.explanation || '');

    const breakdown = $('riskBreakdown');
    if (breakdown) {
      breakdown.innerHTML = `
        ${progressRow('Automation Risk', pct)}
        ${progressRow('Skill Readiness', 100 - pct)}
      `;
    }

    const factors = $('riskFactors');
    if (factors) {
      const reasoning = state.analysis?.reasoning || {};
      const detected = reasoning.skills_detected || state.skills.slice(0, 6);
      factors.innerHTML = `
        <p>• Automation exposure: ${esc(pct)}% (${esc(level)})</p>
        ${detected.length ? `<p>• Profile based on detected skills: ${esc(detected.join(', '))}</p>` : ''}
        <p>• Assessment produced by the local ML risk model.</p>
      `;
    }

    const recs = $('riskRecommendations');
    if (recs) {
      const nextSteps = state.analysis?.guided_next_steps || [];
      const items = nextSteps.length
        ? nextSteps.map((step) => `<p>✓ ${esc(typeof step === 'string' ? step : step.title || step.action || '')}</p>`).join('')
        : `<p>✓ Strengthen the missing skills listed in your Skill Gap analysis.</p>
           <p>✓ Follow the Reskilling Roadmap for your target career.</p>`;
      recs.innerHTML = items;
    }
  }

  /* ── SKILLS ────────────────────────────────────────── */
  const SOFT_SKILL_CATEGORIES = ['soft skills', 'soft', 'interpersonal'];

  function initializeSkillFilters() {
    document.querySelectorAll('.skill-filter').forEach((button) => {
      button.addEventListener('click', () => {
        document.querySelectorAll('.skill-filter').forEach((b) => b.classList.remove('active'));
        button.classList.add('active');
        renderSkillChips(button.dataset.filter);
      });
    });
  }

  function renderSkillChips(filter = 'all') {
    const container = $('skillChips');
    if (!container) return;

    const categoryMap = state.skillsByCategory || {};
    const categories = Object.keys(categoryMap);

    let items = [];
    if (filter === 'all') {
      items = Object.values(categoryMap).flat();
    } else if (filter === 'soft') {
      items = categories
        .filter((c) => SOFT_SKILL_CATEGORIES.some((s) => c.toLowerCase().includes(s)))
        .flatMap((c) => categoryMap[c]);
    } else if (filter === 'technical' || filter === 'tools' || filter === 'other') {
      const matchers = {
        technical: ['programming', 'language', 'framework', 'web', 'database', 'cloud', 'data science', 'devops'],
        tools: ['tool', 'platform'],
      };
      const softCats = categories.filter((c) => SOFT_SKILL_CATEGORIES.some((s) => c.toLowerCase().includes(s)));
      items = categories
        .filter((c) => !softCats.includes(c))
        .filter((c) => {
          const lower = c.toLowerCase();
          if (filter === 'technical') return matchers.technical.some((m) => lower.includes(m));
          if (filter === 'tools') return lower.includes('tool') || lower.includes('platform');
          // "other": everything not matched by the other categories
          return !matchers.technical.some((m) => lower.includes(m))
            && !lower.includes('tool') && !lower.includes('platform');
        })
        .flatMap((c) => categoryMap[c]);
    } else {
      items = categories
        .filter((c) => c.toLowerCase().includes(filter))
        .flatMap((c) => categoryMap[c]);
    }

    items = [...new Set(items)];
    renderChips('skillChips', items, 'No skills detected yet — analyze your resume first.');
  }

  function renderSkills() {
    const analyzed = Boolean(state.analysis);
    const byCategory = state.skillsByCategory || {};
    const all = state.skills || [];

    setText('totalSkills', analyzed ? all.length : '--');
    setText('dashSkills', analyzed ? all.length : 0);

    const softKeys = Object.keys(byCategory).filter((c) =>
      SOFT_SKILL_CATEGORIES.some((s) => c.toLowerCase().includes(s))
    );
    const toolKeys = Object.keys(byCategory).filter((c) =>
      ['tool', 'platform'].some((s) => c.toLowerCase().includes(s))
    );
    const softCount = softKeys.reduce((sum, k) => sum + byCategory[k].length, 0);
    const toolCount = toolKeys.reduce((sum, k) => sum + byCategory[k].length, 0);

    setText('technicalCount', analyzed ? all.length - softCount - toolCount : '--');
    setText('softCount', analyzed ? softCount : '--');
    setText('toolsCount', analyzed ? toolCount : '--');

    renderSkillChips(
      document.querySelector('.skill-filter.active')?.dataset.filter || 'all'
    );

    // Visualization: real detection counts per category (no invented proficiency)
    const container = $('skillVisualization');
    const bars = $('skillBars');
    const maxPerCategory = Math.max(1, ...Object.values(byCategory).map((a) => a.length));

    const html = analyzed && all.length
      ? Object.entries(byCategory)
          .sort((a, b) => b[1].length - a[1].length)
          .map(([category, skills]) => `
            <div class="skill-row">
              <header>
                <span>${esc(category)}</span>
                <strong>${skills.length} detected</strong>
              </header>
              <div class="progress">
                <div style="width:${Math.round((skills.length / maxPerCategory) * 100)}%"></div>
              </div>
            </div>
          `).join('')
      : '<p>Analyze a resume to visualize detected skills.</p>';

    if (container) container.innerHTML = html;
    if (bars) bars.innerHTML = html;
  }

  /* ── JOBS ──────────────────────────────────────────── */
  function initializeJobControls() {
    ['jobSearch', 'jobCategory', 'jobSort'].forEach((id) => {
      $(id)?.addEventListener('input', renderJobs);
      $(id)?.addEventListener('change', renderJobs);
    });
  }

  function renderJobs() {
    const container = $('jobCards');
    const hasData = state.jobs.length > 0;

    if (!container) return;
    if (!hasData) {
      container.innerHTML = state.resumeText
        ? '<p>No job recommendations available for this resume.</p>'
        : '<p>No job recommendations available. Analyze your resume first.</p>';
      renderDashboardJobs();
      renderJobMatchDistribution();
      return;
    }

    const search = ($('jobSearch')?.value || '').toLowerCase().trim();
    const category = categorySelect?.value || 'all';
    const sort = $('jobSort')?.value || 'match';

    let results = state.jobs.filter((job) => {
      const haystack = `${job.title} ${job.industry || ''} ${(job.skills || []).join(' ')}`.toLowerCase();
      const matchesSearch = !search || haystack.includes(search);
      const matchesCategory = category === 'all' || job.industry === category;
      return matchesSearch && matchesCategory;
    });

    results = [...results].sort((a, b) => {
      if (sort === 'title') return String(a.title).localeCompare(String(b.title));
      if (sort === 'matchAsc') return (a.score ?? 0) - (b.score ?? 0);
      if (sort === 'risk') return (a.risk_score ?? 1) - (b.risk_score ?? 1);
      return (b.score ?? 0) - (a.score ?? 0);
    });

    container.innerHTML = results.length
      ? results.map((job, index) => createJobCard(job, state.jobs.indexOf(job))).join('')
      : '<p>No matching jobs found.</p>';

    container.querySelectorAll('[data-job-details]').forEach((button) => {
      button.addEventListener('click', () => openJobModal(Number(button.dataset.jobDetails)));
    });

    renderDashboardJobs();
  }

  function createJobCard(job, index) {
    const riskLevel = job.risk_level || '--';
    return `
      <article class="job-card">
        <h3>${esc(job.title || 'Untitled role')}</h3>
        <span class="match-badge">${esc(job.score ?? 0)}% Match</span>
        <p><strong>Industry:</strong> ${esc(job.industry || '--')}</p>
        <p><strong>Risk:</strong> <span style="color:${riskColor(job.risk_level)}">${esc(riskLevel)}</span> (${esc(fmtRiskPct(job.risk_score))})</p>
        ${(job.skills || []).length
          ? `<div class="chips">${job.skills.map((s) => `<span class="chip">${esc(s)}</span>`).join('')}</div>`
          : ''}
        <button class="secondary-btn" data-job-details="${index}">View Details</button>
      </article>
    `;
  }

  function fmtRiskPct(score) {
    const n = Number(score);
    return Number.isFinite(n) ? `${Math.round(n * 100)}%` : '--';
  }

  function renderDashboardJobs() {
    const container = $('dashboardJobs');
    if (!container) return;

    if (!state.jobs.length) {
      container.innerHTML = state.resumeText
        ? '<p>No job matches available.</p>'
        : '<p>Analyze your resume to view career recommendations.</p>';
      setText('dashJobs', 0);
      return;
    }

    const topJobs = [...state.jobs].sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).slice(0, 3);
    container.innerHTML = topJobs
      .map((job, index) => createJobCard(job, state.jobs.indexOf(job)))
      .join('');

    container.querySelectorAll('[data-job-details]').forEach((button) => {
      button.addEventListener('click', () => openJobModal(Number(button.dataset.jobDetails)));
    });

    setText('dashJobs', state.jobs.length);
  }

  function renderJobMatchDistribution() {
    const container = $('jobMatchDistribution');
    if (!container) return;
    if (!state.jobs.length) {
      container.innerHTML = '<p>Analyze a resume to see the job match distribution.</p>';
      return;
    }
    container.innerHTML = state.jobs
      .slice()
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      .map((job) => `
        <div class="skill-row">
          <header>
            <span>${esc(job.title)}</span>
            <strong>${esc(job.score ?? 0)}%</strong>
          </header>
          <div class="progress">
            <div style="width:${Number(job.score) || 0}%"></div>
          </div>
        </div>`)
      .join('');
  }

  /* ── JOB MODAL ─────────────────────────────────────── */
  function initializeModal() {
    $('jobModalClose')?.addEventListener('click', closeJobModal);
    $('jobModal')?.addEventListener('click', (event) => {
      if (event.target.dataset?.modalClose !== undefined || event.target.classList.contains('modal-backdrop')) {
        closeJobModal();
      }
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeJobModal();
    });
  }

  function openJobModal(index) {
    const job = state.jobs[index];
    const modal = $('jobModal');
    const body = $('jobModalBody');
    if (!job || !modal || !body) return;

    const links = job.job_board_links || [];
    body.innerHTML = `
      <h2 id="jobModalTitle">${esc(job.title || 'Untitled role')}</h2>
      <p><strong>Match score:</strong> ${esc(job.score ?? 0)}%</p>
      <p><strong>Industry:</strong> ${esc(job.industry || '--')}</p>
      <p><strong>Career risk:</strong> <span style="color:${riskColor(job.risk_level)}">${esc(job.risk_level || '--')}</span> (${esc(fmtRiskPct(job.risk_score))})</p>
      ${(job.trait_chips || []).length
        ? `<p><strong>Traits:</strong></p><div class="chips">${job.trait_chips.map((t) => `<span class="chip">${esc(t)}</span>`).join('')}</div>`
        : ''}
      ${(job.skills || []).length
        ? `<p><strong>Your matching skills:</strong></p><div class="chips">${job.skills.map((s) => `<span class="chip chip--success">${esc(s)}</span>`).join('')}</div>`
        : ''}
      ${links.length
        ? `<p><strong>Find openings:</strong></p><div class="chips">${links
            .map((l) => `<a class="chip chip--link" href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${esc(l.label)}</a>`)
            .join('')}</div>`
        : ''}
      <p class="advisor-muted">Recommendation: strengthen the skills shown in your Skill Gap analysis to raise this match score.</p>
    `;
    modal.hidden = false;
  }

  function closeJobModal() {
    const modal = $('jobModal');
    if (modal) modal.hidden = true;
  }

  /* ── CAREER PATH (real backend suggestions) ────────── */
  function renderCareerPath() {
    const flow = $('careerFlow');
    const details = $('careerDetails');
    if (!flow) return;

    const paths = state.careerPaths;
    if (!paths.length) {
      flow.innerHTML = '<p>Analyze a resume to generate career path suggestions.</p>';
      if (details) details.innerHTML = 'Select a career stage to view details.';
      return;
    }

    const top = paths.slice(0, 5);
    flow.innerHTML = top
      .map((path, index) => `
        <button class="career-node" data-career-index="${index}">${esc(path.role)}</button>
        ${index < top.length - 1 ? '<span class="career-arrow">→</span>' : ''}
      `)
      .join('');

    flow.querySelectorAll('.career-node').forEach((button) => {
      button.addEventListener('click', () => {
        const path = top[Number(button.dataset.careerIndex)];
        const next = top[Number(button.dataset.careerIndex) + 1];
        if (!details) return;
        details.innerHTML = `
          <h2>${esc(path.role)}</h2>
          <p><strong>Level:</strong> ${esc(path.category || '--')}</p>
          <p><strong>Demand:</strong> ${esc(path.demand || '--')}${path.growing ? ' • Growing field' : ''}</p>
          <p><strong>Description:</strong> ${esc(path.description || '--')}</p>
          <p><strong>Skills needed:</strong> ${esc((path.skills_needed || []).join(', ') || '--')}</p>
          <p><strong>Your matched keywords:</strong> ${esc((path.matched_keywords || []).join(', ') || 'none detected')}</p>
          ${next ? `<p><strong>Recommended next step:</strong> ${esc(next.role)}</p>` : '<p><strong>Recommended next step:</strong> Deepen expertise in this role.</p>'}
        `;
      });
    });
  }

  /* ── ROADMAP (real learning roadmap) ───────────────── */
  function renderRoadmap() {
    const container = $('roadmapCards');
    if (!container) return;

    const roadmap = state.roadmap;
    if (!state.resumeText) {
      container.innerHTML = '<p>Complete skill-gap analysis to generate your roadmap.</p>';
      return;
    }
    if (!roadmap || !roadmap.length) {
      container.innerHTML = '<p>No learning roadmap could be generated for this resume.</p>';
      return;
    }

    const nextSteps = state.analysis?.guided_next_steps || [];
    const careerReady = nextSteps.length
      ? nextSteps.map((s) => (typeof s === 'string' ? s : s.title || s.action || '')).filter(Boolean)
      : ['Build a portfolio project for your target role.', 'Update your resume with the new skills.', 'Practice with the Interview Preparation page.'];

    container.innerHTML = `
      ${roadmap.map((area) => `
        <article class="roadmap-card">
          <small>${esc(area.icon || '')} ${esc(area.area)}</small>
          ${(area.stages || []).map((stage) => `
            <details class="roadmap-stage">
              <summary>${esc(stage.level)} <small>(${esc(stage.duration || '')})</small></summary>
              <p>${esc(stage.description)}</p>
            </details>
          `).join('')}
        </article>
      `).join('')}
      <article class="roadmap-card roadmap-card--ready">
        <small>🎯 Career Ready</small>
        <h2>Final preparations</h2>
        ${careerReady.map((step) => `<p>✓ ${esc(step)}</p>`).join('')}
      </article>
    `;
  }

  /* ── INTERVIEW (local question bank — no backend endpoint) ── */
  const questionBank = {
    python: [
      { q: 'What is the difference between a list and a tuple in Python?', a: 'Lists are mutable and tuples are immutable; discuss syntax, performance and typical use cases.' },
      { q: 'What are Python decorators?', a: 'Decorators wrap or extend function/class behavior without modifying the original implementation.' },
      { q: 'What is a dictionary in Python?', a: 'Key-value storage with unique keys; cover common operations like get, set, delete and iteration.' },
    ],
    web: [
      { q: 'What is the difference between client-side and server-side rendering?', a: 'Discuss where HTML is generated, initial load performance, SEO and interactivity.' },
      { q: 'What is the DOM?', a: 'The browser’s tree representation of an HTML document that JavaScript can query and manipulate.' },
    ],
    ai: [
      { q: 'What is overfitting in machine learning?', a: 'A model learns training data too closely and performs poorly on unseen data; mention regularization and validation.' },
      { q: 'What is supervised learning?', a: 'Learning from labelled examples to predict outputs for new, unseen data.' },
    ],
    database: [
      { q: 'What is database normalization?', a: 'Reducing redundancy and improving integrity through normal forms.' },
      { q: 'What is a primary key?', a: 'A unique identifier for records in a table; mention constraints and indexing.' },
    ],
    hr: [
      { q: 'Tell me about yourself.', a: 'A concise professional summary: education, relevant skills, projects and career goals.' },
      { q: 'Why should we hire you?', a: 'Connect your skills and project evidence directly to the role requirements.' },
    ],
  };

  function initializeInterview() {
    $('generateQuestion')?.addEventListener('click', generateQuestion);
    $('showAnswer')?.addEventListener('click', toggleAnswer);
    $('prevQuestion')?.addEventListener('click', () => stepQuestion(-1));
    $('nextQuestion')?.addEventListener('click', () => stepQuestion(1));
    $('resetInterview')?.addEventListener('click', resetInterview);
  }

  function generateQuestion() {
    const category = $('questionCategory')?.value || 'python';
    const list = questionBank[category] || [];
    if (!list.length) return;

    const unasked = list.map((item, i) => ({ ...item, i })).filter((item) => !state.askedQuestions.has(`${category}:${item.i}`));
    const pool = unasked.length ? unasked : list.map((item, i) => ({ ...item, i }));
    const picked = pool[Math.floor(Math.random() * pool.length)];

    state.askedQuestions.add(`${category}:${picked.i}`);
    state.currentQuestion = { ...picked, category, listLength: list.length };

    setText('questionText', picked.q);
    setText('questionNumber', `Practice Question • ${category.toUpperCase()}`);
    const guide = $('answerGuide');
    if (guide) { guide.textContent = ''; guide.hidden = true; }
    if ($('showAnswer')) $('showAnswer').disabled = false;
    if ($('nextQuestion')) $('nextQuestion').disabled = false;
    if ($('resetInterview')) $('resetInterview').disabled = false;
  }

  function stepQuestion(direction) {
    if (!state.currentQuestion) { generateQuestion(); return; }
    const category = state.currentQuestion.category;
    const list = questionBank[category] || [];
    const nextIndex = (state.currentQuestion.i + direction + list.length) % list.length;
    const picked = { ...list[nextIndex], i: nextIndex };

    state.askedQuestions.add(`${category}:${picked.i}`);
    state.currentQuestion = { ...picked, category };

    setText('questionText', picked.q);
    setText('questionNumber', `Practice Question • ${category.toUpperCase()}`);
    const guide = $('answerGuide');
    if (guide) { guide.textContent = ''; guide.hidden = true; }
  }

  function toggleAnswer() {
    const guide = $('answerGuide');
    if (!guide || !state.currentQuestion) return;
    if (guide.hidden || !guide.textContent) {
      guide.textContent = state.currentQuestion.a;
      guide.hidden = false;
      setText('showAnswer', 'Hide Answer Guide');
    } else {
      guide.hidden = true;
      setText('showAnswer', 'Show Answer Guide');
    }
  }

  function resetInterview() {
    state.currentQuestion = null;
    state.askedQuestions.clear();
    setText('questionText', 'Select a category and generate a question.');
    setText('questionNumber', '');
    const guide = $('answerGuide');
    if (guide) { guide.textContent = ''; guide.hidden = true; }
    ['showAnswer', 'nextQuestion', 'resetInterview'].forEach((id) => {
      const btn = $(id);
      if (btn) btn.disabled = true;
    });
    if ($('prevQuestion')) $('prevQuestion').disabled = true;
  }

  /* ── AI CAREER ASSISTANT (existing /api/career-chat) ── */
  function initializeChat() {
    $('sendChat')?.addEventListener('click', sendChat);
    $('chatInput')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') sendChat();
    });
    document.querySelectorAll('.chat-chip').forEach((chip) => {
      chip.addEventListener('click', () => {
        const input = $('chatInput');
        if (input) input.value = chip.textContent.trim();
        sendChat();
      });
    });
  }

  async function sendChat() {
    const input = $('chatInput');
    const message = input?.value.trim();
    if (!message || state.busy) return;

    appendMessage(message, 'user');
    if (input) input.value = '';

    const thinking = appendMessage('AI Career Assistant is thinking…', 'bot advisor-thinking');

    try {
      const data = await apiPost('/api/career-chat', {
        message,
        session_id: state.sessionId,
        resume_text: state.resumeText || '',
      });
      thinking.remove();
      state.sessionId = data.session_id || state.sessionId;
      appendMessage(data.reply || data.answer || 'No response received.', 'bot');
    } catch (error) {
      thinking.remove();
      appendMessage('Sorry — the assistant is unavailable right now. Please try again.', 'bot');
      showToast(error.message || 'Assistant request failed.', 'error');
    }
  }

  function appendMessage(text, type) {
    const container = $('chatMessages');
    if (!container) return null;
    const div = document.createElement('div');
    div.className = type.includes('user') ? 'user-message' : type;
    div.textContent = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
  }

  /* ── REPORTS ───────────────────────────────────────── */
  function renderReports() {
    const container = $('reportList');
    if (!container) return;

    if (!state.analysis && !state.resumeScore) {
      container.innerHTML = '<p>No reports available.</p>';
      return;
    }

    const cards = [];

    if (state.resumeScore) {
      cards.push(`
        <article class="job-card">
          <h3>Resume Analysis</h3>
          <p>Overall score: ${esc(state.resumeScore.final_score ?? '--')}/100</p>
          <p>Skills: ${esc(state.resumeScore.skill_score ?? '--')} • Experience: ${esc(state.resumeScore.experience_score ?? '--')} • Quality: ${esc(state.resumeScore.quality_score ?? '--')}</p>
          <p>${esc(state.resumeScore.feedback || '')}</p>
        </article>`);
    }

    if (state.analysis) {
      const topRole = (state.analysis.top_roles || [])[0];
      cards.push(`
        <article class="job-card">
          <h3>Skill Analysis</h3>
          <p>Detected skills: ${esc(state.skills.length)}</p>
          <p>Categories: ${esc(Object.keys(state.skillsByCategory).length)}</p>
          ${topRole ? `<p>Strongest role match: ${esc(topRole.job_role || '--')} (${esc(topRole.similarity ? Math.round(topRole.similarity * 100) + '%' : '--')})</p>` : ''}
        </article>`);
    }

    if (state.risk) {
      cards.push(`
        <article class="job-card">
          <h3>Career Risk</h3>
          <p>Level: ${esc(state.risk.risk_level || '--')}</p>
          <p>Score: ${esc(fmtRiskPct(state.risk.risk_score))}</p>
          <p>${esc(state.risk.explanation || '')}</p>
        </article>`);
    }

    if (state.skillGap) {
      cards.push(`
        <article class="job-card">
          <h3>Skill Gap — ${esc(state.targetRole || '')}</h3>
          <p>Match: ${esc(state.skillGap.match_percentage ?? '--')}%</p>
          <p>Missing: ${esc((state.skillGap.missing_skills || []).join(', ') || 'none')}</p>
        </article>`);
    }

    container.innerHTML = cards.length
      ? cards.join('')
      : '<p>No reports available yet.</p>';
  }

  /* ── HISTORY ───────────────────────────────────────── */
  function saveHistoryEntry() {
    const topJob = [...state.jobs].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))[0];
    state.history.unshift({
      id: Date.now(),
      file: state.file?.name || 'Pasted resume',
      score: state.resumeScore?.final_score ?? null,
      ats: state.resumeScore?.quality_score ?? null,
      skills: state.skills.length,
      match: state.skillGap?.match_percentage ?? null,
      risk: state.risk?.risk_level || 'N/A',
      topJob: topJob?.title || 'N/A',
      date: new Date().toLocaleString(),
    });
    state.history = state.history.slice(0, 10);
  }

  function renderHistory() {
    const container = $('historyList');
    if (!container) return;

    if (!state.history.length) {
      container.innerHTML = '<p>No previous analyses.</p>';
      return;
    }

    container.innerHTML = state.history.map((item) => `
      <div class="panel history-entry">
        <strong>${esc(item.file)}</strong>
        <p>${esc(item.date)}</p>
        <small>
          Resume: ${esc(item.score ?? '--')} |
          ATS: ${esc(item.ats ?? '--')} |
          Skills: ${esc(item.skills)} |
          Match: ${esc(item.match ?? '--')}% |
          Risk: ${esc(item.risk)} |
          Top: ${esc(item.topJob)}
        </small>
        <div class="history-actions">
          <button class="secondary-btn history-view" data-history-id="${item.id}">View</button>
          <button class="secondary-btn history-delete" data-history-id="${item.id}">Delete</button>
        </div>
      </div>
    `).join('');

    container.querySelectorAll('.history-view').forEach((button) => {
      button.addEventListener('click', () => {
        const entry = state.history.find((h) => h.id === Number(button.dataset.historyId));
        if (!entry) return;
        goToPage('reports');
        const container2 = $('reportList');
        if (container2) {
          container2.innerHTML = `
            <article class="job-card">
              <h3>${esc(entry.file)} — ${esc(entry.date)}</h3>
              <p>Resume Score: ${esc(entry.score ?? '--')}/100</p>
              <p>ATS: ${esc(entry.ats ?? '--')}%</p>
              <p>Skills Detected: ${esc(entry.skills)}</p>
              <p>Skill Match: ${esc(entry.match ?? '--')}%</p>
              <p>Career Risk: ${esc(entry.risk)}</p>
              <p>Top Recommendation: ${esc(entry.topJob)}</p>
            </article>`;
        }
      });
    });

    container.querySelectorAll('.history-delete').forEach((button) => {
      button.addEventListener('click', () => {
        const id = Number(button.dataset.historyId);
        if (!window.confirm('Delete this history entry?')) return;
        state.history = state.history.filter((entry) => entry.id !== id);
        saveState();
        renderHistory();
        showToast('History entry deleted.', 'info');
      });
    });
  }

  /* ── RESUME PAGE RENDER ────────────────────────────── */
  function renderResume() {
    const score = state.resumeScore;
    setText('dashResumeScore', score ? `${score.final_score}/100` : '--');
    setText('dashATS', score ? `${score.quality_score}%` : '--');

    // Animate the score meter from real data (respects the no-anim preference)
    const meter = $('resumeScore');
    if (meter) {
      const target = Number(score?.final_score);
      if (Number.isFinite(target)) {
        if (document.body.classList.contains('no-anim') || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
          meter.textContent = `${target}`;
        } else {
          const duration = 900;
          const start = performance.now();
          const step = (now) => {
            const progress = Math.min(1, (now - start) / duration);
            meter.textContent = `${Math.round(target * progress)}`;
            if (progress < 1) requestAnimationFrame(step);
          };
          requestAnimationFrame(step);
        }
      } else {
        meter.textContent = '--';
      }
    }

    const feedback = $('resumeFeedback');
    if (feedback) {
      feedback.innerHTML = score
        ? `<p>${esc(score.feedback || '')}</p>
           ${(score.strengths || []).length ? `<p><strong>Strengths:</strong> ${esc(score.strengths.join('; '))}</p>` : ''}
           ${(score.improvements || []).length ? `<p><strong>Improvements:</strong> ${esc(score.improvements.join('; '))}</p>` : ''}`
        : '<p>Analyze a resume to view your score.</p>';
    }

    const suggestions = $('resumeSuggestions');
    if (suggestions) {
      const improvements = score?.improvements || [];
      suggestions.innerHTML = improvements.length
        ? improvements.map((item) => `<p>✓ ${esc(item)}</p>`).join('')
        : '<p>No suggestions available yet.</p>';
    }

    renderATS();
  }

  /* ── SETTINGS / THEME ──────────────────────────────── */
  function initializeTheme() {
    $('themeBtn')?.addEventListener('click', toggleTheme);
    $('darkToggle')?.addEventListener('change', (event) => {
      document.body.classList.toggle('light', !event.target.checked);
      saveState();
    });
  }

  function toggleTheme() {
    document.body.classList.toggle('light');
    const darkToggle = $('darkToggle');
    if (darkToggle) darkToggle.checked = !document.body.classList.contains('light');
    saveState();
  }

  function initializeSettings() {
    $('saveSettings')?.addEventListener('click', () => {
      const name = $('profileName')?.value.trim();
      localStorage.setItem('careerProfileName', name || 'Student');

      const dark = $('darkToggle');
      if (dark) {
        document.body.classList.toggle('light', !dark.checked);
        localStorage.setItem('careerTheme', dark.checked ? 'dark' : 'light');
      }
      const collapsed = $('sidebarToggle');
      if (collapsed) {
        document.querySelector('.app')?.classList.toggle('sidebar-collapsed', collapsed.checked);
        localStorage.setItem('careerSidebarCollapsed', collapsed.checked ? '1' : '0');
        const btn = $('sidebarCollapse');
        if (btn) btn.textContent = collapsed.checked ? '▶' : '◀';
      }
      const anims = $('animationsToggle');
      if (anims) {
        document.body.classList.toggle('no-anim', !anims.checked);
        localStorage.setItem('careerAnimations', anims.checked ? 'on' : 'off');
      }
      const notifs = $('notificationsToggle');
      if (notifs) localStorage.setItem('careerNotifications', notifs.checked ? 'on' : 'off');

      showToast('Settings saved.', 'success');
    });
  }

  function renderProfile() {
    const name = localStorage.getItem('careerProfileName') || 'Student';
    const nameField = $('profileName');
    if (nameField && !nameField.value) nameField.value = name;

    const emailField = $('profileEmail');
    if (emailField && !emailField.value) emailField.value = 'Sign in to view account email';

    const target = $('profileTargetCareer');
    if (target) target.value = state.targetRole || 'Not set';

    const experience = $('profileExperience');
    if (experience) {
      const expScore = state.resumeScore?.experience_score;
      experience.value = Number.isFinite(expScore)
        ? `Experience score: ${expScore}/100 (from /score_resume)`
        : 'Analyze a resume to estimate experience level';
    }

    const avatar = $('profileAvatar');
    if (avatar) avatar.textContent = (name || 'S').charAt(0).toUpperCase();
  }

  /* ── GLOBAL SEARCH ─────────────────────────────────── */
  function initializeGlobalSearch() {
    const input = $('globalSearch');
    const results = $('globalSearchResults');
    if (!input || !results) return;

    const pageIndex = [
      { label: 'Dashboard', page: 'dashboard' },
      { label: 'Resume Analysis', page: 'resume' },
      { label: 'Skill Extraction', page: 'skills' },
      { label: 'Skill Gap Analysis', page: 'gap' },
      { label: 'Career Risk', page: 'risk' },
      { label: 'Job Matching', page: 'jobs' },
      { label: 'Career Path', page: 'career' },
      { label: 'Reskilling Roadmap', page: 'roadmap' },
      { label: 'Interview Preparation', page: 'interview' },
      { label: 'AI Career Assistant', page: 'assistant' },
      { label: 'Reports', page: 'reports' },
      { label: 'History', page: 'history' },
      { label: 'Profile & Settings', page: 'profile' },
    ];

    const runSearch = () => {
      const query = input.value.toLowerCase().trim();
      if (!query) { results.hidden = true; return; }

      const pageHits = pageIndex.filter((p) => p.label.toLowerCase().includes(query));
      const jobHits = state.jobs
        .filter((j) => `${j.title} ${j.industry || ''}`.toLowerCase().includes(query))
        .slice(0, 4)
        .map((j) => ({ label: `Job: ${j.title} (${j.score ?? 0}%)`, page: 'jobs' }));
      const skillHits = state.skills
        .filter((s) => s.toLowerCase().includes(query))
        .slice(0, 4)
        .map((s) => ({ label: `Skill: ${s}`, page: 'skills' }));

      const hits = [...pageHits, ...jobHits, ...skillHits].slice(0, 8);
      if (!hits.length) {
        results.innerHTML = '<p class="search-empty">No matches found.</p>';
      } else {
        results.innerHTML = hits
          .map((hit) => `<button class="search-result" data-page="${hit.page}">${esc(hit.label)}</button>`)
          .join('');
        results.querySelectorAll('.search-result').forEach((btn) => {
          btn.addEventListener('click', () => {
            goToPage(btn.dataset.page);
            results.hidden = true;
            input.value = '';
          });
        });
      }
      results.hidden = false;
    };

    input.addEventListener('input', runSearch);
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        const first = results.querySelector('.search-result');
        if (first) first.click();
      }
      if (event.key === 'Escape') results.hidden = true;
    });
    document.addEventListener('click', (event) => {
      if (!event.target.closest('.search-wrap')) results.hidden = true;
    });
  }

  /* ── PRINT ─────────────────────────────────────────── */
  function initializePrint() {
    $('printReportBtn')?.addEventListener('click', () => {
      goToPage('reports');
      setTimeout(() => window.print(), 150);
    });
  }

  /* ── CENTRAL UI REFRESH ────────────────────────────── */
  function renderApplication() {
    renderResume();
    renderSkills();
    renderSkillGap();
    renderRisk();
    renderJobs();
    renderJobMatchDistribution();
    renderCareerPath();
    renderRoadmap();
    renderReports();
    renderHistory();
    renderProfile();
  }

  /* ── STORAGE (summaries only — never the resume itself) ── */
  function saveState() {
    const safeState = {
      resumeScore: state.resumeScore,
      risk: state.risk,
      skills: state.skills,
      skillsByCategory: state.skillsByCategory,
      skillGap: state.skillGap,
      targetRole: state.targetRole,
      jobs: state.jobs,
      careerPaths: state.careerPaths,
      roadmap: state.roadmap,
      history: state.history,
    };
    localStorage.setItem('careerDashboardState', JSON.stringify(safeState));
    localStorage.setItem('careerTheme', document.body.classList.contains('light') ? 'light' : 'dark');
  }

  function restoreState() {
    try {
      const saved = JSON.parse(localStorage.getItem('careerDashboardState'));
      if (saved && typeof saved === 'object') {
        state.resumeScore = saved.resumeScore ?? null;
        state.risk = saved.risk ?? null;
        state.skills = Array.isArray(saved.skills) ? saved.skills : [];
        state.skillsByCategory = saved.skillsByCategory || {};
        state.skillGap = saved.skillGap ?? null;
        state.targetRole = saved.targetRole || '';
        state.jobs = Array.isArray(saved.jobs) ? saved.jobs : [];
        state.careerPaths = Array.isArray(saved.careerPaths) ? saved.careerPaths : [];
        state.roadmap = saved.roadmap ?? null;
        state.history = Array.isArray(saved.history) ? saved.history : [];
      }
    } catch {
      localStorage.removeItem('careerDashboardState');
    }

    if (localStorage.getItem('careerTheme') === 'light') {
      document.body.classList.add('light');
    }
    const darkToggle = $('darkToggle');
    if (darkToggle) darkToggle.checked = !document.body.classList.contains('light');

    const name = localStorage.getItem('careerProfileName');
    if (name && $('profileName')) $('profileName').value = name;
    if (state.targetRole && $('targetRole')) $('targetRole').value = state.targetRole;
  }

  initializePrint();
})();
