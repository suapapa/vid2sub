import argparse
import re
import traceback
from typing import Optional

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
    parser.add_argument("input", help="YouTube URL or Local Video Path")
    parser.add_argument("-o", "--output", required=True, help="Output SRT Path")
    parser.add_argument(
        "--lang",
        default=None,
        help="Language code (e.g., ko). Uses whisper_cpp.default_language in config.yaml if unspecified.",
    )
    parser.add_argument(
        "--temp_dir", help="Explicit temporary directory (for debugging)"
    )
    parser.add_argument(
        "--use_gemini",
        action="store_true",
        help="Perform polishing and translation using the Gemini API. (Requires GEMINI_API_KEY)",
    )
    parser.add_argument(
        "--polish_with",
        default=None,
        metavar="PATH_OR_URL",
        help="Reference document (local path or http(s) URL). Used for polishing STT SRT. Uses llama-server if --use_gemini is not specified.",
    )
    parser.add_argument(
        "--translate_to",
        default=None,
        metavar="LANGS",
        help="Comma-separated target language codes (e.g., en,ja). Uses llama-server if --use_gemini is not specified.",
    )

    args = parser.parse_args()

    try:
        translate_langs = _parse_translate_to(args.translate_to)
        gen = SubtitleGenerator()
        gen.process(
            args.input,
            args.output,
            args.temp_dir,
            language=args.lang,
            use_gemini=args.use_gemini,
            polish_with=args.polish_with,
            translate_to=translate_langs,
        )
        print("[+] Done!")
    except Exception as e:
        print(f"[!] Error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
