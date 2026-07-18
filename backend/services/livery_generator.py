"""
Livery Forge — generates SVG racing car livery designs.

Side-profile car templates with custom colour schemes, racing numbers,
sponsor zones, and style presets (clean, aggressive, retro, neon, gulf, etc.)

Car classes: gt3 | formula | rally | touring | lmp
"""
from __future__ import annotations

import math
import os
from pathlib import Path

IMAGES_DIR = Path(os.getenv("IMAGES_DIR", "/data/images"))

# ── Style palettes ────────────────────────────────────────────────────────────
STYLES: dict[str, dict] = {
    "clean":    {"primary": "#1a1a2e", "secondary": "#e94560", "accent": "#f5f5f5", "stripe": "#e94560",  "bg": "#f0f0f0"},
    "aggressive":{"primary":"#0d0d0d", "secondary": "#ff2200", "accent": "#ffffff", "stripe": "#ff6600",  "bg": "#1a1a1a"},
    "retro":    {"primary": "#1b3a6b", "secondary": "#f5c518", "accent": "#ffffff", "stripe": "#f5c518",  "bg": "#e8d5a3"},
    "neon":     {"primary": "#0a0a0a", "secondary": "#00ff88", "accent": "#00e5ff", "stripe": "#ff66ff",  "bg": "#050505"},
    "stealth":  {"primary": "#1a1a1a", "secondary": "#333333", "accent": "#666666", "stripe": "#444444",  "bg": "#0a0a0a"},
    "gulf":     {"primary": "#1e90ff", "secondary": "#ff8c00", "accent": "#ffffff", "stripe": "#ff8c00",  "bg": "#e0eeff"},
    "martini":  {"primary": "#ffffff", "secondary": "#003399", "accent": "#cc0000", "stripe": "#33cc33",  "bg": "#f5f5f5"},
    "jps":      {"primary": "#1a1a1a", "secondary": "#f5c518", "accent": "#f5c518", "stripe": "#f5c518",  "bg": "#0d0d0d"},
    "rothmans": {"primary": "#003399", "secondary": "#ffffff", "accent": "#cc0000", "stripe": "#ffcc00",  "bg": "#e0e8f0"},
}


def _palette(style: str, primary=None, secondary=None, accent=None) -> dict:
    base = STYLES.get(style.lower(), STYLES["clean"]).copy()
    if primary:
        base["primary"] = primary
    if secondary:
        base["secondary"] = secondary
    if accent:
        base["accent"] = accent
    return base


def _spokes(cx, cy, r, n, col, opacity=0.8, width=3) -> str:
    out = []
    for i in range(n):
        a = i * math.pi * 2 / n
        x2 = int(cx + r * math.cos(a))
        y2 = int(cy + r * math.sin(a))
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="{width}" opacity="{opacity}"/>')
    return "".join(out)


def _wheel_svg(cx, cy, outer, inner, hub, col_rim, col_accent) -> str:
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{outer}" fill="#111"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{inner}" fill="#1a1a1a" stroke="{col_rim}" stroke-width="3"/>'
        + _spokes(cx, cy, inner, 5, col_accent, 0.7, 3)
        + f'<circle cx="{cx}" cy="{cy}" r="{hub}" fill="#222" stroke="{col_accent}" stroke-width="2"/>'
    )


def _defs(p: dict) -> str:
    return f"""  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{p['bg']}"/>
      <stop offset="100%" stop-color="{p['primary']}" stop-opacity="0.1"/>
    </linearGradient>
    <linearGradient id="body" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{p['secondary']}" stop-opacity="0.5"/>
      <stop offset="100%" stop-color="{p['primary']}"/>
    </linearGradient>
    <filter id="glow"><feGaussianBlur stdDeviation="3" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <filter id="shadow"><feDropShadow dx="0" dy="4" stdDeviation="6"
      flood-color="{p['primary']}" flood-opacity="0.45"/></filter>
  </defs>"""


def _grid(vw, vh, p) -> str:
    lines = []
    for i in range(1, 9):
        y = int(i * vh / 8)
        lines.append(f'<line x1="0" y1="{y}" x2="{vw}" y2="{y}" stroke="{p["accent"]}" stroke-width="0.3" opacity="0.07"/>')
    for i in range(1, 13):
        x = int(i * vw / 12)
        lines.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{vh}" stroke="{p["accent"]}" stroke-width="0.3" opacity="0.07"/>')
    return "".join(lines)


def _title_bar(vw, vh, p, title, style) -> str:
    return (
        f'<rect x="0" y="{int(vh*0.92)}" width="{vw}" height="{int(vh*0.08)}" fill="{p["primary"]}" opacity="0.88"/>'
        f'<text x="14" y="{int(vh*0.975)}" font-family="Arial" font-size="11" font-weight="700" fill="{p["accent"]}" opacity="0.8">{title[:60]}</text>'
        f'<text x="{vw-14}" y="{int(vh*0.975)}" text-anchor="end" font-family="Arial" font-size="10" fill="{p["secondary"]}" opacity="0.7">{style.upper()} · Kingdom AI</text>'
    )


def _number_svg(vw, vh, p, number) -> str:
    nx, ny = int(vw * 0.46), int(vh * 0.52)
    fs = int(vh * 0.22)
    return (
        f'<text x="{nx}" y="{ny}" text-anchor="middle" dominant-baseline="middle"'
        f' font-family="\'Arial Black\',Impact,sans-serif" font-size="{fs}" font-weight="900"'
        f' fill="{p["accent"]}" opacity="0.95" filter="url(#glow)">{number}</text>'
        f'<text x="{nx}" y="{ny}" text-anchor="middle" dominant-baseline="middle"'
        f' font-family="\'Arial Black\',Impact,sans-serif" font-size="{fs}" font-weight="900"'
        f' fill="none" stroke="{p["secondary"]}" stroke-width="2" opacity="0.6">{number}</text>'
    )


def _sponsor_zone(vw, vh, p, text) -> str:
    x, y = int(vw * 0.16), int(vh * 0.75)
    w, h = int(vw * 0.22), int(vh * 0.09)
    cx = x + w // 2
    if not text:
        return (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{p["accent"]}" opacity="0.08" stroke="{p["accent"]}" stroke-width="0.5" stroke-opacity="0.25"/>'
            f'<text x="{cx}" y="{y+h//2+4}" text-anchor="middle" font-family="Arial" font-size="9" fill="{p["accent"]}" opacity="0.35">SPONSOR</text>'
        )
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{p["accent"]}" opacity="0.14" stroke="{p["secondary"]}" stroke-width="1"/>'
        f'<text x="{cx}" y="{y+h//2+4}" text-anchor="middle" font-family="\'Arial Black\',sans-serif" font-size="12" font-weight="900" fill="{p["accent"]}" opacity="0.9">{text[:22]}</text>'
    )


def _driver_text(vw, vh, p, name) -> str:
    if not name:
        return ""
    return (
        f'<text x="{int(vw*0.5)}" y="{int(vh*0.88)}" text-anchor="middle"'
        f' font-family="Arial" font-size="13" font-weight="700" fill="{p["accent"]}" opacity="0.85"'
        f' letter-spacing="3">{name[:28].upper()}</text>'
    )


# ── Car body builders ─────────────────────────────────────────────────────────

def _gt3(p) -> tuple[str, int, int]:
    vw, vh = 800, 320
    c, s, a, st = p["primary"], p["secondary"], p["accent"], p["stripe"]
    body = (
        f'<ellipse cx="420" cy="292" rx="310" ry="20" fill="#000" opacity="0.22"/>'
        f'<path d="M80,242 C80,242 108,180 158,155 C200,135 258,120 340,112 L420,108 C480,108 540,112 590,128 C640,142 680,165 700,200 L720,242 Z" fill="{c}" filter="url(#shadow)"/>'
        f'<path d="M198,148 L578,132 L598,172 L178,188 Z" fill="{st}" opacity="0.6"/>'
        f'<path d="M318,109 L498,112 L508,147 L328,144 Z" fill="{s}" opacity="0.8"/>'
        f'<path d="M280,112 C290,90 320,75 380,70 L440,70 C490,70 520,82 540,112 Z" fill="{c}"/>'
        f'<path d="M295,112 C302,93 326,80 375,76 L435,76 C478,76 504,89 524,112 Z" fill="{a}" opacity="0.22"/>'
        f'<rect x="680" y="155" width="70" height="8" rx="2" fill="{s}"/>'
        f'<rect x="690" y="148" width="6" height="30" rx="1" fill="{c}"/>'
        f'<rect x="740" y="148" width="6" height="30" rx="1" fill="{c}"/>'
        f'<rect x="58" y="240" width="52" height="6" rx="2" fill="{s}"/>'
        f'<path d="M138,242 L680,242 L685,252 L133,252 Z" fill="{s}" opacity="0.7"/>'
        f'<ellipse cx="208" cy="250" rx="72" ry="30" fill="{c}"/>'
        f'<ellipse cx="598" cy="250" rx="72" ry="30" fill="{c}"/>'
        + _wheel_svg(208, 260, 48, 38, 20, s, a)
        + _wheel_svg(598, 260, 48, 38, 20, s, a)
    )
    details = (
        f'<ellipse cx="100" cy="215" rx="18" ry="10" fill="{a}" opacity="0.9"/>'
        f'<ellipse cx="100" cy="215" rx="11" ry="6" fill="#fff" opacity="0.8"/>'
        f'<rect x="76" y="208" width="35" height="3" rx="1" fill="{s}" opacity="0.85"/>'
        f'<rect x="704" y="206" width="20" height="20" rx="3" fill="{s}" opacity="0.85"/>'
        f'<rect x="707" y="209" width="14" height="14" rx="2" fill="#f00" opacity="0.65"/>'
        f'<line x1="278" y1="150" x2="548" y2="158" stroke="{a}" stroke-width="1.5" opacity="0.25"/>'
        + "".join(f'<rect x="{148+i*8}" y="185" width="5" height="20" rx="1" fill="{a}" opacity="0.18"/>' for i in range(4))
    )
    return body + details, vw, vh


def _formula(p) -> tuple[str, int, int]:
    vw, vh = 800, 280
    c, s, a, st = p["primary"], p["secondary"], p["accent"], p["stripe"]
    body = (
        f'<ellipse cx="400" cy="268" rx="340" ry="14" fill="#000" opacity="0.18"/>'
        f'<path d="M30,215 L130,195 L145,225 L40,230 Z" fill="{c}"/>'
        f'<path d="M30,215 L130,195 L135,206 L35,222 Z" fill="{s}" opacity="0.65"/>'
        f'<path d="M130,175 C150,165 200,158 270,155 L530,155 C600,158 650,168 680,185 L700,225 L110,225 Z" fill="{c}" filter="url(#shadow)"/>'
        f'<path d="M200,156 L520,157 L530,186 L195,184 Z" fill="{st}" opacity="0.6"/>'
        f'<path d="M308,155 C314,134 340,122 378,118 L422,118 C455,120 475,132 490,155 Z" fill="{c}"/>'
        f'<path d="M318,155 C324,137 344,127 376,124 L424,124 C450,127 468,138 478,155 Z" fill="#080808"/>'
        f'<path d="M334,140 C340,128 360,122 388,120 L412,120 C438,122 458,129 462,140 L455,142 C445,132 426,127 400,126 C375,127 356,132 346,142 Z" fill="{s}" opacity="0.88"/>'
        f'<rect x="18" y="228" width="152" height="8" rx="2" fill="{s}"/>'
        f'<rect x="8" y="232" width="167" height="5" rx="2" fill="{c}" opacity="0.75"/>'
        f'<rect x="48" y="218" width="10" height="18" fill="{c}"/>'
        f'<rect x="108" y="218" width="10" height="18" fill="{c}"/>'
        f'<rect x="638" y="155" width="132" height="10" rx="2" fill="{s}"/>'
        f'<rect x="633" y="161" width="142" height="6" rx="2" fill="{a}" opacity="0.28"/>'
        f'<rect x="653" y="161" width="8" height="36" fill="{c}"/>'
        f'<rect x="743" y="161" width="8" height="36" fill="{c}"/>'
        f'<path d="M478,170 L652,172 L667,210 L473,210 Z" fill="{c}" opacity="0.88"/>'
        f'<path d="M488,172 L642,174 L652,195 L483,193 Z" fill="{st}" opacity="0.38"/>'
        + _wheel_svg(178, 235, 36, 27, 12, s, a)
        + _wheel_svg(618, 235, 39, 30, 14, s, a)
        + f'<rect x="293" y="150" width="18" height="8" rx="2" fill="{c}"/>'
        f'<rect x="484" y="150" width="18" height="8" rx="2" fill="{c}"/>'
        f'<rect x="26" y="213" width="18" height="4" rx="2" fill="{s}" opacity="0.88"/>'
        f'<line x1="638" y1="158" x2="770" y2="158" stroke="{a}" stroke-width="1.5" opacity="0.35"/>'
    )
    return body, vw, vh


def _rally(p) -> tuple[str, int, int]:
    vw, vh = 800, 330
    c, s, a, st = p["primary"], p["secondary"], p["accent"], p["stripe"]
    body = (
        f'<ellipse cx="400" cy="312" rx="282" ry="18" fill="#000" opacity="0.28"/>'
        f'<path d="M100,256 C100,256 120,175 170,150 C210,130 270,118 360,112 L440,110 C510,110 565,120 610,140 C655,160 690,190 706,256 Z" fill="{c}" filter="url(#shadow)"/>'
        f'<path d="M184,148 L581,137 L596,175 L194,186 Z" fill="{st}" opacity="0.6"/>'
        f'<path d="M298,112 L498,112 L508,148 L308,148 Z" fill="{s}" opacity="0.76"/>'
        f'<path d="M284,112 C292,88 324,72 384,68 L418,68 C472,68 506,82 520,112 Z" fill="{c}"/>'
        f'<path d="M368,68 L412,68 L417,50 L363,50 Z" fill="{s}"/>'
        f'<rect x="361" y="44" width="56" height="10" rx="3" fill="{c}"/>'
        f'<path d="M296,112 C303,91 328,78 380,74 L418,74 C460,76 487,90 506,112 Z" fill="{a}" opacity="0.2"/>'
        + "".join(f'<circle cx="{308+i*25}" cy="52" r="6" fill="{a}" opacity="0.85"/><circle cx="{308+i*25}" cy="52" r="3" fill="#fff" opacity="0.9"/>' for i in range(7))
        + _wheel_svg(228, 272, 56, 44, 22, s, a)
        + _wheel_svg(573, 272, 56, 44, 22, s, a)
        + f'<rect x="156" y="278" width="20" height="30" rx="2" fill="{c}" opacity="0.8"/>'
        f'<rect x="618" y="278" width="20" height="30" rx="2" fill="{c}" opacity="0.8"/>'
        f'<circle cx="116" cy="222" r="16" fill="{a}" opacity="0.88"/>'
        f'<circle cx="116" cy="222" r="10" fill="#fff" opacity="0.82"/>'
        f'<rect x="696" y="215" width="16" height="22" rx="3" fill="{s}"/>'
    )
    return body, vw, vh


def _touring(p) -> tuple[str, int, int]:
    vw, vh = 800, 302
    c, s, a, st = p["primary"], p["secondary"], p["accent"], p["stripe"]
    body = (
        f'<ellipse cx="400" cy="287" rx="302" ry="16" fill="#000" opacity="0.2"/>'
        f'<path d="M88,242 C88,242 114,180 164,155 C204,135 264,122 354,116 L446,116 C536,118 586,130 626,152 C666,172 696,205 712,242 Z" fill="{c}" filter="url(#shadow)"/>'
        f'<path d="M193,150 L588,141 L603,176 L198,184 Z" fill="{st}" opacity="0.58"/>'
        f'<path d="M338,116 L458,116 L467,151 L347,151 Z" fill="{s}" opacity="0.8"/>'
        f'<rect x="268" y="92" width="264" height="26" rx="8" fill="{c}"/>'
        f'<path d="M268,118 C268,98 280,93 300,93 L500,93 C520,93 532,98 532,118 Z" fill="{c}"/>'
        f'<path d="M280,118 C282,100 298,96 318,95 L482,95 C500,96 516,101 518,118 Z" fill="{a}" opacity="0.2"/>'
        f'<rect x="532" y="98" width="56" height="36" rx="4" fill="{a}" opacity="0.17"/>'
        f'<line x1="298" y1="142" x2="298" y2="237" stroke="{a}" stroke-width="1.5" opacity="0.22"/>'
        f'<line x1="428" y1="140" x2="428" y2="237" stroke="{a}" stroke-width="1.5" opacity="0.22"/>'
        f'<line x1="538" y1="143" x2="538" y2="237" stroke="{a}" stroke-width="1.5" opacity="0.18"/>'
        + _wheel_svg(218, 254, 44, 34, 16, s, a)
        + _wheel_svg(582, 254, 44, 34, 16, s, a)
        + f'<rect x="163" y="239" width="477" height="8" rx="2" fill="{s}" opacity="0.68"/>'
        f'<rect x="86" y="210" width="30" height="18" rx="3" fill="{a}" opacity="0.85"/>'
        f'<rect x="90" y="213" width="22" height="12" rx="2" fill="#fff" opacity="0.8"/>'
        f'<rect x="688" y="210" width="24" height="18" rx="3" fill="{s}" opacity="0.82"/>'
        f'<rect x="692" y="213" width="18" height="12" rx="2" fill="#f00" opacity="0.65"/>'
    )
    return body, vw, vh


def _lmp(p) -> tuple[str, int, int]:
    vw, vh = 800, 280
    c, s, a, st = p["primary"], p["secondary"], p["accent"], p["stripe"]
    body = (
        f'<ellipse cx="420" cy="268" rx="342" ry="14" fill="#000" opacity="0.2"/>'
        f'<path d="M48,226 C58,200 88,175 138,162 C188,150 258,143 358,140 L522,138 C612,140 662,150 692,168 C722,185 752,208 762,226 Z" fill="{c}" filter="url(#shadow)"/>'
        f'<path d="M178,158 L658,142 L668,168 L183,186 Z" fill="{st}" opacity="0.52"/>'
        f'<path d="M348,138 L532,138 L540,168 L356,170 Z" fill="{s}" opacity="0.8"/>'
        f'<path d="M328,140 C336,114 358,104 393,102 L417,102 C446,104 466,115 474,140 Z" fill="{c}"/>'
        f'<path d="M338,140 C345,118 363,110 391,108 L409,108 C432,110 452,118 462,140 Z" fill="{a}" opacity="0.18"/>'
        f'<path d="M588,140 C638,140 692,164 702,222 L558,224 C553,185 568,154 588,140 Z" fill="{c}" opacity="0.8"/>'
        f'<rect x="700" y="130" width="80" height="12" rx="3" fill="{s}"/>'
        f'<rect x="688" y="138" width="102" height="7" rx="2" fill="{a}" opacity="0.38"/>'
        f'<rect x="708" y="138" width="8" height="42" fill="{c}"/>'
        f'<rect x="758" y="138" width="8" height="42" fill="{c}"/>'
        f'<path d="M128,175 C118,175 93,190 86,215 L198,218 C196,185 168,173 128,175 Z" fill="{c}" opacity="0.8"/>'
        f'<path d="M46,218 L88,178 L104,188 L66,226 Z" fill="{s}" opacity="0.78"/>'
        f'<rect x="50" y="212" width="40" height="5" rx="2" fill="{a}" opacity="0.92"/>'
        + _wheel_svg(143, 228, 36, 28, 13, s, a)
        + _wheel_svg(626, 225, 40, 31, 14, s, a)
        + "".join(f'<rect x="{708+i*9}" y="225" width="6" height="14" rx="1" fill="{c}" opacity="0.55"/>' for i in range(6))
    )
    return body, vw, vh


_CAR_BUILDERS = {
    "gt3": _gt3,
    "formula": _formula,
    "rally": _rally,
    "touring": _touring,
    "lmp": _lmp,
}


# ── Public API ────────────────────────────────────────────────────────────────

def generate_livery(
    commission_id: str,
    car_class: str = "gt3",
    style: str = "clean",
    primary_colour: str | None = None,
    secondary_colour: str | None = None,
    accent_colour: str | None = None,
    racing_number: str = "17",
    driver_name: str = "",
    sponsor_text: str = "",
    custom_title: str = "",
) -> dict:
    """Generate a racing livery SVG and save to IMAGES_DIR."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    p = _palette(style, primary_colour, secondary_colour, accent_colour)
    builder = _CAR_BUILDERS.get(car_class.lower(), _gt3)

    try:
        car_svg, vw, vh = builder(p)
    except Exception as e:
        return {"path": "", "url": "", "svg": "", "success": False, "error": str(e)}

    title = (custom_title or f"#{racing_number} {car_class.upper()} Livery")[:60]

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" width="{vw}" height="{vh}">
{_defs(p)}
  <rect width="{vw}" height="{vh}" fill="url(#bg)"/>
{_grid(vw, vh, p)}
{car_svg}
{_number_svg(vw, vh, p, racing_number)}
{_sponsor_zone(vw, vh, p, sponsor_text)}
{_driver_text(vw, vh, p, driver_name)}
{_title_bar(vw, vh, p, title, style)}
</svg>"""

    filename = f"livery_{commission_id}.svg"
    path = IMAGES_DIR / filename
    try:
        path.write_text(svg)
    except Exception as e:
        return {"path": "", "url": "", "svg": svg, "success": False, "error": str(e)}

    return {
        "path": str(path),
        "url": f"/images/{filename}",
        "svg": svg,
        "success": True,
        "error": None,
    }


def livery_exists(commission_id: str) -> bool:
    return (IMAGES_DIR / f"livery_{commission_id}.svg").exists()


def get_livery_url(commission_id: str) -> str | None:
    return f"/images/livery_{commission_id}.svg" if livery_exists(commission_id) else None


def list_styles() -> list[str]:
    return list(STYLES.keys())


def list_car_classes() -> list[str]:
    return list(_CAR_BUILDERS.keys())
