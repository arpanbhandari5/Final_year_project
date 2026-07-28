(() => {
  // ── Dark Mode Toggle (3-state: auto / light / dark) ──
  const themeToggle = document.querySelector("[data-theme-toggle]");
  const themeModeLabel = document.querySelector("[data-theme-mode-label]");
  const html = document.documentElement;
  const STORAGE_KEY = "prayash-theme-mode";

  const prefersDarkMedia = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  const isSystemDark = () => prefersDarkMedia ? prefersDarkMedia.matches : false;

  const MODE_CYCLE = ["auto", "light", "dark"];
  const MODE_ICONS = { auto: "🌓", light: "☀️", dark: "🌙" };
  const MODE_LABELS = { auto: "Auto", light: "Light", dark: "Dark" };

  let themeMode = localStorage.getItem(STORAGE_KEY) || "auto";
  if (!MODE_CYCLE.includes(themeMode)) themeMode = "auto";

  const applyTheme = (mode) => {
    if (mode === "auto") {
      applyResolvedTheme(isSystemDark() ? "dark" : "light");
    } else {
      applyResolvedTheme(mode);
    }
    updateToggleUI(mode);
  };

  const applyResolvedTheme = (resolved) => {
    html.setAttribute("data-theme", resolved);
  };

  const updateToggleUI = (mode) => {
    if (themeToggle) {
      themeToggle.setAttribute("aria-label", `Theme: ${MODE_LABELS[mode]}. Click to cycle.`);
      themeToggle.setAttribute("title", `${MODE_LABELS[mode]} mode` + (mode === "auto" ? " (follows OS setting)" : " (manual)") );
    }
    if (themeModeLabel) {
      themeModeLabel.textContent = MODE_LABELS[mode];
    }
    // Toggle icon visibility
    document.querySelectorAll(".theme-toggle-icon").forEach((icon) => {
      const iconMode = icon.getAttribute("data-icon");
      icon.style.display = iconMode === mode ? "inline" : "none";
    });
  };

  // Initialize on load (head script already set data-theme for FOUC prevention)
  applyTheme(themeMode);

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const currentIndex = MODE_CYCLE.indexOf(themeMode);
      themeMode = MODE_CYCLE[(currentIndex + 1) % MODE_CYCLE.length];
      localStorage.setItem(STORAGE_KEY, themeMode);
      applyTheme(themeMode);
    });
  }

  // Listen for system preference changes (only when in auto mode)
  if (prefersDarkMedia) {
    prefersDarkMedia.addEventListener("change", () => {
      if (themeMode === "auto") {
        applyResolvedTheme(isSystemDark() ? "dark" : "light");
      }
    });
  }

  // ── PWA: Register Service Worker ──
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker
        .register("/static/sw.js")
        .then((reg) => console.log("SW registered:", reg.scope))
        .catch((err) => console.warn("SW registration failed:", err));
    });
  }

  // ── PWA: Install Banner ──
  let deferredPrompt = null;
  const installBanner = document.querySelector("[data-pwa-install-banner]");
  const installButton = document.querySelector("[data-pwa-install-button]");
  const dismissButton = document.querySelector("[data-pwa-dismiss]");
  const bannerDismissed = localStorage.getItem("prayash-pwa-dismissed");

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (installBanner && !bannerDismissed) installBanner.classList.remove("hidden");
  });

  installButton?.addEventListener("click", () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(() => {
        deferredPrompt = null;
        if (installBanner) installBanner.classList.add("hidden");
      });
    }
  });

  dismissButton?.addEventListener("click", () => {
    if (installBanner) installBanner.classList.add("hidden");
    localStorage.setItem("prayash-pwa-dismissed", "1");
  });

  // ── Mobile Menu Toggle ──
  const mobileToggle = document.querySelector("[data-mobile-menu]");
  const navLinks = document.querySelector("[data-nav-links]");
  const navBackdrop = document.querySelector("[data-nav-backdrop]");
  const navbar = document.querySelector(".navbar");
  const closeMobileMenu = () => {
    if (navLinks) navLinks.classList.remove("is-open");
    if (mobileToggle) {
      mobileToggle.classList.remove("is-open");
      mobileToggle.setAttribute("aria-expanded", "false");
    }
    if (navBackdrop) navBackdrop.classList.remove("is-visible");
    if (navbar) navbar.classList.remove("menu-open");
  };
  if (mobileToggle && navLinks) {
    mobileToggle.addEventListener("click", () => {
      const isOpen = navLinks.classList.toggle("is-open");
      mobileToggle.classList.toggle("is-open");
      mobileToggle.setAttribute("aria-expanded", String(isOpen));
      if (navBackdrop) navBackdrop.classList.toggle("is-visible", isOpen);
      if (navbar) navbar.classList.toggle("menu-open", isOpen);
    });
    navBackdrop?.addEventListener("click", closeMobileMenu);
    navLinks.querySelectorAll(".nav-link").forEach((link) => {
      link.addEventListener("click", closeMobileMenu);
    });
  }

  // ── Original App Logic ──
  /** @typedef {{ job_role?: string, industry?: string, similarity?: number, risk_score?: number, skills?: string[], openings?: Array<{label?: string, url?: string}> }} JobPivot */
  /** @typedef {{ course?: string, skill?: string, reason?: string, url?: string }} RoadmapItem */
  /** @typedef {{ primary?: string, secondary?: string, tertiary?: string, scores?: Record<string, number|string> }} RiasecProfile */
  /** @typedef {{ learning_actions?: string[], job_search_actions?: string[], education_training_actions?: string[], support_resources?: string[] }} GuidedNextSteps */
  /** @typedef {{ success?: boolean, mode?: string, risk_score?: number, risk_label?: string, cognitive_career_narrative?: string, top_roles?: JobPivot[], roadmap?: RoadmapItem[], riasec?: RiasecProfile, skill_clusters?: Array<Record<string, unknown>>, guided_next_steps?: GuidedNextSteps, report_guide?: Record<string, string[]>, support_resources?: Array<Record<string, string>> }} AnalysisResult */

  const form = document.querySelector("[data-analysis-form]");
  const modeButtons = document.querySelectorAll("[data-mode]");
  const modeInput = document.querySelector("[data-mode-input]");
  const browseButton = document.querySelector("[data-browse-button]");
  const fileInput = document.querySelector("[data-file-input]");
  const dropZone = document.querySelector("[data-drop-zone]");
  const submitButton = document.querySelector("[data-assess-button]");
  const modal = document.querySelector("[data-result-modal]");
  const modalTitle = document.querySelector("[data-modal-title]");
  const modalRiskScore = document.querySelector("[data-modal-risk-score]");
  const modalRiskLabel = document.querySelector("[data-modal-risk-label]");
  const modalMode = document.querySelector("[data-modal-mode]");
  const modalCloseButtons = document.querySelectorAll("[data-modal-close]");
  const resultBanner = document.querySelector("[data-result-banner]");
  const resultStatus = document.querySelector("[data-result-status]");
  const narrative = document.querySelector("[data-narrative]");
  const rolesList = document.querySelector("[data-roles-list]");
  const roadmapList = document.querySelector("[data-roadmap-list]");
  const riasecList = document.querySelector("[data-riasec-list]");
  const riskScore = document.querySelector("[data-risk-score]");
  const riskLabel = document.querySelector("[data-risk-label]");
  const uploadStatus = document.querySelector("[data-upload-status]");
  const dashboardRiskRing = document.querySelector("[data-risk-ring]");
  const dashboardRiskScore = document.querySelector("[data-risk-score-display]");
  const dashboardRiskLabel = document.querySelector("[data-risk-label-display]");
  const dashboardRiskSummary = document.querySelector("[data-risk-summary]");
  const dashboardRoleStatus = document.querySelector("[data-role-status]");
  const dashboardRoleBars = document.querySelector("[data-role-bars]");
  const riskInsights = document.querySelector("[data-risk-insights]");
  const pathButtons = document.querySelectorAll("[data-path-option]");
  const pathTitle = document.querySelector("[data-path-title]");
  const pathDescription = document.querySelector("[data-path-description]");
  const pathActions = document.querySelector("[data-path-actions]");
  const heroTitle = document.querySelector("[data-hero-title]");
  const heroLead = document.querySelector("[data-hero-lead]");
  const heroActions = document.querySelector("[data-hero-actions]");
  const heroPrimaryLink = document.querySelector("[data-hero-primary-link]");
  const analysisIntro = document.querySelector("[data-analysis-intro]");
  const nextStepsStatus = document.querySelector("[data-next-steps-status]");
  const nextStepsLearning = document.querySelector("[data-next-learning]");
  const nextStepsJobs = document.querySelector("[data-next-jobs]");
  const nextStepsEducation = document.querySelector("[data-next-education]");
  const nextStepsSupport = document.querySelector("[data-next-support]");
  const modalNextSteps = document.querySelector("[data-modal-next-steps]");

  if (!form || !fileInput || !submitButton) {
    return;
  }

  let activeMode = modeInput?.value || "standard";
  let activePath = "student";
  let selectedFile = null;
  const originalSubmitLabel = submitButton.textContent.trim();
  let loadingSkeletonTimer = null;

  const PATHWAY_CONTENT = {
    student: {
      heroTitle: "Turn your student experience into a confident career launch plan.",
      heroLead: "Use your resume, projects, and coursework to identify roles, skill priorities, and practical next actions you can start this week.",
      analysisIntro: "Upload your student resume or paste a profile summary. You will get role fit, skill roadmap, and low-pressure next steps.",
      panelTitle: "Student path selected",
      panelDescription: "Start with standard mode for fast role alignment, then use advanced mode if you want richer narrative guidance.",
      actions: [
        "Run a standard analysis and review your top three role matches.",
        "Pick one roadmap course and schedule weekly learning blocks.",
        "Update one project bullet with stronger role keywords.",
      ],
      chips: ["Student-ready roles", "Project-to-job translation", "Interview preparation"],
      ctaLabel: "Start student assessment",
    },
    "job-seeker": {
      heroTitle: "Focus your job search with clearer role fit and stronger resume targeting.",
      heroLead: "Identify the roles where your profile already aligns, then prioritize skill and application actions that improve interview conversion.",
      analysisIntro: "Upload your current resume to get top role matches, automation risk, and a practical action sequence for applications.",
      panelTitle: "Job-seeker path selected",
      panelDescription: "Use role similarity and risk indicators to focus where your profile is strongest right now.",
      actions: [
        "Track recurring requirements across 10 recent job postings.",
        "Tailor your resume summary to your top matched role.",
        "Use one roadmap item to close a visible skill gap.",
      ],
      chips: ["Role match clarity", "Resume optimization", "Application focus"],
      ctaLabel: "Start job-search assessment",
    },
    "career-switcher": {
      heroTitle: "Plan your career transition with realistic steps and transferable skill mapping.",
      heroLead: "See where your current background overlaps with target roles, then build a practical bridge through focused learning and role targeting.",
      analysisIntro: "Upload your current resume to uncover transferable strengths, target-role alignment, and training priorities.",
      panelTitle: "Career-switcher path selected",
      panelDescription: "A transition works best when you combine targeted roles, visible proof projects, and short-cycle skill gains.",
      actions: [
        "Pick two transferable skills from your strongest role match.",
        "Build one portfolio proof item for your target direction.",
        "Commit to a 4 to 8 week transition learning plan.",
      ],
      chips: ["Transferable strengths", "Transition roadmap", "Targeted training"],
      ctaLabel: "Start transition assessment",
    },
    "new-workforce": {
      heroTitle: "Get a clear first-career direction with practical, beginner-friendly guidance.",
      heroLead: "Use your early experience to identify entry-level role options, next skills, and action steps that build confidence quickly.",
      analysisIntro: "Upload your resume or profile summary to get an approachable report with role options and immediate next steps.",
      panelTitle: "New-workforce path selected",
      panelDescription: "Start with a simple plan: one role focus, one learning milestone, and one weekly job-search routine.",
      actions: [
        "Choose one target role and build your resume around it.",
        "Take one beginner-friendly roadmap course this month.",
        "Apply to a consistent set of entry-level opportunities each week.",
      ],
      chips: ["Entry-level pathways", "Beginner support", "First-job strategy"],
      ctaLabel: "Start first-career assessment",
    },
  };

  const describeFile = (file) => {
    if (!file) {
      return "No file selected yet.";
    }

    return `Selected file: ${file.name}`;
  };

  const normalizeRoleKey = (role) => `${(role?.job_role || "").trim().toLowerCase()}::${(role?.industry || "").trim().toLowerCase()}`;

  const dedupeRoles = (roles) => {
    const roleMap = new Map();

    (roles || []).forEach((role) => {
      const key = normalizeRoleKey(role);
      const current = roleMap.get(key);
      if (!current || (role.similarity || 0) > (current.similarity || 0)) {
        roleMap.set(key, role);
      }
    });

    return Array.from(roleMap.values()).sort((left, right) => (right.similarity || 0) - (left.similarity || 0));
  };

  const buildRoleLinks = (role) => {
    const query = encodeURIComponent(role?.job_role || "career role");
    return [
      { label: "Indeed", url: `https://www.indeed.com/jobs?q=${query}` },
      { label: "LinkedIn", url: `https://www.linkedin.com/jobs/search/?keywords=${query}` },
      { label: "Naukri", url: `https://www.naukri.com/${encodeURIComponent((role?.job_role || "career").toLowerCase().replace(/\s+/g, "-"))}-jobs` },
    ];
  };

  const setUploadStatus = (message) => {
    if (uploadStatus) {
      uploadStatus.textContent = message;
    }
  };

  const clearLoadingSkeleton = () => {
    if (loadingSkeletonTimer) {
      window.clearTimeout(loadingSkeletonTimer);
      loadingSkeletonTimer = null;
    }
    if (modal) {
      modal.classList.remove("is-loading-advanced");
    }
  };

  const renderAdvancedSkeleton = () => {
    if (!modal) return;
    modal.classList.add("is-loading-advanced");
    if (resultStatus) {
      resultStatus.textContent = "Analyzing with Llama 3...";
      resultStatus.classList.add("shimmer-line");
    }
    if (narrative) {
      narrative.textContent = "Preparing an executive narrative, role pivots, and roadmap suggestions.";
      narrative.classList.add("shimmer-line");
    }
    if (dashboardRoleStatus) {
      dashboardRoleStatus.textContent = "Processing advanced request";
    }
  };

  const setMode = (mode) => {
    activeMode = mode;
    if (modeInput) {
      modeInput.value = mode;
    }
    modeButtons.forEach((button) => button.classList.toggle("is-active", button.dataset.mode === mode));
    [dashboardRiskRing, dashboardRiskScore, dashboardRiskLabel, dashboardRoleBars, resultBanner].forEach((element) => {
      if (!element) return;
      element.classList.remove("motion-fade-up", "motion-stagger-1", "motion-stagger-2", "motion-stagger-3");
      void element.offsetWidth;
      element.classList.add("motion-fade-up");
    });
  };

  const openModal = () => {
    if (!modal) return;
    modal.classList.remove("hidden");
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
  };

  const closeModal = () => {
    if (!modal) return;
    modal.classList.remove("is-open");
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
  };

  modalCloseButtons.forEach((button) => {
    button.addEventListener("click", closeModal);
  });

  modal?.addEventListener("click", (event) => {
    if (event.target === modal) {
      closeModal();
    }
  });

  const setBusy = (busy, message) => {
    submitButton.disabled = busy;
    browseButton.disabled = busy;
    modeButtons.forEach((button) => {
      button.disabled = busy;
    });
    submitButton.textContent = busy ? "Loading..." : originalSubmitLabel;

    if (busy) {
      openModal();
      if (activeMode === "advanced") {
        renderAdvancedSkeleton();
      }
      if (modalTitle) {
        modalTitle.textContent = message || "Analyzing resume locally...";
      }
      if (modalMode) {
        modalMode.textContent = `${activeMode === "advanced" ? "Advanced" : "Standard"} mode`;
      }
      if (modalRiskScore) {
        modalRiskScore.textContent = "Processing...";
      }
      if (modalRiskLabel) {
        modalRiskLabel.textContent = "In progress";
      }
      if (resultStatus) {
        resultStatus.textContent = message || "Analyzing resume locally...";
      }
      if (narrative) {
        narrative.textContent = "Please wait while Prayash processes the resume in memory.";
      }
      if (dashboardRiskSummary) {
        dashboardRiskSummary.textContent = "Processing prediction...";
      }
    } else {
      modal?.classList.remove("is-processing");
    }
  };

  const renderList = (container, items, renderer) => {
    if (!container) return;
    container.innerHTML = items.map(renderer).join("");
  };

  const renderSimpleSteps = (container, items, heading) => {
    if (!container) return;
    const safeItems = (items || []).filter(Boolean);
    if (!safeItems.length) {
      container.innerHTML = `<div class="list-card"><div><strong>No actions yet</strong><p>Run analysis to generate practical next steps.</p></div></div>`;
      return;
    }
    container.innerHTML = safeItems.map((item) => `
      <div class="list-card motion-fade-up">
        <div>
          <strong>${heading}</strong>
          <p>${item}</p>
        </div>
      </div>
    `).join("");
  };

  const buildFallbackNextSteps = (payload) => {
    const riskBand = (payload.risk_label || "Moderate").toLowerCase();
    const topRoles = dedupeRoles(payload.top_roles || []).slice(0, 2);
    const roadmap = payload.roadmap || [];

    const learningActions = roadmap.slice(0, 3).map((item) => `Start '${item.course}' and focus on ${item.skill || "core skill"} this week.`);
    if (!learningActions.length) {
      learningActions.push("Pick one high-impact skill gap and schedule three focused practice sessions this week.");
    }

    const jobActions = topRoles.length
      ? [
          ...topRoles.map((role) => `Save 10 postings for ${role.job_role} and track repeated requirements.`),
          "Update your resume summary with language from your best-matched role.",
        ]
      : [
          "Collect 10 postings in your target field and list repeated skills.",
          "Tailor your resume headline for one target role before applying.",
        ];

    const educationActions = [
      riskBand === "elevated"
        ? "Prioritize transferable digital and analytical skills to reduce automation exposure."
        : riskBand === "low"
          ? "Deepen specialization in your strongest areas to preserve your low-risk profile."
          : "Build adjacent skills that improve resilience and role flexibility.",
      "Compare one short certificate and one longer credential for your target direction.",
      "Set a 4, 8, or 12-week timeline and add deadlines to your calendar.",
    ];

    const supportActions = [
      "Review methodology to understand how scores and role matches are generated.",
      "Review privacy details to confirm data handling safeguards.",
      "Use advanced mode if you want deeper narrative guidance.",
    ];

    return {
      learning_actions: learningActions,
      job_search_actions: jobActions,
      education_training_actions: educationActions,
      support_resources: supportActions,
    };
  };

  const renderGuidedNextSteps = (payload) => {
    const guided = payload.guided_next_steps || buildFallbackNextSteps(payload);
    renderSimpleSteps(nextStepsLearning, guided.learning_actions, "Learning action");
    renderSimpleSteps(nextStepsJobs, guided.job_search_actions, "Job action");
    renderSimpleSteps(nextStepsEducation, guided.education_training_actions, "Training action");
    renderSimpleSteps(nextStepsSupport, guided.support_resources, "Support resource");

    if (nextStepsStatus) {
      nextStepsStatus.textContent = "Updated from latest analysis";
    }

    if (modalNextSteps) {
      const compact = [
        ...(guided.learning_actions || []).slice(0, 1),
        ...(guided.job_search_actions || []).slice(0, 1),
        ...(guided.education_training_actions || []).slice(0, 1),
      ];
      renderSimpleSteps(modalNextSteps, compact, "Next step");
    }
  };

  const renderPathway = (pathKey) => {
    const content = PATHWAY_CONTENT[pathKey] || PATHWAY_CONTENT.student;
    activePath = pathKey;

    if (heroTitle) heroTitle.textContent = content.heroTitle;
    if (heroLead) heroLead.textContent = content.heroLead;
    if (analysisIntro) analysisIntro.textContent = content.analysisIntro;
    if (pathTitle) pathTitle.textContent = content.panelTitle;
    if (pathDescription) pathDescription.textContent = content.panelDescription;
    if (heroPrimaryLink) heroPrimaryLink.textContent = content.ctaLabel;

    if (heroActions) {
      heroActions.innerHTML = (content.chips || []).map((chip) => `<span class="chip">${chip}</span>`).join("");
    }

    if (pathActions) {
      pathActions.innerHTML = (content.actions || []).map((action) => `
        <div class="list-card">
          <div>
            <strong>Suggested action</strong>
            <p>${action}</p>
          </div>
        </div>
      `).join("");
    }

    pathButtons.forEach((button) => {
      button.classList.toggle("is-active", button.dataset.pathOption === pathKey);
    });
  };

  const resetResultStyles = () => {
    if (!resultBanner) return;
    resultBanner.style.background = "";
    resultBanner.style.borderColor = "";
    resultBanner.style.color = "";
  };

  const updateDashboardResults = (payload) => {
    const uniqueRoles = dedupeRoles(payload.top_roles || []);
    if (dashboardRiskRing) {
      dashboardRiskRing.style.setProperty("--score", `${Math.max(0.05, Math.min(0.95, payload.risk_score || 0))}`);
    }
    if (dashboardRiskScore) {
      dashboardRiskScore.textContent = `${Math.round((payload.risk_score || 0) * 100)}%`;
    }
    if (dashboardRiskLabel) {
      dashboardRiskLabel.textContent = payload.risk_label ? `${payload.risk_label} risk` : "Risk";
    }
    if (dashboardRiskSummary) {
      dashboardRiskSummary.textContent = payload.cognitive_career_narrative || "Local ML prediction ready.";
    }
    if (dashboardRoleStatus) {
      dashboardRoleStatus.textContent = uniqueRoles.length ? "Live prediction" : "No matches";
    }
    if (dashboardRoleBars) {
      dashboardRoleBars.innerHTML = uniqueRoles.slice(0, 3).map((role, index) => `
        <div class="motion-fade-up motion-stagger-${Math.min(index + 1, 5)}">
          <div class="inline-actions" style="justify-content: space-between;">
            <strong>${role.job_role}</strong><strong class="muted">${Math.round((role.similarity || 0) * 100)}%</strong>
          </div>
          <div class="bar"><span style="width: ${Math.round((role.similarity || 0) * 100)}%;"></span></div>
          <p class="small-note" style="margin: 0.45rem 0 0;">${role.industry} · Risk ${Math.round((role.risk_score || 0) * 100)}%</p>
        </div>
      `).join("");
    }
  };

  const renderReasoningInsights = (payload) => {
    if (!riskInsights) return;
    const reasoning = payload.reasoning || {};
    const cards = [];

    if (reasoning.summary) {
      cards.push(`
        <div class="list-card pivot-card motion-fade-up">
          <div>
            <strong>Why this score</strong>
            <p>${reasoning.summary}</p>
          </div>
        </div>
      `);
    }

    (reasoning.risk_drivers || []).forEach((driver, index) => {
      cards.push(`
        <div class="list-card motion-fade-up motion-stagger-${Math.min(index + 1, 5)}">
          <div>
            <strong>Risk driver ${index + 1}</strong>
            <p>${driver}</p>
          </div>
        </div>
      `);
    });

    if (reasoning.skills_detected?.length) {
      cards.push(`
        <div class="list-card motion-fade-up">
          <div>
            <strong>Detected skills</strong>
            <p>${reasoning.skills_detected.join(", ")}</p>
          </div>
        </div>
      `);
    }

    if (reasoning.next_steps?.length) {
      cards.push(`
        <div class="list-card motion-fade-up">
          <div>
            <strong>Recommended next steps</strong>
            <p>${reasoning.next_steps.join(" · ")}</p>
          </div>
        </div>
      `);
    }

    if (reasoning.evidence?.length) {
      cards.push(`
        <div class="list-card motion-fade-up">
          <div>
            <strong>Evidence trail</strong>
            <p>${reasoning.evidence.map((item) => `${item.label}: ${item.value}`).join(" · ")}</p>
          </div>
        </div>
      `);
    }

    cards.push(`
      <div class="list-card motion-fade-up">
        <div>
          <strong>Confidence note</strong>
          <p>${reasoning.confidence_note || "Explainability is grounded in the local feature trace."}</p>
        </div>
      </div>
    `);

    riskInsights.innerHTML = cards.join("");
  };

  const renderModal = (payload) => {
    clearLoadingSkeleton();
    const uniqueRoles = dedupeRoles(payload.top_roles || []);
    if (modalTitle) {
      modalTitle.textContent = payload.mode === "advanced" ? "Deep AI narrative generated" : "Local ML analysis complete";
    }
    if (modalRiskScore) {
      modalRiskScore.textContent = `${Math.round((payload.risk_score || 0) * 100)}%`;
    }
    if (modalRiskLabel) {
      modalRiskLabel.textContent = payload.risk_label ? `${payload.risk_label} risk` : "Risk";
    }
    if (modalMode) {
      modalMode.textContent = `${payload.mode === "advanced" ? "Advanced" : "Standard"} mode`;
    }
    if (resultStatus) {
      resultStatus.textContent = payload.mode === "advanced" ? "Deep AI narrative generated" : "Local ML analysis complete";
    }
    if (narrative) {
      narrative.textContent = payload.cognitive_career_narrative || "";
    }
    updateDashboardResults(payload);
    renderReasoningInsights(payload);
    renderGuidedNextSteps(payload);

    renderList(rolesList, uniqueRoles, (role) => {
      const openingLinks = buildRoleLinks(role);
      return `
      <div class="list-card pivot-card motion-fade-up">
        <div>
          <strong>${role.job_role}</strong>
          <p>${role.industry} · Risk ${Math.round((role.risk_score || 0) * 100)}%</p>
          <div class="pill-row" style="margin-top: 0.75rem;">
            ${openingLinks.map((link) => `<a class="button-ghost" href="${link.url}" target="_blank" rel="noreferrer">${link.label}</a>`).join("")}
          </div>
        </div>
        <span class="status-pill">${Math.round((role.similarity || 0) * 100)}% match</span>
      </div>
    `;
    });

    renderList(roadmapList, payload.roadmap || [], (course) => `
      <div class="roadmap-item motion-fade-up">
        <div>
          <strong>${course.course}</strong>
          <p>${course.skill} · ${course.reason}</p>
        </div>
        ${course.url ? `<a class="button-ghost" href="${course.url}" target="_blank" rel="noreferrer">Open</a>` : ""}
      </div>
    `);

    renderList(riasecList, Object.entries(payload.riasec?.scores || {}), ([name, score]) => `
      <div class="list-card motion-fade-up">
        <div>
          <strong>${name}</strong>
          <p>Career preference alignment</p>
        </div>
        <span class="status-pill">${score}</span>
      </div>
    `);
  };

  const renderError = (message) => {
    clearLoadingSkeleton();
    openModal();
    if (resultBanner) {
      resultBanner.style.background = "rgba(186, 26, 26, 0.08)";
      resultBanner.style.borderColor = "rgba(186, 26, 26, 0.35)";
      resultBanner.style.color = "var(--error)";
    }
    if (modalTitle) {
      modalTitle.textContent = "Assessment could not complete";
    }
    if (modalRiskScore) {
      modalRiskScore.textContent = "--";
    }
    if (modalRiskLabel) {
      modalRiskLabel.textContent = "Error";
    }
    if (modalMode) {
      modalMode.textContent = `${activeMode === "advanced" ? "Advanced" : "Standard"} mode`;
    }
    if (resultStatus) {
      resultStatus.textContent = "Assessment could not complete";
    }
    if (narrative) {
      narrative.textContent = message;
    }
    if (rolesList) rolesList.innerHTML = "";
    if (roadmapList) roadmapList.innerHTML = "";
    if (riasecList) riasecList.innerHTML = "";
    if (dashboardRiskSummary) {
      dashboardRiskSummary.textContent = message;
    }
    if (dashboardRoleStatus) {
      dashboardRoleStatus.textContent = "Error";
    }
    if (riskInsights) {
      riskInsights.innerHTML = `
        <div class="list-card">
          <div>
            <strong>Analysis unavailable</strong>
            <p>${message}</p>
          </div>
        </div>
      `;
    }
    if (nextStepsStatus) {
      nextStepsStatus.textContent = "Unavailable";
    }
    [nextStepsLearning, nextStepsJobs, nextStepsEducation, nextStepsSupport, modalNextSteps].forEach((container) => {
      if (!container) return;
      container.innerHTML = `
        <div class="list-card">
          <div>
            <strong>Guidance unavailable</strong>
            <p>${message}</p>
          </div>
        </div>
      `;
    });
  };

  modeButtons.forEach((button) => {
    button.addEventListener("click", () => setMode(button.dataset.mode));
  });

  pathButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const pathKey = button.dataset.pathOption || "student";
      renderPathway(pathKey);
    });
  });

  browseButton.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", () => {
    selectedFile = fileInput.files?.[0] || null;
    setUploadStatus(describeFile(selectedFile));
    if (dropZone) {
      dropZone.classList.remove("is-dropped");
    }
  });

  if (dropZone) {
    ["dragenter", "dragover"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropZone.classList.add("is-dragover");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropZone.classList.remove("is-dragover");
      });
    });

    dropZone.addEventListener("drop", (event) => {
      const droppedFile = event.dataTransfer?.files?.[0];
      if (!droppedFile) return;
      const transfer = new DataTransfer();
      transfer.items.add(droppedFile);
      fileInput.files = transfer.files;
      selectedFile = droppedFile;
      setUploadStatus(describeFile(selectedFile));
      dropZone.classList.add("is-dropped");
      window.setTimeout(() => dropZone.classList.remove("is-dropped"), 700);
    });
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const formData = new FormData(form);
    if (selectedFile && !formData.get("resume_file")) {
      formData.set("resume_file", selectedFile);
    }
    formData.set("mode", activeMode);

    const text = (formData.get("resume_text") || "").toString().trim();
    const hasFile = fileInput.files && fileInput.files.length > 0;
    if (!hasFile && !text) {
      renderError("Add a resume file or paste resume text before starting the assessment.");
      return;
    }

    setUploadStatus(describeFile(selectedFile || fileInput.files?.[0] || null));
    setBusy(true, activeMode === "advanced" ? "Running advanced analysis..." : "Running local analysis...");

    try {
      const response = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || "Analysis failed.");
      }

      resetResultStyles();
      renderModal(payload);
    } catch (error) {
      renderError(error.message || "Analysis failed.");
    } finally {
      setBusy(false);
    }
  });

  setMode(activeMode);
  renderPathway(activePath);

  // ── Scroll Reveal: IntersectionObserver ──
  const REVEAL_SELECTORS = [
    ".feature-card",
    ".insight-card",
    ".method-card",
    ".form-card",
    ".section-card",
    ".glass-card",
    ".privacy-card",
    ".contact-card",
    ".dashboard-grid > div",
    ".page-hero__grid > div",
    ".hero__grid > div",
    ".hero__grid > .hero-panel",
  ].join(", ");

  const initScrollReveal = () => {
    // Skip if user prefers reduced motion
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const directions = ["", "", "", "--left", "--right", "--scale"]; // bias toward default (up)
    document.querySelectorAll(REVEAL_SELECTORS).forEach((el) => {
      if (el.closest(".result-modal")) return; // skip modal internals
      const dir = directions[Math.floor(Math.random() * directions.length)];
      el.classList.add(`reveal${dir}`);
    });

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );

    document.querySelectorAll(".reveal").forEach((el) => observer.observe(el));
  };

  // Stagger children in grids that just became visible
  const initStaggerClasses = () => {
    document.querySelectorAll(
      ".feature-grid, .insight-grid, .method-grid, .partnership-grid, .dashboard-grid, .hero__grid, .page-hero__grid"
    ).forEach((grid) => {
      const children = grid.querySelectorAll(":scope > .reveal");
      children.forEach((child, i) => {
        const n = (i % 5) + 1;
        child.classList.add(`reveal--stagger-${n}`);
      });
    });
  };

  // Run after DOM is painted
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      initScrollReveal();
      initStaggerClasses();
    });
  } else {
    initScrollReveal();
    initStaggerClasses();
  }
})();