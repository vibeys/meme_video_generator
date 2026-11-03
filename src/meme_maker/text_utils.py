from __future__ import annotations

import html
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CaptionSegment:
    text: str
    start: float
    end: float


def clean_reddit_text(value: str) -> str:
    """Remove Markdown/HTML clutter while preserving paragraph breaks for narration."""
    text = html.unescape(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"^\s*>+\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_`~]", "", text)

    # Keep real paragraph breaks for a more natural neural narration cadence.
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n+", text):
        paragraph = re.sub(r"\s*\n\s*", " ", paragraph)
        paragraph = re.sub(r"[ \t]+", " ", paragraph).strip()
        if paragraph:
            paragraphs.append(paragraph)
    return "\n\n".join(paragraphs)


def build_narration(title: str, body: str, maximum_characters: int = 0) -> str:
    """Build the full narration. Long stories are split into parts later, never cut off."""
    clean_title = clean_reddit_text(title)
    clean_body = clean_reddit_text(body)

    if clean_title and clean_body:
        script = f"{clean_title}.\n\n{clean_body}"
    else:
        script = clean_title or clean_body

    if not script:
        raise ValueError("The selected post does not contain readable text.")
    return script


def split_narration_parts(text: str, maximum_words: int) -> list[str]:
    """Split a long story on sentence boundaries into short-video-sized parts."""
    if maximum_words < 40:
        raise ValueError("narration_words_per_part must be at least 40.")

    paragraphs = [item.strip() for item in re.split(r"\n\s*\n+", text) if item.strip()]
    sentences: list[str] = []
    for paragraph in paragraphs:
        pieces = re.split(r"(?<=[.!?])\s+", paragraph)
        sentences.extend(piece.strip() for piece in pieces if piece.strip())

    parts: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        words = sentence.split()
        if len(words) > maximum_words:
            # A single unusually long sentence is split at word boundaries.
            if current:
                parts.append(" ".join(current))
                current, current_words = [], 0
            for start in range(0, len(words), maximum_words):
                parts.append(" ".join(words[start:start + maximum_words]))
            continue

        if current and current_words + len(words) > maximum_words:
            parts.append(" ".join(current))
            current, current_words = [], 0

        current.append(sentence)
        current_words += len(words)

    if current:
        parts.append(" ".join(current))

    return parts or [text.strip()]


def split_caption_segments(text: str, audio_duration: float, words_per_segment: int) -> list[CaptionSegment]:
    words = text.split()
    if not words:
        return []

    chunks = [words[i:i + words_per_segment] for i in range(0, len(words), words_per_segment)]
    total_words = len(words)
    cursor = 0.0
    segments: list[CaptionSegment] = []

    for index, chunk in enumerate(chunks):
        duration = audio_duration * (len(chunk) / total_words)
        end = audio_duration if index == len(chunks) - 1 else cursor + duration
        segments.append(CaptionSegment(" ".join(chunk), cursor, end))
        cursor = end

    return segments
