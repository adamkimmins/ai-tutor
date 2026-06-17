"""
Notes panel — slides out to the right of the main window.
Notes are attached to the active TutorProfile and saved on every keystroke (debounced).
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFrame, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, pyqtSlot
from PyQt6.QtGui import QColor, QTextCharFormat, QFont

# ── Palette (mirrors main_window) ──────────────────────────────────────────
BORDER_LIGHT  = "#1e3060"
BORDER_GLOW   = "#2a4a8a"
ACCENT_BRIGHT = "#4a9eff"
ACCENT_MID    = "#2d6fd4"
ACCENT_DEEP   = "#1a4a9a"
TEXT_PRIMARY  = "#deeeff"
TEXT_MUTED    = "#5a7aaa"
TEXT_DIM      = "#2a3a5a"
GREEN         = "#10d4a0"
AMBER         = "#f0a030"

NOTE_FORMATS = ["Plain", "Markdown", "Flashcards", "Outline", "Vocab List"]


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ── Format templates ────────────────────────────────────────────────────────
FORMAT_TEMPLATES = {
    "Plain":       "",
    "Markdown":    "# Title\n\n## Section\n\n- Point one\n- Point two\n",
    "Flashcards":  "Q: \nA: \n\n---\n\nQ: \nA: \n",
    "Outline":     "I. Main Topic\n   A. Subtopic\n      1. Detail\n",
    "Vocab List":  "word — definition\n\n",
}


class NotesPanel(QWidget):
    def __init__(self, profile_manager):
        super().__init__(None,
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(380)

        self._manager  = profile_manager
        self._profile  = None
        self._visible  = False
        self._dirty    = False

        # Debounce timer — save 800 ms after last keystroke
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(800)
        self._save_timer.timeout.connect(self._save_now)

        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._build()

    # ── Build UI ────────────────────────────────────────────────────────────
    def _build(self):
        root = QWidget(self)
        root.setObjectName("notesroot")
        root.setStyleSheet("""
            #notesroot {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(6,10,28,230),
                    stop:1 rgba(10,18,45,230));
                border-radius: 20px;
                border: 1px solid rgba(60,130,255,80);
            }
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ──
        hdr = QWidget()
        hdr.setFixedHeight(48)
        hdr.setStyleSheet("background:transparent;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 12, 0)
        hl.setSpacing(8)

        close_btn = QPushButton("›")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"""
            QPushButton{{background:{rgba(ACCENT_MID,0.1)};border:1px solid {BORDER_LIGHT};
            border-radius:7px;color:{TEXT_MUTED};font-size:16px;}}
            QPushButton:hover{{background:{rgba(ACCENT_MID,0.22)};color:{TEXT_PRIMARY};}}
        """)
        close_btn.clicked.connect(self.slide_out)

        title = QLabel("Notes")
        title.setStyleSheet(f"color:{TEXT_PRIMARY};font-size:14px;font-weight:500;background:transparent;")

        self._format_combo = QComboBox()
        self._format_combo.addItems(NOTE_FORMATS)
        self._format_combo.setFixedHeight(26)
        self._format_combo.setStyleSheet(f"""
            QComboBox{{
                background:{rgba(ACCENT_MID,0.1)};
                border:1px solid {BORDER_LIGHT};
                border-radius:6px;
                color:{TEXT_MUTED};
                font-size:11px;
                padding:0 8px;
            }}
            QComboBox:hover{{color:{TEXT_PRIMARY};background:{rgba(ACCENT_MID,0.22)};}}
            QComboBox::drop-down{{border:none;width:16px;}}
            QComboBox QAbstractItemView{{
                background:#0d1528;
                color:{TEXT_PRIMARY};
                border:1px solid {BORDER_LIGHT};
                selection-background-color:{ACCENT_MID};
                font-size:11px;
            }}
        """)
        self._format_combo.currentTextChanged.connect(self._on_format_change)

        self._save_indicator = QLabel("●")
        self._save_indicator.setFixedWidth(14)
        self._save_indicator.setStyleSheet(f"color:{TEXT_DIM};font-size:10px;background:transparent;")
        self._save_indicator.setToolTip("Unsaved changes")

        hl.addWidget(close_btn)
        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(self._format_combo)
        hl.addWidget(self._save_indicator)
        layout.addWidget(hdr)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1)
        div.setStyleSheet(f"background:{BORDER_LIGHT};border:none;")
        layout.addWidget(div)

        # ── Profile name label ──
        self._profile_lbl = QLabel("No tutor selected")
        self._profile_lbl.setContentsMargins(16, 6, 16, 4)
        self._profile_lbl.setStyleSheet(
            f"color:{TEXT_MUTED};font-size:10px;letter-spacing:0.05em;background:transparent;"
        )
        layout.addWidget(self._profile_lbl)

        # ── Editor ──
        self._editor = QTextEdit()
        self._editor.setStyleSheet(f"""
            QTextEdit {{
                background:transparent;
                border:none;
                color:{TEXT_PRIMARY};
                font-size:13px;
                font-family: 'Consolas', 'Menlo', monospace;
                padding: 8px 16px;
                selection-background-color:{ACCENT_MID};
            }}
            QScrollBar:vertical{{width:3px;background:transparent;}}
            QScrollBar::handle:vertical{{background:{BORDER_GLOW};border-radius:2px;}}
        """)
        self._editor.setPlaceholderText("Start typing notes…")
        self._editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._editor)

        # ── Footer ──
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setFixedHeight(1)
        div2.setStyleSheet(f"background:{BORDER_LIGHT};border:none;")
        layout.addWidget(div2)

        footer = QWidget()
        footer.setFixedHeight(38)
        footer.setStyleSheet("background:transparent;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 0, 16, 0)

        self._char_lbl = QLabel("0 chars")
        self._char_lbl.setStyleSheet(f"color:{TEXT_DIM};font-size:10px;background:transparent;")

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(22)
        clear_btn.setStyleSheet(f"""
            QPushButton{{background:transparent;border:1px solid {BORDER_LIGHT};
            border-radius:5px;color:{TEXT_MUTED};font-size:10px;padding:0 10px;}}
            QPushButton:hover{{color:{TEXT_PRIMARY};border-color:{rgba(ACCENT_BRIGHT,0.4)};}}
        """)
        clear_btn.clicked.connect(self._clear)

        save_btn = QPushButton("Save  ✓")
        save_btn.setFixedHeight(22)
        save_btn.setStyleSheet(f"""
            QPushButton{{background:{rgba(ACCENT_MID,0.2)};border:1px solid {rgba(ACCENT_BRIGHT,0.35)};
            border-radius:5px;color:{ACCENT_BRIGHT};font-size:10px;padding:0 12px;}}
            QPushButton:hover{{background:{rgba(ACCENT_MID,0.38)};}}
        """)
        save_btn.clicked.connect(self._save_now)

        fl.addWidget(self._char_lbl)
        fl.addStretch()
        fl.addWidget(clear_btn)
        fl.addSpacing(6)
        fl.addWidget(save_btn)
        layout.addWidget(footer)

    # ── Profile management ──────────────────────────────────────────────────
    def load_profile(self, profile):
        """Call when a session starts with a new profile."""
        # Save previous profile's notes first
        if self._profile and self._dirty:
            self._save_now()

        self._profile = profile
        self._profile_lbl.setText(
            f"{profile.name.upper()}  ·  {profile.subject}"
        )

        # Populate editor without triggering save
        self._editor.blockSignals(True)
        self._editor.setPlainText(profile.notes or "")
        self._editor.blockSignals(False)

        self._dirty = False
        self._update_save_indicator(False)
        self._update_char_count()

    # ── Slots ───────────────────────────────────────────────────────────────
    def _on_text_changed(self):
        self._dirty = True
        self._update_save_indicator(True)
        self._update_char_count()
        self._save_timer.start()   # restart debounce

    def _on_format_change(self, fmt: str):
        current = self._editor.toPlainText().strip()
        template = FORMAT_TEMPLATES.get(fmt, "")
        if not current and template:
            self._editor.blockSignals(True)
            self._editor.setPlainText(template)
            self._editor.blockSignals(False)
            self._dirty = True
            self._save_timer.start()

    def _clear(self):
        self._editor.clear()
        self._format_combo.setCurrentIndex(0)

    def _save_now(self):
        if not self._profile:
            return
        self._profile.notes = self._editor.toPlainText()
        self._manager.save(self._profile)
        self._dirty = False
        self._update_save_indicator(False)

    def _update_save_indicator(self, unsaved: bool):
        if unsaved:
            self._save_indicator.setStyleSheet(
                f"color:{AMBER};font-size:10px;background:transparent;"
            )
            self._save_indicator.setToolTip("Unsaved changes")
        else:
            self._save_indicator.setStyleSheet(
                f"color:{GREEN};font-size:10px;background:transparent;"
            )
            self._save_indicator.setToolTip("Saved")

    def _update_char_count(self):
        n = len(self._editor.toPlainText())
        self._char_lbl.setText(f"{n:,} chars")

    # ── Slide animation ─────────────────────────────────────────────────────
    def slide_in(self, anchor):
        """anchor is the main window QRect."""
        self.setFixedHeight(anchor.height())
        # Panel sits immediately to the right of the main window
        end_x = anchor.right()
        y     = anchor.top()
        start = QPoint(end_x + 30, y)
        end   = QPoint(end_x, y)
        self.move(start)
        self.show()
        self.raise_()
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()
        self._visible = True

    def slide_out(self):
        if self._dirty:
            self._save_now()
        self.hide()
        self._visible = False

    def toggle(self, anchor):
        if self._visible:
            self.slide_out()
        else:
            self.slide_in(anchor)

    def reposition(self, anchor):
        if self._visible:
            self.setFixedHeight(anchor.height())
            self.move(anchor.right(), anchor.top())