import tempfile
from pathlib import Path
from typing import Any, Optional, Sequence

import requests
import yaml
import yt_dlp
from moviepy import VideoFileClip

from .logger import Logger
from .openai_srt_processor import OpenAiSrtProcessor


class SubtitleGenerator:
    _YDL_OPTS_BASE: dict[str, Any] = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "no_cache_dir": True,
    }

    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        wc = self.config.get("whisper_cpp") or {}
        self.server_url = (wc.get("server_url") or "").rstrip("/")
        self.default_language = wc.get("default_language") or "auto"

        lc = self.config.get("llamma_cpp") or {}
        self.llamma_server_url = (lc.get("server_url") or "").rstrip("/")

        if not self.server_url:
            raise ValueError("whisper_cpp.server_url configuration is required.")

    def _load_config(self, path: str) -> dict:
        p = Path(path)
        if not p.is_file():
            return {}
        raw = p.read_text(encoding="utf-8")
        try:
            return yaml.safe_load(raw) or {}
        except yaml.YAMLError:
            return {}

    def extract_audio(self, source: str, temp_dir: Path) -> Path:
        """Extracts audio from a YouTube URL or a local file."""
        if source.startswith(("http://", "https://", "www.", "youtu.be")):
            return self._download_youtube(source, temp_dir)
        return self._extract_from_file(Path(source), temp_dir)

    def _download_youtube(self, url: str, temp_dir: Path) -> Path:
        Logger.info(f"Downloading YouTube audio: {url}")
        output_path = temp_dir / "raw_audio.mp3"
        ydl_opts = {
            **self._YDL_OPTS_BASE,
            "outtmpl": str(temp_dir / "raw_audio.%(ext)s"),
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
        return output_path

    def _extract_from_file(self, file_path: Path, temp_dir: Path) -> Path:
        Logger.info(f"Extracting audio from local file: {file_path}")
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        output_path = temp_dir / "raw_audio.mp3"
        video = VideoFileClip(str(file_path))
        if not video.audio:
            raise ValueError("The video has no audio track.")

        video.audio.write_audiofile(str(output_path), logger=None)
        video.close()
        return output_path

    def transcribe_via_server(self, audio_path: Path, language: str) -> str:
        """Sends the full audio to the whisper_cpp HTTP server and receives an SRT."""
        inference_url = "".join((self.server_url, "/inference"))
        data = {
            "response_format": "srt",
            "language": language,
        }
        Logger.info(f"POST {inference_url} ({audio_path.name}, language={language})...")
        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "application/octet-stream")}
            resp = requests.post(
                inference_url, data=data, files=files, timeout=24 * 3600
            )
        resp.raise_for_status()
        return resp.text

    def process(
        self,
        source: str,
        output_path: str,
        temp_dir: Optional[str] = None,
        *,
        language: Optional[str] = None,
        use_gemini: bool = False,
        polish_with: Optional[str] = None,
    ):
        """Runs the full subtitle generation process."""
        out_p = Path(output_path)
        if out_p.exists():
            out_p.unlink()

        lang = (language or self.default_language).strip()
        if not lang:
            lang = "auto"

        if temp_dir:
            temp_path = Path(temp_dir)
            temp_path.mkdir(parents=True, exist_ok=True)
            self._run_process(
                source,
                out_p,
                temp_path,
                language=lang,
                use_gemini=use_gemini,
                polish_with=polish_with,
            )
        else:
            with tempfile.TemporaryDirectory() as td:
                self._run_process(
                    source,
                    out_p,
                    Path(td),
                    language=lang,
                    use_gemini=use_gemini,
                    polish_with=polish_with,
                )

    def _run_process(
        self,
        source: str,
        out_file: Path,
        temp_path: Path,
        *,
        language: str,
        use_gemini: bool = False,
        polish_with: Optional[str] = None,
    ):
        raw_audio = self.extract_audio(source, temp_path)
        srt_body = self.transcribe_via_server(raw_audio, language)
        final_srt = srt_body
        Logger.info(f"Saving SRT: {out_file}")
        out_file.write_text(final_srt, encoding="utf-8")

        # Initialize processors based on flags
        polisher = None

        if use_gemini:
            from .gemini_srt_polisher import GeminiSrtPolisher
            polisher = GeminiSrtPolisher.from_env()
        elif self.llamma_server_url:
            openai_proc = OpenAiSrtProcessor(self.llamma_server_url)
            polisher = openai_proc
        elif polish_with:
            raise ValueError(
                "The --use_gemini flag or llamma_cpp.server_url in config.yaml is required for polishing."
            )

        if polish_with:
            # Backup original SRT before polishing
            orig_file = out_file.with_name(f"{out_file.stem}_orig.srt")
            orig_file.write_text(srt_body, encoding="utf-8")
            Logger.info(f"Backup original SRT to: {orig_file}")

            # polisher is already initialized above
            from .gemini_srt_polisher import GeminiSrtPolisher
            ref = GeminiSrtPolisher.load_reference(polish_with)

            final_srt = polisher.polish(srt_body, ref)
            out_file.write_text(final_srt, encoding="utf-8")
            Logger.success(f"Overwrote SRT after polish: {out_file}")

    def translate_srt_file(
        self,
        input_srt_path: str,
        translate_to: Sequence[str],
        use_gemini: bool = False,
    ):
        """Translates an existing SRT file into multiple languages."""
        input_p = Path(input_srt_path)
        if not input_p.exists():
            raise FileNotFoundError(f"SRT file not found: {input_srt_path}")

        srt_body = input_p.read_text(encoding="utf-8")

        translator = None
        if use_gemini:
            from .gemini_srt_translator import GeminiSrtTranslator
            translator = GeminiSrtTranslator.from_env()
        elif self.llamma_server_url:
            translator = OpenAiSrtProcessor(self.llamma_server_url)
        else:
            raise ValueError(
                "The --use_gemini flag or llamma_cpp.server_url in config.yaml is required for translation."
            )

        for code in translate_to:
            c = code.strip().lower()
            if not c:
                continue
            out_lang = input_p.with_name(
                "".join((input_p.stem, "_", c, input_p.suffix))
            )
            translated = translator.translate(srt_body, c)
            out_lang.write_text(translated, encoding="utf-8")
            Logger.success(f"Wrote translated SRT: {out_lang}")
