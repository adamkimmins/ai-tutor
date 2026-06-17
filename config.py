"""
config.py — central configuration for the AI Tutor.

- Auto-detects Whisper binary + model location across Windows/macOS/Linux.
- Falls back gracefully when detection fails (returns None, app should
  surface a friendly error).
- Profile fields (profile.language, profile.tts_voice, etc.) ALWAYS win
  over the defaults here — these are just the launch-time fallbacks.
"""

import os
import sys
import shutil
from pathlib import Path

# ── App paths ────────────────────────────────────────────────────────────
APP_ROOT      = Path(__file__).parent.resolve()
PROFILES_DIR  = APP_ROOT / "profiles"
PROFILES_DIR.mkdir(exist_ok=True)

def _user_temp() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("TEMP", os.path.expanduser("~")))
    return Path("/tmp")

TEMP_DIR = _user_temp()
TEMP_WAV = TEMP_DIR / "ai_tutor_input.wav"
TEMP_TTS = TEMP_DIR / "ai_tutor_tts.wav"


# ── Whisper auto-detection ───────────────────────────────────────────────
def _detect_whisper_bin():
    """Locate whisper-cli. Returns a string path or None."""
    # 1) On PATH?
    found = shutil.which("whisper-cli") or shutil.which("whisper")
    if found:
        return found
    # 2) Platform-specific install locations
    candidates = []
    if sys.platform == "win32":
        candidates += [
            r"C:\Program Files\whisper\Release\whisper-cli.exe",
            r"C:\Program Files (x86)\whisper\Release\whisper-cli.exe",
            os.path.expanduser(r"~\whisper\Release\whisper-cli.exe"),
        ]
    elif sys.platform == "darwin":
        candidates += [
            "/opt/homebrew/bin/whisper-cli",
            "/usr/local/bin/whisper-cli",
        ]
    else:  # linux
        candidates += [
            "/usr/local/bin/whisper-cli",
            "/usr/bin/whisper-cli",
        ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def _detect_whisper_model():
    """Locate a ggml-*.bin model. Returns a string path or None."""
    search_dirs = [str(APP_ROOT / "models")]
    if sys.platform == "win32":
        search_dirs += [
            r"C:\Program Files\whisper\models",
            os.path.expanduser(r"~\whisper\models"),
            os.path.expanduser(r"~\.cache\whisper"),
        ]
    elif sys.platform == "darwin":
        search_dirs += [
            os.path.expanduser("~/.cache/whisper"),
            "/opt/homebrew/share/whisper/models",
        ]
    else:
        search_dirs += [
            os.path.expanduser("~/.cache/whisper"),
            "/usr/local/share/whisper/models",
            "/usr/share/whisper/models",
        ]

    preferred_order = ["ggml-small.bin", "ggml-medium.bin", "ggml-base.bin", "ggml-tiny.bin"]
    for d in search_dirs:
        for name in preferred_order:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
        # Any ggml-*.bin in this dir?
        try:
            for f in sorted(os.listdir(d)):
                if f.startswith("ggml-") and f.endswith(".bin"):
                    return os.path.join(d, f)
        except OSError:
            continue
    return None


WHISPER_BIN   = _detect_whisper_bin()
WHISPER_MODEL = _detect_whisper_model()

# Default language — overridden by profile.language at runtime
DEFAULT_LANGUAGE = "en"


# ── Audio / VAD (universal across platforms) ─────────────────────────────
SAMPLE_RATE             = 16000
CHANNELS                = 1
VAD_SILENCE_THRESHOLD   = 0.01
VAD_SILENCE_SECONDS     = 1.5
VAD_MIN_SPEECH_SECONDS  = 0.5


# ── Language + voice presets (merged from languages.py) ──────────────────
WHISPER_LANGUAGES = {
    "en": "English",  "it": "Italian",  "fr": "French",   "de": "German",
    "es": "Spanish",  "pt": "Portuguese", "nl": "Dutch",  "ru": "Russian",
    "pl": "Polish",   "tr": "Turkish",  "ar": "Arabic",   "hi": "Hindi",
    "ja": "Japanese", "zh": "Chinese",  "ko": "Korean",   "vi": "Vietnamese",
    "th": "Thai",     "id": "Indonesian", "uk": "Ukrainian",
}

MODEL_LANGUAGES = {
    "gemma3:4b":   ["en", "it", "fr", "de", "es", "ja", "zh", "ko", "ru"],
    "gemma3:12b":  ["en", "it", "fr", "de", "es", "ja", "zh", "ko", "ru", "pt", "ar"],
    "llama3.1:8b": ["en", "it", "fr", "de", "es", "pt", "nl", "ru", "ja", "zh", "ko"],
    "qwen2.5:7b":  ["en", "it", "fr", "de", "es", "pt", "ru", "ja", "zh", "ko", "ar", "hi", "vi", "th"],
    "mistral:7b":  ["en", "it", "fr", "de", "es"],
    "phi3:14b":    ["en", "it", "fr", "de", "es", "ja", "zh"],
}

TTS_PRESETS = {
    "f5":     [],
    "kokoro": [
        ("af_heart",    "af_heart  (female, warm)"),
        ("af_bella",    "af_bella  (female)"),
        ("af_aoede",    "af_aoede  (female)"),
        ("af_kore",     "af_kore   (female)"),
        ("af_nova",     "af_nova   (female)"),
        ("am_adam",     "am_adam   (male)"),
        ("am_michael",  "am_michael (male)"),
        ("bf_emma",     "bf_emma   (female, British)"),
        ("bf_isabella", "bf_isabella (female, British)"),
        ("bm_george",   "bm_george (male, British)"),
        ("bm_lewis",    "bm_lewis  (male, British)"),
        ("if_sara",     "if_sara   (female, Italian)"),
        ("if_nicola",   "if_nicola (male, Italian)"),
        ("im_nicola",   "im_nicola (male, Italian)"),
        ("im_adam",     "im_adam   (male, Italian)"),
    ],
    "piper":  [],
}


def languages_for_model(model: str):
    """Languages the model speaks, intersected with Whisper's supported set."""
    codes = MODEL_LANGUAGES.get(model, ["en"])
    return [(c, WHISPER_LANGUAGES[c]) for c in codes if c in WHISPER_LANGUAGES]