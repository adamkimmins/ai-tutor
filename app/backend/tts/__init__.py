"""
TTS backend abstraction.
Each engine implements speak_stream(token_iterator, interrupt_event) -> bool
"""

from profile_manager import TutorProfile


def get_tts_backend(profile: TutorProfile):
    engine = profile.tts_engine.lower()
    if engine == "f5":
        from app.backend.tts.f5 import F5Backend
        return F5Backend(profile)
    elif engine == "kokoro":
        from app.backend.tts.kokoro import KokoroBackend
        return KokoroBackend(profile)
    elif engine == "piper":
        from app.backend.tts.piper import PiperBackend
        return PiperBackend(profile)
    else:
        raise ValueError(f"Unknown TTS engine: {engine}")


class TTSBackend:
    """Base class for TTS backends."""
    def __init__(self, profile: TutorProfile):
        self.profile = profile

    def speak_stream(self, token_iterator, interrupt_event) -> bool:
        raise NotImplementedError

    def load(self):
        pass