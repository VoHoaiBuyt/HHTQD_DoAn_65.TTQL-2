# Disposition of historical report mismatches

Source: `reports/generated/report_vs_mc_mismatches.csv` (31 historical rows). The mismatching document was the auto-generated `reports/stage2_report.docx`; it has been regenerated from current machine-generated artifacts without editing source data. The current checker reports zero discrepancies across 20 source tables. `reports/generated/part4_fix_evidence.md` remains unchanged as a raw record; see `docs/README.md`.

| # | Document/location | Old document value | Current generated value | Source file | Predicted cause | Disposition |
|---:|---|---|---|---|---|---|
| 1 | table 13, row 3, col 5 | 10.012 | 9.926 | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 2 | table 13, row 3, col 6 | 16.624 | 16.562 | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 3 | table 13, row 3, col 7 | 1252 | 1271 | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 4 | table 13, row 4, col 3 | 0.163 | 0.164 | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 5 | table 13, row 4, col 4 | [0.141, 0.187] | [0.142, 0.188] | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 6 | table 13, row 4, col 5 | 10.651 | 10.425 | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 7 | table 13, row 4, col 6 | 16.568 | 16.536 | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 8 | table 13, row 4, col 7 | 1298 | 1340 | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 9 | table 13, row 6, col 1 | ILP | ILP-fixed | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 10 | table 13, row 6, col 7 | 997 | 996 | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 11 | table 13, row 7, full row | [no row] | ILP-matched \| 1000 \| 0.301 \| [0.273, 0.330] \| 9.331 \| 3.223 \| 996 | reports/generated/mc_results.csv | policy row count changed | Regenerated stage2_report.docx; source unchanged |
| 12 | table 14, row 3, col 1 | ILP - B1 | ILP-matched - B1 | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 13 | table 14, row 3, col 4 | [0.035, 0.105] | [0.031, 0.107] | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 14 | table 14, row 3, col 5 | -13.401 | -13.339 | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 15 | table 14, row 3, col 6 | [-13.684, -13.133] | [-13.616, -13.065] | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 16 | table 14, row 4, col 1 | ILP - B2 | ILP-matched - B2 | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 17 | table 14, row 4, col 3 | 0.138 | 0.137 | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 18 | table 14, row 4, col 4 | [0.100, 0.173] | [0.102, 0.171] | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 19 | table 14, row 4, col 5 | -13.345 | -13.313 | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 20 | table 14, row 4, col 6 | [-13.624, -13.082] | [-13.572, -13.039] | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 21 | table 14, row 5, col 1 | ILP - B3 | ILP-matched - B3 | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 22 | table 14, row 5, col 4 | [0.272, 0.332] | [0.273, 0.329] | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 23 | table 14, row 5, col 6 | [-0.148, 0.140] | [-0.151, 0.148] | reports/generated/mc_results.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 24 | table 14, row 6, full row | [no row] | ILP-matched - ILP-fixed \| 1000 \| 0.000 \| [0.000, 0.000] \| 0.000 \| [0.000, 0.000] | reports/generated/mc_results.csv | policy row count changed | Regenerated stage2_report.docx; source unchanged |
| 25 | table 15, row 3, col 1 | ILP | ILP-matched | reports/generated/mc_pareto.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 26 | table 15, row 3, col 3 | chưa phân biệt | ILP vượt trội | reports/generated/mc_pareto.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 27 | table 15, row 4, col 1 | ILP | ILP-matched | reports/generated/mc_pareto.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 28 | table 15, row 4, col 3 | chưa phân biệt | ILP vượt trội | reports/generated/mc_pareto.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 29 | table 15, row 5, col 1 | ILP | ILP-matched | reports/generated/mc_pareto.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 30 | table 15, row 5, col 3 | chưa phân biệt | ILP vượt trội | reports/generated/mc_pareto.csv | report predates 4-fix | Regenerated stage2_report.docx; source unchanged |
| 31 | table 15, row 6, full row | [no row] | ILP-matched \| ILP-fixed \| chưa phân biệt \| Chỉ tiêu chính nào tệ hơn có ý nghĩa thì không kết luận vượt trội; cần ít nhất một chỉ tiêu tốt hơn có ý nghĩa. | reports/generated/mc_pareto.csv | policy row count changed | Regenerated stage2_report.docx; source unchanged |
