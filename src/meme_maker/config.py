from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = PROJECT_ROOT / "settings.json"
ENV_PATH = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class AppConfig:
    subreddits: list[str]
    reddit_sort: str
    top_time_filter: str
    posts_per_subreddit: int
    minimum_score: int
    maximum_post_age_hours: int
    maximum_script_characters: int
    allow_nsfw: bool
    video_width: int
    video_height: int
    video_fps: int
    maximum_video_seconds: int
    caption_words_per_screen: int
    voice_rate: int
    voice_volume: float
    voice_name_contains: str
    tts_engine: str
    edge_voice: str
    edge_rate: str
    edge_volume: str
    edge_pitch: str
    narration_words_per_part: int
    video_brightness: float
    caption_font_size: int
    caption_bottom_margin: int
    show_source_header: bool
    output_prefix: str

    @classmethod
    def load(cls) -> "AppConfig":
        if not SETTINGS_PATH.exists():
            raise FileNotFoundError(f"Missing settings file: {SETTINGS_PATH}")

        with SETTINGS_PATH.open("r", encoding="utf-8") as file:
            raw: dict[str, Any] = json.load(file)

        # Backward-compatible defaults allow older settings.json files to work.
        raw.setdefault("tts_engine", "edge")
        raw.setdefault("edge_voice", "en-US-AriaNeural")
        raw.setdefault("edge_rate", "-5%")
        raw.setdefault("edge_volume", "+0%")
        raw.setdefault("edge_pitch", "-2Hz")
        raw.setdefault("narration_words_per_part", 150)
        config = cls(**raw)
        if config.video_width <= 0 or config.video_height <= 0:
            raise ValueError("Video width and height must be positive numbers.")
        if config.video_fps < 1 or config.video_fps > 60:
            raise ValueError("video_fps must be between 1 and 60.")
        if config.caption_words_per_screen < 1:
            raise ValueError("caption_words_per_screen must be at least 1.")
        if config.narration_words_per_part < 40:
            raise ValueError("narration_words_per_part must be at least 40.")
        if config.tts_engine.casefold() not in {"edge", "local"}:
            raise ValueError("tts_engine must be either 'edge' or 'local'.")
        if not 0.1 <= config.voice_volume <= 1.0:
            raise ValueError("voice_volume must be between 0.1 and 1.0.")
        if not 0.2 <= config.video_brightness <= 1.0:
            raise ValueError("video_brightness must be between 0.2 and 1.0.")
        if config.reddit_sort not in {"hot", "rising", "top", "new"}:
            raise ValueError("reddit_sort must be hot, rising, top, or new.")
        return config


@dataclass(frozen=True)
class RedditCredentials:
    client_id: str
    client_secret: str
    username: str
    app_name: str
    app_version: str


def load_reddit_credentials() -> RedditCredentials:
    load_dotenv(ENV_PATH)
    values = {
        "client_id": os.getenv("REDDIT_CLIENT_ID", "").strip(),
        "client_secret": os.getenv("REDDIT_CLIENT_SECRET", "").strip(),
        "username": os.getenv("REDDIT_USERNAME", "").strip(),
        "app_name": os.getenv("APP_NAME", "local-meme-video-generator").strip(),
        "app_version": os.getenv("APP_VERSION", "1.0.0").strip(),
    }

    placeholders = {"", "put_your_client_id_here", "put_your_client_secret_here"}
    if values["client_id"] in placeholders or values["client_secret"] in placeholders:
        raise ValueError(
            "Reddit credentials are missing. Copy .env.example to .env and fill in "
            "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET. You can still use manual-text mode."
        )

    return RedditCredentials(**values)
