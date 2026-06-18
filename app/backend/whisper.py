import subprocess
import os
from config import WHISPER_BIN, WHISPER_MODEL, WHISPER_LANGUAGES, DEFAULT_LANGUAGE


def transcribe(wav_path: str) -> str:
    if not os.path.exists(wav_path):
        print(f"[whisper] WAV not found: {wav_path}")
        return ""

    cmd = [
        WHISPER_BIN,
        "-m", WHISPER_MODEL,
        "-f", wav_path,
        "-l", DEFAULT_LANGUAGE,
        "--no-timestamps",
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # suppress all the model loading noise
            timeout=60,
        )
        transcript = result.stdout.decode("utf-8", errors="ignore").strip()

        # Clean up noise markers
        transcript = "\n".join(
            line for line in transcript.splitlines()
            if line.strip() and not line.strip().startswith("[")
        )
        return transcript.strip()

    except subprocess.TimeoutExpired:
        print("[whisper] Timed out")
        return ""
    except Exception as e:
        print(f"[whisper] Error: {e}")
        return ""