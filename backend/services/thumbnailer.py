"""YouTube thumbnail generation — pick the most visually energetic frame of a
rendered visualiser video and save it as a JPEG next to the video.

'Energy' = mean brightness × colour variance, sampled across the video. The
beat-flash frames the renderer produces score highest, which is exactly the
look you want in a thumbnail.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def generate_thumbnail(video_path: str, out_path: str | None = None,
                       samples: int = 24) -> str | None:
    """Returns the thumbnail path, or None if unavailable. Never raises."""
    try:
        import numpy as np
        from moviepy import VideoFileClip
    except Exception:
        try:
            import numpy as np  # noqa: F811
            from moviepy.editor import VideoFileClip  # moviepy 1.x
        except Exception:
            logger.warning("Thumbnailer: moviepy unavailable")
            return None

    out_path = out_path or str(video_path).rsplit(".", 1)[0] + "_thumb.jpg"
    try:
        clip = VideoFileClip(str(video_path))
        dur = max(clip.duration, 0.5)
        best_t, best_score = 0.0, -1.0
        # Skip the very start/end (fade-in, credits)
        for i in range(samples):
            t = dur * (0.08 + 0.84 * i / max(samples - 1, 1))
            frame = clip.get_frame(t).astype("float32")
            brightness = frame.mean()
            colour_var = frame.std(axis=(0, 1)).mean()
            score = brightness * 0.6 + colour_var * 2.0
            if score > best_score:
                best_score, best_t = score, t
        clip.save_frame(out_path, t=best_t)
        clip.close()
        logger.info("Thumbnail saved: %s (t=%.1fs)", out_path, best_t)
        return out_path
    except Exception as exc:
        logger.warning("Thumbnailer failed for %s: %s", video_path, exc)
        return None
