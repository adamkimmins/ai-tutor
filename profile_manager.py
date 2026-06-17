"""
Manages tutor profiles — load, save, list, delete.
Each profile is a JSON file in the profiles/ directory.
"""

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

PROFILES_DIR = os.path.join(os.path.dirname(__file__), "profiles")


@dataclass
class TutorProfile:
    name: str
    subject: str
    system_prompt: str
    language: str                        # whisper language code e.g. "it", "en"
    notes: str = ""
    tts_engine: str = "f5"              # "f5" | "kokoro" | "piper"
    tts_voice: str = ""                 # engine-specific voice identifier
    tts_ref_audio: str = ""             # path to reference audio for voice cloning
    llm_provider: str = "ollama"        # "ollama" | "openai" | "anthropic" | "custom"
    llm_model: str = "gemma3:4b"
    llm_url: str = "http://localhost:11434"
    llm_api_key: str = ""
    context_files: list = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def display_name(self) -> str:
        return self.name

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TutorProfile":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class ProfileManager:
    def __init__(self):
        os.makedirs(PROFILES_DIR, exist_ok=True)

    def list_profiles(self) -> list[TutorProfile]:
        profiles = []
        for fname in os.listdir(PROFILES_DIR):
            if fname.endswith(".json"):
                try:
                    p = self.load(fname[:-5])
                    if p:
                        profiles.append(p)
                except Exception:
                    pass
        return sorted(profiles, key=lambda p: p.name)

    def load(self, profile_id: str) -> Optional[TutorProfile]:
        path = os.path.join(PROFILES_DIR, f"{profile_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return TutorProfile.from_dict(json.load(f))

    def save(self, profile: TutorProfile):
        path = os.path.join(PROFILES_DIR, f"{profile.id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, indent=2, ensure_ascii=False)

    def delete(self, profile_id: str):
        path = os.path.join(PROFILES_DIR, f"{profile_id}.json")
        if os.path.exists(path):
            os.remove(path)

    def has_profiles(self) -> bool:
        return len(self.list_profiles()) > 0