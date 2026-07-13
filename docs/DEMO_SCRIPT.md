# Demo Script

This script is for walking someone through the visual reuse demo in 3-5 minutes.

## Setup

Run locally:

```bash
source .venv/bin/activate
uvicorn app:app --host 127.0.0.1 --port 5000 --reload
```

Open:

```text
http://127.0.0.1:5000/demo
```

## Talk Track

### 1. Start With The Problem

Image workflows often repeat most of the same visible structure even when the user asks for a small change.

In a fashion example, the subject, pose, outfit, or scene may stay mostly stable between requests. The demo makes that reuse visible.

### 2. Run A New Result

Click:

```text
Casual Denim, Cafe
```

Explain:

- This is the first request.
- Nothing from this session has been reused yet.
- All visible parts are treated as new.

Expected UI:

- `NEW RESULT`
- `0/8` reused
- all parts marked new

### 3. Show A Scene Update

Click:

```text
Same Look, Rooftop
```

Explain:

- Same subject.
- Same outfit.
- New scene.
- Most visible parts are reused.

Expected UI:

- partial reuse
- `7/8` reused
- only `Background` marked new

### 4. Show An Outfit Update

Click:

```text
Evening Dress, Beach
```

Explain:

- The outfit changes, so more visible parts need to refresh.
- The subject and framing still carry forward in the mock flow.

Expected UI:

- partial reuse
- `3/8` reused

### 5. Show A Small Accessory Update

Click:

```text
Red Heels Only
```

Explain:

- A small request change should not force every visible part to refresh.

Expected UI:

- partial reuse
- `7/8` reused
- only footwear/accessory marked new

### 6. Show The Decision Layer

Point at the **Decision Layer** card while re-running two presets.

Explain:

- The visuals are mocked, but the routing decision is real. Every request runs through
  [epic-cache-router-lab](https://github.com/clitvinsky/epic-cache-router-lab), a separate
  tested library, imported as a dependency.
- The card shows the chosen route, the router's rationale, continuity drift against the
  matched prior result, and the normalized cost of the plan.
- On `Red Heels Only`, the router escalates to identity-locked regeneration even though the
  visual diff is small. The edit chain is already deep, and repeated patching accumulates
  drift. That gate is the difference between a cache and a decision layer.

### 7. Show The Analytics

Open the **Analytics** tab.

Explain:

- The demo records run count, reused parts, refreshed parts, and illustrative cost savings.
- The Decision Layer section shows route distribution, an everything-fresh cost baseline
  versus the routed cost (about 46% avoided on the preset arc), average drift, and an
  unsafe-reuse tripwire that stays at zero while routing behaves.
- The visual-pipeline numbers are mock values for product explanation, not production
  benchmarks; the router costs are normalized planning units.

## Closing Line

The point is simple: related requests often contain reusable visible structure. This demo makes the difference between reuse and regeneration easy to see, and shows the decision layer that keeps reuse safe.
