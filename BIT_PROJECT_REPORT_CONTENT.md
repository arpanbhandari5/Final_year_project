# GANDAKI UNIVERSITY
## Bachelor of Information Technology

# A PROJECT REPORT ON

# PRAYASH: AN EXPLAINABLE, PRIVACY-CONSCIOUS CAREER INTELLIGENCE PLATFORM

Project work submitted in partial fulfillment of the requirements for the award of the degree of Bachelor of Information Technology

**Submitted by**

1. ______________________________ (Registration No. __________)
2. ______________________________ (Registration No. __________)

**Under the guidance of**

______________________________ (Supervisor Name)

**Faculty of Science and Technology**  
**Gandaki University**  
**2024/2026**

---

# CERTIFICATE

*To be printed on the college letterhead for the final submission. Replace the placeholders with the approved names and dates.*

This is to certify that the project entitled **“Prayash: An Explainable, Privacy-Conscious Career Intelligence Platform”**, submitted by ______________________________ in partial fulfillment of the requirements for the award of the Degree of Bachelor of Information Technology of Gandaki University, is a bona fide work completed under my supervision and, to the best of my knowledge, may be placed before the Examination Board for consideration.

**Panel of Examiners**

External Examiner: ______________________________  
Project Supervisor: ______________________________  
Program Coordinator: ______________________________  
Date: ______________________________

---

# ACKNOWLEDGEMENT

I express my sincere gratitude to Gandaki University, the Faculty of Science and Technology, and the Bachelor of Information Technology program for providing the academic environment and resources required to complete this project. I am especially grateful to my project supervisor, ______________________________, for guidance, review, and constructive feedback throughout the analysis, design, implementation, and testing stages.

I also acknowledge the maintainers of the O*NET occupational information system, scikit-learn, Flask, PyMuPDF, pypdf, python-docx, SQLite, and the open-source software used in this project. Finally, I thank my family, classmates, and all individuals who provided feedback during the development and evaluation of Prayash.

---

# ABSTRACT

Prayash is a web-based career intelligence platform designed to help students and early-career users convert resume information into understandable career-development actions. Existing job and career tools commonly separate resume analysis, occupational exploration, skills-gap identification, and learning recommendations. This project combines these activities in one Flask application. The system accepts pasted resume text and PDF, DOCX, or text files. It extracts text and structured resume information, identifies skills, compares resume language with occupational and job-profile text using TF-IDF vectorization and cosine similarity, estimates contextual automation exposure with a local Ridge regression model, produces career-path and skills-gap suggestions, recommends learning resources from a local course catalogue, and derives a non-diagnostic RIASEC-style interest profile from resume keywords and occupational interest data. The application also provides authentication, OAuth integration points, OTP verification, password reset, administration, feedback, rate limiting, CSRF protection, security headers, optional local Ollama narrative generation, and progressive web application support. The current repository contains a functional baseline, but its generated machine-learning artifacts are not stored in the checkout and must be regenerated before analysis endpoints can operate. After regeneration, the focused test suite completed with 83 passed tests and 2 warnings. The current five-fold evaluation produced MAE 0.2501, RMSE 0.2909, and R² -0.0298 for the automation-exposure target, showing that the target is not sufficiently predictive for personal or employment claims. Therefore, Prayash presents this output as an educational, contextual estimate rather than job-loss, hiring, employability, or individual-probability prediction. The recommended next phase is to preserve the current local and explainable foundation while adding versioned O*NET data, evidence provenance, per-job matching, an application tracker, ordered learning plans, consent controls, calibrated uncertainty, and a stronger validation protocol.

**Keywords:** career intelligence, resume parsing, TF-IDF, cosine similarity, O*NET, skills gap, RIASEC, learning roadmap, Flask, explainable AI, privacy-conscious software.

---

# TABLE OF CONTENTS

The final Word document should generate this table automatically after applying heading styles. The chapter sequence below follows the body of the supplied Gandaki University format. The supplied template contains inconsistent numbering in its sample table of contents; the body pages define the coherent sequence as Chapters 1–5.

- Certificate
- Acknowledgement
- Abstract
- Table of Contents
- List of Figures
- List of Tables
- List of Abbreviations
- List of Symbols
- Chapter 1: Introduction
- Chapter 2: Literature Review
- Chapter 3: Methodology
- Chapter 4: Result and Discussions
- Chapter 5: Conclusions and Recommendations
- References
- Appendix A: API and Route Inventory
- Appendix B: Test Cases and Reproducibility Record
- Appendix C: Implementation Roadmap and Change-Control Plan

---

# LIST OF FIGURES

**Figure 3.1:** Overall system architecture of Prayash  
**Figure 3.2:** Resume-to-recommendation processing flow  
**Figure 3.3:** TF-IDF and cosine-similarity role-matching process  
**Figure 3.4:** Database entity relationship overview  
**Figure 3.5:** User interaction flow for standard and advanced analysis  
**Figure 4.1:** Current test and validation workflow  
**Figure 4.2:** Recommended target product loop: intent → evidence → gap → learning → application → re-analysis

*Figures must be drawn by the project team in the final document. Do not copy diagrams from benchmark websites. The Mermaid specifications in Appendix C may be used as drafting references, but the final report should render them as original diagrams with figure numbers and captions.*

---

# LIST OF TABLES

**Table 1.1:** Project objectives  
**Table 2.1:** Comparison with related systems and benchmarks  
**Table 3.1:** Current project technology stack  
**Table 3.2:** Current data files and their purposes  
**Table 3.3:** Main database entities  
**Table 3.4:** Functional test-case design  
**Table 4.1:** Repository verification status  
**Table 4.2:** Current dataset profile  
**Table 4.3:** Current five-fold model-evaluation result  
**Table 4.4:** Focused automated-test result  
**Table 4.5:** Implemented, partial, and proposed capability matrix  
**Table 5.1:** Prioritized recommendations and acceptance criteria

---

# LIST OF ABBREVIATIONS

| Abbreviation | Meaning |
|---|---|
| AI | Artificial Intelligence |
| API | Application Programming Interface |
| ATS | Applicant Tracking System |
| BLS | Bureau of Labor Statistics |
| CI/CD | Continuous Integration and Continuous Delivery |
| CSP | Content Security Policy |
| CSV | Comma-Separated Values |
| DOCX | Microsoft Word Open XML document format |
| E2E | End-to-End |
| ETL | Extract, Transform, Load |
| GDPR | General Data Protection Regulation |
| HTML | HyperText Markup Language |
| JSON | JavaScript Object Notation |
| LLM | Large Language Model |
| MAE | Mean Absolute Error |
| ML | Machine Learning |
| NLP | Natural Language Processing |
| O*NET | Occupational Information Network |
| OTP | One-Time Password |
| PDF | Portable Document Format |
| PWA | Progressive Web Application |
| RAG | Retrieval-Augmented Generation |
| R² | Coefficient of Determination |
| RIASEC | Realistic, Investigative, Artistic, Social, Enterprising, Conventional |
| RMSE | Root Mean Squared Error |
| SMTP | Simple Mail Transfer Protocol |
| SSE | Server-Sent Events |
| SOC | Standard Occupational Classification |
| TF-IDF | Term Frequency–Inverse Document Frequency |
| UI | User Interface |
| UX | User Experience |

---

# LIST OF SYMBOLS

| Symbol | Meaning |
|---|---|
| `d` | A document or text item |
| `t` | A term/token |
| `TF(t,d)` | Frequency of term `t` in document `d` |
| `IDF(t)` | Inverse document frequency of term `t` |
| `w(t,d)` | TF-IDF weight of term `t` in document `d` |
| `x` | Feature vector |
| `y` | Target value |
| `ŷ` | Predicted value |
| `α` | Ridge regression regularization parameter |
| `n` | Number of observations |
| `sim(a,b)` | Similarity between vectors `a` and `b` |
| `ε` | Error or residual term |

---

# CHAPTER 1: INTRODUCTION

## 1.1 Background

Career planning increasingly requires a person to interpret several kinds of information at the same time. A resume describes previous education, experience, projects, skills, and achievements. An occupation database describes the tasks, skills, work context, interests, education, and related occupations associated with a job. Learning providers describe courses and projects that can close a skills gap. Job-search activity adds another layer of information, including job descriptions, application stages, deadlines, and follow-up actions. When these sources are disconnected, a student may receive a list of possible careers without understanding why a career was suggested or what action should be taken next.

The O*NET system is a relevant public benchmark because its occupational content model organizes information about work and worker characteristics, including skills, tasks, knowledge, abilities, interests, education, experience, job zones, work context, and related occupations. The O*NET database is released periodically and is available for use under its stated license and attribution requirements [1]. The O*NET Interest Profiler measures six occupational-interest areas that correspond to the RIASEC structure: Realistic, Investigative, Artistic, Social, Enterprising, and Conventional [2]. These resources provide a stronger foundation for career exploration than an isolated keyword list.

Prayash was developed as a web-based career intelligence platform for students and early-career users. Its central idea is to transform a resume into a set of understandable outputs: detected evidence, similar occupational profiles, a skills-gap view, learning recommendations, career-path suggestions, and a contextual automation-exposure indication. The system combines deterministic parsing, conventional machine learning, occupational data, and an optional local language-model narrative. The design intentionally keeps the primary analysis local so that the user’s resume does not need to be permanently stored as raw content.

The current repository identifies the system as an application named Prayash. The repository includes Flask routes, templates, static frontend files, Python analysis modules, local CSV datasets, a SQLite storage layer, Docker configuration, and test files. The project’s current checkout is a baseline implementation, not the complete future enhancement roadmap. This distinction is important because the planned features described later in this report are recommendations unless they are implemented, tested, and committed in a later checkpoint.

## 1.2 Statement of Problems

Students and early-career applicants face the following problems:

1. Resume information is unstructured and difficult to compare with occupational requirements.
2. A user may know individual skills but not understand which occupations use those skills together.
3. Existing recommendations may return a course list without identifying which missing skill each course addresses.
4. Career-interest information is often separated from resume evidence and occupation information.
5. A single score can appear authoritative even when the underlying data is noisy or synthetic.
6. Users lack a clear connection between analysis, learning action, targeted resume improvement, and application follow-up.
7. Sensitive resume and account information require privacy, access-control, retention, and deletion safeguards.
8. Commercial platforms provide useful benchmarks, but their proprietary datasets, prompts, scoring, and content cannot simply be copied into an academic project.

The specific technical problem addressed by this project is therefore:

> How can a privacy-conscious web application extract career evidence from a resume, compare it with occupational information using transparent methods, identify skills gaps, and recommend learning actions while explaining the basis and limitations of each result?

The project does not attempt to determine whether a person will be hired, whether an applicant will pass an ATS, or whether a person will lose a job. Its automation-related output is restricted to a contextual estimate associated with the language and occupational evidence available to the local system.

## 1.3 Objectives

### 1.3.1 General objective

To design and develop a web-based career intelligence platform that converts resume information into explainable career exploration, skills-gap, and learning recommendations while preserving a privacy-conscious local analysis foundation.

### 1.3.2 Specific objectives

| No. | Objective |
|---:|---|
| 1 | Accept resume information from pasted text and PDF, DOCX, or text files. |
| 2 | Extract contact details, sections, education, experience, projects, certifications, achievements, and skill evidence. |
| 3 | Normalize and group detected skills for downstream comparison. |
| 4 | Match resume language with occupational profiles using TF-IDF vectors and cosine similarity. |
| 5 | Produce a RIASEC-style interest profile as an exploratory heuristic rather than a diagnosis. |
| 6 | Compare resume skills with a selected target role and identify missing or matched skills. |
| 7 | Recommend learning resources from a local course catalogue. |
| 8 | Provide career-path suggestions and an optional narrative explanation through local Ollama integration. |
| 9 | Provide account, authentication, OTP, password-reset, feedback, and administration functions. |
| 10 | Apply security and privacy controls such as CSRF protection, rate limiting, security headers, and metadata-minimizing storage. |
| 11 | Evaluate the software through automated tests, model evaluation, compilation checks, and reproducible training commands. |
| 12 | Establish a future enhancement path that adds evidence provenance, versioned occupational data, per-job matching, ordered learning plans, and calibrated uncertainty. |

## 1.4 Application Areas

Prayash can be applied in the following areas:

1. **Student career exploration:** A student can upload a resume and inspect possible occupations, interest areas, and learning gaps.
2. **Early-career planning:** A user can identify transferable skills and possible adjacent roles.
3. **Academic advising support:** Advisors can use the application as a conversation aid, provided that outputs are treated as exploratory guidance.
4. **Resume improvement:** Users can inspect missing sections, completeness indicators, and target-role skill gaps.
5. **Learning orientation:** A user can connect a detected or missing skill to a course recommendation.
6. **Career-awareness education:** The platform can demonstrate how text preprocessing, information retrieval, regression, and web application security can be combined in a practical system.
7. **Research prototype development:** The architecture can support future experiments in explainable matching, occupational data provenance, and user-owned career planning.

The current application is not intended to be used for employment selection, automatic rejection, hiring ranking, personal credit decisions, insurance decisions, medical decisions, or official psychological diagnosis.

## 1.5 Scope and Limitations

### 1.5.1 Scope

The current scope includes:

- Flask-based web application and REST-like JSON endpoints.
- Resume parsing for PDF, DOCX, and plain text inputs.
- Resume section and contact extraction.
- Skill extraction and normalized skill grouping.
- TF-IDF-based text representation.
- Cosine-similarity role matching.
- Local Ridge regression for a contextual automation-exposure estimate.
- O*NET-related local skill and interest data files.
- RIASEC-style keyword and interest-profile computation.
- Target-role skills-gap comparison using the local role-skills database.
- Local course catalogue indexing and learning-roadmap generation.
- Career-path suggestions, career chat, streaming analysis, and optional Ollama narrative generation.
- User registration, login, OAuth integration points, OTP verification, password reset, admin, feedback, and health-check routes.
- SQLite storage for users, upload metadata, feedback, OTPs, and password-reset tokens.
- PWA manifest, service worker, offline page, and responsive frontend assets.
- Unit and integration testing files, model training, evaluation scripts, Docker support, and Git checkpoints.

### 1.5.2 Limitations

1. The current checkout does not include a committed `ml_models` directory. The model and course artifacts must be generated with `python train_model.py` before the analysis endpoints can complete.
2. The current automation-risk dataset contains 3,000 rows but only 20 unique job roles. The target has weak predictive signal under the current implementation.
3. The current model evaluation uses a five-fold split but vectorization is performed before the folds, and the model uses fixed `Ridge(alpha=1.2)`. This should be improved with leakage-safe pipelines, baselines, and reproducible metadata before making strong claims.
4. The project’s RIASEC output is inferred from resume keywords and local occupational interests. It is not equivalent to an administered O*NET Interest Profiler assessment.
5. The current role skills database is local and manually defined. It is not yet a complete canonical taxonomy with stable skill IDs, source versions, evidence spans, or market coverage.
6. The local course catalogue is a static data file. It is not a live, provider-verified learning marketplace integration.
7. The system does not yet provide a first-class job-posting, application, resume-version, follow-up, or project-evidence domain.
8. The current SQLite schema stores upload metadata and reasoning JSON but does not provide a complete user-owned history and retention workflow for all future career records.
9. Optional Ollama narrative generation depends on the user’s local Ollama server and selected model. If the service is unavailable, the application must rely on the deterministic local analysis.
10. Current security defaults include development credentials in code/configuration paths and must be hardened before production use.
11. The application has not yet completed a full browser accessibility suite, Lighthouse review, or a formal user study.
12. The current report describes the repository state observed during verification. Any feature added after this checkpoint must be recorded with its commit, tests, data version, and migration details.

## 1.6 Report Structure

Chapter 1 introduces the background, problem, objectives, application areas, scope, and limitations. Chapter 2 reviews the technical and domain foundations, including resume parsing, information retrieval, TF-IDF, cosine similarity, Ridge regression, O*NET, RIASEC, explainable AI, privacy, and related systems. Chapter 3 explains the methodology, system architecture, data flow, algorithms, database design, tools, performance measures, and test cases. Chapter 4 presents the current implementation results, dataset profile, model evaluation, automated-test results, limitations, and discussion against the objectives. Chapter 5 concludes the report and gives prioritized recommendations for the next implementation phases. The appendices provide the route inventory, reproducibility record, test cases, and controlled enhancement roadmap.

---

# CHAPTER 2: LITERATURE REVIEW

## 2.1 Resume Parsing and Structured Evidence Extraction

A resume is a semi-structured document. It may contain headings, paragraphs, lists, dates, contact information, hyperlinks, tables, and formatting cues. A parser therefore performs more than plain text conversion. It must extract readable text, identify document sections, detect entities such as email addresses and links, normalize skill phrases, and retain enough evidence to explain where an extracted item came from.

Prayash uses PyMuPDF when available for PDF extraction and layout information, with pypdf as a fallback. It also uses python-docx for DOCX processing and supports plain text. Its parser includes contact extraction, section detection, skills extraction, enhanced parsing, and resume-quality analysis. This is appropriate for a project prototype because it separates document handling from the downstream career-intelligence pipeline.

A limitation of keyword extraction is that the same concept can be expressed in several forms. For example, `JS`, `JavaScript`, and `Java Script` may refer to the same skill, while a short token such as `R` can create false positives. A stronger future parser should preserve both the raw phrase and canonical form, store its section and character span, attach an extraction confidence, and allow the user to correct it. The correction should not silently rewrite the original evidence.

## 2.2 Information Retrieval, TF-IDF, and Cosine Similarity

Information retrieval represents documents in a form that allows a query to be compared with a collection of documents. TF-IDF assigns a larger weight to terms that are frequent in a document but less common across the collection. A common formulation is:

\[
TFIDF(t,d)=TF(t,d)\times IDF(t)
\]

where `TF(t,d)` represents the frequency of term `t` in document `d`, and inverse document frequency reduces the influence of terms that appear in many documents. scikit-learn’s `TfidfVectorizer` converts raw documents into a TF-IDF feature matrix. With L2 normalization, the dot product of two vectors is equivalent to cosine similarity [3].

Cosine similarity between vectors `a` and `b` is:

\[
\cos(\theta)=\frac{a\cdot b}{||a||\,||b||}
\]

A value closer to 1 indicates greater directional similarity, while a value closer to 0 indicates weak overlap. Prayash uses this idea to compare resume text with job-profile text and O*NET-related profile text. This is a suitable transparent baseline because its behavior can be inspected through vocabulary, matching terms, and similarity values.

TF-IDF is not semantic understanding. It can miss synonyms, abbreviations, context, negation, and transferable meaning. It can also overvalue repeated generic words. Consequently, future versions should retain TF-IDF as a transparent baseline while adding canonical skill linking and, only where justified, semantic similarity. Any semantic model should be evaluated against the baseline rather than replacing it without evidence.

## 2.3 Ridge Regression for Contextual Automation Exposure

Ridge regression is a linear regression method with L2 regularization. It minimizes a combination of squared residual error and a penalty on coefficient magnitude:

\[
\min_{w}\left(||y-Xw||^2_2+\alpha||w||^2_2\right)
\]

The parameter `α` controls the strength of shrinkage. A larger value reduces coefficient magnitude and can make a model less sensitive to noisy, high-dimensional features. In Prayash, a TF-IDF vector is passed to a Ridge model whose target is a value clipped to the interval 0 to 1 and labelled as an automation-risk score in the current baseline.

The current implementation should not be interpreted as a validated personal prediction. The target is occupational and dataset-dependent, while the input is a resume. This creates a level mismatch: an occupation-level label is applied to an individual’s text. The result should therefore be described as a contextual estimate associated with the closest available occupational evidence. The proposed enhancement is to rename the display concept to **automation exposure** or **task exposure**, return component evidence, add an insufficient-evidence state, and report the target definition and dataset version.

## 2.4 O*NET Occupational Information

O*NET is a major benchmark for occupational intelligence. Its database contains information on occupations, tasks, skills, abilities, knowledge, work activities, work context, interests, job zones, education, experience, technologies, titles, and related occupations [1]. Its content model is useful because it distinguishes different dimensions of a job rather than reducing an occupation to a single label.

The current repository contains local O*NET-related CSV files for skills, interests, and interest keywords. These files are used to create occupational profile text and interest associations. The current pipeline does not yet constitute a full versioned O*NET occupation-information system. The recommended enhancement is to import an approved release with stable O*NET-SOC codes, alternate titles, tasks, skills, technologies, education, job zones, related occupations, source dates, and licence attribution.

A versioned occupation layer would make recommendations reproducible. It would also allow the user to distinguish official occupational facts from local model estimates, resume evidence, external labor-market facts, and generated narrative. The report should never imply that a local CSV is the complete O*NET OnLine product.

## 2.5 RIASEC and Occupational Interests

Holland’s RIASEC framework groups vocational interests into six areas: Realistic, Investigative, Artistic, Social, Enterprising, and Conventional. The O*NET Interest Profiler uses these six areas and is designed for career exploration and educational planning [2]. The official tool is based on self-assessment responses rather than the automatic interpretation of a resume.

Prayash implements a RIASEC-style heuristic. It counts selected resume keywords such as analysis, design, collaboration, leadership, process, or documentation and combines them with occupational interest information from local data. This can provide a useful conversation prompt, but it must not be described as a psychological diagnosis or an official Interest Profiler score. A future version should separate self-reported interest responses from inferred resume-language signals and label both methods clearly.

## 2.6 Learning Recommendations and Skills-Gap Analysis

Skills-gap analysis compares the skills visible in a user’s evidence with the skills associated with a selected target role. A useful result should distinguish skills that are matched, missing, preferred, transferable, or ambiguous. It should show the resume evidence used for a match and should allow user correction.

The current Prayash implementation includes a local role-to-skills dictionary and a course index constructed from `coursera_catalog.csv`. Its current learning-roadmap logic uses matching role skills first and detected resume keywords as a fallback. It returns course title, URL, short introduction, provider, and level when available. This is a strong baseline for an offline prototype, but a flat course list is not yet a prerequisite-aware learning plan. The proposed enhancement adds a canonical skill registry, prerequisite graph, ordered plan items, project evidence, progress events, credentials, and re-analysis after progress.

The project should not scrape or copy commercial course content. Provider names and links should be used only according to their terms, and any future commercial integration should be implemented through an authorized adapter.

## 2.7 Explainable and Responsible AI

A career tool affects a user’s decisions and self-perception. It should therefore explain the evidence behind an output, identify uncertainty, and avoid unsupported claims. NIST’s AI Risk Management Framework emphasizes managing risks to individuals, organizations, and society and incorporating trustworthiness considerations into the design, development, use, and evaluation of AI systems [4]. The OECD AI Principles also highlight transparency and responsible disclosure when people interact with AI systems [5].

For Prayash, explainability means showing detected evidence, similarity components, source and version, limitations, and the difference between fact and inference. A generated narrative must not be treated as an authoritative source. If the system has insufficient evidence, it should abstain or ask the user for clarification rather than produce a confident-looking result.

The automation-exposure output is especially sensitive. The present evaluation produces an R² below zero, which means that the model does not explain useful variance beyond the baseline under the current procedure. The responsible interpretation is to treat the value as an experimental, contextual estimate and not as a probability of job loss or an employment decision.

## 2.8 Privacy and Web Application Security

Resumes can contain names, contact details, education histories, employment histories, links, and other personal information. The current project’s privacy-first design attempts to process resume text in memory and store upload metadata, risk information, and reasoning JSON rather than permanent raw resume content. This reduces exposure, but the system still requires careful handling of logs, prompts, error messages, backups, account data, and future history features.

The application includes password hashing, login management, OTP records, password-reset tokens, CSRF-related routes, rate-limiting helpers, security headers, and OAuth integration points. The current production risks include default credentials, configuration defaults, optional external model flows, and the need for more complete per-user authorization tests. Before the application stores job descriptions, conversations, editable resumes, or learning progress, it should implement consent, retention, export, deletion, audit events, and ownership checks.

## 2.9 Related Works and Benchmark Comparison

| Capability | Prayash current baseline | Benchmark or reference | Gap and responsible response |
|---|---|---|---|
| Resume input | PDF, DOCX, text, and pasted text | Jobscan, Teal | Add editable evidence spans and job-linked resume versions. |
| Skill extraction | Local extraction and normalization | LinkedIn Skills Match, Lightcast | Build a public/licensed canonical registry; do not copy Lightcast data. |
| Career matching | TF-IDF similarity and local O*NET-related data | O*NET OnLine, My Next Move | Add stable O*NET-SOC mappings, task/skill/technology/education fields, and provenance. |
| Career interests | RIASEC-style heuristic | O*NET Interest Profiler | Separate self-assessment from resume inference and label the method. |
| Automation signal | Local Ridge estimate | Research/dashboard tools | Use contextual task exposure, not job-loss prediction; audit target quality. |
| Learning | Local course catalogue and roadmap | Coursera Career Academy, LinkedIn Learning | Add ordered plans, prerequisites, projects, evidence, and provider-neutral metadata. |
| Coaching | Local RAG chat and optional Ollama narrative | ChatGPT-style career coaches | Ground answers in evidence and sources; keep external use opt-in. |
| Accounts | Login, signup, OAuth integration points, OTP, reset, admin, feedback | Standard SaaS patterns | Harden production defaults and add ownership/lifecycle controls. |
| Data storage | SQLite with upload metadata and account records | Privacy-first platforms | Add retention, export, deletion, audit, backups, and database migration discipline. |
| Job workflow | Not yet a first-class domain | Teal and similar trackers | Add manual job capture, application stages, follow-ups, resume versions, and snapshots. |

The comparison identifies design inspiration, not permission to copy proprietary features or content. The strongest differentiation for Prayash should be explainability, local-first processing, source provenance, and a coherent evidence-to-action loop.

---

# CHAPTER 3: METHODOLOGY

## 3.1 Methodology Background

The project follows an iterative software-engineering and applied-machine-learning methodology. The system is developed as a modular Flask application. The work is separated into requirements analysis, data inspection, parser implementation, ML pipeline construction, web integration, security implementation, testing, evaluation, and controlled future enhancement.

The current implementation uses a local data pipeline rather than a continuously connected commercial API. This choice improves reproducibility and limits external data exposure. It also creates a responsibility to document data versions, schema assumptions, generated artifact status, and known limitations.

The agreed future implementation sequence uses a checkpoint after every green test gate:

1. Baseline and inventory.
2. Production and security hardening.
3. ML reproducibility and honest evaluation.
4. Career intent and editable evidence.
5. Manual job and application workflow.
6. Versioned O*NET occupation intelligence.
7. Canonical skills and ordered learning path.
8. Grounded coaching and text practice.
9. UI/UX and accessibility quality pass.

Only the features visibly present in the current repository should be called implemented in this report. The sequence above is a controlled roadmap, not a claim that all phases have already been completed.

## 3.2 Overall System Architecture

Prayash follows a layered architecture:

1. **Presentation layer:** Jinja templates, HTML, CSS, JavaScript, PWA assets, forms, dashboards, and streamed analysis updates.
2. **Application layer:** Flask routes for authentication, uploads, analysis, skills gaps, career paths, learning roadmaps, chat, feedback, administration, and health checks.
3. **Parsing layer:** PDF, DOCX, and text extraction, section detection, contact extraction, skill extraction, and quality analysis.
4. **Intelligence layer:** TF-IDF vectorization, cosine similarity, Ridge regression, local role and skill comparison, RIASEC heuristic, course indexing, and optional Ollama narrative generation.
5. **Persistence layer:** SQLAlchemy models backed by SQLite for users, uploads, feedback, OTPs, and password-reset tokens.
6. **Deployment layer:** Python startup scripts, Dockerfile, Docker Compose, environment configuration, generated model artifacts, and a health check.

**Figure 3.1** should show these layers as boxes with arrows from browser → Flask routes → parser/analysis → storage and response.

## 3.3 Generic Processing Model

The processing model is:

\[
Input \rightarrow Validation \rightarrow Extraction \rightarrow Normalization \rightarrow Feature\ Representation \rightarrow Matching/Scoring \rightarrow Explanation \rightarrow Action\ Recommendations
\]

The user can submit either pasted text or an uploaded file. The application validates the request, extracts text, cleans it, and sends it through the analysis workflow. The workflow calls `assess_resume`, adds guided next steps and support resources, records upload metadata, and returns JSON to the frontend. In advanced mode, the deterministic local analysis is followed by an optional Ollama narrative request.

## 3.4 Resume Parsing Algorithm

### Inputs

- Uploaded PDF, DOCX, or text file; or pasted resume text.
- File type and filename.
- Optional analysis mode: standard or advanced.

### Processing steps

1. Validate that a file or text has been submitted.
2. For PDF input, attempt PyMuPDF extraction.
3. If PyMuPDF fails or is unavailable, use pypdf.
4. For DOCX input, read document paragraphs and available text.
5. For text input, use the submitted text directly.
6. Normalize whitespace and remove extraction noise.
7. Detect likely sections such as education, experience, projects, and skills.
8. Extract contact information using regular expressions and link patterns.
9. Extract and normalize skill phrases.
10. Calculate completeness or resume-quality signals.
11. Pass the cleaned text and structured evidence to the intelligence layer.

### Pseudocode

```text
FUNCTION parse_resume(input):
    IF input is uploaded file:
        IF extension is PDF:
            text = extract_with_pymupdf(input)
            IF text is empty:
                text = extract_with_pypdf(input)
        ELSE IF extension is DOCX:
            text = extract_docx(input)
        ELSE:
            text = extract_plain_text(input)
    ELSE:
        text = input.pasted_text

    text = clean_text(text)
    sections = detect_sections(text)
    contacts = extract_contact_info(text)
    skills = extract_skills_from_text(text)
    quality = analyze_resume_quality(sections, contacts, skills)
    RETURN {text, sections, contacts, skills, quality}
```

## 3.5 TF-IDF and Role-Matching Algorithm

The training script builds text from the local automation dataset, resume corpus, O*NET-related skill data, interest data, and interest keywords. A `TfidfVectorizer` with unigrams and bigrams, English stop-word removal, and a maximum of 7,000 features is fitted on the combined corpus in the current baseline. Job vectors and occupational cluster vectors are stored in a generated model bundle.

At analysis time, the resume is transformed using the same vectorizer. The application calculates the dot product between the normalized resume vector and stored job/profile vectors, ranks the values in descending order, and returns the top matches.

```text
FUNCTION match_roles(resume_text, model_bundle):
    resume_vector = vectorizer.transform([resume_text])
    similarities = dot(job_vectors, transpose(resume_vector))
    indices = argsort(similarities, descending=True)
    FOR each selected index:
        return job profile plus similarity
    RETURN ranked matches
```

The current result is lexical similarity. It is not a guarantee that a user is qualified for the occupation. The future per-job matcher should add required/preferred skill types, evidence spans, direct role-name evidence, canonical aliases, match methods, and confidence/abstention behavior.

## 3.6 Contextual Automation-Exposure Algorithm

The current baseline uses a Ridge regression model trained on TF-IDF job vectors and the `automation_risk_score` target. The prediction is clipped to 0–1 and mapped to a low, moderate, or higher band using utility thresholds. The result is stored as part of the reasoning response.

The current model should be interpreted as:

- A local text-based estimate.
- Dependent on the local dataset and model artifact.
- Not a personal probability.
- Not a job-loss prediction.
- Not a hiring, employability, or ATS score.

The recommended replacement output is a structured evidence object containing resume-language signal, closest-role signal, skill-role similarity, confidence, model version, dataset version, limitations, and an `insufficient_evidence` status where appropriate.

## 3.7 RIASEC-Style Interest Algorithm

The current implementation defines six keyword groups. It counts matching keywords in the normalized resume text and adds weighted contributions from the top occupational clusters. The six groups are Realistic, Investigative, Artistic, Social, Enterprising, and Conventional. The system sorts the scores and returns primary, secondary, and tertiary types.

This algorithm is an exploratory heuristic. A future self-assessment should collect direct responses and calculate a separate profile. The interface must show which method generated the result.

## 3.8 Skills-Gap Algorithm

The current role-skills database maps roles such as Data Scientist, Data Analyst, Software Engineer, Machine Learning Engineer, Frontend Developer, Backend Developer, Full Stack Developer, DevOps Engineer, Product Manager, UX Designer, Data Engineer, Cybersecurity Analyst, Cloud Architect, Mobile Developer, Technical Writer, and QA Engineer to lists of skills.

The skills-gap procedure is:

1. Validate resume text and target role.
2. Normalize resume text and the target role.
3. Retrieve the required skill list for the role.
4. Detect whether each skill appears in the resume text.
5. Partition skills into matched and missing sets.
6. Return a structured result for the UI.

A later version should use canonical skill IDs, aliases, word boundaries, evidence spans, ambiguity handling, confidence, and user correction. For example, `JS` may map to JavaScript, but `R` must not be matched inside unrelated words.

## 3.9 Learning-Roadmap Algorithm

The current course-index builder reads the local course catalogue and creates a dictionary from skill tokens to courses. It stores title, URL, short introduction, provider, and level. Duplicate course titles are removed and the number of entries per token is bounded.

At recommendation time, the system first examines skills from the top role matches, then falls back to top detected resume keywords. It returns a limited list of courses with a skill and reason. This approach is simple, fast, and suitable for an offline prototype.

A future roadmap should sequence items by prerequisites and distinguish a course recommendation from verified completion. Completion should be entered by the user or verified by an authorized provider. A link click is not proof of mastery.

## 3.10 Database and Storage Design

The current SQLAlchemy storage layer contains the following principal entities:

| Entity | Purpose |
|---|---|
| `User` | Email, username, name, password hash, role, activation, verification, timestamps, and last login. |
| `Upload` | Filename, file type, mode, risk score, risk label, reasoning JSON, user link, and timestamp. |
| `Feedback` | User or upload reference, rating, message, and timestamp. |
| `VerificationOTP` | Email, purpose, code, expiration, use state, attempts, and timestamp. |
| `PasswordResetToken` | User reference, token, expiration, use state, and timestamp. |

The current privacy design aims not to store the full raw resume permanently. However, `reasoning_json` can contain output derived from a resume, so it still requires careful privacy review. Future entities should include explicit ownership and lifecycle fields for career goals, evidence items, job postings, applications, resume versions, analysis snapshots, learning plans, progress events, project evidence, credentials, tasks, contacts, and audit events.

**Figure 3.4** should show the current entities first and a separate dashed extension for future user-owned records.

## 3.11 API and Interface Design

Important current endpoints include:

- `/` for the landing page.
- `/login`, `/signup`, `/verify-otp`, `/forgot-password`, and password-reset routes.
- `/workspace` and `/workspace/skills-gap` for authenticated workspace pages.
- `/api/upload` and `/api/analyze` for resume analysis.
- `/api/analyze-stream` for Server-Sent Events analysis progress.
- `/api/skills-gap/roles` and `/api/skills-gap/analyze` for target-role gap analysis.
- `/api/career-paths` for career-path suggestions.
- `/api/learning-roadmap` for learning recommendations.
- `/api/career-chat` and `/api/career-chat/stream` for conversational support.
- `/api/insights-summary` and `/api/compare` for additional analysis views.
- `/api/feedback` for feedback.
- `/api/rag-status` and `/healthz` for operational status.
- `/admin` and `/api/admin/users` for administrative functions.

The frontend uses server-rendered templates with vanilla HTML, CSS, and JavaScript. The current design direction includes glassmorphism styling, Inter font, dark-mode support, animations, PWA assets, and offline support. The recommended UI/UX improvement is not to add visual effects indiscriminately. It is to establish a clear sequence: career goal, evidence profile, skills gap, learning path, applications, coaching, and privacy settings. Every major screen should show one clear next action, source/version/confidence metadata, loading states, error states, and accessible text alternatives.

## 3.12 Tools and Platform

| Layer | Current tool |
|---|---|
| Backend framework | Flask 3.x |
| Authentication | Flask-Login, Flask-Dance integration points |
| Database | SQLite with SQLAlchemy |
| Form/security support | Flask-WTF and application security helpers |
| Machine learning | scikit-learn, NumPy, pandas, joblib |
| Text processing | Regular expressions, normalization utilities, TF-IDF |
| Resume files | PyMuPDF, pypdf, python-docx |
| Optional local narrative | Ollama HTTP API with Llama 3 configuration |
| Frontend | HTML, CSS, vanilla JavaScript, Jinja templates |
| PWA | Web manifest, service worker, offline fallback |
| Deployment | Dockerfile and Docker Compose |
| Testing | pytest test files and standalone authentication scripts |
| Version control | Git and GitHub branches/tags |

The development workflow should use VS Code, Python, Git, focused tests, and a checkpoint tag after every phase. Free supporting tools include Playwright, axe-core, Lighthouse, Ruff, Bandit, pip-audit, Continue, Ollama, and Aider. These are development tools and should not be presented as runtime features of Prayash.

## 3.13 Current Data Files

| File | Current observation | Purpose |
|---|---:|---|
| `automation_risk.csv` | 3,000 rows, 25 columns, 20 unique job roles, 425 missing cells | Local contextual exposure target and job features. |
| `resume_corpus.csv` | 9,544 rows, 35 columns, 101,704 missing cells | Resume text and structured resume-corpus fields. |
| `coursera_catalog.csv` | 8,092 rows, 45 columns, 252,255 missing cells | Local course catalogue used for recommendations. |
| `onet_interests.csv` | 8,307 rows read as one tab-separated column in the current inspection | Local O*NET-related interest data; delimiter/schema must be verified. |
| `onet_skils.csv` | 44,700 rows read as one tab-separated column in the current inspection | Local O*NET-related skills data; delimiter/schema must be verified. |
| `onet_interest_keywords.csv` | 75 rows read as one tab-separated column in the current inspection | Local interest keywords; delimiter/schema must be verified. |

The one-column observation for the three O*NET-related files is a reproducibility warning. The application’s `read_csv_any` utility may apply delimiter handling at runtime, but this should be explicitly tested and documented. The final report should include a data dictionary and a checksum for every production dataset.

## 3.14 Performance Parameters

### Software performance

- API response time for standard analysis.
- Advanced-mode latency when Ollama is enabled.
- File parsing time by format and file size.
- Memory used by the model and course index.
- Streaming progress responsiveness.
- Health-check response time.

### Machine-learning performance

For the current regression target:

\[
MAE=\frac{1}{n}\sum_{i=1}^{n}|y_i-\hat{y}_i|
\]

\[
RMSE=\sqrt{\frac{1}{n}\sum_{i=1}^{n}(y_i-\hat{y}_i)^2}
\]

\[
R^2=1-\frac{\sum_{i=1}^{n}(y_i-\hat{y}_i)^2}{\sum_{i=1}^{n}(y_i-\bar{y})^2}
\]

MAE and RMSE are lower-is-better error measures, while R² is usually higher-is-better. scikit-learn documents these regression metrics and recommends validation strategies that prevent a single split from being mistaken for general performance [6]. The report should compare the model with mean, median, role-group, and industry-group baselines in the enhanced implementation.

### Information-retrieval performance

For role matching and skill linking, the planned measures are:

- Top-1 and Top-3 role accuracy on labelled examples.
- Precision, recall, and F1 for skill extraction and canonical linking.
- Mean reciprocal rank for ordered role recommendations.
- Coverage and abstention rate for low-evidence cases.
- Calibration error for any confidence value presented as a probability-like quantity.

### Product and safety performance

- Percentage of users who define a target role.
- Percentage reaching a first recommended action.
- Skill-gap helpfulness rating.
- Learning-path start and completion rate.
- Follow-up completion rate.
- Correction rate for extracted skills and roles.
- Export and deletion success.
- Accessibility violations and keyboard-navigation coverage.

## 3.15 Test-Case Design

| Test ID | Scenario | Expected result |
|---|---|---|
| TC-01 | Landing page request | HTTP 200 and expected page content. |
| TC-02 | Signup with valid input | User is created and verification flow begins. |
| TC-03 | Duplicate email or username | Request is rejected without duplicate record. |
| TC-04 | Weak password | Password validation gives a clear error. |
| TC-05 | OTP verification | Valid, unexpired OTP verifies the account. |
| TC-06 | Expired or incorrect OTP | Verification fails and attempt limits apply. |
| TC-07 | Password reset | Valid reset flow changes password safely. |
| TC-08 | Resume analysis without artifact | Application returns a controlled error rather than a false result. |
| TC-09 | Resume analysis after artifact generation | Standard analysis returns success and result fields. |
| TC-10 | SSE analysis | Response has `text/event-stream` and a complete event after successful analysis. |
| TC-11 | PDF/DOCX/text parsing | Text is extracted or a controlled validation error is returned. |
| TC-12 | Skills-gap request without target role | HTTP 400 with validation message. |
| TC-13 | Valid skills-gap request | Matched and missing skills are returned. |
| TC-14 | Career-path request with short text | HTTP 400 with minimum-length message. |
| TC-15 | Learning-roadmap request | Roadmap and total duration fields are returned. |
| TC-16 | Feedback request | Feedback is stored with permitted user/upload references. |
| TC-17 | Admin route without admin role | Access is denied. |
| TC-18 | Rate-limited route | Excessive requests are controlled. |
| TC-19 | Cross-user access | A user cannot read or mutate another user’s records. |
| TC-20 | Production configuration | Missing secrets do not silently activate insecure defaults. |

The current test suite covers many authentication, application, email, OTP, and route behaviors. TC-08 is intentionally expected to fail until model artifacts are generated or a test fixture supplies them. TC-19 and TC-20 should be expanded before production-like storage is introduced.

---

# CHAPTER 4: RESULT AND DISCUSSIONS

## 4.1 Overview

This chapter reports what was verified in the current repository. It does not treat the enhancement roadmap as completed functionality. The checkout was on branch `develop/final-year-enhancement` at commit `b06d932`, tagged `checkpoint-low-cost-coding-plan-complete`, with the planning and audit documents committed. The source implementation still contains the baseline `Ridge(alpha=1.2)` and 7,000-feature TF-IDF configuration described in the ML audit. The newer RidgeCV, metadata, hybrid-score, alias, and explainability improvements are recommendations or changes from another working copy unless they are subsequently merged and re-tested.

## 4.2 Repository Verification Status

| Verification item | Result | Discussion |
|---|---|---|
| Git branch | Passed | `develop/final-year-enhancement` tracks the remote branch. |
| Python compilation before artifact generation | Passed | `python -m compileall -q .` returned exit code 0. |
| Initial full pytest collection | Blocked | Standalone authentication scripts require a running server at `127.0.0.1:5000`. |
| Initial focused tests | 81 passed, 2 failed | Two failures were caused by absent model artifacts. |
| Model training after dependencies were installed | Passed | `python train_model.py` created `model.pkl` and `courses.pkl`. |
| Model evaluation | Passed | Five-fold metrics were printed successfully. |
| Focused tests after artifact generation | 83 passed, 2 warnings | `tests/test_app.py`, `tests/test_email_service.py`, and `tests/test_forgot_password_otp.py` passed. |
| Full standalone E2E tests | Not claimed | They must be run with the Flask server started separately. |

The two warnings were deprecation warnings related to `datetime.utcnow()` in Flask-Login. They do not fail the current tests but should be addressed during dependency and compatibility maintenance.

## 4.3 Dataset Results

| Dataset | Rows | Columns | Key observation |
|---|---:|---:|---|
| `automation_risk.csv` | 3,000 | 25 | Only 20 unique job roles; 425 missing cells. |
| `resume_corpus.csv` | 9,544 | 35 | Large resume corpus; 101,704 missing cells. |
| `coursera_catalog.csv` | 8,092 | 45 | Broad catalogue; 252,255 missing cells. |
| `onet_interests.csv` | 8,307 | 1 in raw inspection | Delimiter/schema handling must be verified. |
| `onet_skils.csv` | 44,700 | 1 in raw inspection | Filename is `skils`; delimiter/schema handling must be verified. |
| `onet_interest_keywords.csv` | 75 | 1 in raw inspection | Delimiter/schema handling must be verified. |

The 20-role limitation is particularly important for automation-exposure modelling. A dataset with many rows but few unique roles may contain repeated or near-repeated occupational patterns. The next evaluation should measure exact duplicates, near duplicates, within-role variance, between-role variance, and group-aware train/test separation.

## 4.4 Current Model-Evaluation Result

After generating the current model artifacts, the repository’s evaluation script produced:

| Metric | Five-fold mean |
|---|---:|
| MAE | 0.2501 |
| RMSE | 0.2909 |
| R² | -0.0298 |

The negative R² indicates that the current model performs worse than the mean-prediction reference under this evaluation procedure. This is not evidence that the software is unusable as a demonstration of a pipeline. It is evidence that the target is not sufficiently predictable from the current text representation and dataset. The system must therefore avoid claims such as “the model predicts a user’s probability of job loss.”

The correct interpretation is:

> The current model generates a local, contextual estimate based on text patterns in the available data. Its evaluation does not support a personal employment or job-loss prediction.

The evaluation script also has a methodological limitation: it fits the vectorizer before splitting the job vectors into folds. The vocabulary is therefore influenced by the full corpus. The future implementation should fit preprocessing inside each fold through a scikit-learn `Pipeline`, report baselines, and use grouped splits where occupation duplication is present.

## 4.5 Focused Automated-Test Result

After the model artifacts were generated, the focused suite completed:

- **83 tests passed.**
- **2 deprecation warnings were reported.**
- The standalone authentication scripts were not included in this focused result because they expect a running server during collection.
- Before artifact generation, two analysis tests failed because `model.pkl` and `courses.pkl` were absent.

The artifact dependency is a reproducibility issue rather than a reason to conceal the test failure. The project should add a test fixture that creates temporary artifacts or run `train_model.py` as a documented setup step. A test that depends silently on untracked binary files is fragile for another developer or evaluator who clones the repository.

## 4.6 Functional Results Against Objectives

| Objective | Current status | Evidence and discussion |
|---|---|---|
| Accept multi-format resumes | Implemented baseline | `resume_parser.py` includes PDF, DOCX, text, PyMuPDF, pypdf, and layout helpers. |
| Extract resume evidence | Implemented baseline | Contact, sections, skills, and quality functions are present. |
| Normalize skills | Implemented baseline | Local normalization and category logic are present; canonical registry is future work. |
| Match occupations | Implemented baseline | TF-IDF vectors and cosine-like dot products rank job profiles. |
| Generate skills gaps | Implemented baseline | Target-role routes and local role-skills database are present. |
| Suggest career paths | Implemented baseline | `/api/career-paths` and recommendation helpers are present. |
| Provide learning roadmap | Implemented baseline | Local course index and `/api/learning-roadmap` are present. |
| Produce RIASEC-style profile | Implemented heuristic | Keyword and cluster-based profile is present; it is not official assessment. |
| Provide automation signal | Implemented baseline | Ridge score is present but weakly predictive and requires cautious naming. |
| Provide narrative support | Optional | Ollama route is optional and requires a local model service. |
| Provide accounts/admin | Implemented baseline | Authentication, roles, OTP, reset, admin, feedback, and OAuth integration points exist. |
| Provide privacy-first storage | Partial | Upload metadata is stored, but lifecycle and future record controls need hardening. |
| Provide job/application workflow | Not yet implemented as a first-class domain | Recommended P0 feature. |
| Provide full O*NET occupation pages | Partial | Local O*NET-related files exist, but full versioned import and provenance are future work. |
| Provide ordered evidence-backed learning | Partial | Roadmap exists, but prerequisite/progress/evidence ledger is future work. |

## 4.7 Discussion of UI/UX and Frontend Direction

The current project already contains a visual foundation: base templates, dashboards, glassmorphism styling, dark-mode-related behavior, animations, a PWA manifest, a service worker, and an offline page. This is a useful starting point. The main UX problem is not the absence of visual effects. It is the absence of a complete user-owned progression loop.

The recommended information architecture is:

1. Dashboard: current goal, current progress, one next action, and follow-up.
2. Career Goal: target role, alternative roles, location, seniority, and constraints.
3. Evidence Profile: resume versions, extracted skills, evidence spans, and corrections.
4. Skill Gaps: required and preferred skills with supporting evidence.
5. Learning Path: ordered courses, projects, prerequisites, and progress.
6. Applications: saved jobs, resume versions, stages, contacts, tasks, and follow-ups.
7. Career Coach: source-linked chat and text interview practice.
8. Settings and Privacy: consent, retention, export, deletion, and integrations.

Free compatible tools include Motion One or the native Web Animations API for lightweight animation, Animate.css for small CSS-only effects, AutoAnimate for list transitions, Lottie for carefully selected vector illustrations, Lucide icons, Alpine.js or HTMX for small server-rendered interactions, Tailwind or Open Props if a deliberate styling migration is approved, Playwright for browser tests, axe-core for accessibility, and Lighthouse for performance review. These tools should be added incrementally. The project should not introduce React solely to use Framer Motion when the current application is Flask, Jinja, and vanilla JavaScript.

## 4.8 Security and Privacy Discussion

The baseline contains meaningful security features, but a production release requires additional work. The following issues are documented in the project playbook:

1. Default admin and student credentials must not be used in production.
2. `FLASK_SECRET_KEY`, database configuration, admin credentials, OAuth secrets, and mail secrets must be required or clearly separated by environment.
3. Debug mode and insecure OAuth transport must be development-only.
4. Resume, token, password, and prompt content must not be written to logs.
5. User-generated or model-generated content must be rendered safely; unsafe `innerHTML` patterns require review.
6. Every future record and route must enforce per-user ownership.
7. External Ollama or any future OpenRouter/LLM route must be opt-in and documented.
8. Retention, export, deletion, backup, and restore behavior must exist before storing larger career histories.
9. Model artifacts and data releases must be versioned so that an old analysis can be interpreted later.

## 4.9 Interpretation of the Results

The project has a credible final-year-project baseline because it integrates multiple areas: document processing, natural-language representation, machine learning, occupational data, web development, authentication, and user-facing recommendations. Its strongest technical qualities are modularity, transparent text similarity, local processing, multiple input formats, and a practical end-to-end workflow.

The most important weakness is not the lack of a more complex model. It is the quality and alignment of the automation target and the lack of a source-versioned occupational foundation. The current evaluation makes this clear. Improving the model should begin with target auditing, deduplication, stable occupation identifiers, better labels, leakage-safe validation, and abstention—not with a deeper neural network selected only because it produces a more impressive score.

The highest-value product enhancement is a traceable loop:

\[
Intent \rightarrow Target\ Role \rightarrow Resume\ Evidence \rightarrow Skill\ Gap \rightarrow Ordered\ Learning \rightarrow Application\ Action \rightarrow Re-analysis
\]

This loop would make the system more useful while preserving the existing strengths.

---

# CHAPTER 5: CONCLUSIONS AND RECOMMENDATIONS

## 5.1 Conclusions

Prayash demonstrates how a Flask web application can combine resume parsing, information retrieval, regression, occupational data, interest profiling, learning recommendation, account management, and local narrative assistance in one career-intelligence prototype. The current system accepts several resume formats, extracts useful information, provides similarity-based role suggestions, performs skills-gap analysis, recommends local learning resources, offers career-path suggestions, and includes a broad account and security foundation.

The project is technically defensible when its outputs are described honestly. TF-IDF and cosine similarity provide a transparent baseline for matching text. Ridge regression provides a compact demonstration of supervised learning on sparse text features. The RIASEC-style output provides an exploratory interpretation of resume language. The local course index demonstrates how recommendations can be connected to skills. The Flask application demonstrates API design, asynchronous streaming, authentication, storage, PWA support, and deployment configuration.

The current evaluation also demonstrates the importance of responsible interpretation. The automation-exposure model produced MAE 0.2501, RMSE 0.2909, and R² -0.0298 under the current five-fold script. These results do not support a personal or employment prediction. The output should remain a contextual educational estimate until a better target, stable occupation mapping, and stronger validation protocol exist.

The current repository can be reproduced after installing requirements and running `python train_model.py` to generate the model artifacts. After this step, the focused test suite completed with 83 passed tests and two deprecation warnings. The full standalone authentication scripts require a separately running application server and should be documented and automated in a future test workflow.

## 5.2 Future Recommendations

### Priority 0: Stabilize the current baseline

1. Add a documented artifact-generation fixture or build step so a fresh clone can run analysis tests without manually guessing the setup.
2. Add a clear data dictionary and verify tab-separated O*NET file parsing.
3. Record dataset hashes, row counts, release dates, feature configuration, Git commit, training timestamp, and artifact version.
4. Remove production use of default credentials and require secure deployment secrets.
5. Add a complete test command that starts the Flask server for standalone E2E authentication tests.
6. Add a migration/backup procedure for the SQLite database.
7. Fix deprecation warnings and pin compatible dependency ranges.

### Priority 1: Make the ML claims honest and reproducible

1. Replace fixed `Ridge(alpha=1.2)` with a leakage-safe `Pipeline` and cross-validated regularization only after comparing it with baselines.
2. Report mean, median, role-group, and industry-group baselines.
3. Audit exact and near duplicates and use group-aware splits where occupations repeat.
4. Report target distribution, unique roles, missingness, within-role variance, and between-role variance.
5. Separate resume-language score, closest-role evidence, skill-role similarity, and confidence.
6. Add `low_evidence` or `insufficient_evidence` behavior.
7. Rename the feature to contextual automation exposure or task exposure.
8. Never describe the value as a personal probability, job-loss prediction, hiring prediction, ATS score, or employability prediction.

### Priority 2: Add user intent and evidence provenance

1. Add target role, alternative roles, geography, seniority, time available, budget, learning format, and application goal.
2. Store editable evidence items with source section, raw phrase, canonical label, confidence, and user correction.
3. Preserve raw resume text only with explicit consent and a retention/deletion policy.
4. Show source, version, date, fact/inference label, and confidence beside every recommendation.

### Priority 3: Add the job and application workflow

1. Add manual job capture with title, company, location, source URL, description, salary text, capture timestamp, and content hash.
2. Add application status, events, notes, contacts, tasks, and follow-up dates.
3. Add resume versions and immutable analysis snapshots.
4. Add per-job required/preferred skills, matched/missing skills, evidence excerpts, scoring components, and limitations.
5. Use manual paste and review first; do not scrape job boards or auto-submit applications in the MVP.

### Priority 4: Build a versioned O*NET foundation

1. Pin an approved O*NET database release.
2. Preserve O*NET attribution and licence terms.
3. Import stable occupation codes, titles, alternate titles, tasks, skills, knowledge, abilities, technologies, interests, Job Zones, education, experience, and related occupations.
4. Add occupation search, detail, compare, pathway, and provenance pages.
5. Distinguish official facts from local estimates and generated narratives.
6. Use an authorized O*NET Interest Profiler integration if official assessment functionality is required; otherwise retain the local result as a heuristic.

### Priority 5: Add canonical skills and ordered learning

1. Create canonical skill IDs and aliases.
2. Preserve raw evidence spans and word-boundary behavior.
3. Add required, preferred, and transferable skill types.
4. Add course prerequisites, level, duration, provider, language, source, and freshness metadata.
5. Add learning-plan items, projects, progress events, evidence, and credentials.
6. Provide one first recommended action and a re-analysis action after progress.

### Priority 6: Ground the coaching layer

1. Add a goal-aware coaching profile.
2. Return source-linked evidence, model version, retrieval version, confidence/coverage, and fact-versus-inference labels.
3. Add text-based interview practice and rubric feedback.
4. Keep external LLM use opt-in and default to deterministic/local behavior where practical.
5. Add prompt-injection tests, redaction tests, unsupported-claim tests, fallback tests, and chat-reset controls.

### Priority 7: Improve UI/UX and accessibility

1. Organize the application around the intent-to-action loop.
2. Show one clear next action on each screen.
3. Reduce nested cards and improve information hierarchy.
4. Add skeleton loading, empty states, error states, and progress indicators.
5. Use semantic headings, labels, keyboard navigation, visible focus, sufficient contrast, reduced-motion support, and text alternatives for charts.
6. Test mobile, tablet, and desktop breakpoints with Playwright.
7. Run axe-core and Lighthouse after backend semantics stabilize.
8. Add animations only where they clarify state changes or improve feedback.

## 5.3 Recommended Acceptance Criteria for the Next Release

The next meaningful release should be considered complete only when a new user can:

1. Create an account or use an approved login method.
2. Define a target role and constraints.
3. Upload or paste a resume.
4. Review and correct extracted evidence.
5. Save or paste a job description.
6. See explainable required and preferred skill gaps.
7. Start an ordered learning path.
8. Create or select a targeted resume version.
9. Track the application and set a follow-up.
10. Re-run analysis after changing evidence or progress.
11. Export or delete their stored data.
12. Understand the source, version, confidence, and limitations of each result.

---

# REFERENCES

[1]: https://www.onetcenter.org/database.html "O*NET 31.0 Database, O*NET Resource Center"

[2]: https://www.onetcenter.org/IP.html "O*NET Interest Profiler, O*NET Resource Center"

[3]: https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html "TfidfVectorizer, scikit-learn documentation"

[4]: https://www.nist.gov/itl/ai-risk-management-framework "Artificial Intelligence Risk Management Framework, National Institute of Standards and Technology"

[5]: https://oecd.ai/en/dashboards/ai-principles/P7 "Transparency and Explainability, OECD AI Principles"

[6]: https://scikit-learn.org/stable/modules/model_evaluation.html "Model Evaluation: Quantifying the Quality of Predictions, scikit-learn documentation"

[7]: https://flask.palletsprojects.com/en/stable/testing/ "Testing Flask Applications, Flask documentation"

[8]: https://www.onetonline.org/ "O*NET OnLine, U.S. Department of Labor and National Center for O*NET Development"

[9]: https://www.mynextmove.org/ "My Next Move, sponsored by the U.S. Department of Labor Employment and Training Administration"

[10]: https://www.nist.gov/itl/ai-risk-management-framework/ai-risk-management-framework-faqs "AI Risk Management Framework FAQs, NIST"

**APA-style bibliography entries for the final Word version:**

National Center for O*NET Development. (2026). *O*NET 31.0 database*. O*NET Resource Center. https://www.onetcenter.org/database.html

National Center for O*NET Development. (n.d.). *O*NET Interest Profiler*. O*NET Resource Center. https://www.onetcenter.org/IP.html

National Institute of Standards and Technology. (2023). *Artificial intelligence risk management framework (AI RMF 1.0)*. U.S. Department of Commerce. https://www.nist.gov/itl/ai-risk-management-framework

OECD. (n.d.). *Transparency and explainability*. OECD AI Principles. https://oecd.ai/en/dashboards/ai-principles/P7

Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., & Duchesnay, É. (2011). Scikit-learn: Machine learning in Python. *Journal of Machine Learning Research, 12*, 2825–2830. https://jmlr.org/papers/v12/pedregosa11a.html

Scikit-learn developers. (n.d.). *Model evaluation: Quantifying the quality of predictions*. https://scikit-learn.org/stable/modules/model_evaluation.html

Scikit-learn developers. (n.d.). *TfidfVectorizer*. https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html

U.S. Department of Labor, Employment and Training Administration. (n.d.). *O*NET OnLine*. https://www.onetonline.org/

---

# APPENDIX A: CURRENT API AND ROUTE INVENTORY

The following inventory was observed in `app.py` during report preparation:

- Authentication and account routes: `/login`, `/signup`, `/verify-otp`, `/resend-otp`, `/forgot-password`, `/forgot-password/otp`, `/reset-password`, `/reset-password/otp`, `/logout`.
- OAuth routes: Google, GitHub, and LinkedIn login/callback integration points.
- Workspace routes: `/workspace`, `/workspace/skills-gap`, `/methodology`, `/privacy`, `/insights`, `/partnerships`.
- Analysis routes: `/api/upload`, `/api/analyze`, `/api/analyze-stream`.
- Skills and career routes: `/api/skills-gap/roles`, `/api/skills-gap/analyze`, `/api/career-paths`, `/api/learning-roadmap`.
- Coaching and summary routes: `/api/career-chat`, `/api/career-chat/stream`, `/api/insights-summary`, `/api/compare`.
- Administration and feedback: `/admin`, `/api/admin/users`, `/admin/logout`, `/api/feedback`.
- Operational and security helpers: `/api/rag-status`, `/healthz`, `/api/csrf-token`, `/api/check-password`.

This inventory should be regenerated automatically before the final submission if routes change.

---

# APPENDIX B: TEST AND REPRODUCIBILITY RECORD

## B.1 Environment commands

```bash
python -m pip install -r requirements.txt
python -m compileall -q .
python train_model.py
python evaluation.py
pytest -q tests/test_app.py tests/test_email_service.py tests/test_forgot_password_otp.py
```

## B.2 Observed result

- Compilation: passed.
- Training: passed after dependencies were installed; generated `ml_models/model.pkl` and `ml_models/courses.pkl`.
- Evaluation: passed; MAE 0.2501, RMSE 0.2909, R² -0.0298.
- Focused tests after artifact generation: 83 passed, 2 warnings.
- Full collection with standalone authentication scripts: requires a running Flask server and should be executed as a separate documented stage.

## B.3 Required final-submission evidence

Before submitting the final report, attach or record:

1. Git commit hash.
2. Git tag used as the final checkpoint.
3. Python version and dependency lock/export.
4. Dataset names, row counts, release dates, and SHA-256 hashes.
5. Model-artifact generation command and artifact hashes.
6. Full test command and output.
7. Browser E2E test output.
8. Accessibility scan output.
9. Screenshots of the main workflows.
10. A statement identifying which roadmap features were implemented after this report draft.

---

# APPENDIX C: IMPLEMENTATION ROADMAP AND CHANGE CONTROL

## C.1 Phase sequence

| Phase | Goal | Green checkpoint |
|---:|---|---|
| 00 | Baseline, inventory, rollback | Compilation, tests, training, evaluation, clean diff. |
| 01 | Security and production hardening | Security tests, config checks, safe rendering review. |
| 02 | ML reproducibility and honest evaluation | Training, leakage-safe evaluation, baseline comparison, ML tests. |
| 03 | Intent and editable evidence | Ownership, validation, CRUD, correction, export/delete tests. |
| 04 | Job/application workflow | Manual capture, per-job matching, tracker, migration, browser tests. |
| 05 | Versioned O*NET intelligence | Idempotent import, provenance, occupation pages, licence review. |
| 06 | Canonical skills and ordered learning | Alias, ranking, prerequisite, progress, and evidence tests. |
| 07 | Grounded coaching and practice | Citation, prompt-injection, redaction, fallback, and reset tests. |
| 08 | UI/UX and accessibility | Playwright, axe-core, keyboard, responsive, and Lighthouse review. |

## C.2 Master coding-agent instruction

```text
Work inside the existing Final_year_project Flask repository. Implement only the requested phase. Preserve existing behavior unless the phase explicitly changes it. Inspect relevant files and tests first. State the implementation plan and expected files. Write focused tests alongside the change. Use public or licensed data only. Do not copy proprietary Lightcast, Teal, LinkedIn, or course-provider data, prompts, scores, or templates. Keep automation exposure contextual; never call it job-loss prediction, hiring prediction, ATS score, employability probability, or a personal probability. Do not send resume data to an external model without explicit opt-in. Use per-user ownership for user records. Do not add unsafe HTML rendering. Run focused tests, full relevant tests, compile checks, and inspect git diff. Do not claim tests passed unless they actually passed. Create a checkpoint only after a green gate and record migrations, artifact versions, assumptions, and rollback instructions.
```

## C.3 Suggested visual diagrams

### Figure 3.2: Processing flow

```text
Resume text/file
      |
Validation and type detection
      |
PDF/DOCX/TXT extraction
      |
Cleaning and section detection
      |
Contact and skill evidence extraction
      |
TF-IDF feature representation
      |------------------|-------------------|------------------|
Role matching       Risk estimate       RIASEC heuristic   Skills gap
      |------------------|-------------------|------------------|
Learning roadmap, career paths, explanation, next actions
```

### Figure 4.2: Recommended product loop

```text
Define intent
     ↓
Select target role and constraints
     ↓
Review resume evidence
     ↓
Save/paste job description
     ↓
Explain matched and missing skills
     ↓
Start ordered learning/project plan
     ↓
Create targeted resume version
     ↓
Track application and follow-up
     ↓
Re-analyze after progress
```

## C.4 Accuracy statement for the final report

The final report must be updated immediately before submission. Any planned feature that is not implemented and tested must remain labelled **proposed**, **partial**, or **future work**. Any metric must include its dataset, evaluation procedure, baseline, and date. Any O*NET-derived material must include the required attribution and release information. Any user study must report its sample, protocol, consent, and limitations. No result should be presented as a fact if it was only suggested by an AI coding assistant or an unverified planning document.
