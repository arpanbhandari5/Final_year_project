# Workspace synchronization status

Generated from the Cursor workspace at `C:\4th project`.

## Two checkouts

| | Cursor workspace (this session) | Reported other sandbox |
|---|---|---|
| Path | `C:\4th project` | not this folder |
| Branch | `main` | `develop/final-year-enhancement` |
| HEAD | `c2d2a1be8f58c3b81dbf9aef8660e40af48cd54c` | `84a28e4` |
| Remote of that branch | `origin/develop/final-year-enhancement` exists, not checked out here | active there |

The newer annotation and normalization files are **on disk in this workspace as untracked files**. They were never committed, so checking out `develop/final-year-enhancement` at `84a28e4` will not show them.

Do not train on `84a28e4` until these untracked files are copied into that working tree (or this `main` working tree is used for the next experimental phase).

Do not `git add .`. Do not commit yet.

## Files in this workspace

| Path | Status here |
|---|---|
| `project_data/task_exposure_labels/annotation_reviewer1.csv` | Present (untracked) |
| `project_data/task_exposure_labels/annotation_reviewer2.csv` | Present (untracked) |
| `project_data/task_exposure_labels/task_exposure_adjudication.csv` | Present (untracked) |
| `project_data/task_exposure_labels/task_exposure_training.csv` | Present (untracked) |
| `project_data/task_exposure_labels/ALLOWED_LOGICAL_SCORES.txt` | Present (untracked) |
| `project_data/task_exposure_labels/final_validated_task_training_table.csv` | Present (untracked) |
| `external_data/normalized/normalization_manifest.json` | Present (untracked) |
| `external_data/normalized/esco/esco_occupations.csv` | Present (untracked) |
| `external_data/normalized/careercorpus/careercorpus_resumes.csv` | Present (untracked) |
| `external_data/raw/bls_employment_projections/bls_employment_projections.xlsx` | **Missing** (wrong name below) |
| `external_data/raw/bls_employment_projections/bls_employment_projections.xlsx.xlsx` | Present (double extension) |
| BLS OEWS / BLS AI exposure | Still `.gitkeep` only |
| `train_model.py` | Committed `Ridge(alpha=1.2)`, TF-IDF 7000; not RidgeCV |
| `ml_models/model.pkl` | Present |

## How to copy into the other checkout

From a shell on the machine that has both folders, copy the untracked trees (example):

```text
project_data/task_exposure_labels/
external_data/normalized/
reports/data_quality/
scripts/data_pipeline/
replacement_data/
```

Use a local copy. Do not email licensed O*NET/ESCO dumps. Then verify in the destination:

```text
git branch --show-current
git rev-parse HEAD
git status --short
```

Still do not commit until the destination checkout is reviewed.

## Label wording (if using the AI pilot)

The 250-task labels are **provisional AI weak supervision**, not human-validated ground truth, not current labour-market truth, and not personal job-loss probability.
