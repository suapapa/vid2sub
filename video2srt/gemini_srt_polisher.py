import os
from pathlib import Path
from typing import Optional

import requests


class GeminiSrtPolisher:
    """레퍼런스 문서를 바탕으로 Gemini API로 SRT 본문을 퇴고합니다."""

    _PROMPT_HEAD = (
        "Polish Korean subtitle dialogue into natural spoken Korean; align wording with the reference after '---'.\n"
        "---\n"
    )
    _PROMPT_TAIL = (
        "\n\nSRT below: keep cue numbers and timecodes exactly; edit dialogue text only. "
        "Reply with the full revised SRT only—no preamble, markdown fences, or notes.\n\n"
    )

    DEFAULT_MODEL = "gemini-2.5-flash"
    REFERENCE_FETCH_TIMEOUT_SEC = 120
    GENERATE_TIMEOUT_MS = 600_000
    _REFERENCE_USER_AGENT = "video2srt/0.1 (polish reference)"

    def __init__(self, api_key: str, *, model: Optional[str] = None) -> None:
        key = api_key.strip()
        if not key:
            raise ValueError(
                "--polish_with 사용 시 환경변수 GEMINI_API_KEY에 Google AI(Gemini) API 키가 필요합니다."
            )
        self._api_key = key
        self._model = (model or self.DEFAULT_MODEL).strip()

    @classmethod
    def from_env(cls, *, model: Optional[str] = None) -> "GeminiSrtPolisher":
        key = (os.environ.get("GEMINI_API_KEY") or "").strip()
        if not key:
            raise ValueError(
                "--polish_with 사용 시 환경변수 GEMINI_API_KEY에 Google AI(Gemini) API 키가 필요합니다."
            )
        return cls(key, model=model)

    @classmethod
    def load_reference(cls, polish_with: str) -> str:
        s = polish_with.strip()
        if not s:
            raise ValueError("--polish_with 값이 비어 있습니다.")
        if s.startswith(("http://", "https://")):
            print(f"[*] Fetching polish reference: {s}")
            resp = requests.get(
                s,
                timeout=cls.REFERENCE_FETCH_TIMEOUT_SEC,
                headers={"User-Agent": cls._REFERENCE_USER_AGENT},
            )
            resp.raise_for_status()
            if not resp.encoding:
                resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        path = Path(s)
        if not path.is_file():
            raise FileNotFoundError(f"레퍼런스 파일을 찾을 수 없습니다: {path}")
        print(f"[*] Loading polish reference file: {path}")
        return path.read_text(encoding="utf-8")

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

    def _build_user_prompt(self, reference_text: str, srt_body: str) -> str:
        return "".join((self._PROMPT_HEAD, reference_text, self._PROMPT_TAIL, srt_body))

    def polish(self, srt_body: str, reference_text: str) -> str:
        from google import genai
        from google.genai import types

        user_msg = self._build_user_prompt(reference_text, srt_body)
        client = genai.Client(api_key=self._api_key)
        print(f"[*] Polishing SRT with Gemini ({self._model})...")
        resp = client.models.generate_content(
            model=self._model,
            contents=user_msg,
            config=types.GenerateContentConfig(
                http_options=types.HttpOptions(timeout=self.GENERATE_TIMEOUT_MS),
                temperature=0.4,
            ),
        )
        out = (resp.text or "").strip()
        if not out:
            raise RuntimeError("Gemini 응답이 비어 있거나 텍스트가 없습니다.")
        out = self._strip_markdown_code_fence(out)
        if not out:
            raise RuntimeError("퇴고 결과가 비어 있습니다.")
        if not out.endswith("\n"):
            out = "".join((out, "\n"))
        return out
