from __future__ import annotations

import argparse
import random
import re
import tempfile
from datetime import datetime
from pathlib import Path

from .config import PROJECT_ROOT, AppConfig
from .reddit_client import RedditPost, fetch_trending_posts, reddit_error_hint
from .renderer import mux_audio, render_silent_video
from .text_utils import build_narration, split_narration_parts
from .tts import create_voiceover


GAMEPLAY_DIR = PROJECT_ROOT / "assets" / "gameplay"
OUTPUT_DIR = PROJECT_ROOT / "output"


def _safe_filename(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_")
    return value[:45] or "reddit_post"


def _find_gameplay_clip() -> Path:
    allowed = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
    clips = [
        path for path in GAMEPLAY_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in allowed
    ] if GAMEPLAY_DIR.exists() else []
    if not clips:
        raise FileNotFoundError(
            "No gameplay clips were found. Add at least one video file to:\n"
            f"{GAMEPLAY_DIR}\nSupported formats: {', '.join(sorted(allowed))}"
        )
    return random.choice(clips)


def _choose_reddit_post(config: AppConfig) -> RedditPost | None:
    print("\nFetching trending text posts from Reddit...")
    try:
        posts = fetch_trending_posts(config)
    except Exception as error:
        print(f"\n{reddit_error_hint(error)}")
        return None

    if not posts:
        print("No eligible posts were found. Try different subreddits or lower minimum_score.")
        return None

    shortlist = posts[:10]
    print("\nTrending post candidates:")
    for index, post in enumerate(shortlist, start=1):
        short_title = post.title.replace("\n", " ")
        if len(short_title) > 92:
            short_title = short_title[:89] + "..."
        print(
            f"  {index:>2}. r/{post.subreddit} | {post.score:,} points | "
            f"{post.comments:,} comments\n      {short_title}"
        )

    print("\nPress Enter to use the top candidate, type a number to choose, or type R for random.")
    choice = input("Your choice [Enter]: ").strip().lower()
    if choice == "r":
        return random.choice(shortlist)
    if not choice:
        return shortlist[0]
    if choice.isdigit() and 1 <= int(choice) <= len(shortlist):
        return shortlist[int(choice) - 1]
    print("Invalid selection. Using the top candidate.")
    return shortlist[0]


def _manual_post() -> tuple[str, str, str, str]:
    print("\nManual post mode")
    title = input("Video title: ").strip()
    print("Paste the post text. Finish by entering a line with only .DONE")
    lines: list[str] = []
    while True:
        line = input()
        if line.strip() == ".DONE":
            break
        lines.append(line)
    body = "\n".join(lines).strip()
    if not title and not body:
        raise ValueError("Please enter a title or some post text.")
    source_url = input("Source URL (optional, press Enter to skip): ").strip()
    return title, body, "Manual text", source_url


def _write_source_note(
    destination: Path,
    source_name: str,
    source_url: str,
    part_count: int,
) -> None:
    note = [
        "Source information",
        f"Source: {source_name}",
        f"URL: {source_url or 'Not provided'}",
        f"Rendered video parts: {part_count}",
        "",
        "This file does not contain a saved copy of the source post text.",
        "Check the post and clip owners' terms before sharing or monetizing the video.",
    ]
    destination.write_text("\n".join(note), encoding="utf-8")


def _split_if_audio_is_too_long(
    narration: str,
    measured_duration: float,
    maximum_duration: float,
    configured_words: int,
) -> list[str]:
    words = narration.split()
    scaled_limit = int(len(words) * (maximum_duration / measured_duration) * 0.85)
    new_limit = max(40, min(configured_words - 1, scaled_limit))
    if new_limit >= len(words):
        new_limit = max(40, len(words) // 2)
    split = split_narration_parts(narration, new_limit)
    if len(split) <= 1:
        midpoint = max(1, len(words) // 2)
        split = [" ".join(words[:midpoint]), " ".join(words[midpoint:])]
    return [part for part in split if part.strip()]


def generate_video(
    title: str,
    body: str,
    source_name: str,
    source_url: str,
    config: AppConfig,
) -> list[Path]:
    narration = build_narration(title, body, config.maximum_script_characters)
    queued_parts = split_narration_parts(narration, config.narration_words_per_part)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{config.output_prefix}_{timestamp}_{_safe_filename(source_name)}"
    source_note = OUTPUT_DIR / f"{stem}_source.txt"
    header = source_name if source_name != "Manual text" else "Original story"
    final_videos: list[Path] = []

    print(f"\nNarration length: {len(narration)} characters / {len(narration.split())} words")
    print(f"Initial story sections: {len(queued_parts)}")
    print(f"Voice engine: {config.tts_engine} ({config.edge_voice if config.tts_engine == 'edge' else 'Windows voice'})")
    print("Long stories are split into separate videos instead of being silently cut off.")

    with tempfile.TemporaryDirectory(prefix="meme_maker_") as temporary_folder:
        temporary_dir = Path(temporary_folder)
        next_part_number = 1

        while queued_parts:
            part_text = queued_parts.pop(0)
            voiceover = temporary_dir / f"voiceover_{next_part_number:03d}.wav"
            silent_video = temporary_dir / f"video_silent_{next_part_number:03d}.mp4"

            print(f"\nPreparing story part {next_part_number}...")
            audio_duration = create_voiceover(part_text, voiceover, config)

            if audio_duration > config.maximum_video_seconds:
                smaller_parts = _split_if_audio_is_too_long(
                    part_text,
                    audio_duration,
                    config.maximum_video_seconds,
                    config.narration_words_per_part,
                )
                if len(smaller_parts) <= 1:
                    raise RuntimeError(
                        "One narration sentence is longer than the configured video limit. "
                        "Lower narration_words_per_part in settings.json or increase maximum_video_seconds."
                    )
                print("This section is longer than the video limit; splitting it into smaller sections.")
                voiceover.unlink(missing_ok=True)
                queued_parts = smaller_parts + queued_parts
                continue

            gameplay = _find_gameplay_clip()
            print(f"Selected gameplay: {gameplay.name}")
            render_silent_video(
                gameplay_path=gameplay,
                narration=part_text,
                audio_duration=audio_duration,
                destination=silent_video,
                header=header,
                config=config,
            )

            final_video = OUTPUT_DIR / f"{stem}_part_{next_part_number:02d}.mp4"
            print("Adding voiceover and encoding final MP4...")
            mux_audio(silent_video, voiceover, final_video)
            final_videos.append(final_video)
            print(f"Created: {final_video}")
            next_part_number += 1

    _write_source_note(source_note, source_name, source_url, len(final_videos))
    print("\nAll video parts created successfully:")
    for video_path in final_videos:
        print(f"  {video_path}")
    print(f"  Source note: {source_note}")
    print(f"  Total parts: {len(final_videos)}")
    return final_videos


def main() -> int:
    parser = argparse.ArgumentParser(description="Turn a Reddit post or manual text into vertical narrated shorts.")
    parser.add_argument("--manual", action="store_true", help="Paste your own text instead of fetching Reddit.")
    args = parser.parse_args()

    try:
        config = AppConfig.load()
        print("=" * 64)
        print("AUTOMATIC MEME VIDEO GENERATOR")
        print("=" * 64)

        if args.manual:
            title, body, source_name, source_url = _manual_post()
        else:
            print("\n1. Fetch a trending Reddit text post")
            print("2. Paste your own text (no Reddit API needed)")
            mode = input("Choose mode [1]: ").strip() or "1"
            if mode == "2":
                title, body, source_name, source_url = _manual_post()
            else:
                post = _choose_reddit_post(config)
                if post is None:
                    print("\nYou can rerun with manual mode: run_manual.bat")
                    return 1
                title, body = post.title, post.body
                source_name = f"r/{post.subreddit}"
                source_url = post.permalink

        generate_video(title, body, source_name, source_url, config)
        return 0

    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"\nERROR: {error}")
        return 1
    except Exception as error:
        print(f"\nUNEXPECTED ERROR: {type(error).__name__}: {error}")
        print("Check the README troubleshooting section before trying again.")
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
