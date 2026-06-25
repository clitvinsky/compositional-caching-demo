"""Offline visual reuse demo.

This app is intentionally mock-only. It demonstrates a high-level visual reuse
workflow with deterministic local responses and static image assets.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageEnhance, ImageOps, ImageStat


BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
IMAGE_OUTPUT_DIR = Path(os.getenv("IMAGE_OUTPUT_DIR", BASE_DIR / "output"))
ASSETS_DIR = Path(os.getenv("WORKERS_ASSETS_DIR", BASE_DIR / "assets"))
STATE_DIR = IMAGE_OUTPUT_DIR / "_state"

for path in (IMAGE_OUTPUT_DIR, ASSETS_DIR, STATE_DIR):
    path.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Visual Reuse Demo")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


PART_NAMES = [
    "Face & Hair",
    "Upper Body",
    "Upper Garment",
    "Lower Garment",
    "Footwear",
    "Background",
    "Style & Lighting",
    "Framing Guide",
]

COST_PER_FULL_RUN = 0.04
COST_PER_PART_RUN = 0.006


@dataclass
class RunRecord:
    reuse_hits: int
    regenerated: int
    latency_ms: float
    cost_saved: float
    change_type: str


class ImageRequest(BaseModel):
    prompt: str


_stats: list[RunRecord] = []
_last_prompt: str | None = None
_last_hash: str | None = None
_seen_prompts: dict[str, str] = {}


IMAGE_PRESETS = [
    {
        "label": "Casual Denim, Cafe",
        "prompt": "Woman wearing a fitted denim jacket with white tee, high-waisted jeans, and clean white sneakers, cozy sidewalk cafe background, fashion photography",
        "expect": "full_miss",
    },
    {
        "label": "Same Look, Rooftop",
        "prompt": "Woman wearing a fitted denim jacket with white tee, high-waisted jeans, and clean white sneakers, modern rooftop terrace at sunset, fashion photography",
        "expect": "background_change",
    },
    {
        "label": "Same Look, Beach",
        "prompt": "Woman wearing a fitted denim jacket with white tee, high-waisted jeans, and clean white sneakers, sandy beach at golden hour, fashion photography",
        "expect": "background_change",
    },
    {
        "label": "Evening Dress, Beach",
        "prompt": "Woman in a sleek black evening dress with subtle gold accessories and black pointed-toe heels, sandy beach at golden hour, fashion editorial",
        "expect": "outfit_change",
    },
    {
        "label": "Same Dress, Restaurant",
        "prompt": "Woman in a sleek black evening dress with subtle gold accessories and black pointed-toe heels, upscale restaurant interior with warm lighting, fashion editorial",
        "expect": "background_change",
    },
    {
        "label": "Red Heels Only",
        "prompt": "Woman in a sleek black evening dress with subtle gold accessories and red stiletto heels, upscale restaurant interior with warm lighting, fashion editorial",
        "expect": "accessory_change",
    },
    {
        "label": "Exact Repeat",
        "prompt": "Woman in a sleek black evening dress with subtle gold accessories and red stiletto heels, upscale restaurant interior with warm lighting, fashion editorial",
        "expect": "no_change",
    },
]


@app.get("/")
@app.get("/demo")
async def demo():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "demo_mode": "mock",
        "reuse_engine_ready": True,
        "parts_ready": (ASSETS_DIR / "parts_manifest.json").exists(),
    }


@app.get("/api/presets/image")
async def image_presets():
    return IMAGE_PRESETS


@app.post("/api/image/run")
async def run_image(body: ImageRequest):
    global _last_prompt, _last_hash

    started = time.perf_counter()
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(400, "Prompt is required")

    change_type = _classify_prompt(prompt)
    reused, regenerated = _reuse_plan(change_type)

    if change_type == "no_change" and prompt in _seen_prompts:
        img_hash = _seen_prompts[prompt]
    else:
        img_hash = _render_mock_result(prompt, change_type)
        _seen_prompts[prompt] = img_hash

    latency = _mock_latency(change_type, started)
    refreshed_count = 8 if regenerated == 8 else len(regenerated)
    saved = max(0.0, COST_PER_FULL_RUN - (refreshed_count * COST_PER_PART_RUN))

    _stats.append(
        RunRecord(
            reuse_hits=len(reused),
            regenerated=refreshed_count,
            latency_ms=latency,
            cost_saved=saved,
            change_type=change_type,
        )
    )

    _last_prompt = prompt
    _last_hash = img_hash

    return {
        "prompt": prompt,
        "image_hash": img_hash,
        "image_available": True,
        "reuse_hit": bool(reused),
        "change_type": change_type,
        "similarity": _similarity_score(change_type),
        "total_latency_ms": latency,
        "cost_saved": round(saved, 4),
        "parts_reused": reused,
        "parts_refreshed": ["all"] if change_type == "full_miss" else regenerated,
        "stored_result_count": len(_seen_prompts),
    }


@app.get("/api/analytics")
async def get_analytics():
    total_hits = sum(r.reuse_hits for r in _stats)
    total_misses = sum(r.regenerated for r in _stats)
    total_calls = total_hits + total_misses
    hit_rate = total_hits / total_calls if total_calls else 0
    change_types: dict[str, int] = {}
    for record in _stats:
        change_types[record.change_type] = change_types.get(record.change_type, 0) + 1

    image = {
        "runs": len(_stats),
        "total_calls": total_calls,
        "hits": total_hits,
        "misses": total_misses,
        "hit_rate": hit_rate,
        "cost_saved": round(sum(r.cost_saved for r in _stats), 4),
        "avg_latency_ms": round(sum(r.latency_ms for r in _stats) / len(_stats), 0) if _stats else 0,
    }
    return {
        "total_runs": len(_stats),
        "total_calls": total_calls,
        "total_hits": total_hits,
        "total_misses": total_misses,
        "hit_rate": round(hit_rate, 4),
        "total_cost_saved": image["cost_saved"],
        "image": image,
        "change_types": change_types,
    }


@app.post("/api/reset/all")
@app.post("/api/reset/image")
async def reset_demo():
    global _last_prompt, _last_hash
    _stats.clear()
    _seen_prompts.clear()
    _last_prompt = None
    _last_hash = None
    for path in IMAGE_OUTPUT_DIR.glob("*.png"):
        path.unlink(missing_ok=True)
    (ASSETS_DIR / "parts_manifest.json").unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/parts")
async def get_reused_parts():
    reuse_path = ASSETS_DIR / "parts_manifest.json"
    if not reuse_path.exists():
        raise HTTPException(404, "No reused parts")
    return JSONResponse(json.loads(reuse_path.read_text()))


@app.post("/api/parts")
async def create_parts():
    result = _mock_parts()
    (ASSETS_DIR / "parts_manifest.json").write_text(json.dumps(result))
    return result


@app.post("/api/canonical-image")
async def upload_canonical_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Image file required")
    data = await file.read()
    image = Image.open(io.BytesIO(data)).convert("RGB")
    image.save(ASSETS_DIR / "source_character.png", "PNG")
    (ASSETS_DIR / "parts_manifest.json").unlink(missing_ok=True)
    return {"ok": True}


@app.get("/images/{filename}")
async def get_image(filename: str):
    path = (IMAGE_OUTPUT_DIR / filename).resolve()
    if path.parent != IMAGE_OUTPUT_DIR.resolve() or not path.exists():
        raise HTTPException(404, "Image not found")
    return FileResponse(str(path), media_type="image/png")


def _classify_prompt(prompt: str) -> str:
    lower = prompt.lower()
    if prompt in _seen_prompts:
        return "no_change"
    if _last_prompt is None:
        return "full_miss"
    if any(word in lower for word in ["heel", "shoe", "sneaker", "boot"]):
        if any(word in (_last_prompt or "").lower() for word in ["dress", "restaurant"]):
            return "accessory_change"
    if any(word in lower for word in ["dress", "camo", "jacket"]) and "denim jacket" not in lower:
        return "outfit_change"
    if any(word in lower for word in ["rooftop", "beach", "restaurant", "cafe"]):
        return "background_change"
    return "outfit_change"


def _reuse_plan(change_type: str) -> tuple[list[str], list[str] | int]:
    if change_type == "no_change":
        return list(PART_NAMES), []
    if change_type == "background_change":
        return [name for name in PART_NAMES if name != "Background"], ["Background"]
    if change_type == "accessory_change":
        return [name for name in PART_NAMES if name != "Footwear"], ["Footwear"]
    if change_type == "outfit_change":
        return ["Face & Hair", "Upper Body", "Framing Guide"], [
            "Upper Garment",
            "Lower Garment",
            "Footwear",
            "Background",
            "Style & Lighting",
        ]
    return [], 8


def _mock_latency(change_type: str, started: float) -> float:
    floor = {
        "no_change": 24,
        "background_change": 620,
        "accessory_change": 480,
        "outfit_change": 1350,
        "full_miss": 3600,
    }.get(change_type, 1200)
    elapsed = (time.perf_counter() - started) * 1000
    return round(max(floor, elapsed), 0)


def _similarity_score(change_type: str) -> float:
    return {
        "no_change": 1.0,
        "background_change": 0.86,
        "accessory_change": 0.82,
        "outfit_change": 0.48,
        "full_miss": 0.0,
    }.get(change_type, 0.5)


def _source_image() -> Image.Image:
    source = ASSETS_DIR / "source_character.png"
    if not source.exists():
        source = STATIC_DIR / "maya_character.png"
    return Image.open(source).convert("RGB")


def _render_mock_result(prompt: str, change_type: str) -> str:
    base = ImageOps.fit(_source_image(), (768, 1024), method=Image.LANCZOS, centering=(0.5, 0.35))
    overlay_color = {
        "full_miss": "#475569",
        "background_change": "#2563eb",
        "outfit_change": "#b45309",
        "accessory_change": "#7c3aed",
        "no_change": "#0f766e",
    }.get(change_type, "#475569")
    overlay = Image.new("RGB", base.size, overlay_color)
    blend = 0.08 if change_type in {"no_change", "background_change"} else 0.14
    image = Image.blend(base, overlay, blend)
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rounded_rectangle((24, 24, 744, 112), radius=18, fill=(15, 15, 19, 185))
    draw.text((46, 48), _label_for(change_type), fill=(255, 255, 255, 230))
    draw.text((46, 78), prompt[:86], fill=(255, 255, 255, 130))

    img_hash = hashlib.sha1(f"{prompt}|{change_type}|{time.time()}".encode()).hexdigest()[:8]
    image.save(IMAGE_OUTPUT_DIR / f"{img_hash}.png", "PNG")
    return img_hash


def _label_for(change_type: str) -> str:
    return {
        "no_change": "Reused prior result",
        "background_change": "Updated scene",
        "outfit_change": "Updated outfit",
        "accessory_change": "Updated accessory",
        "full_miss": "New result",
    }.get(change_type, "Updated result")


def _mock_parts() -> dict[str, Any]:
    crops = _mock_part_crops()
    return {
        "character_description": "Reference image used by the offline visual reuse demo.",
        "parts": [
            {"name": name, "description": desc, "crop": crops[name]}
            for name, desc in [
                ("Face & Hair", "Reference face and hair region"),
                ("Upper Body", "Reference upper-body region"),
                ("Upper Garment", "Reference upper garment region"),
                ("Lower Garment", "Reference lower garment region"),
                ("Footwear", "Reference footwear region"),
                ("Background", "Visible background regions"),
                ("Style & Lighting", "Visual style and lighting cue"),
                ("Framing Guide", "Framing and pose cue"),
            ]
        ],
    }


def _mock_part_crops() -> dict[str, str]:
    base = _source_image()
    width, height = base.size
    boxes = {
        "Face & Hair": (int(width * 0.39), int(height * 0.09), int(width * 0.61), int(height * 0.22)),
        "Upper Body": (int(width * 0.32), int(height * 0.22), int(width * 0.68), int(height * 0.52)),
        "Upper Garment": (int(width * 0.29), int(height * 0.21), int(width * 0.71), int(height * 0.53)),
        "Lower Garment": (int(width * 0.30), int(height * 0.50), int(width * 0.70), int(height * 0.86)),
        "Footwear": (int(width * 0.35), int(height * 0.84), int(width * 0.65), int(height * 0.96)),
    }
    crops = {name: _encode_tile(_stage_crop(base.crop(box), name, "#14b8a6")) for name, box in boxes.items()}
    crops["Background"] = _encode_tile(_background_tile(base))
    crops["Style & Lighting"] = _encode_tile(_style_tile(base))
    crops["Framing Guide"] = _encode_tile(_framing_tile(base))
    return crops


def _stage_crop(img: Image.Image, label: str, accent: str) -> Image.Image:
    canvas = Image.new("RGB", (512, 512), "#101018")
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img.thumbnail((410, 410))
    canvas.paste(img, ((512 - img.width) // 2, 38))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((28, 28, 484, 484), radius=24, outline=accent, width=3)
    draw.rectangle((0, 430, 512, 512), fill="#0f0f13")
    draw.text((34, 452), label.upper(), fill="#d6d6dc")
    return canvas


def _background_tile(base: Image.Image) -> Image.Image:
    width, height = base.size
    regions = [
        (0, 0, int(width * 0.30), int(height * 0.35)),
        (int(width * 0.70), 0, width, int(height * 0.35)),
        (0, int(height * 0.42), int(width * 0.28), int(height * 0.82)),
        (int(width * 0.72), int(height * 0.42), width, int(height * 0.82)),
    ]
    slots = [(0, 0, 256, 215), (256, 0, 512, 215), (0, 215, 256, 430), (256, 215, 512, 430)]
    img = Image.new("RGB", (512, 512), "#101018")
    for region, slot in zip(regions, slots):
        crop = ImageOps.fit(base.crop(region), (slot[2] - slot[0], slot[3] - slot[1]), method=Image.LANCZOS)
        img.paste(crop, (slot[0], slot[1]))
    draw = ImageDraw.Draw(img)
    draw.line((256, 0, 256, 430), fill="#0f0f13", width=4)
    draw.line((0, 215, 512, 215), fill="#0f0f13", width=4)
    draw.rectangle((0, 0, 512, 430), outline="#60a5fa", width=4)
    draw.rectangle((0, 430, 512, 512), fill="#0f0f13")
    draw.text((34, 452), "BACKGROUND", fill="#d6d6dc")
    return img


def _style_tile(base: Image.Image) -> Image.Image:
    source = ImageOps.fit(base, (512, 430), method=Image.LANCZOS, centering=(0.5, 0.42))
    source = ImageEnhance.Contrast(source).enhance(1.08)
    source = Image.blend(source, Image.new("RGB", source.size, "#fbbf24"), 0.08)
    img = Image.new("RGB", (512, 512), "#101018")
    img.paste(source, (0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    regions = [(60, 50, 130, 120), (225, 80, 290, 145), (150, 190, 230, 260), (250, 300, 330, 370), (365, 70, 440, 150)]
    x = 34
    for region in regions:
        color = tuple(int(channel) for channel in ImageStat.Stat(source.crop(region)).mean)
        draw.rounded_rectangle((x, 388, x + 54, 422), radius=8, fill=color + (230,), outline=(255, 255, 255, 60), width=1)
        x += 64
    draw.arc((82, 36, 430, 384), start=210, end=330, fill=(251, 191, 36, 220), width=5)
    draw.rectangle((0, 0, 512, 430), outline=(251, 191, 36, 255), width=4)
    draw.rectangle((0, 430, 512, 512), fill=(15, 15, 19, 255))
    draw.text((34, 452), "STYLE & LIGHTING", fill=(214, 214, 220, 255))
    return img.convert("RGB")


def _framing_tile(base: Image.Image) -> Image.Image:
    source = ImageOps.fit(base, (512, 430), method=Image.LANCZOS, centering=(0.5, 0.42))
    source = ImageEnhance.Brightness(source).enhance(0.62)
    img = Image.new("RGB", (512, 512), "#101018")
    img.paste(source, (0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle((108, 34, 404, 424), outline=(45, 212, 191, 230), width=4)
    draw.line((256, 34, 256, 424), fill=(45, 212, 191, 210), width=3)
    draw.line((108, 164, 404, 164), fill=(45, 212, 191, 170), width=2)
    draw.line((108, 294, 404, 294), fill=(45, 212, 191, 170), width=2)
    draw.ellipse((204, 40, 308, 144), outline=(45, 212, 191, 230), width=4)
    draw.rectangle((0, 0, 512, 430), outline=(45, 212, 191, 255), width=4)
    draw.rectangle((0, 430, 512, 512), fill=(15, 15, 19, 255))
    draw.text((34, 452), "FRAMING GUIDE", fill=(214, 214, 220, 255))
    return img.convert("RGB")


def _encode_tile(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()
