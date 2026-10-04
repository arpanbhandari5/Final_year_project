# Historical benchmark table build report

Generated at: 2026-10-02T07:52:28.142093+00:00
Transformation version: `historical-benchmark-table-v1.0`

This table is an **occupation-level historical computerisation benchmark**, not current task ground truth and not a personal job-loss probability.
The 84 unmatched Frey–Osborne rows were **not** fuzzy-matched and are not in this table.

## Inputs

| file | sha256 |
| --- | --- |
| replacement_data/occupation_master.csv | 4cd1b75dff128d9a912082a193ff2f5c6f616b4fef53e16dc3401bfc3062015d |
| replacement_data/external_occupation_labels.csv | f74dc6b78abe9d3a448bacf2e1b14a195e8ea8bc0420264cc9be8c7f696000e3 |
| replacement_data/unmatched_external_labels.csv | 73b8c71bf54d20b49e91726d95b32e7a39196526e83a3b69e2985444a145877a |
| external_data/raw/onet_31_0/db_31_0_text/Task Statements.txt | aee1788c7ce2ebf19c1700bc4a1d7aa69a59965736d56a521945256df3f68d08 |
| external_data/raw/onet_31_0/db_31_0_text/Software Skills.txt | 3fd63fb00251af89bf55eb1d24986e654ff61d0e5214fc238fbb56da7b4c4f4c |
| external_data/raw/onet_31_0/db_31_0_text/Essential Skills.txt | 91ef60f7e43231136d08e8234f1624883a0ee7b951510d11851c693a2f8edea9 |
| external_data/raw/onet_31_0/db_31_0_text/Transferable Skills.txt | 7bb190ea7e58192ebd024a6775684b1d3b0216f45194669f0bf5854b2fac6596 |

## Output

- Path: `replacement_data/occupation_training_table_historical_benchmark.csv`
- SHA-256: `9f8c7cf38d487e19cd99f126dc03d6d6eaf77ec0aab406fe67f5a507b2e97e10`
- Row count: 618
- Unmatched historical rows left out: 84
- Duplicate occupation_code extra rows: 0
- Missing occupation_master join: 0
- Missing target: 0
- Target outside 0-1: 0
- Occupations with zero task statements: 11
- Target min/max/mean: 0.0028 / 0.9900 / 0.5426

Join key: exact `mapped_onet_soc_code` = `O*NET-SOC Code`. Essential and transferable skill names use Scale ID `IM` only.
Do not train a production model from this table. Do not copy these probabilities onto O*NET task annotation rows.

