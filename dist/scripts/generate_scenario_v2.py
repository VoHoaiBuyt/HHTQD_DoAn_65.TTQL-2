from __future__ import annotations

import json

from core.scenario_v2 import run_scenario_v2_generation


if __name__ == "__main__":
    result = run_scenario_v2_generation()
    print(
        json.dumps(
            {
                "status": result["status"],
                "profiles": result["n_profiles"],
                "progress_rows": result["n_progress_rows"],
                "validation_errors": result["n_errors"],
                "plans": result["plans_count"],
                "sensitivity_rows": result["sensitivity_rows"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
