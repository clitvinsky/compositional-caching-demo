from __future__ import annotations

from router_bridge import DecisionLayer, parse_prompt

DENIM_CAFE = (
    "Woman wearing a fitted denim jacket with white tee, high-waisted jeans, "
    "and clean white sneakers, cozy sidewalk cafe background, fashion photography"
)
DENIM_ROOFTOP = (
    "Woman wearing a fitted denim jacket with white tee, high-waisted jeans, "
    "and clean white sneakers, modern rooftop terrace at sunset, fashion photography"
)
DENIM_BEACH = (
    "Woman wearing a fitted denim jacket with white tee, high-waisted jeans, "
    "and clean white sneakers, sandy beach at golden hour, fashion photography"
)
DRESS_BEACH = (
    "Woman in a sleek black evening dress with subtle gold accessories and "
    "black pointed-toe heels, sandy beach at golden hour, fashion editorial"
)
DRESS_RESTAURANT = (
    "Woman in a sleek black evening dress with subtle gold accessories and "
    "black pointed-toe heels, upscale restaurant interior with warm lighting, fashion editorial"
)
RED_HEELS = (
    "Woman in a sleek black evening dress with subtle gold accessories and "
    "red stiletto heels, upscale restaurant interior with warm lighting, fashion editorial"
)

PRESET_SEQUENCE = [
    DENIM_CAFE,
    DENIM_ROOFTOP,
    DENIM_BEACH,
    DRESS_BEACH,
    DRESS_RESTAURANT,
    RED_HEELS,
    RED_HEELS,
]

# The demo's narrative arc, verified against the router: a fresh start, two
# scene swaps as shallow edits, an outfit change caught by the edit-depth
# gate, another scene swap, an accessory change escalated again by chain
# depth, and an exact repeat served from cache.
EXPECTED_ARC = [
    "fresh_generation",
    "surgical_edit",
    "surgical_edit",
    "identity_locked_regen",
    "surgical_edit",
    "identity_locked_regen",
    "return_cached",
]


def run_sequence(layer: DecisionLayer) -> list[dict]:
    return [layer.decide(prompt) for prompt in PRESET_SEQUENCE]


def test_prompt_parsing_extracts_continuity_metadata():
    request = parse_prompt(DENIM_CAFE, request_id="r1")

    assert request.characters == ("maya",)
    assert set(request.props) == {
        "denim_jacket",
        "white_tee",
        "high_waisted_jeans",
        "white_sneakers",
    }
    assert request.continuity_tags == ("scene:sidewalk_cafe", "style:fashion_photography")


def test_footwear_keywords_are_ordered():
    red = parse_prompt(RED_HEELS, request_id="r1")
    black = parse_prompt(DRESS_BEACH, request_id="r2")

    assert "red_stiletto_heels" in red.props
    assert "black_heels" in black.props


def test_unrecognized_prompt_still_routes():
    layer = DecisionLayer()
    result = layer.decide("a completely unrelated request")

    assert result["route"] == "fresh_generation"
    assert result["continuity"]["failure_reasons"] == ["no_prior_panel"]


def test_preset_sequence_follows_expected_arc():
    layer = DecisionLayer()
    results = run_sequence(layer)

    assert [r["route"] for r in results] == EXPECTED_ARC


def test_exact_repeat_is_cached_and_passes_gates():
    layer = DecisionLayer()
    results = run_sequence(layer)
    repeat = results[-1]

    assert repeat["route"] == "return_cached"
    assert repeat["estimated_cost_units"] == 0.0
    assert repeat["requires_model_call"] is False
    assert repeat["continuity"]["passed"] is True
    assert repeat["continuity"]["drift_score"] == 0.0


def test_edit_chain_depth_escalates_to_regen():
    layer = DecisionLayer()
    results = run_sequence(layer)
    accessory_change = results[5]

    assert accessory_change["route"] == "identity_locked_regen"
    assert "edit_depth_limit" in accessory_change["risk_flags"]
    assert accessory_change["requires_review"] is True


def test_analytics_aggregates_costs_and_routes():
    layer = DecisionLayer()
    run_sequence(layer)
    analytics = layer.analytics()

    assert analytics["runs"] == 7
    assert analytics["unsafe_reuse_count"] == 0
    assert sum(analytics["route_distribution"].values()) == 7
    assert analytics["cost"]["baseline_cost_units"] == 7.0
    assert analytics["cost"]["routed_cost_units"] < 7.0
    assert analytics["cost"]["estimated_savings_ratio"] > 0.0
    # Cached repeat is the only avoided model call in the preset arc.
    assert analytics["cost"]["avoided_model_calls"] == 1


def test_reset_clears_session_state():
    layer = DecisionLayer()
    run_sequence(layer)
    layer.reset()
    analytics = layer.analytics()

    assert analytics["runs"] == 0
    assert analytics["stored_panels"] == 0
    assert layer.decide(DENIM_CAFE)["route"] == "fresh_generation"


def test_decisions_are_deterministic():
    first = [r["route"] for r in run_sequence(DecisionLayer())]
    second = [r["route"] for r in run_sequence(DecisionLayer())]

    assert first == second
