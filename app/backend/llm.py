"""
LLM client — Ollama only.
"""

import json
import requests
from profile_manager import TutorProfile


class LLMClient:
    def __init__(self, profile: TutorProfile):
        self.profile = profile
        self.history: list[dict] = []

    def reset(self):
        self.history = []

    def chat(self, user_message: str, on_token=None) -> str:
        self.history.append({"role": "user", "content": user_message})
        messages = [{"role": "system", "content": self.profile.system_prompt}] + self.history
        payload  = {
            "model": self.profile.llm_model,
            "messages": messages,
            "stream": True,
        }
        full = ""
        try:
            url = self.profile.llm_url.rstrip("/") + "/api/chat"
            with requests.post(url, json=payload, stream=True, timeout=60) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = data.get("message", {}).get("content", "")
                    if token:
                        full += token
                        if on_token:
                            on_token(token)
                    if data.get("done"):
                        break
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"[llm error: {e}]"

        self.history.append({"role": "assistant", "content": full})
        return full