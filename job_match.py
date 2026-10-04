"""Deterministic Target Job Match extraction using the dedicated vocabulary.

Does not call occupation confirmation, benchmark lookup, or risk_assessor.
``not evidenced`` is evidence-coverage only.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from job_requirement_vocabulary import PREFERRED_HEADINGS, REQUIRED_HEADINGS, VOCABULARY

EXTRACTION_VERSION = "tjm-vocabulary-c2"

# Canonical pairs that must never be treated as equivalent by substring matching.
NEAR_MISS_BLOCKLIST = (
    ("java", "javascript"),
    ("sql", "postgresql"),
    ("aws", "cloud"),
    ("azure", "cloud"),
    ("excel", "spreadsheet"),
    ("machine learning", "data analysis"),
)

QUALIFICATION_RE = re.compile(
    r"\b(bachelor|master|mba|phd|doctorate|degree|diploma|certification|certified)\b",
    re.I,
)
EXPERIENCE_RE = re.compile(r"\b(\d+)\s*\+?\s*(?:years?|yrs?)\b", re.I)


def content_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _is_heading(line: str, markers: tuple[str, ...]) -> bool:
    stripped = line.strip().lower().rstrip(".:")
    if not stripped or len(stripped) > 64:
        return False
    if stripped in markers:
        return True
    before_colon = stripped.split(":", 1)[0].strip()
    remainder = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
    return before_colon in markers and not remainder


def _word_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    if re.fullmatch(r"[a-z0-9+#.+-]+", alias, re.I) and " " not in alias:
        return re.compile(rf"(?<!\w){escaped}(?!\w)", re.I)
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.I)


def _match_entry(line: str, entry: dict[str, Any]) -> str | None:
    lowered = line.lower()
    for pattern in entry.get("context_patterns") or ():
        if re.search(pattern, lowered, re.I):
            return str(entry["canonical_name"])
    for alias in (str(entry["canonical_name"]), *tuple(entry.get("aliases") or ())):
        alias_n = _normalise(alias)
        if not alias_n:
            continue
        if len(alias_n) < 3 and alias_n not in {"c++", "aws", "sql", "css", "git", "js"}:
            continue
        if alias_n == "go":
            continue
        if _word_pattern(alias_n).search(lowered):
            return str(entry["canonical_name"])
    return None


def _priority_clauses(line: str) -> list[str]:
    parts = re.split(r"(?=(?:preferred|nice to have|required|must have)\s*:)", line, flags=re.I)
    return [part.strip() for part in parts if part.strip()]


def extract_requirements(description: str) -> list[dict[str, Any]]:
    text = description or ""
    lines = text.splitlines() or [text]
    section = "body"
    found: dict[str, dict[str, Any]] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _is_heading(stripped, PREFERRED_HEADINGS):
            section = "preferred"
            continue
        if _is_heading(stripped, REQUIRED_HEADINGS):
            section = "required"
            continue
        for clause in _priority_clauses(stripped):
            line_priority = ""
            lowered_line = clause.lower()
            if re.match(r"^(preferred|nice to have|bonus|plus)\b", lowered_line):
                line_priority = "preferred"
            elif re.match(r"^(required|requirements|must have|minimum qualifications|basic qualifications)\b", lowered_line):
                line_priority = "required"
            effective = line_priority or ("preferred" if section == "preferred" else "required")
            source_section = "preferred" if effective == "preferred" else ("required" if line_priority == "required" or section == "required" else section)
            for entry in VOCABULARY:
                name = _match_entry(clause, entry)
                if not name:
                    continue
                key = _normalise(name)
                if key in found:
                    continue
                found[key] = {
                    "requirement": name,
                    "canonical_requirement": name,
                    "priority": effective,
                    "category": entry["category"],
                    "normalized": True,
                    "source_line": clause[:280],
                    "source_section": source_section,
                    "provenance": f"vocabulary:{key}",
                    "extraction_method": EXTRACTION_VERSION,
                }
            for match in EXPERIENCE_RE.finditer(clause):
                label = f"{match.group(1)} years of experience"
                key = _normalise(label)
                if key in found:
                    continue
                found[key] = {
                    "requirement": label,
                    "canonical_requirement": None,
                    "priority": effective,
                    "category": "experience",
                    "normalized": False,
                    "source_line": clause[:280],
                    "source_section": source_section,
                    "provenance": "experience-pattern",
                    "extraction_method": EXTRACTION_VERSION,
                }
            if QUALIFICATION_RE.search(clause):
                key = "qualification-review"
                if key not in found:
                    found[key] = {
                        "requirement": clause[:160],
                        "canonical_requirement": None,
                        "priority": effective,
                        "category": "qualification",
                        "normalized": False,
                        "source_line": clause[:280],
                        "source_section": source_section,
                        "provenance": "qualification-pattern",
                        "extraction_method": EXTRACTION_VERSION,
                    }
    if not found and text.strip():
        return []
    return list(found.values())


def skills_from_resume_text(resume_text: str) -> list[dict[str, Any]]:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", resume_text or "")
    skills: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sentence in sentences:
        for entry in VOCABULARY:
            name = _match_entry(sentence, entry)
            if not name:
                continue
            key = _normalise(name)
            if key in seen:
                continue
            seen.add(key)
            skills.append(
                {
                    "skill": name,
                    "evidence_span": sentence.strip()[:280],
                    "status": "confirmed",
                    "source_section": "resume_version",
                }
            )
    return skills


def _lookup(skills: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in skills:
        name = _normalise(str(item.get("skill") or ""))
        if not name:
            continue
        index[name] = item
        for entry in VOCABULARY:
            names = {_normalise(str(entry["canonical_name"]))}
            names.update(_normalise(str(alias)) for alias in entry.get("aliases") or ())
            if name in names:
                for alias in names:
                    index[alias] = item
    return index


def _is_blocked_near_miss(left: str, right: str) -> bool:
    a, b = _normalise(left), _normalise(right)
    if a == b:
        return False
    for first, second in NEAR_MISS_BLOCKLIST:
        pair = {_normalise(first), _normalise(second)}
        if {a, b} == pair:
            return True
    if a in b or b in a:
        return True
    return False


def compare_requirements(
    requirements: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    *,
    evidence_source_label: str,
) -> list[dict[str, Any]]:
    index = _lookup(skills)
    results = []
    for req in requirements:
        name = _normalise(str(req.get("canonical_requirement") or req["requirement"]))
        if not req.get("normalized"):
            status = "review"
            why = (
                "This requirement needs review because the available evidence is not sufficient "
                "for a reliable automatic match."
            )
            evidence = ""
            section = ""
        elif name in index:
            item = index[name]
            status_flag = str(item.get("status") or "needs_review")
            excerpt = str(item.get("evidence_span") or "")
            section = str(item.get("source_section") or "")
            if status_flag in {"confirmed", "user-added"} and excerpt:
                status = "matched"
                why = "Confirmed evidence supports this canonical requirement."
            else:
                status = "partial"
                why = "Related evidence exists, but it is not a fully confirmed excerpt."
            evidence = excerpt[:280]
        else:
            status = "not evidenced"
            why = "The selected evidence source does not provide sufficient evidence for this requirement. That is not a claim that you lack the skill."
            evidence = ""
            section = ""
        results.append(
            {
                **req,
                "status": status,
                "supporting_evidence": evidence,
                "evidence_section": section,
                "evidence_source_label": evidence_source_label,
                "why": why,
            }
        )
    return results


def one_next_action(results: list[dict[str, Any]]) -> dict[str, str]:
    if not results:
        return {
            "title": "Review the job description manually",
            "description": "No supported requirements were confidently extracted. Compare the posting with your resume yourself.",
            "gap": "",
        }
    ranked: list[tuple[int, dict[str, Any]]] = []
    for row in results:
        status = row.get("status")
        priority = row.get("priority")
        if status == "not evidenced" and priority == "required":
            ranked.append((1, row))
        elif status == "partial" and priority == "required":
            ranked.append((2, row))
        elif status == "not evidenced" and priority == "preferred":
            ranked.append((3, row))
        elif status == "partial" and priority == "preferred":
            ranked.append((4, row))
        elif status == "review":
            ranked.append((5, row))
    ranked.sort(key=lambda item: (item[0], str(item[1].get("requirement") or "")))
    if not ranked:
        return {
            "title": "Keep evidence current",
            "description": "Covered requirements already have source evidence. Add newer project outcomes if the posting emphasizes them.",
            "gap": "",
        }
    _rank, row = ranked[0]
    req = row["requirement"]
    status = row.get("status")
    if status == "not evidenced":
        return {
            "title": f"Clarify evidence for {req}",
            "description": (
                f"If you have relevant {req} experience, add one concrete example to the selected evidence source. "
                "If this is a genuine gap, complete a small exercise and record the resulting evidence. "
                "Not evidenced means the selected source has no excerpt yet, not that you lack the skill."
            ),
            "gap": f"{req} is not evidenced in the selected source.",
        }
    if status == "review":
        return {
            "title": f"Review requirement: {req}",
            "description": "This requirement could not be confidently normalized. Compare it with your resume manually.",
            "gap": f"{req} needs manual review.",
        }
    return {
        "title": f"Strengthen evidence for {req}",
        "description": (
            f"If you already have {req} experience, add a measurable outcome or project example that more clearly demonstrates it. "
            "Do not invent experience you do not have."
        ),
        "gap": f"{req} is only partially evidenced.",
    }


def analyze_target_job(
    *,
    description: str,
    skills: list[dict[str, Any]],
    evidence_source_label: str = "Current evidence profile",
) -> dict[str, Any]:
    requirements = extract_requirements(description)
    compared = compare_requirements(requirements, skills, evidence_source_label=evidence_source_label)
    counts = {key: 0 for key in ("matched", "partial", "not evidenced", "review")}
    for row in compared:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    empty_note = ""
    if not compared:
        empty_note = (
            "No supported requirements were identified automatically. "
            "You can review the job description or add clearer requirement wording."
        )
    return {
        "requirements": compared,
        "counts": counts,
        "next_action": one_next_action(compared),
        "empty_extraction_note": empty_note,
        "evidence_source_label": evidence_source_label,
        "extraction_method": EXTRACTION_VERSION,
        "disclaimer": "Statuses describe evidence coverage in the selected source, not hiring probability or whether you possess a skill. Not evidenced is not a claim that you lack a skill. Target Job Match is not a complete ATS analysis.",
    }
