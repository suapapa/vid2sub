import tempfile
from pathlib import Path
from typing import Any, Optional, Sequence

import requests
import yaml
import yt_dlp
from moviepy import VideoFileClip

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
            raise ValueError("whisper_cpp.server_url 설정이 필요합니다.")

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
        """YouTube URL 또는 로컬 파일에서 오디오를 추출합니다."""
        if source.startswith(("http://", "https://", "www.", "youtu.be")):
            return self._download_youtube(source, temp_dir)
        return self._extract_from_file(Path(source), temp_dir)

    def _download_youtube(self, url: str, temp_dir: Path) -> Path:
        print(f"[*] Downloading YouTube audio: {url}")
        output_path = temp_dir / "raw_audio.mp3"
        ydl_opts = {
            **self._YDL_OPTS_BASE,
            "outtmpl": str(temp_dir / "raw_audio.%(ext)s"),
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
        return output_path

    def _extract_from_file(self, file_path: Path, temp_dir: Path) -> Path:
        print(f"[*] Extracting audio from local file: {file_path}")
        if not file_path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        output_path = temp_dir / "raw_audio.mp3"
        video = VideoFileClip(str(file_path))
        if not video.audio:
            raise ValueError("비디오에 오디오 트랙이 없습니다.")

        video.audio.write_audiofile(str(output_path), logger=None)
        video.close()
        return output_path

    def transcribe_via_server(self, audio_path: Path, language: str) -> str:
        """whisper_cpp HTTP 서버에 전체 오디오를 보내 SRT를 받습니다."""
        inference_url = "".join((self.server_url, "/inference"))
        data = {
            "response_format": "srt",
            "language": language,
        }
        print(f"[*] POST {inference_url} ({audio_path.name}, language={language})...")
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
        translate_to: Optional[Sequence[str]] = None,
    ):
        """전체 자막 생성 프로세스를 실행합니다."""
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
                translate_to=translate_to,
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
                    translate_to=translate_to,
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
        translate_to: Optional[Sequence[str]] = None,
    ):
        raw_audio = self.extract_audio(source, temp_path)
        srt_body = self.transcribe_via_server(raw_audio, language)
        final_srt = srt_body
        print(f"[*] Saving SRT: {out_file}")
        out_file.write_text(final_srt, encoding="utf-8")

        # Initialize processors based on flags
        polisher = None
        translator = None

        if use_gemini:
            from .gemini_srt_polisher import GeminiSrtPolisher
            from .gemini_srt_translator import GeminiSrtTranslator
            polisher = GeminiSrtPolisher.from_env()
            translator = GeminiSrtTranslator.from_env()
        elif self.llamma_server_url:
            openai_proc = OpenAiSrtProcessor(self.llamma_server_url)
            polisher = openai_proc
            translator = openai_proc
        elif polish_with or translate_to:
            raise ValueError(
                "퇴고/번역을 위해 --use_gemini 플래그를 사용하거나 config.yaml에 llamma_cpp.server_url 설정이 필요합니다."
            )

        if polish_with:
            # Backup original SRT before polishing
            orig_file = out_file.with_name(f"{out_file.stem}_orig.srt")
            orig_file.write_text(srt_body, encoding="utf-8")
            print(f"[*] Backup original SRT to: {orig_file}")

            # polisher is already initialized above
            if use_gemini:
                from .gemini_srt_polisher import GeminiSrtPolisher
                ref = GeminiSrtPolisher.load_reference(polish_with)
            else:
                # Reuse GeminiSrtPolisher's load_reference as it's a generic static method
                from .gemini_srt_polisher import GeminiSrtPolisher
                ref = GeminiSrtPolisher.load_reference(polish_with)

            final_srt = polisher.polish(srt_body, ref)
            out_file.write_text(final_srt, encoding="utf-8")
            print(f"[*] Overwrote SRT after polish: {out_file}")

        if translate_to:
            for code in translate_to:
                c = code.strip().lower()
                if not c:
                    continue
                out_lang = out_file.with_name(
                    "".join((out_file.stem, "_", c, out_file.suffix))
                )
                translated = translator.translate(final_srt, c)
                out_lang.write_text(translated, encoding="utf-8")
                print(f"[*] Wrote translated SRT: {out_lang}")
