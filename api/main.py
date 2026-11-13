"""FastAPI backend application for Academic Risk & Curriculum Optimization DSS."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.view_data import (
    MC_GRAD_HIST_PATH,
    MC_INTERPRETATION_PATH,
    MC_PAIRWISE_PATH,
    MC_PARETO_PATH,
    MC_RESULTS_PATH,
    build_courses_data,
    build_plans_data,
    build_profile_data,
    build_risk_data,
    build_what_if_data,
    list_scenarios,
)
from core.dag import build_curriculum_dag
from core.run_dss import (
    DEFAULT_BETA,
    DEFAULT_GAMMA,
    DEFAULT_LAMBDA,
    DEFAULT_RISK_CAP_MODE,
    run_dss,
)
from core.xai import explain_student_risk


ROOT = Path(__file__).resolve().parents[1]
WEB_DIST = ROOT / "web" / "dist"

app = FastAPI(
    title="HHTQD Academic Decision Support System API",
    description="Backend API supporting Academic Risk Warning & Credit Pathway Optimization",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cached Monte Carlo tables for high performance (<20ms response time)
_MC_CACHE: dict[str, Any] = {}


def _load_csv_as_dicts(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _init_mc_cache() -> None:
    if not _MC_CACHE:
        _MC_CACHE["results"] = _load_csv_as_dicts(MC_RESULTS_PATH)
        _MC_CACHE["pairwise"] = _load_csv_as_dicts(MC_PAIRWISE_PATH)
        _MC_CACHE["pareto"] = _load_csv_as_dicts(MC_PARETO_PATH)
        _MC_CACHE["grad_hist"] = _load_csv_as_dicts(MC_GRAD_HIST_PATH)
        interpretation = ""
        if MC_INTERPRETATION_PATH.is_file():
            interpretation = MC_INTERPRETATION_PATH.read_text(encoding="utf-8-sig")
        _MC_CACHE["interpretation"] = interpretation


_init_mc_cache()


class WhatIfRequest(BaseModel):
    load_lambda: float = DEFAULT_LAMBDA
    beta: float = DEFAULT_BETA
    gamma: float = DEFAULT_GAMMA
    budget: int | None = None
    fmax: float | None = None
    risk_cap_mode: str = DEFAULT_RISK_CAP_MODE
    progress_override: dict[str, str] = {}


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "version": "2.0.0"}


@app.get("/api/scenarios")
def get_scenarios() -> list[dict[str, str]]:
    return list_scenarios()


@app.get("/api/dss/{student_id}")
def get_dss_evaluation(
    student_id: str,
    load_lambda: float = Query(DEFAULT_LAMBDA, alias="lambda"),
    beta: float = Query(DEFAULT_BETA),
    gamma: float = Query(DEFAULT_GAMMA),
    budget: int | None = Query(None),
    fmax: float | None = Query(None),
    risk_cap_mode: str = Query(DEFAULT_RISK_CAP_MODE),
) -> dict[str, Any]:
    sid = str(student_id).strip()
    try:
        options = {
            "lambda": load_lambda,
            "beta": beta,
            "gamma": gamma,
            "budget": budget,
            "fmax": fmax,
            "risk_cap_mode": risk_cap_mode,
        }
        res = run_dss(sid, options=options)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    profile_data = build_profile_data(res)
    risk_data = build_risk_data(res)
    courses_data = build_courses_data(res)
    plans_data = build_plans_data(res)
    xai_data = explain_student_risk(sid)

    return {
        "student_id": sid,
        "profile": profile_data,
        "risk": {**risk_data, "xai": xai_data},
        "courses": courses_data,
        "plans": plans_data,
        "provenance": res.get("provenance", {}),
        "status": res.get("status", "optimal"),
        "warnings": res.get("warnings", []),
    }


@app.post("/api/dss/{student_id}")
def evaluate_what_if(student_id: str, payload: WhatIfRequest) -> dict[str, Any]:
    sid = str(student_id).strip()
    try:
        # Baseline run with default options
        baseline = run_dss(sid)

        # What-if run with custom parameters and overrides
        options = {
            "lambda": payload.load_lambda,
            "beta": payload.beta,
            "gamma": payload.gamma,
            "budget": payload.budget,
            "fmax": payload.fmax,
            "risk_cap_mode": payload.risk_cap_mode,
            "progress_override": {
                k: {"status": v} for k, v in payload.progress_override.items()
            },
        }
        whatif = run_dss(sid, options=options)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    what_if_data = build_what_if_data(baseline, whatif)
    return {
        "student_id": sid,
        "whatif": what_if_data,
        "parameters": {
            "lambda": payload.load_lambda,
            "beta": payload.beta,
            "gamma": payload.gamma,
            "budget": payload.budget,
            "fmax": payload.fmax,
            "risk_cap_mode": payload.risk_cap_mode,
        },
    }


@app.get("/api/dag/{student_id}")
def get_curriculum_dag(student_id: str) -> dict[str, Any]:
    sid = str(student_id).strip()
    try:
        return build_curriculum_dag(sid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/simulation/{student_id}")
def get_simulation_data(
    student_id: str,
    load_lambda: float = Query(0.1, alias="lambda"),
) -> dict[str, Any]:
    sid = str(student_id).strip()
    _init_mc_cache()

    lam_str = f"{load_lambda:.1f}" if load_lambda in {0.0, 0.1, 0.3} else str(load_lambda)

    results = [
        row for row in _MC_CACHE["results"]
        if row.get("student_id") == sid and (load_lambda is None or row.get("lambda") == lam_str)
    ]
    pairwise = [
        row for row in _MC_CACHE["pairwise"]
        if row.get("student_id") == sid and (load_lambda is None or row.get("lambda") == lam_str)
    ]
    pareto = [
        row for row in _MC_CACHE["pareto"]
        if row.get("student_id") == sid and (load_lambda is None or row.get("lambda") == lam_str)
    ]
    grad_hist = [
        row for row in _MC_CACHE["grad_hist"]
        if row.get("student_id") == sid
    ]

    return {
        "student_id": sid,
        "lambda": load_lambda,
        "results": results,
        "pairwise": pairwise,
        "pareto": pareto,
        "grad_hist": grad_hist,
        "interpretation": _MC_CACHE["interpretation"],
        "source_label": "SCENARIO / GIẢ ĐỊNH (Monte Carlo 5 chính sách × 3 mức λ)",
        "limitation_note": "Kết quả phân tích kịch bản theo giả định; không phải bằng chứng hiệu quả thực tế trên sinh viên NTU.",
    }


# Serve built React static files if web/dist exists
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="static")
