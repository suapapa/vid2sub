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
| Local Video-based Audio Extraction | ✅ Done | `moviepy` → MP3 |
| Vocal Isolation (pre-STT) | ✅ Done | Optional `demucs` (`--two-stems=vocals`) step in `vid2sub/vocal_isolator.py`. Enabled via `--isolate-vocals` or `audio.isolate_vocals`. Optional dep group `separate`. |
| STT (Speech-to-Text) Integration | ✅ Done | `whisper-server --convert` + `POST .../inference` at `stt.api_url` (multipart, `requests`). Client uploads MP3 only. |
| SRT Output | ✅ Done | Save server response (`response_format=srt`) directly. |
| Configuration File (`config.yaml`) Integration | ✅ Done | `stt.api_url`, `stt.api_key`, `stt.default_language`, `llm.api_url`, `llm.model`, `llm.api_key` (`pyyaml`) |
| Gemini-based SRT Polishing (`--polish_with`, `GEMINI_API_KEY`) | ✅ Done | `google-genai`, reference is local file or URL. Requires `--use_gemini` flag. |
| Gemini-based SRT Translation (`-l`, `GEMINI_API_KEY`) | ✅ Done | `vid2sub/gemini_srt_translator.py`, Requires `--use_gemini` flag. |
| OpenAI-Compatible Server Support (llama-server) | ✅ Done | Using `llm.api_url` (OpenAI API compatible). |
| Subcommand Support (`create`, `translate`) | ✅ Done | Separated generation and translation into subcommands. |
| SRT Preprocessing Step | ✅ Done | Correct typos/grammar and merge redundant entries. Run by default if LLM is available. |
| Korean Humanizer Integration | ✅ Done | Auto-applies `.agents/skills/humanizer` for Korean SRT after LLM preprocessing/polishing. |
| Centralized LLM Prompts (`prompt.yaml`) | ✅ Done | All LLM prompts in `prompt.yaml`; loaded by `vid2sub/prompts.py`. |
| LICENSE File Addition | ✅ Done | MIT License |

## Technical Stack Notes

- **FFmpeg**: Used in post-processing for `moviepy` and `yt-dlp`. Must be installed on the system.
- **Vocal Isolation**: Optional `demucs` (PyTorch) dependency, invoked as a subprocess (`python -m demucs --two-stems=vocals`). Runs between `extract_audio` and `transcribe_via_server`. Installed via the optional `separate` extra (`uv sync --extra separate`). Config keys: `audio.isolate_vocals`, `audio.separator_model`, `audio.separator_device`, `audio.separator_output_mp3`.
- **STT**: Endpoint selection depends on `stt.type`:
  - `whisper.cpp`: POSTs to `{stt.api_url}/inference` (server started with **`whisper-server --convert`**). Body uses `file`, `response_format=srt`, `language`.
  - `openai`: POSTs to `{stt.api_url}/audio/transcriptions` (OpenAI-compatible gateway, e.g. Bifrost). Body additionally includes `model` (from `stt.model`).
  Audio format conversion is NOT performed by the client. If `stt.api_key` is set, it is sent as a Bearer token.
- **Language**: If CLI `--lang` is missing, `stt.default_language` is used.
- **Subcommands**: Use `create` for generating subtitles from video/URL and `translate` for translating existing SRT files. The `translate` subcommand supports `-l` for multiple target languages.
- **LLM Prompts**: Stored in `prompt.yaml`. `vid2sub/prompts.py` builds user/system messages for preprocess, polish, translate, and humanize steps.
