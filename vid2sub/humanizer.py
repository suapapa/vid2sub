from functools import lru_cache
from pathlib import Path

_SRT_HUMANIZE_HEAD = (
    "아래 humanizer 스킬 지침에 따라 SRT 자막의 한국어 대사만 자연스럽게 다듬어 주세요.\n\n"
    "SRT 형식 규칙 (humanizer 적용 중에도 반드시 준수):\n"
    "- 순번(index)과 타임코드는 문자 하나도 변경하지 마세요.\n"
    "- 자막 블록 수, 각 블록의 텍스트 줄 수를 유지하세요. 병합·분할 금지.\n"
    "- 대사는 타임코드 다음 줄에 시작해야 합니다.\n"
    "- 분석 결과, 자연도 등급, 변경 요약은 출력하지 마세요. 유효한 SRT 본문만 응답하세요.\n"
    "- 의미·수치·고유명사·인과관계·부정 표현은 보존하세요 (humanizer 4.5단계).\n"
    "- 변경률은 30% 이내로 보수적으로 다듬으세요.\n\n"
    "--- humanizer skill ---\n\n"
)


def find_skill_dir() -> Path:
    root = Path(__file__).resolve().parent.parent
    skill_dir = root / ".agents" / "skills" / "humanizer"
    if (skill_dir / "SKILL.md").is_file():
        return skill_dir
    raise FileNotFoundError(
        f"humanizer skill not found at {skill_dir}. "
        "Expected .agents/skills/humanizer/SKILL.md in the project root."
    )


@lru_cache(maxsize=1)
def load_skill_bundle() -> str:
    skill_dir = find_skill_dir()
    parts: list[str] = [(skill_dir / "SKILL.md").read_text(encoding="utf-8")]
    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        for ref_path in sorted(refs_dir.glob("*.md")):
            parts.append(
                f"\n\n--- {ref_path.name} ---\n\n{ref_path.read_text(encoding='utf-8')}"
            )
    return "".join(parts)


def is_korean_language(language: str) -> bool:
    code = language.strip().lower()
    if not code or code == "auto":
        return False
    return code in ("ko", "kor", "korean") or code.startswith("ko-")


def contains_korean(text: str) -> bool:
    return any("\uac00" <= ch <= "\ud7a3" for ch in text)


def should_humanize(language: str, srt_body: str) -> bool:
    if is_korean_language(language):
        return True
    if language.strip().lower() == "auto":
        return contains_korean(srt_body)
    return False


def build_humanize_prompt(srt_body: str) -> str:
    return (
        f"{_SRT_HUMANIZE_HEAD}{load_skill_bundle()}\n\n"
        f"--- SRT to humanize ---\n\n{srt_body}"
    )
