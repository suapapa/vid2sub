# VID2SUB : Automated Subtitle Creator for Local Videos and YouTube

![vid2sub demo](_asset/vid2sub.gif)

A CLI tool that extracts audio from YouTube URLs or local videos, sends the full audio to a **`whisper-server`** (from **[whisper.cpp](https://github.com/ggml-org/whisper.cpp)**) HTTP endpoint, and saves the received SRT. It sends the entire audio at once without splitting by silence.

## Key Features

- **YouTube**: Downloads best audio using `yt-dlp` and extracts as MP3.
- **Local Video**: Extracts audio tracks from local video files as MP3 using `moviepy`.
- **Upload**: Sends the extracted MP3 directly to the `/inference` endpoint. Format conversion is handled on the **server-side** (`whisper-server --convert`).
- **Subtitles**: Writes the SRT body returned by the server directly to the output file.
- **Polishing (Optional)**: Refines generated SRTs for mistranslations and typos using a project reference (local file or URL) via `create --polish_with`.
  - **Preprocessing**: If an LLM is available (via `llamma_cpp.server_url` in config or `--use_gemini`), the tool automatically corrects typos, fixes grammar, and merges redundant entries.
  - **Polishing**: If `--polish_with` is specified, it further refines jargon and terminology based on the provided reference document.
  - By default, it uses `llama-server` (OpenAI-compatible), or **Google Gemini** when the `--use_gemini` flag is provided.
- **Translation**: Translates SRT files into target languages (comma-separated codes) using the `translate` subcommand. Similarly, it defaults to `llama-server` and supports Gemini.

## Requirements

- Python 3.12 or higher
- [FFmpeg](https://ffmpeg.org/): Required for `moviepy` / `yt-dlp` audio processing.
- **whisper-server (`--convert`)**: Follow the build and run instructions in the [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp) repository. You **must** enable the **`--convert`** flag when starting **`whisper-server`**. This allows the server to convert uploaded audio (like MP3) to the required format. This project interacts with the server's **`/inference`** multipart API.
- **Network**: The client must be able to reach the server at `whisper_cpp.server_url` specified in `config.yaml`.
- **LLM Server (Polishing/Translation)**: Polishing and translation features require **llama-server** (providing an OpenAI-compatible API) by default. Set `llamma_cpp.server_url` in `config.yaml`. If using `--use_gemini`, you must have access to the Google Gemini API.

## STT Server (whisper-server)

Transcription is performed entirely on the server. Clone and build [whisper.cpp](https://github.com/ggml-org/whisper.cpp), then start **`whisper-server` with the `--convert` flag**. Without `--convert`, the server may fail to recognize uploaded MP3s if they aren't in the expected WAV/sample rate format.

Example command (adjust model path and port as needed):

```bash
# From the whisper.cpp build directory
./build/bin/whisper-server -m models/ggml-base.en.bin --host 0.0.0.0 --port 8080 --convert
```

Specify the base URL (scheme, host, port) in `server_url`; the client will request `{server_url}/inference`.

## Configuration

Place the following in `config.yaml` (see `config_sample.yaml` for a template):

```yaml
whisper_cpp:
  server_url: "http://host:port"   # No trailing slash; requests will be sent to .../inference
  default_language: "auto"        # e.g., ko, en. Can be overridden with CLI --lang

llamma_cpp:
  server_url: "http://host:port"   # OpenAI-compatible API server (e.g., llama-server)
```

The server is expected to receive multipart requests with:
- `file`: Audio file
- `response_format`: `srt`
- `language`: Recognition language (or values allowed by the server)

## Installation

```bash
git clone <repository-url>
cd vid2sub
uv sync
```

## Usage

```bash
# YouTube → SRT (Uploads MP3; requires whisper-server --convert running)
uv run main.py create "https://www.youtube.com/watch?v=..." -o output.srt

# Local File → SRT
uv run main.py create video.mp4 -o output.srt

# Polish using Gemini
export GEMINI_API_KEY=...
uv run main.py create video.mp4 -o output.srt --use_gemini --polish_with ./README.md

# Translate existing SRT
uv run main.py translate -l en,ja,pl output.srt
```

### CLI Options

| Subcommand | Option | Description |
| :--- | :--- | :--- |
| **create** | `input` | YouTube URL or Local Video Path (Positional) |
| | `-o`, `--output` | Path to output SRT file (Required) |
| | `--lang` | Language code. Uses `whisper_cpp.default_language` if omitted. |
| | `--temp_dir` | Fixed temporary directory; will not be deleted after processing. |
| | `--use_gemini` | Use Gemini API for polishing/translation (Requires `GEMINI_API_KEY`). |
| | `--polish_with` | Path or `http(s)` URL to a reference document. Refines STT results and overwrites the `-o` file. |
| **translate** | `input` | Input SRT file (Positional) |
| | `-l`, `--langs` | Comma-separated language codes (Required) |
| | `--use_gemini` | Use Gemini API for translation. |

## Dependency Summary

Based on `pyproject.toml`: `requests`, `yt-dlp`, `moviepy`, `pyyaml`, `google-genai`, etc. Refer to the repository's lock/metadata for specific versions.

## License

MIT License
