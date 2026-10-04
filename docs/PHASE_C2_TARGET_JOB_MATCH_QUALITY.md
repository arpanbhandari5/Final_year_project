# Phase C.2 — Target Job Match quality

Date: 2026-10-04. No Git commit or push.

## Purpose

Improve the existing Target Job Match loop without adding a tracker, LLM, ATS score, or hiring prediction.

```text
evidence source
→ target job
→ requirements
→ evidence comparison
→ gap
→ one next action
```

## Workflow

The user selects a supported evidence source, pastes a job description, reviews extracted requirements, inspects evidence excerpts, and receives one immediate action grounded in a gap.

## Evidence semantics

- **matched:** confirmed/user-added excerpt supports the same canonical requirement (including conservative aliases such as Postgres → PostgreSQL).
- **partial:** the same canonical requirement has related but unconfirmed evidence.
- **not evidenced:** the selected source does not provide sufficient evidence. This is **not** “the user does not have the skill.”
- **review:** the phrase could not be normalized or compared confidently.

Near-miss concepts are **not** equated. Java is not JavaScript. SQL evidence is not PostgreSQL. AWS is not generic cloud. Excel is not every spreadsheet. Machine learning is not every data-analysis task.

## Source provenance

Selectable sources:

- **Current evidence profile:** stored `ResumeProfile.extracted_skills` for the authenticated user. This is **not** a fresh reparse of an uploaded file.
- **Owned resume version:** `ResumeVersion` text owned by the session user, scanned with the Target Job Match vocabulary.

The UI states: **This analysis used the following evidence source:** followed by the server-derived label. Client `user_id`, `owner_id`, `is_owner`, and `evidence_source_label` are ignored.

The comparison snapshot is stored on the match row (`result_json`) with `resume_version_id` when used. Re-submitting the same description hash and evidence key updates that row (C.1 Option B). A deleted resume version cannot be selected for a new comparison (404). Existing match snapshots remain readable by the owner.

## Requirement extraction

Dedicated vocabulary in `job_requirement_vocabulary.py` (`extraction_method=tjm-vocabulary-c2`). `risk_assessor._extract_skills` is not expanded.

C.2 addition: **Kubernetes** (`kubernetes`, `k8s`) with a false-positive test against ordinary English such as “asks”.

Ambiguous education/experience phrases remain **review**. Short tokens R/C/Go still need programming context.

## Next action

Deterministic priority (stable name order within a rank):

1. required + not evidenced
2. required + partial
3. preferred + not evidenced
4. preferred + partial
5. review

Wording tells the user to add evidence **if they have** the experience, or to record a genuine learning exercise. It does not instruct them to fabricate credentials or predict hiring.

## Quality evaluation

`tests/test_target_job_match_quality.py` is a set of **deterministic regression/quality fixtures**. It is **not** a production accuracy benchmark. Do not cite those counts as model performance.

## Privacy

Unchanged from C.1: job text is stored privately for reopen, deleted with the match, not exported, not written to logs. Maximum length remains 20,000 characters.

## Limitations

- Not an ATS, hiring, employment, or job-loss predictor
- No application submission or scraping
- No cloud LLM
- Conservative vocabulary; many posting phrases stay `review`
- Profile source is stored extracted evidence, not a live file reparse
- Evidence correction remains the workspace evidence-profile flow; C.2 does not add a separate match-correction UI
