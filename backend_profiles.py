"""Documented execution profiles mapping routes to a real generation backend.

This module describes how each routing decision WOULD execute on FLUX.2 klein.
It is a documented mapping, not an integration: the demo stays mock and no
model is called. See docs/backend_profiles.md for the full write-up.

One distinction matters and is easy to get wrong. klein's "-kv" feature is
INTRA-request reuse: in multi-reference editing, the K/V for reference-image
tokens is computed once at step 0 and reused across the remaining denoising
steps of that same request. It accelerates executing one edit. It is not a
response cache and not cross-request reuse. The decision layer in this demo
works on the other axis, deciding whether and how to reuse prior results
across requests. The two compose; they do not overlap. Cross-request reuse of
reference K/V is deliberately out of scope here.

Speedup figures are published by Black Forest Labs for multi-reference
editing, not measured by this demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from epic_cache_router_lab.router import (
    ROUTE_CAMERA_OR_POSE,
    ROUTE_FRESH,
    ROUTE_IDENTITY_LOCKED_REGEN,
    ROUTE_MANUAL_REVIEW,
    ROUTE_RETURN_CACHED,
    ROUTE_SURGICAL_EDIT,
)

# klein-4b / klein-base-4b are Apache 2.0 (~13 GB VRAM). The 9B variants,
# including flux.2-klein-9b-kv (the reference-KV feature), are FLUX
# Non-Commercial. A commercial deployment would need the 4B models or a BFL
# license.
MODEL_KLEIN_4B = "flux.2-klein-4b"
MODEL_KLEIN_9B_KV = "flux.2-klein-9b-kv"

REFERENCE_KV_INTRA_REQUEST = "step-0 reference K/V reused across all denoising steps"
PUBLISHED_SPEEDUP = "1.21-2.66x published by BFL for multi-reference editing"


@dataclass(frozen=True)
class BackendProfile:
    """How one routing decision would execute on the klein backend."""

    operation: str
    model: str | None
    steps: int
    reference_kv: str | None
    published_speedup: str | None
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": "flux.2-klein (documented mapping, not integrated)",
            "operation": self.operation,
            "model": self.model,
            "steps": self.steps,
            "reference_kv": self.reference_kv,
            "published_speedup": self.published_speedup,
            "detail": self.detail,
        }


KLEIN_PROFILES: dict[str, BackendProfile] = {
    ROUTE_RETURN_CACHED: BackendProfile(
        operation="serve_cached",
        model=None,
        steps=0,
        reference_kv=None,
        published_speedup=None,
        detail="Serve the stored result. No model call.",
    ),
    ROUTE_SURGICAL_EDIT: BackendProfile(
        operation="multi_reference_edit",
        model=MODEL_KLEIN_9B_KV,
        steps=4,
        reference_kv=REFERENCE_KV_INTRA_REQUEST,
        published_speedup=PUBLISHED_SPEEDUP,
        detail=(
            "Edit with the canonical character image and the matched prior result as "
            "references. Reference-token K/V is computed once at step 0 and reused "
            "across the 4 denoising steps of this request."
        ),
    ),
    ROUTE_CAMERA_OR_POSE: BackendProfile(
        operation="multi_reference_edit",
        model=MODEL_KLEIN_9B_KV,
        steps=4,
        reference_kv=REFERENCE_KV_INTRA_REQUEST,
        published_speedup=PUBLISHED_SPEEDUP,
        detail=(
            "Reframe with the canonical character image as identity reference and the "
            "matched prior for scene context. Same intra-request reference-KV reuse."
        ),
    ),
    ROUTE_IDENTITY_LOCKED_REGEN: BackendProfile(
        operation="multi_reference_regen",
        model=MODEL_KLEIN_9B_KV,
        steps=4,
        reference_kv=REFERENCE_KV_INTRA_REQUEST,
        published_speedup=PUBLISHED_SPEEDUP,
        detail=(
            "Regenerate the scene passing only the canonical character reference, "
            "dropping the drifted edit chain. Reference K/V still reused within the "
            "request."
        ),
    ),
    ROUTE_FRESH: BackendProfile(
        operation="text_to_image",
        model=MODEL_KLEIN_4B,
        steps=4,
        reference_kv=None,
        published_speedup=None,
        detail=(
            "Fresh 4-step distilled generation. No reference images, so reference-KV "
            "reuse does not apply."
        ),
    ),
    ROUTE_MANUAL_REVIEW: BackendProfile(
        operation="hold_for_review",
        model=None,
        steps=0,
        reference_kv=None,
        published_speedup=None,
        detail="Hold for a human decision. No model call until the reviewer picks a path.",
    ),
}


def profile_for_route(route: str) -> BackendProfile:
    profile = KLEIN_PROFILES.get(route)
    if profile is None:
        raise ValueError(f"No backend profile for route: {route!r}")
    return profile
