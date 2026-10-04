# Occupation confirmation security

Production confirmation no longer trusts a client-supplied `verified_occupation_code`, title, `confirmation_method`, or allowlist flags. The browser may send only server-issued identifiers (candidate confirm) or a code chosen from the server allowlist (manual select).

## Allowlist

Selectable occupations are the exact-code intersection of:

- `project_data/occupation_selection/occupation_master_800.csv`
- `experiments/task_exposure/data/public_benchmark/public_gpts_are_gpts_benchmark.csv`

Inventory (computed from those files; flags are never taken from the client):

| Metric | Count |
| --- | ---: |
| 800 source rows | 800 |
| Unique 800 occupation codes | 800 |
| Duplicate 800 codes | 0 |
| Invalid SOC codes | 0 |
| Missing titles | 0 |
| 800 codes with published benchmark coverage | 800 |
| 800 codes without published benchmark coverage | 0 |
| Selectable codes (`800 ∩ benchmark`, unique, titled) | 800 |

Duplicate benchmark occupation codes collapse to one selectable record per canonical code. Research-only codes that appear in the 923-row published benchmark but not in the 800 product file are not selectable and cannot authorize verified lookup.

## Session records

On successful upload or analyze-stream the server stores at most two pending analysis records in the signed Flask session:

- `analysis_id`, `candidate_id`
- server-issued `candidate_code` / `candidate_title` / matcher score
- `created_at`, `expires_at` (1 hour)
- session nonce; authenticated `user_id` when logged in
- `consumed` after a successful confirm or select

Resume text, filenames, extracted paragraphs, skill arrays, Ollama prompts, and benchmark task tables are not stored in the cookie.

Confirm requires the current session (and user, when bound), matching `candidate_id`, an unexpired unconsumed record, and 800∩benchmark coverage of the **stored** candidate code.

## Endpoints

| Method | Path | Client fields used |
| --- | --- | --- |
| GET | `/api/occupations/selectable` | none (titles and codes from server files) |
| POST | `/api/confirm-occupation` | `analysis_id`, `candidate_id`, `action=confirm_candidate` |
| POST | `/api/select-occupation` | `analysis_id`, `selected_code`, `action=select_occupation` |

Ignored if sent: `verified_occupation_code`, client titles, `confirmation_method`, `in_product_800`, `benchmark_coverage`.

Provenance after success:

- Candidate confirm: `confirmation_method=candidate_confirmation`, `source=server_issued_candidate`
- Manual select: `confirmation_method=user_selected_occupation`, `source=user_selection`

A 923-only code returns `status=unavailable`, `product_coverage_available=false`. CSRF remains enabled via Flask-WTF (`X-CSRFToken`).
