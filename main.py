import sys
import queue
import threading
import argparse
import numpy as np

sys.path.insert(0, ".")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from profile_manager import ProfileManager, TutorProfile
from app.ui.main_window import MainWindow, signals
from app.backend.whisper import transcribe
from app.backend.llm import LLMClient
from app.backend.tts import get_tts_backend

manager         = ProfileManager()
llm_client      = None
tts_backend     = None
state_lock      = threading.Lock()
_state          = "loading"
interrupt_event = threading.Event()
input_queue     = queue.Queue()
listener        = None
_mic_on         = True
window          = None


def set_state(s: str):
    global _state
    with state_lock:
        _state = s
    signals.update_status.emit(s)


def get_state() -> str:
    with state_lock:
        return _state


def run_pipeline(transcript: str):
    if not transcript or not llm_client or not tts_backend:
        return
    signals.add_user_msg.emit(transcript)
    set_state("thinking")
    signals.start_tutor_msg.emit()
    signals.waveform_active.emit(False)

    token_queue = queue.Queue()

    def llm_worker():
        def on_token(t):
            token_queue.put(t)
            signals.append_tutor_token.emit(t)
        llm_client.chat(transcript, on_token=on_token)
        token_queue.put(None)

    t = threading.Thread(target=llm_worker, daemon=True)
    t.start()

    def token_iter():
        while True:
            tok = token_queue.get()
            if tok is None: break
            yield tok

    if listener: listener.disable()
    set_state("speaking")
    signals.waveform_active.emit(True)
    interrupted = tts_backend.speak_stream(token_iter(), interrupt_event)
    interrupt_event.clear()
    signals.waveform_active.emit(False)
    if interrupted:
        tts_backend.speak_stream(iter(["Hm?"]), threading.Event())
    if listener and _mic_on: listener.enable()
    t.join()
    set_state("listening" if _mic_on else "off")


def on_speech(wav_path: str):
    transcript = transcribe(wav_path)
    if not transcript: return
    if get_state() == "speaking": interrupt_event.set()
    input_queue.put(transcript)


def pipeline_worker():
    while True:
        t = input_queue.get()
        run_pipeline(t)
        input_queue.task_done()


def on_mic_toggle(on: bool):
    global _mic_on
    _mic_on = on
    if listener:
        if on: listener.enable(); set_state("listening")
        else:  listener.disable(); set_state("off")


def activate_profile(profile: TutorProfile):
    global llm_client, tts_backend
    llm_client  = LLMClient(profile)
    tts_backend = get_tts_backend(profile)

    def load():
        try:
            signals.component_loaded.emit("whisper")
            tts_backend.load()
            signals.component_loaded.emit("kokoro")
            signals.component_loaded.emit("ollama")
            signals.all_loaded.emit()
        except Exception as e:
            import traceback; traceback.print_exc()
            signals.all_loaded.emit()

    threading.Thread(target=load, daemon=True).start()

def start_mic(session):
    global listener
    from app.backend.listener import Listener
    listener = Listener(on_speech_ready=on_speech)
    listener.start()
    session.connect_mic_toggle(on_mic_toggle)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow(manager)

    # Wire profile launch
    def on_launch(profile: TutorProfile):
        activate_profile(profile)
        QTimer.singleShot(400, lambda: start_mic(window.get_session()))

    signals.launch_session.connect(on_launch)
    window.show()

    threading.Thread(target=pipeline_worker, daemon=True).start()

    sys.exit(app.exec())