# AGENTS.md

This file serves as a guideline and progress log for AI agents developing the **vid2sub** project.

## Agent Guidelines

1. **Document Synchronization**: Whenever a new feature (e.g., STT integration, SRT formatting, etc.) is implemented, update the feature list and usage instructions in `README.md` with the latest information.
2. **Progress Tracking**: Update the status of completed items in the [Development Roadmap](#development-roadmap) section of this document.
3. **Maintain Consistency**: Respect and adhere to the existing code style and dependency management practices (`uv`).

## Development Roadmap

| Feature | Status | Remarks |
| :--- | :---: | :--- |
| Project Structure & Dependency Definition | ✅ Done | Using `pyproject.toml`, `uv` |
| YouTube URL-based Audio Extraction | ✅ Done | `yt-dlp` → MP3 |
| YouTube Existing Captions Reuse | ✅ Done | Prefer manual then auto captions via `yt-dlp` metadata; skip audio / vocal isolation / STT when found. `--lang` selects the track; falls back to STT otherwise. `--no-youtube-subtitles` forces the audio/STT path. |
| Local Video-based Audio Extraction | ✅ Done | `moviepy` → MP3 |
| Local MP3 Input (skip extraction) | ✅ Done | `.mp3` path passed directly to STT |
| Vocal Isolation (pre-STT) | ✅ Done | Optional `demucs` (`--two-stems=vocals`) step in `vid2sub/vocal_isolator.py`. Enabled via `--isolate-vocals` or `audio.isolate_vocals`. Optional dep group `separate`. |
| STT (Speech-to-Text) Integration | ✅ Done | `whisper-server --convert` + `POST .../inference` at `stt.api_url` (multipart, `requests`). Client uploads MP3 only. |
| SRT Output | ✅ Done | Save server response (`response_format=srt`) directly. |
| Configuration File (`config.yaml`) Integration | ✅ Done | `stt.api_url`, `stt.api_key`, `stt.default_language`, `llm.api_url`, `llm.model`, `llm.api_key` (`pyyaml`). `OPENAI_API_URL` / `OPENAI_API_KEY` env vars apply to both `stt` and `llm` when omitted from the file; explicit `config.yaml` values override env. |
| OpenAI-Compatible Server Support (llama-server) | ✅ Done | Using `llm.api_url` (OpenAI API compatible) for polishing, translation, preprocessing, and humanization. |
| Unified Single-Command CLI (`--translate`) | ✅ Done | No subcommands. Video/URL → generate (`-o`); optional `--translate` adds `<output>_<lang>.srt`. `.srt` input → translate-only (`--translate` required); writes `<input>_<lang>.srt`. |
| SRT Preprocessing Step | ✅ Done | Correct typos/grammar and merge redundant entries. Opt-in via `--preprocess` (requires an available LLM). |
| Korean Humanizer Integration | ✅ Done | Applies `.agents/skills/humanizer` for Korean SRT after LLM preprocessing/polishing. Opt-in via `--humanize`. |
| Centralized LLM Prompts (`prompt.yaml`) | ✅ Done | All LLM prompts in `prompt.yaml`; loaded by `vid2sub/prompts.py`. |
| LICENSE File Addition | ✅ Done | MIT License |

## Technical Stack Notes

- **FFmpeg**: Used in post-processing for `moviepy` and `yt-dlp`. Must be installed on the system.
- **Vocal Isolation**: Optional `demucs` (PyTorch) dependency, invoked as a subprocess (`python -m demucs --two-stems=vocals`). Runs between `extract_audio` and `transcribe_via_server`. Installed via the optional `separate` extra (`uv sync --extra separate`). Config keys: `audio.isolate_vocals`, `audio.separator_model`, `audio.separator_device`, `audio.separator_output_mp3`.
- **STT**: Endpoint selection depends on `stt.type`:
  - `whisper.cpp`: POSTs to `{stt.api_url}/inference` (server started with **`whisper-server --convert`**). Body uses `file`, `response_format=srt`, `language`, `temperature`, `temperature_inc`. Stock servers default to `no_context=true` (equivalent to `condition_on_previous_text=false`).
  - `openai`: POSTs to `{stt.api_url}/audio/transcriptions` (OpenAI-compatible gateway, e.g. Bifrost). Body additionally includes `model` (from `stt.model`), `temperature`, and `condition_on_previous_text` when supported by the gateway.
  Config keys: `stt.condition_on_previous_text` (default `false`), `stt.temperature` (default `[0.0, 0.2, 0.4, 0.6]`), optional `stt.temperature_inc` (whisper.cpp).
  Audio format conversion is NOT performed by the client. If `stt.api_key` is set, it is sent as a Bearer token.
- **Language**: If CLI `--lang` is missing, `stt.default_language` is used.
- **CLI**: Single command, no subcommands. `input` is a YouTube URL, local video path, or existing `.srt` file. Video/URL: generates subtitles to `-o` or, if omitted, `<temp_dir>/<name>.srt` when `--temp_dir` is set else `<name>.srt` in the current directory (`<name>` is the YouTube title or local file stem); optional `--translate` (`-t`) also writes `<output>_<lang>.srt`. For YouTube URLs, existing captions (manual preferred, then automatic) are downloaded when available and audio/STT is skipped; otherwise the audio→STT path runs. `--no-youtube-subtitles` ignores captions and forces audio/STT. `.srt` input: translate-only; `--translate` is required and writes `<input>_<lang>.srt`. LLM preprocessing and Korean humanization are off by default; enable with `--preprocess` / `--humanize`. When `--temp_dir` is set, each intermediate SRT stage (YouTube/STT, preprocess, polish, humanize, translate) is written under `<temp_dir>/stages/` with numeric-prefixed names for inspection; original SRT backups before LLM steps are saved there as `05_orig.srt`.
- **LLM Prompts**: Stored in `prompt.yaml`. `vid2sub/prompts.py` builds user/system messages for preprocess, polish, translate, and humanize steps.
- **YouTube captions**: `SubtitleGenerator.try_download_youtube_subtitles` probes `subtitles` / `automatic_captions` (excluding `live_chat`), picks a track for `--lang` / `stt.default_language` (`auto` prefers video language then common codes), downloads SRT/VTT, converts VTT→SRT when needed, and stage-dumps as `10_youtube.srt`. `stt.api_url` is only required when the STT fallback path runs.
