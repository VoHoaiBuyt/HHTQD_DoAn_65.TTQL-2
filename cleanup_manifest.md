# Cleanup manifest — Phần 5.5

## Baseline and hash policy

- Baseline source: tag `pre-restructure`; include only
  `reports/generated/**`, `data/official/**`, `data/scenarios/**`,
  `data/processed/split_manifest.json`, `models/**`, and `config/**`.
- Exclude `reports/generated/pytest_summary.txt` as explicitly directed, along
  with generated artifacts added after the tag.
- Text files are SHA-256 hashed after CRLF/CR-to-LF normalization; binary files
  are hashed byte-for-byte. The reproducible path/hash list is
  `reports/generated/restructure_baseline.txt`; comparisons are in
  `reports/generated/restructure_hashes.csv`.
- The tag contains 72 baseline files, not 82 (delta: -10). The earlier 82-path
  comparison list was not retained, so the exact per-path difference from that
  comparison cannot be reconstructed. No attempt was made to force the count.
- Six current generated files are additions relative to the tag and excluded
  from baseline: `reports/generated/cleanup_inventory.csv`,
  `reports/generated/report_consistency_current.txt`,
  `reports/generated/report_consistency_pre_restructure.txt`,
  `reports/generated/report_vs_mc_mismatches.csv`,
  `reports/generated/restructure_baseline.txt`, and
  `reports/generated/restructure_hashes.csv`.

## Step 2A — completed

- Removed the inventoried cache/bytecode group; the 56 inventory rows occupy
  1,185,011 bytes according to the inventory. Added ignore rules for virtual
  environments, Python bytecode/cache, pytest cache, and notebook checkpoints.
- Test count: 119 passed before cleanup and 119 passed after cleanup. The
  post-cleanup full suite reported 252 warnings.
- Gates: pytest PASS (119); AppTest PASS (23); Streamlit `/_stcore/health` PASS
  (HTTP 200, body `ok`); baseline hash PASS (72/72 match, 0 mismatch, 0 missing).
- The baseline directories and file locations did not change in Step 2A.

## Step 2B — pending

- Pending archive moves: two notebooks, `reports/data_dictionary.csv`,
  `reports/stage1_report.md`, and `requirements-stage1.txt`.
- Pending documentation moves: seven files listed as MOVE in
  `reports/generated/cleanup_inventory.csv`.
- References, path scan, and all four gates remain pending.

## Step 2C/2D — deferred

- Deferred as instructed; legacy modules remain in place and paths are not
  consolidated.

## Review inventory

- The reviewer approved retaining unresolved REVIEW items. No unresolved item
  is deleted or moved solely based on its REVIEW classification.
- `.github/prompts/**`: retain in place; classify as editor tooling, exclude
  from `dist/`; the requested quick secret/path scan remains pending.
- `data/scenarios_v1/`: retain in place; include both files in `dist/` with a
  short evidence-only README, pending packaging.
- The requested `BaoCao_Nhom1_HTTQD-2.docx` filename was not found at repository
  root. Do not rename/move the similarly named
  `BaoCao_Nhom1_HTTQD_65.TTQL-2.docx` without confirmation.
