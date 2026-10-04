# Public benchmark model evaluation

This experiment evaluates task-level classification against a published GPTs-are-GPTs exposure taxonomy using human-derived benchmark labels. The benchmark provides an external reference and does not constitute new human validation of Prayash's original 0-1 scoring rubric. The labels are human-derived from the published source; they are not newly reviewed by this project's reviewers.

Target: `human_labels` in E0 / E1 / E2. GPT-4 fields were not used as the target.
TF-IDF is fitted inside sklearn Pipelines on training occupations only.
Hyperparameters were selected with GroupKFold on training occupations; the test occupation set was not used.

- Majority baseline: accuracy=0.5458; balanced_accuracy=0.3333; macro-F1=0.2354; weighted-F1=0.3854; MCC=0.0000
- Stratified dummy baseline: accuracy=0.3985; balanced_accuracy=0.3240; macro-F1=0.3237; weighted-F1=0.3995; MCC=-0.0200
- TF-IDF + Logistic Regression (C=1.0): accuracy=0.7353; balanced_accuracy=0.6328; macro-F1=0.6502; weighted-F1=0.7234; MCC=0.5343
- TF-IDF + Linear SVM (C=1.0): accuracy=0.7255; balanced_accuracy=0.6401; macro-F1=0.6519; weighted-F1=0.7191; MCC=0.5219

The research classifier outperformed the included baseline models on the held-out benchmark, but this does not establish production or real-world employment-outcome accuracy. Per-class metrics and the confusion matrix are in CSV sidecars.
Linear-model n-grams are features associated with model predictions, not causal determinants of exposure.
Occupation-level summaries are descriptive category shares, not Prayash 0–1 scores and not personal risk.

```text
Occupation leakage: false
TF-IDF leakage: false
Target leakage: false
Hyperparameter/test leakage: false
```
