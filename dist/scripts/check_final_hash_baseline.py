from __future__ import annotations

import csv
import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "reports" / "generated" / "restructure_hashes.csv"
OUTPUT = ROOT / "reports" / "generated" / "final_hash_check.csv"


def main() -> None:
    with BASELINE.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 72:
        raise ValueError(f"Expected 72 baseline rows, got {len(rows)}")

    results = []
    for row in rows:
        path = ROOT / row["path"]
        if not path.is_file():
            actual = "MISSING"
            head_hash = "MISSING"
            baseline_status = "MISSING"
            worktree_status = "MISSING"
        else:
            actual = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            head_bytes = subprocess.run(
                ["git", "show", f"HEAD:{row['path']}"],
                cwd=ROOT,
                check=True,
                capture_output=True,
            ).stdout
            head_hash = hashlib.sha256(head_bytes.replace(b"\r\n", b"\n")).hexdigest()
            baseline_status = (
                "MATCH"
                if actual == row["baseline_sha256"] == row["current_sha256"]
                else "PREEXISTING_BASELINE_MISMATCH"
            )
            worktree_status = "UNCHANGED_FROM_HEAD" if actual == head_hash else "CHANGED"
        results.append(
            {
                "path": row["path"],
                "baseline_sha256": row["baseline_sha256"],
                "recorded_current_sha256": row["current_sha256"],
                "actual_sha256_lf_normalized": actual,
                "head_sha256_lf_normalized": head_hash,
                "baseline_status": baseline_status,
                "worktree_status": worktree_status,
            }
        )
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "path",
                "baseline_sha256",
                "recorded_current_sha256",
                "actual_sha256_lf_normalized",
                "head_sha256_lf_normalized",
                "baseline_status",
                "worktree_status",
            ),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(results)
    baseline_matches = sum(row["baseline_status"] == "MATCH" for row in results)
    unchanged = sum(row["worktree_status"] == "UNCHANGED_FROM_HEAD" for row in results)
    preexisting = sum(
        row["baseline_status"] == "PREEXISTING_BASELINE_MISMATCH"
        and row["worktree_status"] == "UNCHANGED_FROM_HEAD"
        for row in results
    )
    print(f"HASH_BASELINE: {baseline_matches}/{len(results)} recorded hashes match; {preexisting} pre-existing differences")
    print(f"HASH_WORKTREE: {unchanged}/{len(results)} unchanged from HEAD")
    if unchanged != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
