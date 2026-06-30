"""
PulseBreak Track Quality Gate.

Analyses audio files and returns a QualityReport with a score 0-100.
Tracks below AUTO_FAIL_THRESHOLD are rejected outright.
Tracks between AUTO_FAIL and REVIEW_THRESHOLD are quarantined for founder review.
Tracks at or above REVIEW_THRESHOLD are cleared for release.

No external dependencies beyond numpy (which visualiser already requires).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal

# Thresholds
AUTO_PASS_SCORE = 72     # auto-cleared for release
REVIEW_SCORE = 45        # below this → quarantine for human review
AUTO_FAIL_SCORE = 25     # below this → rejected outright (technical disaster)

# Technical limits
MIN_DURATION_SECS = 60           # shorter than this = not a real track
WARN_DURATION_SECS = 90          # warn if under 90s
CLIPPING_THRESHOLD = 0.995       # sample abs() above this = clipping
MAX_CLIPPING_PCT = 0.02          # more than 2% clipped samples = fail
SILENCE_RMS_THRESHOLD = 0.001    # below this = silence
MAX_SILENCE_SECS = 8.0           # more than 8s consecutive silence = fail
MIN_LOUDNESS_RMS = 0.020         # too quiet overall
MAX_LOUDNESS_RMS = 0.85          # too loud (will clip on platform encode)
MIN_DYNAMIC_RANGE_DB = 4.0       # crest factor < 4dB = brick-wall compressed
FREQ_BASS_MAX_RATIO = 0.75       # bass > 75% of total energy = muddy
FREQ_HIGH_MIN_RATIO = 0.05       # high end < 5% of energy = dull/muffled


@dataclass
class QualityCheck:
    name: str
    passed: bool
    score_impact: int      # points added (positive) or deducted (negative)
    detail: str
    severity: Literal["info", "warning", "fail", "critical"]


@dataclass
class QualityReport:
    track_name: str
    score: int                           # 0-100
    verdict: Literal["pass", "review", "fail"]
    checks: list[QualityCheck] = field(default_factory=list)
    duration_secs: float = 0.0
    peak_db: float = 0.0
    rms_db: float = 0.0
    dynamic_range_db: float = 0.0
    bass_ratio: float = 0.0
    high_ratio: float = 0.0
    clipping_pct: float = 0.0
    max_silence_secs: float = 0.0
    summary: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["checks"] = [asdict(c) for c in self.checks]
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def _db(linear: float) -> float:
    """Linear amplitude to dBFS. Returns -inf for 0."""
    if linear <= 0:
        return -100.0
    return 20 * math.log10(max(linear, 1e-10))


def analyse_track(audio_path: str | Path) -> QualityReport:
    """
    Run all quality checks on an audio file.
    Returns a QualityReport regardless of errors — bad files get score 0.
    """
    track_name = Path(audio_path).stem
    report = QualityReport(track_name=track_name, score=0, verdict="fail")

    try:
        import numpy as np
        from moviepy.audio.io.AudioFileClip import AudioFileClip
    except ImportError:
        report.summary = "numpy/moviepy not available — quality gate skipped (track queued for review)"
        report.score = REVIEW_SCORE
        report.verdict = "review"
        return report

    # Load audio
    try:
        clip = AudioFileClip(str(audio_path))
        fps = 44100
        arr = clip.to_soundarray(fps=fps)
        clip.close()
        mono = arr.mean(axis=1) if arr.ndim > 1 else arr.copy()
        mono = mono.astype(np.float32)
    except Exception as exc:
        report.summary = f"Could not load audio: {exc}"
        report.score = 0
        report.verdict = "fail"
        return report

    checks: list[QualityCheck] = []
    score = 100  # start at 100, deduct for problems

    # ── Duration ──────────────────────────────────────────────────────────────
    duration = len(mono) / fps
    report.duration_secs = round(duration, 1)

    if duration < MIN_DURATION_SECS:
        checks.append(QualityCheck(
            name="duration",
            passed=False,
            score_impact=-60,
            detail=f"Track is only {duration:.0f}s — minimum is {MIN_DURATION_SECS}s for a releasable track",
            severity="critical",
        ))
        score -= 60
    elif duration < WARN_DURATION_SECS:
        checks.append(QualityCheck(
            name="duration",
            passed=True,
            score_impact=-10,
            detail=f"Track is {duration:.0f}s — consider extending to 90s+ for better platform placement",
            severity="warning",
        ))
        score -= 10
    else:
        checks.append(QualityCheck(
            name="duration",
            passed=True,
            score_impact=0,
            detail=f"Duration {duration:.0f}s ✓",
            severity="info",
        ))

    # ── Peak level & clipping ─────────────────────────────────────────────────
    peak = float(np.abs(mono).max())
    peak_db = _db(peak)
    report.peak_db = round(peak_db, 1)

    clipping_samples = int((np.abs(mono) > CLIPPING_THRESHOLD).sum())
    clipping_pct = clipping_samples / max(len(mono), 1) * 100
    report.clipping_pct = round(clipping_pct, 3)

    if clipping_pct > MAX_CLIPPING_PCT * 100:
        checks.append(QualityCheck(
            name="clipping",
            passed=False,
            score_impact=-40,
            detail=f"{clipping_pct:.2f}% of samples are clipping — this will sound distorted on all platforms",
            severity="critical",
        ))
        score -= 40
    elif peak_db > -0.5:
        checks.append(QualityCheck(
            name="peak_level",
            passed=True,
            score_impact=-8,
            detail=f"Peak at {peak_db:.1f}dBFS — close to 0dB, may clip after platform encode. Target: -1dBFS",
            severity="warning",
        ))
        score -= 8
    elif peak_db < -12:
        checks.append(QualityCheck(
            name="peak_level",
            passed=True,
            score_impact=-5,
            detail=f"Peak at {peak_db:.1f}dBFS — very quiet. Consider normalising to -1dBFS",
            severity="warning",
        ))
        score -= 5
    else:
        checks.append(QualityCheck(
            name="peak_level",
            passed=True,
            score_impact=0,
            detail=f"Peak level {peak_db:.1f}dBFS ✓",
            severity="info",
        ))

    # ── Overall loudness (RMS) ────────────────────────────────────────────────
    rms = float(np.sqrt(np.mean(mono ** 2)))
    rms_db = _db(rms)
    report.rms_db = round(rms_db, 1)

    if rms < MIN_LOUDNESS_RMS:
        checks.append(QualityCheck(
            name="loudness",
            passed=False,
            score_impact=-25,
            detail=f"Track is very quiet (RMS {rms_db:.1f}dBFS) — will disappear on streaming platforms. Needs mastering.",
            severity="fail",
        ))
        score -= 25
    elif rms > MAX_LOUDNESS_RMS:
        checks.append(QualityCheck(
            name="loudness",
            passed=False,
            score_impact=-20,
            detail=f"Track is excessively loud (RMS {rms_db:.1f}dBFS) — over-driven, will distort after encoding",
            severity="fail",
        ))
        score -= 20
    else:
        checks.append(QualityCheck(
            name="loudness",
            passed=True,
            score_impact=0,
            detail=f"Loudness {rms_db:.1f}dBFS ✓",
            severity="info",
        ))

    # ── Dynamic range (crest factor) ──────────────────────────────────────────
    crest = peak / max(rms, 1e-10)
    dynamic_range_db = _db(crest)
    report.dynamic_range_db = round(dynamic_range_db, 1)

    if dynamic_range_db < MIN_DYNAMIC_RANGE_DB:
        checks.append(QualityCheck(
            name="dynamic_range",
            passed=False,
            score_impact=-20,
            detail=f"Dynamic range only {dynamic_range_db:.1f}dB — brick-wall compressed, sounds fatiguing. Target: 6dB+",
            severity="fail",
        ))
        score -= 20
    elif dynamic_range_db < 6.0:
        checks.append(QualityCheck(
            name="dynamic_range",
            passed=True,
            score_impact=-8,
            detail=f"Dynamic range {dynamic_range_db:.1f}dB — slightly over-compressed. Reduce limiting for better feel.",
            severity="warning",
        ))
        score -= 8
    else:
        checks.append(QualityCheck(
            name="dynamic_range",
            passed=True,
            score_impact=0,
            detail=f"Dynamic range {dynamic_range_db:.1f}dB ✓",
            severity="info",
        ))

    # ── Silence detection ─────────────────────────────────────────────────────
    chunk_frames = int(0.1 * fps)  # 100ms chunks
    n_chunks = len(mono) // chunk_frames
    chunk_rms = np.array([
        float(np.sqrt(np.mean(mono[i * chunk_frames:(i + 1) * chunk_frames] ** 2)))
        for i in range(n_chunks)
    ])
    is_silent = chunk_rms < SILENCE_RMS_THRESHOLD

    max_silence = 0
    current = 0
    for s in is_silent:
        current = current + 0.1 if s else 0
        max_silence = max(max_silence, current)
    report.max_silence_secs = round(max_silence, 1)

    if max_silence > MAX_SILENCE_SECS:
        checks.append(QualityCheck(
            name="silence",
            passed=False,
            score_impact=-30,
            detail=f"{max_silence:.1f}s of consecutive silence found — track has dead sections or a failed render",
            severity="critical",
        ))
        score -= 30
    elif max_silence > 3.0:
        checks.append(QualityCheck(
            name="silence",
            passed=True,
            score_impact=-5,
            detail=f"Up to {max_silence:.1f}s of silence — acceptable if intentional (long intro/outro)",
            severity="warning",
        ))
        score -= 5
    else:
        checks.append(QualityCheck(
            name="silence",
            passed=True,
            score_impact=0,
            detail=f"No excessive silence ✓ (max {max_silence:.1f}s)",
            severity="info",
        ))

    # ── Frequency balance (FFT over full track) ───────────────────────────────
    fft_full = np.abs(np.fft.rfft(mono))
    n_fft = len(fft_full)
    # Divide into thirds: bass 0-200Hz, mid 200-4kHz, high 4kHz+
    # At fps=44100, freq resolution = 44100 / len(mono) Hz/bin
    hz_per_bin = fps / len(mono)
    bass_end = int(200 / hz_per_bin)
    mid_end = int(4000 / hz_per_bin)
    bass_end = min(bass_end, n_fft)
    mid_end = min(mid_end, n_fft)

    energy_bass = float(np.sum(fft_full[:bass_end] ** 2))
    energy_mid = float(np.sum(fft_full[bass_end:mid_end] ** 2))
    energy_high = float(np.sum(fft_full[mid_end:] ** 2))
    energy_total = energy_bass + energy_mid + energy_high + 1e-10

    bass_ratio = energy_bass / energy_total
    high_ratio = energy_high / energy_total
    report.bass_ratio = round(bass_ratio, 3)
    report.high_ratio = round(high_ratio, 3)

    if bass_ratio > FREQ_BASS_MAX_RATIO:
        checks.append(QualityCheck(
            name="frequency_balance",
            passed=False,
            score_impact=-20,
            detail=f"Bass is {bass_ratio * 100:.0f}% of total energy — extremely muddy, mids and highs are buried",
            severity="fail",
        ))
        score -= 20
    elif high_ratio < FREQ_HIGH_MIN_RATIO:
        checks.append(QualityCheck(
            name="frequency_balance",
            passed=False,
            score_impact=-15,
            detail=f"High frequencies only {high_ratio * 100:.1f}% of energy — track sounds muffled/dull, no air or sparkle",
            severity="fail",
        ))
        score -= 15
    else:
        checks.append(QualityCheck(
            name="frequency_balance",
            passed=True,
            score_impact=0,
            detail=f"Frequency balance OK — bass {bass_ratio * 100:.0f}%, high {high_ratio * 100:.0f}% ✓",
            severity="info",
        ))

    # ── Stereo width check (if stereo) ────────────────────────────────────────
    if arr.ndim > 1 and arr.shape[1] == 2:
        left = arr[:, 0].astype(np.float32)
        right = arr[:, 1].astype(np.float32)
        corr_num = float(np.mean(left * right))
        corr_den = float(np.sqrt(np.mean(left ** 2) * np.mean(right ** 2)) + 1e-10)
        correlation = corr_num / corr_den  # 1 = mono, 0 = wide, -1 = out-of-phase

        if correlation > 0.98:
            checks.append(QualityCheck(
                name="stereo_width",
                passed=True,
                score_impact=-8,
                detail=f"Track is effectively mono (L/R correlation {correlation:.2f}) — sounds narrow on speakers",
                severity="warning",
            ))
            score -= 8
        elif correlation < -0.3:
            checks.append(QualityCheck(
                name="stereo_width",
                passed=False,
                score_impact=-20,
                detail=f"L/R channels are partially out-of-phase ({correlation:.2f}) — will cancel on mono playback (phone/earbuds)",
                severity="fail",
            ))
            score -= 20
        else:
            checks.append(QualityCheck(
                name="stereo_width",
                passed=True,
                score_impact=0,
                detail=f"Stereo width good (L/R correlation {correlation:.2f}) ✓",
                severity="info",
            ))

    # ── Final score & verdict ─────────────────────────────────────────────────
    score = max(0, min(100, score))
    report.score = score
    report.checks = checks

    if score >= AUTO_PASS_SCORE:
        report.verdict = "pass"
    elif score >= REVIEW_SCORE:
        report.verdict = "review"
    else:
        report.verdict = "fail"

    # Human-readable summary
    fails = [c for c in checks if c.severity in ("critical", "fail") and not c.passed]
    warnings = [c for c in checks if c.severity == "warning" and not c.passed]

    if report.verdict == "pass":
        report.summary = (
            f"Track cleared for release (score {score}/100). "
            + (f"Minor notes: {'; '.join(w.name for w in warnings)}." if warnings else "No issues.")
        )
    elif report.verdict == "review":
        issues = "; ".join(f.name for f in fails + warnings)
        report.summary = (
            f"Track needs your review (score {score}/100). "
            f"Issues found: {issues}. Listen and decide."
        )
    else:
        issues = "; ".join(f.detail[:60] for f in fails)
        report.summary = (
            f"Track FAILED quality gate (score {score}/100). "
            f"Technical problems: {issues}."
        )

    return report
