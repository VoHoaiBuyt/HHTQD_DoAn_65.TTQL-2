from __future__ import annotations

import csv
import re
from pathlib import Path

from docx import Document

from scripts.build_report import REPORT_PATH, ROOT


NUMBER = re.compile(r"(?<![\w])(?:\d{1,3}(?:,\d{3})+|\d+)(?:[.,]\d+)?%?(?![\w])")
TEXT_SUFFIXES = {".csv", ".json", ".md", ".txt", ".yaml", ".yml"}
AUDIT_OUTPUTS = {
    "final_prose_numbers.csv",
    "final_phrase_scan.csv",
    "prose_claims.csv",
    "final_heading_outline.md",
}
PHRASES = (
    "tốt hơn",
    "vượt trội",
    "hiệu quả hơn",
    "tối ưu hơn",
    "an toàn",
    "chứng minh",
    "nhân quả",
)


def _read_text(path: Path) -> str:
    content = path.read_bytes()
    encoding = "utf-16" if content.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    return content.decode(encoding, errors="replace")


def _number(value: str) -> tuple[float, int, bool]:
    is_percent = value.endswith("%")
    cleaned = value.rstrip("%")
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", cleaned):
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")
    decimals = len(cleaned.partition(".")[2]) if "." in cleaned else 0
    result = float(cleaned)
    if is_percent:
        result /= 100
        decimals += 2
    return result, decimals, is_percent


def _source_numbers() -> dict[Path, list[float]]:
    source_files = [
        *ROOT.joinpath("reports", "generated").rglob("*"),
        *ROOT.joinpath("config").rglob("*"),
    ]
    sources: dict[Path, list[float]] = {}
    repro_dir = ROOT / "reports" / "generated" / "_repro_tmp"
    for path in source_files:
        if (
            not path.is_file()
            or path.suffix.lower() not in TEXT_SUFFIXES
            or path.name in AUDIT_OUTPUTS
        ):
            continue
        if repro_dir in path.parents:
            continue
        values = []
        for match in NUMBER.finditer(_read_text(path)):
            try:
                values.append(_number(match.group())[0])
            except ValueError:
                continue
        sources[path] = values
    return sources


def audit() -> list[dict[str, str]]:
    document = Document(REPORT_PATH)
    sources = _source_numbers()
    rows: list[dict[str, str]] = []
    for paragraph_index, paragraph in enumerate(document.paragraphs, 1):
        text = paragraph.text
        for match in NUMBER.finditer(text):
            token = match.group()
            target, decimals, _ = _number(token)
            tolerance = 0.5 * (10 ** -decimals) + 1e-12
            matches = [
                path.relative_to(ROOT).as_posix()
                for path, values in sources.items()
                if any(abs(value - target) <= tolerance for value in values)
            ]
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            rows.append(
                {
                    "number": token,
                    "context": text[start:end].strip(),
                    "source_match": "; ".join(matches) if matches else "KHÔNG KHỚP/CHƯA XÁC ĐỊNH",
                    "paragraph": str(paragraph_index),
                }
            )
    output = ROOT / "reports" / "generated" / "final_prose_numbers.csv"
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("number", "context", "source_match", "paragraph"),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return rows


def phrase_hits() -> list[tuple[str, str, str]]:
    document = Document(REPORT_PATH)
    texts = [
        ("report prose", "\n".join(p.text for p in document.paragraphs)),
        (
            "report tables",
            "\n".join(cell.text for table in document.tables for row in table.rows for cell in row.cells),
        ),
        (
            "cover message",
            _read_text(ROOT / "reports" / "generated" / "final_cover_message.md"),
        ),
    ]
    texts.extend(
        (path.relative_to(ROOT).as_posix(), _read_text(path))
        for path in ROOT.joinpath("app").rglob("*")
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES | {".py", ".toml"}
    )
    hits = []
    for location, text in texts:
        for phrase in PHRASES:
            for match in re.finditer(re.escape(phrase), text, flags=re.IGNORECASE):
                hits.append(
                    (
                        location,
                        phrase,
                        text[
                            max(0, match.start() - 120) : match.end() + 120
                        ].replace("\n", " ").strip(),
                    )
                )
    return hits


def main() -> None:
    rows = audit()
    unresolved = sum(
        row["source_match"] == "KHÔNG KHỚP/CHƯA XÁC ĐỊNH" for row in rows
    )
    print(f"PROSE_NUMBER_OCCURRENCES={len(rows)}")
    print(f"UNMATCHED_OR_UNCERTAIN={unresolved}")
    print("PROSE_NUMBER_CSV=reports/generated/final_prose_numbers.csv")
    hits = phrase_hits()
    phrase_output = ROOT / "reports" / "generated" / "final_phrase_scan.csv"
    with phrase_output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("location", "phrase", "context", "assessment"),
            lineterminator="\n",
        )
        writer.writeheader()
        for location, phrase, context in hits:
            normalized = context.casefold()
            negative = any(
                marker in normalized
                for marker in (
                    "không kết luận",
                    "không phải",
                    "không cho phép",
                    "không được gọi",
                    "chưa kết luận",
                    "chưa được",
                    "not evidence",
                )
            )
            if phrase == "vượt trội":
                assessment = "Descriptive Pareto category or explicit qualification; not a claim of NTU effectiveness"
            elif phrase == "an toàn" and location == "app/view_data.py":
                assessment = "Risk-focused display label for non-best_effort optimal plan; best_effort uses another label"
            elif phrase == "an toàn" and "best_effort" in normalized and not negative:
                assessment = "PROHIBITED: best_effort is labeled safe"
            elif phrase in {"tốt hơn", "hiệu quả hơn", "tối ưu hơn"} and not negative:
                assessment = "REVIEW: possible unsupported comparative claim"
            elif phrase in {"chứng minh", "nhân quả"} and not negative:
                assessment = "REVIEW: possible unsupported causal/effectiveness claim"
            else:
                assessment = "Negated, qualified, or non-assertive context"
            writer.writerow(
                {
                    "location": location,
                    "phrase": phrase,
                    "context": context,
                    "assessment": assessment,
                }
            )
    print(f"PHRASE_HITS={len(hits)}")
    print("PHRASE_SCAN_CSV=reports/generated/final_phrase_scan.csv")


if __name__ == "__main__":
    main()
