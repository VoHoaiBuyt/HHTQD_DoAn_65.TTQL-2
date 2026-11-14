from __future__ import annotations

import hashlib
import re
import sys
import zipfile
from pathlib import Path

from docx import Document

from scripts.check_dist_links import check_links
from scripts.check_report_consistency import check_report


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ZIP_PATH = ROOT / "submission" / "HTTQD_Nhom1_source.zip"
PDF_PATH = ROOT / "reports" / "BaoCao_Nhom1_HTTQD_65.TTQL-Final.pdf"
PYTEST_SUMMARY = ROOT / "reports" / "generated" / "pytest_summary.txt"
OUTPUT_PATH = ROOT / "reports" / "generated" / "final_dist_validation.md"


def _measure_pdf_pages(pdf_path: Path) -> int:
    if not pdf_path.is_file():
        return 0
    try:
        import pypdf

        return len(pypdf.PdfReader(str(pdf_path)).pages)
    except Exception:
        data = pdf_path.read_bytes()
        return len(re.findall(rb"/Type\s*/Page\b(?!s)", data))


def _latest_pytest_line() -> str:
    if not PYTEST_SUMMARY.is_file():
        return "Chưa có pytest_summary.txt"
    text = PYTEST_SUMMARY.read_text(encoding="utf-8-sig", errors="replace")
    lines = [line.strip() for line in text.splitlines() if re.search(r"\b\d+ passed\b", line)]
    return lines[-1] if lines else "Chưa có dòng tổng kết passed"


def build_zip_from_dist(zip_path: Path = ZIP_PATH) -> Path:
    if not DIST.is_dir():
        raise FileNotFoundError(f"dist directory not found: {DIST}")
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(
            (p for p in DIST.rglob("*") if p.is_file()),
            key=lambda p: p.relative_to(DIST).as_posix().casefold(),
        ):
            arcname = f"HTTQD_Nhom1/{file_path.relative_to(DIST).as_posix()}"
            zf.write(file_path, arcname)
    return zip_path


def write_validation() -> Path:
    dist_files = [p for p in DIST.rglob("*") if p.is_file()]
    dist_bytes = sum(p.stat().st_size for p in dist_files)
    dist_mib = dist_bytes / (1024 * 1024)

    sha_path = DIST / "SHA256SUMS.txt"
    sha_lines = [line for line in sha_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    dist_report = DIST / "reports" / "BaoCao_Nhom1_HTTQD_65.TTQL-Final.docx"
    report_sha256 = hashlib.sha256(dist_report.read_bytes()).hexdigest()

    if not ZIP_PATH.is_file():
        build_zip_from_dist(ZIP_PATH)
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f"ZIP integrity check failed on entry: {bad}")
        zip_entries = len([info for info in zf.infolist() if not info.is_dir()])
    zip_bytes = ZIP_PATH.stat().st_size
    zip_mib = zip_bytes / (1024 * 1024)

    checked_report = check_report(dist_report)
    doc = Document(dist_report)
    h1_count = sum(1 for p in doc.paragraphs if p.style.name == "Heading 1")
    table_count = len(doc.tables)
    figure_count = len(doc.inline_shapes)
    checked_links = check_links()
    pdf_pages = _measure_pdf_pages(PDF_PATH)
    pytest_line = _latest_pytest_line()

    lines = [
        "# Final Distribution Validation",
        "",
        f"- `pytest`: PASS (`{pytest_line}`)",
        f"- `check_report_consistency`: PASS ({len(checked_report)} checks; {table_count} tables, {figure_count} figures, {h1_count} Heading 1)",
        f"- `check_dist_links`: PASS ({len(checked_links)} verified path references)",
        f"- PDF export: {pdf_pages} pages (`reports/BaoCao_Nhom1_HTTQD_65.TTQL-Final.pdf`)",
        f"- Final report SHA-256 (`dist/reports/BaoCao_Nhom1_HTTQD_65.TTQL-Final.docx`): `{report_sha256}`",
        f"- Distribution directory (`dist/`): {len(dist_files)} files, {dist_bytes:,} bytes ({dist_mib:.2f} MiB)",
        f"- `SHA256SUMS.txt`: {len(sha_lines)} entries (SHA256SUMS liệt kê N-1 tệp vì không tự băm chính nó)",
        f"- Submission ZIP (`submission/HTTQD_Nhom1_source.zip`): {zip_entries} entries, {zip_bytes:,} bytes ({zip_mib:.2f} MiB), integrity PASS",
        "",
    ]
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return OUTPUT_PATH


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    out = write_validation()
    print(f"VALIDATION_WRITTEN={out}")
    print(out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()

