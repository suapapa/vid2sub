import os
from pathlib import Path
from typing import Optional

from .logger import Logger


class GeminiSrtPolisher:
    """Polishes SRT content using the Gemini API based on a reference document."""

    _PROMPT_HEAD = (
        "주어진 자막에는 STT가 잘못 알아들은 jargon이 포함되어 있어 원어와 다르니, '---' 라인 아래에 제공된 참고 자료의 문체와 용어에 맞춰 번역을 수정해주세요.\n"
        "---\n"
    )
    _PROMPT_TAIL = (
        "\n\n이후에 SRT 내용이 이어집니다. 당신의 임무는 잘못 전사된 jargon을 참고 자료에 맞게 수정하는 것입니다. "
        "순번(cue number)이나 타임코드를 변경하지 마세요. 자막 항목을 병합하거나 분할하지 마세요. "
        "출력은 입력과 정확히 동일한 수의 항목을 유지해야 합니다.\n\n"
        "엄격한 형식 규칙:\n"
        "대사 텍스트는 반드시 타임코드 라인 바로 다음 줄(새 줄)에서 시작해야 합니다. "
        "절대로 타임코드 라인 뒤에 대사를 붙이지 마세요.\n\n"
        "수정된 전체 SRT 내용만 응답하세요. 서문, 마크다운 코드 펜스(```), 설명 등은 포함하지 마세요.\n\n"
    )

    _PREPROCESS_PROMPT = (
        "주어진 SRT는 STT로 전사한 내용으로 오탈자를 포함하고 있으며 음성이 아닌 곳에서 오동작 하여 동어 반복이 발생되기도 함.\n"
        "오탈자와 문법을 수정하고, 여러번 같은 내용의 자막이 반복되면 하나의 긴 자막으로 합쳐주세요.\n"
        "다만, 하나의 자막이 너무 길어지지 않도록, 한 타임코드에 하나의 문장을 표시하도록 지향해 주세요.\n\n"
        "엄격한 형식 규칙:\n"
        "결과는 반드시 유효한 SRT 형식이어야 합니다. 서문이나 마크다운 코드 펜스(```), 설명 없이 SRT 내용만 응답하세요.\n\n"
        "--- SRT 입력 ---\n\n"
    )


    DEFAULT_MODEL = "gemini-2.5-flash"
    GENERATE_TIMEOUT_MS = 600_000

    def __init__(self, api_key: str, *, model: Optional[str] = None) -> None:
        key = api_key.strip()
        if not key:
            raise ValueError(
                "Google AI (Gemini) API key is required in the GEMINI_API_KEY environment variable when using --polish_with."
            )
        self._api_key = key
        self._model = (model or self.DEFAULT_MODEL).strip()

    @classmethod
    def from_env(cls, *, model: Optional[str] = None) -> "GeminiSrtPolisher":
        key = (os.environ.get("GEMINI_API_KEY") or "").strip()
        if not key:
            raise ValueError(
                "Google AI (Gemini) API key is required in the GEMINI_API_KEY environment variable when using --polish_with."
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

    def _build_user_prompt(self, reference_text: str, srt_body: str) -> str:
        return "".join((self._PROMPT_HEAD, reference_text, self._PROMPT_TAIL, srt_body))

    def preprocess(self, srt_body: str) -> str:
        from google import genai
        from google.genai import types

        user_msg = f"{self._PREPROCESS_PROMPT}{srt_body}"
        client = genai.Client(api_key=self._api_key)
        Logger.info(f"Preprocessing SRT with Gemini ({self._model})...")
        resp = client.models.generate_content(
            model=self._model,
            contents=user_msg,
            config=types.GenerateContentConfig(
                http_options=types.HttpOptions(timeout=self.GENERATE_TIMEOUT_MS),
                temperature=0.1,
            ),
        )
        out = (resp.text or "").strip()
        if not out:
            raise RuntimeError("Gemini response is empty or contains no text.")
        out = self._strip_markdown_code_fence(out)
        if not out:
            raise RuntimeError("Preprocessing result is empty.")
        if not out.endswith("\n"):
            out = "".join((out, "\n"))
        return out

    def polish(self, srt_body: str, reference_text: str) -> str:
        from google import genai
        from google.genai import types

        user_msg = self._build_user_prompt(reference_text, srt_body)
        client = genai.Client(api_key=self._api_key)
        Logger.info(f"Polishing SRT with Gemini ({self._model})...")
        resp = client.models.generate_content(
            model=self._model,
            contents=user_msg,
            config=types.GenerateContentConfig(
                http_options=types.HttpOptions(timeout=self.GENERATE_TIMEOUT_MS),
                temperature=0.3,
            ),
        )
        out = (resp.text or "").strip()
        if not out:
            raise RuntimeError("Gemini response is empty or contains no text.")
        out = self._strip_markdown_code_fence(out)
        if not out:
            raise RuntimeError("Polishing result is empty.")
        if not out.endswith("\n"):
            out = "".join((out, "\n"))
        return out
