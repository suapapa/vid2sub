import requests
from typing import Optional
from .logger import Logger

class OpenAiSrtProcessor:
    """Polishes or translates SRT using an OpenAI-compatible API (e.g., llama-server)."""

    _PREPROCESS_PROMPT = (
        "주어진 SRT는 STT로 전사한 내용으로 오탈자를 포함하고 있으며 음성이 아닌 곳에서 오동작 하여 동어 반복이 발생되기도 함.\n"
        "오탈자와 문법을 수정하고, 여러번 같은 내용의 자막이 반복되면 하나의 타임코드의 자막으로 합쳐주세요.\n"
        "다만, 하나의 자막이 너무 길어지지 않도록, 한 타임코드에 하나의 문장을 표시하도록 지향해 주세요.\n\n"
        "엄격한 형식 규칙:\n"
        "결과는 반드시 유효한 SRT 형식이어야 합니다. 서문이나 마크다운 코드 펜스, 설명 없이 SRT 내용만 응답하세요.\n\n"
        "--- SRT 입력 ---\n\n"
    )

    _POLISH_PROMPT_HEAD = (
        "주어진 자막에는 STT가 잘못 알아들은 jargon이 포함되어 있어 원어와 다르니, ---' 라인 아래에 제공된 참고 자료의 문체와 용어에 맞춰 번역을 수정해주세요.\n"
        "---\n"
    )
    _POLISH_PROMPT_TAIL = (
        "\n\n이후에 SRT 내용이 이어집니다. 당신의 임무는 잘못 전사된 jargon을 참고 자료에 맞게 수정하는 것입니다. "
        "순번(cue number)이나 타임코드를 변경하지 마세요. 자막 항목을 병합하거나 분할하지 마세요. "
        "출력은 입력과 정확히 동일한 수의 항목을 유지해야 합니다.\n\n"
        "엄격한 형식 규칙:\n"
        "대사 텍스트는 반드시 타임코드 라인 바로 다음 줄(새 줄)에서 시작해야 합니다. "
        "절대로 타임코드 라인 뒤에 대사를 붙이지 마세요.\n\n"
        "수정된 전체 SRT 내용만 응답하세요. 서문, 마크다운 코드 펜스, 설명 등은 포함하지 마세요.\n\n"
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

    def _call_api(self, prompt: str, temp: float = 0.3) -> str:
        import json
        import sys

        url = f"{self.server_url}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant specialized in SRT subtitle processing."},
                {"role": "user", "content": prompt}
            ],
            "temperature": temp,
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

    def preprocess(self, srt_body: str) -> str:
        Logger.info(f"Preprocessing SRT using llama-server...")
        prompt = f"{self._PREPROCESS_PROMPT}{srt_body}"
        out = self._call_api(prompt, temp=0.1)
        if not out.endswith("\n"):
            out += "\n"
        return out

    def polish(self, srt_body: str, reference_text: str) -> str:
        Logger.info(f"Polishing SRT using llama-server...")
        prompt = f"{self._POLISH_PROMPT_HEAD}{reference_text}{self._POLISH_PROMPT_TAIL}{srt_body}"
        out = self._call_api(prompt, temp=0.4)
        if not out.endswith("\n"):
            out += "\n"
        return out

    def translate(self, srt_body: str, target_lang: str) -> str:
        Logger.info(f"Translating SRT to [{target_lang}] using llama-server...")
        prompt = f"{self._TRANSLATE_PROMPT_HEAD}{target_lang}{self._TRANSLATE_PROMPT_MID}{srt_body}"
        out = self._call_api(prompt, temp=0.3)
        if not out.endswith("\n"):
            out += "\n"
        return out
