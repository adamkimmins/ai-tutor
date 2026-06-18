"""
F5-TTS backend — best prosody, voice cloning support.
"""

import re
import time
import threading
import numpy as np
import sounddevice as sd
from app.backend.tts import TTSBackend
from profile_manager import TutorProfile

SAMPLE_RATE = 24000


class F5Backend(TTSBackend):
    def __init__(self, profile: TutorProfile):
        super().__init__(profile)
        self._tts = None
        self._lock = threading.Lock()

    def load(self):
        if self._tts is None:
            print("[f5-tts] Loading model...")
            try:
                from f5_tts.api import F5TTS
                self._tts = F5TTS()
                print("[f5-tts] Ready.")
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[f5-tts] FAILED to load: {e}")
                self._tts = None

    def _synthesize(self, text: str) -> np.ndarray | None:
        if not text.strip():
            return None
        try:
            ref_audio = self.profile.tts_ref_audio or None
            wav, sr, _ = self._tts.infer(
                ref_file=ref_audio,
                ref_text="",
                gen_text=text,
                show_info=False,
            )
            # Resample to SAMPLE_RATE if needed
            if sr != SAMPLE_RATE:
                import librosa
                wav = librosa.resample(wav, orig_sr=sr, target_sr=SAMPLE_RATE)
            return wav.astype(np.float32)
        except Exception as e:
            print(f"[f5-tts] Synthesis error: {e}")
            return None

    def _play(self, audio: np.ndarray, interrupt_event) -> bool:
        try:
            from app.ui.main_window import signals as ui_signals
            has_ui = True
        except ImportError:
            has_ui = False

        CHUNK = 2048
        sd.play(audio, SAMPLE_RATE)
        pos = 0
        while pos < len(audio):
            end    = min(pos + CHUNK, len(audio))
            chunk  = np.abs(audio[pos:end])
            if has_ui and len(chunk) > 0:
                n      = 36
                step   = max(1, len(chunk) // n)
                levels = np.array([chunk[i*step:min((i+1)*step, len(chunk))].mean() for i in range(n)])
                mx     = levels.max()
                if mx > 0:
                    levels /= mx
                ui_signals.set_waveform.emit(levels)
            pos += CHUNK
            time.sleep(CHUNK / SAMPLE_RATE * 0.8)
            if interrupt_event.is_set():
                sd.stop()
                return True
        sd.wait()
        return False

    def speak_stream(self, token_iterator, interrupt_event) -> bool:
        self.load()
        buffer   = ""
        sent_end = re.compile(r'(?<=[.!?])\s+')
        interrupted = False

        def flush(sentence: str) -> bool:
            sentence = sentence.strip()
            if not sentence:
                return False
            try:
                audio = self._synthesize(sentence)
                if audio is not None:
                    return self._play(audio, interrupt_event)
            except Exception as e:
                print(f"[f5-tts] flush error: {e}")
                import traceback; traceback.print_exc()
            return False

        try:
            with self._lock:
                for token in token_iterator:
                    if interrupt_event.is_set():
                        interrupted = True
                        break
                    buffer += token
                    parts   = sent_end.split(buffer)
                    if len(parts) > 1:
                        for s in parts[:-1]:
                            if flush(s):
                                interrupted = True
                                break
                        if interrupted:
                            break
                        buffer = parts[-1]

                if not interrupted and buffer.strip():
                    flush(buffer)
        except Exception as e:
            print(f"[f5-tts] speak_stream error: {e}")
            import traceback; traceback.print_exc()

        return interrupted
    # def speak_stream(self, token_iterator, interrupt_event) -> bool:
    #     self.load()
    #     if self._tts is None:
    #         print("[f5-tts] Skipping, model not loaded")
    #         return False
    #     buffer   = ""
    #     sent_end = re.compile(r'(?<=[.!?])\s+')
    #     interrupted = False

    #     def flush(sentence: str) -> bool:
    #         sentence = sentence.strip()
    #         if not sentence:
    #             return False
    #         audio = self._synthesize(sentence)
    #         if audio is not None:
    #             return self._play(audio, interrupt_event)
    #         return False

    #     with self._lock:
    #         for token in token_iterator:
    #             if interrupt_event.is_set():
    #                 interrupted = True
    #                 break
    #             buffer += token
    #             parts   = sent_end.split(buffer)
    #             if len(parts) > 1:
    #                 for s in parts[:-1]:
    #                     if flush(s):
    #                         interrupted = True
    #                         break
    #                 if interrupted:
    #                     break
    #                 buffer = parts[-1]

    #         if not interrupted and buffer.strip():
    #             flush(buffer)

    #     return interrupted