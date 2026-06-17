"""
Always-on microphone capture with simple energy-based VAD.
Runs in its own thread. Calls a callback when a speech chunk is ready.
"""

import threading
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import time
import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from config import SAMPLE_RATE, CHANNELS, VAD_SILENCE_THRESHOLD, VAD_SILENCE_SECONDS, VAD_MIN_SPEECH_SECONDS, TEMP_WAV


class Listener(threading.Thread):
    def __init__(self, on_speech_ready, on_listening_state=None):
        """
        on_speech_ready(wav_path: str)  — called when a speech chunk is captured
        on_listening_state(bool)        — optional, called when listening starts/stops
        """
        super().__init__(daemon=True)
        self.on_speech_ready = on_speech_ready
        self.on_listening_state = on_listening_state
        self.enabled = True          # can be toggled by GUI switch
        self._stop_event = threading.Event()
        self._audio_buffer = []
        self._in_speech = False
        self._silence_start = None

    def stop(self):
        self._stop_event.set()

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False
        self._audio_buffer = []
        self._in_speech = False

    def _is_speech(self, chunk: np.ndarray) -> bool:
        energy = np.sqrt(np.mean(chunk.astype(np.float32) ** 2)) / 32768.0
        return energy > VAD_SILENCE_THRESHOLD

    def _save_and_dispatch(self):
        if not self._audio_buffer:
            return
        audio = np.concatenate(self._audio_buffer, axis=0)
        duration = len(audio) / SAMPLE_RATE
        if duration < VAD_MIN_SPEECH_SECONDS:
            self._audio_buffer = []
            return
        wav.write(TEMP_WAV, SAMPLE_RATE, audio)
        self._audio_buffer = []
        if self.on_listening_state:
            self.on_listening_state(False)  # signal: processing, not listening
        self.on_speech_ready(TEMP_WAV)

    def run(self):
        block_size = int(SAMPLE_RATE * 0.1)  # 100ms chunks

        def callback(indata, frames, time_info, status):
            if not self.enabled:
                return
            chunk = indata.copy()
            speaking = self._is_speech(chunk)

            if speaking:
                if not self._in_speech:
                    self._in_speech = True
                    self._silence_start = None
                    if self.on_listening_state:
                        self.on_listening_state(True)
                self._audio_buffer.append(chunk)
            else:
                if self._in_speech:
                    self._audio_buffer.append(chunk)  # include trailing silence
                    if self._silence_start is None:
                        self._silence_start = time.time()
                    elif time.time() - self._silence_start >= VAD_SILENCE_SECONDS:
                        self._in_speech = False
                        self._save_and_dispatch()

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=block_size,
            callback=callback,
        ):
            while not self._stop_event.is_set():
                time.sleep(0.05)