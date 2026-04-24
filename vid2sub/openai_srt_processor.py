import requests
from typing import Optional
from .logger import Logger

class OpenAiSrtProcessor:
    """Polishes or translates SRT using an OpenAI-compatible API (e.g., llama-server)."""

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
        import json
        import sys

        url = f"{self.server_url}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant specialized in SRT subtitle processing."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "stream": True,
        }
        
        Logger.info(f"Calling OpenAI-compatible API at {url} (streaming)...")
        resp = requests.post(url, json=payload, timeout=600, stream=True)
        resp.raise_for_status()

        full_content = ""
        reasoning_content = ""
        
        Logger.separator()
        for line in resp.iter_lines():
            if not line:
                continue
            
            line_str = line.decode("utf-8")
            if line_str.startswith("data: "):
                data_json = line_str[6:]
                if data_json == "[DONE]":
                    break
                
                try:
                    chunk = json.loads(data_json)
                    delta = chunk["choices"][0].get("delta", {})
                    
                    # 사고 과정(reasoning_content) 출력 - 회색
                    if "reasoning_content" in delta and delta["reasoning_content"]:
                        rc = delta["reasoning_content"]
                        if not reasoning_content:
                            print(f"{Logger.C_DIM}{Logger.C_GRAY}[Thinking]{Logger.C_RESET}")
                            sys.stdout.write(Logger.C_DIM + Logger.C_GRAY)
                        reasoning_content += rc
                        sys.stdout.write(rc)
                        sys.stdout.flush()
                    
                    # 실제 응답(content) 출력 - 파란색
                    if "content" in delta and delta["content"]:
                        if reasoning_content and full_content == "":
                            # Thinking이 끝나고 응답이 시작될 때 색상 리셋 및 새 헤더
                            sys.stdout.write(Logger.C_RESET)
                            print(f"\n\n{Logger.C_BLUE}[Response]{Logger.C_RESET}")
                            sys.stdout.write(Logger.C_BLUE)
                        elif full_content == "":
                            print(f"{Logger.C_BLUE}[Response]{Logger.C_RESET}")
                            sys.stdout.write(Logger.C_BLUE)
                        
                        c = delta["content"]
                        full_content += c
                        sys.stdout.write(c)
                        sys.stdout.flush()
                except (json.JSONDecodeError, KeyError):
                    continue

        # 마지막 색상 리셋 및 하단 구분선
        sys.stdout.write(Logger.C_RESET)
        print()
        Logger.separator()
        return self._strip_markdown_code_fence(full_content)

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
        Logger.info(f"Polishing SRT using llama-server...")
        prompt = f"{self._POLISH_PROMPT_HEAD}{reference_text}{self._POLISH_PROMPT_TAIL}{srt_body}"
        out = self._call_api(prompt)
        if not out.endswith("\n"):
            out += "\n"
        return out

    def translate(self, srt_body: str, target_lang: str) -> str:
        Logger.info(f"Translating SRT to [{target_lang}] using llama-server...")
        prompt = f"{self._TRANSLATE_PROMPT_HEAD}{target_lang}{self._TRANSLATE_PROMPT_MID}{srt_body}"
        out = self._call_api(prompt)
        if not out.endswith("\n"):
            out += "\n"
        return out
