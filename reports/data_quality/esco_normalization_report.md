# ESCO normalization report

Generated at: 2026-10-02T07:37:45.973589+00:00
Source version: 1.2.1
Transformation version: `norm-v1.0-esco-careercorpus`

ESCO is normalized for skill/occupation identifiers only. It is not an automation-risk target.
Rows are retained unless every identity field is empty. Invalid URIs are counted and kept.

| output | input rows | output rows | excluded | invalid identifier fields | duplicate identity values |
| --- | --- | --- | --- | --- | --- |
| esco_occupations.csv | 3043 | 3043 | 0 | 0 | 4 |
| esco_skills.csv | 13960 | 13960 | 0 | 0 | 21 |
| esco_occupation_skill_relations.csv | 126051 | 126051 | 0 | 0 | 0 |
| esco_skill_relations.csv | 5818 | 5818 | 0 | 0 | 0 |

## esco_occupations.csv

- Input path: `external_data/raw/esco/ESCO dataset - v1.2.1 - classification - en - csv/occupations_en.csv`
- Input SHA-256: `8034348d84b6d1dd24a5bcf9609186ecbba0a85457ee2eacd65bddec33a51b4a`
- Output path: `external_data/normalized/esco/esco_occupations.csv`
- Exclusion log: `external_data/normalized/esco/esco_occupations_excluded.csv`
- Input row count: 3043
- Output row count: 3043
- Excluded row count: 0
- Column names: `esco_occupation_uri`, `esco_occupation_code`, `isco_group`, `preferred_label`, `alt_labels`, `hidden_labels`, `status`, `modified_date`, `definition`, `description`, `concept_type`, `in_scheme`, `nace_code`, `regulated_profession_note`, `scope_note`, `source_version`, `transformation_version`, `source_licence_note`
- Invalid identifier counts: 0
- Duplicate identifier values: 4
- Extra rows due to duplicates: 4
- Duplicate URIs retained from source: `4d27152a-a8ee-4f5a-9f93-a2fb4fb2b2e3`, `5d601b40-7e0e-404e-bbff-bb98e147437c`, `ad404c6b-291f-439e-9ad4-c93ddabd3c13`, `b4bff870-5c8f-4c33-b07f-f04d79830633`
- Transformation version: `norm-v1.0-esco-careercorpus`
- Source version: `1.2.1`

Missing-value counts:

| column | missing |
| --- | --- |
| esco_occupation_uri | 0 |
| esco_occupation_code | 0 |
| isco_group | 0 |
| preferred_label | 0 |
| alt_labels | 0 |
| hidden_labels | 3035 |
| status | 0 |
| modified_date | 0 |
| definition | 3035 |
| description | 0 |
| concept_type | 0 |
| in_scheme | 0 |
| nace_code | 0 |
| regulated_profession_note | 0 |
| scope_note | 2733 |
| source_version | 0 |
| transformation_version | 0 |
| source_licence_note | 0 |

Excluded rows: none.


## esco_skills.csv

- Input path: `external_data/raw/esco/ESCO dataset - v1.2.1 - classification - en - csv/skills_en.csv`
- Input SHA-256: `d03b10efca94b4bcfa260a992cfde89c375f0fa12095d6662a663cfd2f9f2950`
- Output path: `external_data/normalized/esco/esco_skills.csv`
- Exclusion log: `external_data/normalized/esco/esco_skills_excluded.csv`
- Input row count: 13960
- Output row count: 13960
- Excluded row count: 0
- Column names: `esco_skill_uri`, `skill_type`, `reuse_level`, `preferred_label`, `alt_labels`, `hidden_labels`, `status`, `modified_date`, `definition`, `description`, `concept_type`, `in_scheme`, `scope_note`, `source_version`, `transformation_version`, `source_licence_note`
- Invalid identifier counts: 0
- Duplicate identifier values: 21
- Extra rows due to duplicates: 21
- Transformation version: `norm-v1.0-esco-careercorpus`
- Source version: `1.2.1`

Missing-value counts:

| column | missing |
| --- | --- |
| esco_skill_uri | 0 |
| skill_type | 5 |
| reuse_level | 5 |
| preferred_label | 0 |
| alt_labels | 18 |
| hidden_labels | 13807 |
| status | 0 |
| modified_date | 0 |
| definition | 13958 |
| description | 0 |
| concept_type | 0 |
| in_scheme | 0 |
| scope_note | 13724 |
| source_version | 0 |
| transformation_version | 0 |
| source_licence_note | 0 |

Excluded rows: none.


## esco_occupation_skill_relations.csv

- Input path: `external_data/raw/esco/ESCO dataset - v1.2.1 - classification - en - csv/occupationSkillRelations_en.csv`
- Input SHA-256: `e1a46511f0ef4d505f106f1d41f528ef76d289f93e59d4d0cbaac38986102c44`
- Output path: `external_data/normalized/esco/esco_occupation_skill_relations.csv`
- Exclusion log: `external_data/normalized/esco/esco_occupation_skill_relations_excluded.csv`
- Input row count: 126051
- Output row count: 126051
- Excluded row count: 0
- Column names: `esco_occupation_uri`, `occupation_label`, `relation_type`, `skill_type`, `esco_skill_uri`, `skill_label`, `source_version`, `transformation_version`, `source_licence_note`
- Invalid identifier counts: 0
- Duplicate identifier values: 0
- Extra rows due to duplicates: 0
- Transformation version: `norm-v1.0-esco-careercorpus`
- Source version: `1.2.1`

Missing-value counts:

| column | missing |
| --- | --- |
| esco_occupation_uri | 0 |
| occupation_label | 0 |
| relation_type | 0 |
| skill_type | 59 |
| esco_skill_uri | 0 |
| skill_label | 0 |
| source_version | 0 |
| transformation_version | 0 |
| source_licence_note | 0 |

Excluded rows: none.


## esco_skill_relations.csv

- Input path: `external_data/raw/esco/ESCO dataset - v1.2.1 - classification - en - csv/skillSkillRelations_en.csv`
- Input SHA-256: `64a5f8fb7b8dda4932ff06db4738ce1beed3906e45a49b14453349056c609439`
- Output path: `external_data/normalized/esco/esco_skill_relations.csv`
- Exclusion log: `external_data/normalized/esco/esco_skill_relations_excluded.csv`
- Input row count: 5818
- Output row count: 5818
- Excluded row count: 0
- Column names: `original_skill_uri`, `original_skill_type`, `relation_type`, `related_skill_type`, `related_skill_uri`, `source_version`, `transformation_version`, `source_licence_note`
- Invalid identifier counts: 0
- Duplicate identifier values: 0
- Extra rows due to duplicates: 0
- Transformation version: `norm-v1.0-esco-careercorpus`
- Source version: `1.2.1`

Missing-value counts:

| column | missing |
| --- | --- |
| original_skill_uri | 0 |
| original_skill_type | 0 |
| relation_type | 0 |
| related_skill_type | 0 |
| related_skill_uri | 0 |
| source_version | 0 |
| transformation_version | 0 |
| source_licence_note | 0 |

Excluded rows: none.

