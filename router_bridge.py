"""Bridge between the demo's prompt workflow and the epic-cache-router-lab
decision layer.

The demo is subject-centric: the unit of reuse is the composed character
image, the scene is a swappable layer, and the framing is fixed. That shapes
how prompts map onto the router's continuity metadata:

- ``characters`` / ``location`` / ``camera`` / ``action`` pin the composition
  frame and stay constant for this workflow
- outfit items parsed from the prompt become ``props``
- the scene and photographic style become ``continuity_tags``

Every generated result is stored as an accepted prior panel, so the router
sees the same session history the visual pipeline does. Edit chains are
tracked: surgical edits deepen ``edit_depth``; regenerations reset it.
"""

from __future__ import annotations

from typing import Any

from epic_cache_router_lab import (
    CacheRouter,
    GenerationPlan,
    PanelRequest,
    PriorPanel,
    plan_generation,
    score_continuity,
    summarize_costs,
)
from epic_cache_router_lab.router import (
    ROUTE_CAMERA_OR_POSE,
    ROUTE_FRESH,
    ROUTE_IDENTITY_LOCKED_REGEN,
    ROUTE_MANUAL_REVIEW,
    ROUTE_RETURN_CACHED,
    ROUTE_SURGICAL_EDIT,
)

SUBJECT = ("maya",)
LOCATION = "studio_frame"
CAMERA = "full_body"
ACTION = "pose"

# Ordered keyword tables. First match wins within a group; groups are
# independent. Deliberately simple, a production system would use a prompt
# parser or embeddings behind the same PanelRequest shape.
OUTFIT_KEYWORDS = [
    ("denim jacket", "denim_jacket"),
    ("white tee", "white_tee"),
    ("jeans", "high_waisted_jeans"),
    ("sneaker", "white_sneakers"),
    ("dress", "black_evening_dress"),
    ("gold accessories", "gold_accessories"),
    ("camo", "camo_outfit"),
]
FOOTWEAR_KEYWORDS = [
    ("red stiletto", "red_stiletto_heels"),
    ("red heels", "red_stiletto_heels"),
    ("heels", "black_heels"),
    ("boot", "boots"),
]
SCENE_KEYWORDS = [
    ("cafe", "sidewalk_cafe"),
    ("rooftop", "rooftop_terrace"),
    ("beach", "golden_hour_beach"),
    ("restaurant", "upscale_restaurant"),
]
STYLE_KEYWORDS = [
    ("editorial", "fashion_editorial"),
    ("photography", "fashion_photography"),
]

EDIT_ROUTES = {ROUTE_SURGICAL_EDIT, ROUTE_CAMERA_OR_POSE}
REGEN_ROUTES = {ROUTE_IDENTITY_LOCKED_REGEN, ROUTE_FRESH}
NO_STORE_ROUTES = {ROUTE_RETURN_CACHED, ROUTE_MANUAL_REVIEW}


def parse_prompt(prompt: str, request_id: str) -> PanelRequest:
    """Map a free-text demo prompt onto the router's continuity metadata."""
    lower = prompt.lower()
    props = [prop for keyword, prop in OUTFIT_KEYWORDS if keyword in lower]
    footwear = next((prop for keyword, prop in FOOTWEAR_KEYWORDS if keyword in lower), None)
    if footwear and footwear not in props:
        props.append(footwear)

    scene = next((tag for keyword, tag in SCENE_KEYWORDS if keyword in lower), "unspecified_scene")
    style = next((tag for keyword, tag in STYLE_KEYWORDS if keyword in lower), "fashion_default")

    return PanelRequest(
        request_id=request_id,
        prompt=prompt,
        characters=SUBJECT,
        location=LOCATION,
        camera=CAMERA,
        action=ACTION,
        props=tuple(props),
        continuity_tags=(f"scene:{scene}", f"style:{style}"),
    )


class DecisionLayer:
    """Session-scoped routing state built on epic-cache-router-lab."""

    def __init__(self) -> None:
        self._panels: list[PriorPanel] = []
        self._plans: list[GenerationPlan] = []
        self._routes: list[str] = []
        self._drift_scores: list[float] = []
        self._unsafe_reuse_count = 0
        self._counter = 0

    def decide(self, prompt: str) -> dict[str, Any]:
        """Route one prompt against session history and record the outcome."""
        self._counter += 1
        request = parse_prompt(prompt, request_id=f"run{self._counter:03d}")
        router = CacheRouter(self._panels)
        decision = router.route(request)
        plan = plan_generation(decision)
        matched = next(
            (p for p in self._panels if p.panel_id == decision.matched_panel_id), None
        )
        continuity = score_continuity(request, matched)

        self._plans.append(plan)
        self._routes.append(decision.route)
        if matched is not None:
            self._drift_scores.append(continuity.drift_score)
        if decision.route == ROUTE_RETURN_CACHED and not continuity.passed:
            self._unsafe_reuse_count += 1
        self._store_panel(request, decision, matched)

        return {
            "request_id": request.request_id,
            "route": decision.route,
            "rationale": decision.rationale,
            "matched_panel_id": decision.matched_panel_id,
            "similarity": round(decision.similarity, 3),
            "safety_score": round(decision.safety_score, 3),
            "risk_flags": list(decision.risk_flags),
            "generation_mode": plan.generation_mode,
            "starting_point": plan.starting_point,
            "estimated_steps": plan.estimated_steps,
            "estimated_cost_units": plan.estimated_cost_units,
            "requires_model_call": plan.requires_model_call,
            "requires_review": plan.requires_review,
            "continuity": continuity.to_dict(),
            "request_metadata": {
                "characters": list(request.characters),
                "location": request.location,
                "camera": request.camera,
                "action": request.action,
                "props": list(request.props),
                "continuity_tags": list(request.continuity_tags),
            },
            "stored_panels": len(self._panels),
        }

    def analytics(self) -> dict[str, Any]:
        cost = summarize_costs(self._plans)
        route_distribution = {
            route: self._routes.count(route) for route in sorted(set(self._routes))
        }
        avg_drift = (
            round(sum(self._drift_scores) / len(self._drift_scores), 3)
            if self._drift_scores
            else None
        )
        return {
            "runs": len(self._plans),
            "route_distribution": route_distribution,
            "avg_drift_score": avg_drift,
            "unsafe_reuse_count": self._unsafe_reuse_count,
            "stored_panels": len(self._panels),
            "cost": cost.to_dict(),
        }

    def reset(self) -> None:
        self._panels.clear()
        self._plans.clear()
        self._routes.clear()
        self._drift_scores.clear()
        self._unsafe_reuse_count = 0
        self._counter = 0

    def _store_panel(
        self,
        request: PanelRequest,
        decision: Any,
        matched: PriorPanel | None,
    ) -> None:
        if decision.route in NO_STORE_ROUTES:
            return
        if decision.route in EDIT_ROUTES and matched is not None:
            edit_depth = matched.edit_depth + 1
        else:
            edit_depth = 0
        self._panels.append(
            PriorPanel(
                panel_id=request.request_id,
                prompt=request.prompt,
                characters=request.characters,
                location=request.location,
                camera=request.camera,
                action=request.action,
                props=request.props,
                continuity_tags=request.continuity_tags,
                accepted=True,
                edit_depth=edit_depth,
            )
        )
