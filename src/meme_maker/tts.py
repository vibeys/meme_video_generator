from __future__ import annotations

import asyncio
import os
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
import pyttsx3

from .config import AppConfig


def _create_local_engine():
    try:
        if os.name == "nt":
            return pyttsx3.init(driverName="sapi5")
        return pyttsx3.init()
    except Exception as error:
        raise RuntimeError(
            "Could not start the local Windows speech engine. Check that a Windows "
            "text-to-speech voice is installed."
        ) from error


def _create_local_voiceover(text: str, destination: Path, config: AppConfig) -> None:
    engine = _create_local_engine()
    try:
        engine.setProperty("rate", config.voice_rate)
        engine.setProperty("volume", config.voice_volume)

        if config.voice_name_contains.strip():
            target = config.voice_name_contains.casefold()
            matches = [
                voice for voice in engine.getProperty("voices")
                if target in f"{voice.name} {voice.id}".casefold()
            ]
            if matches:
                engine.setProperty("voice", matches[0].id)
            else:
                available = ", ".join(voice.name for voice in engine.getProperty("voices"))
                raise ValueError(
                    f"No installed local voice matched '{config.voice_name_contains}'. "
                    f"Available voices: {available or 'none detected'}"
                )

        engine.save_to_file(text, str(destination))
        engine.runAndWait()
    except ValueError:
        raise
    except Exception as error:
        raise RuntimeError("The local text-to-speech engine failed.") from error
    finally:
        engine.stop()


def _edge_tts_available() -> bool:
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        return False


async def _save_edge_mp3(text: str, destination: Path, config: AppConfig) -> None:
    import edge_tts

    communicator = edge_tts.Communicate(
        text=text,
        voice=config.edge_voice,
        rate=config.edge_rate,
        volume=config.edge_volume,
        pitch=config.edge_pitch,
    )
    await communicator.save(str(destination))


def _convert_mp3_to_wav(source: Path, destination: Path) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source),
        "-vn", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not destination.exists():
        detail = (result.stderr or result.stdout or "Unknown FFmpeg error").strip()
        raise RuntimeError(f"Could not convert the neural voice audio to WAV:\n{detail}")


def _audio_duration(destination: Path) -> float:
    if not destination.exists() or destination.stat().st_size < 1000:
        raise RuntimeError("The speech engine did not create a usable audio file.")
    try:
        with wave.open(str(destination), "rb") as audio_file:
            duration = audio_file.getnframes() / float(audio_file.getframerate())
    except (wave.Error, ZeroDivisionError) as error:
        raise RuntimeError("The speech engine produced an invalid WAV file.") from error
    if duration <= 0:
        raise RuntimeError("The generated voiceover has no audio duration.")
    return duration


def create_voiceover(text: str, destination: Path, config: AppConfig) -> float:
    """Create a WAV voiceover using Edge Neural TTS or the local Windows voice."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    engine = config.tts_engine.casefold().strip()

    if engine == "edge":
        if not _edge_tts_available():
            raise RuntimeError(
                "Microsoft Edge Neural TTS is not installed. Run install.bat again, "
                "or set tts_engine to 'local' in settings.json."
            )

        mp3_destination = destination.with_suffix(".mp3")
        try:
            asyncio.run(_save_edge_mp3(text, mp3_destination, config))
            _convert_mp3_to_wav(mp3_destination, destination)
        except RuntimeError:
            raise
        except Exception as error:
            raise RuntimeError(
                "Microsoft Edge Neural TTS could not connect or generate speech. "
                "Check your internet connection, then try again. You can set "
                "tts_engine to 'local' in settings.json to use Windows voices."
            ) from error
        finally:
            if mp3_destination.exists():
                mp3_destination.unlink(missing_ok=True)

    elif engine == "local":
        _create_local_voiceover(text, destination, config)
    else:
        raise ValueError("tts_engine must be either 'edge' or 'local'.")

    return _audio_duration(destination)


def list_voices() -> list[tuple[str, str]]:
    """List local Windows voices. Edge Neural voice names are set in settings.json."""
    engine = _create_local_engine()
    try:
        return [(voice.id, voice.name) for voice in engine.getProperty("voices")]
    finally:
        engine.stop()
