from __future__ import annotations

import fnmatch
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
REPORT = ROOT / "reports" / "BaoCao_Nhom1_HTTQD_65.TTQL-Final.docx"
EXCLUDED_GENERATED = {
    "pytest_part4_output.txt",
    "part4_fix_evidence.md",
    "part5_fix_report.md",
    "report_vs_mc_mismatches.csv",
    "report_consistency_current.txt",
    "report_consistency_pre_restructure.txt",
    "cleanup_inventory.csv",
    "restructure_baseline.txt",
    "restructure_hashes.csv",
    "old_report_outline.md",
    "old_report_replaced_content.md",
    "final_mismatch_disposition.md",
    "final_cover_message.md",
    "scenario_v1_defects.json",
    # audit logs
    "final_prose_numbers.csv",
    "final_phrase_scan.csv",
    "final_report_phrase_scan.csv",
    "final_hash_check.csv",
    # examples
    "run_dss_example.json",
    "regulation_evaluation_example.json",
    "evaluate_student_test_fixture.json",
    # unreferenced exploratory / diagnostic tables
    "mc_d1_loads.csv",
    "mc_regime_counts.csv",
    "mc_d4c_ilp_vs_b2_lambda_0_3.csv",
    "risk_warning_tier_oof.csv",
    "risk_restriction_threshold_oof.csv",
    "pass_rate_calibration_deciles.csv",
    "risk_to_plan_persona_scenarios.csv",
}
# lambda sensitivity raw (keeps mc_planner_lambda_sensitivity.csv)
EXCLUDED_GENERATED_PATTERNS = (
    "mc_*_lambda_0*.csv",
    "mc_runtime_lambda_*.json",
)


def _is_excluded_generated(name: str) -> bool:
    return name in EXCLUDED_GENERATED or any(
        fnmatch.fnmatch(name, pattern) for pattern in EXCLUDED_GENERATED_PATTERNS
    )
IGNORED_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ipynb_checkpoints",
    "_repro_tmp",
    "archive",
}


def _copy_tree(source: Path, destination: Path, *, exclude_templates: bool = False) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name in IGNORED_NAMES or name.endswith((".pyc", ".pyo"))}
        if exclude_templates and Path(directory).name == "docs":
            ignored.add("templates")
        return ignored

    shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignore)


def _copy_current_docs() -> None:
    destination = DIST / "docs"
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("README.md", "course_code_provenance.md", "ml_protocol.md"):
        shutil.copy2(ROOT / "docs" / name, destination / name)


def _clear_notebook_outputs() -> None:
    for path in (DIST / "notebooks").rglob("*.ipynb"):
        notebook = json.loads(path.read_text(encoding="utf-8"))
        for cell in notebook.get("cells", []):
            if cell.get("cell_type") == "code":
                cell["execution_count"] = None
                cell["outputs"] = []
        path.write_text(
            json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )


def _write_hashes() -> None:
    lines = []
    for path in sorted(
        (item for item in DIST.rglob("*") if item.is_file() and item.name != "SHA256SUMS.txt"),
        key=lambda item: item.relative_to(DIST).as_posix().casefold(),
    ):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(DIST).as_posix()}")
    (DIST / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_deliverables_tree() -> None:
    path = ROOT / "deliverables.md"
    text = path.read_text(encoding="utf-8")
    start = "<!-- DIST_TREE_START -->"
    end = "<!-- DIST_TREE_END -->"
    if start not in text or end not in text:
        raise ValueError("deliverables.md must contain distribution-tree markers")
    entries = []
    for item in sorted(DIST.iterdir(), key=lambda entry: (not entry.is_dir(), entry.name.casefold())):
        entries.append(f"- `{item.name}{'/' if item.is_dir() else ''}`")
        if item.is_dir():
            entries.extend(
                f"  - `{item.name}/{child.name}{'/' if child.is_dir() else ''}`"
                for child in sorted(item.iterdir(), key=lambda entry: (not entry.is_dir(), entry.name.casefold()))
            )
    replacement = start + "\n" + "\n".join(entries) + "\n" + end
    before, remainder = text.split(start, 1)
    _, after = remainder.split(end, 1)
    path.write_text(before + replacement + after, encoding="utf-8")
    shutil.copy2(path, DIST / path.name)


def build_dist() -> list[Path]:
    if not REPORT.is_file():
        raise FileNotFoundError(f"Build the final report before packaging: {REPORT}")
    DIST.mkdir(exist_ok=True)
    for child in list(DIST.iterdir()):
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    for name in ("README.md", "HANDOFF.md", "requirements.txt", "deliverables.md"):
        shutil.copy2(ROOT / name, DIST / name)
    for name in ("core", "app", "config", "tests", "scripts", "notebooks", "models"):
        _copy_tree(ROOT / name, DIST / name)
    _clear_notebook_outputs()
    for name in ("raw", "official", "scenarios", "processed"):
        _copy_tree(ROOT / "data" / name, DIST / "data" / name)
    _copy_current_docs()
    _copy_tree(ROOT / "reports" / "figures", DIST / "reports" / "figures")
    shutil.copy2(ROOT / "reports" / "data_dictionary.csv", DIST / "reports" / "data_dictionary.csv")
    generated_dest = DIST / "reports" / "generated"
    generated_dest.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / "reports" / "generated").iterdir():
        if path.is_file() and not _is_excluded_generated(path.name):
            shutil.copy2(path, generated_dest / path.name)
    shutil.copy2(REPORT, DIST / "reports" / REPORT.name)
    _copy_tree(ROOT / "demo_media", DIST / "demo_media")

    forbidden = []
    for path in DIST.rglob("*"):
        if path.name in IGNORED_NAMES or path.suffix.lower() in {".pyc", ".pyo"}:
            forbidden.append(path)
    if forbidden:
        raise RuntimeError(f"Forbidden archive/cache/environment entries in dist: {forbidden}")
    _write_hashes()
    _update_deliverables_tree()
    _write_hashes()
    return [path for path in DIST.rglob("*") if path.is_file()]


def main() -> None:
    files = build_dist()
    total_bytes = sum(path.stat().st_size for path in files)
    print(f"DIST_FILES={len(files)}")
    print(f"DIST_BYTES={total_bytes}")
    print(f"DIST_MIB={total_bytes / (1024 * 1024):.2f}")
    print(f"DEMO_MEDIA_FILES={sum(path.is_file() for path in (DIST / 'demo_media').rglob('*'))}")


if __name__ == "__main__":
    main()
