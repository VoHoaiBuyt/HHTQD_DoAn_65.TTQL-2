# Clean-dist verification

- Fresh virtual environment: `pip install -r requirements.txt` passed; the final package manifest was rechecked successfully.
- Full pytest in the latest clean distribution: `125 passed in 36.09s`.
- `scripts.test_prose_claims`: PASS (178 sourced rows); risk levels PASS (27/27); plan signatures PASS (3 identical profiles; 7 distinct result patterns).
- `check_report_consistency`: PASS; 19 source tables, 29 Word tables, 13 figures, 21 Heading 1 entries, and 23 checks.
- Final-report restricted-phrase scan: 7 occurrences, all assessed as explicitly qualified or negated; 0 unresolved. Details: `final_report_phrase_scan.csv`.
- Word font/size check: all checked runs and paragraph styles use Times New Roman; body 12 pt, tables 11 pt, Heading 1/2/3 are 14/13/12 pt; 0 mismatches.
- `check_dist_links`: PASS (210 internal path references).
- Streamlit health: HTTP 200; response body `ok`.
- ZIP test: PASS (178 entries, archive integrity verified; 3.84 MiB). The test archive was created outside the package to avoid recursive packaging.
- SHA256 manifest: PASS (177 entries; 0 mismatches). Distribution: 178 files, 8,217,266 bytes (7.84 MiB), below the 25 MB threshold.
- Personal-path and machine-username scan: 0 hits. The internal-token scan found 4 code-only validator/configuration lines; no document or generated-result hits.
- Distribution includes seven demo-media files, the final Word report, and `reports/generated/pytest_summary.txt`; no cover letter is packaged. The cover letter is stored in the sibling `outbox/`.
- Notebook execution in a clean environment: 6/6 code cells completed, 0 errors; saved outputs remain cleared in the distribution.
- Estimated report body length: 26.47 pages, excluding appendices; actual rendered page count remains unverified because no Word/PDF renderer was available.
- Full Chapters 6–7 and Appendix A text with table rows: `final_sections_6_7_appendix_a.md`.
- The package retains Monte Carlo reproduction notes; no Monte Carlo rerun was performed.
