"""
Tutor selection screen — shown on startup if profiles exist.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from profile_manager import ProfileManager, TutorProfile

DARK_BG      = "#080d1a"
BORDER       = "#1e3060"
ACCENT       = "#4a9eff"
ACCENT2      = "#2d6fd4"
TEXT_PRIMARY = "#deeeff"
TEXT_MUTED   = "#5a7aaa"
TEXT_DIM     = "#2a3a5a"


def rgba(h, a):
    h = h.lstrip("#")
    r,g,b = int(h[:2],16),int(h[2:4],16),int(h[4:],16)
    return f"rgba({r},{g},{b},{a})"


class TutorCard(QWidget):
    clicked = pyqtSignal(object)  # TutorProfile

    def __init__(self, profile: TutorProfile):
        super().__init__()
        self.profile = profile
        self.setFixedHeight(72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QWidget {{
                background: {rgba(ACCENT2, 0.1)};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
            QWidget:hover {{
                background: {rgba(ACCENT, 0.18)};
                border: 1px solid {rgba(ACCENT, 0.5)};
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)

        icon = QLabel(profile.subject[0].upper())
        icon.setFixedSize(40, 40)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {ACCENT},stop:1 {ACCENT2});
            border-radius: 10px;
            color: white;
            font-size: 16px;
            font-weight: 500;
            border: none;
        """)

        col = QVBoxLayout()
        col.setSpacing(2)
        name = QLabel(profile.name)
        name.setStyleSheet(f"color:{TEXT_PRIMARY};font-size:14px;font-weight:500;background:transparent;border:none;")
        sub  = QLabel(f"{profile.subject} · {profile.llm_model}")
        sub.setStyleSheet(f"color:{TEXT_MUTED};font-size:11px;background:transparent;border:none;")
        col.addWidget(name)
        col.addWidget(sub)

        layout.addWidget(icon)
        layout.addSpacing(12)
        layout.addLayout(col)
        layout.addStretch()

        arrow = QLabel("›")
        arrow.setStyleSheet(f"color:{TEXT_MUTED};font-size:18px;background:transparent;border:none;")
        layout.addWidget(arrow)

    def mousePressEvent(self, e):
        self.clicked.emit(self.profile)


class SelectScreen(QWidget):
    profile_selected = pyqtSignal(object)   # TutorProfile
    create_new       = pyqtSignal()

    def __init__(self, manager: ProfileManager):
        super().__init__()
        self.manager = manager
        self.setStyleSheet("background:transparent;")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 24, 20, 20)
        layout.setSpacing(16)

        title = QLabel("Choose a Tutor")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{TEXT_PRIMARY};font-size:18px;font-weight:500;background:transparent;")
        layout.addWidget(title)

        sub = QLabel("Select an existing tutor or create a new one")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color:{TEXT_MUTED};font-size:12px;background:transparent;")
        layout.addWidget(sub)

        # Cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        self._cards_layout = QVBoxLayout(inner)
        self._cards_layout.setSpacing(8)
        self._cards_layout.setContentsMargins(0,0,0,0)
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        self._populate()

        # New tutor button
        new_btn = QPushButton("+ New Tutor")
        new_btn.setFixedHeight(40)
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background: {rgba(ACCENT, 0.15)};
                border: 1px solid {rgba(ACCENT, 0.4)};
                border-radius: 10px;
                color: {ACCENT};
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {rgba(ACCENT, 0.28)};
            }}
        """)
        new_btn.clicked.connect(self.create_new)
        layout.addWidget(new_btn)

    def _populate(self):
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for profile in self.manager.list_profiles():
            card = TutorCard(profile)
            card.clicked.connect(self.profile_selected)
            self._cards_layout.addWidget(card)
        self._cards_layout.addStretch()

    def refresh(self):
        self._populate()