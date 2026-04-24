import os
from typing import Optional


class GeminiSrtTranslator:
    """Gemini API로 SRT 대사만 목표 언어로 번역합니다. 번호·타임코드는 유지합니다."""

    DEFAULT_MODEL = "gemini-2.5-flash"
    GENERATE_TIMEOUT_MS = 600_000

    _PROMPT_HEAD = (
        "You are a professional audiovisual subtitle translator.\n\n"
        "Task: Translate ONLY the dialogue/caption text in the SRT below into the language "
        "identified by this ISO 639-1 (or BCP-47) code: "
    )
    _PROMPT_MID = (
        ".\n\n"
        "Strict rules:\n"
        "- Keep each subtitle index line (the integer line) exactly as in the source.\n"
        "- Keep each timestamp line (HH:MM:SS,mmm --> HH:MM:SS,mmm) exactly unchanged, "
        "character-for-character.\n"
        "- Translate only the dialogue line(s) in each block. If a block has multiple text lines, "
        "translate each line; keep the same number of lines per block.\n"
        "- Preserve one blank line between blocks (standard SRT layout).\n"
        "- Do not merge or split blocks. Do not shift timings.\n"
        "- Output valid SRT only: no preamble, no markdown code fences, no commentary.\n"
        "- Keep product names, repo/project names, and code tokens readable; localize only when "
        "natural for that locale.\n\n"
        "--- SRT to translate ---\n\n"
    )

    def __init__(self, api_key: str, *, model: Optional[str] = None) -> None:
        key = api_key.strip()
        if not key:
            raise ValueError(
                "--translate_to 사용 시 환경변수 GEMINI_API_KEY에 Google AI(Gemini) API 키가 필요합니다."
            )
        self._api_key = key
        self._model = (model or self.DEFAULT_MODEL).strip()

    @classmethod
    def from_env(cls, *, model: Optional[str] = None) -> "GeminiSrtTranslator":
        key = (os.environ.get("GEMINI_API_KEY") or "").strip()
        if not key:
            raise ValueError(
                "--translate_to 사용 시 환경변수 GEMINI_API_KEY에 Google AI(Gemini) API 키가 필요합니다."
            )
        return cls(key, model=model)

    @staticmethod
    def _strip_markdown_code_fence(text: str) -> str:
        t = text.strip()
        if not t.startswith("```"):
            return t
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    def _build_user_prompt(self, srt_body: str, target_lang: str) -> str:
        return "".join(
            (self._PROMPT_HEAD, target_lang, self._PROMPT_MID, srt_body)
        )

    def translate(self, srt_body: str, target_lang: str) -> str:
        code = target_lang.strip().lower()
        if not code:
            raise ValueError("번역 언어 코드가 비어 있습니다.")

        from google import genai
        from google.genai import types

        user_msg = self._build_user_prompt(srt_body, code)
        client = genai.Client(api_key=self._api_key)
        print(f"[*] Translating SRT to [{code}] with Gemini ({self._model})...")
        resp = client.models.generate_content(
            model=self._model,
            contents=user_msg,
            config=types.GenerateContentConfig(
                http_options=types.HttpOptions(timeout=self.GENERATE_TIMEOUT_MS),
                temperature=0.25,
            ),
        )
        out = (resp.text or "").strip()
        if not out:
            raise RuntimeError(
                f"Gemini 번역 응답이 비어 있거나 텍스트가 없습니다 (대상: {code})."
            )
        out = self._strip_markdown_code_fence(out)
        if not out:
            raise RuntimeError(f"번역 결과가 비어 있습니다 (대상: {code}).")
        if not out.endswith("\n"):
            out = "".join((out, "\n"))
        return out
