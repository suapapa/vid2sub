import re
import tempfile
from pathlib import Path
from typing import Any, Optional, Sequence

import requests
import yt_dlp
from moviepy import VideoFileClip

from .config import load_config
from .humanizer import should_humanize
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
        self.config = load_config(config_path)
        stt = self.config.get("stt") or {}
        self.stt_type = stt.get("type") or "whisper.cpp"
        self.stt_api_url = (stt.get("api_url") or "").rstrip("/")
        self.stt_api_key = stt.get("api_key") or None
        self.stt_model = stt.get("model") or "whisper-1"
        self.default_language = stt.get("default_language") or "auto"
        self.stt_condition_on_previous_text = bool(
            stt.get("condition_on_previous_text", False)
        )
        self.stt_temperature, self.stt_temperature_inc = self._parse_stt_temperature(
            stt.get("temperature", [0.0, 0.2, 0.4, 0.6])
        )
        if stt.get("temperature_inc") is not None:
            self.stt_temperature_inc = float(stt["temperature_inc"])

        llm = self.config.get("llm") or {}
        self.llm_api_url = (llm.get("api_url") or "").rstrip("/")
        self.llm_api_key = llm.get("api_key") or None
        self.llm_model = llm.get("model") or "gpt-3.5-turbo"

        audio = self.config.get("audio") or {}
        self.isolate_vocals_default = bool(audio.get("isolate_vocals") or False)
        self.separator_model = audio.get("separator_model") or "htdemucs"
        self.separator_device = audio.get("separator_device") or None
        self.separator_output_mp3 = audio.get("separator_output_mp3")
        if self.separator_output_mp3 is None:
            self.separator_output_mp3 = True

    @staticmethod
    def _parse_stt_temperature(raw: Any) -> tuple[float, float]:
        """Maps Python-whisper-style temperature tuple to (start, increment)."""
        if raw is None:
            return 0.0, 0.2
        if isinstance(raw, (list, tuple)):
            if not raw:
                return 0.0, 0.2
            temps = [float(value) for value in raw]
            if len(temps) >= 2:
                return temps[0], temps[1] - temps[0]
            return temps[0], 0.2
        return float(raw), 0.2

    def _build_stt_request_data(self, language: str) -> dict[str, str]:
        data: dict[str, str] = {
            "response_format": "srt",
        }
        # OpenAI-compatible servers (e.g. whisperX) expect an ISO-639-1 code and
        # reject the literal "auto"; omit the field to enable auto-detection.
        if self.stt_type == "openai":
            if language and language.lower() != "auto":
                data["language"] = language
        else:
            data["language"] = language
        if self.stt_type == "whisper.cpp":
            data["temperature"] = str(self.stt_temperature)
            data["temperature_inc"] = str(self.stt_temperature_inc)
            if self.stt_condition_on_previous_text:
                Logger.warn(
                    "stt.condition_on_previous_text=true is not supported by "
                    "whisper-server HTTP API; stock servers default to "
                    "no_context=true (equivalent to false)."
                )
        elif self.stt_type == "openai":
            # Only send parameters defined by the OpenAI /audio/transcriptions
            # schema. Non-standard fields (e.g. condition_on_previous_text,
            # temperature_inc) make strict gateways/servers such as whisperX
            # return HTTP 422 Unprocessable Content.
            data["model"] = self.stt_model
            data["temperature"] = str(self.stt_temperature)

            # data["align"] = "true"
            # data["diarize"] = "true"
            # data["max_line_count"] = "2"
            # data["max_line_width"] = "16"

            if self.stt_condition_on_previous_text:
                Logger.warn(
                    "stt.condition_on_previous_text is not part of the OpenAI "
                    "/audio/transcriptions schema; ignoring it for stt.type=openai."
                )
        return data

    @staticmethod
    def _maybe_humanize(
        processor, language: str, srt_body: str, *, enabled: bool = True
    ) -> str:
        if not enabled:
            return srt_body
        if not should_humanize(language, srt_body):
            return srt_body
        humanize = getattr(processor, "humanize", None)
        if not callable(humanize):
            return srt_body
        try:
            Logger.info("Applying humanizer skill for Korean subtitle text...")
            return humanize(srt_body)
        except FileNotFoundError as exc:
            Logger.warn(f"Skipping humanizer: {exc}")
            return srt_body

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
        sanitized = re.sub(r"\s+", " ", sanitized).strip().rstrip(". ")
        if not sanitized:
            sanitized = "output"
        if len(sanitized) > 200:
            sanitized = sanitized[:200].rstrip()
        return sanitized

    @staticmethod
    def _is_url(source: str) -> bool:
        return source.strip().startswith(("http://", "https://", "www.", "youtu.be"))

    def get_youtube_title(self, url: str) -> str:
        ydl_opts = {**self._YDL_OPTS_BASE, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        title = info.get("title") if isinstance(info, dict) else None
        return self._sanitize_filename(title or "output")

    def default_output_path(
        self, source: str, temp_dir: Optional[str] = None
    ) -> Path:
        """Resolves the output SRT path when -o is omitted."""
        base_dir = Path(temp_dir) if temp_dir else Path.cwd()
        if self._is_url(source):
            stem = self.get_youtube_title(source)
        else:
            stem = self._sanitize_filename(Path(source.strip()).stem)
        return base_dir / f"{stem}.srt"

    @staticmethod
    def _dump_stage(temp_path: Optional[Path], name: str, body: str) -> None:
        """Persists an intermediate SRT stage into the temp directory."""
        if not temp_path:
            return
        try:
            stages_dir = Path(temp_path) / "stages"
            stages_dir.mkdir(parents=True, exist_ok=True)
            stage_file = stages_dir / name
            stage_file.write_text(body, encoding="utf-8")
            Logger.info(f"Saved stage SRT: {stage_file}")
        except OSError as exc:
            Logger.warn(f"Could not save stage SRT {name}: {exc}")

    @staticmethod
    def load_reference(polish_with: str) -> str:
        s = polish_with.strip()
        if not s:
            raise ValueError("--polish_with value is empty.")
        if s.startswith(("http://", "https://")):
            Logger.info(f"Fetching polish reference: {s}")
            resp = requests.get(
                s,
                timeout=120,
                headers={"User-Agent": "vid2sub/0.1 (polish reference)"},
            )
            resp.raise_for_status()
            if not resp.encoding:
                resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        path = Path(s)
        if not path.is_file():
            raise FileNotFoundError(f"Reference file not found: {path}")
        Logger.info(f"Loading polish reference file: {path}")
        return path.read_text(encoding="utf-8")

    def extract_audio(self, source: str, temp_dir: Path) -> Path:
        """Extracts audio from a YouTube URL or a local file."""
        if self._is_url(source):
            return self._download_youtube(source, temp_dir)
        file_path = Path(source)
        if file_path.suffix.lower() == ".mp3":
            return self._use_mp3_file(file_path)
        return self._extract_from_file(file_path, temp_dir)

    @staticmethod
    def _subtitle_lang_match(available: dict[str, Any], wanted: str) -> Optional[str]:
        """Exact or prefix match for a subtitle language code."""
        if wanted in available:
            return wanted
        base = wanted.split("-", 1)[0]
        if base in available:
            return base
        for code in available:
            if code.startswith(base + "-"):
                return code
        return None

    @classmethod
    def _pick_youtube_subtitle_track(
        cls,
        info: dict[str, Any],
        language: str,
    ) -> Optional[tuple[str, list[dict[str, Any]], bool]]:
        """Picks a caption track: (lang, formats, is_manual) or None."""

        def _usable(subs: Any) -> dict[str, list[dict[str, Any]]]:
            if not isinstance(subs, dict):
                return {}
            out: dict[str, list[dict[str, Any]]] = {}
            for code, formats in subs.items():
                key = str(code).lower()
                if not key or key == "live_chat" or not formats:
                    continue
                if isinstance(formats, list):
                    out[key] = formats
            return out

        manual = _usable(info.get("subtitles"))
        automatic = _usable(info.get("automatic_captions"))
        wanted = (language or "auto").strip().lower() or "auto"

        if wanted != "auto":
            for pool, is_manual in ((manual, True), (automatic, False)):
                found = cls._subtitle_lang_match(pool, wanted)
                if found:
                    return found, pool[found], is_manual
            return None

        video_lang = info.get("language")
        preferred: list[str] = []
        if isinstance(video_lang, str) and video_lang.strip():
            preferred.append(video_lang.strip().lower())
        preferred.extend(("en", "ko", "ja", "zh-hans", "zh", "es", "fr", "de"))

        for pool, is_manual in ((manual, True), (automatic, False)):
            for pref in preferred:
                found = cls._subtitle_lang_match(pool, pref)
                if found:
                    return found, pool[found], is_manual
            if pool:
                code = next(iter(pool))
                return code, pool[code], is_manual
        return None

    @staticmethod
    def _select_subtitle_format(
        formats: Sequence[dict[str, Any]],
    ) -> Optional[dict[str, Any]]:
        by_ext = {
            str(fmt.get("ext")): fmt
            for fmt in formats
            if isinstance(fmt, dict) and fmt.get("url") and fmt.get("ext")
        }
        for ext in ("srt", "vtt", "ttml", "srv3", "srv2", "srv1"):
            if ext in by_ext:
                return by_ext[ext]
        for fmt in formats:
            if isinstance(fmt, dict) and fmt.get("url"):
                return fmt
        return None

    @staticmethod
    def _strip_subtitle_markup(text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        return text.strip()

    @classmethod
    def _vtt_to_srt(cls, vtt_body: str) -> str:
        """Converts WEBVTT (incl. YouTube auto-captions) into SRT text."""
        lines = vtt_body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        blocks: list[tuple[str, str]] = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.upper().startswith("WEBVTT") or line.startswith(
                ("NOTE", "STYLE", "KIND:", "LANGUAGE:", "REGION")
            ):
                i += 1
                continue
            if "-->" not in line:
                i += 1
                continue

            timing = line.split("-->")
            if len(timing) != 2:
                i += 1
                continue
            start = timing[0].strip().split()[0].replace(".", ",")
            end = timing[1].strip().split()[0].replace(".", ",")
            # Normalize short timestamps (mm:ss.mmm → 00:mm:ss,mmm)
            if start.count(":") == 1:
                start = "00:" + start
            if end.count(":") == 1:
                end = "00:" + end

            i += 1
            text_lines: list[str] = []
            while i < len(lines) and lines[i].strip():
                cleaned = cls._strip_subtitle_markup(lines[i])
                if cleaned:
                    text_lines.append(cleaned)
                i += 1
            text = "\n".join(text_lines).strip()
            if not text:
                continue
            # Drop cascading duplicates common in YouTube auto captions.
            if blocks and blocks[-1][1] == text:
                # Extend previous cue end time to the later end.
                prev_start = blocks[-1][0].split(" --> ")[0]
                blocks[-1] = (f"{prev_start} --> {end}", text)
                continue
            blocks.append((f"{start} --> {end}", text))

        out: list[str] = []
        for idx, (timing, text) in enumerate(blocks, start=1):
            out.append(str(idx))
            out.append(timing)
            out.append(text)
            out.append("")
        return "\n".join(out).strip() + ("\n" if blocks else "")

    @classmethod
    def _subtitle_payload_to_srt(cls, body: str, ext: Optional[str]) -> str:
        ext_l = (ext or "").lower().lstrip(".")
        raw = body.lstrip("\ufeff")
        if ext_l == "srt" or (
            "-->" in raw and not raw.lstrip().upper().startswith("WEBVTT")
        ):
            return raw if raw.endswith("\n") else raw + "\n"
        if ext_l in ("vtt", "webvtt") or raw.lstrip().upper().startswith("WEBVTT"):
            return cls._vtt_to_srt(raw)
        # Last resort: try VTT conversion for srv*/ttml-ish text that embeds cues.
        if "-->" in raw:
            return cls._vtt_to_srt(raw)
        raise ValueError(f"Unsupported YouTube subtitle format: {ext_l or 'unknown'}")

    def try_download_youtube_subtitles(
        self, url: str, language: str
    ) -> Optional[tuple[str, str]]:
        """Downloads existing YouTube captions when available.

        Returns ``(srt_body, lang_code)`` or ``None`` when no usable track exists.
        Prefers manual captions over automatic ones. Skips download/STT when used.
        """
        Logger.info(f"Checking YouTube for existing subtitles: {url}")
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "no_cache_dir": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if not isinstance(info, dict):
            return None

        picked = self._pick_youtube_subtitle_track(info, language)
        if not picked:
            Logger.info("No YouTube subtitles found; falling back to audio STT.")
            return None

        lang_code, formats, is_manual = picked
        fmt = self._select_subtitle_format(formats)
        if not fmt:
            Logger.info(
                f"YouTube subtitle track '{lang_code}' has no downloadable URL; "
                "falling back to audio STT."
            )
            return None

        sub_url = str(fmt["url"])
        ext = str(fmt.get("ext") or "vtt")
        kind = "manual" if is_manual else "automatic"
        Logger.info(
            f"Downloading YouTube {kind} subtitles "
            f"(lang={lang_code}, format={ext})..."
        )
        resp = requests.get(
            sub_url,
            timeout=120,
            headers={"User-Agent": "vid2sub/0.1 (youtube subtitles)"},
        )
        resp.raise_for_status()
        if not resp.encoding:
            resp.encoding = resp.apparent_encoding or "utf-8"
        srt_body = self._subtitle_payload_to_srt(resp.text, ext)
        if not srt_body.strip():
            Logger.warn(
                "Downloaded YouTube subtitles were empty; falling back to audio STT."
            )
            return None
        Logger.success(
            f"Using YouTube {kind} subtitles (lang={lang_code}); "
            "skipping audio download, vocal isolation, and STT."
        )
        return srt_body, lang_code

    def _use_mp3_file(self, file_path: Path) -> Path:
        Logger.info(f"Using MP3 file directly: {file_path}")
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        return file_path.resolve()

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

    def isolate_vocals(self, audio_path: Path, temp_dir: Path) -> Path:
        """Separates clean vocals from background music/SFX before STT."""
        from .vocal_isolator import VocalIsolator

        isolator = VocalIsolator(
            model=self.separator_model,
            device=self.separator_device,
            output_mp3=bool(self.separator_output_mp3),
        )
        return isolator.isolate(audio_path, temp_dir)

    def transcribe_via_server(self, audio_path: Path, language: str) -> str:
        """Sends the full audio to the STT HTTP server and receives an SRT."""
        if not self.stt_api_url:
            raise ValueError("stt.api_url configuration is required for STT.")
        if self.stt_type == "whisper.cpp":
            inference_url = f"{self.stt_api_url}/inference"
        elif self.stt_type == "openai":
            inference_url = f"{self.stt_api_url}/audio/transcriptions"
        else:
            raise ValueError(f"Unsupported stt.type: {self.stt_type!r}")
        data = self._build_stt_request_data(language)
        Logger.info(
            f"POST {inference_url} ({audio_path.name}, language={language}, "
            f"temperature={self.stt_temperature}, "
            f"condition_on_previous_text={self.stt_condition_on_previous_text})..."
        )
        headers = {}
        if self.stt_api_key:
            headers["Authorization"] = f"Bearer {self.stt_api_key}"
        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "application/octet-stream")}
            resp = requests.post(
                inference_url,
                data=data,
                files=files,
                headers=headers,
                timeout=24 * 3600,
                # max_line_width=2,
                # max_line_count=20,
            )
        if not resp.ok:
            Logger.error(
                f"STT server returned HTTP {resp.status_code} for "
                f"{inference_url}. Sent fields: {sorted(data)}. "
                f"Response body: {resp.text[:2000]}"
            )
        resp.raise_for_status()
        return self._extract_srt(resp)

    @staticmethod
    def _extract_srt(resp: requests.Response) -> str:
        """Extracts the SRT body from the STT response.

        Some servers return the SRT wrapped in a JSON object ({"text": "..."});
        others return the raw SRT text. Prefer the JSON `text` field when present,
        otherwise fall back to the raw response body.
        """
        raw = resp.text
        content_type = (resp.headers.get("Content-Type") or "").lower()
        looks_json = "json" in content_type or raw.lstrip().startswith("{")
        if looks_json:
            try:
                payload = resp.json()
            except ValueError:
                return raw
            if isinstance(payload, dict):
                text = payload.get("text")
                if isinstance(text, str) and text.strip():
                    return text
        return raw

    def process(
        self,
        source: str,
        output_path: str,
        temp_dir: Optional[str] = None,
        *,
        language: Optional[str] = None,
        polish_with: Optional[str] = None,
        isolate_vocals: Optional[bool] = None,
        preprocess: bool = False,
        humanize: bool = False,
    ):
        """Runs the full subtitle generation process."""
        out_p = Path(output_path)
        if out_p.exists():
            out_p.unlink()

        lang = (language or self.default_language).strip()
        if not lang:
            lang = "auto"

        do_isolate = (
            self.isolate_vocals_default if isolate_vocals is None else isolate_vocals
        )

        if temp_dir:
            temp_path = Path(temp_dir)
            temp_path.mkdir(parents=True, exist_ok=True)
            self._run_process(
                source,
                out_p,
                temp_path,
                language=lang,
                polish_with=polish_with,
                isolate_vocals=do_isolate,
                preprocess=preprocess,
                humanize=humanize,
            )
        else:
            with tempfile.TemporaryDirectory() as td:
                self._run_process(
                    source,
                    out_p,
                    Path(td),
                    language=lang,
                    polish_with=polish_with,
                    isolate_vocals=do_isolate,
                    preprocess=preprocess,
                    humanize=humanize,
                )

    def _run_process(
        self,
        source: str,
        out_file: Path,
        temp_path: Path,
        *,
        language: str,
        polish_with: Optional[str] = None,
        isolate_vocals: bool = False,
        preprocess: bool = False,
        humanize: bool = False,
    ):
        effective_language = language
        youtube_sub = None
        if self._is_url(source):
            youtube_sub = self.try_download_youtube_subtitles(source, language)

        if youtube_sub:
            srt_body, caption_lang = youtube_sub
            if (language or "auto").strip().lower() in ("", "auto"):
                effective_language = caption_lang
            self._dump_stage(temp_path, "10_youtube.srt", srt_body)
        else:
            raw_audio = self.extract_audio(source, temp_path)
            audio_for_stt = raw_audio
            if isolate_vocals:
                audio_for_stt = self.isolate_vocals(raw_audio, temp_path)
            srt_body = self.transcribe_via_server(audio_for_stt, language)
            self._dump_stage(temp_path, "10_stt.srt", srt_body)

        final_srt = srt_body
        Logger.info(f"Saving SRT: {out_file}")
        out_file.write_text(final_srt, encoding="utf-8")

        polisher = None
        if self.llm_api_url:
            polisher = OpenAiSrtProcessor(
                self.llm_api_url,
                model=self.llm_model,
                api_key=self.llm_api_key,
            )
        elif polish_with or preprocess or humanize:
            raise ValueError(
                "llm.api_url in config.yaml is required for preprocessing, polishing, or humanization."
            )

        if polisher and (preprocess or polish_with or humanize):
            self._dump_stage(temp_path, "05_orig.srt", srt_body)

            if preprocess:
                srt_body = polisher.preprocess(srt_body)
                self._dump_stage(temp_path, "20_preprocess.srt", srt_body)
            final_srt = srt_body

            if polish_with:
                ref = self.load_reference(polish_with)
                final_srt = polisher.polish(srt_body, ref)
                self._dump_stage(temp_path, "30_polish.srt", final_srt)

            humanized = self._maybe_humanize(
                polisher, effective_language, final_srt, enabled=humanize
            )
            if humanized != final_srt:
                self._dump_stage(temp_path, "40_humanize.srt", humanized)
            final_srt = humanized
            out_file.write_text(final_srt, encoding="utf-8")
            Logger.success(f"Overwrote SRT after LLM processing: {out_file}")

    def translate_srt_file(
        self,
        input_srt_path: str,
        translate_to: Sequence[str],
        humanize: bool = False,
        temp_dir: Optional[str] = None,
    ):
        """Translates an existing SRT file into multiple languages."""
        input_p = Path(input_srt_path)
        if not input_p.exists():
            raise FileNotFoundError(f"SRT file not found: {input_srt_path}")

        temp_path = Path(temp_dir) if temp_dir else None
        srt_body = input_p.read_text(encoding="utf-8")

        if not self.llm_api_url:
            raise ValueError("llm.api_url in config.yaml is required for translation.")
        translator = OpenAiSrtProcessor(
            self.llm_api_url,
            model=self.llm_model,
            api_key=self.llm_api_key,
        )

        for code in translate_to:
            c = code.strip().lower()
            if not c:
                continue
            out_lang = input_p.with_name(
                "".join((input_p.stem, "_", c, input_p.suffix))
            )
            translated = translator.translate(srt_body, c)
            self._dump_stage(temp_path, f"50_translate_{c}.srt", translated)
            humanized = self._maybe_humanize(
                translator, c, translated, enabled=humanize
            )
            if humanized != translated:
                self._dump_stage(temp_path, f"60_humanize_{c}.srt", humanized)
            translated = humanized
            out_lang.write_text(translated, encoding="utf-8")
            Logger.success(f"Wrote translated SRT: {out_lang}")
