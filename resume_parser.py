"""
Prayash - Enhanced Resume Parser
=================================
Ports SAHAY_AI's advanced resume parsing into Prayash's Flask ecosystem.

Features:
- Advanced skill extraction (multi-separator, category-labeled, cleaning)
- Contact info extraction (email, phone, LinkedIn, GitHub)
- Section detection (education, experience, projects, skills)
- Resume quality / completeness scoring
- Backward-compatible with existing extract_resume_text()
"""

from __future__ import annotations
import logging
import re
from io import BytesIO
from typing import Any

try:
    from docx import Document
except Exception:
    Document = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

# PyMuPDF – SAHAY_AI-style enhanced PDF extraction (3x better quality)
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except Exception:
    HAS_PYMUPDF = False

from utils import clean_text as _clean_text

log = logging.getLogger("prayash.parser")


# ─── 1. Text Extraction (PyMuPDF preferred, fallback to pypdf) ────


def _extract_pdf_with_pymupdf(payload: bytes) -> str | None:
    """Extract text from PDF bytes using PyMuPDF (3x better extraction).
    Returns None if PyMuPDF is unavailable or fails."""
    if not HAS_PYMUPDF:
        return None
    try:
        doc = fitz.open(stream=payload, filetype="pdf")
        text_parts: list[str] = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text("text")
            # Clean PDF-specific noise
            page_text = re.sub(r'\s+', ' ', page_text)
            page_text = re.sub(r'([a-z])([A-Z])', r'\1 \2', page_text)
            page_text = re.sub(r'\b\d+\s*$', '', page_text, flags=re.MULTILINE)
            text_parts.append(page_text.strip())
        doc.close()
        result = " ".join(text_parts)
        if len(result.strip()) > 20:
            return result
        return None
    except Exception:
        log.warning("PyMuPDF extraction failed, falling back to pypdf")
        return None


# ─── 1b. SAHAY_AI-style PDF Layout Extraction (font-size + position) ──


def extract_pdf_layout(payload: bytes) -> dict[str, Any]:
    """Extract text with layout information using PyMuPDF's get_text("dict").

    Returns structured data with font sizes, positions (bbox), and font names
    per text span, enabling font-size-based section header detection.
    Returns an empty dict if PyMuPDF is unavailable or extraction fails.

    This is adapted from SAHAY_AI's ``extract_text_with_layout()`` which uses
    ``page.get_text("dict")`` to obtain per-span metadata.

    Returns:
        dict with keys:
          - "text": combined plain text string
          - "spans": list of {text, font_size, font_name, bbox, page}
          - "metadata": PDF metadata dict from doc.metadata
          - "page_count": int
    """
    if not HAS_PYMUPDF:
        return {"text": "", "spans": [], "metadata": {}, "page_count": 0}
    try:
        doc = fitz.open(stream=payload, filetype="pdf")
        spans: list[dict[str, Any]] = []
        text_parts: list[str] = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            blocks = page.get_text("dict")
            for block in blocks.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            raw = (span.get("text") or "").strip()
                            if not raw:
                                continue
                            spans.append({
                                "text": raw,
                                "font_size": span.get("size", 12.0),
                                "font_name": span.get("font", ""),
                                "bbox": span.get("bbox", [0, 0, 0, 0]),
                                "page": page_num,
                            })
                            text_parts.append(raw)
                    text_parts.append("\n")

        doc_meta = dict(doc.metadata) if doc.metadata else {}
        page_count = len(doc)
        doc.close()

        return {
            "text": " ".join(text_parts).strip(),
            "spans": spans,
            "metadata": doc_meta,
            "page_count": page_count,
        }
    except Exception as exc:
        log.warning("PyMuPDF layout extraction failed: %s", exc)
        return {"text": "", "spans": [], "metadata": {}, "page_count": 0}


def extract_text_by_sections(payload: bytes) -> dict[str, str]:
    """Extract PDF text organized by sections using font-size analysis.

    Uses ``extract_pdf_layout()`` to get per-span font sizes, then
    identifies section headers as spans whose font size exceeds 1.2x
    the average and whose text is ≤ 4 words (SAHAY_AI heuristic).

    Adapted from SAHAY_AI's ``extract_text_by_sections()``.

    Returns:
        dict mapping section names (derived from header text) to content,
        plus a "full_text" entry with the combined raw text.
    """
    layout = extract_pdf_layout(payload)
    spans = layout.get("spans", [])
    if not spans:
        return {"full_text": layout.get("text", "")}

    # Calculate average font size for header threshold
    font_sizes = [s["font_size"] for s in spans]
    avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12.0
    header_threshold = avg_font_size * 1.2

    sections: dict[str, list[str]] = {}
    current_section = "general"
    current_text: list[str] = []

    for span in spans:
        text = span["text"]
        font_size = span["font_size"]

        # Check if this span looks like a section header
        is_header = (
            font_size > header_threshold
            and len(text.split()) <= 4
            and (text.isupper() or text.istitle() or text[0].isupper())
        )

        if is_header:
            # Save previous section
            if current_text:
                sections[current_section] = " ".join(current_text)
            # Start new section — normalise the key
            current_section = text.lower().replace(" ", "_").replace(":", "")
            current_text = []
        else:
            current_text.append(text)

    # Save the last section
    if current_text:
        sections[current_section] = " ".join(current_text)

    # Always include full raw text
    sections["full_text"] = layout.get("text", "")
    return sections


def get_pdf_metadata(payload: bytes) -> dict[str, Any]:
    """Extract PDF metadata (title, author, subject, creator, producer, pages).

    Adapted from SAHAY_AI's ``get_pdf_metadata()``.

    Returns:
        dict with keys: title, author, subject, creator, producer, pages.
        Returns an empty dict if extraction fails.
    """
    if not HAS_PYMUPDF:
        return {}
    try:
        doc = fitz.open(stream=payload, filetype="pdf")
        meta = dict(doc.metadata) if doc.metadata else {}
        result = {
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "subject": meta.get("subject", ""),
            "creator": meta.get("creator", ""),
            "producer": meta.get("producer", ""),
            "pages": len(doc),
        }
        doc.close()
        return result
    except Exception as exc:
        log.warning("PyMuPDF metadata extraction failed: %s", exc)
        return {}


def extract_resume_text(uploaded_file) -> str:
    """Extract raw text from an uploaded resume file (PDF, DOCX, or TXT).
    Uses PyMuPDF for PDFs when available (3x better extraction),
    falls back to pypdf2, then to plain text."""
    filename = (uploaded_file.filename or "").lower()
    payload = uploaded_file.read()
    uploaded_file.stream.seek(0)

    if filename.endswith(".pdf"):
        # Try PyMuPDF first (SAHAY_AI-style enhanced extraction)
        if HAS_PYMUPDF:
            text = _extract_pdf_with_pymupdf(payload)
            if text:
                return _clean_text(text)
        # Fallback to pypdf
        if PdfReader is not None:
            reader = PdfReader(BytesIO(payload))
            return _clean_text(" ".join(page.extract_text() or "" for page in reader.pages))

    if filename.endswith(".docx") and Document is not None:
        document = Document(BytesIO(payload))
        return _clean_text(" ".join(paragraph.text for paragraph in document.paragraphs))

    return _clean_text(payload.decode("utf-8", errors="ignore"))


# ─── 2. Contact Info Extraction ─────────────────────────────────────

def extract_contact_info(text: str) -> dict[str, str]:
    """Extract contact information from resume text."""
    contact: dict[str, str] = {}
    email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
    if email_match:
        contact["email"] = email_match.group().lower()
    phone_patterns = [
        r"\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        r"\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,4}\b",
    ]
    for pat in phone_patterns:
        m = re.search(pat, text)
        if m:
            raw = m.group().strip()
            digits = re.sub(r"\D", "", raw)
            if len(digits) >= 10:
                contact["phone"] = raw
                break
    linkedin_pat = r"(?:linkedin\.com/in/|linkedin\.com/pub/|linkedin\.com/profile/view\\?id=)[\w-]+"
    lii = re.search(linkedin_pat, text, re.IGNORECASE)
    if lii:
        contact["linkedin"] = lii.group().lower()
    ghi = re.search(r"github\.com/[\w-]+", text, re.IGNORECASE)
    if ghi:
        contact["github"] = ghi.group().lower()
    return contact


# ─── 3. Section Detection ─────────────────────────────────────────

_SECTION_HEADERS: set[str] = {
    "education", "experience", "skills", "projects", "work", "employment",
    "academic", "qualifications", "certifications", "languages", "interests",
    "achievements", "awards", "publications", "references", "contact",
    "professional summary", "summary", "objective", "career objective",
    "technical skills", "technical experience", "professional experience",
    "work experience", "open source", "leadership", "volunteer",
    "extracurricular", "activities", "honors", "training",
}


def _is_section_header(line: str) -> bool:
    cleaned = line.strip()
    if not cleaned:
        return False
    if cleaned.lower() in _SECTION_HEADERS:
        return True
    if len(cleaned.split()) <= 4:
        if cleaned.isupper() or re.match(r'^[A-Z][A-Z\s]+$', cleaned):
            return True
        if cleaned.istitle() and cleaned.replace(" & ", " ").istitle():
            return True
    return False


def extract_section(lines: list[str], keywords: list[str]) -> list[str]:
    """Extract content from a section identified by keywords."""
    section: list[str] = []
    found = False
    for line in lines:
        lc = line.strip()
        if not lc:
            continue
        matched = any(kw in lc.lower() for kw in keywords)
        if matched and not found:
            found = True
            continue
        if found:
            if _is_section_header(lc):
                break
            section.append(lc)
    return section


# ─── 4. Skill Extraction (34+ Categories) ───────────────────────────

_SKILL_CATEGORIES: dict[str, list[str]] = {
    "AI / ML Frameworks": ["tensorflow", "pytorch", "keras", "scikit-learn", "sklearn", "xgboost", "lightgbm", "catboost", "hugging face", "transformers", "langchain", "langgraph", "langsmith", "llama", "llamaindex", "openai", "gpt", "claude", "anthropic", "gemini", "mistral", "ollama", "vllm", "stable diffusion", "diffusers", "whisper", "onnx", "mlflow", "kubeflow", "opencv", "spacy", "nltk", "gensim", "fastai", "jax", "caffe", "gradio", "streamlit", "chainlit", "semantic kernel", "guardrails", "instructor"],
    "Backend Frameworks": ["django", "flask", "fastapi", "spring", "spring boot", "express", "express.js", "ruby on rails", "rails", "laravel", "symfony", "asp.net", "asp.net core", "dotnet", ".net", "nestjs", "koa", "tornado", "aiohttp", "gin", "echo", "fiber", "actix", "axum", "rocket", "poetry", "uvicorn", "gunicorn"],
    "Business & Soft Skills": ["leadership", "team management", "mentoring", "coaching", "communication", "presentation", "public speaking", "negotiation", "conflict resolution", "decision making", "problem solving", "critical thinking", "creativity", "adaptability", "collaboration", "strategic planning", "operations management"],
    "Cloud & Infrastructure": ["aws", "amazon web services", "azure", "microsoft azure", "gcp", "google cloud", "google cloud platform", "oracle cloud", "oci", "cloudflare", "heroku", "digitalocean", "linode", "terraform", "ansible", "pulumi", "cloudformation", "cdk", "serverless", "lambda", "ec2", "s3", "rds", "cloudfront", "ecs", "eks", "aks", "gke", "vercel", "netlify", "render", "fly", "railway", "cloudflare workers", "cloudflare pages", "hashicorp", "packer", "nomad", "boundary", "tailscale", "zerotier"],
    "Creative & Content": ["content writing", "content strategy", "content marketing", "copywriting", "technical writing", "blogging", "editing", "proofreading", "translation", "seo", "social media marketing", "email marketing", "video production", "video editing", "motion graphics", "photography", "illustration", "animation", "blender", "after effects", "premiere pro", "da vinci resolve", "final cut pro", "audacity"],
    "Data Engineering": ["etl", "data pipeline", "data warehouse", "data lake", "data modeling", "apache spark", "spark", "pyspark", "apache flink", "flink", "apache kafka", "kafka", "apache airflow", "airflow", "prefect", "dbt", "dataform", "snowflake", "bigquery", "redshift", "databricks", "hadoop", "hive", "stream processing", "delta lake", "lakehouse", "iceberg", "dlt", "duckdb", "polars", "clickhouse", "druid", "pinot", "starrocks", "materialize", "risingwave", "unity catalog"],
    "Data Science & ML": ["machine learning", "deep learning", "natural language processing", "nlp", "computer vision", "cv", "reinforcement learning", "statistics", "statistical modeling", "regression", "classification", "clustering", "dimensionality reduction", "feature engineering", "a/b testing", "time series analysis", "forecasting", "recommender systems", "anomaly detection", "data mining", "predictive modeling", "supervised learning", "unsupervised learning", "transfer learning", "bayesian statistics", "hypothesis testing", "causal inference", "experimental design"],
    "Data Visualization": ["tableau", "power bi", "looker", "metabase", "superset", "matplotlib", "seaborn", "plotly", "dash", "bokeh", "ggplot2", "d3.js", "d3", "chart.js", "highcharts", "google data studio", "data studio", "qlik", "sigmoid", "hex"],
    "Databases": ["sql", "mysql", "postgresql", "postgres", "sqlite", "oracle", "sql server", "mssql", "mariadb", "cassandra", "mongodb", "redis", "elasticsearch", "dynamodb", "couchdb", "couchbase", "firebase", "firestore", "neo4j", "influxdb", "timescaledb", "cockroachdb", "supabase", "planetscale", "neon", "turso", "motherduck", "singlestore", "surrealdb", "edgedb", "chroma", "chromadb", "pinecone", "weaviate", "milvus", "qdrant", "pgvector"],
    "Design / UX": ["figma", "sketch", "adobe xd", "photoshop", "illustrator", "canva", "invision", "zeplin", "framer", "wireframing", "prototyping", "information architecture", "interaction design", "visual design", "graphic design", "user interface", "user experience", "ux research", "design systems", "accessibility", "responsive design", "design thinking", "maze", "hotjar", "fullstory"],
    "DevOps & CI/CD": ["docker", "kubernetes", "k8s", "jenkins", "github actions", "gitlab ci", "circleci", "travis ci", "teamcity", "bamboo", "argo cd", "helm", "istio", "consul", "vault", "prometheus", "grafana", "datadog", "new relic", "splunk", "elk stack", "elastic stack", "fluentd", "kibana", "logstash", "dagger", "earthly", "podman", "buildah", "skopeo", "kaniko", "sops", "sealed secrets", "external secrets", "crossplane", "opentelemetry", "signoz", "tempo", "loki", "mimir", "thanos", "cortex"],
    "Embedded / IoT": ["arduino", "raspberry pi", "esp32", "esp8266", "stm32", "microcontroller", "firmware", "rtos", "freertos", "embedded c", "embedded linux", "mqtt", "coap", "zigbee", "bluetooth low energy", "ble", "iot", "internet of things", "sensors", "industrial automation", "plc", "scada"],
    "Finance / Accounting": ["financial analysis", "financial modeling", "valuation", "accounting", "bookkeeping", "quickbooks", "xero", "sap", "oracle financials", "netsuite", "budgeting", "forecasting", "financial planning", "cfa", "cpa", "acca", "gaap", "ifrs", "stripe", "square", "braintree", "plaid"],
    "Frontend Frameworks": ["react", "angular", "vue", "vue.js", "svelte", "next.js", "nextjs", "nuxt", "nuxt.js", "gatsby", "ember", "backbone", "preact", "solid.js", "solidjs", "qwik", "alpine.js", "alpinejs", "lit", "htmx", "redux", "mobx", "vuex", "pinia", "remix", "remix.run", "sveltekit", "astro", "eleventy", "11ty", "jekyll", "hugo"],
    "Game Development": ["unity", "unreal engine", "unreal", "godot", "game design", "level design", "game mechanics", "3d modeling", "animation", "shaders", "vr", "virtual reality", "ar", "augmented reality", "webgl", "three.js", "bevy", "roblox studio"],
    "Generative AI & LLMOps": ["generative ai", "genai", "mlops", "prompt engineering", "prompt tuning", "retrieval augmented generation", "rag", "fine-tuning", "instruction tuning", "rlhf", "dpo", "preference optimization", "langsmith", "langfuse", "wandb", "weights & biases", "neptune", "comet", "dvc", "dagshub", "prompt flow", "semantic kernel", "vector database", "embedding", "tokenization", "agents", "agentic", "multi-agent", "autogpt", "crewai", "autogen", "function calling", "tool use", "chain of thought", "cot", "knowledge graph", "graphrag", "lora", "qlora", "quantization", "gguf", "awq", "gptq", "sglang", "triton inference server", "tensorrt", "llm evaluation", "red teaming", "guardrails", "grounding", "hallucination detection"],
    "Healthcare / BioTech": ["clinical research", "clinical trials", "medical writing", "bioinformatics", "genomics", "biostatistics", "health informatics", "electronic health records", "hipaa", "fda", "regulatory affairs", "medical devices", "telemedicine", "digital health"],
    "Human Resources": ["recruiting", "talent acquisition", "sourcing", "interviewing", "onboarding", "employee relations", "performance management", "workday", "bamboo hr", "greenhouse", "labor law", "employment law", "diversity & inclusion", "employee engagement", "learning & development", "lattice", "culture amp", "lever", "ashby"],
    "Legal": ["contract law", "corporate law", "intellectual property", "litigation", "dispute resolution", "arbitration", "compliance", "regulatory compliance", "legal research", "due diligence", "data privacy", "gdpr", "ccpa", "hipaa", "contract drafting", "contract negotiation"],
    "Marketing": ["digital marketing", "growth marketing", "seo", "sem", "ppc", "google ads", "facebook ads", "content marketing", "brand strategy", "branding", "social media management", "email marketing", "mailchimp", "sendgrid", "hubspot", "lead generation", "google analytics", "market research", "mixpanel", "amplitude", "segment", "intercom", "customer io"],
    "Mobile Development": ["android", "ios", "kotlin", "swift", "react native", "flutter", "dart", "xamarin", "ionic", "cordova", "capacitor", "jetpack compose", "swiftui", "uikit", "android sdk", "expo", "outsystems", "flutterflow"],
    "Networking": ["tcp/ip", "dns", "http", "https", "ssl", "tls", "udp", "routing", "switching", "firewall", "vpn", "load balancer", "proxy", "reverse proxy", "nginx", "apache", "caddy", "traefik", "haproxy", "network monitoring", "netbird", "headscale", "wireguard", "ipsec"],
    "Operating Systems": ["linux", "unix", "ubuntu", "debian", "centos", "red hat", "fedora", "arch linux", "alpine", "macos", "windows", "bash", "zsh", "powershell", "shell scripting", "nixos", "nix", "opensuse", "rocky linux"],
    "Programming Languages": ["python", "java", "javascript", "typescript", "c++", "c#", "c", "go", "golang", "rust", "swift", "kotlin", "ruby", "php", "scala", "perl", "lua", "haskell", "elixir", "clojure", "dart", "r", "matlab", "julia", "assembly", "fortran", "cobol", "delphi", "groovy", "objective-c", "f#", "solidity", "vba", "zig", "nim", "mojo", "ocaml", "erlang", "crystal", "racket", "common lisp"],
    "Project Management": ["agile", "scrum", "kanban", "waterfall", "lean", "sprint planning", "jira", "confluence", "trello", "asana", "monday.com", "notion", "risk management", "stakeholder management", "budgeting", "roadmapping", "pmp", "prince2", "certified scrum master", "csm", "linear", "basecamp", "clickup", "height", "shortcut"],
    "Sales": ["b2b sales", "b2c sales", "enterprise sales", "saas sales", "salesforce", "hubspot", "sales development", "account management", "account executive", "lead generation", "prospecting", "crm", "sales pipeline", "negotiation", "closing", "upselling", "sales strategy", "consultative selling"],
    "Scientific / Engineering": ["matlab", "simulink", "labview", "ansys", "autocad", "solidworks", "catia", "creo", "inventor", "revit", "finite element analysis", "fea", "computational fluid dynamics", "cfd", "control systems", "robot operating system", "ros", "ros2", "gazebo", "fusion 360", "onshape", "freecad", "kiCad", "altium"],
    "Security": ["cybersecurity", "network security", "application security", "appsec", "penetration testing", "vulnerability assessment", "siem", "incident response", "threat intelligence", "cryptography", "encryption", "authentication", "authorization", "oauth", "jwt", "saml", "openid connect", "zero trust", "compliance", "gdpr", "hipaa", "soc 2", "iso 27001", "owasp", "burp suite", "cloud security", "semgrep", "snyk", "sonarqube", "trivy", "falco", "wazuh", "crowdstrike", "sentinelone", "qualys", "nessus", "tenable"],
    "Soft Skills": ["teamwork", "communication skills", "interpersonal skills", "empathy", "emotional intelligence", "time management", "attention to detail", "self-motivation", "initiative", "ownership", "integrity", "customer service", "relationship building"],
    "System Design": ["system design", "microservices", "monolithic", "event-driven", "cqrs", "event sourcing", "domain-driven design", "ddd", "hexagonal architecture", "clean architecture", "message queue", "rabbitmq", "kafka", "nats", "zeromq", "api gateway", "load balancing", "caching", "cdn", "distributed systems", "cap theorem", "grpc", "protobuf", "graphql", "rest", "webhook", "event bus", "outbox pattern", "saga pattern", "circuit breaker", "retry", "backpressure", "rate limiting"],
    "Testing": ["jest", "mocha", "chai", "cypress", "playwright", "selenium", "pytest", "junit", "testng", "jasmine", "karma", "enzyme", "testing library", "react testing library", "vitest", "cucumber", "gherkin", "load testing", "jmeter", "k6", "unit testing", "integration testing", "e2e testing", "tdd", "test-driven development", "bdd", "detox", "appium", "locust", "gatling", "artillery", "sonar", "eslint", "prettier", "husky", "lint-staged"],
    "Tools & Productivity": ["microsoft office", "excel", "word", "powerpoint", "outlook", "google workspace", "google docs", "google sheets", "slack", "teams", "discord", "zoom", "notion", "obsidian", "evernote", "vim", "neovim", "emacs", "vscode", "visual studio code", "intellij", "pycharm", "eclipse", "postman", "insomnia", "swagger", "openapi", "zed", "cursor", "warp", "hyper", "iterm2", "raycast", "alfred", "kitty", "alacritty", "tmux", "screen"],
    "Version Control": ["git", "github", "gitlab", "bitbucket", "mercurial", "svn", "subversion", "cvs", "perforce", "fossil"],
    "Web Technologies": ["html", "css", "sass", "scss", "less", "bootstrap", "tailwind", "jquery", "ajax", "graphql", "rest", "restful", "soap", "webpack", "babel", "vite", "esbuild", "node.js", "node", "npm", "yarn", "pnpm", "gulp", "grunt", "webassembly", "wasm", "bun", "deno", "turbo", "turborepo", "nx", "nrwl", "lerna", "rollup", "parcel", "snowpack", "rome", "biome", "oxc", "rolldown", "rsbuild", "rspack", "tauri", "electron", "capacitor"],
}


def _normalize_skill_name(skill: str) -> str:
    s = skill.strip().lower()
    s = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", s)
    s = re.sub(r"\s+\d+\.?\d*\s*$", "", s).strip()
    return s


def _skill_display_name(kw: str) -> str:
    """Return a display-friendly version of a skill keyword."""
    special = {
        "c++": "C++", "c#": "C#", "f#": "F#", ".net": ".NET",
        "node.js": "Node.js", "next.js": "Next.js", "nuxt.js": "Nuxt.js",
        "vue.js": "Vue.js", "express.js": "Express.js", "d3.js": "D3.js",
        "react native": "React Native", "machine learning": "Machine Learning",
        "deep learning": "Deep Learning", "azure": "Azure", "aws": "AWS",
        "gcp": "GCP", "ci/cd": "CI/CD", "docker": "Docker",
        "chromadb": "ChromaDB", "pgvector": "pgvector", "autogpt": "AutoGPT",
        "k8s": "k8s", "mlops": "MLOps", "genai": "GenAI", "llmops": "LLMOps",
        "rag": "RAG", "rlhf": "RLHF", "dpo": "DPO", "lora": "LoRA",
        "qlora": "QLoRA", "gptq": "GPTQ", "awq": "AWQ", "gguf": "GGUF",
        "wandb": "WandB", "dvc": "DVC", "cot": "CoT", "autogen": "AutoGen",
    }
    if kw in special:
        return special[kw]
    return kw.title()


def extract_skills_from_text(text: str) -> dict[str, object]:
    """Extract skills from text, grouped by category."""
    lower_text = text.lower()
    all_skills: list[str] = []
    by_category: dict[str, list[str]] = {}

    for category, keywords in _SKILL_CATEGORIES.items():
        found: set[str] = set()
        for kw in keywords:
            pattern = re.escape(kw)
            if re.search(r"\b" + pattern + r"\b", lower_text):
                found.add(_skill_display_name(kw))
        if found:
            by_category[category] = sorted(found)
            all_skills.extend(sorted(found))

    seen: set[str] = set()
    deduped: list[str] = []
    for s in all_skills:
        if s.lower() not in seen:
            seen.add(s.lower())
            deduped.append(s)

    return {
        "by_category": dict(sorted(by_category.items())),
        "all_skills": deduped,
        "count": len(deduped),
        "categories_found": len(by_category),
    }


# ─── 5. Main Parsing Entry Point ─────────────────────────────────

def parse_resume_enhanced(raw_text: str, layout_sections: dict[str, str] | None = None) -> dict[str, object]:
    """Parse resume text into a structured dictionary.

    When ``layout_sections`` is provided (from ``extract_text_by_sections()``),
    the font-size-based section detection overrides keyword-based heuristics
    for more accurate section identification (SAHAY_AI-style).

    Args:
        raw_text: The full resume text to parse.
        layout_sections: Optional dict from ``extract_text_by_sections()``
            mapping section names to content, plus a "full_text" key.

    Returns:
        Structured dict with contact, education, experience, projects,
        skills, certifications, achievements, and quality analysis.
    """
    lines = [ln.strip() for ln in raw_text.split("\n") if ln.strip()]
    contact_info = extract_contact_info(raw_text)
    layout_sections = layout_sections or {}

    # Helper: prefer layout-based content, fall back to keyword-based extraction
    def _sec(layout_key: str, keywords: list[str]) -> list[str]:
        content = layout_sections.get(layout_key)
        if content:
            return [c.strip() for c in content.split("\n") if c.strip()]
        return extract_section(lines, keywords)

    education = _sec("education", [
        "education", "academic", "qualifications", "degree", "university", "college"
    ])
    experience = _sec("experience", [
        "experience", "work", "employment", "career", "professional experience"
    ])
    projects_lines = _sec("projects", [
        "projects", "project", "portfolio", "works", "personal projects"
    ])
    skills_lines = _sec("skills", [
        "skills", "technical skills", "technologies", "programming",
        "core competencies", "expertise"
    ])
    certifications = _sec("certifications", [
        "certifications", "certificates", "licenses", "professional certifications"
    ])
    achievements = _sec("achievements", [
        "achievements", "awards", "honors", "publications", "recognition"
    ])

    projects: list[dict[str, object]] = []
    if projects_lines:
        current: dict[str, object] | None = None
        for line in projects_lines:
            if not line.strip():
                continue
            if len(line.split()) <= 6 and (line.istitle() or line.isupper() or line[0].isupper()):
                if not _is_section_header(line):
                    if current and current.get('name'):
                        projects.append(current)
                    current = {"name": line}
                    continue
            if current is not None:
                current.setdefault('description', [])
                current['description'].append(line)
        if current and current.get("name"):
            projects.append(current)

    skills_text = " ".join(skills_lines) if skills_lines else raw_text
    skill_data = extract_skills_from_text(skills_text)

    sections_found: list[str] = []
    for name, val in [
        ("education", education), ("experience", experience),
        ("projects", projects), ("skills", skill_data["all_skills"]),
        ("certifications", certifications), ("achievements", achievements),
    ]:
        if val:
            sections_found.append(name)
    if contact_info:
        sections_found.append("contact")

    return {
        "contact": contact_info,
        "education": education,
        "experience": experience,
        "projects": projects,
        "skills": skill_data,
        "certifications": certifications,
        "achievements": achievements,
        "sections_found": sections_found,
        'metadata': {
            "total_characters": len(raw_text),
            "total_lines": len(lines),
            "sections_found_count": len(sections_found),
        },
        "raw_text": raw_text,
    }


# ─── 6. Resume Quality Scoring ───────────────────────────────────

def analyze_resume_quality(parsed: dict[str, object]) -> dict[str, object]:
    """Score resume completeness and quality (0-100)."""
    score = 0
    max_score = 0
    strengths: list[str] = []
    missing: list[str] = []
    recommendations: list[str] = []

    # Contact info (10 pts)
    max_score += 10
    contact = parsed.get("contact", {})
    if isinstance(contact, dict) and contact:
        if contact.get("email"):
            score += 4
            strengths.append("Email address provided")
        else:
            missing.append("Email address")
            recommendations.append("Add your email address")
        if contact.get("phone"):
            score += 3
            strengths.append("Phone number provided")
        else:
            missing.append("Phone number")
        if contact.get('linkedin'):
            score += 2
            strengths.append("LinkedIn profile linked")
        if contact.get('github'):
            score += 1
            strengths.append("GitHub profile linked")

    # Education (15 pts)
    max_score += 15
    edu = parsed.get("education", [])
    if edu and len(edu) > 0:
        score += 15
        strengths.append(f"Education section found ({len(edu)} entries)")
    else:
        missing.append("Education")
        recommendations.append("Add your educational background")

    # Experience (20 pts)
    max_score += 20
    exp = parsed.get("experience", [])
    if exp and len(exp) > 0:
        score += min(20, len(exp) * 7)
        strengths.append(f"Work experience listed ({len(exp)} entries)")
    else:
        missing.append("Experience")
        recommendations.append("Add your work experience")

    # Projects (15 pts)
    max_score += 15
    proj = parsed.get("projects", [])
    if proj and len(proj) > 0:
        score += min(15, len(proj) * 5)
        strengths.append(f"Projects section found ({len(proj)} entries)")
    else:
        missing.append("Projects")
        recommendations.append("Add projects to demonstrate experience")

    # Skills (30 pts)
    max_score += 30
    skills = parsed.get("skills", {})
    skill_count = 0
    if isinstance(skills, dict):
        skill_count = skills.get("count", 0)
    if skill_count > 0:
        score += min(20, skill_count * 3)
        if skill_count >= 10:
            score += 5
            strengths.append(f"Strong skills section ({skill_count} skills)")
        elif skill_count >= 5:
            score += 3
            strengths.append(f"Moderate skills section ({skill_count} skills)")
        cats = skills.get("categories_found", 0) if isinstance(skills, dict) else 0
        if cats >= 3:
            score += 5
            strengths.append(f"Skills span {cats} categories")
    else:
        missing.append("Skills")
        recommendations.append("Add a comprehensive skills section")

    # Certifications (5 pts)
    max_score += 5
    certs = parsed.get("certifications", [])
    if certs and len(certs) > 0:
        score += min(5, len(certs) * 2)
        strengths.append(f"Certifications listed ({len(certs)})")

    # Achievements (5 pts)
    max_score += 5
    ach = parsed.get("achievements", [])
    if ach and len(ach) > 0:
        score += min(5, len(ach) * 2)
        strengths.append(f"Achievements section found ({len(ach)} entries)")

    pct = round((score / max_score) * 100, 1) if max_score > 0 else 0
    grade = "A" if pct >= 90 else "B" if pct >= 75 else "C" if pct >= 60 else "D" if pct >= 40 else "F"

    if pct < 100:
        recommendations.append(f"Your resume is {pct:.0f}% complete - filling in missing sections will help")
    if len(recommendations) > 6:
        recommendations = recommendations[:6]
        recommendations.append("... and improve other sections as time allows")

    return {
        "completeness_score": pct,
        "grade": grade,
        "missing_sections": missing,
        "strengths": strengths,
        "recommendations": recommendations,
    }


# ─── 7. Backward-compatible alias ────────────────────────────────

def parse_resume(raw_text: str) -> dict[str, object]:
    """Alias for parse_resume_enhanced for backward compatibility."""
    return parse_resume_enhanced(raw_text)

