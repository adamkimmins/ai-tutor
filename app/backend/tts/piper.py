import subprocess
import threading
import sounddevice as sd
import scipy.io.wavfile as wav
import tempfile
import os
from app.backend.tts import TTSBackend


class PiperBackend(TTSBackend):
    def speak_stream(self, token_iterator, interrupt_event) -> bool:
        import re
        text     = "".join(token_iterator)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            if interrupt_event.is_set():
                return True
            self._speak_sentence(sentence, interrupt_event)
        return False

    def _speak_sentence(self, text: str, interrupt_event):
        if not text.strip():
            return
        voice = self.profile.tts_voice  # path to .onnx
        if not voice or not os.path.exists(voice):
            print("[piper] No voice file configured")
            return
        tmp = tempfile.mktemp(suffix=".wav")
        try:
            subprocess.run(
                ["piper.exe", "--model", voice, "--output_file", tmp],
                input=text.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
            rate, data = wav.read(tmp)
            sd.play(data, rate)
            sd.wait()
        except Exception as e:
            print(f"[piper] Error: {e}")
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)