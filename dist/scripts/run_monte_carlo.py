from __future__ import annotations

import argparse
import json
import os
import time

from core.curriculum import ROOT
from core.simulation import (
    DEFAULT_MC_SEED,
    run_monte_carlo_simulation,
    run_and_write_monte_carlo,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run seeded Part 4 Monte Carlo policies.")
    parser.add_argument("--runs", type=int, default=1000)
    parser.add_argument("--lambda", dest="lambdas", type=float, nargs="+", default=[0.1])
    parser.add_argument("--seed", type=int, default=DEFAULT_MC_SEED)
    parser.add_argument("--student-ids", nargs="*")
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--benchmark-only", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    if args.runs < 1 or args.workers < 1:
        parser.error("--runs and --workers must be positive")
    lambdas = tuple(args.lambdas)
    if any(value < 0 for value in lambdas):
        parser.error("--lambda values must be non-negative")
    if args.benchmark_only:
        start = time.perf_counter()
        results, pairwise, pareto = run_monte_carlo_simulation(
            n_runs=args.runs,
            lambdas=lambdas,
            seed=args.seed,
            student_ids=args.student_ids,
            n_workers=args.workers,
        )
        elapsed = time.perf_counter() - start
        benchmark = {
            "n_runs": args.runs,
            "profiles": int(results["student_id"].nunique()),
            "policies": int(results["policy"].nunique()),
            "lambdas": list(lambdas),
            "workers": args.workers,
            "elapsed_seconds": elapsed,
            "estimated_seconds_at_1000": elapsed * 1000 / args.runs,
            "results_rows": len(results),
            "pairwise_rows": len(pairwise),
            "pareto_rows": len(pareto),
            "seed": args.seed,
        }
        path = ROOT / "reports" / "generated" / "mc_benchmark.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(benchmark, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(benchmark, indent=2))
        return
    if args.no_write:
        start = time.perf_counter()
        results, pairwise, pareto = run_monte_carlo_simulation(
            n_runs=args.runs,
            lambdas=lambdas,
            seed=args.seed,
            student_ids=args.student_ids,
            n_workers=args.workers,
        )
        print(
            json.dumps(
                {
                    "elapsed_seconds": time.perf_counter() - start,
                    "results_rows": len(results),
                    "pairwise_rows": len(pairwise),
                    "pareto_rows": len(pareto),
                },
                indent=2,
            )
        )
        return
    results, pairwise, pareto, elapsed = run_and_write_monte_carlo(
        n_runs=args.runs,
        lambdas=lambdas,
        seed=args.seed,
        student_ids=args.student_ids,
        n_workers=args.workers,
    )
    print(
        json.dumps(
            {
                "elapsed_seconds": elapsed,
                "results_rows": len(results),
                "pairwise_rows": len(pairwise),
                "pareto_rows": len(pareto),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
