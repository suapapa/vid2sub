# VID2SUB : Automated Subtitle Creator for Local Videos and YouTube

![vid2sub demo](_asset/vid2sub.gif)

A CLI tool that extracts audio from YouTube URLs or local videos, sends the full audio to a **`whisper-server`** (from **[whisper.cpp](https://github.com/ggml-org/whisper.cpp)**) HTTP endpoint, and saves the received SRT. It sends the entire audio at once without splitting by silence.

## Key Features

- **YouTube**: Downloads best audio using `yt-dlp` and extracts as MP3.
- **Local Video**: Extracts audio tracks from local video files as MP3 using `moviepy`.
- **Vocal Isolation (Optional)**: When the source contains background music or sound effects that degrade transcription, `demucs` can separate clean vocals before STT. Enable with `create --isolate-vocals` or `audio.isolate_vocals: true` in config.
- **Upload**: Sends the extracted MP3 directly to the `/inference` endpoint. Format conversion is handled on the **server-side** (`whisper-server --convert`).
- **Subtitles**: Writes the SRT body returned by the server directly to the output file.
- **Polishing (Optional)**: Refines generated SRTs for mistranslations and typos using a project reference (local file or URL) via `create --polish_with`.
  - **Preprocessing**: When enabled with `--preprocess` (requires an LLM via `llm.api_url` in config or `--use_gemini`), the tool corrects typos, fixes grammar, and merges redundant entries. Off by default.
  - **Humanizer (Korean)**: When enabled with `--humanize` and the subtitle language is Korean (or detected as Korean with `--lang auto`), the `.agents/skills/humanizer` skill is applied after preprocessing/polishing to make dialogue sound more natural. Off by default.
  - **Polishing**: If `--polish_with` is specified, it further refines jargon and terminology based on the provided reference document.
  - By default, it uses `llama-server` (OpenAI-compatible), or **Google Gemini** when the `--use_gemini` flag is provided.
- **Translation**: With the `--translate` (`-t`) option, translates subtitles into target languages (comma-separated codes). After generating from video/URL, writes `<output>_<lang>.srt` for each language. When `input` is an existing `.srt` file, runs translate-only mode and writes `<input>_<lang>.srt` (requires `--translate`). Defaults to `llama-server`; supports Gemini with `--use_gemini`.

## Requirements

- Python 3.12 or higher
- [FFmpeg](https://ffmpeg.org/): Required for `moviepy` / `yt-dlp` audio processing.
- **Demucs (Optional, for vocal isolation)**: Only needed when using `--isolate-vocals` / `audio.isolate_vocals`. Install the optional dependency group with `uv sync --extra separate`. This pulls in PyTorch, so it is large; a GPU (CUDA/MPS) is recommended but not required.
- **whisper-server (`--convert`)**: Follow the build and run instructions in the [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp) repository. You **must** enable the **`--convert`** flag when starting **`whisper-server`**. This allows the server to convert uploaded audio (like MP3) to the required format. This project interacts with the server's **`/inference`** multipart API.
- **Network**: The client must be able to reach the server at `stt.api_url` specified in `config.yaml`.
- **LLM Server (Polishing/Translation)**: Polishing and translation features require **llama-server** (providing an OpenAI-compatible API) by default. Set `llm.api_url` (and optionally `llm.model`, `llm.api_key`) in `config.yaml`. If using `--use_gemini`, you must have access to the Google Gemini API.

## STT Server (whisper-server)

Transcription is performed entirely on the server. Clone and build [whisper.cpp](https://github.com/ggml-org/whisper.cpp), then start **`whisper-server` with the `--convert` flag**. Without `--convert`, the server may fail to recognize uploaded MP3s if they aren't in the expected WAV/sample rate format.

Example command (adjust model path and port as needed):

```bash
# From the whisper.cpp build directory
./build/bin/whisper-server -m models/ggml-base.en.bin --host 0.0.0.0 --port 8080 --convert
```

Specify the base URL (scheme, host, port) in `stt.api_url`; the client will request `{api_url}/inference`.

## Configuration

Place the following in `config.yaml` (see `config_sample.yaml` for a template):

```yaml
stt:
  # whisper.cpp -> requests {api_url}/inference (whisper-server --convert)
  # openai      -> requests {api_url}/audio/transcriptions (OpenAI-compatible, e.g. Bifrost)
  type: whisper.cpp
  api_url: "http://host:port"   # No trailing slash. whisper.cpp: base host; openai: include /v1
  api_key:                        # Optional; sent as Bearer token if set
  model: whisper-1              # Used by the openai type as the transcription model
  default_language: "auto"      # e.g., ko, en. Can be overridden with CLI --lang

llm:
  api_url: "http://host:port/v1"   # OpenAI-compatible API base (e.g., llama-server)
  api_key:                        # Optional; sent as Bearer token if set
  model:                          # Optional; defaults to gpt-3.5-turbo

audio:
  isolate_vocals: false         # Separate vocals from music/SFX (demucs) before STT
  separator_model: htdemucs     # demucs model (htdemucs, htdemucs_ft, mdx_extra, ...)
  separator_device:             # cpu | cuda | mps | (empty = auto-detect)
  separator_output_mp3: true    # keep stems as mp3 instead of wav
```

The server is expected to receive multipart requests with:
- `file`: Audio file
- `response_format`: `srt`
- `language`: Recognition language (or values allowed by the server)

### LLM Prompts

Preprocessing, polishing, translation, and humanization prompts are defined in **`prompt.yaml`** at the project root. Gemini and OpenAI-compatible backends both read from this file via `vid2sub/prompts.py`. Edit the YAML to tune LLM behavior without changing Python code.

Sections: `preprocess`, `polish`, `translate`, `humanize`, and `openai.system` (system message for chat-completions APIs).

## Installation

```bash
git clone <repository-url>
cd vid2sub
uv sync
```

## Usage

```bash
# YouTube → SRT (Uploads MP3; requires whisper-server --convert running)
uv run main.py "https://www.youtube.com/watch?v=..." -o output.srt

# Local File → SRT
uv run main.py video.mp4 -o output.srt

# Generate and translate in one command → output.srt, output_ko.srt, output_en.srt, output_ja.srt
uv run main.py video.mp4 -o output.srt --translate ko,en,ja

# Translate an existing SRT → output_en.srt, output_ja.srt
uv run main.py output.srt --translate en,ja

# Isolate vocals first (source has music/SFX; requires `uv sync --extra separate`)
uv run main.py video.mp4 -o output.srt --isolate-vocals

# Polish using Gemini
export GEMINI_API_KEY=...
uv run main.py video.mp4 -o output.srt --use_gemini --polish_with ./README.md
```

### CLI Options

| Option | Description |
| :--- | :--- |
| `input` | YouTube URL, local video path, or existing `.srt` file (translate-only when `.srt`) |
| `-o`, `--output` | Path to output SRT when generating from video/URL (default: `output.srt`). Ignored for `.srt` input. |
| `-l`, `--lang` | Language code. Uses `stt.default_language` if omitted. |
| `-t`, `--translate` | Comma-separated language codes (e.g., `ko,en,ja`). With video/URL: also translates the generated SRT. With `.srt` input: required; translates that file. Writes `<stem>_<lang>.srt` for each. |
| `--isolate-vocals` / `--no-isolate-vocals` | Enable/disable vocal isolation (demucs) before STT. Overrides `audio.isolate_vocals` in config. |
| `--preprocess` | Enable LLM preprocessing (typo/grammar fixes). Off by default; requires an available LLM. |
| `--humanize` | Enable Korean humanizer after LLM steps. Off by default; applies to Korean subtitles. |
| `--temp_dir` | Fixed temporary directory; not deleted after processing. Per-stage SRTs (STT, preprocess, polish, humanize, translate) are saved under `<temp_dir>/stages/`. |
| `--use_gemini` | Use Gemini API for polishing/translation (Requires `GEMINI_API_KEY`). |
| `-p`, `--polish_with` | Path or `http(s)` URL to a reference document. Refines STT results and overwrites the `-o` file. |

## Dependency Summary

Based on `pyproject.toml`: `requests`, `yt-dlp`, `moviepy`, `pyyaml`, `google-genai`, etc. Refer to the repository's lock/metadata for specific versions.

## Cheat Sheet

Download audio track of an Youtube video with best quality:
```sh
uvx run yt-dlp -f bestaudio --audio-format mp3 "https://www.youtube.com/watch?v=..."
```

Download an Youtube video with best quality:
```sh
uvx run yt-dlp -f bestvideo+bestaudio --merge-output-format mp4 "https://www.youtube.com/watch?v=..."
```

## License

MIT License
