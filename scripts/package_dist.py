from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
EXCLUDED_GENERATED = {
    "pytest_summary.txt",
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
}


def _copy_tree(source: Path, destination: Path, *, exclude_templates: bool = False) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = {
            name
            for name in names
            if name in {".git", ".venv", "__pycache__", ".pytest_cache", ".ipynb_checkpoints"}
            or name.endswith((".pyc", ".pyo"))
        }
        if exclude_templates and Path(directory).name == "docs":
            ignored.add("templates")
        return ignored

    shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignore)


def build_dist() -> list[Path]:
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
    core_init = DIST / "core" / "__init__.py"
    core_init.write_bytes(core_init.read_bytes().rstrip(b"\r\n") + b"\n")
    for name in ("raw", "official", "scenarios", "scenarios_v1", "processed"):
        _copy_tree(ROOT / "data" / name, DIST / "data" / name)
    (DIST / "data" / "scenarios_v1" / "README.md").write_text(
        "# Scenario v1 validation evidence\n\n"
        "These two files are retained for consistency checks and legacy validation only. "
        "They are not used to produce final results and are not displayed in the application.\n",
        encoding="utf-8",
    )
    _copy_tree(ROOT / "docs", DIST / "docs", exclude_templates=True)
    _copy_tree(ROOT / "reports" / "figures", DIST / "reports" / "figures")
    shutil.copy2(ROOT / "reports" / "data_dictionary.csv", DIST / "reports" / "data_dictionary.csv")
    (DIST / "reports" / "generated").mkdir(parents=True, exist_ok=True)
    for path in (ROOT / "reports" / "generated").iterdir():
        if path.is_file() and path.name not in EXCLUDED_GENERATED:
            shutil.copy2(path, DIST / "reports" / "generated" / path.name)
    shutil.copy2(ROOT / "reports" / "stage2_report.docx", DIST / "reports" / "stage2_report.docx")

    demo_media = ROOT / "demo_media"
    if demo_media.is_dir():
        _copy_tree(demo_media, DIST / "demo_media")
    else:
        (DIST / "demo_media").mkdir()

    forbidden = []
    for path in DIST.rglob("*"):
        if path.name in {".git", ".venv", "__pycache__", ".pytest_cache", ".ipynb_checkpoints"}:
            forbidden.append(path)
        elif path.suffix.lower() in {".pyc", ".pyo"}:
            forbidden.append(path)
    if forbidden:
        raise RuntimeError(f"Forbidden cache or environment files in dist: {forbidden}")
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
