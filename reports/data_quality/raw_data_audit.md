# Raw-data audit — 2026-10-02

Phase: complete dataset organization and raw-data audit.
Did not train, normalize, fill human labels, modify `data/` or `ml_models/`, delete duplicates, or commit.

## Verified paths

| Dataset | Exact path | Status |
|---|---|---|
| O*NET zip | `C:\4th project\external_data\raw\onet_31_0\onet_31_0_text.zip` | Present (13,183,034 bytes) |
| O*NET extract | `C:\4th project\external_data\raw\onet_31_0\db_31_0_text\` | Present, **46** `.txt` files (zip + extract = 47 artifacts) |
| ESCO | `C:\4th project\external_data\raw\esco\ESCO dataset - v1.2.1 - classification - en - csv\` | Present, version **1.2.1**, 19 CSV files |
| CareerCorpus (required) | `C:\4th project\external_data\raw\careercorpus\CareerCorpus.xlsx` | Present; copy not required |
| Historical canonical | `C:\4th project\external_data\raw\historical_benchmark\frey_osborne_historical_702_occupations.csv` | Present, 702 rows |
| Historical duplicate | `C:\4th project\external_data\raw\historical_benchmark\frey_osborne_historical_702_occupations.csv.csv` | Present; **not deleted** |
| BLS OEWS | `C:\4th project\external_data\raw\bls_oews\` | Missing (`.gitkeep` only) |
| BLS AI exposure | `C:\4th project\external_data\raw\bls_ai_exposure\` | Missing (`.gitkeep` only) |
| Blank task template | `C:\4th project\replacement_data\task_exposure_annotation_template.csv` | Present, 18,838 rows, 0 filled scores |
| Round-one annotations | `C:\4th project\project_data\task_exposure_labels\onet_task_annotations_round_1.csv` | Created this phase as an identical blank copy |
| Historical training table | `C:\4th project\replacement_data\occupation_training_table_historical_benchmark.csv` | Missing |

O*NET occupation dictionary (`Occupation Data.txt`) remains 1,016 rows. Task statements remain 18,838 rows.

## CareerCorpus copy action

The required file was already at `external_data/raw/careercorpus/CareerCorpus.xlsx`.
An extra source file exists and has the **same SHA-256**:

`C:\Users\Owner\Downloads\CareerCorpus  A Comprehensive Dataset of Annotated\CareerCorpus  A Comprehensive Dataset of Annotated\CareerCorpus.xlsx`

SHA-256: `97b1fa6cca1232912dd3f7bc312d71a2478249787168fd41dfbf6c1da90479d3`

No overwrite was performed.

## Historical duplicates (identical SHA-256)

Both files:

`5f4a78996cc5e5856c7277085a10a7ff3bea376435b7da4d7d9d3d7c3a7d474c`

1. `C:\4th project\external_data\raw\historical_benchmark\frey_osborne_historical_702_occupations.csv`
2. `C:\4th project\external_data\raw\historical_benchmark\frey_osborne_historical_702_occupations.csv.csv`

Keep both until a later cleanup approval. Use file (1) as the canonical input. File (2) is a Windows double-extension copy of the same bytes.

## How to regenerate the historical training table (do not run in this phase)

The missing file should be built later from the **canonical** CSV (not the `.csv.csv` duplicate) plus O*NET `Occupation Data.txt`, using the existing exact-match rule already implemented in `scripts/data_pipeline/build_replacement_label_tracks.py`:

1. Read `frey_osborne_historical_702_occupations.csv` (`_ - code`, `prob`/`probability`, `occupation`).
2. If the code is `##-####`, append `.00`. If it is already `##-####.##`, keep it. Do not fuzzy-match titles.
3. Inner-join to O*NET 31.0 `O*NET-SOC Code`.
4. Write mapped rows only to `replacement_data/occupation_training_table_historical_benchmark.csv` with metadata: `label_type=historical_occupation_computerisation_probability`, `label_source=Frey_Osborne`, `label_year=2013/2017`, `source_artifact=plotly_public_mirror`, `not_current_task_ground_truth=true`.
5. Keep the 84 unmatched rows in `replacement_data/unmatched_external_labels.csv`.
6. Do not copy `prob` onto task rows or into `onet_task_annotations_round_1.csv`.

`replacement_data/external_occupation_labels.csv` already holds the 618 exact mappings and can be the input to that writer. It is not a substitute name for the training table.

## ESCO raw names and schemas (row counts exclude header)

Folder: `external_data/raw/esco/ESCO dataset - v1.2.1 - classification - en - csv/`

| File | Rows | Header |
|---|---|---|
| occupations_en.csv | 3,043 | conceptType, conceptUri, iscoGroup, preferredLabel, altLabels, hiddenLabels, status, modifiedDate, regulatedProfessionNote, scopeNote, definition, inScheme, description, code, naceCode |
| skills_en.csv | 13,960 | conceptType, conceptUri, skillType, reuseLevel, preferredLabel, altLabels, hiddenLabels, status, modifiedDate, scopeNote, definition, inScheme, description |
| occupationSkillRelations_en.csv | 126,051 | occupationUri, occupationLabel, relationType, skillType, skillUri, skillLabel |
| broaderRelationsOccPillar_en.csv | 3,648 | conceptType, conceptUri, conceptLabel, broaderType, broaderUri, broaderLabel |
| broaderRelationsSkillPillar_en.csv | 20,819 | conceptType, conceptUri, conceptLabel, broaderType, broaderUri, broaderLabel |
| conceptSchemes_en.csv | 20 | conceptType, conceptSchemeUri, preferredLabel, title, status, description, hasTopConcept |
| dictionary_en.csv | 160 | filename, data header, property, description |
| digCompSkillsCollection_en.csv | 25 | conceptType, conceptUri, preferredLabel, status, skillType, reuseLevel, altLabels, description, broaderConceptUri, broaderConceptPT |
| digitalSkillsCollection_en.csv | 1,284 | (same collection schema as digComp) |
| greenShareOcc_en.csv | 3,590 | conceptType, conceptUri, code, preferredLabel, greenShare |
| greenSkillsCollection_en.csv | 629 | collection schema |
| ISCOGroups_en.csv | 619 | conceptType, conceptUri, code, preferredLabel, status, altLabels, inScheme, description |
| languageSkillsCollection_en.csv | 359 | collection schema |
| researchOccupationsCollection_en.csv | 122 | conceptType, conceptUri, preferredLabel, status, altLabels, description, broaderConceptUri, broaderConceptPT |
| researchSkillsCollection_en.csv | 40 | collection schema |
| skillGroups_en.csv | 640 | conceptType, conceptUri, preferredLabel, altLabels, hiddenLabels, status, modifiedDate, scopeNote, inScheme, description, code |
| skillsHierarchy_en.csv | 640 | Level 0–3 URI/term/code, Description, Scope note |
| skillSkillRelations_en.csv | 5,818 | originalSkillUri, originalSkillType, relationType, relatedSkillType, relatedSkillUri |
| transversalSkillsCollection_en.csv | 95 | collection schema |

There is no `esco_1.2.0_en_csv.zip` in the repo. Raw ESCO is already extracted at v1.2.1.

## CareerCorpus sheet names and schema

File: `external_data/raw/careercorpus/CareerCorpus.xlsx`

- Sheets: `Sheet1` only
- Header: `ID`, `Domain`, `Education`, `Skills and Achievements`, `Experience`, `Job_type`, `Annotator-1`, `Annotator-2`
- Data rows: **998**
- `Annotator-1` / `Annotator-2` are CareerCorpus resume annotations, not O*NET task-exposure labels

## Round-one annotation file

Copied without filling scores:

- Source: `replacement_data/task_exposure_annotation_template.csv`
- Destination: `project_data/task_exposure_labels/onet_task_annotations_round_1.csv`
- SHA-256 (both): `07e483677d52ba24f42efcd6155195f7715bd43b18e3e513057b586ecd3e3a72`
- Human-filled reviewer/adjudicated scores: **zero**
