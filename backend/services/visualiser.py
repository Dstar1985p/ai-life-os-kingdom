"""
Animated audio visualiser MP4 — radial design for YouTube, TikTok, Instagram.
Uses moviepy + numpy. Requires ffmpeg. Falls back gracefully if unavailable.
"""
from __future__ import annotations

import math

FFMPEG_AVAILABLE = False
try:
    import numpy as np
    try:
        import moviepy.editor as mpy          # moviepy 1.x
    except ImportError:
        import moviepy as mpy                 # moviepy 2.x
    from moviepy.audio.io.AudioFileClip import AudioFileClip
    FFMPEG_AVAILABLE = True
except Exception:
    pass


class VisualizerUnavailableError(Exception):
    pass


# ── Constants ────────────────────────────────────────────────────────────────

_N_BARS = 128           # frequency bars around the circle
_MAX_PARTICLES = 600    # particle ring buffer size
_HUE_SPEED = 0.024      # hue cycles per second (full cycle ≈ 100 s)
_BLOOM_SHIFTS = [(-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, -2), (-2, 2), (2, 2)]


# ── Colour helpers ────────────────────────────────────────────────────────────

def _hsv_to_rgb_scalar(h: float, s: float, v: float):
    """h, s, v in [0, 1]. Returns (r, g, b) ints 0-255."""
    h6 = (h % 1.0) * 6.0
    i = int(h6) % 6
    f = h6 - math.floor(h6)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    rgb = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]
    return (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))


def _hsv_to_rgb_vec(h, s, v):
    """Vectorized HSV → RGB. h/s/v are float arrays [0, 1]. Returns float array [..., 3] in [0, 255]."""
    h6 = (h % 1.0) * 6.0
    i = h6.astype(np.int32) % 6
    f = h6 - np.floor(h6)
    p = v * (1 - s)
    q = v * (1 - s * f)
    t_c = v * (1 - s * (1 - f))
    result = np.zeros(h.shape + (3,), dtype=np.float32)
    for k, (rv, gv, bv) in enumerate([(v, t_c, p), (q, v, p), (p, v, t_c),
                                        (p, q, v), (t_c, p, v), (v, p, q)]):
        m = i == k
        result[m, 0] = rv[m] if hasattr(rv, '__len__') else rv
        result[m, 1] = gv[m] if hasattr(gv, '__len__') else gv
        result[m, 2] = bv[m] if hasattr(bv, '__len__') else bv
    return result * 255.0


# ── Line drawing (used for waveform ring) ────────────────────────────────────

def _draw_text_simple(frame, text: str, x: int, y: int, colour, scale: int = 1):
    """Pixel-font text onto float32 frame."""
    FONT = {
        'A': ['01110', '10001', '10001', '11111', '10001', '10001', '10001'],
        'B': ['11110', '10001', '10001', '11110', '10001', '10001', '11110'],
        'C': ['01111', '10000', '10000', '10000', '10000', '10000', '01111'],
        'D': ['11110', '10001', '10001', '10001', '10001', '10001', '11110'],
        'E': ['11111', '10000', '10000', '11110', '10000', '10000', '11111'],
        'F': ['11111', '10000', '10000', '11110', '10000', '10000', '10000'],
        'G': ['01111', '10000', '10000', '10111', '10001', '10001', '01111'],
        'H': ['10001', '10001', '10001', '11111', '10001', '10001', '10001'],
        'I': ['11111', '00100', '00100', '00100', '00100', '00100', '11111'],
        'J': ['00111', '00010', '00010', '00010', '10010', '10010', '01100'],
        'K': ['10001', '10010', '10100', '11000', '10100', '10010', '10001'],
        'L': ['10000', '10000', '10000', '10000', '10000', '10000', '11111'],
        'M': ['10001', '11011', '10101', '10001', '10001', '10001', '10001'],
        'N': ['10001', '11001', '10101', '10011', '10001', '10001', '10001'],
        'O': ['01110', '10001', '10001', '10001', '10001', '10001', '01110'],
        'P': ['11110', '10001', '10001', '11110', '10000', '10000', '10000'],
        'Q': ['01110', '10001', '10001', '10001', '10101', '10010', '01101'],
        'R': ['11110', '10001', '10001', '11110', '10100', '10010', '10001'],
        'S': ['01111', '10000', '10000', '01110', '00001', '00001', '11110'],
        'T': ['11111', '00100', '00100', '00100', '00100', '00100', '00100'],
        'U': ['10001', '10001', '10001', '10001', '10001', '10001', '01110'],
        'V': ['10001', '10001', '10001', '10001', '10001', '01010', '00100'],
        'W': ['10001', '10001', '10001', '10101', '10101', '11011', '10001'],
        'X': ['10001', '10001', '01010', '00100', '01010', '10001', '10001'],
        'Y': ['10001', '10001', '01010', '00100', '00100', '00100', '00100'],
        'Z': ['11111', '00001', '00010', '00100', '01000', '10000', '11111'],
        ' ': ['00000', '00000', '00000', '00000', '00000', '00000', '00000'],
        '-': ['00000', '00000', '00000', '11111', '00000', '00000', '00000'],
        '.': ['00000', '00000', '00000', '00000', '00000', '00100', '00000'],
        '|': ['00100', '00100', '00100', '00100', '00100', '00100', '00100'],
        '0': ['01110', '10001', '10011', '10101', '11001', '10001', '01110'],
        '1': ['00100', '01100', '00100', '00100', '00100', '00100', '01110'],
        '2': ['01110', '10001', '00001', '00110', '01000', '10000', '11111'],
        '3': ['11110', '00001', '00001', '01110', '00001', '00001', '11110'],
        '4': ['00010', '00110', '01010', '10010', '11111', '00010', '00010'],
        '5': ['11111', '10000', '10000', '11110', '00001', '00001', '11110'],
        '6': ['01110', '10000', '10000', '11110', '10001', '10001', '01110'],
        '7': ['11111', '00001', '00010', '00100', '01000', '10000', '10000'],
        '8': ['01110', '10001', '10001', '01110', '10001', '10001', '01110'],
        '9': ['01110', '10001', '10001', '01111', '00001', '00001', '01110'],
    }
    h, w = frame.shape[:2]
    col = np.array(colour, dtype=np.float32)
    px = x
    for char in text.upper():
        glyph = FONT.get(char, FONT[' '])
        for row_i, row in enumerate(glyph):
            for col_i, pixel in enumerate(row):
                if pixel == '1':
                    for sy in range(scale):
                        for sx in range(scale):
                            fy = y + row_i * scale + sy
                            fx = px + col_i * scale + sx
                            if 0 <= fy < h and 0 <= fx < w:
                                frame[fy, fx] = np.maximum(frame[fy, fx], col)
        px += (6 * scale) + scale


# ── Audio analysis helpers ────────────────────────────────────────────────────

def _get_fft(audio_mono, t: float, fps_audio: int, n_bars: int,
             smooth_state: list, chunk_size: int):
    """Return smoothed log-spaced FFT bars [0, 1]."""
    start = int(t * fps_audio)
    chunk = audio_mono[start:start + chunk_size]
    if len(chunk) < chunk_size:
        chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
    window = np.hanning(len(chunk))
    raw = np.abs(np.fft.rfft(chunk * window, n=chunk_size))
    # Spectral tilt compensation — music rolls off ~1/f, lift the highs so
    # hats/snares light up as much as the sub bass
    raw = raw * np.sqrt(np.arange(1, len(raw) + 1, dtype=np.float32))
    n_fft = len(raw)
    log_idx = np.logspace(0, math.log10(max(n_fft - 1, 2)), n_bars + 1).astype(int)
    log_idx = np.clip(log_idx, 0, n_fft - 1)
    bars = np.array([raw[log_idx[i]:log_idx[i + 1] + 1].mean() for i in range(n_bars)],
                    dtype=np.float32)
    if bars.max() > 0:
        bars /= bars.max()
    bars = bars ** 0.65   # perceptual compression — mid-level details visible
    # Attack fast, release slow
    prev = smooth_state[0]
    smoothed = np.where(bars > prev, 0.35 * prev + 0.65 * bars, 0.72 * prev + 0.28 * bars)
    smooth_state[0] = smoothed
    return smoothed.copy()


def _get_bass_energy(audio_mono, t: float, fps_audio: int) -> float:
    """Sub-bass energy ratio relative to full spectrum."""
    sz = fps_audio // 20
    start = int(t * fps_audio)
    chunk = audio_mono[start:start + sz]
    if len(chunk) < 4:
        return 0.0
    raw = np.abs(np.fft.rfft(chunk))
    bass_bins = max(1, len(raw) // 12)
    return float(np.clip(raw[:bass_bins].mean() / (raw.mean() + 1e-8), 0, 8))


# ── Bloom ─────────────────────────────────────────────────────────────────────

def _apply_bloom(frame: 'np.ndarray', strength: float = 0.35) -> 'np.ndarray':
    """Cheap directional-shift bloom: adds glow around bright pixels."""
    bloom = frame * strength
    result = frame.copy()
    for dy, dx in _BLOOM_SHIFTS:
        shifted = np.roll(np.roll(bloom, dy, axis=0), dx, axis=1)
        np.maximum(result, shifted, out=result)
    return result


# ── Turntable disc ────────────────────────────────────────────────────────────

GREEN_HUE = 0.42          # PulseBreak neon green (#00ff88 territory)


def _make_disc(disc_r: int, logo_path: str | None):
    """Pre-render the spinning disc as an RGBA PIL image.

    If a logo file is supplied it becomes the disc face (circle-cropped);
    otherwise a procedural vinyl: grooved black disc, neon-green label,
    PULSEBREAK wordmark, and a position marker so the spin reads clearly.
    """
    from PIL import Image, ImageDraw

    size = disc_r * 2
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA").resize((size, size))
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
            img.paste(logo, (0, 0), mask)
            return img
        except Exception:
            pass  # fall through to procedural vinyl

    c = disc_r
    # Vinyl body
    draw.ellipse([0, 0, size - 1, size - 1], fill=(14, 14, 16, 255))
    # Grooves
    for gr in range(int(disc_r * 0.45), disc_r - 2, 5):
        draw.ellipse([c - gr, c - gr, c + gr, c + gr],
                     outline=(34, 38, 36, 255), width=1)
    # Neon-green label
    label_r = int(disc_r * 0.40)
    draw.ellipse([c - label_r, c - label_r, c + label_r, c + label_r],
                 fill=(0, 40, 20, 255), outline=(0, 255, 136, 255), width=3)
    # Spindle
    draw.ellipse([c - 4, c - 4, c + 4, c + 4], fill=(0, 255, 136, 255))
    # Wordmark (pixel font onto the label via numpy then back)
    arr = np.array(img).astype(np.float32)
    text = "PULSEBREAK"
    scale = max(1, label_r // 40)
    tw = len(text) * (6 * scale + scale)
    _draw_text_simple(arr[:, :, :3], text, x=c - tw // 2, y=c - label_r // 2,
                      colour=(0, 255, 136), scale=scale)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(img)
    # Position marker on the rim so rotation is obvious
    draw.ellipse([c - 6, 6, c + 6, 18], fill=(0, 255, 136, 255))
    return img


# ── Main ──────────────────────────────────────────────────────────────────────

def generate_visualiser(
    audio_path: str,
    output_path: str,
    title: str = "PulseBreak",
    artist: str = "PulseBreak",
    bg_colour: tuple = (5, 0, 20),
    bar_colour: tuple = (0, 220, 180),
    accent_colour: tuple = (180, 0, 255),
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    fmt: str = "youtube",   # "youtube" | "tiktok" | "square"
    style: str = "turntable",   # "turntable" (black + neon green + spinning logo) | "cosmic" (rainbow)
    logo_path: str | None = None,   # optional PNG for the disc; auto-detects pulsebreak_tracks/logo.png
    # Legacy positional compat — ignored (format is now radial always)
    **_kwargs,
) -> str:
    """
    Generate a radial audio visualiser MP4.

    fmt:
      "youtube"  → 1920×1080 (16:9)
      "tiktok"   → 1080×1920 (9:16 for Reels/TikTok)
      "square"   → 1080×1080 (Instagram square)
    """
    if not FFMPEG_AVAILABLE:
        raise VisualizerUnavailableError("moviepy/ffmpeg not available")

    if fmt == "tiktok":
        width, height = 1080, 1920
    elif fmt == "square":
        width, height = 1080, 1080

    audio_path, output_path = str(audio_path), str(output_path)

    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    fps_audio = 44100
    audio_array = audio_clip.to_soundarray(fps=fps_audio)
    audio_mono = (audio_array.mean(axis=1) if audio_array.ndim > 1 else audio_array).astype(np.float32)

    # ── Geometry ──────────────────────────────────────────────────────────────
    cx, cy = width // 2, height // 2
    short = min(width, height)
    r_inner = short * 0.13     # radius of center circle
    r_max = short * 0.44       # maximum bar reach
    r_wf = r_inner * 0.88      # waveform ring radius

    # ── Turntable style setup ─────────────────────────────────────────────────
    LIME = 0.195                       # PulseBreak electric lime (#c8ff00)
    turntable = style == "turntable"
    disc_r = int(r_inner * 1.30)
    disc_img = None
    if turntable:
        if not logo_path:
            import os as _os
            for cand in ("pulsebreak_tracks/logo.png",
                         _os.path.join(_os.path.dirname(__file__), "..", "static", "pulsebreak_logo.png")):
                if _os.path.exists(cand):
                    logo_path = cand
                    break
        try:
            disc_img = _make_disc(disc_r, logo_path)
        except Exception:
            disc_img = None
        if disc_img is None:
            turntable = False   # fall back to cosmic style

    # ── Precompute polar grid ─────────────────────────────────────────────────
    ys_g, xs_g = np.mgrid[0:height, 0:width].astype(np.float32)
    dx_g = xs_g - cx
    dy_g = ys_g - cy
    theta_g = np.arctan2(dy_g, dx_g) % (2 * math.pi)   # (H, W) in [0, 2π]
    r_g = np.sqrt(dx_g ** 2 + dy_g ** 2)                # (H, W)

    # Which bar does each pixel belong to?
    bar_idx_g = (theta_g / (2 * math.pi) * _N_BARS).astype(np.int32) % _N_BARS  # (H, W)

    # Mirror map: angle position → spectrum index, symmetric about the vertical
    # axis so the display is balanced no matter how bass-heavy the track is.
    # Bar 0 = top, sweeping down both sides to the highest band at the bottom.
    _half = _N_BARS // 2
    _mirror = np.minimum(np.arange(_N_BARS), _N_BARS - np.arange(_N_BARS)) % _half
    _mirror = np.clip(_mirror, 0, _half - 1)

    bar_angles = np.linspace(0, 2 * math.pi, _N_BARS, endpoint=False)
    bar_center_theta = bar_angles[bar_idx_g]  # (H, W) — center angle of nearest bar
    theta_diff = theta_g - bar_center_theta
    # Wrap to [-π, π]
    theta_diff = ((theta_diff + math.pi) % (2 * math.pi)) - math.pi

    bar_half_rad = math.pi / _N_BARS * 0.62  # 62% fill, 38% gap
    in_bar_ang = np.abs(theta_diff) <= bar_half_rad  # (H, W) bool

    in_annulus = (r_g >= r_inner) & (r_g <= r_max)   # (H, W) bool
    r_norm_g = np.clip((r_g - r_inner) / max(r_max - r_inner, 1), 0.0, 1.0)  # (H, W)

    # Bar hue offset per pixel (0–0.4 spread across all bars)
    bar_hue_g = (bar_idx_g / _N_BARS * 0.4).astype(np.float32)  # (H, W)

    # Inner circle mask + normalized distance for the gradient orb
    ic_r = int(r_inner * 0.82)
    ys_ic = np.arange(max(0, cy - ic_r), min(height, cy + ic_r + 1))
    xs_ic = np.arange(max(0, cx - ic_r), min(width, cx + ic_r + 1))
    ic_yg, ic_xg = np.meshgrid(ys_ic, xs_ic, indexing='ij')
    ic_dist = np.sqrt((ic_xg - cx) ** 2 + (ic_yg - cy) ** 2)
    ic_in = ic_dist <= ic_r
    ic_ys = ic_yg[ic_in].astype(int)
    ic_xs = ic_xg[ic_in].astype(int)
    ic_grad = (1.0 - (ic_dist[ic_in] / max(ic_r, 1)) ** 1.5).astype(np.float32)

    # Static background: deep space + subtle centre nebula
    bg = np.zeros((height, width, 3), dtype=np.float32)
    max_dist = math.sqrt(cx ** 2 + cy ** 2)
    nebula = np.clip(1.0 - r_g / max_dist, 0.0, 1.0) * 0.28
    bg[:, :, 0] = nebula * 18
    bg[:, :, 1] = nebula * 4
    bg[:, :, 2] = nebula * 38

    # ── State ─────────────────────────────────────────────────────────────────
    smooth_state = [np.zeros(_N_BARS, dtype=np.float32)]
    particles = np.zeros((_MAX_PARTICLES, 6), dtype=np.float32)
    # columns: [x, y, vx, vy, life, hue]
    p_head = [0]
    beat_cooldown = [0]
    beat_flash = [0.0]
    rolling_bass = [0.08]
    chunk_size = fps_audio // 8  # ≈ 5512 samples — gives ~90ms window

    cos_a = np.cos(bar_angles)
    sin_a = np.sin(bar_angles)

    # ── Extra state for the upgraded engine ──────────────────────────────────
    shockwaves = []            # list of [radius, strength, hue]
    trail = [None]             # previous frame for motion trails
    star_count = 140
    rng = np.random.default_rng(7)
    star_xs = rng.integers(0, width, star_count)
    star_ys = rng.integers(0, height, star_count)
    star_phase = rng.uniform(0, 2 * math.pi, star_count).astype(np.float32)
    star_speed = rng.uniform(1.5, 5.0, star_count).astype(np.float32)
    rot_state = [0.0]          # slowly rotating spectrum

    def _spawn_particles(fft_bars, hue_base):
        hot = np.where(fft_bars > 0.55)[0]
        for i in hot[::4]:   # every 4th hot bar to keep count manageable
            r_tip = r_inner + fft_bars[i] * (r_max - r_inner)
            tx = cx + r_tip * cos_a[i]
            ty = cy + r_tip * sin_a[i]
            speed = 1.2 + fft_bars[i] * 2.5
            vx = cos_a[i] * speed + np.random.randn() * 0.4
            vy = sin_a[i] * speed + np.random.randn() * 0.4
            idx = p_head[0] % _MAX_PARTICLES
            particles[idx] = [tx, ty, vx, vy, 1.0, (hue_base + i / _N_BARS * 0.85) % 1.0]
            p_head[0] += 1

    def make_frame(t: float):
        hue_base = LIME if turntable else (t * _HUE_SPEED) % 1.0

        # ── Audio analysis ────────────────────────────────────────────────────
        fft_bars = _get_fft(audio_mono, t, fps_audio, _N_BARS, smooth_state, chunk_size)
        bass = _get_bass_energy(audio_mono, t, fps_audio)

        # Three-band energies: bass drives the core + shockwaves,
        # mids drive bar brightness, highs drive stars + particles
        n3 = _N_BARS // 3
        e_bass = float(fft_bars[:n3].mean())
        e_mid  = float(fft_bars[n3:2 * n3].mean())
        e_high = float(fft_bars[2 * n3:].mean())

        # Beat detection (kick)
        rolling_bass[0] = rolling_bass[0] * 0.94 + bass * 0.06
        is_beat = (bass > rolling_bass[0] * 1.85) and beat_cooldown[0] <= 0
        if is_beat:
            beat_cooldown[0] = int(fps * 0.14)
            beat_flash[0] = 0.45
            shockwaves.append([r_inner * 1.05, 1.0, hue_base])
        else:
            beat_cooldown[0] = max(0, beat_cooldown[0] - 1)
            beat_flash[0] = max(0.0, beat_flash[0] - 0.05)

        # Spectrum rotation — speeds up with the music's energy
        rot_state[0] = (rot_state[0] + (0.0012 + e_mid * 0.004)) % (2 * math.pi)
        rot = rot_state[0]

        # ── Background: breathing nebula ─────────────────────────────────────
        frame = bg.copy() if not turntable else np.zeros((height, width, 3), dtype=np.float32)
        breathe = 0.75 + e_bass * 0.9 + beat_flash[0] * 0.8
        neb_hue = (hue_base + 0.55) % 1.0
        neb_r, neb_g, neb_b = _hsv_to_rgb_scalar(neb_hue, 0.85, 1.0)
        if not turntable:
            neb = np.clip(1.0 - r_g / (short * 0.75), 0.0, 1.0) ** 2 * 30.0 * breathe
            frame[:, :, 0] += neb * (neb_r / 255.0)
            frame[:, :, 1] += neb * (neb_g / 255.0)
            frame[:, :, 2] += neb * (neb_b / 255.0)

        # ── Starfield twinkling with the highs ────────────────────────────────
        tw = (np.sin(star_phase + t * star_speed) * 0.5 + 0.5) * (0.35 + e_high * 1.6)
        star_v = np.clip(tw, 0, 1) * (90 if turntable else 200)
        if turntable:
            star_rgb = np.stack([star_v * 0.75, star_v, star_v * 0.1], axis=-1)
        else:
            star_rgb = np.stack([star_v, star_v, np.minimum(star_v * 1.15, 255)], axis=-1)
        frame[star_ys, star_xs] = np.maximum(frame[star_ys, star_xs], star_rgb)

        # ── Kick shockwave rings ──────────────────────────────────────────────
        for sw in shockwaves:
            ring_w = 6.0 + (1.0 - sw[1]) * 10.0
            ring_mask = np.abs(r_g - sw[0]) < ring_w
            if ring_mask.any():
                rr, gg, bb = _hsv_to_rgb_scalar(sw[2], 0.65, sw[1])
                ring_col = np.array([rr, gg, bb], dtype=np.float32)
                frame[ring_mask] = np.maximum(frame[ring_mask], ring_col)
            sw[0] += short * 0.016          # expand
            sw[1] *= 0.90                   # fade
        shockwaves[:] = [sw for sw in shockwaves if sw[1] > 0.06 and sw[0] < short]

        # ── Smooth spectrum corona (shorts-style flame ring around the core) ──
        # Heavy angular smoothing turns the spectrum into a fluid blob that
        # breathes with the music — the signature look of shorts visualisers.
        theta_rot = (theta_g + rot) % (2 * math.pi)
        bar_idx_r = (theta_rot / (2 * math.pi) * _N_BARS).astype(np.int32) % _N_BARS
        spectrum = fft_bars[:_half] if len(fft_bars) >= _half else fft_bars
        full_spec = spectrum[_mirror]                       # (_N_BARS,) mirrored
        kernel = np.array([1, 4, 8, 12, 8, 4, 1], dtype=np.float32)
        kernel /= kernel.sum()
        smooth_spec = np.convolve(
            np.concatenate([full_spec[-3:], full_spec, full_spec[:3]]),
            kernel, mode="same")[3:-3]
        pump = 1.0 + min(bass / max(rolling_bass[0], 0.01), 3.0) * 0.10 + beat_flash[0] * 0.25
        core_r = disc_r if turntable else r_inner
        corona_amp = (r_inner * 0.05 + smooth_spec * r_inner * 0.85) * pump
        corona_r_pix = core_r * 1.02 + corona_amp[bar_idx_r]   # (H, W)
        in_corona = (r_g >= core_r * 0.9) & (r_g <= corona_r_pix)
        if in_corona.any():
            depth = np.clip((corona_r_pix[in_corona] - r_g[in_corona]) /
                            np.maximum(corona_amp[bar_idx_r][in_corona], 1.0), 0, 1)
            hue_spread_cor = 0.035 if turntable else 0.5
            h_cor = (hue_base + (bar_idx_r[in_corona] / _N_BARS) * hue_spread_cor) % 1.0
            s_cor = np.full(h_cor.shape, 0.95, dtype=np.float32)
            v_cor = np.clip(0.35 + depth * 0.65, 0, 1)
            cor_rgb = _hsv_to_rgb_vec(h_cor, s_cor, v_cor)
            frame[in_corona] = np.maximum(frame[in_corona], cor_rgb)
            # White-hot rim right at the corona edge
            rim = in_corona & (np.abs(r_g - corona_r_pix) < 2.5)
            if rim.any():
                frame[rim] = np.maximum(frame[rim], np.full((int(rim.sum()), 3), 235, dtype=np.float32))

        # ── Rotating mirrored radial bars ─────────────────────────────────────
        theta_diff_r = theta_rot - bar_angles[bar_idx_r]
        theta_diff_r = ((theta_diff_r + math.pi) % (2 * math.pi)) - math.pi
        in_bar_r = np.abs(theta_diff_r) <= bar_half_rad

        bar_mags = spectrum[_mirror[bar_idx_r]]
        # Outward bars
        lit_out = in_annulus & in_bar_r & (r_norm_g <= bar_mags)
        # Inward mirror — bars also grow into the centre circle
        r_norm_in = np.clip((r_inner - r_g) / max(r_inner * 0.85, 1), 0.0, 1.0)
        lit_in = (r_g < r_inner) & in_bar_r & (r_norm_in <= bar_mags * 0.55)

        bar_hue_r = (bar_idx_r / _N_BARS * (0.05 if turntable else 0.85)).astype(np.float32)
        for lit, v_scale in ((lit_out, 1.0), (lit_in, 0.55)):
            if lit.any():
                h_lit = (hue_base + bar_hue_r[lit]) % 1.0
                s_lit = np.full(h_lit.shape, 0.9, dtype=np.float32)
                v_lit = np.clip(0.15 + bar_mags[lit] * (0.65 + e_mid * 0.9), 0, 1) * v_scale
                bar_rgb = _hsv_to_rgb_vec(h_lit, s_lit, v_lit)
                frame[lit] = np.maximum(frame[lit], bar_rgb)

        # White-hot bar tips
        tip = in_annulus & in_bar_r & (np.abs(r_norm_g - bar_mags) < 0.02) & (bar_mags > 0.12)
        if tip.any():
            tip_v = np.clip(bar_mags[tip] * 255 * 1.2, 0, 255)
            frame[tip] = np.maximum(frame[tip], np.stack([tip_v, tip_v, tip_v], axis=-1))

        # ── Inner circle: bass-pumping core ───────────────────────────────────
        bass_norm = min(bass / max(rolling_bass[0], 0.01), 3.0)
        if turntable and disc_img is not None:
            # Spin at 33⅓ rpm like a turntable, nudged faster by the bass
            from PIL import Image as _PILImage
            angle = -((t * (33.333 / 60.0)) * 360.0) - bass_norm * 4.0
            rot_disc = disc_img.rotate(angle, resample=_PILImage.BILINEAR)
            d_arr = np.asarray(rot_disc, dtype=np.float32)
            y0, x0 = cy - disc_r, cx - disc_r
            y1, x1 = y0 + disc_r * 2, x0 + disc_r * 2
            if y0 >= 0 and x0 >= 0 and y1 <= height and x1 <= width:
                alpha = d_arr[:, :, 3:4] / 255.0
                region = frame[y0:y1, x0:x1]
                region[:] = region * (1 - alpha) + d_arr[:, :, :3] * alpha
        core_v = min(0.35 + bass_norm * 0.22 + beat_flash[0] * 0.55, 1.0)
        if not (turntable and disc_img is not None):
            # Gradient orb: white-hot centre falling off to a saturated hue rim
            h_core = np.full(ic_grad.shape, hue_base, dtype=np.float32)
            s_core = (1.0 - ic_grad * 0.85).astype(np.float32)   # centre → white
            v_core = np.clip(ic_grad * core_v * 1.6, 0, 1).astype(np.float32)
            core_rgb = _hsv_to_rgb_vec(h_core, s_core, v_core)
            frame[ic_ys, ic_xs] = np.maximum(frame[ic_ys, ic_xs], core_rgb)

        # ── Waveform ring ─────────────────────────────────────────────────────
        wf_start = int(t * fps_audio)
        wf_sz = int(fps_audio / fps)
        wf = audio_mono[wf_start:wf_start + wf_sz]
        if len(wf) > 0:
            wf_norm = wf / (np.abs(wf).max() + 1e-8)
            n_wf = min(len(wf_norm), _N_BARS * 6)
            wf_a = np.linspace(0, 2 * math.pi, n_wf, endpoint=False) + rot
            wf_sub = np.interp(np.linspace(0, len(wf_norm) - 1, n_wf),
                               np.arange(len(wf_norm)), wf_norm)
            wf_r = ((disc_r * 1.05) if turntable else r_wf) + wf_sub * (r_inner * (0.22 if turntable else 0.16))
            wxs = np.clip((cx + wf_r * np.cos(wf_a)).astype(int), 0, width - 1)
            wys = np.clip((cy + wf_r * np.sin(wf_a)).astype(int), 0, height - 1)
            wf_col = np.array(
                _hsv_to_rgb_scalar(hue_base if turntable else (hue_base + 0.5) % 1.0,
                                   1.0 if turntable else 0.5, 1.0 if turntable else 0.95),
                dtype=np.float32)
            for dy2, dx2 in [(-1, 0), (1, 0), (0, -1), (0, 1), (0, 0)]:
                yy = np.clip(wys + dy2, 0, height - 1)
                xx = np.clip(wxs + dx2, 0, width - 1)
                frame[yy, xx] = np.maximum(frame[yy, xx], wf_col)

        # ── Particles (spawn rate rides the highs) ────────────────────────────
        _spawn_particles(fft_bars, hue_base)
        if e_high > 0.35:
            _spawn_particles(fft_bars * 0.9, (hue_base + 0.3) % 1.0)
        alive = particles[:, 4] > 0
        if alive.any():
            particles[alive, 0] += particles[alive, 2]
            particles[alive, 1] += particles[alive, 3]
            particles[alive, 4] -= 0.016
            particles[alive, 2] *= 0.975
            particles[alive, 3] *= 0.975
            pxs = particles[alive, 0].astype(int)
            pys = particles[alive, 1].astype(int)
            valid = (pxs >= 0) & (pxs < width) & (pys >= 0) & (pys < height)
            if valid.any():
                lifes = particles[alive, 4][valid]
                hues = particles[alive, 5][valid]
                pcols = _hsv_to_rgb_vec(hues, np.full_like(hues, 0.9), lifes)
                for dy2, dx2 in [(-1, 0), (1, 0), (0, -1), (0, 1), (0, 0)]:
                    yy = np.clip(pys[valid] + dy2, 0, height - 1)
                    xx = np.clip(pxs[valid] + dx2, 0, width - 1)
                    np.maximum(frame[yy, xx], pcols * 0.8, out=frame[yy, xx])
                frame[pys[valid], pxs[valid]] = np.maximum(
                    frame[pys[valid], pxs[valid]], pcols)

        # ── Motion trails: blend in a ghost of the previous frame ─────────────
        if trail[0] is not None:
            np.maximum(frame, trail[0] * 0.55, out=frame)
        trail[0] = frame.copy()

        # ── Bloom ─────────────────────────────────────────────────────────────
        frame = _apply_bloom(frame, strength=0.32)

        # ── Beat flash ────────────────────────────────────────────────────────
        if beat_flash[0] > 0.05:
            frame = np.clip(frame + beat_flash[0] * 26, 0, 255)

        # ── Text + progress bar ───────────────────────────────────────────────
        title_col = _hsv_to_rgb_scalar(hue_base, 0.35, 1.0)
        artist_col = _hsv_to_rgb_scalar((hue_base + 0.28) % 1.0, 0.6, 0.75)
        if fmt == "tiktok":
            tx = max(40, cx - len(title) * 12)
            _draw_text_simple(frame, title, x=tx, y=60, colour=title_col, scale=3)
            _draw_text_simple(frame, artist, x=tx + 6, y=115, colour=artist_col, scale=2)
        else:
            _draw_text_simple(frame, title, x=55, y=48, colour=title_col, scale=3)
            _draw_text_simple(frame, artist, x=57, y=100, colour=artist_col, scale=2)

        # Brand mark in the centre of the orb
        if turntable:
            brand = ""
        else:
            brand = "PULSEBREAK"
        if brand:
            bscale = 2 if short >= 900 else 1
            bx = cx - (len(brand) * (6 * bscale + bscale)) // 2
            _draw_text_simple(frame, brand, x=bx, y=cy - 3 * bscale,
                              colour=(255, 255, 255), scale=bscale)

        progress = min(t / max(duration, 1), 1.0)
        pb_col = np.array(_hsv_to_rgb_scalar(hue_base, 0.9, 1.0), dtype=np.float32)
        pb_y = height - 5
        pb_end = int(width * progress)
        frame[pb_y:pb_y + 4, :pb_end] = pb_col
        dot_x = max(0, min(pb_end, width - 4))
        frame[pb_y - 3:pb_y + 7, dot_x:dot_x + 4] = pb_col * 1.2

        return np.clip(frame, 0, 255).astype(np.uint8)

    video_clip = mpy.VideoClip(make_frame, duration=duration)
    if hasattr(video_clip, "with_audio"):      # moviepy 2.x
        video_clip = video_clip.with_audio(audio_clip)
    else:                                       # moviepy 1.x
        video_clip = video_clip.set_audio(audio_clip)
    video_clip.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )
    audio_clip.close()
    video_clip.close()
    return output_path
