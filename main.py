import argparse
import re
import traceback
from typing import Optional

from video2srt.subtitle_generator import SubtitleGenerator

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
                f"번역 언어 코드는 영문 소문자·숫자·하이픈만 허용합니다(2~24자): {part!r}"
            )
        if c not in out:
            out.append(c)
    return out or None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="video2srt - Advanced Subtitle Generator"
    )
    parser.add_argument("input", help="YouTube URL or Local Video Path")
    parser.add_argument("-o", "--output", required=True, help="Output SRT Path")
    parser.add_argument(
        "--lang",
        default=None,
        help="언어 코드 (예: ko). 미지정 시 config.yaml의 whisper_cpp.default_language 사용",
    )
    parser.add_argument(
        "--temp_dir", help="Explicit temporary directory (for debugging)"
    )
    parser.add_argument(
        "--use_gemini",
        action="store_true",
        help="Gemini API를 사용하여 퇴고 및 번역을 수행합니다. (GEMINI_API_KEY 필요)",
    )
    parser.add_argument(
        "--polish_with",
        default=None,
        metavar="PATH_OR_URL",
        help="레퍼런스 문서(로컬 경로 또는 http(s) URL). STT SRT를 퇴고할 때 사용. --use_gemini 미지정 시 llama-server 사용",
    )
    parser.add_argument(
        "--translate_to",
        default=None,
        metavar="LANGS",
        help="쉼표로 구분된 목표 언어 코드(예: en,ja). --use_gemini 미지정 시 llama-server 사용",
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
