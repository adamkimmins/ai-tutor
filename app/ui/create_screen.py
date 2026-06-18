"""
Create / edit a tutor profile.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QComboBox,
    QFileDialog, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from profile_manager import TutorProfile, ProfileManager

DARK_BG      = "#080d1a"
BORDER       = "#1e3060"
ACCENT       = "#4a9eff"
ACCENT2      = "#2d6fd4"
TEXT_PRIMARY = "#deeeff"
TEXT_MUTED   = "#5a7aaa"
TEXT_DIM     = "#2a3a5a"
INPUT_BG     = "rgba(10,25,60,0.8)"


def rgba(h, a):
    h = h.lstrip("#")
    r,g,b = int(h[:2],16),int(h[2:4],16),int(h[4:],16)
    return f"rgba({r},{g},{b},{a})"


FIELD_STYLE = f"""
    QLineEdit, QTextEdit, QComboBox {{
        background: {INPUT_BG};
        border: 1px solid {BORDER};
        border-radius: 8px;
        color: {TEXT_PRIMARY};
        font-size: 13px;
        padding: 6px 10px;
        selection-background-color: {ACCENT2};
    }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
        border: 1px solid {ACCENT};
    }}
    QComboBox::drop-down {{ border: none; }}
    QComboBox::down-arrow {{ color: {TEXT_MUTED}; }}
    QComboBox QAbstractItemView {{
        background: #0d1528;
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        selection-background-color: {ACCENT2};
    }}
"""


class CreateScreen(QWidget):
    saved    = pyqtSignal(object)   # TutorProfile
    canceled = pyqtSignal()

    def __init__(self, manager: ProfileManager, existing: TutorProfile = None):
        super().__init__()
        self.manager  = manager
        self.existing = existing
        self.setStyleSheet("background:transparent;")
        self._build()
        if existing:
            self._populate(existing)

    def _label(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(f"color:{TEXT_MUTED};font-size:11px;letter-spacing:0.04em;background:transparent;")
        return l

    def _divider(self):
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setFixedHeight(1)
        f.setStyleSheet(f"background:{BORDER};border:none;")
        return f

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        outer.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet("background:transparent;")
        hl  = QHBoxLayout(hdr)
        hl.setContentsMargins(16,0,16,0)
        back = QPushButton("‹ Back")
        back.setStyleSheet(f"background:transparent;border:none;color:{TEXT_MUTED};font-size:13px;")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(self.canceled)
        title = QLabel("New Tutor" if not self.existing else "Edit Tutor")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{TEXT_PRIMARY};font-size:15px;font-weight:500;background:transparent;")
        hl.addWidget(back)
        hl.addStretch()
        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(QLabel("     "))  # spacer to center title
        outer.addWidget(hdr)
        outer.addWidget(self._divider())

        # Scrollable form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        form_widget = QWidget()
        form_widget.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(form_widget)
        layout.setContentsMargins(20,16,20,20)
        layout.setSpacing(12)
        scroll.setWidget(form_widget)
        outer.addWidget(scroll)

        self.setStyleSheet(FIELD_STYLE + "background:transparent;")

        # ── Basic info ──
        layout.addWidget(self._label("TUTOR NAME"))
        self.name_field = QLineEdit()
        self.name_field.setPlaceholderText("e.g. Italian Tutor")
        layout.addWidget(self.name_field)

        layout.addWidget(self._label("SUBJECT"))
        self.subject_field = QLineEdit()
        self.subject_field.setPlaceholderText("e.g. Italian Language, Calculus, History")
        layout.addWidget(self.subject_field)

        layout.addWidget(self._label("SYSTEM PROMPT"))
        self.prompt_field = QTextEdit()
        self.prompt_field.setFixedHeight(100)
        self.prompt_field.setPlaceholderText(
            "Describe how the tutor should behave, what language to use, tone, etc."
        )
        layout.addWidget(self.prompt_field)

       # ── LLM ──
        layout.addWidget(self._divider())
        # layout.addWidget(self._label("OLLAMA MODEL"))
        self.model_field = QLineEdit()
        self.model_field.setPlaceholderText("e.g. gemma3:4b, llama3.2:3b, qwen3:8b")
        layout.addWidget(self.model_field)

        # ── Speech ──
        layout.addWidget(self._divider())
        layout.addWidget(self._label("STT LANGUAGE CODE"))
        self.lang_field = QLineEdit()
        self.lang_field.setPlaceholderText("e.g. it, en, fr, de, ja")
        layout.addWidget(self.lang_field)

        layout.addWidget(self._label("TTS ENGINE"))
        self.tts_combo = QComboBox()
        self.tts_combo.addItems(["f5", "kokoro", "piper"])
        self.tts_combo.currentTextChanged.connect(self._on_tts_change)
        layout.addWidget(self.tts_combo)

        layout.addWidget(self._label("TTS VOICE"))
        self.voice_field = QLineEdit()
        self.voice_field.setPlaceholderText("Kokoro: if_sara / im_nicola — Piper: path to .onnx")
        layout.addWidget(self.voice_field)

        layout.addWidget(self._label("REFERENCE AUDIO (F5 voice cloning — optional)"))
        ref_row = QHBoxLayout()
        self.ref_audio_field = QLineEdit()
        self.ref_audio_field.setPlaceholderText("Path to .wav reference file")
        browse = QPushButton("Browse")
        browse.setFixedWidth(70)
        browse.setStyleSheet(f"""
            QPushButton {{
                background:{rgba(ACCENT2,0.2)};
                border:1px solid {BORDER};
                border-radius:7px;
                color:{TEXT_MUTED};
                font-size:12px;
                padding:4px;
            }}
            QPushButton:hover{{color:{TEXT_PRIMARY};background:{rgba(ACCENT,0.25)};}}
        """)
        browse.clicked.connect(self._browse_ref)
        ref_row.addWidget(self.ref_audio_field)
        ref_row.addWidget(browse)
        layout.addLayout(ref_row)

        layout.addStretch()

        # ── Save button ──
        outer.addWidget(self._divider())
        btn_row = QWidget()
        btn_row.setStyleSheet("background:transparent;")
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(20,10,20,16)
        save = QPushButton("Save Tutor")
        save.setFixedHeight(40)
        save.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {ACCENT},stop:1 {ACCENT2});
                border:none;
                border-radius:10px;
                color:white;
                font-size:14px;
                font-weight:500;
            }}
            QPushButton:hover{{opacity:0.85;}}
        """)
        save.clicked.connect(self._save)
        bl.addWidget(save)
        outer.addWidget(btn_row)

    def _on_tts_change(self, engine: str):
        if engine == "f5":
            self.voice_field.setPlaceholderText("Leave blank to use default F5 voice")
        elif engine == "kokoro":
            self.voice_field.setPlaceholderText("if_sara (female) or im_nicola (male)")
        elif engine == "piper":
            self.voice_field.setPlaceholderText("Full path to .onnx voice file")

    def _browse_ref(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select reference audio", "", "Audio files (*.wav *.mp3 *.flac)"
        )
        if path:
            self.ref_audio_field.setText(path)

    def _populate(self, p: TutorProfile):
        self.name_field.setText(p.name)
        self.subject_field.setText(p.subject)
        self.prompt_field.setPlainText(p.system_prompt)
        self.model_field.setText(p.llm_model)
        self.lang_field.setText(p.language)
        idx = self.tts_combo.findText(p.tts_engine)
        if idx >= 0:
            self.tts_combo.setCurrentIndex(idx)
        self.voice_field.setText(p.tts_voice)
        self.ref_audio_field.setText(p.tts_ref_audio)

    def _save(self):
        name = self.name_field.text().strip()
        if not name:
            self.name_field.setPlaceholderText("⚠ Name required")
            return

        p = self.existing or TutorProfile(
            name="", subject="", system_prompt="", language="en"
        )
        p.name           = name
        p.subject        = self.subject_field.text().strip() or name
        p.system_prompt  = self.prompt_field.toPlainText().strip()
        p.llm_provider  = "ollama"
        p.llm_model     = self.model_field.text().strip() or "gemma3:4b"
        p.llm_url       = "http://localhost:11434"
        p.llm_api_key   = ""
        p.language       = self.lang_field.text().strip() or "en"
        p.tts_engine     = self.tts_combo.currentText()
        p.tts_voice      = self.voice_field.text().strip()
        p.tts_ref_audio  = self.ref_audio_field.text().strip()

        self.manager.save(p)
        self.saved.emit(p)