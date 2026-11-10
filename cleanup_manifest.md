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

## Directory tree (two levels)

Before Step 2A/2B:

```text
.
├── .github/prompts
├── app/__pycache__
├── archive/__pycache__
├── config
├── core/__pycache__, core/data
├── data/official, data/processed, data/raw, data/scenarios, data/scenarios_v1
├── models
├── notebooks
├── reports/diagrams, reports/figures, reports/generated
├── scripts/__pycache__
├── src/analysis, src/config, src/data, src/optimize, src/rules
└── tests/__pycache__
```

After Step 2A/2B:

```text
.
├── .github/prompts
├── app
├── archive
├── config
├── core/data
├── data/official, data/processed, data/raw, data/scenarios, data/scenarios_v1
├── docs/diagrams
├── models
├── notebooks
├── reports/figures, reports/generated
├── scripts
├── src/analysis, src/config, src/data, src/models, src/optimize, src/rules, src/scenario
└── tests
```

After Step 3 review packaging (partial `dist/` for the two v1 evidence files):

```text
dist/data/scenarios_v1
```

## Step 2B — completed

- Archived: `notebooks/02_risk_to_plan_exploration.ipynb`,
  `notebooks/03_ilp_formulation_check.ipynb`,
  `reports/data_dictionary.csv`, `reports/stage1_report.md`, and
  `requirements-stage1.txt` are now under `archive/`.
- Retained an identical `reports/data_dictionary.csv` compatibility copy
  because the protected `core/data/consistency.py` still reads that path.
  SHA-256 of both the archive source and compatibility copy:
  `36a701dd78d141703957edcea62d5dc7106811140ec358553a74c47167dad032`.
- Moved the seven MOVE documents from `reports/` into `docs/`, preserving the
  diagrams subfolder under `docs/diagrams/`.
- Updated active references in `README.md`, `HANDOFF.md`,
  `scripts/build_report.py`, the legacy archive docs/script, the moved methods
  doc, and the existing Word report. The generated historical inventory/report
  artifacts remain unchanged as required.
- Targeted stale-path scan: 0 broken references in README, HANDOFF, scripts,
  archive, and docs. Two generated historical artifacts still mention old
  paths; they were not edited because `reports/generated/` is protected.
- Gates: pytest PASS (119; 252 warnings); AppTest PASS (23; 84 warnings);
  Streamlit `/_stcore/health` PASS (HTTP 200, body `ok`); baseline hash PASS
  (72/72 match, 0 mismatch, 0 missing).
- `python -m scripts.check_report_consistency` still fails at the same
  pre-existing Monte Carlo table mismatch as both the tag and pre-move branch.
  The saved/current mismatch sets both contain 31 rows; no result values were
  changed during the moves.
- Added folder READMEs for `.github/`, `archive/`, `docs/`, `notebooks/`,
  `reports/`, `scripts/`, `src/`, and `tests/`. Per the explicit no-touch rule,
  no README was added inside `app/`, `core/`, `config/`, `data/`, or `models/`.

## Step 2C/2D — deferred

- Deferred as instructed; legacy modules remain in place and paths are not
  consolidated.

## Review inventory

- The reviewer approved retaining unresolved REVIEW items. No unresolved item
  is deleted or moved solely based on its REVIEW classification.
- `.github/prompts/**`: retain in place; classify as editor tooling, exclude
  from `dist/`. Inventory: 172 files, 4,252,724 bytes. Quick scan found no
  credential-assignment or provider-token patterns; four files contain
  potential personal absolute-path strings:
  `ui-ux-pro-max/data/stacks/avalonia.csv`,
  `ui-ux-pro-max/data/stacks/javafx.csv`,
  `ui-ux-pro-max/data/stacks/laravel.csv`, and
  `ui-ux-pro-max/data/stacks/nextjs.csv`. Values were not copied; manual review
  is still needed to determine whether these are real personal paths.
- `data/scenarios_v1/`: retain in place; include both files in `dist/` with a
  short evidence-only README, pending packaging. Current contents: two files,
  19,476 bytes.
- The requested `BaoCao_Nhom1_HTTQD-2.docx` filename was not found at repository
  root. Do not rename/move the similarly named
  `BaoCao_Nhom1_HTTQD_65.TTQL-2.docx` without confirmation. No code/script
  reference to the requested filename was found.
- `dist/data/scenarios_v1/` now contains byte-for-byte copies of the two source
  scenario files and a README labeling them as v1 validation evidence, not final
  results. The rest of `dist/` is intentionally left for Part 6.
- The package whitelist projection is 5,279,166 bytes (5.035 MiB, 148 files),
  including the raw UCI data and model artifacts, excluding `.github/prompts/`,
  `archive/`, `.git`, environments, and caches. This is an estimate before
  Part 6 packaging and any added demo media; the partial `dist/` currently holds
  19,844 bytes.
- Folder READMEs were added where permitted. READMEs inside `app/`, `core/`,
  `config/`, `data/`, and `models/` remain omitted to honor the explicit
  no-touch constraint; the root README describes those locations.

## Full REVIEW list

All entries below are retained under the reviewer’s instruction; none is
deleted or moved solely because it is marked REVIEW. Specific handling for
`.github/prompts/` and `data/scenarios_v1/` is described above.

| Path | Bytes | Decision |
|---|---:|---|
| `.github/prompts/banner-design/SKILL.md` | 8326 | Retained; no deletion/move pending specific decision |
| `.github/prompts/banner-design/references/banner-sizes-and-styles.md` | 4993 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/SKILL.md` | 2939 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/references/approval-checklist.md` | 4245 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/references/asset-organization.md` | 5110 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/references/brand-guideline-template.md` | 3572 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/references/color-palette-management.md` | 4254 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/references/consistency-checklist.md` | 1926 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/references/logo-usage-rules.md` | 5464 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/references/messaging-framework.md` | 1763 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/references/typography-specifications.md` | 5042 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/references/update.md` | 3365 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/references/visual-identity.md` | 1884 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/references/voice-framework.md` | 1997 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/scripts/extract-colors.cjs` | 9328 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/scripts/inject-brand-context.cjs` | 9677 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/scripts/sync-brand-to-tokens.cjs` | 9545 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/scripts/tests/test_sync_brand_to_tokens.py` | 1970 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/scripts/validate-asset.cjs` | 10173 | Retained; no deletion/move pending specific decision |
| `.github/prompts/brand/templates/brand-guidelines-starter.md` | 6638 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/SKILL.md` | 6875 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/data/slide-backgrounds.csv` | 1038 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/data/slide-charts.csv` | 8631 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/data/slide-color-logic.csv` | 877 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/data/slide-copy.csv` | 6427 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/data/slide-layout-logic.csv` | 981 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/data/slide-layouts.csv` | 8760 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/data/slide-strategies.csv` | 8232 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/data/slide-typography.csv` | 735 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/references/component-specs.md` | 6914 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/references/component-tokens.md` | 4986 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/references/primitive-tokens.md` | 4562 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/references/semantic-tokens.md` | 4245 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/references/states-and-variants.md` | 4771 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/references/tailwind-integration.md` | 5633 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/references/token-architecture.md` | 5365 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/scripts/embed-tokens.cjs` | 2558 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/scripts/fetch-background.py` | 12287 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/scripts/generate-slide.py` | 28595 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/scripts/generate-tokens.cjs` | 4968 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/scripts/html-token-validator.py` | 11894 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/scripts/search-slides.py` | 9210 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/scripts/slide-token-validator.py` | 973 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/scripts/slide_search_core.py` | 14756 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/scripts/tests/test_validate_tokens.py` | 1619 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/scripts/validate-tokens.cjs` | 5942 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design-system/templates/design-tokens-starter.json` | 7184 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/SKILL.md` | 12322 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/data/cip/deliverables.csv` | 13385 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/data/cip/industries.csv` | 4935 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/data/cip/mockup-contexts.csv` | 5205 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/data/cip/styles.csv` | 5967 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/data/icon/styles.csv` | 2250 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/data/logo/colors.csv` | 10674 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/data/logo/industries.csv` | 13274 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/data/logo/styles.csv` | 13678 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/banner-sizes-and-styles.md` | 4993 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/cip-deliverable-guide.md` | 1735 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/cip-design.md` | 4589 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/cip-prompt-engineering.md` | 2493 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/cip-style-guide.md` | 2357 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/design-routing.md` | 5826 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/icon-design.md` | 4343 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/logo-color-psychology.md` | 3341 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/logo-design.md` | 3163 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/logo-prompt-engineering.md` | 4314 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/logo-style-guide.md` | 3435 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/slides-copywriting-formulas.md` | 2604 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/slides-create.md` | 153 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/slides-html-template.md` | 9004 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/slides-layout-patterns.md` | 3691 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/slides-strategies.md` | 2715 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/slides.md` | 1742 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/references/social-photos-design.md` | 11251 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/scripts/cip/core.py` | 8062 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/scripts/cip/generate.py` | 19430 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/scripts/cip/render-html.py` | 13941 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/scripts/cip/search.py` | 4524 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/scripts/icon/generate.py` | 17151 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/scripts/logo/core.py` | 6023 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/scripts/logo/generate.py` | 14630 | Retained; no deletion/move pending specific decision |
| `.github/prompts/design/scripts/logo/search.py` | 4745 | Retained; no deletion/move pending specific decision |
| `.github/prompts/slides/SKILL.md` | 1137 | Retained; no deletion/move pending specific decision |
| `.github/prompts/slides/references/copywriting-formulas.md` | 2604 | Retained; no deletion/move pending specific decision |
| `.github/prompts/slides/references/create.md` | 153 | Retained; no deletion/move pending specific decision |
| `.github/prompts/slides/references/html-template.md` | 9004 | Retained; no deletion/move pending specific decision |
| `.github/prompts/slides/references/layout-patterns.md` | 3691 | Retained; no deletion/move pending specific decision |
| `.github/prompts/slides/references/slide-strategies.md` | 2715 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-styling/LICENSE.txt` | 11357 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-styling/SKILL.md` | 10045 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-styling/references/canvas-design-system.md` | 7888 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-styling/references/shadcn-accessibility.md` | 9976 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-styling/references/shadcn-components.md` | 11155 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-styling/references/shadcn-theming.md` | 8672 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-styling/references/tailwind-customization.md` | 10171 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-styling/references/tailwind-responsive.md` | 8270 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-styling/references/tailwind-utilities.md` | 9980 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-styling/scripts/requirements.txt` | 444 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-styling/scripts/shadcn_add.py` | 8799 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-styling/scripts/tailwind_config_gen.py` | 14418 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-styling/scripts/tests/coverage-ui.json` | 35121 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-styling/scripts/tests/requirements.txt` | 52 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-styling/scripts/tests/test_shadcn_add.py` | 9919 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-styling/scripts/tests/test_tailwind_config_gen.py` | 14658 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max.prompt.md` | 28041 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/app-interface.csv` | 11046 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/catalog-summary.json` | 2392 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/charts.csv` | 23365 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/colors.csv` | 37940 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/data-provenance.json` | 36686 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/google-font-licenses.json` | 433127 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/google-fonts.csv` | 747241 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/icons.csv` | 57945 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/landing.csv` | 25449 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/motion.csv` | 14679 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/phosphor-icons-upstream.json` | 823933 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/products.csv` | 75623 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/react-performance.csv` | 15080 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/angular.csv` | 19863 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/astro.csv` | 14591 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/avalonia.csv` | 27327 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/flutter.csv` | 14192 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/html-tailwind.csv` | 16551 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/javafx.csv` | 33577 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/jetpack-compose.csv` | 12295 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/laravel.csv` | 20163 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/nextjs.csv` | 18687 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/nuxt-ui.csv` | 24106 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/nuxtjs.csv` | 23014 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/react-native.csv` | 14049 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/react.csv` | 19036 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/shadcn.csv` | 23184 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/svelte.csv` | 15078 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/swiftui.csv` | 15323 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/threejs.csv` | 46051 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/uno.csv` | 30091 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/uwp.csv` | 24692 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/vue.csv` | 12813 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/winui.csv` | 27890 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/stacks/wpf.csv` | 24158 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/styles.csv` | 149478 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/typography.csv` | 49997 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/ui-reasoning.csv` | 77360 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/data/ux-guidelines.csv` | 27516 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/core.py` | 41234 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/design_system.py` | 70937 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/reasoning_contract.py` | 5824 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/search.py` | 9123 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-api.json` | 1079 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-catalog.json` | 1772 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-existing.csv` | 480 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-metadata.json` | 328 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/fixtures/catalogs/google-overrides.json` | 97 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/fixtures/catalogs/icons-curated.csv` | 495 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/fixtures/catalogs/phosphor-core.json` | 571 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/fixtures/catalogs/phosphor-package.json` | 370 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/fixtures/catalogs/phosphor-react-exports.json` | 87 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/fixtures/catalogs/phosphor-react-package.json` | 81 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/fixtures/relevance-baseline.json` | 89436 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/fixtures/relevance-cases.json` | 36734 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/fixtures/relevance-thresholds.json` | 5079 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/test_catalog_refresh.py` | 19466 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/test_core.py` | 16680 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/test_core_data_quality.py` | 8954 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/test_data_contracts.py` | 19513 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/test_design_system_mode.py` | 7690 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/test_native_desktop_stack_freshness.py` | 8170 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/test_relevance_evaluator.py` | 8430 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/test_style_taxonomy.py` | 7425 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/test_text_layout_resilience.py` | 5874 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/tests/test_web_stack_freshness.py` | 7699 | Retained; no deletion/move pending specific decision |
| `.github/prompts/ui-ux-pro-max/scripts/validate_data.py` | 52064 | Retained; no deletion/move pending specific decision |
| `BaoCao_Nhom1_HTTQD_65.TTQL-2.docx` | 53905 | Retained; no deletion/move pending specific decision |
| `data/scenarios_v1/student_profile.csv` | 3462 | Retained; no deletion/move pending specific decision |
| `data/scenarios_v1/student_progress.csv` | 16014 | Retained; no deletion/move pending specific decision |
