import os
from pathlib import Path
from typing import Any

import yaml

OPENAI_API_URL_ENV = "OPENAI_API_URL"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"

_API_SECTIONS = ("stt", "llm")
_API_ENV_FIELDS = (
    (OPENAI_API_URL_ENV, "api_url"),
    (OPENAI_API_KEY_ENV, "api_key"),
)


def _read_yaml_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    raw = path.read_text(encoding="utf-8")
    try:
        return yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        return {}


def _merge_api_env_defaults(
    yaml_config: dict[str, Any],
) -> dict[str, Any]:
    """Apply OPENAI_API_* env vars to stt/llm unless config.yaml sets those keys."""
    merged = dict(yaml_config)

    for section_name in _API_SECTIONS:
        yaml_section = yaml_config.get(section_name)
        if yaml_section is None:
            yaml_section = {}
        elif not isinstance(yaml_section, dict):
            yaml_section = {}

        section: dict[str, Any] = {}
        for env_name, field_name in _API_ENV_FIELDS:
            env_value = os.environ.get(env_name)
            if env_value and field_name not in yaml_section:
                section[field_name] = env_value

        section.update(yaml_section)
        if section:
            merged[section_name] = section
        elif section_name in merged:
            merged[section_name] = section

    return merged


def load_config(path: str = "config.yaml") -> dict[str, Any]:
    yaml_config = _read_yaml_config(Path(path))
    return _merge_api_env_defaults(yaml_config)
