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
| STT (Speech-to-Text) Integration | ✅ Done | `whisper-server --convert` + `POST .../inference` in `config.yaml`'s `server_url` (multipart, `requests`). Client uploads MP3 only. |
| SRT Output | ✅ Done | Save server response (`response_format=srt`) directly. |
| Configuration File (`config.yaml`) Integration | ✅ Done | `server_url`, `default_language` (`pyyaml`) |
| Gemini-based SRT Polishing (`--polish_with`, `GEMINI_API_KEY`) | ✅ Done | `google-genai`, reference is local file or URL. Requires `--use_gemini` flag. |
| Gemini-based SRT Translation (`-l`, `GEMINI_API_KEY`) | ✅ Done | `vid2sub/gemini_srt_translator.py`, Requires `--use_gemini` flag. |
| OpenAI-Compatible Server Support (llama-server) | ✅ Done | Using `llamma_cpp.server_url` (OpenAI API compatible). |
| Subcommand Support (`create`, `translate`) | ✅ Done | Separated generation and translation into subcommands. |
| SRT Preprocessing Step | ✅ Done | Correct typos/grammar and merge redundant entries. Run by default if LLM is available. |
| LICENSE File Addition | ✅ Done | MIT License |

## Technical Stack Notes

- **FFmpeg**: Used in post-processing for `moviepy` and `yt-dlp`. Must be installed on the system.
- **STT**: Assumes an HTTP server started with **`whisper-server --convert`**, not a local `whisper-cli` binary. The endpoint is `{server_url}/inference`, and the request body uses `file`, `response_format=srt`, and `language` fields. Audio format conversion is NOT performed by the client.
- **Language**: If CLI `--lang` is missing, `whisper_cpp.default_language` is used.
- **Subcommands**: Use `create` for generating subtitles from video/URL and `translate` for translating existing SRT files. The `translate` subcommand supports `-l` for multiple target languages.
