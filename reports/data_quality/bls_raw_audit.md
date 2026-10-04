# BLS raw-data audit — 2026-10-02

Phase: audit BLS data only. No training, normalization, or production edits.

## Result

Both BLS datasets are **missing**. Only placeholder files exist:

| Expected dataset | Path | Contents |
|---|---|---|
| BLS OEWS | `external_data/raw/bls_oews/` | `.gitkeep` only |
| BLS AI exposure | `external_data/raw/bls_ai_exposure/` | `.gitkeep` only |

No filename, release year, geography, SOC version, row count, columns, missing values, suppression symbols, duplicate SOC codes, source URL, licence, or SHA-256 can be reported until the files are placed.

Place them as:

- `external_data/raw/bls_oews/bls_oews_may_2025_national.zip`
- `external_data/raw/bls_ai_exposure/bls_ai_exposure_categories_2025_2035.xlsx`

Then re-run the BLS audit phase. Do not treat wages or BLS AI categories as task-exposure labels.
