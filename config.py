import os

# Whisper
WHISPER_BIN = r"C:\Program Files\whisper\Release\whisper-cli.exe"
WHISPER_MODEL = r"C:\Program Files\whisper\models\ggml-small.bin"
WHISPER_LANGUAGE = "it"

# Audio capture
SAMPLE_RATE = 16000
CHANNELS = 1

# VAD
VAD_SILENCE_THRESHOLD = 0.01
VAD_SILENCE_SECONDS = 1.5
VAD_MIN_SPEECH_SECONDS = 0.5

# Temp files
TEMP_WAV = os.path.join(os.environ["TEMP"], "italian_tutor_input.wav")
TEMP_TTS = os.path.join(os.environ["TEMP"], "italian_tutor_tts.wav")