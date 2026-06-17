"""
AI Tutor — Main GUI Window v5
- Chat log panel slides LEFT
- Notes panel slides RIGHT
- Notes saved per-profile
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

from config import TTS_PRESETS, languages_for_model

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
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
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
        for key, name in [("whisper","Whisper STT"),("kokoro","TTS"),("ollama","Ollama LLM")]:
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


# ── Chat panel (slides LEFT) ───────────────────────────────────────────────
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
        hl.setContentsMargins(12, 0, 16, 0)

        close_btn = QPushButton("›")
        close_btn.setFixedSize(28,28)
        close_btn.setStyleSheet(f"""
            QPushButton{{background:{rgba(ACCENT_MID,0.1)};border:1px solid {BORDER_LIGHT};
            border-radius:7px;color:{TEXT_MUTED};font-size:16px;}}
            QPushButton:hover{{background:{rgba(ACCENT_MID,0.22)};color:{TEXT_PRIMARY};}}
        """)
        close_btn.clicked.connect(self.slide_out)

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

        hl.addWidget(close_btn)
        hl.addSpacing(8)
        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(clear_btn)
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

    # ── Slide LEFT (panel lives to the left of main window) ────────────────
    def slide_in(self, anchor: QRect):
        self.setFixedHeight(anchor.height())
        # Right edge of chat panel = left edge of main window
        end_x = anchor.left() - self.width()
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
            self.move(anchor.left() - self.width(), anchor.top())

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
    edit_profile     = pyqtSignal(object)   # TutorProfile
    delete_profile   = pyqtSignal(object)   # TutorProfile

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.setStyleSheet("background:transparent;")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)

        # ── Header bar with close button ──
        hdr = QWidget(); hdr.setFixedHeight(52); hdr.setStyleSheet("background:transparent;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14,0,14,0)
        title = QLabel("Choose a Tutor")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{TEXT_PRIMARY};font-size:16px;font-weight:500;background:transparent;")
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"""
            QPushButton{{background:{rgba(RED,0.12)};border:1px solid {rgba(RED,0.3)};
            border-radius:7px;color:{RED};font-size:12px;}}
            QPushButton:hover{{background:{rgba(RED,0.28)};color:#ff8a9a;}}
        """)
        close_btn.clicked.connect(lambda: self.window().close())
        hl.addWidget(QLabel("  ")); hl.addStretch()
        hl.addWidget(title); hl.addStretch(); hl.addWidget(close_btn)
        layout.addWidget(hdr)

        div0 = QFrame(); div0.setFrameShape(QFrame.Shape.HLine)
        div0.setFixedHeight(1); div0.setStyleSheet(f"background:{BORDER_LIGHT};border:none;")
        layout.addWidget(div0)

        inner_w = QWidget(); inner_w.setStyleSheet("background:transparent;")
        inner_layout = QVBoxLayout(inner_w)
        inner_layout.setContentsMargins(20,16,20,20)
        inner_layout.setSpacing(14)
        layout.addWidget(inner_w)
        layout = inner_layout   # redirect rest of build into inner widget

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
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction

        card = QWidget()
        card.setFixedHeight(72)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(f"""
            QWidget{{background:{rgba(ACCENT_MID,0.1)};border:1px solid {BORDER_LIGHT};border-radius:12px;}}
            QWidget:hover{{background:{rgba(ACCENT_BRIGHT,0.18)};border:1px solid {rgba(ACCENT_BRIGHT,0.5)};}}
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16,0,10,0)

        icon = QLabel(profile.subject[0].upper())
        icon.setFixedSize(40,40)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {ACCENT_BRIGHT},stop:1 {ACCENT_MID});
            border-radius:10px;color:white;font-size:16px;font-weight:500;border:none;
        """)

        col = QVBoxLayout()
        col.setSpacing(2)
        name_lbl = QLabel(profile.name)
        name_lbl.setStyleSheet(f"color:{TEXT_PRIMARY};font-size:14px;font-weight:500;background:transparent;border:none;")
        sub_lbl = QLabel(f"{profile.subject} · {profile.llm_model}")
        sub_lbl.setStyleSheet(f"color:{TEXT_MUTED};font-size:11px;background:transparent;border:none;")
        col.addWidget(name_lbl); col.addWidget(sub_lbl)

        # 3-dot menu button — stops click propagation to card
        dots_btn = QPushButton("•••")
        dots_btn.setFixedSize(28, 28)
        dots_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dots_btn.setStyleSheet(f"""
            QPushButton{{background:transparent;border:none;color:{TEXT_DIM};
            font-size:11px;letter-spacing:1px;}}
            QPushButton:hover{{background:{rgba(ACCENT_MID,0.3)};border-radius:6px;color:{TEXT_PRIMARY};}}
        """)

        def show_menu(_checked=False):
            p = profile
            menu = QMenu(card)
            menu.setStyleSheet(f"""
                QMenu{{background:#0d1528;border:1px solid {BORDER_LIGHT};border-radius:8px;padding:4px;}}
                QMenu::item{{color:{TEXT_PRIMARY};font-size:12px;padding:6px 16px;border-radius:5px;}}
                QMenu::item:selected{{background:{rgba(ACCENT_MID,0.3)};}}
                QMenu::separator{{background:{BORDER_LIGHT};height:1px;margin:3px 8px;}}
            """)
            edit_act = QAction("✏  Edit", menu)
            del_act  = QAction("🗑  Delete", menu)
            menu.addAction(edit_act)
            menu.addSeparator()
            menu.addAction(del_act)
            edit_act.triggered.connect(lambda _=False: self.edit_profile.emit(p))
            del_act.triggered.connect(lambda _=False: self._confirm_delete(p))
            menu.exec(dots_btn.mapToGlobal(dots_btn.rect().bottomLeft()))

        dots_btn.clicked.connect(show_menu)

        layout.addWidget(icon); layout.addSpacing(12)
        layout.addLayout(col); layout.addStretch(); layout.addWidget(dots_btn)

        # Click the card body (not the dots button) to launch
        def card_press(e, p=profile):
            # Only launch if not clicking the dots button area
            if not dots_btn.geometry().contains(e.pos()):
                self.profile_selected.emit(p)
        card.mousePressEvent = card_press
        return card

    def _confirm_delete(self, profile):
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(self.window())
        msg.setWindowTitle("Delete Tutor")
        msg.setText(f"Delete <b>{profile.name}</b>?")
        msg.setInformativeText("This cannot be undone.")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        msg.setStyleSheet(f"""
            QMessageBox{{background:#0d1528;color:{TEXT_PRIMARY};}}
            QLabel{{color:{TEXT_PRIMARY};font-size:13px;}}
            QPushButton{{background:{rgba(ACCENT_MID,0.2)};border:1px solid {BORDER_LIGHT};
            border-radius:7px;color:{TEXT_PRIMARY};font-size:12px;padding:5px 16px;min-width:60px;}}
            QPushButton:hover{{background:{rgba(ACCENT_BRIGHT,0.3)};}}
        """)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.delete_profile.emit(profile)

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

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        outer.setSpacing(0)

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
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"""
            QPushButton{{background:{rgba(RED,0.12)};border:1px solid {rgba(RED,0.3)};
            border-radius:7px;color:{RED};font-size:12px;}}
            QPushButton:hover{{background:{rgba(RED,0.28)};color:#ff8a9a;}}
        """)
        close_btn.clicked.connect(lambda: self.window().close())
        hl.addWidget(back); hl.addStretch(); hl.addWidget(title)
        hl.addStretch(); hl.addWidget(close_btn)
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

        # ── Ollama model dropdown ──
        model_hdr = QHBoxLayout()
        model_hdr.addWidget(self._lbl("OLLAMA MODEL"))
        model_hdr.addStretch()
        self._model_refresh_btn = QPushButton("↻ refresh")
        self._model_refresh_btn.setFixedHeight(18)
        self._model_refresh_btn.setStyleSheet(f"""
            QPushButton{{background:transparent;border:none;color:{TEXT_DIM};font-size:10px;}}
            QPushButton:hover{{color:{ACCENT_BRIGHT};}}
        """)
        self._model_refresh_btn.clicked.connect(self._fetch_ollama_models)
        model_hdr.addWidget(self._model_refresh_btn)
        layout.addLayout(model_hdr)

        from config import languages_for_model, TTS_PRESETS

        # ── Ollama model (dropdown, non-editable) ──
        layout.addWidget(self._lbl("OLLAMA MODEL"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(False)  # was True
        self._fetch_ollama_models()
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        layout.addWidget(self.model_combo)

        # ── STT language (dropdown filtered by model) ──
        layout.addWidget(self._lbl("STT LANGUAGE"))
        self.lang_combo = QComboBox()
        self.lang_combo.setEditable(False)
        self.lang_combo.setEnabled(False)  # until models load
        layout.addWidget(self.lang_combo)

        div3 = QFrame(); div3.setFrameShape(QFrame.Shape.HLine)
        div3.setFixedHeight(1); div3.setStyleSheet(f"background:{BORDER_LIGHT};border:none;")
        layout.addWidget(div3)

        # ── TTS engine ──
        layout.addWidget(self._lbl("TTS ENGINE"))
        self.tts_combo = QComboBox()
        self.tts_combo.addItems(["f5", "kokoro", "piper"])
        self.tts_combo.currentTextChanged.connect(self._on_tts_engine_change)
        layout.addWidget(self.tts_combo)

        # ── TTS voice (dropdown for kokoro; hidden for f5/piper) ──
        self._voice_section_label = self._lbl("TTS VOICE")
        layout.addWidget(self._voice_section_label)
        self.voice_combo = QComboBox()
        self.voice_combo.setEditable(False)  # was True — now a real dropdown
        layout.addWidget(self.voice_combo)

        # Advanced toggle (ref audio / custom path)
        self._adv_btn = QPushButton("▸ Advanced")
        self._adv_btn.setStyleSheet(f"""
            QPushButton{{background:transparent;border:none;color:{TEXT_DIM};
            font-size:11px;text-align:left;padding:0;}}
            QPushButton:hover{{color:{TEXT_MUTED};}}
        """)
        self._adv_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._adv_btn.clicked.connect(self._toggle_advanced)
        layout.addWidget(self._adv_btn)

        # ── Advanced section (per-engine fields, with stable references) ────────
        self._adv_widget = QWidget()
        self._adv_widget.setStyleSheet("background:transparent;")
        self._adv_widget.setVisible(False)
        adv_layout = QVBoxLayout(self._adv_widget)
        adv_layout.setContentsMargins(0, 4, 0, 0)
        adv_layout.setSpacing(6)

        def _make_advanced_row(label_text, field_placeholder, browse_handler):
            """A labeled row: label on top, QLineEdit + Browse button below.
            Returns the row widget (so we can show/hide the whole row at once),
            the label, the line edit, and the browse button.
            """
            row = QWidget()
            row.setStyleSheet("background:transparent;")
            rl = QVBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(4)

            lbl = self._lbl(label_text)
            rl.addWidget(lbl)

            h = QHBoxLayout()
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)

            edit = QLineEdit()
            edit.setPlaceholderText(field_placeholder)

            browse = QPushButton("Browse")
            browse.setFixedWidth(70)
            browse.setStyleSheet(f"""
                QPushButton{{background:{rgba(ACCENT_MID,0.2)};border:1px solid {BORDER_LIGHT};
                border-radius:7px;color:{TEXT_MUTED};font-size:12px;padding:4px;}}
                QPushButton:hover{{color:{TEXT_PRIMARY};background:{rgba(ACCENT_BRIGHT,0.25)};}}
            """)
            browse.clicked.connect(browse_handler)

            h.addWidget(edit)
            h.addWidget(browse)
            rl.addLayout(h)
            return row, lbl, edit, browse

        # Custom voice path row (piper .onnx)
        self._voice_custom_row, self._voice_custom_label, self.voice_custom_f, self._browse_voice_btn = \
            _make_advanced_row(
                "CUSTOM VOICE PATH (overrides dropdown)",
                "Path to .onnx (piper) or leave blank",
                self._browse_voice,
            )
        adv_layout.addWidget(self._voice_custom_row)

        # Reference audio row (f5 voice cloning)
        self._ref_row, self._ref_section_label, self.ref_f, self._browse_ref_btn = \
            _make_advanced_row(
                "REFERENCE AUDIO (F5 voice cloning)",
                "Path to .wav reference file",
                self._browse_ref,
            )
        adv_layout.addWidget(self._ref_row)

        layout.addWidget(self._adv_widget)

        # layout.addStretch() # COME BACK TO THIS

        # Populate initial voice list
        self._on_tts_engine_change("f5")

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

    # ── Voice presets per engine ────────────────────────────────────────────
    def _fetch_ollama_models(self):
        """Hit Ollama API in a thread and populate the combo."""
        import threading, requests

        # Show a "fetching" placeholder item while we wait
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItem("fetching models…")
        self.model_combo.setEnabled(False)
        self.model_combo.blockSignals(False)

        def _fetch():
            try:
                r = requests.get("http://localhost:11434/api/tags", timeout=4)
                models = [m["name"] for m in r.json().get("models", [])]
            except Exception:
                models = []

            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(
                self, "_set_ollama_models",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(object, models),
            )

        threading.Thread(target=_fetch, daemon=True).start()


    # Must be a real slot so invokeMethod can reach it across threads
    from PyQt6.QtCore import pyqtSlot
    @pyqtSlot(object)
    def _set_ollama_models(self, models):
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.setEnabled(True)

        if models:
            self.model_combo.addItems(models)
            # Default to gemma3:4b if present, else first model
            default = "gemma3:4b" if "gemma3:4b" in models else models[0]
            idx = self.model_combo.findText(default)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
        else:
            # Couldn't reach Ollama — show a single fallback item so the
            # language dropdown still has something to react to.
            self.model_combo.addItem("gemma3:4b")

        self.model_combo.blockSignals(False)

        # Force _on_model_changed to fire so the language dropdown populates.
        # (It won't auto-fire when signals are blocked, and won't fire on addItems
        # if the first item happens to be empty.)
        self._on_model_changed(self.model_combo.currentText())

        # If we're editing an existing profile, restore its model selection
        if self.existing:
            idx = self.model_combo.findText(self.existing.llm_model)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
            # _on_model_changed already fired above with the default; re-fire
            # with the actual existing model so the language dropdown matches.
            self._on_model_changed(self.model_combo.currentText())
    # VOICE_PRESETS = {
    #     "f5":     ["(default — no selection needed)"],
    #     "kokoro": [
    #         "if_sara", "if_nicola", "if_sara_slow",
    #         "im_nicola", "im_adam", "im_santa",
    #         "af_heart", "af_bella", "af_aoede", "af_kore", "af_nova",
    #         "am_adam", "am_michael",
    #         "bf_emma", "bf_isabella", "bm_george", "bm_lewis",
    #     ],
    #     "piper":  ["(browse for .onnx file below)"],
    # }

    # def _fetch_ollama_models(self):
    #     """Hit Ollama API in a thread and populate the combo."""
    #     import threading, requests
    #     self.model_combo.clear()
    #     self.model_combo.lineEdit().setPlaceholderText("fetching…")

    #     def _fetch():
    #         try:
    #             r = requests.get("http://localhost:11434/api/tags", timeout=4)
    #             models = [m["name"] for m in r.json().get("models", [])]
    #         except Exception:
    #             models = []

    #         from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
    #         QMetaObject.invokeMethod(
    #             self, "_set_ollama_models",
    #             Qt.ConnectionType.QueuedConnection,
    #             Q_ARG(object, models),
    #         )

    #     threading.Thread(target=_fetch, daemon=True).start()

    # # Must be a real slot so invokeMethod can reach it across threads
    # from PyQt6.QtCore import pyqtSlot
    # @pyqtSlot(object)
    # def _set_ollama_models(self, models):
    #     self.model_combo.clear()
    #     if models:
    #         self.model_combo.addItems(models)
    #         self.model_combo.lineEdit().setPlaceholderText("")
    #     else:
    #         self.model_combo.lineEdit().setPlaceholderText("couldn't reach Ollama — type manually")
    #     # If editing an existing profile, re-select its model
    #     self._on_model_changed(self.model_combo.currentText())
    #     if self.existing:
    #         idx = self.model_combo.findText(self.existing.llm_model)
    #         if idx >= 0:
    #             self.model_combo.setCurrentIndex(idx)
            # else:
            #     self.model_combo.setCurrentText(self.existing.llm_model)
        # Trigger language population for the selected model
        # self._on_model_changed(self.model_combo.currentText())

    # def _on_tts_engine_change(self, engine: str):
    #     self.voice_combo.clear()
    #     presets = self.VOICE_PRESETS.get(engine, [])
    #     self.voice_combo.addItems(presets)
    #     # Show/hide ref audio row in advanced based on engine
    #     has_adv = self._adv_widget.layout() is not None
    #     if has_adv:
    #         pass  # always show advanced section; ref audio only matters for f5

    # def _toggle_advanced(self):
    #     visible = not self._adv_widget.isVisible()
    #     self._adv_widget.setVisible(visible)
    #     self._adv_btn.setText("▾ Advanced" if visible else "▸ Advanced")
    def _on_model_changed(self, model: str):
        """Rebuild the language dropdown based on the selected model."""
        self.lang_combo.blockSignals(True)
        self.lang_combo.clear()
        langs = languages_for_model(model)
        if not langs:
            langs = [("en", "English")]
        for code, label in langs:
            self.lang_combo.addItem(label, userData=code)
        # Preserve current selection if still valid; else default to first
        cur = getattr(self, "_current_lang_code", None)
        target_idx = next(
            (i for i in range(self.lang_combo.count())
            if self.lang_combo.itemData(i) == cur),
            0,
        )
        self.lang_combo.setCurrentIndex(target_idx)
        self.lang_combo.setEnabled(True)
        self.lang_combo.blockSignals(False)

    def _on_tts_engine_change(self, engine: str):
        """Engine changed — rebuild voice dropdown and toggle advanced rows."""
        presets = TTS_PRESETS.get(engine, [])

        self.voice_combo.blockSignals(True)
        self.voice_combo.clear()

        if presets:
            # kokoro: real voice dropdown, hide advanced rows
            for vid, label in presets:
                self.voice_combo.addItem(label, userData=vid)
            self.voice_combo.show()
            self._voice_section_label.show()
        else:
            # f5 / piper: no preset list, force advanced open so user sees
            # where to put the path
            self.voice_combo.hide()
            self._voice_section_label.hide()
            self._adv_widget.setVisible(True)
            self._adv_btn.setText("▾ Advanced")

        self.voice_combo.blockSignals(False)

        # Show/hide individual rows inside advanced
        self._toggle_advanced_visibility(engine)

        # Show/hide the ref-audio row inside advanced based on engine
        self._toggle_advanced_visibility(engine)
        self.voice_combo.blockSignals(False)

    def _toggle_advanced(self):
        visible = not self._adv_widget.isVisible()
        self._adv_widget.setVisible(visible)
        self._adv_btn.setText("▾ Advanced" if visible else "▸ Advanced")

    def _toggle_advanced_visibility(self, engine: str):
        """f5 needs reference audio; piper needs voice .onnx path; kokoro needs neither."""
        if not hasattr(self, "_ref_section_label"):
            return  # not built yet
        show_ref = (engine == "f5")
        show_custom_voice = (engine in ("piper", "f5"))
        self._ref_section_label.setVisible(show_ref)
        self.ref_f.setVisible(show_ref)
        # (your browse_ref button should also be hidden — wrap them in a QFrame for cleanliness)
        self._voice_custom_label.setVisible(show_custom_voice)
        self.voice_custom_f.setVisible(show_custom_voice)
        # browse_voice similarly
    


    def _browse_voice(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Select voice model", "", "ONNX model (*.onnx);;All files (*)"
        )
        if path:
            self.voice_custom_f.setText(path)

    def _browse_ref(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Select reference audio", "", "Audio (*.wav *.mp3 *.flac)"
        )
        if path:
            self.ref_f.setText(path)

    # def _populate(self, p):
    #     self.name_f.setText(p.name)
    #     self.subject_f.setText(p.subject)
    #     self.prompt_f.setPlainText(p.system_prompt)
    #     # Model combo — may not be populated yet (async fetch); set text directly
    #     self.model_combo.setCurrentText(p.llm_model)
    #     self.lang_f.setText(p.language)
    #     idx = self.tts_combo.findText(p.tts_engine)
    #     if idx >= 0:
    #         self.tts_combo.setCurrentIndex(idx)
    #     # Voice: try dropdown first, else put in custom field and open advanced
    #     voice_idx = self.voice_combo.findText(p.tts_voice)
    #     if voice_idx >= 0:
    #         self.voice_combo.setCurrentIndex(voice_idx)
    #     elif p.tts_voice:
    #         self.voice_custom_f.setText(p.tts_voice)
    #         self._adv_widget.setVisible(True)
    #         self._adv_btn.setText("▾ Advanced")
    #     self.ref_f.setText(p.tts_ref_audio or "")

    # def _save(self):
    #     from profile_manager import TutorProfile
    #     name = self.name_f.text().strip()
    #     if not name:
    #         self.name_f.setPlaceholderText("⚠ Name required")
    #         return
    #     p = self.existing or TutorProfile(name="", subject="", system_prompt="", language="en")
    #     p.name          = name
    #     p.subject       = self.subject_f.text().strip() or name
    #     p.system_prompt = self.prompt_f.toPlainText().strip()
    #     p.llm_provider  = "ollama"
    #     p.llm_model     = self.model_combo.currentText().strip() or "gemma3:4b"
    #     p.llm_url       = "http://localhost:11434"
    #     p.llm_api_key   = ""
    #     p.language      = self.lang_f.text().strip() or "en"
    #     p.tts_engine    = self.tts_combo.currentText()
    #     # Custom path overrides dropdown
    #     custom_voice = self.voice_custom_f.text().strip()
    #     if custom_voice:
    #         p.tts_voice = custom_voice
    #     else:
    #         v = self.voice_combo.currentText()
    #         p.tts_voice = "" if v.startswith("(") else v
    #     p.tts_ref_audio = self.ref_f.text().strip()
    #     self.manager.save(p)
    #     self.saved.emit(p)
    def _populate(self, p):
        self.name_f.setText(p.name)
        self.subject_f.setText(p.subject)
        self.prompt_f.setPlainText(p.system_prompt)
        self.model_combo.setCurrentText(p.llm_model)   # will trigger _on_model_changed
        # Language
        self._current_lang_code = p.language
        idx = self.lang_combo.findData(p.language)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        # TTS
        idx = self.tts_combo.findText(p.tts_engine)
        if idx >= 0:
            self.tts_combo.setCurrentIndex(idx)         # triggers _on_tts_engine_change
        # Voice — try dropdown first, else put in custom field and expand advanced
        vidx = self.voice_combo.findData(p.tts_voice)
        if vidx >= 0:
            self.voice_combo.setCurrentIndex(vidx)
        elif p.tts_voice:
            self.voice_custom_f.setText(p.tts_voice)
        self.ref_f.setText(p.tts_ref_audio or "")

    def _save(self):
        from profile_manager import TutorProfile
        name = self.name_f.text().strip()
        if not name:
            self.name_f.setPlaceholderText("⚠ Name required")
            return
        p = self.existing or TutorProfile(name="", subject="", system_prompt="", language="en")
        p.name          = name
        p.subject       = self.subject_f.text().strip() or name
        p.system_prompt = self.prompt_f.toPlainText().strip()
        p.llm_provider  = "ollama"
        p.llm_model     = self.model_combo.currentText().strip() or "gemma3:4b"
        p.llm_url       = "http://localhost:11434"
        p.llm_api_key   = ""
        p.language      = self.lang_combo.currentData() or "en"   # ← was lang_f.text()
        p.tts_engine    = self.tts_combo.currentText()
        # Custom path overrides dropdown
        custom_voice = self.voice_custom_f.text().strip()
        if custom_voice:
            p.tts_voice = custom_voice
        else:
            p.tts_voice = self.voice_combo.currentData() or ""
        p.tts_ref_audio = self.ref_f.text().strip()
        self.manager.save(p)
        self.saved.emit(p)


# ── Session screen ─────────────────────────────────────────────────────────
class SessionScreen(QWidget):
    go_back = pyqtSignal()

    def __init__(self, profile_name: str = "AI Tutor"):
        super().__init__()
        self._profile_name = profile_name
        self.setStyleSheet("background:transparent;")
        self._chat_panel  = None
        self._notes_panel = None
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

        back_btn = self._icon_btn("←", "Back")
        back_btn.clicked.connect(self.go_back)

        settings_btn = self._icon_btn("⚙", "Settings")

        exit_btn = self._icon_btn("✕", "Exit")
        exit_btn.setStyleSheet(f"""
            QPushButton {{
                background:{rgba(RED,0.12)};border:1px solid {rgba(RED,0.3)};
                border-radius:7px;color:{RED};font-size:13px;
            }}
            QPushButton:hover {{background:{rgba(RED,0.28)};color:#ff8a9a;}}
        """)
        exit_btn.clicked.connect(lambda: self.window().close())

        title = QLabel(self._profile_name)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{TEXT_PRIMARY};font-size:15px;font-weight:500;background:transparent;"
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

        # ‹ chat log button — LEFT side
        chat_btn = QPushButton("‹ chat log")
        chat_btn.setFixedHeight(24)
        chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        chat_btn.setStyleSheet(f"""
            QPushButton{{background:{rgba(ACCENT_MID,0.15)};border:1px solid {BORDER_LIGHT};
            border-radius:5px;color:{TEXT_MUTED};font-size:11px;padding:0 10px;}}
            QPushButton:hover{{background:{rgba(ACCENT_MID,0.28)};color:{TEXT_PRIMARY};}}
        """)
        chat_btn.clicked.connect(self._toggle_chat)

        # mic toggle — CENTER
        self.mic_toggle = MicToggle()

        # notes › button — RIGHT side
        notes_btn = QPushButton("notes ›")
        notes_btn.setFixedHeight(24)
        notes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        notes_btn.setStyleSheet(f"""
            QPushButton{{background:{rgba(ACCENT_MID,0.15)};border:1px solid {BORDER_LIGHT};
            border-radius:5px;color:{TEXT_MUTED};font-size:11px;padding:0 10px;}}
            QPushButton:hover{{background:{rgba(ACCENT_MID,0.28)};color:{TEXT_PRIMARY};}}
        """)
        notes_btn.clicked.connect(self._toggle_notes)

        layout.addWidget(chat_btn)
        layout.addStretch()
        layout.addWidget(self.mic_toggle)
        layout.addStretch()
        layout.addWidget(notes_btn)
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
        signals.set_waveform.connect(lambda lvl: self.waveform.push_levels(np.asarray(lvl, dtype=float)))
        signals.waveform_active.connect(self.waveform.set_active)
        signals.component_loaded.connect(self.loading_panel.mark)
        signals.all_loaded.connect(self._on_loaded)

    def _on_loaded(self):
        self.loading_panel.hide()

    def _toggle_chat(self):
        if self._chat_panel:
            self._chat_panel.toggle(self.window().geometry())

    def _toggle_notes(self):
        if self._notes_panel:
            self._notes_panel.toggle(self.window().geometry())

    def set_chat_panel(self, panel: ChatPanel):
        self._chat_panel = panel

    def set_notes_panel(self, panel):
        self._notes_panel = panel

    def connect_mic_toggle(self, callback):
        self.mic_toggle.toggled.connect(callback)


# ── Main Window ────────────────────────────────────────────────────────────
class MainWindow(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(380)
        self._drag_pos = None
        self._manager  = manager
        self._session  = None

        # Panels — created once, shared across sessions
        self.chat_panel  = ChatPanel()

        # Notes panel needs profile manager to save
        from app.ui.notes_panel import NotesPanel
        self.notes_panel = NotesPanel(manager)

        self._glass = _GlassBg(self)

        self._stack = QStackedWidget(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        outer.addWidget(self._stack)

        if manager.has_profiles():
            self._show_select()
        else:
            self._show_create()

    def _show_select(self):
        self.chat_panel.slide_out()
        self.notes_panel.slide_out()

        screen = SelectScreen(self._manager)
        screen.profile_selected.connect(self._launch)
        screen.create_new.connect(self._show_create)
        screen.delete_profile.connect(self._delete_profile)
        self._set_screen(screen, 420)
    
    def _delete_profile(self, profile):
        if self._session is not None and self._session._profile_name == profile.name:
            self._session = None
        self._manager.delete(profile.id)
        self._show_select()

    def _show_create(self, existing=None):
        self.chat_panel.slide_out()
        self.notes_panel.slide_out()

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
        self._session.set_notes_panel(self.notes_panel)
        self._set_screen(self._session, 420)

        # Load this profile's notes into the panel
        self.notes_panel.load_profile(profile)

        signals.launch_session.emit(profile)

    def _set_screen(self, widget, height):
        while self._stack.count():
            w = self._stack.widget(0)
            self._stack.removeWidget(w)
        self._stack.addWidget(widget)
        self._stack.setCurrentWidget(widget)
        self.setFixedHeight(height)
        self._glass.setGeometry(0, 0, self.width(), self.height())

    def get_session(self) -> SessionScreen | None:
        return self._session

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag_pos:
            d = e.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + d)
            self._drag_pos = e.globalPosition().toPoint()
            # Reposition both panels to track the window
            self.chat_panel.reposition(self.geometry())
            self.notes_panel.reposition(self.geometry())

    def mouseReleaseEvent(self, e: QMouseEvent):
        self._drag_pos = None

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._glass.setGeometry(0, 0, self.width(), self.height())

    def paintEvent(self, _):
        pass


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