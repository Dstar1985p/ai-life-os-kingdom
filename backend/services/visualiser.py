"""
Generates an animated audio visualiser MP4 from an MP3 file.
Uses moviepy + numpy. Requires ffmpeg to be installed.
If ffmpeg/moviepy unavailable, raises VisualizerUnavailableError.
"""

FFMPEG_AVAILABLE = False
try:
    import numpy as np
    import moviepy.editor as mpy
    from moviepy.audio.io.AudioFileClip import AudioFileClip
    FFMPEG_AVAILABLE = True
except Exception:
    pass


class VisualizerUnavailableError(Exception):
    pass


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
) -> str:
    """
    Generate a visualiser video from an audio file.
    Returns the output_path on success.
    """
    if not FFMPEG_AVAILABLE:
        raise VisualizerUnavailableError("moviepy/ffmpeg not available")

    audio_path = str(audio_path)
    output_path = str(output_path)

    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration

    fps_audio = 44100
    audio_array = audio_clip.to_soundarray(fps=fps_audio)
    if audio_array.ndim > 1:
        audio_mono = audio_array.mean(axis=1)
    else:
        audio_mono = audio_array

    n_bars = 64
    bar_gap = 4
    bar_width = (width - (n_bars + 1) * bar_gap) // n_bars
    max_bar_height = int(height * 0.55)
    baseline_y = int(height * 0.72)

    def make_frame(t: float):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = bg_colour

        for y in range(0, height, 80):
            frame[y, :] = tuple(min(255, c + 15) for c in bg_colour)

        sample_start = int(t * fps_audio)
        chunk_size = fps_audio // 10
        chunk = audio_mono[sample_start:sample_start + chunk_size]

        if len(chunk) == 0:
            chunk = np.zeros(chunk_size)

        fft = np.abs(np.fft.rfft(chunk, n=chunk_size))
        fft = fft[:n_bars]
        if fft.max() > 0:
            fft = fft / fft.max()

        for i, magnitude in enumerate(fft):
            bar_h = int(magnitude * max_bar_height)
            bar_h = max(4, bar_h)
            x_start = bar_gap + i * (bar_width + bar_gap)
            x_end = x_start + bar_width
            y_top = baseline_y - bar_h

            for y in range(y_top, baseline_y):
                t_grad = (y - y_top) / max(1, bar_h)
                r = int(bar_colour[0] * (1 - t_grad) + accent_colour[0] * t_grad)
                g = int(bar_colour[1] * (1 - t_grad) + accent_colour[1] * t_grad)
                b = int(bar_colour[2] * (1 - t_grad) + accent_colour[2] * t_grad)
                frame[y, x_start:x_end] = (r, g, b)

            if y_top > 0:
                frame[max(0, y_top - 2):y_top + 1, x_start:x_end] = bar_colour

        waveform_chunk = audio_mono[sample_start:sample_start + int(fps_audio / fps)]
        if len(waveform_chunk) > 0:
            waveform_chunk = waveform_chunk / (np.abs(waveform_chunk).max() + 1e-8)
            xs = np.linspace(0, width - 1, len(waveform_chunk)).astype(int)
            ys = (waveform_chunk * 30 + baseline_y + 60).astype(int)
            ys = np.clip(ys, 0, height - 1)
            for x, y in zip(xs, ys):
                frame[y, x] = (100, 255, 200)

        _draw_text_simple(frame, title.upper(), x=60, y=40, colour=bar_colour, scale=2)
        _draw_text_simple(frame, artist.upper(), x=60, y=80, colour=(150, 150, 200), scale=1)

        progress = t / duration
        pb_y = height - 6
        frame[pb_y:pb_y + 4, 0:int(width * progress)] = bar_colour

        return frame

    video_clip = mpy.VideoClip(make_frame, duration=duration)
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


def _draw_text_simple(frame, text: str, x: int, y: int, colour: tuple, scale: int = 1):
    """Draw simple block-letter text onto a numpy frame array."""
    FONT = {
        'A': ['01110','10001','10001','11111','10001','10001','10001'],
        'B': ['11110','10001','10001','11110','10001','10001','11110'],
        'C': ['01111','10000','10000','10000','10000','10000','01111'],
        'D': ['11110','10001','10001','10001','10001','10001','11110'],
        'E': ['11111','10000','10000','11110','10000','10000','11111'],
        'F': ['11111','10000','10000','11110','10000','10000','10000'],
        'G': ['01111','10000','10000','10111','10001','10001','01111'],
        'H': ['10001','10001','10001','11111','10001','10001','10001'],
        'I': ['11111','00100','00100','00100','00100','00100','11111'],
        'J': ['00111','00010','00010','00010','10010','10010','01100'],
        'K': ['10001','10010','10100','11000','10100','10010','10001'],
        'L': ['10000','10000','10000','10000','10000','10000','11111'],
        'M': ['10001','11011','10101','10001','10001','10001','10001'],
        'N': ['10001','11001','10101','10011','10001','10001','10001'],
        'O': ['01110','10001','10001','10001','10001','10001','01110'],
        'P': ['11110','10001','10001','11110','10000','10000','10000'],
        'Q': ['01110','10001','10001','10001','10101','10010','01101'],
        'R': ['11110','10001','10001','11110','10100','10010','10001'],
        'S': ['01111','10000','10000','01110','00001','00001','11110'],
        'T': ['11111','00100','00100','00100','00100','00100','00100'],
        'U': ['10001','10001','10001','10001','10001','10001','01110'],
        'V': ['10001','10001','10001','10001','10001','01010','00100'],
        'W': ['10001','10001','10001','10101','10101','11011','10001'],
        'X': ['10001','10001','01010','00100','01010','10001','10001'],
        'Y': ['10001','10001','01010','00100','00100','00100','00100'],
        'Z': ['11111','00001','00010','00100','01000','10000','11111'],
        ' ': ['00000','00000','00000','00000','00000','00000','00000'],
        '-': ['00000','00000','00000','11111','00000','00000','00000'],
        ':': ['00000','00100','00000','00000','00100','00000','00000'],
        '0': ['01110','10001','10011','10101','11001','10001','01110'],
        '1': ['00100','01100','00100','00100','00100','00100','01110'],
    }
    h, w = frame.shape[:2]
    px = x
    for char in text:
        glyph = FONT.get(char, FONT.get(' '))
        for row_i, row in enumerate(glyph):
            for col_i, pixel in enumerate(row):
                if pixel == '1':
                    py = y + row_i * scale
                    ppx = px + col_i * scale
                    for sy in range(scale):
                        for sx in range(scale):
                            fy, fx = py + sy, ppx + sx
                            if 0 <= fy < h and 0 <= fx < w:
                                frame[fy, fx] = colour
        px += (6 * scale) + scale
