type AnalysisMode = "standard" | "advanced";

type RoleOpening = { label?: string; url?: string };

export interface JobPivot {
  job_role?: string;
  industry?: string;
  similarity?: number;
  risk_score?: number;
  skills?: string[];
  openings?: RoleOpening[];
}

export interface RoadmapItem {
  course?: string;
  skill?: string;
  reason?: string;
  url?: string;
}

export interface RiasecProfile {
  primary?: string;
  secondary?: string;
  tertiary?: string;
  scores?: Record<string, number | string>;
}

export interface AnalysisResult {
  success?: boolean;
  mode?: AnalysisMode | string;
  risk_score?: number;
  risk_label?: string;
  cognitive_career_narrative?: string;
  top_roles?: JobPivot[];
  roadmap?: RoadmapItem[];
  riasec?: RiasecProfile;
  skill_clusters?: Array<Record<string, unknown>>;
  reasoning?: {
    summary?: string;
    risk_drivers?: string[];
    evidence?: Array<{ label?: string; value?: string; detail?: string }>;
    skills_detected?: string[];
    next_steps?: string[];
    confidence_note?: string;
  };
  error?: string;
}

const form = document.querySelector<HTMLFormElement>("[data-analysis-form]");
const modeButtons = document.querySelectorAll<HTMLButtonElement>("[data-mode]");
const modeInput = document.querySelector<HTMLInputElement>("[data-mode-input]");
const browseButton = document.querySelector<HTMLButtonElement>("[data-browse-button]");
const fileInput = document.querySelector<HTMLInputElement>("[data-file-input]");
const dropZone = document.querySelector<HTMLElement>("[data-drop-zone]");
const submitButton = document.querySelector<HTMLButtonElement>("[data-assess-button]");
const modal = document.querySelector<HTMLElement>("[data-result-modal]");
const modalTitle = document.querySelector<HTMLElement>("[data-modal-title]");
const modalRiskScore = document.querySelector<HTMLElement>("[data-modal-risk-score]");
const modalRiskLabel = document.querySelector<HTMLElement>("[data-modal-risk-label]");
const modalMode = document.querySelector<HTMLElement>("[data-modal-mode]");
const modalCloseButtons = document.querySelectorAll<HTMLButtonElement>("[data-modal-close]");
const resultBanner = document.querySelector<HTMLElement>("[data-result-banner]");
const resultStatus = document.querySelector<HTMLElement>("[data-result-status]");
const narrative = document.querySelector<HTMLElement>("[data-narrative]");
const rolesList = document.querySelector<HTMLElement>("[data-roles-list]");
const roadmapList = document.querySelector<HTMLElement>("[data-roadmap-list]");
const riasecList = document.querySelector<HTMLElement>("[data-riasec-list]");
const uploadStatus = document.querySelector<HTMLElement>("[data-upload-status]");
const dashboardRiskRing = document.querySelector<HTMLElement>("[data-risk-ring]");
const dashboardRiskScore = document.querySelector<HTMLElement>("[data-risk-score-display]");
const dashboardRiskLabel = document.querySelector<HTMLElement>("[data-risk-label-display]");
const dashboardRiskSummary = document.querySelector<HTMLElement>("[data-risk-summary]");
const dashboardRoleStatus = document.querySelector<HTMLElement>("[data-role-status]");
const dashboardRoleBars = document.querySelector<HTMLElement>("[data-role-bars]");
const riskInsights = document.querySelector<HTMLElement>("[data-risk-insights]");

if (!form || !fileInput || !submitButton || !browseButton) {
  throw new Error("Prayash dashboard controls are missing.");
}

let activeMode: AnalysisMode = (modeInput?.value as AnalysisMode) || "standard";
let selectedFile: File | null = null;
const originalSubmitLabel = submitButton.textContent?.trim() || "Run analysis";
let loadingSkeletonTimer: number | null = null;

const describeFile = (file: File | null): string => (file ? `Selected file: ${file.name}` : "No file selected yet.");

const normalizeRoleKey = (role: JobPivot): string => `${(role.job_role || "").trim().toLowerCase()}::${(role.industry || "").trim().toLowerCase()}`;

const dedupeRoles = (roles: JobPivot[] = []): JobPivot[] => {
  const roleMap = new Map<string, JobPivot>();
  roles.forEach((role) => {
    const key = normalizeRoleKey(role);
    const current = roleMap.get(key);
    if (!current || (role.similarity || 0) > (current.similarity || 0)) {
      roleMap.set(key, role);
    }
  });
  return Array.from(roleMap.values()).sort((left, right) => (right.similarity || 0) - (left.similarity || 0));
};

const buildRoleLinks = (role: JobPivot): RoleOpening[] => {
  const query = encodeURIComponent(role.job_role || "career role");
  return [
    { label: "Indeed", url: `https://www.indeed.com/jobs?q=${query}` },
    { label: "LinkedIn", url: `https://www.linkedin.com/jobs/search/?keywords=${query}` },
    {
      label: "Naukri",
      url: `https://www.naukri.com/${encodeURIComponent((role.job_role || "career").toLowerCase().replace(/\s+/g, "-"))}-jobs`,
    },
  ];
};

const setUploadStatus = (message: string): void => {
  if (uploadStatus) uploadStatus.textContent = message;
};

const clearLoadingSkeleton = (): void => {
  if (loadingSkeletonTimer !== null) {
    window.clearTimeout(loadingSkeletonTimer);
    loadingSkeletonTimer = null;
  }
  modal?.classList.remove("is-loading-advanced");
};

const renderAdvancedSkeleton = (): void => {
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

const setMode = (mode: AnalysisMode): void => {
  activeMode = mode;
  if (modeInput) modeInput.value = mode;
  modeButtons.forEach((button) => button.classList.toggle("is-active", button.dataset.mode === mode));
  [dashboardRiskRing, dashboardRiskScore, dashboardRiskLabel, dashboardRoleBars, resultBanner].forEach((element) => {
    if (!element) return;
    element.classList.remove("motion-fade-up", "motion-stagger-1", "motion-stagger-2", "motion-stagger-3");
    void element.offsetWidth;
    element.classList.add("motion-fade-up");
  });
};

const openModal = (): void => {
  if (!modal) return;
  modal.classList.remove("hidden");
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
};

const closeModal = (): void => {
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
};

modalCloseButtons.forEach((button) => button.addEventListener("click", closeModal));
modal?.addEventListener("click", (event) => {
  if (event.target === modal) closeModal();
});

const setBusy = (busy: boolean, message?: string): void => {
  submitButton.disabled = busy;
  browseButton.disabled = busy;
  modeButtons.forEach((button) => {
    button.disabled = busy;
  });
  submitButton.textContent = busy ? "Loading..." : originalSubmitLabel;

  if (busy) {
    openModal();
    if (activeMode === "advanced") renderAdvancedSkeleton();
    if (modalTitle) modalTitle.textContent = message || "Analyzing resume locally...";
    if (modalMode) modalMode.textContent = `${activeMode === "advanced" ? "Advanced" : "Standard"} mode`;
    if (modalRiskScore) modalRiskScore.textContent = "Processing...";
    if (modalRiskLabel) modalRiskLabel.textContent = "In progress";
    if (resultStatus) resultStatus.textContent = message || "Analyzing resume locally...";
    if (narrative) narrative.textContent = "Please wait while Prayash processes the resume in memory.";
    if (dashboardRiskSummary) dashboardRiskSummary.textContent = "Processing prediction...";
    return;
  }

  modal?.classList.remove("is-processing");
};

const renderList = <T>(container: HTMLElement | null, items: T[], renderer: (item: T, index: number) => string): void => {
  if (!container) return;
  container.innerHTML = items.map(renderer).join("");
};

const resetResultStyles = (): void => {
  if (!resultBanner) return;
  resultBanner.style.background = "";
  resultBanner.style.borderColor = "";
  resultBanner.style.color = "";
};

const updateDashboardResults = (payload: AnalysisResult): void => {
  const uniqueRoles = dedupeRoles(payload.top_roles || []);
  if (dashboardRiskRing) {
    dashboardRiskRing.style.setProperty("--score", `${Math.max(0.05, Math.min(0.95, payload.risk_score || 0))}`);
  }
  if (dashboardRiskScore) dashboardRiskScore.textContent = `${Math.round((payload.risk_score || 0) * 100)}%`;
  if (dashboardRiskLabel) dashboardRiskLabel.textContent = payload.risk_label ? `${payload.risk_label} risk` : "Risk";
  if (dashboardRiskSummary) dashboardRiskSummary.textContent = payload.cognitive_career_narrative || "Local ML prediction ready.";
  if (dashboardRoleStatus) dashboardRoleStatus.textContent = uniqueRoles.length ? "Live prediction" : "No matches";
  if (dashboardRoleBars) {
    dashboardRoleBars.innerHTML = uniqueRoles.slice(0, 3).map((role, index) => `
      <div class="motion-fade-up motion-stagger-${Math.min(index + 1, 5)}">
        <div class="inline-actions" style="justify-content: space-between;">
          <strong>${role.job_role || "Role"}</strong><strong class="muted">${Math.round((role.similarity || 0) * 100)}%</strong>
        </div>
        <div class="bar"><span style="width: ${Math.round((role.similarity || 0) * 100)}%;"></span></div>
        <p class="small-note" style="margin: 0.45rem 0 0;">${role.industry || "Career"} · Risk ${Math.round((role.risk_score || 0) * 100)}%</p>
      </div>
    `).join("");
  }
};

const renderReasoningInsights = (payload: AnalysisResult): void => {
  if (!riskInsights) return;
  const reasoning = payload.reasoning || {};
  const cards: string[] = [];

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

  (reasoning.risk_drivers || []).forEach((driver: string, index: number) => {
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
          <p>${reasoning.evidence.map((item: { label?: string; value?: string }) => `${item.label}: ${item.value}`).join(" · ")}</p>
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

const renderModal = (payload: AnalysisResult): void => {
  clearLoadingSkeleton();
  const uniqueRoles = dedupeRoles(payload.top_roles || []);
  if (modalTitle) modalTitle.textContent = payload.mode === "advanced" ? "Deep AI narrative generated" : "Local ML analysis complete";
  if (modalRiskScore) modalRiskScore.textContent = `${Math.round((payload.risk_score || 0) * 100)}%`;
  if (modalRiskLabel) modalRiskLabel.textContent = payload.risk_label ? `${payload.risk_label} risk` : "Risk";
  if (modalMode) modalMode.textContent = `${payload.mode === "advanced" ? "Advanced" : "Standard"} mode`;
  if (resultStatus) resultStatus.textContent = payload.mode === "advanced" ? "Deep AI narrative generated" : "Local ML analysis complete";
  if (narrative) narrative.textContent = payload.cognitive_career_narrative || "";
  updateDashboardResults(payload);
  renderReasoningInsights(payload);

  renderList(rolesList, uniqueRoles, (role) => {
    const openingLinks = buildRoleLinks(role);
    return `
      <div class="list-card pivot-card motion-fade-up">
        <div>
          <strong>${role.job_role || "Role"}</strong>
          <p>${role.industry || "Career"} · Risk ${Math.round((role.risk_score || 0) * 100)}%</p>
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
        <strong>${course.course || "Learning path"}</strong>
        <p>${course.skill || "Skill"} · ${course.reason || "Aligned course recommendation"}</p>
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

const renderError = (message: string): void => {
  clearLoadingSkeleton();
  openModal();
  if (resultBanner) {
    resultBanner.style.background = "rgba(186, 26, 26, 0.08)";
    resultBanner.style.borderColor = "rgba(186, 26, 26, 0.35)";
    resultBanner.style.color = "var(--error)";
  }
  if (modalTitle) modalTitle.textContent = "Assessment could not complete";
  if (modalRiskScore) modalRiskScore.textContent = "--";
  if (modalRiskLabel) modalRiskLabel.textContent = "Error";
  if (modalMode) modalMode.textContent = `${activeMode === "advanced" ? "Advanced" : "Standard"} mode`;
  if (resultStatus) resultStatus.textContent = "Assessment could not complete";
  if (narrative) narrative.textContent = message;
  if (rolesList) rolesList.innerHTML = "";
  if (roadmapList) roadmapList.innerHTML = "";
  if (riasecList) riasecList.innerHTML = "";
  if (dashboardRiskSummary) dashboardRiskSummary.textContent = message;
  if (dashboardRoleStatus) dashboardRoleStatus.textContent = "Error";
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
};

modeButtons.forEach((button) => {
  button.addEventListener("click", () => setMode((button.dataset.mode as AnalysisMode) || "standard"));
});

browseButton.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  selectedFile = fileInput.files?.[0] || null;
  setUploadStatus(describeFile(selectedFile));
  dropZone?.classList.remove("is-dropped");
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

  dropZone.addEventListener("drop", (event: DragEvent) => {
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
  if (selectedFile && !formData.get("resume_file")) formData.set("resume_file", selectedFile);
  formData.set("mode", activeMode);

  const text = (formData.get("resume_text") || "").toString().trim();
  const hasFile = Boolean(fileInput.files && fileInput.files.length > 0);
  if (!hasFile && !text) {
    renderError("Add a resume file or paste resume text before starting the assessment.");
    return;
  }

  setUploadStatus(describeFile(selectedFile || fileInput.files?.[0] || null));
  setBusy(true, activeMode === "advanced" ? "Running advanced analysis..." : "Running local analysis...");

  try {
    const response = await fetch("/api/upload", { method: "POST", body: formData });
    const payload = (await response.json()) as AnalysisResult;
    if (!response.ok || !payload.success) {
      throw new Error(payload.error || "Analysis failed.");
    }
    resetResultStyles();
    renderModal(payload);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Analysis failed.";
    renderError(message);
  } finally {
    setBusy(false);
  }
});

setMode(activeMode);
