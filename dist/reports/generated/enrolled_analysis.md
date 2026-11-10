# Enrolled-class analysis (validation only)

- Validation counts: `{"Dropout": 284, "Enrolled": 159, "Graduate": 442}`.
- Enrolled is right-censored at the collection endpoint and may later become Graduate or Dropout.
- PR-AUC and ROC-AUC are one-vs-rest on validation; confusion matrix follows class order Dropout, Enrolled, Graduate.

| Model | Enrolled precision | Enrolled recall | Enrolled F1 | Enrolled PR-AUC | Enrolled ROC-AUC |
|---|---:|---:|---:|---:|---:|
| LogisticRegression | 0.4842 | 0.2893 | 0.3622 | 0.4445 | 0.7796 |
| RandomForest | 0.6452 | 0.1258 | 0.2105 | 0.4456 | 0.7778 |
| XGBoost | 0.5200 | 0.3270 | 0.4015 | 0.4603 | 0.7912 |

- Balanced Random Forest: `{"elapsed_seconds": 1.7717973999997412, "enrolled": {"precision": 0.419811320754717, "recall": 0.559748427672956, "f1": 0.4797843665768194, "support": 159}, "pr_auc": 0.42298860297984464, "roc_auc": 0.7721035396850149, "confusion_matrix": [[187, 56, 41], [29, 89, 41], [30, 67, 345]]}`.
- One-vs-rest Logistic Regression: `{"elapsed_seconds": 0.7719107000002623, "enrolled": {"precision": 0.5072463768115942, "recall": 0.22012578616352202, "f1": 0.30701754385964913, "support": 159}, "pr_auc": 0.4149426972543938, "roc_auc": 0.7612142003222621, "confusion_matrix": [[201, 19, 64], [48, 35, 76], [28, 15, 399]]}`.
- Selected three-class confusion matrix: `[[202, 24, 58], [44, 52, 63], [22, 24, 396]]`.
- Smallest absolute standardized mean differences for numeric features are reported as overlap evidence:

| Feature | Comparison | Enrolled mean | Other-class mean | Standardized difference |
|---|---|---:|---:|---:|
| Curricular units 1st sem (enrolled) | Enrolled_vs_Dropout | 5.8994 | 5.8979 | 0.0007 |
| Educational special needs | Enrolled_vs_Graduate | 0.0063 | 0.0068 | -0.0062 |
| International | Enrolled_vs_Dropout | 0.0189 | 0.0176 | 0.0094 |
| Curricular units 1st sem (without evaluations) | Enrolled_vs_Dropout | 0.2075 | 0.1972 | 0.0118 |
| Nacionality | Enrolled_vs_Dropout | 1.5031 | 1.5810 | -0.0149 |
| Mother's qualification | Enrolled_vs_Graduate | 18.8365 | 19.0950 | -0.0164 |
| Course | Enrolled_vs_Graduate | 8885.0063 | 8819.7489 | 0.0327 |
| Course | Enrolled_vs_Dropout | 8885.0063 | 8812.1796 | 0.0355 |
| Educational special needs | Enrolled_vs_Dropout | 0.0063 | 0.0106 | -0.0467 |
| Mother's occupation | Enrolled_vs_Dropout | 11.6101 | 10.3345 | 0.0506 |

These comparisons are descriptive evidence of overlap, not causal explanations. Class weighting/one-vs-rest do not guarantee that the censored Enrolled class is separable.
