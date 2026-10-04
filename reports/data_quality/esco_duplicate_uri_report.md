# ESCO duplicate URI report

Raw ESCO files were not modified. Normalized rows were not deleted. No training.

Source: `external_data/normalized/esco/esco_occupations.csv` and `esco_skills.csv`.

## Recommendation (not applied)

Preferred labels, codes, and descriptions match within each duplicate URI pair.
The only conflicting field is `modified_date` (July 2025 vs November 2025 timestamps).

Preserve all source rows in `norm-v1.0`. For later feature joins, collapse to one row per URI by keeping the **latest** `modified_date`. Do not edit raw ESCO files. Do not silently drop rows from the auditable normalized snapshot.

## Duplicate occupation URIs

- Duplicate esco_occupation_uri values: 4
- URI groups that are identical extra copies: 0
- URI groups with at least one conflicting field: 4

### http://data.europa.eu/esco/occupation/4d27152a-a8ee-4f5a-9f93-a2fb4fb2b2e3

- Preferred label: early years teaching assistant
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:38:59.122Z', '2025-11-26T10:02:16.164Z']

### http://data.europa.eu/esco/occupation/5d601b40-7e0e-404e-bbff-bb98e147437c

- Preferred label: legal policy officer
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:38:50.084Z', '2025-11-26T10:02:36.927Z']

### http://data.europa.eu/esco/occupation/ad404c6b-291f-439e-9ad4-c93ddabd3c13

- Preferred label: mining, construction and civil engineering machinery distribution manager
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:40:29.933Z', '2025-11-26T10:03:23.138Z']

### http://data.europa.eu/esco/occupation/b4bff870-5c8f-4c33-b07f-f04d79830633

- Preferred label: food service worker
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:41:03.211Z', '2025-11-26T10:03:40.525Z']

| uri suffix | n | preferred_label | verdict |
| --- | --- | --- | --- |
| occupation/4d27152a-a8ee-4f5a-9f93-a2fb4fb2b2e3 | 2 | early years teaching assistant | conflict: modified_date |
| occupation/5d601b40-7e0e-404e-bbff-bb98e147437c | 2 | legal policy officer | conflict: modified_date |
| occupation/ad404c6b-291f-439e-9ad4-c93ddabd3c13 | 2 | mining, construction and civil engineering machinery distribution manager | conflict: modified_date |
| occupation/b4bff870-5c8f-4c33-b07f-f04d79830633 | 2 | food service worker | conflict: modified_date |

## Duplicate skill URIs

- Duplicate esco_skill_uri values: 21
- URI groups that are identical extra copies: 0
- URI groups with at least one conflicting field: 21

### http://data.europa.eu/esco/skill/11dc8e6b-dffa-42e4-9de1-c47293a848ff

- Preferred label: operate pumping equipment
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:41:33.786Z', '2025-11-26T10:07:57.331Z']

### http://data.europa.eu/esco/skill/1258cc12-37bb-4a12-b219-9c3d6b294533

- Preferred label: work in an organised manner
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:42:24.033Z', '2025-11-26T10:08:15.494Z']

### http://data.europa.eu/esco/skill/1330576d-b3c7-4776-94cb-b7bd92d62993

- Preferred label: implement airport emergency plans
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:42:50.86Z', '2025-11-26T10:08:32.133Z']

### http://data.europa.eu/esco/skill/19c610ff-f8eb-44e1-9f83-0e130303643c

- Preferred label: assess data collected to improve community arts programme
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:43:13.798Z', '2025-11-26T10:09:22.019Z']

### http://data.europa.eu/esco/skill/1b9899a4-5b50-44b0-a21a-e2f86c51ac5a

- Preferred label: assess physical conditions of clients
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:43:45.519Z', '2025-11-26T10:10:19.028Z']

### http://data.europa.eu/esco/skill/30e0f65f-82b9-458d-b454-fba8f7d6a24b

- Preferred label: manage game management plans
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:44:05.259Z', '2025-11-26T10:12:20.677Z']

### http://data.europa.eu/esco/skill/51b4a8c4-6af7-41b7-a68d-f3c2fd63c9ec

- Preferred label: de-limb trees
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:44:46.321Z', '2025-11-26T10:14:19.526Z']

### http://data.europa.eu/esco/skill/598de5b0-5b58-4ea7-8058-a4bc4d18c742

- Preferred label: SQL
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:45:14.168Z', '2025-11-26T10:14:58.688Z']

### http://data.europa.eu/esco/skill/5ad31f50-15ca-4940-8db3-2104c9b79d0b

- Preferred label: assist the veterinary surgeon as a scrub nurse
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:45:45.976Z', '2025-11-26T10:15:19.642Z']

### http://data.europa.eu/esco/skill/61844a55-4103-4bf2-afcf-08e4ee120928

- Preferred label: urogynaecology
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:46:02.962Z', '2025-11-26T10:16:12.574Z']

### http://data.europa.eu/esco/skill/669fd6f4-92a8-4ed7-8cf9-48cd3fca4f20

- Preferred label: build miniature sets
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:46:18.046Z', '2025-11-26T10:16:39.051Z']

### http://data.europa.eu/esco/skill/72a109e1-df31-4f08-81d1-2baef60dac74

- Preferred label: coordinate closing room in footwear manufacturing
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:46:43.643Z', '2025-11-26T10:17:35.181Z']

### http://data.europa.eu/esco/skill/76731933-dad3-4053-aba3-d3ed6160b580

- Preferred label: perform pediatric surgery
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:47:00.829Z', '2025-11-26T10:18:20.255Z']

### http://data.europa.eu/esco/skill/933e7ccf-5d56-46ba-aca4-857f826a6b3a

- Preferred label: administer appointments
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:47:16.283Z', '2025-11-26T10:21:07.894Z']

### http://data.europa.eu/esco/skill/9a825ed0-6186-4e18-9db7-6975e9d70dea

- Preferred label: weld mining machinery
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:47:36.048Z', '2025-11-26T10:21:56.542Z']

### http://data.europa.eu/esco/skill/9d00803f-5dde-4803-8111-416ed174676f

- Preferred label: immobilise patients for emergency intervention
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:48:00.12Z', '2025-11-26T10:22:09.434Z']

### http://data.europa.eu/esco/skill/a6bbc19a-381c-4c60-a79a-41dea2d1a422

- Preferred label: drive agricultural machines
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:48:14.958Z', '2025-11-26T10:23:04.78Z']

### http://data.europa.eu/esco/skill/b65691e8-1b0f-4593-8d18-9ebb66e10383

- Preferred label: monitor roasting
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:48:42.826Z', '2025-11-26T10:25:10.058Z']

### http://data.europa.eu/esco/skill/b77b7ac5-f25f-4baf-8e49-dcd4f31899f2

- Preferred label: contribute to public health campaigns
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:49:11.725Z', '2025-11-26T10:25:22.393Z']

### http://data.europa.eu/esco/skill/b7e57889-a84f-440c-9e60-459aa69979e9

- Preferred label: analyse supply chain trends
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:51:18.351Z', '2025-11-27T08:27:09.46Z']

### http://data.europa.eu/esco/skill/fa46a48d-9cb9-422d-afab-1047654dbcdd

- Preferred label: memorise information
- Occurrences: 2
- Verdict: conflicting values

- `modified_date`: ['2025-07-31T09:51:40.289Z', '2025-11-26T10:31:09.298Z']

| uri suffix | n | preferred_label | verdict |
| --- | --- | --- | --- |
| skill/11dc8e6b-dffa-42e4-9de1-c47293a848ff | 2 | operate pumping equipment | conflict: modified_date |
| skill/1258cc12-37bb-4a12-b219-9c3d6b294533 | 2 | work in an organised manner | conflict: modified_date |
| skill/1330576d-b3c7-4776-94cb-b7bd92d62993 | 2 | implement airport emergency plans | conflict: modified_date |
| skill/19c610ff-f8eb-44e1-9f83-0e130303643c | 2 | assess data collected to improve community arts programme | conflict: modified_date |
| skill/1b9899a4-5b50-44b0-a21a-e2f86c51ac5a | 2 | assess physical conditions of clients | conflict: modified_date |
| skill/30e0f65f-82b9-458d-b454-fba8f7d6a24b | 2 | manage game management plans | conflict: modified_date |
| skill/51b4a8c4-6af7-41b7-a68d-f3c2fd63c9ec | 2 | de-limb trees | conflict: modified_date |
| skill/598de5b0-5b58-4ea7-8058-a4bc4d18c742 | 2 | SQL | conflict: modified_date |
| skill/5ad31f50-15ca-4940-8db3-2104c9b79d0b | 2 | assist the veterinary surgeon as a scrub nurse | conflict: modified_date |
| skill/61844a55-4103-4bf2-afcf-08e4ee120928 | 2 | urogynaecology | conflict: modified_date |
| skill/669fd6f4-92a8-4ed7-8cf9-48cd3fca4f20 | 2 | build miniature sets | conflict: modified_date |
| skill/72a109e1-df31-4f08-81d1-2baef60dac74 | 2 | coordinate closing room in footwear manufacturing | conflict: modified_date |
| skill/76731933-dad3-4053-aba3-d3ed6160b580 | 2 | perform pediatric surgery | conflict: modified_date |
| skill/933e7ccf-5d56-46ba-aca4-857f826a6b3a | 2 | administer appointments | conflict: modified_date |
| skill/9a825ed0-6186-4e18-9db7-6975e9d70dea | 2 | weld mining machinery | conflict: modified_date |
| skill/9d00803f-5dde-4803-8111-416ed174676f | 2 | immobilise patients for emergency intervention | conflict: modified_date |
| skill/a6bbc19a-381c-4c60-a79a-41dea2d1a422 | 2 | drive agricultural machines | conflict: modified_date |
| skill/b65691e8-1b0f-4593-8d18-9ebb66e10383 | 2 | monitor roasting | conflict: modified_date |
| skill/b77b7ac5-f25f-4baf-8e49-dcd4f31899f2 | 2 | contribute to public health campaigns | conflict: modified_date |
| skill/b7e57889-a84f-440c-9e60-459aa69979e9 | 2 | analyse supply chain trends | conflict: modified_date |
| skill/fa46a48d-9cb9-422d-afab-1047654dbcdd | 2 | memorise information | conflict: modified_date |

