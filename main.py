import argparse
import re
import traceback
from pathlib import Path
from typing import Optional

from vid2sub.logger import Logger
from vid2sub.subtitle_generator import SubtitleGenerator

_TRANSLATE_LANG_RE = re.compile(r"^[a-z0-9-]{2,24}$")


def _parse_translate_to(raw: Optional[str]) -> Optional[list[str]]:
    if not raw or not str(raw).strip():
        return None
    out: list[str] = []
    for part in str(raw).split(","):
        c = part.strip().lower()
        if not c:
            continue
        if not _TRANSLATE_LANG_RE.fullmatch(c):
            raise ValueError(
                f"Translation language codes must only contain lowercase letters, numbers, and hyphens (2-24 chars): {part!r}"
            )
        if c not in out:
            out.append(c)
    return out or None


def _is_srt_input(source: str) -> bool:
    s = source.strip()
    if s.startswith(("http://", "https://", "www.", "youtu.be")):
        return False
    return Path(s).suffix.lower() == ".srt"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="vid2sub - Advanced Subtitle Generator"
    )
    parser.add_argument(
        "input",
        help="YouTube URL, local video/MP3 path, or existing .srt file (translate-only when .srt)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output SRT path when generating from video/URL. Defaults to <temp_dir>/<name>.srt when --temp_dir is set, otherwise <name>.srt in the current directory (<name> is the YouTube title or local file stem). Ignored for .srt input.",
    )
    parser.add_argument(
        "-l", "--lang",
        default=None,
        help="Language code (e.g., ko). Uses stt.default_language in config.yaml if unspecified.",
    )
    parser.add_argument(
        "-t", "--translate",
        default=None,
        metavar="LANGS",
        help="Translate into comma-separated languages (e.g., ko,en,ja). With video/URL: also writes <output>_<lang>.srt. With .srt input: required; writes <input>_<lang>.srt.",
    )
    parser.add_argument(
        "-p", "--polish_with",
        default=None,
        metavar="PATH_OR_URL",
        help="Reference document (local path or http(s) URL). Used for polishing STT SRT.",
    )
    parser.add_argument(
        "--isolate-vocals",
        dest="isolate_vocals",
        action="store_true",
        default=None,
        help="Separate vocals from background music/SFX with demucs before STT. Overrides audio.isolate_vocals in config.yaml.",
    )
    parser.add_argument(
        "--no-isolate-vocals",
        dest="isolate_vocals",
        action="store_false",
        help="Disable vocal isolation even if enabled in config.yaml.",
    )
    parser.add_argument(
        "--preprocess",
        dest="preprocess",
        action="store_true",
        help="Run LLM preprocessing (typo/grammar fixes). Off by default.",
    )
    parser.add_argument(
        "--humanize",
        dest="humanize",
        action="store_true",
        help="Apply Korean humanizer after LLM steps. Off by default.",
    )
    parser.add_argument(
        "--temp_dir",
        help="Explicit temporary directory (kept, not deleted). Intermediate per-stage SRTs are saved under <temp_dir>/stages/.",
    )

    args = parser.parse_args()
    preprocess = args.preprocess
    humanize = args.humanize

    try:
        translate_langs = _parse_translate_to(args.translate)
        gen = SubtitleGenerator()

        if _is_srt_input(args.input):
            if not translate_langs:
                raise ValueError(
                    "SRT input requires --translate with at least one target language "
                    "(e.g., --translate en,ja)."
                )
            if args.polish_with:
                raise ValueError(
                    "--polish_with applies only when generating subtitles from video/URL, "
                    "not when translating an existing SRT."
                )
            gen.translate_srt_file(
                args.input,
                translate_to=translate_langs,
                humanize=humanize,
                temp_dir=args.temp_dir,
            )
        else:
            output_path = args.output or str(
                gen.default_output_path(args.input, args.temp_dir)
            )
            gen.process(
                args.input,
                output_path,
                args.temp_dir,
                language=args.lang,
                polish_with=args.polish_with,
                isolate_vocals=args.isolate_vocals,
                preprocess=preprocess,
                humanize=humanize,
            )

            if translate_langs:
                gen.translate_srt_file(
                    output_path,
                    translate_to=translate_langs,
                    humanize=humanize,
                    temp_dir=args.temp_dir,
                )

        Logger.success("Done!")
    except Exception as e:
        Logger.error(f"Error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
