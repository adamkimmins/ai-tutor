"""
AI Tutor — Main GUI Window v4
Single frameless window, internal screen stack, glass blue aesthetic
"""

import math
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSignal, QObject, pyqtSlot, QRect, QPoint
)
from PyQt6.QtGui import (
    QPainter, QColor, QLinearGradient, QBrush,
    QPen, QMouseEvent, QRadialGradient
)

# ── Palette ────────────────────────────────────────────────────────────────
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
PURPLE        = "#8a60ff"
RED           = "#ff4a6a"
USER_BUBBLE   = "#0d2050"
TUTOR_BUBBLE  = "#0a1830"
BUBBLE_USER_BORDER  = "#2a4a9a"
BUBBLE_TUTOR_BORDER = "#1a2a4a"


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    return f"rgba({r},{g},{b},{alpha})"


# ── Signals ────────────────────────────────────────────────────────────────
class Signals(QObject):
    update_status      = pyqtSignal(str)
    add_user_msg       = pyqtSignal(str)
    start_tutor_msg    = pyqtSignal()
    append_tutor_token = pyqtSignal(str)
    set_waveform       = pyqtSignal(object)
    waveform_active    = pyqtSignal(bool)
    clear_chat         = pyqtSignal()
    component_loaded   = pyqtSignal(str)
    all_loaded         = pyqtSignal()
    show_select        = pyqtSignal()
    show_create        = pyqtSignal()
    launch_session     = pyqtSignal(object)   # TutorProfile

signals = Signals()


# ── Waveform ───────────────────────────────────────────────────────────────
class WaveformWidget(QWidget):
    N = 36

    def __init__(self):
        super().__init__()
        self.setFixedHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.levels  = np.zeros(self.N)
        self.targets = np.zeros(self.N)
        self._active = False
        self._phase  = 0.0
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(33)

    def push_levels(self, arr):
        n = min(len(arr), self.N)
        self.targets[:n] = np.clip(arr[:n], 0, 1)

    def set_active(self, v: bool):
        self._active = v
        if not v:
            self.targets[:] = 0

    def _tick(self):
        self._phase += 0.055
        s = 0.28 if self._active else 0.15
        self.levels += (self.targets - self.levels) * s
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        bw   = 3
        gap  = (W - self.N * bw) / (self.N + 1)
        for i in range(self.N):
            x    = gap + i * (bw + gap)
            lv   = float(self.levels[i])
            idle = 2.5 + math.sin(self._phase + i * 0.38) * 1.4
            bh   = max(idle, lv * (H - 12)) if self._active else idle
            y    = (H - bh) / 2
            g = QLinearGradient(0, y, 0, y + bh)
            if self._active:
                g.setColorAt(0, QColor(ACCENT_BRIGHT))
                g.setColorAt(1, QColor(ACCENT_DEEP))
            else:
                g.setColorAt(0, QColor(TEXT_DIM))
                g.setColorAt(1, QColor(TEXT_DIM))
            p.setBrush(QBrush(g))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(int(x), int(y), bw, max(2, int(bh)), 2, 2)


# ── Status ─────────────────────────────────────────────────────────────────
STATE_META = {
    "ready":      (GREEN,         "●"),
    "listening":  (ACCENT_BRIGHT, "◉"),
    "thinking":   (AMBER,         "◌"),
    "speaking":   (PURPLE,        "◆"),
    "off":        (TEXT_DIM,      "○"),
    "loading":    (TEXT_MUTED,    "◌"),
}

class StatusWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(32)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(6)
        self.dot = QLabel("●")
        self.dot.setFixedWidth(14)
        self.lbl = QLabel("loading")
        for w, sz, c in [(self.dot,12,TEXT_MUTED),(self.lbl,12,TEXT_MUTED)]:
            w.setStyleSheet(f"color:{c};font-size:{sz}px;background:transparent;")
        layout.addWidget(self.dot)
        layout.addWidget(self.lbl)
        layout.addStretch()

    def set_state(self, state: str):
        color, symbol = STATE_META.get(state, (TEXT_MUTED, "●"))
        self.dot.setText(symbol)
        self.dot.setStyleSheet(f"color:{color};font-size:12px;background:transparent;")
        self.lbl.setText(state)
        self.lbl.setStyleSheet(f"color:{color};font-size:12px;font-weight:500;background:transparent;")


# ── Mic toggle ─────────────────────────────────────────────────────────────
class MicToggle(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(44)
        self.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._lbl_l = QLabel("mic")
        self._lbl_l.setStyleSheet(f"color:{TEXT_MUTED};font-size:12px;background:transparent;")

        self._btn = QPushButton()
        self._btn.setFixedSize(48, 26)
        self._btn.setCheckable(True)
        self._btn.setChecked(True)
        self._btn.toggled.connect(self._on_toggled)
        self._update_style(True)

        self._lbl_r = QLabel("on")
        self._lbl_r.setStyleSheet(f"color:{TEXT_PRIMARY};font-size:12px;background:transparent;")

        layout.addWidget(self._lbl_l)
        layout.addWidget(self._btn)
        layout.addWidget(self._lbl_r)

    def _update_style(self, on: bool):
        c = ACCENT_BRIGHT if on else TEXT_DIM
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {c}, stop:1 {ACCENT_MID if on else TEXT_DIM});
                border-radius:13px; border:none;
            }}
        """)

    def _on_toggled(self, on: bool):
        self._update_style(on)
        self._lbl_r.setText("on" if on else "off")
        self._lbl_r.setStyleSheet(
            f"color:{TEXT_PRIMARY};font-size:12px;background:transparent;" if on
            else f"color:{TEXT_MUTED};font-size:12px;background:transparent;"
        )
        self.toggled.emit(on)

    def set_on(self, on: bool):
        self._btn.blockSignals(True)
        self._btn.setChecked(on)
        self._btn.blockSignals(False)
        self._update_style(on)


# ── Chat bubble ────────────────────────────────────────────────────────────
class ChatBubble(QWidget):
    def __init__(self, is_user: bool):
        super().__init__()
        self._text = ""
        self.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8,3,8,3)
        layout.setSpacing(2)

        who = QLabel("you" if is_user else "tutor")
        who.setStyleSheet(f"color:{TEXT_DIM};font-size:10px;background:transparent;")
        if is_user:
            who.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.bubble = QLabel("..." if not is_user else "")
        self.bubble.setWordWrap(True)
        self.bubble.setStyleSheet(f"""
            background:{USER_BUBBLE if is_user else TUTOR_BUBBLE};
            color:{TEXT_PRIMARY};
            border:1px solid {BUBBLE_USER_BORDER if is_user else BUBBLE_TUTOR_BORDER};
            border-radius:10px;
            padding:7px 11px;
            font-size:13px;
        """)
        if is_user:
            self.bubble.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(who)
        layout.addWidget(self.bubble)

    def set_text(self, t: str):
        self._text = t
        self.bubble.setText(t)

    def append_token(self, t: str):
        self._text += t
        self.bubble.setText(self._text)


# ── Loading panel ──────────────────────────────────────────────────────────
class LoadingPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20,14,20,14)
        layout.setSpacing(8)
        t = QLabel("Starting up…")
        t.setStyleSheet(f"color:{TEXT_PRIMARY};font-size:13px;font-weight:500;background:transparent;")
        layout.addWidget(t)
        self._rows = {}
        for key, name in [("whisper","Whisper STT"),("kokoro","F5 TTS"),("ollama","Ollama LLM")]:
            row = QHBoxLayout()
            dot = QLabel("◦")
            dot.setFixedWidth(16)
            dot.setStyleSheet(f"color:{TEXT_DIM};font-size:14px;background:transparent;")
            lbl = QLabel(name)
            lbl.setStyleSheet(f"color:{TEXT_MUTED};font-size:12px;background:transparent;")
            row.addWidget(dot); row.addWidget(lbl); row.addStretch()
            layout.addLayout(row)
            self._rows[key] = (dot, lbl)

    def mark(self, key: str):
        if key in self._rows:
            d, l = self._rows[key]
            d.setText("✓")
            d.setStyleSheet(f"color:{GREEN};font-size:12px;background:transparent;")
            l.setStyleSheet(f"color:{TEXT_PRIMARY};font-size:12px;background:transparent;")

# ── Chat slide panel ───────────────────────────────────────────────────────
class ChatPanel(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool |
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(380)
        self._visible = False

        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        root = QWidget(self)
        root.setObjectName("chatroot")
        root.setStyleSheet("""
            #chatroot {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(6,10,28,230),
                    stop:1 rgba(8,15,40,230));
                border-radius: 20px;
                border: 1px solid rgba(60,130,255,80);
            }
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        outer.addWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)

        hdr = QWidget()
        hdr.setFixedHeight(48)
        hdr.setStyleSheet("background:transparent;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16,0,12,0)

        title = QLabel("Conversation Log")
        title.setStyleSheet(f"color:{TEXT_PRIMARY};font-size:14px;font-weight:500;background:transparent;")

        clear_btn = QPushButton("🗑")
        clear_btn.setFixedSize(28,28)
        clear_btn.setStyleSheet(f"""
            QPushButton{{background:{rgba(ACCENT_MID,0.1)};border:1px solid {BORDER_LIGHT};
            border-radius:7px;color:{TEXT_MUTED};font-size:13px;}}
            QPushButton:hover{{background:{rgba(ACCENT_MID,0.22)};color:{TEXT_PRIMARY};}}
        """)
        clear_btn.clicked.connect(lambda: signals.clear_chat.emit())

        close_btn = QPushButton("‹")
        close_btn.setFixedSize(28,28)
        close_btn.setStyleSheet(f"""
            QPushButton{{background:{rgba(ACCENT_MID,0.1)};border:1px solid {BORDER_LIGHT};
            border-radius:7px;color:{TEXT_MUTED};font-size:16px;}}
            QPushButton:hover{{background:{rgba(ACCENT_MID,0.22)};color:{TEXT_PRIMARY};}}
        """)
        close_btn.clicked.connect(self.slide_out)

        hl.addWidget(title); hl.addStretch()
        hl.addWidget(clear_btn); hl.addSpacing(6); hl.addWidget(close_btn)
        layout.addWidget(hdr)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1)
        div.setStyleSheet(f"background:{BORDER_LIGHT};border:none;")
        layout.addWidget(div)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea{{background:transparent;border:none;}}
            QScrollBar:vertical{{width:3px;background:transparent;}}
            QScrollBar::handle:vertical{{background:{BORDER_GLOW};border-radius:2px;}}
        """)
        self.inner = QWidget()
        self.inner.setStyleSheet("background:transparent;")
        self.chat_layout = QVBoxLayout(self.inner)
        self.chat_layout.setContentsMargins(10,10,10,10)
        self.chat_layout.setSpacing(4)
        self.chat_layout.addStretch()
        scroll.setWidget(self.inner)
        self._scroll = scroll
        layout.addWidget(scroll)

        self._active_bubble = None

        signals.add_user_msg.connect(self._add_user)
        signals.start_tutor_msg.connect(self._start_tutor)
        signals.append_tutor_token.connect(self._append_token)
        signals.clear_chat.connect(self._clear)

    def slide_in(self, anchor: QRect):
        self.setFixedHeight(anchor.height())
        end_x = anchor.right()
        y     = anchor.top()
        start = QPoint(end_x - 30, y)
        end   = QPoint(end_x, y)
        self.move(start)
        self.show()
        self.raise_()
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()
        self._visible = True

    def slide_out(self):
        self.hide()
        self._visible = False

    def toggle(self, anchor: QRect):
        if self._visible:
            self.slide_out()
        else:
            self.slide_in(anchor)

    def reposition(self, anchor: QRect):
        if self._visible:
            self.setFixedHeight(anchor.height())
            self.move(anchor.right(), anchor.top())

    def _scroll_bottom(self):
        QTimer.singleShot(30, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()))

    @pyqtSlot(str)
    def _add_user(self, text: str):
        b = ChatBubble(True); b.set_text(text)
        self.chat_layout.insertWidget(self.chat_layout.count()-1, b)
        self._scroll_bottom()

    @pyqtSlot()
    def _start_tutor(self):
        b = ChatBubble(False)
        self.chat_layout.insertWidget(self.chat_layout.count()-1, b)
        self._active_bubble = b
        self._scroll_bottom()

    @pyqtSlot(str)
    def _append_token(self, token: str):
        if self._active_bubble:
            self._active_bubble.append_token(token)
            self._scroll_bottom()

    @pyqtSlot()
    def _clear(self):
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._active_bubble = None


# ── Select screen ──────────────────────────────────────────────────────────
class SelectScreen(QWidget):
    profile_selected = pyqtSignal(object)
    create_new       = pyqtSignal()

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.setStyleSheet("background:transparent;")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20,24,20,20)
        layout.setSpacing(14)

        title = QLabel("Choose a Tutor")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{TEXT_PRIMARY};font-size:18px;font-weight:500;background:transparent;")
        layout.addWidget(title)

        sub = QLabel("Select an existing tutor or create a new one")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color:{TEXT_MUTED};font-size:12px;background:transparent;")
        layout.addWidget(sub)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        self._cards = QVBoxLayout(inner)
        self._cards.setSpacing(8)
        self._cards.setContentsMargins(0,0,0,0)
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        self._populate()

        new_btn = QPushButton("+ New Tutor")
        new_btn.setFixedHeight(40)
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setStyleSheet(f"""
            QPushButton{{background:{rgba(ACCENT_MID,0.15)};border:1px solid {rgba(ACCENT_BRIGHT,0.4)};
            border-radius:10px;color:{ACCENT_BRIGHT};font-size:13px;font-weight:500;}}
            QPushButton:hover{{background:{rgba(ACCENT_MID,0.28)};}}
        """)
        new_btn.clicked.connect(self.create_new)
        layout.addWidget(new_btn)

    def _populate(self):
        while self._cards.count():
            item = self._cards.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        for profile in self.manager.list_profiles():
            card = self._make_card(profile)
            self._cards.addWidget(card)
        self._cards.addStretch()

    def _make_card(self, profile):
        card = QWidget()
        card.setFixedHeight(72)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(f"""
            QWidget{{background:{rgba(ACCENT_MID,0.1)};border:1px solid {BORDER_LIGHT};border-radius:12px;}}
            QWidget:hover{{background:{rgba(ACCENT_BRIGHT,0.18)};border:1px solid {rgba(ACCENT_BRIGHT,0.5)};}}
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16,0,16,0)

        icon = QLabel(profile.subject[0].upper())
        icon.setFixedSize(40,40)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {ACCENT_BRIGHT},stop:1 {ACCENT_MID});
            border-radius:10px;color:white;font-size:16px;font-weight:500;border:none;
        """)

        col = QVBoxLayout()
        col.setSpacing(2)
        name = QLabel(profile.name)
        name.setStyleSheet(f"color:{TEXT_PRIMARY};font-size:14px;font-weight:500;background:transparent;border:none;")
        sub = QLabel(f"{profile.subject} · {profile.llm_model}")
        sub.setStyleSheet(f"color:{TEXT_MUTED};font-size:11px;background:transparent;border:none;")
        col.addWidget(name); col.addWidget(sub)

        arrow = QLabel("›")
        arrow.setStyleSheet(f"color:{TEXT_MUTED};font-size:18px;background:transparent;border:none;")

        layout.addWidget(icon); layout.addSpacing(12)
        layout.addLayout(col); layout.addStretch(); layout.addWidget(arrow)

        # Click handler
        card.mousePressEvent = lambda e, p=profile: self.profile_selected.emit(p)
        return card

    def refresh(self):
        self._populate()


# ── Create screen ──────────────────────────────────────────────────────────
class CreateScreen(QWidget):
    saved    = pyqtSignal(object)
    canceled = pyqtSignal()

    def __init__(self, manager, existing=None):
        super().__init__()
        self.manager  = manager
        self.existing = existing
        self.setStyleSheet("background:transparent;")
        self._build()
        if existing:
            self._populate(existing)

    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"color:{TEXT_MUTED};font-size:11px;letter-spacing:0.04em;background:transparent;")
        return l

    def _build(self):
        from PyQt6.QtWidgets import QLineEdit, QTextEdit, QComboBox, QFileDialog
        self._QLineEdit = QLineEdit
        self._QTextEdit = QTextEdit
        self._QComboBox = QComboBox

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        outer.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet("background:transparent;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16,0,16,0)
        back = QPushButton("‹ Back")
        back.setStyleSheet(f"background:transparent;border:none;color:{TEXT_MUTED};font-size:13px;")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(self.canceled)
        title = QLabel("New Tutor" if not self.existing else "Edit Tutor")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{TEXT_PRIMARY};font-size:15px;font-weight:500;background:transparent;")
        hl.addWidget(back); hl.addStretch(); hl.addWidget(title)
        hl.addStretch(); hl.addWidget(QLabel("  "))
        outer.addWidget(hdr)

        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1); div.setStyleSheet(f"background:{BORDER_LIGHT};border:none;")
        outer.addWidget(div)

        FIELD = f"""
            QLineEdit, QTextEdit, QComboBox {{
                background:rgba(10,25,60,0.8);border:1px solid {BORDER_LIGHT};
                border-radius:8px;color:{TEXT_PRIMARY};font-size:13px;padding:6px 10px;
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus{{border:1px solid {ACCENT_BRIGHT};}}
            QComboBox::drop-down{{border:none;}}
            QComboBox QAbstractItemView{{background:#0d1528;color:{TEXT_PRIMARY};
            border:1px solid {BORDER_LIGHT};selection-background-color:{ACCENT_MID};}}
        """
        self.setStyleSheet(FIELD + "background:transparent;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        fw = QWidget(); fw.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(fw)
        layout.setContentsMargins(20,16,20,20)
        layout.setSpacing(10)
        scroll.setWidget(fw)
        outer.addWidget(scroll)

        layout.addWidget(self._lbl("TUTOR NAME"))
        self.name_f = QLineEdit(); self.name_f.setPlaceholderText("e.g. Italian Tutor")
        layout.addWidget(self.name_f)

        layout.addWidget(self._lbl("SUBJECT"))
        self.subject_f = QLineEdit(); self.subject_f.setPlaceholderText("e.g. Italian Language, Calculus")
        layout.addWidget(self.subject_f)

        layout.addWidget(self._lbl("SYSTEM PROMPT"))
        self.prompt_f = QTextEdit(); self.prompt_f.setFixedHeight(90)
        self.prompt_f.setPlaceholderText("How should the tutor behave? What language, tone, rules?")
        layout.addWidget(self.prompt_f)

        div2 = QFrame(); div2.setFrameShape(QFrame.Shape.HLine)
        div2.setFixedHeight(1); div2.setStyleSheet(f"background:{BORDER_LIGHT};border:none;")
        layout.addWidget(div2)

        layout.addWidget(self._lbl("OLLAMA MODEL"))
        self.model_f = QLineEdit()
        self.model_f.setPlaceholderText("e.g. gemma3:4b, llama3.2:3b, qwen3:8b")
        layout.addWidget(self.model_f)

        div3 = QFrame(); div3.setFrameShape(QFrame.Shape.HLine)
        div3.setFixedHeight(1); div3.setStyleSheet(f"background:{BORDER_LIGHT};border:none;")
        layout.addWidget(div3)

        layout.addWidget(self._lbl("STT LANGUAGE CODE"))
        self.lang_f = QLineEdit(); self.lang_f.setPlaceholderText("e.g. it, en, fr, de, ja")
        layout.addWidget(self.lang_f)

        layout.addWidget(self._lbl("TTS ENGINE"))
        self.tts_combo = QComboBox()
        self.tts_combo.addItems(["f5", "kokoro", "piper"])
        layout.addWidget(self.tts_combo)

        layout.addWidget(self._lbl("TTS VOICE"))
        self.voice_f = QLineEdit()
        self.voice_f.setPlaceholderText("Kokoro: if_sara / im_nicola — Piper: path to .onnx — F5: leave blank")
        layout.addWidget(self.voice_f)

        layout.addWidget(self._lbl("REFERENCE AUDIO (F5 voice cloning — optional)"))
        ref_row = QHBoxLayout()
        self.ref_f = QLineEdit(); self.ref_f.setPlaceholderText("Path to .wav reference file")
        browse = QPushButton("Browse")
        browse.setFixedWidth(70)
        browse.setStyleSheet(f"""
            QPushButton{{background:{rgba(ACCENT_MID,0.2)};border:1px solid {BORDER_LIGHT};
            border-radius:7px;color:{TEXT_MUTED};font-size:12px;padding:4px;}}
            QPushButton:hover{{color:{TEXT_PRIMARY};background:{rgba(ACCENT_BRIGHT,0.25)};}}
        """)
        browse.clicked.connect(self._browse)
        ref_row.addWidget(self.ref_f); ref_row.addWidget(browse)
        layout.addLayout(ref_row)
        layout.addStretch()

        # Save button
        div4 = QFrame(); div4.setFrameShape(QFrame.Shape.HLine)
        div4.setFixedHeight(1); div4.setStyleSheet(f"background:{BORDER_LIGHT};border:none;")
        outer.addWidget(div4)

        btn_row = QWidget(); btn_row.setStyleSheet("background:transparent;")
        bl = QHBoxLayout(btn_row); bl.setContentsMargins(20,10,20,16)
        save = QPushButton("Save Tutor")
        save.setFixedHeight(40)
        save.setStyleSheet(f"""
            QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {ACCENT_BRIGHT},stop:1 {ACCENT_MID});border:none;border-radius:10px;
            color:white;font-size:14px;font-weight:500;}}
        """)
        save.clicked.connect(self._save)
        bl.addWidget(save)
        outer.addWidget(btn_row)

    def _browse(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Select reference audio", "", "Audio (*.wav *.mp3 *.flac)")
        if path: self.ref_f.setText(path)

    def _populate(self, p):
        self.name_f.setText(p.name)
        self.subject_f.setText(p.subject)
        self.prompt_f.setPlainText(p.system_prompt)
        self.model_f.setText(p.llm_model)
        self.lang_f.setText(p.language)
        idx = self.tts_combo.findText(p.tts_engine)
        if idx >= 0: self.tts_combo.setCurrentIndex(idx)
        self.voice_f.setText(p.tts_voice)
        self.ref_f.setText(p.tts_ref_audio)

    def _save(self):
        from profile_manager import TutorProfile
        name = self.name_f.text().strip()
        if not name:
            self.name_f.setPlaceholderText("⚠ Name required")
            return
        p = self.existing or TutorProfile(name="",subject="",system_prompt="",language="en")
        p.name          = name
        p.subject       = self.subject_f.text().strip() or name
        p.system_prompt = self.prompt_f.toPlainText().strip()
        p.llm_provider  = "ollama"
        p.llm_model     = self.model_f.text().strip() or "gemma3:4b"
        p.llm_url       = "http://localhost:11434"
        p.llm_api_key   = ""
        p.language      = self.lang_f.text().strip() or "en"
        p.tts_engine    = self.tts_combo.currentText()
        p.tts_voice     = self.voice_f.text().strip()
        p.tts_ref_audio = self.ref_f.text().strip()
        self.manager.save(p)
        self.saved.emit(p)


# ── Session screen (the tutor UI) ──────────────────────────────────────────
class SessionScreen(QWidget):
    go_back = pyqtSignal()

    def __init__(self, profile_name: str = "AI Tutor"):
        super().__init__()
        self._profile_name = profile_name
        self.setStyleSheet("background:transparent;")
        self._build()
        self._connect_signals()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)

        layout.addWidget(self._title_bar())
        layout.addWidget(self._divider())
        layout.addWidget(self._waveform_row())
        layout.addWidget(self._divider())
        layout.addWidget(self._status_row())
        layout.addWidget(self._divider())
        layout.addWidget(self._mic_row())
        layout.addWidget(self._divider())

        self.loading_panel = LoadingPanel()
        layout.addWidget(self.loading_panel)

    def _title_bar(self):
        w = QWidget(); w.setFixedHeight(56); w.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(w); layout.setContentsMargins(14,0,14,0); layout.setSpacing(0)

        # close_btn = self._icon_btn("✕", "Close")
        # close_btn.setStyleSheet(f"""
        #     QPushButton{{background:{rgba(RED,0.12)};border:1px solid {rgba(RED,0.3)};
        #     border-radius:7px;color:{RED};font-size:13px;}}
        #     QPushButton:hover{{background:{rgba(RED,0.28)};color:#ff8a9a;}}
        # """)
        # close_btn.clicked.connect(self.go_back)

        # title = QLabel(self._profile_name)
        # title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # title.setStyleSheet(f"color:{TEXT_PRIMARY};font-size:15px;font-weight:500;background:transparent;")

        # settings_btn = self._icon_btn("⚙", "Settings")

        # layout.addWidget(close_btn); layout.addStretch()
        # layout.addWidget(title); layout.addStretch()
        # layout.addWidget(settings_btn)
        # return w
        # Back button
        back_btn = self._icon_btn("←", "Back")
        back_btn.clicked.connect(self.go_back)

        # Settings button
        settings_btn = self._icon_btn("⚙", "Settings")

        # Exit button
        exit_btn = self._icon_btn("✕", "Exit")
        exit_btn.setStyleSheet(f"""
            QPushButton {{
                background:{rgba(RED,0.12)};
                border:1px solid {rgba(RED,0.3)};
                border-radius:7px;
                color:{RED};
                font-size:13px;
            }}
            QPushButton:hover {{
                background:{rgba(RED,0.28)};
                color:#ff8a9a;
            }}
        """)
        exit_btn.clicked.connect(lambda: self.window().close())

        title = QLabel(self._profile_name)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{TEXT_PRIMARY};"
            "font-size:15px;"
            "font-weight:500;"
            "background:transparent;"
        )

        layout.addWidget(back_btn)
        layout.addWidget(settings_btn)

        layout.addStretch()
        layout.addWidget(title)
        layout.addStretch()

        layout.addWidget(exit_btn)

        return w
    

    def _waveform_row(self):
        w = QWidget(); w.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(w); layout.setContentsMargins(16,10,16,10)
        self.waveform = WaveformWidget()
        layout.addWidget(self.waveform)
        return w

    def _status_row(self):
        self.status_widget = StatusWidget()
        self.status_widget.setStyleSheet("background:transparent;")
        return self.status_widget

    def _mic_row(self):
        w = QWidget(); w.setFixedHeight(52); w.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(w); layout.setContentsMargins(16,0,16,0); layout.setSpacing(0)
        self.mic_toggle = MicToggle()
        chat_btn = QPushButton("chat log  ›")
        chat_btn.setFixedHeight(24)
        chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        chat_btn.setStyleSheet(f"""
            QPushButton{{background:{rgba(ACCENT_MID,0.15)};border:1px solid {BORDER_LIGHT};
            border-radius:5px;color:{TEXT_MUTED};font-size:11px;padding:0 10px;}}
            QPushButton:hover{{background:{rgba(ACCENT_MID,0.28)};color:{TEXT_PRIMARY};}}
        """)
        chat_btn.clicked.connect(self._toggle_chat)
        layout.addWidget(notes_btn)
        layout.addStretch()

        layout.addWidget(self.mic_toggle)

        layout.addStretch()
        layout.addWidget(chat_btn)
        return w

    def _icon_btn(self, icon, tooltip):
        btn = QPushButton(icon); btn.setFixedSize(28,28); btn.setToolTip(tooltip)
        btn.setStyleSheet(f"""
            QPushButton{{background:{rgba(ACCENT_MID,0.12)};border:1px solid {BORDER_LIGHT};
            border-radius:7px;color:{TEXT_MUTED};font-size:13px;}}
            QPushButton:hover{{background:{rgba(ACCENT_BRIGHT,0.22)};color:{TEXT_PRIMARY};}}
        """)
        return btn

    def _divider(self):
        f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
        f.setFixedHeight(1); f.setStyleSheet(f"background:{BORDER_LIGHT};border:none;")
        return f

    def _connect_signals(self):
        signals.update_status.connect(self.status_widget.set_state)
        signals.set_waveform.connect(lambda lvl: self.waveform.push_levels(np.asarray(lvl,dtype=float)))
        signals.waveform_active.connect(self.waveform.set_active)
        signals.component_loaded.connect(self.loading_panel.mark)
        signals.all_loaded.connect(self._on_loaded)

    def _on_loaded(self):
        self.loading_panel.hide()

    def _toggle_chat(self):
        if hasattr(self, '_chat_panel'):
            self._chat_panel.toggle(self.window().geometry())

    def set_chat_panel(self, panel: ChatPanel):
        self._chat_panel = panel

    def connect_mic_toggle(self, callback):
        self.mic_toggle.toggled.connect(callback)


# ── Main Window — single real window ──────────────────────────────────────
class MainWindow(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(380)
        self._drag_pos   = None
        self._manager    = manager
        self._session    = None

        # Single chat panel shared across sessions
        self.chat_panel  = ChatPanel()

        # Glass background
        self._glass = _GlassBg(self)

        # Stack
        self._stack = QStackedWidget(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        outer.addWidget(self._stack)

        # Start on correct screen
        if manager.has_profiles():
            self._show_select()
        else:
            self._show_create()

    def _show_select(self):
        screen = SelectScreen(self._manager)
        screen.profile_selected.connect(self._launch)
        screen.create_new.connect(self._show_create)
        self._set_screen(screen, 420)

    def _show_create(self, existing=None):
        screen = CreateScreen(self._manager, existing)
        screen.saved.connect(self._launch)
        screen.canceled.connect(
            self._show_select if self._manager.has_profiles() else self.close
        )
        self._set_screen(screen, 580)

    def _launch(self, profile):
        self._session = SessionScreen(profile.name)
        self._session.go_back.connect(self._show_select)
        self._session.set_chat_panel(self.chat_panel)
        self._set_screen(self._session, 420)
        signals.launch_session.emit(profile)

    def _set_screen(self, widget, height):
        # Remove old screens
        while self._stack.count():
            w = self._stack.widget(0)
            self._stack.removeWidget(w)
        self._stack.addWidget(widget)
        self._stack.setCurrentWidget(widget)
        self.setFixedHeight(height)
        self._glass.setGeometry(0, 0, self.width(), self.height())

    def get_session(self) -> SessionScreen | None:
        return self._session

    # Drag — single window, no nesting issues
    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag_pos:
            d = e.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + d)
            self._drag_pos = e.globalPosition().toPoint()
            self.chat_panel.reposition(self.geometry())

    def mouseReleaseEvent(self, e: QMouseEvent):
        self._drag_pos = None

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._glass.setGeometry(0, 0, self.width(), self.height())

    def paintEvent(self, _):
        pass  # GlassBg handles painting


class _GlassBg(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lower()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.setBrush(QBrush(QColor(8,14,35,210)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(1,1,W-2,H-2,19,19)
        g = QLinearGradient(0,0,W,H)
        g.setColorAt(0, QColor(20,100,200,50))
        g.setColorAt(1, QColor(15,80,180,40))
        p.setBrush(QBrush(g)); p.drawRoundedRect(1,1,W-2,H-2,19,19)
        rg = QRadialGradient(W*0.5,-H*0.1,W*0.9)
        rg.setColorAt(0, QColor(60,180,255,55))
        rg.setColorAt(1, QColor(0,0,0,0))
        p.setBrush(QBrush(rg)); p.drawRoundedRect(1,1,W-2,H-2,19,19)
        sh = QLinearGradient(0,0,0,H*0.28)
        sh.setColorAt(0, QColor(180,220,255,35))
        sh.setColorAt(1, QColor(0,0,0,0))
        p.setBrush(QBrush(sh)); p.drawRoundedRect(1,1,W-2,H-2,19,19)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(60,130,255,80),1))
        p.drawRoundedRect(1,1,W-2,H-2,19,19)
        p.setPen(QPen(QColor(20,60,140,120),1))
        p.drawRoundedRect(0,0,W-1,H-1,20,20)