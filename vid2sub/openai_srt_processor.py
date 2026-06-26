import requests
from typing import Optional

from .logger import Logger
from .prompts import (
    build_humanize_prompt,
    build_polish_prompt,
    build_preprocess_prompt,
    build_translate_prompt,
    openai_system_message,
)

class OpenAiSrtProcessor:
    """Polishes or translates SRT using an OpenAI-compatible API (e.g., llama-server)."""

    def __init__(
        self,
        api_url: str,
        model: str = "gpt-3.5-turbo",
        api_key: Optional[str] = None,
    ):
        self.api_url = api_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    def _call_api(self, prompt: str, temp: float = 0.3) -> str:
        import json
        import sys

        url = f"{self.api_url}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": openai_system_message()},
                {"role": "user", "content": prompt}
            ],
            "temperature": temp,
            "stream": True,
        }
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        Logger.info(f"Calling OpenAI-compatible API at {url} (streaming)...")
        resp = requests.post(url, json=payload, timeout=600, stream=True, headers=headers)
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
        prompt = build_preprocess_prompt(srt_body)
        out = self._call_api(prompt, temp=0.1)
        if not out.endswith("\n"):
            out += "\n"
        return out

    def polish(self, srt_body: str, reference_text: str) -> str:
        Logger.info(f"Polishing SRT using llama-server...")
        prompt = build_polish_prompt(reference_text, srt_body)
        out = self._call_api(prompt, temp=0.4)
        if not out.endswith("\n"):
            out += "\n"
        return out

    def humanize(self, srt_body: str) -> str:
        Logger.info("Humanizing Korean SRT using humanizer skill...")
        prompt = build_humanize_prompt(srt_body)
        out = self._call_api(prompt, temp=0.3)
        if not out.endswith("\n"):
            out += "\n"
        return out

    def translate(self, srt_body: str, target_lang: str) -> str:
        Logger.info(f"Translating SRT to [{target_lang}] using llama-server...")
        prompt = build_translate_prompt(target_lang, srt_body)
        out = self._call_api(prompt, temp=0.3)
        if not out.endswith("\n"):
            out += "\n"
        return out
