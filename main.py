import sys
import os
import random
import datetime
import psutil
import speech_recognition as sr
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFrame, QStackedWidget, QProgressBar,
    QTextEdit, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QUrl, QThread, Signal
from PySide6.QtGui import QPainter, QPainterPath, QColor
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

# ── PALETTE ──────────────────────────────────────────────────────────────────
TANGERINE  = "#FF9966"
LILAC      = "#CC99CC"
GOLD       = "#FFCC00"
LIGHT_BLUE = "#99CCFF"
BG_BLACK   = "#000000"

# ── ASSET HELPER ─────────────────────────────────────────────────────────────
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ═════════════════════════════════════════════════════════════════════════════
#  SHARED WIDGETS
# ═════════════════════════════════════════════════════════════════════════════

class LcarsHollowElbow(QWidget):
    """QPainter-drawn LCARS curved corner elbow."""
    def __init__(self, color=TANGERINE, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.setFixedSize(160, 100)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.color)
        w, h, thick, r, ir = self.width(), self.height(), 30, 40, 20
        path = QPainterPath()
        path.moveTo(w, 0)
        path.lineTo(r, 0)
        path.arcTo(0, 0, r * 2, r * 2, 90, 90)
        path.lineTo(0, h)
        path.lineTo(thick, h)
        path.lineTo(thick, thick + ir)
        path.arcTo(thick, thick, ir * 2, ir * 2, 180, -90)
        path.lineTo(w, thick)
        path.closeSubpath()
        painter.drawPath(path)


class LcarsButton(QPushButton):
    def __init__(self, text, color=GOLD):
        super().__init__(text)
        self.setMinimumHeight(32)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color}; color: black; border-radius: 15px;
                font-family: 'Arial Narrow'; font-weight: bold;
                text-align: right; padding-right: 15px; border: none;
            }}
            QPushButton:pressed {{ background-color: white; }}
            QPushButton:hover   {{ background-color: white; }}
        """)


class LcarsKey(QPushButton):
    """Tactical grid button that plays a beep when clicked."""
    def __init__(self, text, color=GOLD, player=None):
        super().__init__(text)
        self.player = player
        self.setFixedSize(80, 40)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color}; color: black; border-radius: 5px;
                font-family: 'Arial Narrow'; font-weight: bold;
                font-size: 12px; border: none;
            }}
            QPushButton:pressed {{ background-color: white; }}
        """)
        if self.player:
            self.clicked.connect(self._play)

    def _play(self):
        self.player.stop()
        self.player.play()


# ═════════════════════════════════════════════════════════════════════════════
#  BACKGROUND WORKER
# ═════════════════════════════════════════════════════════════════════════════

class VoiceWorker(QThread):
    command_received = Signal(str)
    error_occurred   = Signal(str)

    def run(self):
        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)
                while True:
                    try:
                        audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                        text  = recognizer.recognize_google(audio).lower()
                        if "computer" in text:
                            self.command_received.emit(text.split("computer")[-1].strip())
                    except (sr.WaitTimeoutError, sr.UnknownValueError):
                        continue
                    except Exception:
                        continue
        except Exception as e:
            self.error_occurred.emit(str(e))


# ═════════════════════════════════════════════════════════════════════════════
#  PAGES
# ═════════════════════════════════════════════════════════════════════════════

class NavPage(QWidget):
    """Scrolling live sensor-telemetry feed (from main2.py)."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        header = QLabel("STELLAR CARTOGRAPHY  —  SECTOR 001-ALPHA")
        header.setStyleSheet(
            f"color: {GOLD}; font-size: 20px; font-family: 'Arial Narrow'; font-weight: bold;"
        )
        header.setAlignment(Qt.AlignRight)
        layout.addWidget(header)

        self.feed = QTextEdit()
        self.feed.setReadOnly(True)
        self.feed.setFrameStyle(QFrame.NoFrame)
        self.feed.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_BLACK}; color: {LIGHT_BLUE};
                font-family: 'Courier New'; font-size: 13px;
                border: 1px solid {TANGERINE}; border-radius: 5px;
            }}
            QScrollBar:vertical {{ width: 0px; }}
        """)
        layout.addWidget(self.feed)

        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(200)

    def _tick(self):
        prefix = random.choice(["TRN", "SUB", "VEC", "MAG", "GRV", "ION", "PLZ"])
        val1   = random.randint(1000, 9999)
        val2   = random.random() * 100
        status = random.choices(["STABLE", "NOMINAL", "WARNING"], weights=[6, 3, 1])[0]
        color  = LIGHT_BLUE if status != "WARNING" else "#FF6644"
        self.feed.append(
            f'<span style="color:{color}">{prefix}-{val1} : {status} : {val2:.4f} m/s²</span>'
        )
        sb = self.feed.verticalScrollBar()
        sb.setValue(sb.maximum())


class EngPage(QWidget):
    """System monitoring — CPU, memory, simulated plasma conduit (from main.py)."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header = QLabel("ENGINEERING  —  WARP CORE STATUS")
        header.setStyleSheet(
            f"color: {GOLD}; font-size: 20px; font-family: 'Arial Narrow'; font-weight: bold;"
        )
        header.setAlignment(Qt.AlignRight)
        layout.addWidget(header)

        def make_bar(label_text, color):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(220)
            lbl.setStyleSheet(
                f"color: {LIGHT_BLUE}; font-family: 'Arial Narrow'; font-size: 14px;"
            )
            bar = QProgressBar()
            bar.setTextVisible(True)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: #111; border: 1px solid {color};
                    border-radius: 5px; color: white;
                    font-family: 'Arial Narrow'; text-align: center;
                }}
                QProgressBar::chunk {{ background-color: {color}; border-radius: 4px; }}
            """)
            row.addWidget(lbl)
            row.addWidget(bar)
            layout.addLayout(row)
            return bar

        self.cpu_bar  = make_bar("WARP CORE OUTPUT   (CPU)", LILAC)
        self.mem_bar  = make_bar("DEUTERIUM RESERVE  (MEM)", TANGERINE)
        self.warp_bar = make_bar("PLASMA CONDUIT     (SIM)", GOLD)
        layout.addStretch()

        self._warp_val = 50
        self._warp_dir = 1
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self):
        self.cpu_bar.setValue(int(psutil.cpu_percent()))
        self.mem_bar.setValue(int(psutil.virtual_memory().percent))
        self._warp_val = max(10, min(99,
            self._warp_val + self._warp_dir * random.randint(1, 5)))
        if self._warp_val >= 99 or self._warp_val <= 10:
            self._warp_dir *= -1
        self.warp_bar.setValue(self._warp_val)


class TacPage(QWidget):
    """Sound-enabled 4×4 tactical keypad (from main5.py)."""
    def __init__(self, player):
        super().__init__()
        layout = QVBoxLayout(self)

        header = QLabel("TACTICAL CONSOLE  —  WEAPONS ARRAY")
        header.setStyleSheet(
            f"color: {GOLD}; font-size: 20px; font-family: 'Arial Narrow'; font-weight: bold;"
        )
        header.setAlignment(Qt.AlignRight)
        layout.addWidget(header)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(6)

        colors = [TANGERINE, LILAC, LIGHT_BLUE, GOLD]
        for row in range(4):
            for col in range(4):
                btn = LcarsKey(
                    str(random.randint(100, 999)),
                    colors[row % len(colors)],
                    player
                )
                grid.addWidget(btn, row, col)

        layout.addWidget(grid_widget, alignment=Qt.AlignCenter)
        layout.addStretch()


# ═════════════════════════════════════════════════════════════════════════════
#  BOOT SCREEN  (from main3.py)
# ═════════════════════════════════════════════════════════════════════════════

class BootScreen(QWidget):
    boot_complete = Signal()

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {BG_BLACK};")
        layout = QHBoxLayout(self)

        # Animated sidebar
        sidebar_widget = QWidget()
        sidebar_widget.setFixedWidth(170)
        self._sidebar = QVBoxLayout(sidebar_widget)
        self._sidebar.setContentsMargins(5, 0, 5, 5)
        self._sidebar.setSpacing(6)

        self._elbow = QFrame()
        self._elbow.setFixedWidth(160)
        self._elbow.setStyleSheet(
            f"background-color: {TANGERINE}; border-top-left-radius: 40px;"
        )
        self._sidebar.addWidget(self._elbow)

        self._boot_lbls = []
        for label in ["SYS-CORE", "NAV-ARRAY", "ENG-GRID", "TAC-MODULE", "VOICE-AI"]:
            lbl = QLabel(f"  {label}")
            lbl.setMinimumHeight(32)
            lbl.setStyleSheet(f"""
                background-color: {LILAC}; color: black; border-radius: 15px;
                font-family: 'Arial Narrow'; font-weight: bold; font-size: 13px;
            """)
            lbl.hide()
            self._sidebar.addWidget(lbl)
            self._boot_lbls.append(lbl)
        self._sidebar.addStretch()
        layout.addWidget(sidebar_widget)

        # Boot log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFrameStyle(QFrame.NoFrame)
        self.log.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_BLACK}; color: {LIGHT_BLUE};
                font-family: 'Courier New'; font-size: 13px; border: none;
            }}
        """)
        layout.addWidget(self.log)

        # Elbow grow animation
        self._elbow_anim = QPropertyAnimation(self._elbow, b"minimumHeight")
        self._elbow_anim.setDuration(700)
        self._elbow_anim.setStartValue(0)
        self._elbow_anim.setEndValue(100)
        self._elbow_anim.setEasingCurve(QEasingCurve.OutExpo)

        self._btn_idx = 0
        self._btn_timer = QTimer()
        self._btn_timer.timeout.connect(self._reveal_next)

        QTimer.singleShot(300, self._start)

    def _start(self):
        self.log.append(
            f'<span style="color:{GOLD}">▶ INITIALIZING LCARS INTERFACE v7.4.2...</span>'
        )
        self._elbow_anim.start()
        self._btn_timer.start(280)

    def _reveal_next(self):
        if self._btn_idx < len(self._boot_lbls):
            lbl = self._boot_lbls[self._btn_idx]
            lbl.show()
            self.log.append(
                f'<span style="color:{LIGHT_BLUE}">  SUBSYSTEM {lbl.text().strip()} '
                f'... <span style="color:#66FF66">ONLINE</span></span>'
            )
            self._btn_idx += 1
        else:
            self._btn_timer.stop()
            self.log.append(
                f'<span style="color:{GOLD}">▶ ALL SYSTEMS NOMINAL. LCARS READY.</span>'
            )
            QTimer.singleShot(800, self.boot_complete.emit)


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN INTERFACE
# ═════════════════════════════════════════════════════════════════════════════

class LcarsInterface(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {BG_BLACK}; color: white;")

        # Audio
        self.player = QMediaPlayer()
        self._audio_out = QAudioOutput()
        self.player.setAudioOutput(self._audio_out)
        self._audio_out.setVolume(0.5)
        sound = resource_path("sounds/computerbeep_4.mp3")
        if not os.path.exists(sound):
            sound = resource_path("beep.mp3")
        self.player.setSource(QUrl.fromLocalFile(sound))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Top bar ──────────────────────────────────────────────────────────
        top_bar = QWidget()
        top_bar.setFixedHeight(40)
        top_bar.setStyleSheet(f"background-color: {TANGERINE};")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 0, 10, 0)

        ship_lbl = QLabel("USS PYSIDE6  —  NCC-1701")
        ship_lbl.setStyleSheet(
            "color: black; font-family: 'Arial Narrow'; font-weight: bold; font-size: 16px;"
        )
        self._stardate_lbl = QLabel()
        self._stardate_lbl.setStyleSheet(
            "color: black; font-family: 'Arial Narrow'; font-size: 14px;"
        )
        top_layout.addWidget(ship_lbl)
        top_layout.addStretch()
        top_layout.addWidget(self._stardate_lbl)
        outer.addWidget(top_bar)

        # ── Body ─────────────────────────────────────────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Sidebar
        sidebar_widget = QWidget()
        sidebar_widget.setFixedWidth(175)
        sidebar_widget.setStyleSheet(f"background-color: {BG_BLACK};")
        sidebar = QVBoxLayout(sidebar_widget)
        sidebar.setContentsMargins(5, 0, 5, 5)
        sidebar.setSpacing(6)

        sidebar.addWidget(LcarsHollowElbow(TANGERINE))

        self._nav_btn = LcarsButton("NAVIGATION",  LIGHT_BLUE)
        self._eng_btn = LcarsButton("ENGINEERING", LILAC)
        self._tac_btn = LcarsButton("TACTICAL",    TANGERINE)
        sidebar.addWidget(self._nav_btn)
        sidebar.addWidget(self._eng_btn)
        sidebar.addWidget(self._tac_btn)
        sidebar.addStretch()

        self._voice_lbl = QLabel("  VOICE: ACTIVE")
        self._voice_lbl.setStyleSheet(
            "color: #66FF66; font-family: 'Arial Narrow'; font-size: 11px;"
        )
        sidebar.addWidget(self._voice_lbl)

        exit_btn = LcarsButton("EXIT", GOLD)
        exit_btn.clicked.connect(self._safe_exit)
        sidebar.addWidget(exit_btn)

        body.addWidget(sidebar_widget)

        # Pages
        self._stack = QStackedWidget()
        self._stack.addWidget(NavPage())
        self._stack.addWidget(EngPage())
        self._stack.addWidget(TacPage(self.player))
        body.addWidget(self._stack)

        outer.addLayout(body)

        # ── Wire up ───────────────────────────────────────────────────────────
        self._nav_btn.clicked.connect(lambda: self._change_page(0))
        self._eng_btn.clicked.connect(lambda: self._change_page(1))
        self._tac_btn.clicked.connect(lambda: self._change_page(2))

        self._sd_timer = QTimer()
        self._sd_timer.timeout.connect(self._update_stardate)
        self._sd_timer.start(1000)
        self._update_stardate()

        self._voice = VoiceWorker()
        self._voice.command_received.connect(self._handle_voice)
        self._voice.error_occurred.connect(self._voice_error)
        self._voice.start()

    def _change_page(self, index):
        self.player.stop()
        self.player.play()
        self._stack.setCurrentIndex(index)

    def _update_stardate(self):
        now = datetime.datetime.now()
        stardate = 2026 + (now.timetuple().tm_yday / 365.0)
        self._stardate_lbl.setText(
            f"STARDATE  {stardate:.1f}   {now.strftime('%H:%M:%S')}"
        )

    def _handle_voice(self, cmd):
        if "engineering" in cmd:
            self._change_page(1)
        elif "tactical" in cmd:
            self._change_page(2)
        elif "navigation" in cmd:
            self._change_page(0)
        elif "exit" in cmd or "quit" in cmd:
            self._safe_exit()

    def _voice_error(self, _msg):
        self._voice_lbl.setText("  VOICE: OFFLINE")
        self._voice_lbl.setStyleSheet(
            "color: #FF6644; font-family: 'Arial Narrow'; font-size: 11px;"
        )

    def _safe_exit(self):
        self._voice.quit()
        self.close()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self._safe_exit()
        elif key == Qt.Key_1:
            self._change_page(0)
        elif key == Qt.Key_2:
            self._change_page(1)
        elif key == Qt.Key_3:
            self._change_page(2)


# ═════════════════════════════════════════════════════════════════════════════
#  ROOT APP  — boot screen → main interface
# ═════════════════════════════════════════════════════════════════════════════

class LcarsApp(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LCARS")
        self._boot = BootScreen()
        self._main = LcarsInterface()
        self.addWidget(self._boot)
        self.addWidget(self._main)
        self._boot.boot_complete.connect(self._show_main)

    def _show_main(self):
        self.setCurrentWidget(self._main)
        self._main.setFocus()


if __name__ == "__main__":
    import PySide6
    plugin_path = os.path.join(os.path.dirname(PySide6.__file__), "plugins")
    os.environ["QT_PLUGIN_PATH"] = plugin_path
    app = QApplication(sys.argv)
    window = LcarsApp()
    window.setWindowFlags(Qt.FramelessWindowHint)
    window.showFullScreen()
    sys.exit(app.exec())