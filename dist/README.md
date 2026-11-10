# NTU IT study-risk and credit-planning prototype

## Data locations and labels

- `data/official/`: curriculum and prerequisite rows transcribed from the
  team-provided `210_CNTT.pdf`, section 7.1. Course IDs are preserved exactly.
- `data/scenarios_v1/`: scenario-v1 profiles and progress retained for audit
  only. Known defects are reported but the input files are not changed.
- `data/raw/uci_697/`: the independent UCI-697 dataset.
- `data/processed/split_manifest.json`: deterministic stratified split IDs and
  row hashes; it is not regenerated unless the source hash changes.
- `archive/`: legacy Stage 1 files retained outside pytest discovery.
- `core/`: UI-independent curriculum, rule, consistency, ML, and metrics code.

Curriculum enrichments are labeled `GIẢ ĐỊNH (suy từ CTĐT)` in
`config/courses_enrichment.yaml`. Regulation values transcribed from
QĐ 753/QĐ-ĐHNT carry article references and `CONFIRMED` status; unresolved
interpretations (including final-term identification, exact 105-credit year,
debt definition, corequisite meaning, and offering parity) remain `UNCONFIRMED` in
`config/credit_rules_official.yaml` and
`reports/generated/regulation_assumptions.md`. GPA calculations and enrollment
limits are implemented in `core/gpa.py` and `core/rules.py`. The previous
ILP/risk-projection functions remain marked `LEGACY`; the new scenario-v2
planner uses `core/optimizer.py` and never imports the legacy solver.

## Clean Windows PowerShell environment

The verified environment is Windows 11, Python 3.14.6, pip 26.1.2. Create and
activate a fresh virtual environment, then install pinned dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -v
python -m scripts.build_report
python -m scripts.check_report_consistency
```

The required ML libraries import on the verified Python 3.14 environment.
LightGBM is optional and was not installed; XGBoost is used. If a clean
interpreter cannot install one of the pinned ML wheels, use Python 3.12 for the
venv. If SHAP is unavailable, the documented alternatives are XGBoost
`pred_contribs=True` or, for Logistic Regression, coefficient times
`(feature - training_mean)`.

### Clean-copy verification (2026-11-10)

A clean copy excluding `.git`, `.venv`, `__pycache__`, `.pytest_cache`,
notebook checkpoints, `dist/`, and `_repro_tmp/` was verified with a new venv.
PowerShell commands run inside that copy:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe -m streamlit run app/main.py --server.headless true --server.port 8766
```

Observed results: `pip install` exit 0; `119 passed in 29.19s`; Streamlit health
`HTTP 200; body=ok`. This verifies a clean project copy, not the filtered
submission `dist/` package. The full in-worktree pytest transcript is
`reports/generated/pytest_summary.txt`; the concise clean-copy record is
`reports/generated/final_environment_validation.md`.

### Submission package

Build the whitelist package with `python -m scripts.package_dist`. The package
is assembled under `dist/`; `deliverables.md` lists its contents and exclusions.
The package intentionally excludes the previous report template, temporary
Monte Carlo reproductions, raw machine-specific test logs, caches, `.git`, and
`.github/prompts/`. The final package has 154 files (5.47 MiB). A clean copy
installed requirements, passed 119 tests (28.30s after final package sync) and
the report checker (20 source tables; 242 prose numbers; 0 unresolved), and
returned HTTP 200 from Streamlit. No UI screenshots or demo videos are available
yet.

## Curriculum and regulation checks

```powershell
python -m core.curriculum_validation
python -m core.data.consistency
python -m core.regulation
```

These commands write generated reports under `reports/generated/`. Scenario
v1 is audited only; it is not repaired or promoted.

## Scenario v2 and credit planning

The scenario generator reads OFFICIAL curriculum rows, uses REAL UCI-697
feature vectors with explicit labels, and calls the existing
`core.pass_prob.p_student_pass` interface. It stops rather than fabricating a
probability if the estimator cannot return one. The default NW specialization
is a configurable GIẢ ĐỊNH awaiting confirmation.

```powershell
python -m scripts.generate_scenario_v2
```

The command writes scenario-v2 profiles and progress under `data/scenarios/`,
plus validation, three-plan outputs, reduced sensitivity, unlock-value
statistics, and `optimization_spec.md` under `reports/generated/`. Risk
probabilities and Fmax are advisory; they do not limit official registration
rights.

## DSS and Monte Carlo comparison

`core.run_dss.run_dss(student_id, options)` is the shared entry point for
student summaries and simulated term decisions. Run a small multi-process
smoke test, benchmark N=200, then run the requested N=1,000 at the central
load penalty:

```powershell
python -m scripts.run_monte_carlo --runs 1 --student-ids V2-001 --workers 2 --no-write
python -m scripts.run_monte_carlo --runs 200 --lambda 0.1 --workers 4 --benchmark-only
python -m scripts.run_monte_carlo --runs 1000 --lambda 0.1 --workers 4
```

Simulation settings and explicitly assumed pass/fail proxies are in
`config/monte_carlo_scenario.yaml`; retake multipliers are shared with the
scenario-v2 optimizer configuration.

The final command writes `mc_results.csv`, `mc_pairwise.csv`, `mc_pareto.csv`,
`mc_grad_hist.csv`, `mc_runtime.json`, and figures under `reports/`. Simulation outputs are
scenario analyses, not evidence of effectiveness for NTU students. Future
pass/fail outcomes are independent; M3-prime already includes later dropout,
so no extra hazard is added. Later registration regimes are recalculated from
the previous simulated main term using representative pass/fail grades of 7.0
and 4.0, explicitly labeled GIẢ ĐỊNH. Summer terms are not modeled.

## ML training and one-time test evaluation

```powershell
python -m core.train_models --skip-test
```

Review the validation metrics, thresholds, protocol, and SHAP summaries before
the one-time holdout evaluation. Tuning and calibration use training OOF
predictions and validation only. Test access requires explicit opt-in:

```powershell
$env:ALLOW_TEST_EVAL = "1"
python -m core.train_models --evaluate-test
```

The loader refuses test access without the environment variable and logs
accepted access to `reports/generated/test_evaluation_log.jsonl`. Do not rerun
the test evaluation; only one successful evaluation is allowed.

## Streamlit interface

Run the presentation layer from the repository root:

```powershell
streamlit run app/main.py
```

The interface selects only `SCENARIO` profiles, calls `core.run_dss` for
student results, and reads Monte Carlo artifacts already generated under
`reports/generated/`. It does not calculate an alternative business result in
the UI. ML risk and local SHAP are shown only for `ml_scope=T1_valid`; what-if
parameters are labeled `GIẢ ĐỊNH`, and Monte Carlo results are not described
as evidence for NTU students. When editing course status or grade, inconsistent
combinations are rejected before the DSS is rerun. Run the page-data and Streamlit AppTest coverage for every scenario/page,
invalid progress edits, empty-plan handling, final-term profiles, risk callouts,
and profile isolation with:

```powershell
python -m pytest tests/test_app_smoke.py -q
```

The required student/screenshots scenarios are listed in
`docs/screens_to_capture.md`.

The simulation page discovers policies, comparisons, and Pareto labels from
the generated CSV columns, defaults to `ILP-matched`, and offers `ILP-fixed` as
a robustness row when present. It filters all MC tables, including
`mc_grad_hist.csv`, by the selected scenario and λ. The graduation histogram
shows term-by-term completions, forced withdrawals, and the residual not
completed by term 16; if the histogram is unavailable, the UI reports that
instead of reconstructing it. Pairwise confidence intervals and the generated
`mc_interpretation.md` are displayed alongside the scenario results.

## Word report and report consistency

Build `reports/stage2_report.docx` from the generated ML, curriculum, ILP, and
Monte Carlo artifacts, then verify every embedded source table:

```powershell
python -m scripts.build_report
python -m scripts.check_report_consistency
```

The checker fails if a required input is missing, if `n_checks` differs from
the number of curriculum checks in JSON, or if a table value differs from its
source artifact. The current pytest transcript is preserved verbatim in
`reports/generated/pytest_summary.txt`; rerun `python -m pytest -v` to validate
the current environment.
