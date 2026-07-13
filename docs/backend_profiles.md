# Backend Profiles: FLUX.2 klein

How each routing decision in this demo would execute on a real generation
backend, using Black Forest Labs' FLUX.2 klein family as the reference
target. This is a documented mapping, not an integration. The demo stays
mock-only and deterministic; no model is downloaded or called.

## Why klein fits this workflow

The demo's edit routes assume a backend that can take reference images: a
canonical character for identity, and the matched prior result for context.
klein's multi-reference editing does exactly that, in 4 distilled denoising
steps.

## The KV-cache distinction (read this before citing it)

klein's `-kv` variants accelerate multi-reference editing with
**intra-request** reuse: the K/V for reference-image tokens is computed once
at step 0 and reused across the remaining denoising steps of that same
request. BFL publishes 1.21-2.66x speedups for this.

That is not a response cache and not cross-request reuse. It is the DiT
analog of exact-prefix KV reuse in LLM serving: it makes one edit cheaper to
execute, it does not decide whether an edit should happen.

This demo's decision layer works on the other axis: deciding across requests
whether to reuse, edit, regenerate, or escalate to a human. The two compose
cleanly:

- the router picks the route and the references to pass
- klein executes the edit, reusing reference K/V within the request

Cross-request reuse of reference K/V (sharing computed reference state
between similar requests) is deliberately out of scope for this demo.

## Route-to-execution mapping

| Route | Operation | Model | Steps | Reference K/V |
|---|---|---|---:|---|
| `return_cached` | serve cached | none | 0 | n/a |
| `surgical_edit` | multi-reference edit | klein-9b-kv | 4 | computed at step 0, reused across steps |
| `camera_or_pose_change` | multi-reference edit | klein-9b-kv | 4 | computed at step 0, reused across steps |
| `identity_locked_regen` | multi-reference regen (canonical ref only) | klein-9b-kv | 4 | computed at step 0, reused across steps |
| `fresh_generation` | text-to-image | klein-4b | 4 | n/a, no references |
| `manual_review` | hold for human | none | 0 | n/a |

The `identity_locked_regen` mapping is the interesting one: the router has
decided the edit chain drifted too far, so the backend call drops the prior
result entirely and regenerates from the canonical character reference only.
The route taxonomy and the backend operation express the same judgment.

## Licensing

- `flux.2-klein-4b` and `flux.2-klein-base-4b`: Apache 2.0, roughly 13 GB
  VRAM.
- The 9B variants, **including `flux.2-klein-9b-kv`** (the reference-KV
  feature): FLUX Non-Commercial license.

A commercial deployment of this mapping would use the 4B models without the
reference-KV acceleration, or license from BFL.

## Honesty notes

- Speedup figures are BFL's published numbers for multi-reference editing,
  not measured by this repo.
- The demo's cost units remain the router's normalized planning estimates.
  Mapping them to klein step counts and wall-clock latency would require
  running the models, which is out of scope for this mock.
