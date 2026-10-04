# CareerCorpus duplicate resume_id 35421497

Raw data was not modified. No training. No policy applied.

- Resume rows: 2 in `external_data/normalized/careercorpus/careercorpus_resumes.csv`
- Annotation rows: 2 in `external_data/normalized/careercorpus/careercorpus_annotations.csv`
- Compared content fields identical: 5
- Compared content fields different: 4

## Classification

two annotations for one resume (same career narrative, abbreviated vs expanded text, identical annotator_1_score, different annotator_2_score)

They are **not** byte-identical duplicates. They are **not** two unrelated people sharing an ID.
Row 172 is a longer statement of the same education, skills, and work history as row 173.
`annotator_1_score` is 0.73 on both rows. `annotator_2_score` is 0.79 vs 0.66.

## Field comparison (resumes)

| field | status | row 172 | row 173 |
| --- | --- | --- | --- |
| resume_id | identical | 35421497 | 35421497 |
| domain | identical | TEACHER | TEACHER |
| education | different | B.A. Childhood Education (1–6), Brooklyn College (2007), minor in Psychology; A.A. Liberal Arts, Nassau Community College (2003). | B.A. Childhood Education (1–6), Brooklyn College 2007; A.A. Liberal Arts, Nassau CC 2003; minor Psychology. |
| skills_and_achievements | different | Differentiated instruction, balanced literacy, classroom management, student assessment (running records, rubrics, portfolios), SEL-focused environment, family communication, lesso | Differentiated instruction, balanced literacy, classroom management, assessment, SEL, family communication, lesson planning, collaboration. Trilingual (English/Russian/Hebrew). Cer |
| experience | different | Teacher (Current)—builds inclusive, inquiry-based classrooms; adapts lessons; designs hands-on projects; guides social-emotional growth; partners with staff and families. Student T | Teacher (current)—inclusive, hands-on, adaptive lessons; Student Teacher, Grade 1 (2006–2007); Dentist Office Manager (2002–2012)—leadership, training, scheduling, insurance. |
| job_type | identical | Mid-level | Mid-level |
| source_sheet | identical | Sheet1 | Sheet1 |
| source_row_number | different | 172 | 173 |
| not_onet_task_label | identical | true | true |

## Annotation comparison

| field | row 172 | row 173 |
| --- | --- | --- |
| resume_id | 35421497 | 35421497 |
| annotator_1_score | 0.73 | 0.73 |
| annotator_2_score | 0.79 | 0.66 |
| source_row_number | 172 | 173 |
| label_source | CareerCorpus | CareerCorpus |

## Recommended policy (not applied)

- Keep both raw and normalized rows.
- Add a unique `record_id` such as `{resume_id}:{source_sheet}:{source_row_number}` (`35421497:Sheet1:172` and `35421497:Sheet1:173`).
- Preserve `resume_id=35421497` as the group key.
- For supervised role-matching or skill-extraction evaluation, split by `resume_id` (GroupKFold / GroupShuffleSplit), not by `record_id`.
- Do not put row 172 in train and row 173 in test.
- Do not drop either row until a later documented evaluation-set decision.

Do not invent O*NET task-exposure labels from these CareerCorpus annotator scores.

