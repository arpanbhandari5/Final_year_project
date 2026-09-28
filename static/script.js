(() => {
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
  const uncertaintyBanner = document.querySelector("[data-uncertainty-banner]");
  const modalUncertaintyBanner = document.querySelector("[data-modal-uncertainty]");
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
  const jdMatch = document.querySelector("[data-jd-match]");
  const feedbackForm = document.querySelector("[data-feedback-form]");
  const feedbackStatus = document.querySelector("[data-feedback-status]");
  const feedbackUploadId = document.querySelector("[data-feedback-upload-id]");
  const discoveryForm = document.querySelector("[data-discovery-form]");
  const discoverySummary = document.querySelector("[data-discovery-summary]");
  const discoverySummaryText = document.querySelector("[data-discovery-summary-text]");
  let selectedRating = null;

  if (!form || !fileInput || !submitButton) {
    return;
  }

  let activeMode = modeInput?.value || "standard";
  let activePath = "student";
  let selectedFile = null;
  const originalSubmitLabel = submitButton.textContent.trim();
  let loadingSkeletonTimer = null;
  const escapeHtml = (value) => String(value || "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
  const createElement = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  };
  const replaceChildren = (container, children) => {
    if (container) container.replaceChildren(...children.filter(Boolean));
  };
  const makeListCard = (title, description, className = "list-card") => {
    const card = createElement("div", className);
    const content = createElement("div");
    content.append(createElement("strong", null, title), createElement("p", null, description));
    card.append(content);
    return card;
  };

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
    replaceChildren(container, items.map(renderer));
  };

  const renderSimpleSteps = (container, items, heading) => {
    if (!container) return;
    const safeItems = (items || []).filter(Boolean);
    if (!safeItems.length) {
      replaceChildren(container, [makeListCard("No actions yet", "Run analysis to generate practical next steps.")]);
      return;
    }
    replaceChildren(container, safeItems.map((item) => makeListCard(heading, item, "list-card motion-fade-up")));
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
      replaceChildren(heroActions, (content.chips || []).map((chip) => createElement("span", "chip", chip)));
    }

    if (pathActions) {
      replaceChildren(pathActions, (content.actions || []).map((action) => makeListCard("Suggested action", action)));
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
    const confidence = payload.confidence || {};
    const uncertaintyText = `Uncertainty: ${confidence.label || "Limited"} confidence (${Math.round((confidence.score || 0) * 100)}%). This is an educational estimate, not a forecast.`;
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
    if (uncertaintyBanner) uncertaintyBanner.textContent = uncertaintyText;
    if (modalUncertaintyBanner) modalUncertaintyBanner.textContent = uncertaintyText;
    if (dashboardRoleStatus) {
      dashboardRoleStatus.textContent = uniqueRoles.length ? "Live prediction" : "No matches";
    }
    if (dashboardRoleBars) {
      const roleNodes = uniqueRoles.slice(0, 3).map((role, index) => {
        const similarity = Math.round((role.similarity || 0) * 100);
        const wrapper = createElement("div", `motion-fade-up motion-stagger-${Math.min(index + 1, 5)}`);
        const header = createElement("div", "inline-actions");
        header.style.justifyContent = "space-between";
        header.append(createElement("strong", null, role.job_role), createElement("strong", "muted", `${similarity}%`));
        const bar = createElement("div", "bar");
        const barFill = createElement("span");
        barFill.style.width = `${similarity}%`;
        bar.append(barFill);
        const detail = createElement("p", "small-note", `${role.industry || "Unknown industry"} · Risk ${Math.round((role.risk_score || 0) * 100)}%`);
        detail.style.margin = "0.45rem 0 0";
        wrapper.append(header, bar, detail);
        return wrapper;
      });
      replaceChildren(dashboardRoleBars, roleNodes);
    }
  };

  const renderReasoningInsights = (payload) => {
    if (!riskInsights) return;
    const reasoning = payload.reasoning || {};
    const cards = [];

    if (reasoning.summary) {
      cards.push(makeListCard("Why this score", reasoning.summary, "list-card pivot-card motion-fade-up"));
    }

    (reasoning.risk_drivers || []).forEach((driver, index) => {
      cards.push(makeListCard(`Risk driver ${index + 1}`, driver, `list-card motion-fade-up motion-stagger-${Math.min(index + 1, 5)}`));
    });

    if (reasoning.skills_detected?.length) {
      cards.push(makeListCard("Detected skills", reasoning.skills_detected.join(", "), "list-card motion-fade-up"));
    }

    if (reasoning.next_steps?.length) {
      cards.push(makeListCard("Recommended next steps", reasoning.next_steps.join(" · "), "list-card motion-fade-up"));
    }

    if (reasoning.evidence?.length) {
      cards.push(makeListCard("Evidence trail", reasoning.evidence.map((item) => `${item.label}: ${item.value}`).join(" · "), "list-card motion-fade-up"));
    }

    cards.push(makeListCard("Confidence note", reasoning.confidence_note || "Explainability is grounded in the local feature trace.", "list-card motion-fade-up"));

    replaceChildren(riskInsights, cards);
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
    if (feedbackUploadId) feedbackUploadId.value = payload.upload_id || "";
    if (jdMatch) {
      const match = payload.jd_match;
      if (!match) {
        replaceChildren(jdMatch, [makeListCard("No target job added", "Paste a job description in the form to compare it with your resume.")]);
      } else {
        const matchCard = createElement("div", "list-card");
        const matchContent = createElement("div");
        matchContent.append(
          createElement("strong", null, `${match.match_percent}% identified skill overlap`),
          createElement("p", null, `Matched: ${(match.matched_skills || []).join(", ") || "None identified"}`),
          createElement("p", null, `Missing: ${(match.missing_skills || []).join(", ") || "None identified"}`),
        );
        matchCard.append(matchContent);
        const evidenceCards = (match.evidence || []).map((item) => makeListCard(item.skill, item.context));
        const actionCards = (match.action_plan || []).map((item) => makeListCard("Next action", item));
        replaceChildren(jdMatch, [matchCard, ...evidenceCards, ...actionCards]);
      }
    }

    renderList(rolesList, uniqueRoles, (role) => {
      const openingLinks = buildRoleLinks(role);
      const card = createElement("div", "list-card pivot-card motion-fade-up");
      const content = createElement("div");
      content.append(
        createElement("strong", null, role.job_role),
        createElement("p", null, `${role.industry || "Unknown industry"} · Risk ${Math.round((role.risk_score || 0) * 100)}%`),
      );
      const links = createElement("div", "pill-row");
      links.style.marginTop = "0.75rem";
      openingLinks.forEach((link) => {
        const anchor = createElement("a", "button-ghost", link.label);
        anchor.href = link.url;
        anchor.target = "_blank";
        anchor.rel = "noreferrer";
        links.append(anchor);
      });
      content.append(links);
      card.append(content, createElement("span", "status-pill", `${Math.round((role.similarity || 0) * 100)}% match`));
      return card;
    });

    renderList(roadmapList, payload.roadmap || [], (course) => {
      const item = createElement("div", "roadmap-item motion-fade-up");
      const content = createElement("div");
      content.append(createElement("strong", null, course.course), createElement("p", null, `${course.skill} · ${course.reason}`));
      item.append(content);
      if (course.url) {
        const link = createElement("a", "button-ghost", "Open");
        link.href = course.url;
        link.target = "_blank";
        link.rel = "noreferrer";
        item.append(link);
      }
      return item;
    });

    renderList(riasecList, Object.entries(payload.riasec?.scores || {}), ([name, score]) => {
      const card = makeListCard(name, "Career preference alignment", "list-card motion-fade-up");
      card.append(createElement("span", "status-pill", score));
      return card;
    });
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
    [rolesList, roadmapList, riasecList].forEach((container) => replaceChildren(container, []));
    if (dashboardRiskSummary) {
      dashboardRiskSummary.textContent = message;
    }
    if (dashboardRoleStatus) {
      dashboardRoleStatus.textContent = "Error";
    }
    if (riskInsights) {
      replaceChildren(riskInsights, [makeListCard("Analysis unavailable", message)]);
    }
    if (nextStepsStatus) {
      nextStepsStatus.textContent = "Unavailable";
    }
    [nextStepsLearning, nextStepsJobs, nextStepsEducation, nextStepsSupport, modalNextSteps].forEach((container) => {
      if (!container) return;
      replaceChildren(container, [makeListCard("Guidance unavailable", message)]);
    });
  };

  modeButtons.forEach((button) => {
    button.addEventListener("click", () => setMode(button.dataset.mode));
  });

  document.querySelectorAll("[data-feedback-rating]").forEach((button) => {
    button.addEventListener("click", () => {
      selectedRating = Number(button.dataset.feedbackRating);
      document.querySelectorAll("[data-feedback-rating]").forEach((item) => item.classList.toggle("is-selected", item === button));
    });
  });

  feedbackForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(feedbackForm);
    if (selectedRating !== null) formData.set("rating", String(selectedRating));
    if (!(formData.get("message") || "").toString().trim()) formData.set("message", selectedRating === 1 ? "Recommendation marked helpful." : "Recommendation marked not helpful.");
    const response = await fetch("/api/feedback", { method: "POST", body: formData });
    const payload = await response.json();
    if (feedbackStatus) feedbackStatus.textContent = payload.success ? "Thanks — your feedback was saved." : (payload.error || "Feedback could not be saved.");
  });

  discoveryForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const answers = new FormData(discoveryForm);
    const value = (name) => String(answers.get(name) || "");
    const summary = `You are focused on ${value("direction").toLowerCase()}, with ${value("priority").toLowerCase()} as your main priority. Your vision is: “${value("vision")}” When facing a skill gap, you would ${value("gap_response").toLowerCase()}; you value ${value("decision_style").toLowerCase()} when choosing opportunities and prefer to ${value("work_style").toLowerCase()}.`;
    if (discoverySummaryText) discoverySummaryText.textContent = summary;
    discoverySummary?.classList.remove("hidden");
    discoverySummary?.scrollIntoView({ behavior: "smooth", block: "nearest" });
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
})();
