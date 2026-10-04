# CareerCorpus normalization report

Generated at: 2026-10-02T07:42:25.331487+00:00
Input path: `external_data/raw/careercorpus/CareerCorpus.xlsx`
Input SHA-256: `97b1fa6cca1232912dd3f7bc312d71a2478249787168fd41dfbf6c1da90479d3`
Source version: `CareerCorpus-xlsx-raw`
Transformation version: `norm-v1.0-esco-careercorpus`

Workbook sheets inspected:

| sheet | xml rows | data rows | header |
| --- | --- | --- | --- |
| Sheet1 | 999 | 998 | ID, Domain, Education, Skills and Achievements, Experience, Job_type, Annotator-1, Annotator-2 |

CareerCorpus annotator scores are resume-domain labels, not O*NET task-exposure labels.
Resume text and annotation scores are written to separate files. No O*NET task labels were filled.

| output | input rows | output rows | invalid resume_id values | duplicate resume_id values |
| --- | --- | --- | --- | --- |
| careercorpus_resumes.csv | 998 | 302 | 0 | 1 |
| careercorpus_annotations.csv | 998 | 302 | 0 | 1 |

Excluded row count: 696
Invalid annotation value counts: 0
Duplicate `resume_id` retained: `35421497` appears on Sheet1 rows 172 and 173 (both TEACHER). Neither row was dropped.
Exclusion log: `external_data/normalized/careercorpus/careercorpus_excluded.csv`

## careercorpus_resumes.csv

- Output path: `external_data/normalized/careercorpus/careercorpus_resumes.csv`
- Column names: `resume_id`, `domain`, `education`, `skills_and_achievements`, `experience`, `job_type`, `source_sheet`, `source_row_number`, `source_version`, `transformation_version`, `not_onet_task_label`

Missing-value counts:

| column | missing |
| --- | --- |
| resume_id | 0 |
| domain | 0 |
| education | 0 |
| skills_and_achievements | 0 |
| experience | 0 |
| job_type | 0 |
| source_sheet | 0 |
| source_row_number | 0 |
| source_version | 0 |
| transformation_version | 0 |
| not_onet_task_label | 0 |

## careercorpus_annotations.csv

- Output path: `external_data/normalized/careercorpus/careercorpus_annotations.csv`
- Column names: `resume_id`, `annotator_1_score`, `annotator_2_score`, `label_source`, `source_sheet`, `source_row_number`, `source_version`, `transformation_version`, `not_onet_task_label`

Missing-value counts:

| column | missing |
| --- | --- |
| resume_id | 0 |
| annotator_1_score | 0 |
| annotator_2_score | 0 |
| label_source | 0 |
| source_sheet | 0 |
| source_row_number | 0 |
| source_version | 0 |
| transformation_version | 0 |
| not_onet_task_label | 0 |

Excluded rows (complete list is in the exclusion log):

- Sheet1 rows 304-999: empty_row (696 rows). Full list: `external_data/normalized/careercorpus/careercorpus_excluded.csv`
