from functools import lru_cache
from pathlib import Path


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
