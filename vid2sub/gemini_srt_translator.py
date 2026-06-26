import os
from typing import Optional

from .logger import Logger
from .prompts import build_humanize_prompt, build_translate_prompt


class GeminiSrtTranslator:
    """Translates only SRT dialogue into the target language using the Gemini API. Indices and timecodes are preserved."""

    DEFAULT_MODEL = "gemini-2.5-flash"
    GENERATE_TIMEOUT_MS = 600_000

    def __init__(self, api_key: str, *, model: Optional[str] = None) -> None:
        key = api_key.strip()
        if not key:
            raise ValueError(
                "Google AI (Gemini) API key is required in the GEMINI_API_KEY environment variable when using --translate_to."
            )
        self._api_key = key
        self._model = (model or self.DEFAULT_MODEL).strip()

    @classmethod
    def from_env(cls, *, model: Optional[str] = None) -> "GeminiSrtTranslator":
        key = (os.environ.get("GEMINI_API_KEY") or "").strip()
        if not key:
            raise ValueError(
                "Google AI (Gemini) API key is required in the GEMINI_API_KEY environment variable when using --translate_to."
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

    def translate(self, srt_body: str, target_lang: str) -> str:
        code = target_lang.strip().lower()
        if not code:
            raise ValueError("Translation language code is empty.")

        from google import genai
        from google.genai import types

        user_msg = build_translate_prompt(code, srt_body)
        client = genai.Client(api_key=self._api_key)
        Logger.info(f"Translating SRT to [{code}] with Gemini ({self._model})...")
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
            raise RuntimeError(
                f"Gemini translation response is empty or contains no text (target: {code})."
            )
        out = self._strip_markdown_code_fence(out)
        if not out:
            raise RuntimeError(f"Translation result is empty (target: {code}).")
        if not out.endswith("\n"):
            out = "".join((out, "\n"))
        return out

    def humanize(self, srt_body: str) -> str:
        from google import genai
        from google.genai import types

        user_msg = build_humanize_prompt(srt_body)
        client = genai.Client(api_key=self._api_key)
        Logger.info(f"Humanizing Korean SRT with Gemini ({self._model})...")
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
            raise RuntimeError("Gemini humanizer response is empty or contains no text.")
        out = self._strip_markdown_code_fence(out)
        if not out:
            raise RuntimeError("Humanizer result is empty.")
        if not out.endswith("\n"):
            out = "".join((out, "\n"))
        return out
