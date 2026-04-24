import argparse
import traceback

from video2srt.subtitle_generator import SubtitleGenerator


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
        "--polish_with",
        default=None,
        metavar="PATH_OR_URL",
        help="레퍼런스 문서(로컬 경로 또는 http(s) URL). STT SRT를 Gemini로 퇴고할 때 사용. GEMINI_API_KEY 필요",
    )

    args = parser.parse_args()

    try:
        gen = SubtitleGenerator()
        gen.process(
            args.input,
            args.output,
            args.temp_dir,
            language=args.lang,
            polish_with=args.polish_with,
        )
        print("[+] Done!")
    except Exception as e:
        print(f"[!] Error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
