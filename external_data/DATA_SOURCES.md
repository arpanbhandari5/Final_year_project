# External data sources

Download date recorded in this file: 2026-10-02.

Hashes are filled after `scripts/data_pipeline/download_raw_sources.py` succeeds. Raw zip archives stay under `external_data/raw/` and are not mixed into `data/`.

## O*NET 31.0

- Dataset name: O*NET 31.0 Database (text/CSV archive)
- Source URL: https://www.onetcenter.org/database.html
- Download URL: https://www.onetcenter.org/dl_files/database/db_31_0_text.zip
- Dictionary: https://www.onetcenter.org/dictionary/31.0/csv/occupation_data.html
- Download date: 2026-10-02
- Release/version: 31.0
- Licence: CC BY 4.0
- Local filename: `external_data/raw/onet_31_0/onet_31_0_text.zip`
- SHA-256 hash: `6883548adf5fde64cf6f801b35d15519c9225f2732c3cab0e281c652d16b23a9`
- Transformation script: `scripts/data_pipeline/download_raw_sources.py`; extract via `scripts/data_pipeline/build_replacement_label_tracks.py`
- Known limitations: U.S. occupational taxonomy; quarterly snapshot; not a personal outcome dataset; derived files must retain attribution

Attribution:

> This product includes information from the O*NET 31.0 Database by the U.S. Department of Labor, Employment and Training Administration (USDOL/ETA). Used under the CC BY 4.0 license. O*NET® is a trademark of USDOL/ETA. The project modified or aggregated some of this information. USDOL/ETA has not approved, endorsed, or tested these modifications.

## Historical Frey–Osborne occupation table

- Dataset name: job-automation-probability (702 occupations)
- Methodology: Frey, C. B., & Osborne, M. A. (2013/2017), *The Future of Employment*
- Oxford Martin URL: https://www.oxfordmartin.ox.ac.uk/publications/the-future-of-employment
- Download URL: https://raw.githubusercontent.com/plotly/datasets/master/job-automation-probability.csv
- Download date: 2026-10-02
- Release/version: 2013/2017 methodology; Plotly public mirror of a 2016-era SOC table
- Licence: treat as a public research table mirrored by Plotly; cite Frey & Osborne; not O*NET
- Local filename: `external_data/raw/historical_benchmark/frey_osborne_historical_702_occupations.csv`
- SHA-256 hash: `5f4a78996cc5e5856c7277085a10a7ff3bea376435b7da4d7d9d3d7c3a7d474c`
- Transformation script: `scripts/data_pipeline/build_replacement_label_tracks.py` (exact `.00` append only)
- Known limitations: occupation-level computerisation probability; can overestimate automatability (OECD task-based caution); not current task ground truth; 84 rows expected to remain unmatched without fuzzy matching; `source_artifact=plotly_public_mirror`

## OECD caution (not a training file)

- URL: https://www.oecd.org/en/publications/the-risk-of-automation-for-jobs-in-oecd-countries_5jlz9h56dvq7-en.html
- Use: methodological warning only
- Do not download into the training tables
- Known limitations: occupation-based labels should not be mixed with O*NET tasks and described as current task-level labels

## ESCO v1.2.1 (raw, not normalized)

- Dataset name: ESCO classification English CSV
- Local folder: `external_data/raw/esco/ESCO dataset - v1.2.1 - classification - en - csv/`
- Version: 1.2.1 (folder name; no `esco_1.2.0_en_csv.zip` in this checkout)
- Occupations: 3,043 rows in `occupations_en.csv`
- Skills: 13,960 rows in `skills_en.csv`
- Occupation-skill relations: 126,051 rows in `occupationSkillRelations_en.csv`
- Transformation script: none in this phase (raw audit only)
- Known limitations: European classification; not an automation-risk target; join later on ESCO URIs, not titles

## CareerCorpus (raw, not normalized)

- Dataset name: CareerCorpus annotated resumes
- Required local filename: `external_data/raw/careercorpus/CareerCorpus.xlsx` (present)
- SHA-256: `97b1fa6cca1232912dd3f7bc312d71a2478249787168fd41dfbf6c1da90479d3`
- Extra identical copy (not deleted): `C:\Users\Owner\Downloads\CareerCorpus  A Comprehensive Dataset of Annotated\CareerCorpus  A Comprehensive Dataset of Annotated\CareerCorpus.xlsx`
- Sheet: `Sheet1`; 998 data rows; columns `ID`, `Domain`, `Education`, `Skills and Achievements`, `Experience`, `Job_type`, `Annotator-1`, `Annotator-2`
- Known limitations: resume/domain classification sample, not a full occupational census; annotator columns are CareerCorpus labels, not O*NET task-exposure scores

## Missing in this phase

- BLS OEWS (`external_data/raw/bls_oews/` contains only `.gitkeep`)
- BLS AI exposure (`external_data/raw/bls_ai_exposure/` contains only `.gitkeep`)
- `replacement_data/occupation_training_table_historical_benchmark.csv` (not generated; regenerate later from the canonical historical CSV)

## Production files left unchanged

- `data/automation_risk.csv`
- `ml_models/model.pkl`
- `ml_models/automation_model.pkl`
