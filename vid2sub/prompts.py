from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_PROMPTS_PATH = Path(__file__).resolve().parent.parent / "prompt.yaml"


@lru_cache(maxsize=1)
def _load_prompts(path: str = "") -> dict[str, Any]:
    prompts_path = Path(path) if path else _DEFAULT_PROMPTS_PATH
    if not prompts_path.is_file():
        raise FileNotFoundError(
            f"Prompt file not found: {prompts_path}. "
            "Expected prompt.yaml in the project root."
        )
    raw = prompts_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid prompt file format: {prompts_path}")
    return data


def _section(*keys: str, path: str = "") -> str:
    node: Any = _load_prompts(path)
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            raise KeyError(f"Missing prompt section: {'.'.join(keys)}")
        node = node[key]
    if not isinstance(node, str):
        raise TypeError(f"Prompt section {'.'.join(keys)} must be a string")
    return node


def openai_system_message(*, path: str = "") -> str:
    return _section("openai", "system", path=path)


def build_preprocess_prompt(srt_body: str, *, path: str = "") -> str:
    return f"{_section('preprocess', 'body', path=path)}{srt_body}"


def build_polish_prompt(
    reference_text: str, srt_body: str, *, path: str = ""
) -> str:
    return "".join(
        (
            _section("polish", "head", path=path),
            reference_text,
            _section("polish", "tail", path=path),
            srt_body,
        )
    )


def build_translate_prompt(
    target_lang: str, srt_body: str, *, path: str = ""
) -> str:
    code = target_lang.strip().lower()
    if not code:
        raise ValueError("Translation language code is empty.")
    return "".join(
        (
            _section("translate", "head", path=path),
            code,
            _section("translate", "mid", path=path),
            srt_body,
        )
    )


def build_humanize_prompt(srt_body: str, *, path: str = "") -> str:
    from .humanizer import load_skill_bundle

    return (
        f"{_section('humanize', 'head', path=path)}{load_skill_bundle()}\n\n"
        f"{_section('humanize', 'srt_marker', path=path)}\n\n{srt_body}"
    )
