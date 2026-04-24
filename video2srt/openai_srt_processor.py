import requests
from typing import Optional

class OpenAiSrtProcessor:
    """OpenAI 호환 API(llama-server 등)를 사용하여 SRT를 퇴고하거나 번역합니다."""

    _POLISH_PROMPT_HEAD = (
        "Polish Korean subtitle dialogue into natural spoken Korean. Align wording and terminology with the reference provided below the '---' line.\n"
        "---\n"
    )
    _POLISH_PROMPT_TAIL = (
        "\n\nSRT content follows. Your task: edit ONLY the dialogue text for natural flow. "
        "DO NOT change any cue numbers, DO NOT change any timecodes, and DO NOT merge or split subtitle entries. "
        "The output MUST have the EXACT same number of entries as the input.\n\n"
        "STRICT FORMATTING RULE:\n"
        "The dialogue text MUST start on a NEW line immediately following the timecode line. "
        "NEVER append dialogue to the timecode line.\n\n"
        "Reply with the full revised SRT only—no preamble, markdown fences, or notes.\n\n"
    )

    _TRANSLATE_PROMPT_HEAD = (
        "You are a professional audiovisual subtitle translator.\n\n"
        "Task: Translate ONLY the dialogue/caption text in the SRT below into the language "
        "identified by this ISO 639-1 (or BCP-47) code: "
    )
    _TRANSLATE_PROMPT_MID = (
        ".\n\n"
        "Strict rules:\n"
        "- Keep each subtitle index line (the integer line) exactly as in the source.\n"
        "- Keep each timestamp line (HH:MM:SS,mmm --> HH:MM:SS,mmm) exactly unchanged, character-for-character.\n"
        "- Translate only the dialogue line(s) in each block. If a block has multiple text lines, translate each line; keep the same number of lines per block.\n"
        "- Preserve one blank line between blocks (standard SRT layout).\n"
        "- Do not merge or split blocks. Do not shift timings.\n"
        "- STRICT FORMATTING RULE: The translated dialogue text MUST start on a NEW line immediately following the timecode line. NEVER append dialogue to the timecode line.\n"
        "- Output valid SRT only: no preamble, no markdown code fences, no commentary.\n"
        "- Keep product names, repo/project names, and code tokens readable; localize only when natural for that locale.\n\n"
        "--- SRT to translate ---\n\n"
    )

    def __init__(self, server_url: str, model: str = "gpt-3.5-turbo"):
        self.server_url = server_url.rstrip("/")
        self.model = model

    def _call_api(self, prompt: str) -> str:
        url = f"{self.server_url}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant specialized in SRT subtitle processing."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
        }
        
        print(f"[*] Calling OpenAI-compatible API at {url}...")
        resp = requests.post(url, json=payload, timeout=600)
        resp.raise_for_status()
        
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        return self._strip_markdown_code_fence(content)

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

    def polish(self, srt_body: str, reference_text: str) -> str:
        print(f"[*] Polishing SRT using llama-server...")
        prompt = f"{self._POLISH_PROMPT_HEAD}{reference_text}{self._POLISH_PROMPT_TAIL}{srt_body}"
        out = self._call_api(prompt)
        if not out.endswith("\n"):
            out += "\n"
        return out

    def translate(self, srt_body: str, target_lang: str) -> str:
        print(f"[*] Translating SRT to [{target_lang}] using llama-server...")
        prompt = f"{self._TRANSLATE_PROMPT_HEAD}{target_lang}{self._TRANSLATE_PROMPT_MID}{srt_body}"
        out = self._call_api(prompt)
        if not out.endswith("\n"):
            out += "\n"
        return out
