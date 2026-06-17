import re
import time
import warnings
import threading
import numpy as np
import sounddevice as sd
from app.backend.tts import TTSBackend

SAMPLE_RATE = 24000
_pipeline   = None
_lock       = threading.Lock()


class KokoroBackend(TTSBackend):
    def load(self):
        global _pipeline
        if _pipeline is None:
            print("[kokoro] Loading pipeline...")
            from kokoro import KPipeline
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                _pipeline = KPipeline(lang_code=self.profile.language or 'it',
                                      repo_id='hexgrad/Kokoro-82M')
            print("[kokoro] Ready.")

    def speak_stream(self, token_iterator, interrupt_event) -> bool:
        self.load()
        voice    = self.profile.tts_voice or 'if_sara'
        buffer   = ""
        sent_end = re.compile(r'(?<=[.!?])\s+')
        interrupted = False

        try:
            from app.ui.main_window import signals as ui_signals
            has_ui = True
        except ImportError:
            has_ui = False

        def play_chunks(generator) -> bool:
            CHUNK = 2048
            for _, _, audio in generator:
                if audio is None or len(audio) == 0:
                    continue
                sd.play(audio, SAMPLE_RATE)
                pos = 0
                while pos < len(audio):
                    end   = min(pos + CHUNK, len(audio))
                    chunk = np.abs(audio[pos:end])
                    if has_ui and len(chunk):
                        n      = 36
                        step   = max(1, len(chunk) // n)
                        levels = np.array([chunk[i*step:min((i+1)*step,len(chunk))].mean() for i in range(n)])
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
                if interrupt_event.is_set():
                    sd.stop()
                    return True
            return False

        def flush(sentence: str) -> bool:
            sentence = sentence.strip()
            if not sentence:
                return False
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                gen = _pipeline(sentence, voice=voice)
            return play_chunks(gen)

        with _lock:
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

        return interrupted