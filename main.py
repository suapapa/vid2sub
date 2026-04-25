import argparse
import re
import traceback
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="vid2sub - Advanced Subtitle Generator"
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # 'create' subcommand
    create_parser = subparsers.add_parser("create", help="Create subtitles from video/URL")
    create_parser.add_argument("input", help="YouTube URL or Local Video Path")
    create_parser.add_argument("-o", "--output", default="output.srt", help="Output SRT Path (default: output.srt)")
    create_parser.add_argument(
        "-l", "--lang",
        default=None,
        help="Language code (e.g., ko). Uses whisper_cpp.default_language in config.yaml if unspecified.",
    )
    create_parser.add_argument(
        "-p", "--polish_with",
        default=None,
        metavar="PATH_OR_URL",
        help="Reference document (local path or http(s) URL). Used for polishing STT SRT.",
    )
    create_parser.add_argument(
        "--use_gemini",
        action="store_true",
        help="Perform polishing and translation using the Gemini API. (Requires GEMINI_API_KEY)",
    )
    create_parser.add_argument(
        "--temp_dir", help="Explicit temporary directory (for debugging)"
    )

    # 'translate' subcommand
    translate_parser = subparsers.add_parser("translate", help="Translate existing subtitles")
    translate_parser.add_argument("input", help="Input SRT Path")
    translate_parser.add_argument(
        "-l", "--langs",
        required=True,
        metavar="LANGS",
        help="Comma-separated target language codes (e.g., en,ja)",
    )
    translate_parser.add_argument(
        "--use_gemini",
        action="store_true",
        help="Perform translation using the Gemini API. (Requires GEMINI_API_KEY)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        gen = SubtitleGenerator()
        if args.command == "create":
            gen.process(
                args.input,
                args.output,
                args.temp_dir,
                language=args.lang,
                use_gemini=args.use_gemini,
                polish_with=args.polish_with,
            )
        elif args.command == "translate":
            translate_langs = _parse_translate_to(args.langs)
            if not translate_langs:
                raise ValueError("At least one target language must be specified.")
            gen.translate_srt_file(
                args.input,
                translate_to=translate_langs,
                use_gemini=args.use_gemini,
            )
        
        Logger.success("Done!")
    except Exception as e:
        Logger.error(f"Error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
