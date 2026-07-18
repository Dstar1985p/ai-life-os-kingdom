"""
Image Generator — creates motorsport art for Print Forge listings.

Priority order:
1. DALL-E 3 via OpenAI API (if OPENAI_API_KEY set)
2. SVG procedural art — zero cost, always available
"""
from __future__ import annotations

import hashlib
import logging
import os
import random
import re
from pathlib import Path

logger = logging.getLogger(__name__)

IMAGES_DIR = Path(os.getenv("IMAGES_DIR", "/data/images"))
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

_PALETTE_BY_STYLE = {
    "minimalist bauhaus poster":     ["#D72B2B","#1B4F9E","#F5E642","#FFFFFF","#1A1A1A"],
    "retro 1970s illustration":      ["#E8633A","#F2C94C","#2D6A4F","#1A1A2E","#F7E7D0"],
    "high-contrast silhouette":      ["#000000","#FFFFFF","#C0392B","#F39C12","#ECF0F1"],
    "blueprint technical line art":  ["#0047AB","#FFFFFF","#B8D4F8","#001F5B","#C9D6EF"],
    "hand-drawn charcoal sketch":    ["#2C2C2C","#8B8B8B","#D4C5B2","#F5F0E8","#3D2B1F"],
    "vintage travel poster":         ["#C0392B","#E67E22","#F1C40F","#2980B9","#FDFAF6"],
    "watercolour wash":              ["#5DADE2","#EC407A","#66BB6A","#FFA726","#F8F9FA"],
    "halftone print":                ["#E74C3C","#2C3E50","#ECF0F1","#F39C12","#27AE60"],
    "neon noir":                     ["#00F5FF","#FF00FF","#7FFF00","#FF6600","#0A0A0F"],
}

_DEFAULT_PALETTE = ["#00D4FF","#FF6B35","#F7C59F","#1A1A2E","#E8E8E8"]


def _palette_for(style: str) -> list[str]:
    style_l = style.lower()
    for k, v in _PALETTE_BY_STYLE.items():
        if k in style_l:
            return v
    return _DEFAULT_PALETTE


def _car_silhouette_path(car: str) -> str:
    """Return an SVG path string approximating a rally/racing car profile."""
    # Generic sleek car silhouette — works for all eras
    rng = random.Random(hashlib.md5(car.encode()).hexdigest())
    # Body length varies slightly by car type
    long = "rally" in car.lower() or "wrc" in car.lower() or "escort" in car.lower()
    bw = 220 if long else 200
    # Main body
    return (
        f"M30,80 Q40,55 80,52 L{bw},52 Q{bw+20},52 {bw+30},65 "
        f"L{bw+30},80 Q{bw+20},85 {bw},85 L80,85 Q40,85 30,80 Z"
    )


def _wheel(cx: int, cy: int, r: int = 16) -> str:
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#1A1A1A" stroke="#888" stroke-width="2"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r//2}" fill="#555"/>'
    )


def _make_svg_motorsport_art(title: str, car: str, event: str, style: str, era: str) -> str:
    """Generate a 600×450 SVG motorsport art piece procedurally."""
    pal = _palette_for(style)
    bg, accent1, accent2, dark, light = pal[0], pal[1], pal[2], pal[3], pal[4]

    rng = random.Random(hashlib.md5(title.encode()).hexdigest())
    is_neon = "neon" in style.lower()
    is_blueprint = "blueprint" in style.lower()
    is_watercolour = "watercolour" in style.lower()
    is_halftone = "halftone" in style.lower()
    is_silhouette = "silhouette" in style.lower()

    # Dynamic elements
    angle = rng.randint(-8, 8)
    speed_lines = "\n".join(
        f'<line x1="{rng.randint(0,100)}" y1="{rng.randint(160,300)}" '
        f'x2="{rng.randint(100,260)}" y2="{rng.randint(160,300)}" '
        f'stroke="{light}" stroke-width="{rng.uniform(0.5,2):.1f}" opacity="0.25"/>'
        for _ in range(20)
    )

    # Glow filter for neon style
    filter_defs = ""
    glow_attr = ""
    if is_neon:
        filter_defs = f"""
        <filter id="glow"><feGaussianBlur stdDeviation="4" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>"""
        glow_attr = 'filter="url(#glow)"'

    # Blueprint grid
    grid_lines = ""
    if is_blueprint:
        grid_lines = "\n".join(
            f'<line x1="{x}" y1="0" x2="{x}" y2="450" stroke="{light}" stroke-width="0.3" opacity="0.2"/>'
            for x in range(0, 600, 30)
        ) + "\n".join(
            f'<line x1="0" y1="{y}" x2="600" y2="{y}" stroke="{light}" stroke-width="0.3" opacity="0.2"/>'
            for y in range(0, 450, 30)
        )

    # Watercolour blobs
    blobs = ""
    if is_watercolour:
        for i in range(5):
            cx = rng.randint(50, 550)
            cy = rng.randint(50, 400)
            rx = rng.randint(60, 150)
            ry = rng.randint(40, 100)
            blobs += f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{pal[i%len(pal)]}" opacity="0.18"/>'

    # Halftone dots pattern
    halftone = ""
    if is_halftone:
        halftone = '<pattern id="dots" width="12" height="12" patternUnits="userSpaceOnUse">' \
                   f'<circle cx="6" cy="6" r="2.5" fill="{accent1}" opacity="0.3"/></pattern>' \
                   '<rect width="600" height="450" fill="url(#dots)"/>'

    # Car body transform
    car_y_shift = 20 if is_blueprint else 0
    car_color = "#000000" if is_silhouette else accent1
    car_stroke = light if is_blueprint or is_neon else dark

    # Track markings
    track = (
        f'<ellipse cx="300" cy="310" rx="240" ry="60" '
        f'fill="none" stroke="{dark}" stroke-width="3" opacity="0.3"/>'
        f'<line x1="60" y1="310" x2="540" y2="310" stroke="{dark}" stroke-width="1" opacity="0.2" stroke-dasharray="8,6"/>'
    )

    # Starburst / radial lines behind car
    starburst = "\n".join(
        f'<line x1="300" y1="240" x2="{300+int(260*__import__("math").cos(i*0.523))}" '
        f'y2="{240+int(160*__import__("math").sin(i*0.523))}" '
        f'stroke="{accent2}" stroke-width="0.8" opacity="0.12"/>'
        for i in range(12)
    )

    # Short car name for display
    short_car = re.sub(r'\b(WRC|RS|GT|M|HF)\b', '', car).strip()[:20]

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 450" width="600" height="450">
  <defs>
    {filter_defs}
    {'<pattern id="dots" width="12" height="12" patternUnits="userSpaceOnUse"><circle cx="6" cy="6" r="2.5" fill="' + accent1 + '" opacity="0.3"/></pattern>' if is_halftone else ''}
  </defs>

  <!-- Background -->
  <rect width="600" height="450" fill="{bg}"/>
  {blobs}
  {grid_lines}
  {'<rect width="600" height="450" fill="url(#dots)"/>' if is_halftone else ''}

  <!-- Speed lines -->
  {speed_lines}

  <!-- Starburst -->
  {starburst}

  <!-- Track -->
  {track}

  <!-- Car group -->
  <g transform="translate(85, {210+car_y_shift}) rotate({angle}, 215, 20)" {glow_attr}>
    <!-- Car body -->
    <path d="{_car_silhouette_path(car)}"
          fill="{car_color}" stroke="{car_stroke}" stroke-width="{'1.5' if is_blueprint else '2'}"/>

    <!-- Windscreen -->
    <path d="M130,52 L165,30 L195,30 L210,52 Z"
          fill="{'none' if is_silhouette else '#1a3a5c'}"
          stroke="{car_stroke}" stroke-width="1.5" opacity="0.85"/>

    <!-- Roof fin -->
    <path d="M160,52 L172,38 L188,38 L195,52 Z"
          fill="{accent2}" stroke="{car_stroke}" stroke-width="1"/>

    <!-- Headlights -->
    <ellipse cx="262" cy="68" rx="8" ry="5"
             fill="{'#FFE000' if not is_silhouette else car_color}"
             stroke="{car_stroke}" stroke-width="1.2"/>

    <!-- Racing number -->
    <rect x="90" y="58" width="28" height="18" rx="3"
          fill="{'white' if not is_silhouette else '#444'}" opacity="0.9"/>
    <text x="104" y="71" text-anchor="middle" font-family="Arial Black,sans-serif"
          font-size="11" font-weight="900" fill="{dark}">{rng.randint(1,99)}</text>

    <!-- Side stripe -->
    <rect x="85" y="72" width="175" height="6" rx="2"
          fill="{accent2}" opacity="0.8"/>

    <!-- Wheels -->
    {_wheel(108, 85)}
    {_wheel(222, 85)}
  </g>

  <!-- Accent bar top -->
  <rect x="0" y="0" width="600" height="12" fill="{accent1}" opacity="0.9"/>
  <rect x="0" y="12" width="600" height="4" fill="{accent2}" opacity="0.7"/>

  <!-- Accent bar bottom -->
  <rect x="0" y="434" width="600" height="16" fill="{accent1}" opacity="0.9"/>

  <!-- Era badge -->
  <rect x="20" y="20" width="70" height="26" rx="4" fill="{accent2}" opacity="0.9"/>
  <text x="55" y="38" text-anchor="middle" font-family="Arial,sans-serif"
        font-size="13" font-weight="800" fill="{dark}">{era}</text>

  <!-- Event text -->
  <text x="300" y="385" text-anchor="middle" font-family="Arial,sans-serif"
        font-size="12" fill="{light}" opacity="0.7" letter-spacing="3">{event.upper()[:30]}</text>

  <!-- Car name -->
  <text x="300" y="410" text-anchor="middle" font-family="Arial Black,sans-serif"
        font-size="22" font-weight="900" fill="{light}" letter-spacing="2"
        {"filter='url(#glow)'" if is_neon else ""}>{short_car.upper()}</text>

  <!-- Style label -->
  <text x="300" y="432" text-anchor="middle" font-family="Arial,sans-serif"
        font-size="9" fill="{light}" opacity="0.45" letter-spacing="4">{style.upper()[:35]}</text>

  <!-- Corner mark -->
  <text x="575" y="28" text-anchor="end" font-family="Arial,sans-serif"
        font-size="9" fill="{light}" opacity="0.4">PITWALL CLASSICS</text>
</svg>"""
    return svg


def _title_to_filename(title: str) -> str:
    safe = re.sub(r"[^a-z0-9]+", "_", title.lower())[:80]
    return safe + ".svg"


def generate_image(
    title: str,
    car: str,
    event: str,
    style: str,
    era: str,
    force_svg: bool = False,
) -> dict:
    """
    Generate artwork for a print listing.
    Returns {"path": str, "url": str, "method": "dalle"|"svg", "success": bool}
    """
    filename = _title_to_filename(title)
    out_path = IMAGES_DIR / filename

    # Always regenerate if forced or file is SVG-only and DALL-E now available
    openai_key = os.getenv("OPENAI_API_KEY", "")

    if openai_key and not force_svg:
        try:
            result = _generate_dalle(title, car, event, style, era, out_path)
            if result["success"]:
                return result
        except Exception as exc:
            logger.warning("DALL-E generation failed, falling back to SVG: %s", exc)

    # SVG fallback — always succeeds
    svg_content = _make_svg_motorsport_art(title, car, event, style, era)
    out_path.with_suffix(".svg").write_text(svg_content, encoding="utf-8")
    svg_path = str(out_path.with_suffix(".svg"))
    return {
        "path": svg_path,
        "url": "/images/" + Path(svg_path).name,
        "method": "svg",
        "success": True,
    }


def _generate_dalle(title: str, car: str, event: str, style: str, era: str, out_path: Path) -> dict:
    import requests as _req
    prompt = (
        f"A stunning {style} motorsport art print of the {car} competing at the {event}. "
        f"{era} era. High quality, suitable for wall art. Professional illustration. "
        f"Bold composition, dramatic lighting. No text."
    )
    resp = _req.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"},
        json={"model": "dall-e-3", "prompt": prompt[:1000], "n": 1,
              "size": "1024x1024", "response_format": "url"},
        timeout=60,
    )
    resp.raise_for_status()
    img_url = resp.json()["data"][0]["url"]
    # Download the image
    img_resp = _req.get(img_url, timeout=30)
    img_resp.raise_for_status()
    png_path = out_path.with_suffix(".png")
    png_path.write_bytes(img_resp.content)
    return {
        "path": str(png_path),
        "url": "/images/" + png_path.name,
        "method": "dalle",
        "success": True,
    }


def image_exists(title: str) -> bool:
    filename = _title_to_filename(title)
    base = IMAGES_DIR / filename
    return base.with_suffix(".png").exists() or base.with_suffix(".svg").exists()


def get_image_url(title: str) -> str | None:
    filename = _title_to_filename(title)
    base = IMAGES_DIR / filename
    for ext in (".png", ".svg"):
        if (base.with_suffix(ext)).exists():
            return "/images/" + base.with_suffix(ext).name
    return None
