from __future__ import annotations

from fastapi.testclient import TestClient

import app as demo_app

client = TestClient(demo_app.app)

DENIM_CAFE = (
    "Woman wearing a fitted denim jacket with white tee, high-waisted jeans, "
    "and clean white sneakers, cozy sidewalk cafe background, fashion photography"
)


def setup_function(_):
    client.post("/api/reset/all")


def test_run_response_includes_router_decision():
    response = client.post("/api/image/run", json={"prompt": DENIM_CAFE})

    assert response.status_code == 200
    router = response.json()["router"]
    assert router["route"] == "fresh_generation"
    assert router["generation_mode"] == "fresh_noise"
    assert router["estimated_cost_units"] == 1.0
    assert router["continuity"]["failure_reasons"] == ["no_prior_panel"]


def test_repeat_run_returns_cached_route():
    client.post("/api/image/run", json={"prompt": DENIM_CAFE})
    response = client.post("/api/image/run", json={"prompt": DENIM_CAFE})

    router = response.json()["router"]
    assert router["route"] == "return_cached"
    assert router["requires_model_call"] is False
    assert router["continuity"]["passed"] is True


def test_analytics_includes_router_block():
    client.post("/api/image/run", json={"prompt": DENIM_CAFE})
    response = client.get("/api/analytics")

    router = response.json()["router"]
    assert router["runs"] == 1
    assert router["cost"]["baseline_cost_units"] == 1.0
    assert router["unsafe_reuse_count"] == 0


def test_reset_clears_router_state():
    client.post("/api/image/run", json={"prompt": DENIM_CAFE})
    client.post("/api/reset/all")
    response = client.get("/api/analytics")

    assert response.json()["router"]["runs"] == 0
