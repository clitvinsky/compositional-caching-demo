from __future__ import annotations

import pytest

from backend_profiles import (
    KLEIN_PROFILES,
    MODEL_KLEIN_4B,
    MODEL_KLEIN_9B_KV,
    profile_for_route,
)
from router_bridge import DecisionLayer

ALL_ROUTES = {
    "return_cached",
    "surgical_edit",
    "camera_or_pose_change",
    "identity_locked_regen",
    "fresh_generation",
    "manual_review",
}

DENIM_CAFE = (
    "Woman wearing a fitted denim jacket with white tee, high-waisted jeans, "
    "and clean white sneakers, cozy sidewalk cafe background, fashion photography"
)


def test_every_route_has_a_profile():
    assert set(KLEIN_PROFILES) == ALL_ROUTES


def test_unknown_route_raises():
    with pytest.raises(ValueError):
        profile_for_route("teleport")


def test_edit_routes_use_reference_kv():
    for route in ("surgical_edit", "camera_or_pose_change", "identity_locked_regen"):
        profile = profile_for_route(route)
        assert profile.model == MODEL_KLEIN_9B_KV
        assert profile.reference_kv is not None
        assert profile.published_speedup is not None
        assert profile.steps == 4


def test_fresh_generation_has_no_reference_kv():
    profile = profile_for_route("fresh_generation")

    assert profile.model == MODEL_KLEIN_4B
    assert profile.reference_kv is None
    assert profile.published_speedup is None


def test_no_model_routes_make_no_model_call():
    for route in ("return_cached", "manual_review"):
        profile = profile_for_route(route)
        assert profile.model is None
        assert profile.steps == 0
        assert profile.reference_kv is None


def test_decision_response_includes_matching_backend_profile():
    layer = DecisionLayer()

    fresh = layer.decide(DENIM_CAFE)
    assert fresh["backend_profile"]["operation"] == "text_to_image"
    assert fresh["backend_profile"]["model"] == MODEL_KLEIN_4B

    repeat = layer.decide(DENIM_CAFE)
    assert repeat["backend_profile"]["operation"] == "serve_cached"
    assert repeat["backend_profile"]["model"] is None


def test_profiles_are_labeled_as_documented_mapping():
    for route in ALL_ROUTES:
        payload = profile_for_route(route).to_dict()
        assert "not integrated" in payload["backend"]
