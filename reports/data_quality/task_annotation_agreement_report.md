# Task annotation agreement report (AI-pass agreement / AI self-consistency)

Generated at: 2026-10-02T09:31:09.477326+00:00

**These metrics are not human inter-rater reliability and do not establish label accuracy.**
They measure agreement between two AI scoring passes before score resolution.

Quadratic weighted Cohen's kappa is the principal **ordinal** statistic.
Implementation: sklearn `cohen_kappa_score(..., weights='quadratic')` on ranks 0.00=0, 0.25=1, 0.50=2, 0.75=3, 1.00=4.
Gwet's AC1 is a supplementary **nominal** statistic (Gwet 2008) on the same five categories treated as nominal. Assumptions: two raters, q=5 known categories, complete paired cases only. It is not an ordinal weighted measure.
Operational threshold: quadratic kappa >= 0.70. Outcome: **met** (0.9120).
Meeting the threshold is not evidence that labels are correct or human-valid.

| metric | value | denominator |
| --- | --- | --- |
| original tasks | 250 | sample rows |
| valid paired original scores | 250 | tasks with two valid nonblank scores |
| exact agreement | 0.8240 | 250 |
| mean absolute disagreement | 0.0440 | 250 |
| quadratic weighted kappa | 0.9120 | 250 |
| Gwet AC1 (nominal) | 0.7854 | 250 |
| disagreement > 0.30 | 0 | 250 |
| missing/invalid original scores | 0 | 250 |
| identical (Case A) | 206 | 250 |
| deterministic mean+snap (Case B) | 44 | 250 |
| AI adjudication (Case C) | 0 | 250 |
| unresolved/incomplete | 0 | 250 |

### Disagreement distribution

| |r1-r2| | n |
| --- | --- |
| 0.00 | 206 |
| 0.25 | 44 |

### Pass 1 original distribution

| score | n |
| --- | --- |
| 0.00 | 86 |
| 0.25 | 67 |
| 0.50 | 81 |
| 0.75 | 16 |
| 1.00 | 0 |

### Pass 2 original distribution

| score | n |
| --- | --- |
| 0.00 | 71 |
| 0.25 | 78 |
| 0.50 | 69 |
| 0.75 | 29 |
| 1.00 | 3 |

### Final eligible training-score distribution (one row per task group)

| score | n |
| --- | --- |
| 0.00 | 86 |
| 0.25 | 66 |
| 0.50 | 81 |
| 0.75 | 15 |
| 1.00 | 0 |

## Confidence assignment (heuristic operational indicators, not calibrated probabilities)

- identical reviewer scores: 1.00
- deterministic mean, |r1-r2| = 0.25 (or <= 0.25): 0.85
- deterministic mean, 0.25 < |r1-r2| <= 0.30: 0.70
- AI-adjudicated: 0.60
- unresolved/incomplete: blank

On the permitted 5-point grid the only Case B difference that occurs is 0.25.

No Case C independent AI adjudication was applied in this run because no paired disagreement exceeded 0.30. Independence of the original two JSONL passes is supported by separate files, different score encodings, and mostly distinct rationales (2 identical rationale strings of 250).
That is not a proof of isolated human review.

