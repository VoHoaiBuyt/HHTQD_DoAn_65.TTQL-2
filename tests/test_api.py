"""Integration tests for FastAPI backend endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_api_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_scenarios(client: TestClient) -> None:
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 9
    ids = [item["student_id"] for item in data]
    assert "V2-001" in ids
    assert "V2-006" in ids


def test_api_dss_evaluation(client: TestClient) -> None:
    # Test valid profile with T1 valid
    response = client.get("/api/dss/V2-001")
    assert response.status_code == 200
    data = response.json()
    assert data["student_id"] == "V2-001"
    assert "profile" in data
    assert "risk" in data
    assert "plans" in data
    assert "xai" in data["risk"]
    assert data["risk"]["xai"]["status"] == "success"
    assert len(data["risk"]["xai"]["features"]) > 0

    # Test custom sliders: lambda, beta, gamma
    response_custom = client.get("/api/dss/V2-003?lambda=0.3&beta=0.25&gamma=1.5")
    assert response_custom.status_code == 200
    assert len(response_custom.json()["plans"]["plans"]) > 0

    # Test non-existent profile
    response_404 = client.get("/api/dss/V2-999")
    assert response_404.status_code == 404


def test_api_what_if_post(client: TestClient) -> None:
    payload = {
        "load_lambda": 0.2,
        "beta": 0.2,
        "gamma": 1.2,
        "risk_cap_mode": "soft",
        "progress_override": {"HP024": "completed"},
    }
    response = client.post("/api/dss/V2-006", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "whatif" in data
    assert "baseline_plans" in data["whatif"]
    assert "comparison_plans" in data["whatif"]


def test_api_dag(client: TestClient) -> None:
    response = client.get("/api/dag/V2-006")
    assert response.status_code == 200
    data = response.json()
    assert data["student_id"] == "V2-006"
    assert data["total_nodes"] > 50
    assert data["total_edges"] > 10
    assert len(data["bottlenecks"]) > 0
    bottleneck_ids = [b["course_id"] for b in data["bottlenecks"]]
    assert "HP024" in bottleneck_ids


def test_api_simulation(client: TestClient) -> None:
    response = client.get("/api/simulation/V2-001?lambda=0.1")
    assert response.status_code == 200
    data = response.json()
    assert data["student_id"] == "V2-001"
    assert len(data["results"]) > 0
    assert len(data["pareto"]) > 0
    assert len(data["grad_hist"]) > 0
    assert "limitation_note" in data
