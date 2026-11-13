from __future__ import annotations

import re
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT if ROOT.name.casefold() == "dist" else ROOT / "dist"
OUTBOX_COVER = (
    ROOT.parent / "outbox" / "final_cover_message.md"
    if ROOT.name.casefold() == "dist"
    else ROOT / "outbox" / "final_cover_message.md"
)
REPORT = Path("reports/BaoCao_Nhom1_HTTQD_65.TTQL-Final.docx")
MARKDOWN_INPUTS = (
    Path("README.md"),
    Path("HANDOFF.md"),
    Path("deliverables.md"),
    Path("docs/README.md"),
)
PATH_MENTION = re.compile(
    r"(?<![\w.-])(?:\.\.?[\\/])?"
    r"(?:\.venv|reports|scripts|docs|data|core|api|web|app|config|tests|models|notebooks|demo_media)"
    r"(?:[\\/][\w().-]+)*[\\/]?"
    r"|(?<![\w.-])[\w.-]+\.(?:py|md|csv|json|yaml|yml|docx|png|txt|ipynb)",
    re.IGNORECASE,
)
LEGACY_MENTIONS = {
    "app", "app/", "app/main.py", "app/risk_labels.py", "tests/test_app_smoke.py", "App",
}
CODE_SPAN = re.compile(r"`([^`]+)`")
LINK_TARGET = re.compile(r"\]\(([^)]+)\)")


def _read_markdown(path: Path) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def _report_text(path: Path) -> str:
    document = Document(path)
    parts = [paragraph.text for paragraph in document.paragraphs]
    parts.extend(
        cell.text for table in document.tables for row in table.rows for cell in row.cells
    )
    return "\n".join(parts)


def _candidate_paths(text: str) -> set[str]:
    candidates: set[str] = set()
    for token in CODE_SPAN.findall(text):
        candidates.update(
            match.group(0).rstrip(".,;:!?")
            for match in PATH_MENTION.finditer(token)
        )
    for token in LINK_TARGET.findall(text):
        token = token.strip().split("#", 1)[0].strip()
        if token and not token.startswith(("http://", "https://", "mailto:")):
            candidates.add(token.rstrip(".,;:!?"))
    candidates.update(
        match.group(0).rstrip(".,;:!?")
        for match in PATH_MENTION.finditer(text)
    )
    return candidates


def check_links() -> list[str]:
    if not DIST.is_dir():
        raise FileNotFoundError(f"dist directory not found: {DIST}")
    if (DIST / "final_cover_message.md").exists():
        raise FileExistsError("final_cover_message.md must remain outside dist/")
    if ROOT.name.casefold() != "dist" and not OUTBOX_COVER.is_file():
        raise FileNotFoundError(f"Cover message must be stored outside dist/: {OUTBOX_COVER}")
    inputs = [*MARKDOWN_INPUTS, REPORT]
    missing_inputs = [str(path) for path in inputs if not (DIST / path).is_file()]
    if missing_inputs:
        raise FileNotFoundError(f"Required dist link-check inputs are missing: {missing_inputs}")

    checked: list[str] = []
    missing: list[tuple[str, str]] = []
    for relative in inputs:
        source = DIST / relative
        text = _report_text(source) if relative.suffix.lower() == ".docx" else _read_markdown_dist(relative)
        for token in sorted(_candidate_paths(text)):
            normalized = token.replace("\\", "/")
            while normalized.startswith("./"):
                normalized = normalized[2:]
            normalized = normalized.lstrip("/")
            if re.match(r"^[A-Za-z]:/", normalized):
                continue
            if normalized == ".venv" or normalized.startswith(".venv/"):
                continue
            if normalized in LEGACY_MENTIONS or normalized.rstrip("/") in LEGACY_MENTIONS:
                continue
            target = DIST / Path(normalized.replace("/", "\\"))
            if not target.exists():
                target = source.parent / Path(normalized.replace("/", "\\"))
            if not target.exists() and relative.suffix.lower() == ".docx":
                target = DIST / "reports" / "generated" / Path(normalized.replace("/", "\\"))
            if target.exists():
                checked.append(f"{relative.as_posix()} -> {normalized}")
            else:
                missing.append((relative.as_posix(), normalized))
    if missing:
        details = "\n".join(f"{source}: {target}" for source, target in missing)
        raise FileNotFoundError(f"Broken paths referenced from distribution files:\n{details}")
    return checked


def _read_markdown_dist(path: Path) -> str:
    return (DIST / path).read_text(encoding="utf-8-sig")


def main() -> None:
    checked = check_links()
    print(f"DIST_LINKS: PASS ({len(checked)} internal path references)")
    for item in checked:
        print(item)


if __name__ == "__main__":
    main()
