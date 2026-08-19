/**
 * Career Analysis — Connected Feature Flow
 * Dashboard → Resume → Skills → Careers → Skill Gap → Roadmap → Jobs → AI Advisor → Settings
 */
(() => {
  'use strict';

  // ── State ──────────────────────────────────────────────────
  let resumeText = '';
  let skillsData = null;
  let careerPaths = [];
  let selectedCareer = null;
  let gapData = null;
  let roadmapData = [];
  let personalizedRoadmap = null; // New personalized roadmap data
  let roadmapCompletion = {}; // { "phaseIdx-itemIdx": true }
  let currentStep = 0;
  const steps = ['dashboard', 'resume', 'skill-extraction', 'skills', 'careers', 'gap', 'roadmap', 'jobs', 'advisor', 'settings'];
  const ANALYSIS_STEPS = ['resume', 'skill-extraction', 'skills', 'careers', 'gap', 'roadmap'];

  // Activity log
  let activityLog = [];

  // ── DOM refs ───────────────────────────────────────────────
  const app = document.querySelector('[data-career-app]');
  if (!app) return;

  const $ = (s, p = document) => p.querySelector(s);
  const $$ = (s, p = document) => Array.from(p.querySelectorAll(s));

  // Sidebar
  const sidebarToggle = $('[data-career-sidebar-toggle]');
  const sidebarBackdrop = $('[data-career-sidebar-backdrop]');
  const navItems = $$('.career-nav-item');
  const progressFill = $('[data-progress-fill]');
  const progressText = $('[data-progress-text]');

  // Step 1: Resume
  const resumeFile = $('[data-resume-file]');
  const uploadZone = $('[data-upload-zone]');
  const resumeTextEl = $('[data-resume-text]');
  const analyzeBtn = $('[data-analyze-btn]');
  const loading = $('[data-loading]');
  const resumeResults = $('[data-resume-results]');
  const nextCareersBtn = $('[data-next-careers]');

  // Step 2: Careers
  const careerCards = $('[data-career-cards]');
  const nextGapBtn = $('[data-next-gap]');
  const profileSkills = $('[data-profile-skills]');
  const profileExp = $('[data-profile-exp]');
  const profileStrength = $('[data-profile-strength]');

  // Career Recommendations Dashboard (new UI)
  const recRanks = $('[data-career-rec-ranks]');
  const recDetail = $('[data-career-rec-detail]');
  const recTopMatch = $('[data-rec-top-match]');
  const recTopMatchPct = $('[data-rec-top-match-pct]');
  const recCareersCount = $('[data-rec-careers-count]');
  const recAvgMatch = $('[data-rec-avg-match]');
  const recDemand = $('[data-rec-demand]');
  const outlookSalary = $('[data-outlook-salary]');
  const outlookGrowth = $('[data-outlook-growth]');
  const outlookOpportunities = $('[data-outlook-opportunities]');
  const companiesGrid = $('[data-companies-grid]');
  const relatedList = $('[data-related-list]');
  const viewAllCareers = $('[data-view-all-careers]');
  const viewMoreCareers = $('[data-view-more-careers]');
  const reanalyzeBtn = $('[data-reanalyze-btn]');

  // Step 3: Gap
  const gapRoleSelect = $('[data-gap-role-select]');
  const gapAnalyzeBtn = $('[data-gap-analyze-btn]');
  const gapLoading = $('[data-gap-loading]');
  const gapResults = $('[data-gap-results]');
  const gapTarget = $('[data-gap-target]');
  const matchValue = $('[data-match-value]');
  const matchRing = $('[data-match-ring]');
  const matchedSkills = $('[data-matched-skills]');
  const missingSkills = $('[data-missing-skills]');
  const highPriority = $('[data-high-priority]');
  const mediumPriority = $('[data-medium-priority]');
  const lowPriority = $('[data-low-priority]');
  const nextRoadmapBtn = $('[data-next-roadmap]');

  // Step 4: Roadmap
  const roadmapPhases = $('[data-roadmap-phases]');
  const roadmapProgress = $('[data-roadmap-progress]');
  const roadmapSummary = $('[data-roadmap-summary]');

  // Dashboard
  const dashAnalyses = $('[data-dash-analyses]');
  const dashCareers = $('[data-dash-careers]');
  const dashSkills = $('[data-dash-skills]');
  const dashMatch = $('[data-dash-match]');
  const dashRoadmapProgress = $('[data-dash-roadmap-progress]');
  const dashActivity = $('[data-dash-activity]');
  const dashStartBtn = $('[data-dash-start]');

  // Skills deep dive
  const skillsOverview = $('[data-skills-overview]');
  const skillsEmpty = $('[data-skills-empty]');
  const totalTech = $('[data-total-tech]');
  const totalSoft = $('[data-total-soft]');
  const totalCategories = $('[data-total-categories]');
  const skillsStrengths = $('[data-skills-strengths]');
  const skillsCategoryBars = $('[data-skills-category-bars]');
  const skillsGotoResume = $('[data-skills-goto-resume]');

  // Jobs
  const jobsSearchInput = $('[data-jobs-search-input]');
  const jobsSearchBtn = $('[data-jobs-search-btn]');
  const jobsList = $('[data-jobs-list]');
  const jobsEmpty = $('[data-jobs-empty]');
  const jobsFilters = $$('[data-jobs-filter]');

  // AI Advisor
  const advisorMessages = $('[data-advisor-messages]');
  const advisorInput = $('[data-advisor-input]');
  const advisorSend = $('[data-advisor-send]');
  const advisorClear = $('[data-advisor-clear]');
  const advisorSuggestions = $$('[data-advisor-prompt]');

  // Settings
  const themePrefBtns = $$('[data-theme-pref]');

  // ── Helpers ────────────────────────────────────────────────
  const csrfToken = () => {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  };

  const apiPost = async (url, body) => {
    const headers = { 'X-CSRFToken': csrfToken() };
    if (body && !(body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(body);
    }
    return fetch(url, { method: 'POST', headers, body });
  };

  const toast = (msg, type = 'info') => {
    const container = document.querySelector('[data-toast-container]');
    if (!container) return;
    const el = document.createElement('div');
    el.className = `toast toast--${type}`;
    el.innerHTML = `<span class="toast__msg">${msg}</span><button class="toast__close" aria-label="Dismiss">&times;</button>`;
    const dismiss = () => { el.classList.remove('toast--visible'); setTimeout(() => el.remove(), 300); };
    el.querySelector('.toast__close').addEventListener('click', dismiss);
    container.appendChild(el);
    requestAnimationFrame(() => el.classList.add('toast--visible'));
    setTimeout(dismiss, 4000);
  };

  const addActivity = (text) => {
    activityLog.unshift({ text, time: new Date() });
    if (activityLog.length > 10) activityLog = activityLog.slice(0, 10);
    renderActivity();
  };

  const renderActivity = () => {
    if (!dashActivity) return;
    if (!activityLog.length) {
      dashActivity.innerHTML = '<div class="career-dash-empty"><span>📄</span><p>No activity yet. Run your first analysis to get started!</p></div>';
      return;
    }
    dashActivity.innerHTML = activityLog.map(a => {
      const timeStr = a.time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      return `<div class="career-dash-activity-item" style="display:flex;gap:0.5rem;align-items:center;padding:0.4rem 0;border-bottom:1px solid var(--outline-variant);font-size:0.82rem;">
        <span style="color:var(--on-surface-variant);font-size:0.72rem;min-width:50px;">${timeStr}</span>
        <span style="color:var(--on-surface);">${a.text}</span>
      </div>`;
    }).join('');
  };

  // ── Navigation ─────────────────────────────────────────────
  const goToStep = (idx) => {
    if (idx < 0 || idx >= steps.length) return;
    currentStep = idx;

    // Update sections
    $$('.career-step').forEach((s, i) => s.classList.toggle('is-active', i === idx));

    // Update nav
    navItems.forEach((item, i) => {
      item.classList.toggle('is-active', i === idx);
      // Allow completed steps and the current step to be clickable
      if (i < idx || i === idx) {
        // Keep it enabled if it's in ANALYSIS_STEPS and we've done the prerequisite
        const stepName = steps[i];
        if (stepName === 'dashboard' || stepName === 'settings') {
          item.disabled = false;
        }
      }
    });

    // Update progress bar (only for analysis steps)
    const analysisIdx = ANALYSIS_STEPS.indexOf(steps[idx]);
    if (analysisIdx >= 0) {
      const pct = ((analysisIdx + 1) / ANALYSIS_STEPS.length) * 100;
      progressFill.style.width = `${pct}%`;
      progressText.textContent = `Step ${analysisIdx + 1} of ${ANALYSIS_STEPS.length}`;
    } else if (steps[idx] === 'dashboard') {
      progressFill.style.width = '0%';
      progressText.textContent = 'Overview';
    } else {
      progressFill.style.width = '100%';
      progressText.textContent = steps[idx] === 'jobs' ? 'Job Search' : steps[idx] === 'advisor' ? 'AI Advisor' : 'Settings';
    }

    // Auto-populate gap select when navigating to gap step
    if (steps[idx] === 'gap' && gapRoleSelect && careerPaths.length) {
      gapRoleSelect.innerHTML = '<option value="">Select a career...</option>' +
        careerPaths.map(p => `<option value="${esc(p.role)}">${esc(p.role)} (${p.score}%)</option>`).join('');
      if (selectedCareer) gapRoleSelect.value = selectedCareer;
    }

    // Render careers when navigating to careers step
    if (steps[idx] === 'careers' && careerPaths.length) {
      renderCareerCards();
    }

    // Render skills deep dive when navigating to skills step
    if (steps[idx] === 'skills') {
      renderSkillsDeepDive();
    }

    // Close mobile sidebar
    app.classList.remove('is-sidebar-open');
  };

  // Sidebar toggle (mobile)
  if (sidebarToggle) sidebarToggle.addEventListener('click', () => app.classList.toggle('is-sidebar-open'));
  if (sidebarBackdrop) sidebarBackdrop.addEventListener('click', () => app.classList.remove('is-sidebar-open'));

  // Nav clicks
  navItems.forEach((item, idx) => {
    item.addEventListener('click', () => {
      if (!item.disabled) goToStep(idx);
    });
  });

  // Back button clicks
  document.querySelectorAll('[data-back-btn]').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetStep = btn.getAttribute('data-back-btn');
      const idx = steps.indexOf(targetStep);
      if (idx >= 0) goToStep(idx);
    });
  });

  // ── Dashboard ──────────────────────────────────────────────
  if (dashStartBtn) {
    dashStartBtn.addEventListener('click', () => {
      const resumeIdx = steps.indexOf('resume');
      goToStep(resumeIdx);
    });
  }

  function updateDashboard() {
    if (dashAnalyses) dashAnalyses.textContent = activityLog.filter(a => a.text.includes('analyzed')).length || 0;
    if (dashCareers) dashCareers.textContent = careerPaths.length || 0;
    if (dashSkills) dashSkills.textContent = skillsData?.count || 0;
    if (dashMatch) {
      const top = careerPaths[0];
      dashMatch.textContent = top ? `${top.score}%` : '—';
    }
    // Update roadmap progress on dashboard
    if (dashRoadmapProgress) {
      const stats = getRoadmapCompletionStats();
      dashRoadmapProgress.textContent = stats.total > 0 ? `${stats.pct}%` : '—';
    }
    // Update career score ring in sidebar
    updateCareerScoreRing();
  }

  function updateCareerScoreRing() {
    const scoreCircle = document.querySelector('[data-score-circle]');
    const scorePct = document.querySelector('[data-score-pct]');
    const scoreLabel = document.querySelector('[data-score-label]');
    if (!scoreCircle || !scorePct || !scoreLabel) return;
    const top = careerPaths[0];
    const score = top ? top.score : 0;
    const circumference = 2 * Math.PI * 42; // r=42 from SVG
    const offset = circumference - (score / 100) * circumference;
    scoreCircle.style.strokeDashoffset = offset;
    scorePct.textContent = score ? `${score}%` : '0%';
    if (score >= 70) { scoreLabel.textContent = 'Good'; scoreLabel.style.color = '#22c55e'; }
    else if (score >= 50) { scoreLabel.textContent = 'Fair'; scoreLabel.style.color = '#f59e0b'; }
    else { scoreLabel.textContent = 'Low'; scoreLabel.style.color = '#ef4444'; }
  }

  // ── STEP 1: Resume Analysis ────────────────────────────────
  // File upload
  if (resumeFile) {
    resumeFile.addEventListener('change', (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        resumeTextEl.value = ev.target.result;
        analyzeResume();
      };
      reader.readAsText(file);
    });
  }

  // Drag & drop
  if (uploadZone) {
    uploadZone.addEventListener('click', () => resumeFile?.click());
    uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('is-dragover'); });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('is-dragover'));
    uploadZone.addEventListener('drop', (e) => {
      e.preventDefault(); uploadZone.classList.remove('is-dragover');
      const file = e.dataTransfer.files?.[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = (ev) => { resumeTextEl.value = ev.target.result; analyzeResume(); };
        reader.readAsText(file);
      }
    });
  }

  if (analyzeBtn) analyzeBtn.addEventListener('click', analyzeResume);

  async function analyzeResume() {
    resumeText = (resumeTextEl?.value || '').trim();
    if (resumeText.length < 20) {
      toast('Please enter at least 20 characters of resume text.', 'warning');
      return;
    }

    loading?.classList.remove('hidden');
    resumeResults?.classList.add('hidden');
    analyzeBtn.disabled = true;

    try {
      const res = await apiPost('/api/upload', { resume_text: resumeText, mode: 'standard' });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Analysis failed');

      skillsData = data.skills || {};
      careerPaths = data.career_paths?.paths || [];

      // Render results
      renderResumeResults(data);
      loading?.classList.add('hidden');
      resumeResults?.classList.remove('hidden');
      toast('Resume analyzed successfully!', 'success');
      addActivity('Resume analyzed — ' + (skillsData.count || 0) + ' skills found');

      // Render Skill Extraction page
      if (typeof SkillExtraction !== 'undefined') {
        SkillExtraction.render(data);
      }

      // Enable all analysis steps
      enableAnalysisSteps();
      updateDashboard();
    } catch (err) {
      loading?.classList.add('hidden');
      toast(err.message || 'Analysis failed', 'error');
    } finally {
      analyzeBtn.disabled = false;
    }
  }

  function enableAnalysisSteps() {
    navItems.forEach((item, i) => {
      const stepName = steps[i];
      if (ANALYSIS_STEPS.includes(stepName) && stepName !== 'resume') {
        item.disabled = false;
      }
    });
  }

  function renderResumeResults(data) {
    const skills = data.skills || {};
    const parsed = data.parsed || {};

    // Stats
    const skillsCount = $('[data-skills-count]');
    const experience = $('[data-experience]');
    const education = $('[data-education]');
    const projects = $('[data-projects]');
    if (skillsCount) skillsCount.textContent = skills.count || 0;
    if (experience) experience.textContent = (parsed.experience || []).length;
    if (education) education.textContent = (parsed.education || []).length;
    if (projects) projects.textContent = (parsed.projects || []).length;

    // Separate technical vs soft skills
    const TECH_CATEGORIES = ['Programming Languages', 'Backend Frameworks', 'Frontend Frameworks', 'Databases', 'Cloud & Infrastructure', 'DevOps & CI/CD', 'Data Science & ML', 'AI / ML Frameworks', 'Web Technologies', 'Mobile Development', 'Testing', 'Version Control', 'System Design', 'Networking', 'Operating Systems', 'Security', 'Data Engineering', 'Data Visualization', 'Tools & Productivity'];
    const allSkills = skills.all_skills || [];
    const byCategory = skills.by_category || {};
    const techSkills = [];
    const softSkills = [];
    const techSeen = new Set();
    const softSeen = new Set();

    for (const [cat, sks] of Object.entries(byCategory)) {
      const isTech = TECH_CATEGORIES.some(tc => cat.includes(tc));
      for (const sk of sks) {
        if (isTech && !techSeen.has(sk.toLowerCase())) {
          techSkills.push(sk);
          techSeen.add(sk.toLowerCase());
        } else if (!isTech && !softSeen.has(sk.toLowerCase())) {
          softSkills.push(sk);
          softSeen.add(sk.toLowerCase());
        }
      }
    }
    for (const sk of allSkills) {
      if (!techSeen.has(sk.toLowerCase()) && !softSeen.has(sk.toLowerCase())) {
        techSkills.push(sk);
        techSeen.add(sk.toLowerCase());
      }
    }

    // Render technical skills
    const techSkillsEl = $('[data-technical-skills]');
    if (techSkillsEl) {
      techSkillsEl.innerHTML = techSkills.map(s =>
        `<span class="career-skill-tag career-skill-tag--primary">${esc(s)}</span>`
      ).join('') || '<span class="career-skill-tag">No technical skills detected</span>';
    }

    // Render soft skills
    const softSkillsEl = $('[data-soft-skills]');
    if (softSkillsEl) {
      softSkillsEl.innerHTML = softSkills.map(s =>
        `<span class="career-skill-tag">${esc(s)}</span>`
      ).join('') || '<span class="career-skill-tag">No soft skills detected</span>';
    }

    // Render categories
    const cats = $('[data-skill-categories]');
    if (cats) {
      cats.innerHTML = Object.entries(byCategory).map(([cat, sks]) =>
        `<div class="career-category-card">
          <div class="career-category-name">${esc(cat)}</div>
          <div class="career-category-count">${sks.length} skills</div>
          <div class="career-category-skills">${sks.slice(0, 4).join(', ')}${sks.length > 4 ? '...' : ''}</div>
        </div>`
      ).join('');
    }

    // Enable next step
    navItems[steps.indexOf('skills')].disabled = false;
    navItems[steps.indexOf('careers')].disabled = false;
  }

  if (nextCareersBtn) nextCareersBtn.addEventListener('click', () => {
    renderCareerCards();
    goToStep(steps.indexOf('careers'));
  });

  // ── Skills Deep Dive ───────────────────────────────────────
  if (skillsGotoResume) {
    skillsGotoResume.addEventListener('click', () => goToStep(steps.indexOf('resume')));
  }

  function renderSkillsDeepDive() {
    if (!skillsData) {
      skillsOverview?.classList.add('hidden');
      skillsEmpty?.classList.remove('hidden');
      return;
    }

    skillsEmpty?.classList.add('hidden');
    skillsOverview?.classList.remove('hidden');

    const TECH_CATEGORIES = ['Programming Languages', 'Backend Frameworks', 'Frontend Frameworks', 'Databases', 'Cloud & Infrastructure', 'DevOps & CI/CD', 'Data Science & ML', 'AI / ML Frameworks', 'Web Technologies', 'Mobile Development', 'Testing', 'Version Control', 'System Design', 'Networking', 'Operating Systems', 'Security', 'Data Engineering', 'Data Visualization', 'Tools & Productivity'];
    const byCategory = skillsData.by_category || {};
    const allSkills = skillsData.all_skills || [];

    let techCount = 0;
    let softCount = 0;
    const categoryCounts = [];

    for (const [cat, sks] of Object.entries(byCategory)) {
      const isTech = TECH_CATEGORIES.some(tc => cat.includes(tc));
      if (isTech) techCount += sks.length;
      else softCount += sks.length;
      categoryCounts.push({ name: cat, count: sks.length });
    }

    // Uncategorized skills
    const categorized = new Set();
    for (const sks of Object.values(byCategory)) {
      for (const sk of sks) categorized.add(sk.toLowerCase());
    }
    const uncategorized = allSkills.filter(s => !categorized.has(s.toLowerCase()));
    techCount += uncategorized.length;

    if (totalTech) totalTech.textContent = techCount;
    if (totalSoft) totalSoft.textContent = softCount;
    if (totalCategories) totalCategories.textContent = Object.keys(byCategory).length;

    // Strengths
    if (skillsStrengths) {
      const topSkills = allSkills.slice(0, 15);
      skillsStrengths.innerHTML = topSkills.map(s =>
        `<span class="career-skills-strength-tag">✓ ${esc(s)}</span>`
      ).join('') || '<span>No skills detected yet.</span>';
    }

    // Category bars
    if (skillsCategoryBars) {
      const maxCount = Math.max(...categoryCounts.map(c => c.count), 1);
      skillsCategoryBars.innerHTML = categoryCounts
        .sort((a, b) => b.count - a.count)
        .slice(0, 8)
        .map(c => {
          const pct = Math.round((c.count / maxCount) * 100);
          return `<div class="career-skill-bar">
            <span class="career-skill-bar__name">${esc(c.name)}</span>
            <div class="career-skill-bar__track"><div class="career-skill-bar__fill" style="width:${pct}%"></div></div>
            <span class="career-skill-bar__count">${c.count}</span>
          </div>`;
        }).join('');
    }
  }

  // ── STEP 2: Career Recommendations ─────────────────────────
  const CAREER_ICONS = {
    'Software Developer': '💻', 'Backend Developer': '🖥️', 'Frontend Developer': '🎨',
    'Full Stack Developer': '🌐', 'Data Analyst': '📊', 'Data Scientist': '🔬',
    'Cloud Engineer': '☁️', 'DevOps Engineer': '⚙️', 'Mobile App Developer': '📱',
    'Machine Learning Engineer': '🤖', 'AI Engineer': '🧠', 'Database Administrator': '🗄️',
    'Cybersecurity Analyst': '🔒', 'Product Manager': '📋', 'Project Manager': '📌',
    'UX Designer': '🎨', 'System Administrator': '🔧', 'Network Engineer': '🌐',
    'QA Engineer': '✅', 'Business Analyst': '📈', 'Solutions Architect': '🏗️',
    'Site Reliability Engineer': '⚡', 'Security Engineer': '🛡️', 'Embedded Systems Engineer': '🔌',
    'Data Engineer': '🔧', 'Blockchain Developer': '⛓️', 'Game Developer': '🎮',
    'Technical Writer': '📝', 'IT Consultant': '💼', 'Scrum Master': '🏃',
  };

  function getCareerIcon(role) {
    for (const [key, icon] of Object.entries(CAREER_ICONS)) {
      if (role.toLowerCase().includes(key.toLowerCase())) return icon;
    }
    return '💼';
  }

  // Career card icons for ranking
  const CAREER_CARD_ICONS = {
    'Software Developer': '💻', 'Backend Developer': '🗄️', 'Frontend Developer': '🎨',
    'Full Stack Developer': '🌐', 'Data Analyst': '📊', 'Cloud Engineer': '☁️',
    'DevOps Engineer': '🛡️', 'Mobile App Developer': '📱', 'Data Scientist': '🔬',
    'Machine Learning Engineer': '🤖', 'AI Engineer': '🧠', 'System Administrator': '⚙️',
  };

  function getRankCardIcon(role) {
    for (const [key, icon] of Object.entries(CAREER_CARD_ICONS)) {
      if (role.toLowerCase().includes(key.toLowerCase())) return icon;
    }
    return '💼';
  }

  function renderCareerCards() {
    const skills = skillsData || {};
    const paths = careerPaths || [];
    if (!paths.length) return;

    // ── Summary Cards ──
    const top = paths[0];
    const avgScore = paths.length ? Math.round(paths.reduce((s, p) => s + (p.score || 0), 0) / paths.length) : 0;
    const demands = paths.map(p => (p.demand || '').toLowerCase());
    let demandLabel = 'N/A';
    if (demands.some(d => d.includes('high'))) demandLabel = 'High';
    else if (demands.some(d => d.includes('medium'))) demandLabel = 'Medium';
    else if (demands.some(d => d.includes('low'))) demandLabel = 'Low';

    if (recTopMatch) recTopMatch.textContent = top ? top.role : '—';
    if (recTopMatchPct) recTopMatchPct.textContent = top ? `${top.score}% match` : '';
    if (recCareersCount) recCareersCount.textContent = paths.length;
    if (recAvgMatch) recAvgMatch.textContent = `${avgScore}%`;
    if (recDemand) recDemand.textContent = demandLabel;

    // ── Left: Career Rankings ──
    renderCareerRankings();

    // ── Right: Companies & Related ──
    renderCompanies(paths);

    // ── Default: select top career ──
    if (!selectedCareer && top) {
      renderCareerDetail(top);
    } else if (selectedCareer) {
      const p = paths.find(c => c.role === selectedCareer);
      if (p) renderCareerDetail(p);
    }

    // ── Keep old profile summary updated ──
    if (profileSkills) profileSkills.textContent = skills.count || 0;
    if (profileExp) profileExp.textContent = (resumeText.match(/\b(intern|engineer|developer|analyst|manager)\b/gi) || []).length || 0;
    if (profileStrength) profileStrength.textContent = `${Math.min(100, (skills.count || 0) * 5 + 20)}%`;

    // Old career cards still used by nextGapBtn flow
    if (careerCards) {
      careerCards.innerHTML = paths.slice(0, 6).map((p, i) => {
        const matched = (p.skills_analysis || []).filter(s => s.status === 'matched').map(s => s.skill);
        const missing = (p.missing_for_role || []).slice(0, 4);
        return `<div class="career-card ${i === 0 ? 'career-card--top' : ''}">
            <div class="career-card__header">
              <span class="career-card__title">${i === 0 ? '🥇 ' : ''}${esc(p.role)}</span>
              <span class="career-card__score">${p.score}% Match</span>
            </div>
            <div class="career-card__meta">${esc(p.category)} · ${esc(p.avg_salary || 'N/A')} · ${esc(p.demand || 'N/A')} demand</div>
            <div class="career-card__reasons">Why: ${(p.reasons || []).slice(0, 3).join(', ')}</div>
            <div class="career-card__skills">
              ${matched.slice(0, 5).map(s => `<span class="career-card__skill career-card__skill--matched">✓ ${esc(s)}</span>`).join('')}
              ${missing.map(s => `<span class="career-card__skill career-card__skill--missing">✗ ${esc(s)}</span>`).join('')}
            </div>
            <div class="career-card__actions">
              <button type="button" class="career-card__btn career-card__btn--primary" data-select-career="${esc(p.role)}">View Skill Gap</button>
              <button type="button" class="career-card__btn" data-search-job="${esc(p.role)}">Search Jobs</button>
            </div>
          </div>`;
      }).join('');

      $$('[data-select-career]', careerCards).forEach(btn => {
        btn.addEventListener('click', () => {
          selectedCareer = btn.dataset.selectCareer;
          gapRoleSelect.value = selectedCareer;
          goToStep(steps.indexOf('gap'));
        });
      });
      $$('[data-search-job]', careerCards).forEach(btn => {
        btn.addEventListener('click', () => {
          const role = btn.dataset.searchJob;
          if (jobsSearchInput) jobsSearchInput.value = role;
          goToStep(steps.indexOf('jobs'));
          searchJobs(role);
        });
      });
    }

    navItems[steps.indexOf('gap')].disabled = false;
    addActivity('Viewed ' + paths.length + ' career recommendations');
  }

  // ── Career Detail Panel ──────────────────────────────────────
  function renderCareerDetail(p) {
    selectedCareer = p.role;
    // Highlight selected rank
    $$('[data-rec-rank]').forEach(el => {
      el.classList.toggle('is-selected', el.dataset.recRank === p.role);
    });

    const matched = (p.skills_analysis || []).filter(s => s.status === 'matched').map(s => s.skill);
    const missing = (p.missing_for_role || []).slice(0, 6);
    const reasons = p.reasons || [];

    // Compute breakdown values deterministically from career data
    const totalRequired = (p.required_skills || []).length || 1;
    const skillsPct = Math.min(100, Math.round((matched.length / totalRequired) * 100));
    // Derive other percentages from available data (seeded by score for consistency)
    const baseScore = p.score || 50;
    const expPct = Math.min(100, Math.max(30, Math.round(skillsPct * 0.95 + (baseScore % 11) - 5)));
    const eduPct = Math.min(100, Math.max(40, Math.round(skillsPct * 1.1 + (baseScore % 13))));
    const otherPct = Math.max(20, Math.round(baseScore * 0.8));

    // Outlook data
    if (outlookSalary) outlookSalary.textContent = p.avg_salary || 'N/A';
    if (outlookGrowth) outlookGrowth.textContent = p.job_growth || 'N/A';
    if (outlookOpportunities) outlookOpportunities.textContent = p.demand || 'N/A';

    // Related careers
    if (relatedList) {
      const related = careerPaths.filter(c => c.role !== p.role).slice(0, 3);
      relatedList.innerHTML = related.map(r =>
        `<div class="career-rec-related__item" data-rec-related="${esc(r.role)}">
          <span>${esc(r.role)}</span>
          <span class="career-rec-related__item-arrow">›</span>
        </div>`
      ).join('') || '<div style="font-size:0.82rem;color:var(--on-surface-variant);">No related careers</div>';

      $$('[data-rec-related]', relatedList).forEach(el => {
        el.addEventListener('click', () => {
          const rp = careerPaths.find(c => c.role === el.dataset.recRelated);
          if (rp) renderCareerDetail(rp);
        });
      });
    }

    // Donut chart — proper non-overlapping arc segments
    const circumference = 2 * Math.PI * 45;
    const total = skillsPct + expPct + eduPct + otherPct || 100;
    const segSkills = (skillsPct / total) * circumference;
    const segExp = (expPct / total) * circumference;
    const segEdu = (eduPct / total) * circumference;
    const segOther = (otherPct / total) * circumference;
    // Each segment offset = previous segments' total length
    const gap = 4; // small gap between segments
    const offSkills = 0;
    const offExp = segSkills + gap;
    const offEdu = segSkills + segExp + gap * 2;
    const offOther = segSkills + segExp + segEdu + gap * 3;

    if (recDetail) {
      recDetail.innerHTML = `
        <div class="career-rec-detail__badge">✨ Best Match For You</div>
        <div class="career-rec-detail__header">
          <h2 class="career-rec-detail__title">${esc(p.role)}</h2>
          <span class="career-rec-detail__match-badge">${p.score}% Match</span>
        </div>
        <p class="career-rec-detail__desc">Great match! Your skills and experience align well with this career path.</p>
        <div class="career-rec-detail__tags">
          <span class="career-rec-detail__tag career-rec-detail__tag--green">🔥 High Demand</span>
          <span class="career-rec-detail__tag career-rec-detail__tag--blue">💰 Good Salary</span>
          <span class="career-rec-detail__tag career-rec-detail__tag--purple">📈 Growth Opportunity</span>
        </div>
        ${reasons.length ? `
        <div class="career-rec-detail__section">
          <h4 class="career-rec-detail__section-title">Why This Career?</h4>
          <p class="career-rec-detail__section-text">${esc(reasons.join('. '))}.</p>
        </div>` : ''}
        ${matched.length ? `
        <div class="career-rec-detail__section">
          <h4 class="career-rec-detail__section-title">Your Strengths</h4>
          <div class="career-rec-detail__strengths">
            ${matched.slice(0, 6).map(s => `<div class="career-rec-detail__strength"><span class="career-rec-detail__strength-icon">✓</span><span>${esc(s)}</span></div>`).join('')}
          </div>
        </div>` : ''}          <div class="career-rec-detail__breakdown">
          <div class="career-rec-donut">
            <svg viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="45" fill="none" stroke="var(--surface-container)" stroke-width="8"/>
              <circle cx="50" cy="50" r="45" fill="none" stroke="#3b82f6" stroke-width="8" stroke-dasharray="${segSkills} ${circumference - segSkills}" stroke-dashoffset="${-offSkills}" stroke-linecap="round" transform="rotate(-90 50 50)"/>
              <circle cx="50" cy="50" r="45" fill="none" stroke="#8b5cf6" stroke-width="8" stroke-dasharray="${segExp} ${circumference - segExp}" stroke-dashoffset="${-offExp}" stroke-linecap="round" transform="rotate(-90 50 50)"/>
              <circle cx="50" cy="50" r="45" fill="none" stroke="#22c55e" stroke-width="8" stroke-dasharray="${segEdu} ${circumference - segEdu}" stroke-dashoffset="${-offEdu}" stroke-linecap="round" transform="rotate(-90 50 50)"/>
              <circle cx="50" cy="50" r="45" fill="none" stroke="#f59e0b" stroke-width="8" stroke-dasharray="${segOther} ${circumference - segOther}" stroke-dashoffset="${-offOther}" stroke-linecap="round" transform="rotate(-90 50 50)"/>
            </svg>
            <div class="career-rec-donut__center">
              <div class="career-rec-donut__pct">${p.score}%</div>
              <div class="career-rec-donut__label">Overall Match</div>
            </div>
          </div>
          <div class="career-rec-breakdown__list">
            <div class="career-rec-breakdown__row">
              <span class="career-rec-breakdown__dot career-rec-breakdown__dot--skills"></span>
              <span class="career-rec-breakdown__name">Skills Match</span>
              <span class="career-rec-breakdown__pct">${skillsPct}%</span>
            </div>
            <div class="career-rec-breakdown__row">
              <span class="career-rec-breakdown__dot career-rec-breakdown__dot--experience"></span>
              <span class="career-rec-breakdown__name">Experience Match</span>
              <span class="career-rec-breakdown__pct">${expPct}%</span>
            </div>
            <div class="career-rec-breakdown__row">
              <span class="career-rec-breakdown__dot career-rec-breakdown__dot--education"></span>
              <span class="career-rec-breakdown__name">Education Match</span>
              <span class="career-rec-breakdown__pct">${eduPct}%</span>
            </div>
            <div class="career-rec-breakdown__row">
              <span class="career-rec-breakdown__dot career-rec-breakdown__dot--other"></span>
              <span class="career-rec-breakdown__name">Other Factors</span>
              <span class="career-rec-breakdown__pct">${otherPct}%</span>
            </div>
          </div>
        </div>
        <div class="career-rec-detail__actions">
          <button type="button" class="career-btn career-btn--primary" data-rec-view-gap="${esc(p.role)}">
            📊 View Skill Gap Analysis
          </button>
          <button type="button" class="career-btn career-btn--ghost" data-rec-view-roadmap="${esc(p.role)}">
            🗺️ View Learning Roadmap
          </button>
        </div>
      `;

      // Bind action buttons
      const gapBtn = $('[data-rec-view-gap]', recDetail);
      const roadmapBtn = $('[data-rec-view-roadmap]', recDetail);
      if (gapBtn) gapBtn.addEventListener('click', () => {
        selectedCareer = p.role;
        if (gapRoleSelect) {
          gapRoleSelect.innerHTML = '<option value="">Select a career...</option>' +
            careerPaths.map(cp => `<option value="${esc(cp.role)}">${esc(cp.role)} (${cp.score}%)</option>`).join('');
          gapRoleSelect.value = p.role;
        }
        goToStep(steps.indexOf('gap'));
      });
      if (roadmapBtn) roadmapBtn.addEventListener('click', async () => {
        selectedCareer = p.role;
        // Run skill gap analysis first if not done for this role
        if (!gapData || gapData.target_role !== p.role) {
          try {
            const gapRes = await apiPost('/api/skills-gap/analyze', { resume_text: resumeText, target_role: p.role });
            const gapJson = await gapRes.json();
            if (gapJson.success && gapJson.analysis) {
              gapData = gapJson.analysis;
            }
          } catch (e) { /* continue anyway */ }
        }
        generateRoadmap();
        goToStep(steps.indexOf('roadmap'));
      });
    }
  }

  // ── Companies Grid ───────────────────────────────────────────
  function renderCompanies(paths) {
    if (!companiesGrid) return;
    // SVG logos styled to match reference image
    const companies = [
      { name: 'Google', color: '#4285f4', svg: '<svg viewBox="0 0 24 24" width="20" height="20"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285f4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34a853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#fbbc05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#ea4335"/></svg>' },
      { name: 'Microsoft', color: '#00a4ef', svg: '<svg viewBox="0 0 24 24" width="20" height="20"><rect x="1" y="1" width="10" height="10" fill="#f25022"/><rect x="13" y="1" width="10" height="10" fill="#7fba00"/><rect x="1" y="13" width="10" height="10" fill="#00a4ef"/><rect x="13" y="13" width="10" height="10" fill="#ffb900"/></svg>' },
      { name: 'Amazon', color: '#ff9900', svg: '<svg viewBox="0 0 24 24" width="20" height="20"><text x="12" y="17" text-anchor="middle" font-size="14" font-weight="bold" fill="#ff9900">a</text></svg>' },
      { name: 'Meta', color: '#0668E1', svg: '<svg viewBox="0 0 24 24" width="20" height="20"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm3.09 7.5c-.41 0-.75.34-.75.75v.5c0 .41.34.75.75.75s.75-.34.75-.75v-.5c0-.41-.34-.75-.75-.75zm-6.18 0c-.41 0-.75.34-.75.75v.5c0 .41.34.75.75.75s.75-.34.75-.75v-.5c0-.41-.34-.75-.75-.75z" fill="#0668E1"/></svg>' },
      { name: 'Spotify', color: '#1db954', svg: '<svg viewBox="0 0 24 24" width="20" height="20"><circle cx="12" cy="12" r="10" fill="#1db954"/><path d="M7 14.5c2.5-1 5-1 7.5.3" stroke="white" stroke-width="1.5" fill="none" stroke-linecap="round"/><path d="M6 11.5c3-1.2 6.5-1.2 9.5.5" stroke="white" stroke-width="1.5" fill="none" stroke-linecap="round"/><path d="M5.5 8.5c3.5-1.5 8-1.5 11.5.7" stroke="white" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>' },
      { name: 'Figma', color: '#a259ff', svg: '<svg viewBox="0 0 24 24" width="20" height="20"><path d="M8 24c2.2 0 4-1.8 4-4v-4H8c-2.2 0-4 1.8-4 4s1.8 4 4 4z" fill="#0acf83"/><path d="M4 12c0-2.2 1.8-4 4-4h4v8H8c-2.2 0-4-1.8-4-4z" fill="#a259ff"/><path d="M4 4c0-2.2 1.8-4 4-4h4v8H8C5.8 8 4 6.2 4 4z" fill="#f24e1e"/><path d="M12 0h4c2.2 0 4 1.8 4 4s-1.8 4-4 4h-4V0z" fill="#ff7262"/><path d="M20 12c0 2.2-1.8 4-4 4s-4-1.8-4-4 1.8-4 4-4 4 1.8 4 4z" fill="#1abcfe"/></svg>' },
      { name: 'Netflix', color: '#e50914', svg: '<svg viewBox="0 0 24 24" width="20" height="20"><path d="M5 2h4l3 11V2h4v20h-4l-3-11v11H5V2z" fill="#e50914"/></svg>' }
    ];
    companiesGrid.innerHTML = companies.map((c, i) =>
      `<div class="career-rec-company" title="${c.name}" style="color:${c.color};">${c.svg}</div>`
    ).join('');
  }

  // Re-analyze button
  if (reanalyzeBtn) {
    reanalyzeBtn.addEventListener('click', () => {
      goToStep(steps.indexOf('resume'));
    });
  }

  // View all careers — toggle between showing 5 and all careers
  let showAllCareers = false;
  function renderCareerRankings() {
    if (!recRanks) return;
    const paths = showAllCareers ? careerPaths : careerPaths.slice(0, 5);
    recRanks.innerHTML = paths.map((p, i) => {
      const num = i + 1;
      const isSelected = selectedCareer === p.role;
      return `<div class="career-rec-rank ${isSelected ? 'is-selected' : ''}" data-rec-rank="${esc(p.role)}">
        <span class="career-rec-rank__num career-rec-rank__num--${num}">${num}</span>
        <span class="career-rec-rank__icon">${getRankCardIcon(p.role)}</span>
        <div class="career-rec-rank__info">
          <div class="career-rec-rank__name">${esc(p.role)}</div>
          <div class="career-rec-rank__match">${p.score}% match</div>
          <div class="career-rec-rank__bar"><div class="career-rec-rank__bar-fill" style="width:${p.score}%"></div></div>
        </div>
        <span class="career-rec-rank__arrow">›</span>
      </div>`;
    }).join('');
    // Bind click handlers
    $$('[data-rec-rank]', recRanks).forEach(el => {
      el.addEventListener('click', () => {
        const role = el.dataset.recRank;
        const p = careerPaths.find(c => c.role === role);
        if (p) renderCareerDetail(p);
      });
    });
    // Update button text
    if (viewAllCareers) viewAllCareers.textContent = showAllCareers ? 'Show Top 5 →' : 'View All Careers →';
    if (viewMoreCareers) viewMoreCareers.textContent = showAllCareers ? 'Show Top 5 →' : 'Explore More Careers →';
  }

  if (viewAllCareers) viewAllCareers.addEventListener('click', () => {
    showAllCareers = !showAllCareers;
    renderCareerRankings();
  });

  if (viewMoreCareers) viewMoreCareers.addEventListener('click', () => {
    showAllCareers = !showAllCareers;
    renderCareerRankings();
  });

  // View Full Outlook — navigate to jobs
  const viewFullOutlook = $('[data-view-full-outlook]');
  if (viewFullOutlook) {
    viewFullOutlook.addEventListener('click', () => {
      if (selectedCareer && jobsSearchInput) jobsSearchInput.value = selectedCareer;
      goToStep(steps.indexOf('jobs'));
      if (selectedCareer) searchJobs(selectedCareer);
    });
  }

  if (nextGapBtn) nextGapBtn.addEventListener('click', () => {
    if (gapRoleSelect) {
      gapRoleSelect.innerHTML = '<option value="">Select a career...</option>' +
        careerPaths.map(p => `<option value="${esc(p.role)}">${esc(p.role)} (${p.score}%)</option>`).join('');
      if (selectedCareer) gapRoleSelect.value = selectedCareer;
    }
    goToStep(steps.indexOf('gap'));
  });

  // ── STEP 3: Skill Gap ──────────────────────────────────────
  if (gapAnalyzeBtn) gapAnalyzeBtn.addEventListener('click', analyzeSkillGap);

  async function analyzeSkillGap() {
    const role = gapRoleSelect?.value;
    if (!role) {
      toast('Please select a target career.', 'warning');
      return;
    }
    if (!resumeText || resumeText.length < 20) {
      toast('Resume text required.', 'warning');
      return;
    }

    gapLoading?.classList.remove('hidden');
    gapResults?.classList.add('hidden');
    gapAnalyzeBtn.disabled = true;

    try {
      const res = await apiPost('/api/skills-gap/analyze', { resume_text: resumeText, target_role: role });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Analysis failed');

      gapData = data.analysis;
      renderGapResults(gapData);
      gapLoading?.classList.add('hidden');
      gapResults?.classList.remove('hidden');
      addActivity('Skill gap analyzed for ' + role);
    } catch (err) {
      gapLoading?.classList.add('hidden');
      toast(err.message || 'Gap analysis failed', 'error');
    } finally {
      gapAnalyzeBtn.disabled = false;
    }
  }

  function renderGapResults(data) {
    if (gapTarget) gapTarget.textContent = data.target_role;
    if (matchValue) matchValue.textContent = `${data.match_percentage || 0}%`;
    if (matchRing) matchRing.style.setProperty('--pct', `${data.match_percentage || 0}%`);

    if (matchedSkills) {
      matchedSkills.innerHTML = (data.matched_skills || []).map(s =>
        `<div class="career-gap-item career-gap-item--matched">✓ ${esc(s)}</div>`
      ).join('') || '<div class="career-gap-item">No matched skills</div>';
    }

    if (missingSkills) {
      missingSkills.innerHTML = (data.missing_skills || []).map(s => {
        const isHigh = (data.high_priority || []).includes(s);
        const isMed = (data.medium_priority || []).includes(s);
        const priority = isHigh ? 'HIGH' : isMed ? 'MEDIUM' : 'LOW';
        const dot = isHigh ? '🔴' : isMed ? '🟡' : '🟢';
        return `<div class="career-gap-item career-gap-item--missing">${dot} ${esc(s)} <span style="margin-left:auto;font-size:0.72rem;opacity:0.7;">${priority}</span></div>`;
      }).join('') || '<div class="career-gap-item">No missing skills</div>';
    }

    if (highPriority) highPriority.textContent = (data.high_priority || []).join(', ') || 'None';
    if (mediumPriority) mediumPriority.textContent = (data.medium_priority || []).join(', ') || 'None';
    if (lowPriority) lowPriority.textContent = (data.low_priority || []).join(', ') || 'None';

    navItems[steps.indexOf('roadmap')].disabled = false;
    navItems[steps.indexOf('jobs')].disabled = false;
  }

  if (nextRoadmapBtn) nextRoadmapBtn.addEventListener('click', () => {
    generateRoadmap();
    goToStep(steps.indexOf('roadmap'));
  });

  // ── STEP 4: Learning Roadmap ───────────────────────────────
  async function generateRoadmap() {
    if (!resumeText || resumeText.length < 20) return;
    if (!gapData || !gapData.target_role) {
      toast('Please complete skill gap analysis first.', 'warning');
      return;
    }

    try {
      // Use the new personalized roadmap API
      const res = await apiPost('/api/personalized-roadmap', {
        resume_text: resumeText,
        target_role: gapData.target_role,
        user_skills: gapData.matched_skills || [],
        missing_skills: gapData.missing_skills || [],
        matched_skills: gapData.matched_skills || [],
        high_priority: gapData.high_priority || [],
        medium_priority: gapData.medium_priority || [],
        low_priority: gapData.low_priority || [],
        weekly_hours: 8,
      });
      const data = await res.json();
      if (data.success && data.roadmap) {
        personalizedRoadmap = data.roadmap;
        roadmapData = data.roadmap.phases || [];
        renderRoadmap();
        renderRoadmapHeader();
        addActivity('Personalized learning roadmap generated — ' + roadmapData.length + ' phases');
        navItems[steps.indexOf('advisor')].disabled = false;
      } else {
        toast(data.error || 'Could not generate roadmap', 'error');
      }
    } catch (err) {
      toast('Could not load personalized roadmap', 'error');
    }
  }

  // ── Reskilling Roadmap ───────────────────────────────────
  async function generateReskillingRoadmap(currentCareer, riskLabel, recommendedTransition) {
    if (!resumeText || resumeText.length < 20) return;

    try {
      const res = await apiPost('/api/reskilling-roadmap', {
        resume_text: resumeText,
        current_career: currentCareer,
        automation_risk: riskLabel,
        recommended_transition: recommendedTransition,
        weekly_hours: 8,
      });
      const data = await res.json();
      if (data.success && data.roadmap) {
        personalizedRoadmap = data.roadmap;
        roadmapData = data.roadmap.phases || [];
        renderRoadmap();
        renderRoadmapHeader();
        addActivity('Reskilling roadmap generated for ' + recommendedTransition);
      } else {
        toast(data.error || 'Could not generate reskilling roadmap', 'error');
      }
    } catch (err) {
      toast('Could not load reskilling roadmap', 'error');
    }
  }

  // ── Roadmap Progress Persistence ─────────────────────────
  const PROGRESS_STORAGE_KEY = 'prayash-roadmap-progress';

  function loadRoadmapProgress() {
    try {
      const saved = JSON.parse(localStorage.getItem(PROGRESS_STORAGE_KEY) || '{}');
      roadmapCompletion = saved;
    } catch { roadmapCompletion = {}; }
  }

  function saveRoadmapProgress() {
    try { localStorage.setItem(PROGRESS_STORAGE_KEY, JSON.stringify(roadmapCompletion)); } catch {}
  }

  function getProgressKey(phaseIdx, itemIdx) {
    return `${gapData?.target_role || 'default'}::${phaseIdx}::${itemIdx}`;
  }

  function isItemComplete(phaseIdx, itemIdx) {
    return !!roadmapCompletion[getProgressKey(phaseIdx, itemIdx)];
  }

  function toggleItemComplete(phaseIdx, itemIdx) {
    const key = getProgressKey(phaseIdx, itemIdx);
    if (roadmapCompletion[key]) {
      delete roadmapCompletion[key];
    } else {
      roadmapCompletion[key] = true;
    }
    saveRoadmapProgress();
    updateRoadmapProgressBar();
    updateDashboard();
  }

  function getRoadmapCompletionStats() {
    let totalItems = 0;
    let completedItems = 0;
    const mapping = getPhaseMapping();
    mapping.forEach((phase, pIdx) => {
      (phase.stages || []).forEach((s, sIdx) => {
        totalItems++;
        const pI = s._phaseIdx != null ? s._phaseIdx : pIdx;
        const sI = s._skillIdx != null ? s._skillIdx : sIdx;
        if (isItemComplete(pI, sI)) completedItems++;
      });
    });
    return { total: totalItems, completed: completedItems, pct: totalItems ? Math.round((completedItems / totalItems) * 100) : 0 };
  }

  function updateRoadmapProgressBar() {
    const stats = getRoadmapCompletionStats();
    if (roadmapProgress) roadmapProgress.style.width = `${stats.pct}%`;
  }

  function resetRoadmapProgress() {
    roadmapCompletion = {};
    saveRoadmapProgress();
    renderRoadmap();
    updateDashboard();
    toast('Roadmap progress reset.', 'info');
  }

  // Load saved progress on init
  loadRoadmapProgress();

  // ── Step-by-Step Roadmap ─────────────────────────────────
  const RM_PHASE_NAMES = ['Beginner', 'Intermediate', 'Advanced', 'Projects', 'Job Ready'];
  const RM_PHASE_ICONS = ['📚', '🔧', '🚀', '💼', '🎯'];
  const RM_PHASE_DESCS = [
    'Build your foundation with core concepts',
    'Expand your skills with intermediate topics',
    'Master advanced techniques and patterns',
    'Apply your knowledge in real projects',
    'Prepare for the job market'
  ];
  let rmCurrentPhase = 0;

  function getPhaseMapping() {
    // If we have personalized roadmap data, use its phases directly
    if (personalizedRoadmap && personalizedRoadmap.phases && personalizedRoadmap.phases.length) {
      return personalizedRoadmap.phases.map((phase, idx) => ({
        name: phase.name || RM_PHASE_NAMES[idx],
        icon: phase.icon || RM_PHASE_ICONS[idx],
        desc: phase.description || RM_PHASE_DESCS[idx],
        stages: (phase.skills || []).map((skill, sIdx) => ({
          ...skill,
          _phaseIdx: idx,
          _skillIdx: sIdx,
        })),
      }));
    }
    // Fallback: Map roadmapData areas to 5 structured phases (legacy)
    const mapping = [];
    const totalAreas = roadmapData.length;
    const areasPerPhase = Math.max(1, Math.ceil(totalAreas / 5));

    for (let phaseIdx = 0; phaseIdx < 5; phaseIdx++) {
      const startIdx = phaseIdx * areasPerPhase;
      const endIdx = Math.min(startIdx + areasPerPhase, totalAreas);
      const areas = roadmapData.slice(startIdx, endIdx);
      const stages = [];
      areas.forEach((area, aIdx) => {
        (area.stages || []).forEach((s, sIdx) => {
          stages.push({
            ...s,
            _areaIdx: startIdx + aIdx,
            _stageIdx: sIdx,
          });
        });
      });
      mapping.push({
        name: RM_PHASE_NAMES[phaseIdx],
        icon: RM_PHASE_ICONS[phaseIdx],
        desc: RM_PHASE_DESCS[phaseIdx],
        stages: stages,
      });
    }
    return mapping;
  }

  function _stageIds(s) {
    // Support both new (_phaseIdx/_skillIdx) and legacy (_areaIdx/_stageIdx) formats
    return {
      p: s._phaseIdx != null ? s._phaseIdx : (s._areaIdx != null ? s._areaIdx : 0),
      i: s._skillIdx != null ? s._skillIdx : (s._stageIdx != null ? s._stageIdx : 0),
    };
  }

  function isPhaseUnlocked(phaseIdx) {
    if (phaseIdx === 0) return true;
    const mapping = getPhaseMapping();
    const prevPhase = mapping[phaseIdx - 1];
    if (!prevPhase || prevPhase.stages.length === 0) return true;
    return prevPhase.stages.every(s => { const ids = _stageIds(s); return isItemComplete(ids.p, ids.i); });
  }

  function isPhaseComplete(phaseIdx) {
    const mapping = getPhaseMapping();
    const phase = mapping[phaseIdx];
    if (!phase || phase.stages.length === 0) return false;
    return phase.stages.every(s => { const ids = _stageIds(s); return isItemComplete(ids.p, ids.i); });
  }

  function getPhaseProgress(phaseIdx) {
    const mapping = getPhaseMapping();
    const phase = mapping[phaseIdx];
    if (!phase || phase.stages.length === 0) return { done: 0, total: 0, pct: 0 };
    const done = phase.stages.filter(s => { const ids = _stageIds(s); return isItemComplete(ids.p, ids.i); }).length;
    return { done, total: phase.stages.length, pct: Math.round((done / phase.stages.length) * 100) };
  }

  function findCurrentPhase() {
    for (let i = 0; i < 5; i++) {
      if (!isPhaseComplete(i)) return i;
    }
    return 5; // all complete
  }

  function renderRoadmap() {
    if (!roadmapPhases && !document.querySelector('[data-rm-phase-container]')) return;

    const mapping = getPhaseMapping();
    rmCurrentPhase = findCurrentPhase();

    // Update step indicators
    document.querySelectorAll('[data-rm-step]').forEach((el, idx) => {
      el.classList.toggle('is-active', idx === rmCurrentPhase);
      el.classList.toggle('is-completed', isPhaseComplete(idx));
      el.classList.toggle('is-locked', !isPhaseUnlocked(idx));
      const dot = el.querySelector('.rm-step-indicator__dot');
      if (dot) {
        dot.textContent = isPhaseComplete(idx) ? '✓' : (idx + 1);
      }
    });

    // Update progress fill
    const progressFill = document.querySelector('[data-rm-progress-fill]');
    if (progressFill) {
      const overallStats = getRoadmapCompletionStats();
      progressFill.style.width = `${overallStats.pct}%`;
    }

    // Show/hide sections
    const phaseContent = document.querySelector('[data-rm-phase-content]');
    const phaseLoading = document.querySelector('[data-rm-loading]');
    const completeSection = document.querySelector('[data-rm-complete]');

    if (rmCurrentPhase >= 5) {
      if (phaseContent) phaseContent.classList.add('hidden');
      if (phaseLoading) phaseLoading.classList.add('hidden');
      if (completeSection) completeSection.classList.remove('hidden');
      return;
    }

    if (completeSection) completeSection.classList.add('hidden');
    if (phaseLoading) phaseLoading.classList.add('hidden');
    if (phaseContent) phaseContent.classList.remove('hidden');

    const phase = mapping[rmCurrentPhase];
    const progress = getPhaseProgress(rmCurrentPhase);

    // Update phase header
    const phaseIcon = document.querySelector('[data-rm-phase-icon]');
    const phaseTitle = document.querySelector('[data-rm-phase-title]');
    const phaseDesc = document.querySelector('[data-rm-phase-desc]');
    const phaseCount = document.querySelector('[data-rm-phase-count]');
    const phaseDuration = document.querySelector('[data-rm-phase-duration]');

    if (phaseIcon) phaseIcon.textContent = phase.icon;
    if (phaseTitle) phaseTitle.textContent = `Phase ${rmCurrentPhase + 1}: ${phase.name}`;
    if (phaseDesc) phaseDesc.textContent = phase.desc;
    if (phaseCount) phaseCount.textContent = `${progress.done}/${progress.total}`;
    if (phaseDuration) {
      const totalHours = phase.stages.reduce((acc, s) => acc + (s.estimated_hours || 0), 0);
      const weeks = Math.ceil(totalHours / 8);
      phaseDuration.textContent = `~${weeks} weeks`;
    }

    // Render phase items
    const itemsContainer = document.querySelector('[data-rm-phase-items]');
    if (itemsContainer) {
      itemsContainer.innerHTML = phase.stages.map((s, sIdx) => {
        const pIdx = s._phaseIdx != null ? s._phaseIdx : rmCurrentPhase;
        const iIdx = s._skillIdx != null ? s._skillIdx : sIdx;
        const done = isItemComplete(pIdx, iIdx);
        const priority = s.priority || 'MEDIUM';
        const priorityClass = priority === 'HIGH' ? 'rm-priority--high' : priority === 'MEDIUM' ? 'rm-priority--medium' : 'rm-priority--low';
        const resourceCount = (s.resources || []).length;
        const topicCount = (s.topics || []).length;
        const progressPct = s.progress || 0;
        const skillType = s.type || 'skill';

        return `
          <div class="rm-item ${done ? 'rm-item--done' : ''}" data-rm-item-click="${pIdx}-${iIdx}">
            <label class="rm-item__check" onclick="event.stopPropagation()">
              <input type="checkbox" data-rm-item-toggle="${pIdx}-${iIdx}" ${done ? 'checked' : ''}>
              <span class="rm-item__checkmark"></span>
            </label>
            <div class="rm-item__content">
              <div class="rm-item__text">
                <div class="rm-item__top-row">
                  <strong>${esc(s.name || s.skill || s.level || '')}</strong>
                  <span class="rm-item__priority ${priorityClass}">${priority}</span>
                </div>
                <p class="rm-item__desc">${esc(s.description || '').substring(0, 120)}${(s.description || '').length > 120 ? '...' : ''}</p>
                <div class="rm-item__meta-row">
                  ${s.difficulty ? `<span class="rm-item__badge rm-item__badge--diff">${esc(s.difficulty)}</span>` : ''}
                  ${s.estimated_time ? `<span class="rm-item__badge rm-item__badge--time">⏱️ ${esc(s.estimated_time)}</span>` : ''}
                  ${topicCount > 0 ? `<span class="rm-item__badge rm-item__badge--topics">📝 ${topicCount} topics</span>` : ''}
                  ${resourceCount > 0 ? `<span class="rm-item__badge rm-item__badge--resources">📚 ${resourceCount} resources</span>` : ''}
                </div>
                ${progressPct > 0 ? `<div class="rm-item__progress"><div class="rm-item__progress-bar"><div class="rm-item__progress-fill" style="width:${progressPct}%"></div></div><span class="rm-item__progress-pct">${progressPct}%</span></div>` : ''}
              </div>
              <div class="rm-item__actions">
                <button type="button" class="rm-item__view-btn" data-rm-view-detail="${pIdx}-${iIdx}" onclick="event.stopPropagation()">View Details →</button>
              </div>
            </div>
          </div>`;
      }).join('');

      // Bind checkboxes
      itemsContainer.querySelectorAll('[data-rm-item-toggle]').forEach(cb => {
        cb.addEventListener('change', () => {
          const [pIdx, iIdx] = cb.dataset.rmItemToggle.split('-').map(Number);
          toggleItemComplete(pIdx, iIdx);
          renderRoadmap();
        });
      });

      // Bind item click for detail panel
      itemsContainer.querySelectorAll('[data-rm-item-click]').forEach(el => {
        el.addEventListener('click', () => {
          const [pIdx, iIdx] = el.dataset.rmItemClick.split('-').map(Number);
          showSkillDetail(pIdx, iIdx);
        });
      });

      // Bind view detail buttons
      itemsContainer.querySelectorAll('[data-rm-view-detail]').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const [pIdx, iIdx] = btn.dataset.rmViewDetail.split('-').map(Number);
          showSkillDetail(pIdx, iIdx);
        });
      });
    }

    // Update navigation buttons
    const prevBtn = document.querySelector('[data-rm-prev-phase]');
    const nextBtn = document.querySelector('[data-rm-next-phase]');
    const hint = document.querySelector('[data-rm-phase-hint]');

    if (prevBtn) prevBtn.disabled = rmCurrentPhase === 0;
    if (nextBtn) {
      const phaseDone = isPhaseComplete(rmCurrentPhase);
      nextBtn.disabled = !phaseDone;
      nextBtn.textContent = rmCurrentPhase === 4 ? 'Complete Roadmap ✓' : 'Next Phase →';
    }
    if (hint) {
      const phaseDone = isPhaseComplete(rmCurrentPhase);
      hint.textContent = phaseDone
        ? 'Phase complete! Click Next Phase to continue.'
        : `Complete all ${progress.total} items to unlock the next phase`;
      hint.style.color = phaseDone ? 'var(--success)' : '';
    }

    // Update summary
    if (roadmapSummary) {
      const stats = getRoadmapCompletionStats();
      const completedPhases = [0,1,2,3,4].filter(i => isPhaseComplete(i)).length;
      if (stats.total > 0 && stats.completed > 0) {
        roadmapSummary.textContent = `${completedPhases}/5 phases completed. ${stats.completed}/${stats.total} items done (${stats.pct}%). ${stats.pct === 100 ? '🎉 Congratulations! You\'ve finished your entire roadmap!' : 'Keep going — you\'re making great progress!'}`;
      } else {
        roadmapSummary.textContent = `Your personalized learning roadmap has 5 phases. Start with Phase 1 (Foundation) and complete each phase to unlock the next. You'll become job-ready in ${stats.total} steps!`;
      }
    }
  }

  // ── Render Roadmap Header Stats ─────────────────────────
  function renderRoadmapHeader() {
    if (!personalizedRoadmap) return;

    const tcEl = document.querySelector('[data-rm-target-career]');
    const opEl = document.querySelector('[data-rm-overall-progress]');
    const durEl = document.querySelector('[data-rm-duration]');
    const whEl = document.querySelector('[data-rm-weekly-hours]');
    const cmEl = document.querySelector('[data-rm-current-match]');
    const pmEl = document.querySelector('[data-rm-potential-match]');
    const cpEl = document.querySelector('[data-rm-coverage-pct]');
    const cfEl = document.querySelector('[data-rm-coverage-fill]');

    const stats = getRoadmapCompletionStats();
    if (tcEl) tcEl.textContent = personalizedRoadmap.target_role || gapData?.target_role || '—';
    if (opEl) opEl.textContent = `${stats.pct}%`;
    if (durEl) durEl.textContent = personalizedRoadmap.estimated_duration || '—';
    if (whEl) whEl.textContent = `${personalizedRoadmap.weekly_hours || 8} hrs/week`;
    if (cmEl) cmEl.textContent = `${personalizedRoadmap.current_skill_match || 0}%`;
    if (pmEl) pmEl.textContent = `${personalizedRoadmap.potential_skill_coverage || 0}%`;
    if (cpEl) cpEl.textContent = `${personalizedRoadmap.potential_skill_coverage || 0}%`;
    if (cfEl) cfEl.style.width = `${personalizedRoadmap.potential_skill_coverage || 0}%`;

    // Show reskilling banner if applicable
    const banner = document.querySelector('[data-rm-reskilling-banner]');
    if (banner && personalizedRoadmap.reskilling) {
      const r = personalizedRoadmap.reskilling;
      banner.classList.remove('hidden');
      const titleEl = banner.querySelector('[data-rm-reskilling-title]');
      const descEl = banner.querySelector('[data-rm-reskilling-desc]');
      if (titleEl) titleEl.textContent = `Career Transition: ${r.current_career} → ${r.recommended_transition}`;
      if (descEl) descEl.textContent = r.reason || '';
    }
  }

  // ── Skill Detail Panel ─────────────────────────────────
  function showSkillDetail(phaseIdx, skillIdx) {
    const mapping = getPhaseMapping();
    const phase = mapping[phaseIdx];
    if (!phase || !phase.stages[skillIdx]) return;
    const skill = phase.stages[skillIdx];

    const panel = document.querySelector('[data-rm-detail-panel]');
    if (!panel) return;
    panel.classList.remove('hidden');

    // Populate detail panel
    const title = panel.querySelector('[data-rm-detail-title]');
    const difficulty = panel.querySelector('[data-rm-detail-difficulty]');
    const time = panel.querySelector('[data-rm-detail-time]');
    const priority = panel.querySelector('[data-rm-detail-priority]');
    const why = panel.querySelector('[data-rm-detail-why]');
    const prereqsSection = panel.querySelector('[data-rm-detail-prereqs-section]');
    const prereqs = panel.querySelector('[data-rm-detail-prereqs]');
    const topics = panel.querySelector('[data-rm-detail-topics]');
    const resources = panel.querySelector('[data-rm-detail-resources]');
    const practice = panel.querySelector('[data-rm-detail-practice]');
    const projects = panel.querySelector('[data-rm-detail-projects]');
    const assessment = panel.querySelector('[data-rm-detail-assessment]');

    if (title) title.textContent = skill.name || skill.skill || '';
    if (difficulty) difficulty.textContent = skill.difficulty || 'Intermediate';
    if (time) time.textContent = `⏱️ ${skill.estimated_time || '2-3 weeks'}`;
    if (priority) {
      const p = skill.priority || 'MEDIUM';
      priority.textContent = p;
      priority.className = `rm-detail-badge rm-detail-badge--priority rm-priority--${p.toLowerCase()}`;
    }
    if (why) why.textContent = skill.why_needed || skill.description || '';

    // Prerequisites
    if (prereqsSection && prereqs) {
      const prereqList = skill.prerequisites || [];
      if (prereqList.length > 0) {
        prereqsSection.classList.remove('hidden');
        prereqs.innerHTML = prereqList.map(p => {
          const hasSkill = (gapData?.matched_skills || []).some(ms => ms.toLowerCase() === p.toLowerCase());
          return `<span class="rm-detail-prereq ${hasSkill ? 'rm-detail-prereq--has' : ''}">${hasSkill ? '✓' : '○'} ${esc(p)}</span>`;
        }).join('');
      } else {
        prereqsSection.classList.add('hidden');
      }
    }

    // Topics
    if (topics) {
      const topicList = skill.topics || [];
      topics.innerHTML = topicList.map(t => `<div class="rm-detail-topic"><span class="rm-detail-topic__check">□</span><span>${esc(t)}</span></div>`).join('');
    }

    // Resources
    if (resources) {
      const resList = skill.resources || [];
      if (resList.length > 0) {
        resources.innerHTML = resList.map(r => {
          const rating = r.rating || 3;
          const stars = '★'.repeat(rating) + '☆'.repeat(5 - rating);
          return `
            <div class="rm-detail-resource">
              <div class="rm-detail-resource__header">
                <span class="rm-detail-resource__stars">${stars}</span>
                <span class="rm-detail-resource__title">${esc(r.title || '')}</span>
              </div>
              <div class="rm-detail-resource__meta">
                <span>${esc(r.type || 'Resource')}</span>
                <span>•</span>
                <span>${esc(r.level || 'Beginner')}</span>
                <span>•</span>
                <span>${esc(r.provider || '')}</span>
                ${r.free ? '<span class="rm-detail-resource__free">Free</span>' : ''}
              </div>
              ${r.url ? `<a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer" class="rm-detail-resource__link">Open Resource ↗</a>` : ''}
            </div>`;
        }).join('');
      } else {
        resources.innerHTML = '<p class="rm-detail-empty">No specific resources available. Search for learning materials on this topic.</p>';
      }
    }

    // Practice
    if (practice) {
      const practiceList = skill.practice || [];
      practice.innerHTML = practiceList.map(p => `<div class="rm-detail-practice-item"><span>✓</span><span>${esc(p)}</span></div>`).join('');
    }

    // Projects
    if (projects) {
      const projectList = skill.projects || [];
      projects.innerHTML = projectList.map(p => `<div class="rm-detail-project-item"><span>🚀</span><span>${esc(p)}</span></div>`).join('');
    }

    // Assessment
    if (assessment) {
      const assessList = skill.assessment || [];
      assessment.innerHTML = assessList.map(a => `<div class="rm-detail-assess-item"><span>□</span><span>${esc(a)}</span></div>`).join('');
    }

    // Bind complete button
    const completeBtn = panel.querySelector('[data-rm-detail-complete]');
    if (completeBtn) {
      completeBtn.onclick = () => {
        toggleItemComplete(phaseIdx, skillIdx);
        panel.classList.add('hidden');
        renderRoadmap();
      };
    }

    // Bind close buttons
    const closeBtn = panel.querySelector('[data-rm-detail-close-btn]');
    const closeAction = panel.querySelector('[data-rm-detail-close-action]');
    const overlay = panel.querySelector('[data-rm-detail-close]');
    const closeHandler = () => panel.classList.add('hidden');
    if (closeBtn) closeBtn.addEventListener('click', closeHandler);
    if (closeAction) closeAction.addEventListener('click', closeHandler);
    if (overlay) overlay.addEventListener('click', closeHandler);
  }

  // Bind phase navigation
  document.querySelectorAll('[data-rm-prev-phase]').forEach(btn => {
    btn.addEventListener('click', () => {
      if (rmCurrentPhase > 0) {
        rmCurrentPhase--;
        renderRoadmap();
      }
    });
  });

  document.querySelectorAll('[data-rm-next-phase]').forEach(btn => {
    btn.addEventListener('click', () => {
      if (rmCurrentPhase < 5 && isPhaseComplete(rmCurrentPhase)) {
        rmCurrentPhase++;
        renderRoadmap();
        // Scroll to top of roadmap
        const container = document.querySelector('[data-rm-phase-container]');
        if (container) container.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // Bind step indicator clicks
  document.querySelectorAll('[data-rm-step]').forEach((el, idx) => {
    el.addEventListener('click', () => {
      if (isPhaseUnlocked(idx)) {
        rmCurrentPhase = idx;
        renderRoadmap();
      }
    });
  });

  // Bind view jobs button
  document.querySelectorAll('[data-rm-view-jobs]').forEach(btn => {
    btn.addEventListener('click', () => {
      goToStep(steps.indexOf('jobs'));
    });
  });

  // ── Roadmap Export ────────────────────────────────────────
  $$('[data-export-roadmap]').forEach(btn => {
    btn.addEventListener('click', () => {
      const format = btn.dataset.exportRoadmap;
      exportRoadmap(format);
    });
  });

  function exportRoadmap(format) {
    if (!roadmapData.length) {
      toast('No roadmap to export yet. Generate a roadmap first.', 'warning');
      return;
    }

    const targetRole = personalizedRoadmap?.target_role || gapData?.target_role || 'your target role';
    const skillCount = skillsData?.count || 0;
    const matchPct = personalizedRoadmap?.current_skill_match || gapData?.match_percentage || 0;
    const duration = personalizedRoadmap?.estimated_duration || '';
    const now = new Date();
    const dateStr = now.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

    // Helper to extract skill info from new or legacy format
    function getSkillName(s) { return s.name || s.skill || s.level || ''; }
    function getSkillDesc(s) { return s.description || ''; }
    function getSkillDuration(s) { return s.estimated_time || s.duration || ''; }
    function getSkillDiff(s) { return s.difficulty || s.level || ''; }
    function getSkillResources(s) { return s.resources || []; }
    function getPhaseName(p) { return p.name || p.area || ''; }
    function getPhaseSkills(p) { return p.skills || p.stages || []; }

    if (format === 'txt') {
      const lines = [
        'My Personalized Learning Roadmap',
        '='.repeat(40),
        '',
        `Generated: ${dateStr}`,
        `Target Role: ${targetRole}`,
        `Skills Detected: ${skillCount}`,
        `Match: ${matchPct}%`,
        duration ? `Estimated Duration: ${duration}` : '',
        '',
        '-'.repeat(40),
        '',
      ];
      roadmapData.forEach((phase, idx) => {
        const skills = getPhaseSkills(phase);
        const totalHours = skills.reduce((acc, s) => acc + (s.estimated_hours || 0), 0);
        const weeks = Math.ceil(totalHours / 8);
        lines.push(`Phase ${idx + 1}: ${getPhaseName(phase)} (~${weeks} weeks)`);
        lines.push('-'.repeat(30));
        skills.forEach(s => {
          const name = getSkillName(s);
          const desc = getSkillDesc(s);
          const time = getSkillDuration(s);
          const diff = getSkillDiff(s);
          const priority = s.priority || '';
          const resources = getSkillResources(s);
          lines.push(`  [${diff}] ${name} (${priority})`);
          if (desc) lines.push(`    ${desc}`);
          if (time) lines.push(`    Duration: ${time}`);
          if (s.topics && s.topics.length) {
            lines.push(`    Topics: ${s.topics.join(', ')}`);
          }
          if (resources.length) {
            lines.push('    Resources:');
            resources.forEach(r => {
              const stars = '★'.repeat(r.rating || 3) + '☆'.repeat(5 - (r.rating || 3));
              lines.push(`      ${stars} ${r.title || ''} (${r.provider || ''})`);
              if (r.url) lines.push(`        ${r.url}`);
            });
          }
          lines.push('');
        });
        lines.push('');
      });
      lines.push('-'.repeat(40));
      lines.push('Exported from Prayash CareerAI');
      downloadFile(lines.join('\n'), `learning-roadmap-${sanitizeFilename(targetRole)}.txt`, 'text/plain');
      toast('Roadmap exported as TXT!', 'success');
    }

    if (format === 'md') {
      const lines = [
        '# My Personalized Learning Roadmap',
        '',
        `**Generated:** ${dateStr}  `,
        `**Target Role:** ${targetRole}  `,
        `**Skills Detected:** ${skillCount}  `,
        `**Match:** ${matchPct}%`,
        duration ? `**Estimated Duration:** ${duration}  ` : '',
        '',
        '---',
        '',
      ];
      roadmapData.forEach((phase, idx) => {
        const skills = getPhaseSkills(phase);
        const totalHours = skills.reduce((acc, s) => acc + (s.estimated_hours || 0), 0);
        const weeks = Math.ceil(totalHours / 8);
        lines.push(`## Phase ${idx + 1}: ${getPhaseName(phase)}`);
        lines.push(`*~${weeks} weeks*`);
        lines.push('');
        skills.forEach(s => {
          const name = getSkillName(s);
          const desc = getSkillDesc(s);
          const time = getSkillDuration(s);
          const priority = s.priority || '';
          const resources = getSkillResources(s);
          lines.push(`### ${name} [${priority}]`);
          if (desc) lines.push(`${desc}`);
          if (time) lines.push(`*Duration: ${time}*`);
          if (s.topics && s.topics.length) {
            lines.push('');
            lines.push('**Topics:**');
            s.topics.forEach(t => lines.push(`- [ ] ${t}`));
          }
          if (resources.length) {
            lines.push('');
            lines.push('**Resources:**');
            resources.forEach(r => {
              const stars = '★'.repeat(r.rating || 3);
              lines.push(`- ${stars} [${r.title || ''}](${r.url || '#'}) — ${r.provider || ''}`);
            });
          }
          lines.push('');
        });
      });
      lines.push('---');
      lines.push('*Exported from Prayash CareerAI*');
      downloadFile(lines.join('\n'), `learning-roadmap-${sanitizeFilename(targetRole)}.md`, 'text/markdown');
      toast('Roadmap exported as Markdown!', 'success');
    }

    if (format === 'json') {
      const exportData = {
        generated: now.toISOString(),
        target_role: targetRole,
        skills_detected: skillCount,
        match_percentage: matchPct,
        estimated_duration: duration,
        weekly_hours: personalizedRoadmap?.weekly_hours || 8,
        roadmap: roadmapData,
        personalized_roadmap: personalizedRoadmap,
        summary: roadmapSummary?.textContent || '',
        exported_from: 'Prayash CareerAI',
      };
      downloadFile(JSON.stringify(exportData, null, 2), `learning-roadmap-${sanitizeFilename(targetRole)}.json`, 'application/json');
      toast('Roadmap exported as JSON!', 'success');
    }

    if (format === 'print') {
      const printContent = buildPrintHTML(targetRole, skillCount, matchPct, dateStr, duration);
      const printWindow = window.open('', '_blank');
      if (printWindow) {
        printWindow.document.write(printContent);
        printWindow.document.close();
        setTimeout(() => { printWindow.print(); }, 500);
        toast('Print dialog opened!', 'success');
      } else {
        toast('Pop-up blocked. Please allow pop-ups for this site.', 'warning');
      }
    }
  }

  function buildPrintHTML(targetRole, skillCount, matchPct, dateStr, duration) {
    let phases = '';
    roadmapData.forEach((phase, idx) => {
      const skills = phase.skills || phase.stages || [];
      const totalHours = skills.reduce((acc, s) => acc + (s.estimated_hours || 0), 0);
      const weeks = Math.ceil(totalHours / 8);
      const phaseName = phase.name || phase.area || '';
      phases += `
        <div style="margin-bottom:1.5rem;page-break-inside:avoid;">
          <h2 style="color:#4c1d95;font-size:1.1rem;margin:0 0 0.5rem;">Phase ${idx + 1}: ${esc(phaseName)} <span style="font-weight:400;color:#666;font-size:0.85rem;">(~${weeks} weeks)</span></h2>
          <ul style="margin:0;padding-left:1.5rem;">
            ${skills.map(s => {
              const name = s.name || s.skill || s.level || '';
              const desc = s.description || '';
              const time = s.estimated_time || s.duration || '';
              const diff = s.difficulty || '';
              const priority = s.priority || '';
              const resources = s.resources || [];
              const resourceLinks = resources.length ? resources.map(r => `${r.title || ''} (${r.url || ''})`).join(', ') : '';
              return `<li style="margin-bottom:0.5rem;"><strong>${esc(name)}</strong> <span style="color:#888;font-size:0.8rem;">[${esc(diff)}] [${esc(priority)}]</span><br><span style="color:#555;">${esc(desc).substring(0, 150)}${desc.length > 150 ? '...' : ''}</span><br><em style="color:#666;">⏱️ ${esc(time)}</em>${resourceLinks ? `<br><small style="color:#888;">📚 ${resourceLinks}</small>` : ''}</li>`;
            }).join('')}
          </ul>
        </div>`;
    });

    return `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Learning Roadmap - ${esc(targetRole)}</title>
        <style>
          body { font-family: Inter, -apple-system, sans-serif; max-width: 700px; margin: 2rem auto; color: #1a1a1a; line-height: 1.6; }
          h1 { color: #4c1d95; border-bottom: 2px solid #4c1d95; padding-bottom: 0.5rem; }
          .meta { color: #666; font-size: 0.9rem; margin-bottom: 1.5rem; }
          .meta span { display: inline-block; margin-right: 1.5rem; }
          @media print { body { margin: 0; } }
        </style>
      </head>
      <body>
        <h1>🗺️ My Personalized Learning Roadmap</h1>
        <div class="meta">
          <span>📅 ${dateStr}</span>
          <span>🎯 ${esc(targetRole)}</span>
          <span>🧠 ${skillCount} skills</span>
          <span>📊 ${matchPct}% match</span>
          ${duration ? `<span>⏱️ ${esc(duration)}</span>` : ''}
        </div>
        ${phases}
        <hr style="margin-top:2rem;">
        <p style="color:#888;font-size:0.8rem;">Exported from Prayash CareerAI</p>
      </body>
      </html>`;
  }

  function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 100);
  }

  function sanitizeFilename(str) {
    return (str || 'career').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').substring(0, 40);
  }

  // ── Jobs Search ────────────────────────────────────────────
  if (jobsSearchBtn) jobsSearchBtn.addEventListener('click', () => searchJobs(jobsSearchInput?.value || ''));
  if (jobsSearchInput) {
    jobsSearchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') searchJobs(jobsSearchInput.value);
    });
  }

  // Filter buttons
  jobsFilters.forEach(btn => {
    btn.addEventListener('click', () => {
      jobsFilters.forEach(b => b.classList.remove('is-active'));
      btn.classList.add('is-active');
    });
  });

  function searchJobs(query) {
    const q = (query || '').trim();
    if (!q) {
      // Show career path-based jobs
      if (careerPaths.length && jobsList) {
        renderJobResults(careerPaths.slice(0, 6).map(p => ({
          title: p.role,
          company: 'Various companies',
          location: 'Remote / On-site',
          level: p.demand || 'Mid Level',
          tags: (p.skills_analysis || []).filter(s => s.status === 'matched').map(s => s.skill).slice(0, 3),
          match: p.score,
          url: `https://www.indeed.com/jobs?q=${encodeURIComponent(p.role)}`
        })));
        jobsEmpty?.classList.add('hidden');
        jobsList?.classList.remove('hidden');
        return;
      }
      jobsEmpty?.classList.remove('hidden');
      jobsList?.classList.add('hidden');
      return;
    }

    // Generate search results from the query
    const searchResults = generateSearchResults(q);
    renderJobResults(searchResults);
    jobsEmpty?.classList.add('hidden');
    jobsList?.classList.remove('hidden');
  }

  function generateSearchResults(query) {
    const titles = [
      `${query} Engineer`,
      `Senior ${query}`,
      `${query} Developer`,
      `${query} Analyst`,
      `Junior ${query}`,
    ];
    const companies = ['Tech Corp', 'InnovateLabs', 'DataFlow Inc', 'CloudNine', 'SmartSystems'];
    const locations = ['Remote', 'New York, NY', 'San Francisco, CA', 'Austin, TX', 'Seattle, WA'];
    const levels = ['Entry Level', 'Mid Level', 'Senior', 'Lead'];

    return titles.map((title, i) => ({
      title,
      company: companies[i % companies.length],
      location: locations[i % locations.length],
      level: levels[i % levels.length],
      tags: skillsData?.all_skills?.slice(0, 3) || [],
      match: Math.max(30, 95 - i * 12),
      url: `https://www.indeed.com/jobs?q=${encodeURIComponent(title)}`
    }));
  }

  function renderJobResults(jobs) {
    if (!jobsList) return;
    jobsList.innerHTML = jobs.map(j => `
      <a href="${j.url}" target="_blank" rel="noopener noreferrer" class="career-job-card" style="text-decoration:none;color:inherit;">
        <div class="career-job-card__info">
          <h4>${esc(j.title)}</h4>
          <div class="career-job-card__meta">${esc(j.company)} · ${esc(j.location)} · ${esc(j.level)}</div>
          <div class="career-job-card__tags">
            ${(j.tags || []).map(t => `<span class="career-job-tag">${esc(t)}</span>`).join('')}
          </div>
        </div>
        <div class="career-job-card__match">
          <div class="career-job-match-pct">${j.match}%</div>
          <div class="career-job-match-label">match</div>
        </div>
      </a>
    `).join('');
  }

  // ── AI Advisor ─────────────────────────────────────────────
  let advisorSessionId = '';

  if (advisorSend) {
    advisorSend.addEventListener('click', sendAdvisorMessage);
  }
  if (advisorInput) {
    advisorInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendAdvisorMessage();
      }
    });
  }
  if (advisorClear) {
    advisorClear.addEventListener('click', () => {
      if (advisorMessages) {
        advisorMessages.innerHTML = `
          <div class="career-advisor-msg career-advisor-msg--ai">
            <div class="career-advisor-msg__avatar">🤖</div>
            <div class="career-advisor-msg__content">
              <p>Chat cleared. Ask me anything about your career!</p>
            </div>
          </div>`;
      }
      advisorSessionId = '';
    });
  }

  // Quick suggestions
  advisorSuggestions.forEach(btn => {
    btn.addEventListener('click', () => {
      if (advisorInput) advisorInput.value = btn.dataset.advisorPrompt;
      sendAdvisorMessage();
    });
  });

  async function sendAdvisorMessage() {
    const question = (advisorInput?.value || '').trim();
    if (!question) return;

    // Add user message
    addAdvisorMessage(question, 'user');
    if (advisorInput) advisorInput.value = '';

    // Show typing indicator
    const typingEl = document.createElement('div');
    typingEl.className = 'career-advisor-msg career-advisor-msg--ai';
    typingEl.innerHTML = `<div class="career-advisor-msg__avatar">🤖</div><div class="career-advisor-typing"><span></span><span></span><span></span></div>`;
    advisorMessages?.appendChild(typingEl);
    advisorMessages.scrollTop = advisorMessages.scrollHeight;

    try {
      const res = await apiPost('/api/career-chat', {
        message: question,
        session_id: advisorSessionId,
        resume_text: resumeText || ''
      });
      const data = await res.json();

      // Remove typing indicator
      typingEl.remove();

      if (data.success) {
        advisorSessionId = data.session_id || '';
        addAdvisorMessage(data.reply || data.answer || 'No response.', 'ai');
      } else {
        addAdvisorMessage('Sorry, I could not process that. Please try again.', 'ai');
      }
    } catch (err) {
      typingEl.remove();
      addAdvisorMessage('Connection error. Please check your network and try again.', 'ai');
    }
  }

  function addAdvisorMessage(text, role) {
    const msgEl = document.createElement('div');
    msgEl.className = `career-advisor-msg career-advisor-msg--${role}`;
    const avatar = role === 'ai' ? '🤖' : '👤';
    msgEl.innerHTML = `<div class="career-advisor-msg__avatar">${avatar}</div><div class="career-advisor-msg__content"><p>${esc(text)}</p></div>`;
    advisorMessages?.appendChild(msgEl);
    advisorMessages.scrollTop = advisorMessages.scrollHeight;
  }

  // ── Settings ───────────────────────────────────────────────
  const themeQuickToggle = $('[data-theme-toggle-quick]');
  const themeModeLabel = $('[data-theme-mode-label]');
  const themeModeDesc = $('[data-theme-mode-desc]');

  const THEME_LABELS = { auto: 'Auto', light: 'Light', dark: 'Dark' };
  const THEME_DESCS = {
    auto: 'Follows your system preference',
    light: 'Always use light mode',
    dark: 'Always use dark mode',
  };

  function applyThemeMode(mode) {
    const html = document.documentElement;
    let resolved = 'light';
    if (mode === 'dark') resolved = 'dark';
    else if (mode === 'auto' && window.matchMedia?.('(prefers-color-scheme: dark)').matches) resolved = 'dark';
    html.setAttribute('data-theme', resolved);
    try { localStorage.setItem('prayash-theme-mode', mode); } catch {}
    // Update button states
    themePrefBtns.forEach(b => b.classList.toggle('is-active', b.dataset.themePref === mode));
    // Update label and description
    if (themeModeLabel) themeModeLabel.textContent = THEME_LABELS[mode] || 'Auto';
    if (themeModeDesc) themeModeDesc.textContent = THEME_DESCS[mode] || THEME_DESCS.auto;
  }

  themePrefBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      applyThemeMode(btn.dataset.themePref);
    });
  });

  // Quick toggle: switches between light and dark (or toggles auto)
  if (themeQuickToggle) {
    themeQuickToggle.addEventListener('click', () => {
      const current = (() => { try { return localStorage.getItem('prayash-theme-mode') || 'auto'; } catch { return 'auto'; } })();
      const html = document.documentElement;
      const isDark = html.getAttribute('data-theme') === 'dark';
      // Toggle: if dark → light, if light/auto → dark
      applyThemeMode(isDark ? 'light' : 'dark');
    });
  }

  // Set initial theme button state
  const savedTheme = (() => { try { return localStorage.getItem('prayash-theme-mode') || 'auto'; } catch { return 'auto'; } })();
  applyThemeMode(savedTheme);

  // Reset roadmap progress
  const resetProgressBtn = $('[data-settings-reset-progress]');
  if (resetProgressBtn) {
    resetProgressBtn.addEventListener('click', () => {
      if (confirm('Are you sure you want to reset all roadmap progress? This cannot be undone.')) {
        resetRoadmapProgress();
      }
    });
  }

  // Clear all local data
  const clearDataBtn = $('[data-settings-clear-data]');
  if (clearDataBtn) {
    clearDataBtn.addEventListener('click', () => {
      if (confirm('This will clear all saved preferences, progress, and activity from this browser. Continue?')) {
        try {
          localStorage.removeItem('prayash-roadmap-progress');
          localStorage.removeItem('prayash-theme-mode');
          localStorage.removeItem('prayash-analysis-mode');
          localStorage.removeItem('prayash-active-path');
          roadmapCompletion = {};
          toast('All local data cleared.', 'info');
        } catch {}
      }
    });
  }

  // ── Utilities ──────────────────────────────────────────────
  function esc(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str == null ? '' : String(str)));
    return div.innerHTML;
  }

  // ── Init ───────────────────────────────────────────────────
  goToStep(0);
  renderSkillsDeepDive();
  renderActivity();

  // Skill Extraction: render if data exists
  if (typeof SkillExtraction !== 'undefined' && skillsData) {
    SkillExtraction.render(skillsData);
  }

  // Skill Extraction: bind Go to Resume button
  const seGotoResume = document.querySelector('[data-se-goto-resume]');
  if (seGotoResume) {
    seGotoResume.addEventListener('click', () => {
      goToStep(steps.indexOf('resume'));
    });
  }

  // Skill Extraction: bind Re-analyze button
  const seReanalyze = document.querySelector('[data-se-reanalyze]');
  if (seReanalyze) {
    seReanalyze.addEventListener('click', () => {
      goToStep(steps.indexOf('resume'));
    });
  }
})();
