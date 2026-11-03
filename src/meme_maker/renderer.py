from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .config import AppConfig
from .text_utils import CaptionSegment, split_caption_segments


class RenderError(RuntimeError):
    pass


def _load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def _wrap_words(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=font, stroke_width=2)[2] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _crop_to_vertical(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    source_height, source_width = frame.shape[:2]
    target_ratio = width / height
    source_ratio = source_width / source_height

    if source_ratio > target_ratio:
        crop_width = int(source_height * target_ratio)
        left = max(0, (source_width - crop_width) // 2)
        frame = frame[:, left:left + crop_width]
    else:
        crop_height = int(source_width / target_ratio)
        top = max(0, (source_height - crop_height) // 2)
        frame = frame[top:top + crop_height, :]

    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


def _draw_caption(
    frame_bgr: np.ndarray,
    caption: str,
    header: str,
    config: AppConfig,
) -> np.ndarray:
    image = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    header_font = _load_font(30)
    caption_font = _load_font(config.caption_font_size)
    width, height = image.size

    if config.show_source_header and header:
        header_box = (44, 58, width - 44, 120)
        draw.rounded_rectangle(header_box, radius=22, fill=(0, 0, 0, 155))
        draw.text((70, 72), header, font=header_font, fill=(255, 255, 255, 245))

    if caption:
        max_text_width = width - 150
        lines = _wrap_words(draw, caption, caption_font, max_text_width)
        line_heights = [draw.textbbox((0, 0), line, font=caption_font, stroke_width=3)[3] for line in lines]
        line_gap = 16
        content_height = sum(line_heights) + line_gap * max(0, len(lines) - 1)
        padding_x, padding_y = 42, 36
        box_height = content_height + padding_y * 2
        box_top = min(height - box_height - 80, config.video_height - config.caption_bottom_margin)
        box_top = max(160, box_top)
        box = (48, box_top, width - 48, box_top + box_height)
        draw.rounded_rectangle(box, radius=34, fill=(0, 0, 0, 176), outline=(255, 255, 255, 75), width=2)

        y = box_top + padding_y
        for line, line_height in zip(lines, line_heights):
            bounds = draw.textbbox((0, 0), line, font=caption_font, stroke_width=3)
            text_width = bounds[2] - bounds[0]
            x = (width - text_width) // 2
            draw.text(
                (x, y), line, font=caption_font,
                fill=(255, 255, 255, 255),
                stroke_width=4, stroke_fill=(0, 0, 0, 255),
            )
            y += line_height + line_gap

    combined = Image.alpha_composite(image, overlay).convert("RGB")
    return cv2.cvtColor(np.asarray(combined), cv2.COLOR_RGB2BGR)


def _caption_for_time(segments: list[CaptionSegment], current_time: float) -> str:
    for segment in segments:
        if segment.start <= current_time < segment.end:
            return segment.text
    return segments[-1].text if segments and current_time >= segments[-1].end else ""


def render_silent_video(
    gameplay_path: Path,
    narration: str,
    audio_duration: float,
    destination: Path,
    header: str,
    config: AppConfig,
) -> float:
    capture = cv2.VideoCapture(str(gameplay_path))
    if not capture.isOpened():
        raise RenderError(f"Could not open gameplay clip: {gameplay_path}")

    source_fps = capture.get(cv2.CAP_PROP_FPS)
    source_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    source_duration = source_count / source_fps if source_fps > 0 and source_count > 0 else 0
    if source_duration <= 0:
        capture.release()
        raise RenderError("The selected gameplay clip has no readable video frames.")

    duration = min(audio_duration, float(config.maximum_video_seconds))
    total_frames = max(1, int(duration * config.video_fps))
    segments = split_caption_segments(
        narration, duration, config.caption_words_per_screen
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(
        str(destination), fourcc, config.video_fps,
        (config.video_width, config.video_height),
    )
    if not writer.isOpened():
        capture.release()
        raise RenderError("OpenCV could not start the temporary MP4 writer.")

    frame_index = 0
    source_fps = source_fps if source_fps > 0 else float(config.video_fps)
    current_source_index = -1
    current_frame = None
    try:
        for output_index in range(total_frames):
            target_source_index = int(output_index * source_fps / config.video_fps) % source_count
            if target_source_index < current_source_index:
                capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                current_source_index = -1
                current_frame = None

            while current_source_index < target_source_index:
                ok, next_frame = capture.read()
                if not ok:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    current_source_index = -1
                    current_frame = None
                    continue
                current_source_index += 1
                current_frame = next_frame

            if current_frame is None:
                raise RenderError("The gameplay clip could not be read or looped.")
            frame = current_frame.copy()
            frame = _crop_to_vertical(frame, config.video_width, config.video_height)
            frame = cv2.convertScaleAbs(frame, alpha=config.video_brightness, beta=0)
            current_time = output_index / config.video_fps
            caption = _caption_for_time(segments, current_time)
            frame = _draw_caption(frame, caption, header, config)
            writer.write(frame)
            frame_index += 1

            if output_index % max(1, config.video_fps * 5) == 0:
                print(f"  Rendering frames: {output_index + 1}/{total_frames}", end="\r")
    finally:
        capture.release()
        writer.release()

    print(f"  Rendered {frame_index} frames.             ")
    return duration


def mux_audio(silent_video: Path, voiceover: Path, destination: Path) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(silent_video),
        "-i", str(voiceover),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "21",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        str(destination),
    ]

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Unknown FFmpeg error").strip()
        raise RenderError(f"FFmpeg could not combine the video and voiceover:\n{detail}")
