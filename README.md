# Visual Reuse Demo

A small, offline demo that shows a simple product idea: when a user makes a related image request, some visible parts of the prior result can be reused while only the changed parts are refreshed.

This repository is intentionally mock-only. It runs locally with deterministic demo responses and static image assets.

## What It Shows

- **New result:** first request in a session.
- **Scene update:** same outfit and subject, different setting.
- **Outfit update:** same subject, different clothing.
- **Accessory update:** small change to footwear.
- **Repeat:** exact same request reused.
- **Analytics:** run count, reuse rate, refreshed parts, and illustrative cost savings.

## Project Layout

| Path | Purpose |
|---|---|
| `app.py` | FastAPI mock API and deterministic image/part generation |
| `static/` | Browser UI |
| `assets/source_character.png` | Local demo reference image |
| `docs/DEMO_SCRIPT.md` | Short talk track for the demo |

Generated files are ignored by git:

- `output/`
- `assets/parts_manifest.json`
- `__pycache__/`

## Quick Start

```bash
git clone <repo-url>
cd visual-reuse-demo

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app:app --host 127.0.0.1 --port 5000 --reload
```

Open:

```text
http://127.0.0.1:5000/demo
```

The root path also opens the demo:

```text
http://127.0.0.1:5000/
```

## Demo Flow

Use the preset chips at the top of the UI:

1. **Casual Denim, Cafe**  
   First request. Expected result: `NEW RESULT`, `0/8` reused.

2. **Same Look, Rooftop**  
   Same outfit and subject, different setting. Expected result: `7/8` reused.

3. **Same Look, Beach**  
   Another scene update. Expected result: `7/8` reused.

4. **Evening Dress, Beach**  
   Outfit changes. Expected result: `3/8` reused.

5. **Same Dress, Restaurant**  
   Same outfit, new setting. Expected result: `7/8` reused.

6. **Red Heels Only**  
   Small accessory change. Expected result: `7/8` reused.

7. **Exact Repeat**  
   Same prompt again. Expected result: `8/8` reused.

Then open the **Analytics** tab to see the session summary.

## Docker

Build:

```bash
docker build -t visual-reuse-demo .
```

Run:

```bash
docker run --rm -p 5000:5000 visual-reuse-demo
```

Open:

```text
http://127.0.0.1:5000/demo
```

## License

MIT. See `LICENSE`.
