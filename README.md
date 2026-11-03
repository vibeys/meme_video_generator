# Automatic Meme Video Generator v2

A Windows-friendly Python project that turns a Reddit text post or manually pasted story into one or more vertical 9:16 MP4 videos with a neural voiceover, gameplay footage, and timed captions.

## What's improved in v2

- **Microsoft Edge Neural TTS is the default voice engine.** It sounds more natural than the old Windows system voice and does not require an API key. It does require an internet connection while generating audio.
- The voice is configurable in `settings.json` (`edge_voice`, `edge_rate`, `edge_pitch`, `edge_volume`). The default is `en-US-AriaNeural`, slightly slower than normal, with a slightly lower pitch.
- **Long stories are split into multiple short videos.** The app no longer silently cuts a long post off at the character limit. It splits around sentence boundaries and exports numbered parts, each within the configured video duration.
- Paragraph breaks are preserved in narration to encourage more natural pauses.
- The old Windows `pyttsx3` voice remains available by setting `tts_engine` to `local`.

> Note: Edge Neural TTS provides natural neural speech and rate/pitch/volume adjustments. It does not expose full per-sentence emotion controls through the `edge-tts` package. For actual named emotional speaking styles, a separate speech service with supported SSML styles is required.

## What it does

1. Fetches text posts from configured subreddits using Reddit's authenticated Data API.
2. Lets you choose a trending candidate, or paste your own story.
3. Generates speech with Microsoft Edge Neural TTS by default.
4. Splits a long story into multiple short-video-sized parts rather than cutting it off.
5. Picks a random gameplay video for each part from `assets/gameplay`.
6. Crops and resizes footage to 1080 x 1920, adds timed captions and a small source header, then combines the voiceover.
7. Saves numbered MP4 parts and a source note in `output`.

## Requirements

- Windows 10 or 11
- Python 3.10 or newer (64-bit recommended)
- Internet connection for installing packages, Edge Neural TTS, and Reddit mode
- At least one gameplay video that you own or are allowed to use
- Reddit Data API access for Reddit mode

## Installation / updating from v1

1. Extract this updated ZIP into a **new folder** first, so your old project stays as a backup.
2. Copy your gameplay clips from the old project's `assets\gameplay` folder into the new project's `assets\gameplay` folder.
3. Double-click `install.bat` in the new folder. It creates a fresh `.venv` and installs Edge TTS with the other dependencies.
4. For Reddit mode, copy your Reddit API values into the new folder's `.env` file. You can also copy the old `.env` if it already contains your working credentials. Keep that file private.
5. Run `run_manual.bat` to paste a story, or `run.bat` for Reddit mode.

Do not copy the old `.venv` folder into the new project. Virtual environments should be recreated by `install.bat`.

## Adding gameplay footage

Place one or more video clips in:

```text
assets\gameplay\
```

Supported formats: MP4, MOV, MKV, AVI, WEBM, and M4V. Use clips you created, own, or have permission to reuse.

## Voice settings

Open `settings.json` and edit:

```json
"tts_engine": "edge",
"edge_voice": "en-US-AriaNeural",
"edge_rate": "-5%",
"edge_volume": "+0%",
"edge_pitch": "-2Hz",
"narration_words_per_part": 150,
"maximum_video_seconds": 90
```

- `tts_engine`: `edge` for Microsoft Edge Neural TTS, or `local` for the installed Windows voice.
- `edge_voice`: Edge voice name. Change it to another supported voice name if preferred.
- `edge_rate`: speaking rate adjustment, for example `-5%` or `+0%`.
- `edge_pitch`: pitch adjustment, for example `-2Hz` or `+0Hz`.
- `edge_volume`: volume adjustment, normally `+0%`.
- `narration_words_per_part`: approximate number of words in each exported Short. Lower this for slower narration or shorter videos.
- `maximum_video_seconds`: hard maximum duration for each output video.

Edge Neural TTS uses an online service, so keep an internet connection active while rendering. If the service cannot connect, check your connection and try again. To use the old local voice instead, set `tts_engine` to `local`.

## Output

For a long story, output will look like this:

```text
output/
|-- reddit_short_YYYYMMDD_HHMMSS_Manual_text_part_01.mp4
|-- reddit_short_YYYYMMDD_HHMMSS_Manual_text_part_02.mp4
|-- reddit_short_YYYYMMDD_HHMMSS_Manual_text_part_03.mp4
`-- reddit_short_YYYYMMDD_HHMMSS_Manual_text_source.txt
```

Each part is a separate vertical video. Review the parts in order before publishing.

## Reddit API setup

Reddit mode requires authenticated Data API access and may require approval. Follow Reddit's current developer instructions and terms:

- Reddit Data API overview: https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki
- Developer platform and data access: https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data

Once your app has access, set these values in `.env`:

```env
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USERNAME=your_reddit_username
```

Never put your Reddit account password in this project. Keep `.env` private.

## Troubleshooting

### Edge voice cannot connect
Edge Neural TTS needs an internet connection. Check your connection and rerun. You can switch to the local Windows voice by changing `tts_engine` to `local` in `settings.json`.

### `No gameplay clips were found`
Add at least one supported video file to `assets\gameplay`.

### Video sections are too long
Lower `narration_words_per_part` in `settings.json` (for example, from `150` to `110`). The app also splits any section that exceeds `maximum_video_seconds` after measuring its generated voiceover.

### FFmpeg or H.264 error
The project uses the FFmpeg binary distributed by `imageio-ffmpeg`. Run `install.bat` again if a package is missing. Review any security software alert before allowing a quarantined binary.

### Captions do not line up perfectly with speech
Caption timing is estimated from word counts, not generated by speech recognition. Lower `caption_words_per_screen` in `settings.json` for shorter caption cards.

## Usage notes

- Only use gameplay clips you have rights or permission to reuse.
- Reddit posts are user-generated content. Check the original post, the creator's rights, Reddit's current Data API terms, and platform rules before republishing or monetizing anything. Attribution alone does not grant permission.
- Review every generated video before publishing. Automated narration can mispronounce names or interpret context incorrectly.

## Run from a terminal

```powershell
.venv\Scripts\python.exe -m meme_maker.main
```

Manual mode:

```powershell
.venv\Scripts\python.exe -m meme_maker.main --manual
```
