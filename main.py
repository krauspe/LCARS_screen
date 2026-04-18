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
import pygame
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QThread, Signal
from PySide6.QtGui import QPainter, QPainterPath, QColor, QPen, QRadialGradient, QBrush, QFont

# ── PALETTE ──────────────────────────────────────────────────────────────────
TANGERINE  = "#FF9966"
LILAC      = "#CC99CC"
GOLD       = "#FFCC00"
LIGHT_BLUE = "#99CCFF"
BG_BLACK   = "#000000"

# ── AUDIO ────────────────────────────────────────────────────────────────────
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.mixer.init()

class Beeper:
    """Thin wrapper around pygame.mixer.Sound for one-shot beep playback."""
    def __init__(self, filepath):
        self._sound = None
        if os.path.exists(filepath):
            try:
                self._sound = pygame.mixer.Sound(filepath)
                self._sound.set_volume(0.5)
            except Exception:
                pass

    def play(self):
        if self._sound:
            self._sound.stop()
            self._sound.play()

    def stop(self):
        if self._sound:
            self._sound.stop()


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
            import traceback
            self.error_occurred.emit(traceback.format_exc())


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


class SysPage(QWidget):
    """System core — primary overview dashboard."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header = QLabel("SYS-CORE  —  PRIMARY SYSTEMS OVERVIEW")
        header.setStyleSheet(
            f"color: {GOLD}; font-size: 20px; font-family: 'Arial Narrow'; font-weight: bold;"
        )
        header.setAlignment(Qt.AlignRight)
        layout.addWidget(header)

        self.info = QTextEdit()
        self.info.setReadOnly(True)
        self.info.setFrameStyle(QFrame.NoFrame)
        self.info.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_BLACK}; color: {LIGHT_BLUE};
                font-family: 'Courier New'; font-size: 13px;
                border: 1px solid {LILAC}; border-radius: 5px;
            }}
            QScrollBar:vertical {{ width: 0px; }}
        """)
        layout.addWidget(self.info)

        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(2000)
        self._tick()

    def _tick(self):
        self.info.clear()
        now  = datetime.datetime.now()
        cpu  = psutil.cpu_percent()
        mem  = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        for line in [
            f'<span style="color:{GOLD}">▶ LCARS SYSTEM STATUS — {now.strftime("%Y-%m-%d %H:%M:%S")}</span>',
            f'<span style="color:{LIGHT_BLUE}">  CPU UTILIZATION ....... {cpu:.1f}%</span>',
            f'<span style="color:{LIGHT_BLUE}">  MEMORY USED ........... {mem.percent:.1f}%'
            f'  ({mem.used // 1024**2} MB / {mem.total // 1024**2} MB)</span>',
            f'<span style="color:{LIGHT_BLUE}">  DISK UTILIZATION ...... {disk.percent:.1f}%</span>',
            f'<span style="color:#66FF66">  ALL PRIMARY SYSTEMS ... NOMINAL</span>',
        ]:
            self.info.append(line)


# ═════════════════════════════════════════════════════════════════════════════
#  WARP FIELD PAGE
# ═════════════════════════════════════════════════════════════════════════════

class WarpPage(QWidget):
    """LCARS Warp Field Output — fully custom-painted, matching the canonical display."""

    _SMIN = 10
    _SMAX = 120

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {BG_BLACK};")

        # 4 coil levels (10-120 scale)
        self._levels  = [96.0, 101.0, 97.0, 91.0]
        self._targets = [96.0, 101.0, 97.0, 91.0]

        # Stripe scroll offset 0–1
        self._scroll   = 0.0
        self._warp_out = 206

        # Scrolling data rows (top readout)
        self._data = [self._gen_row() for _ in range(4)]

        # Left sidebar labels
        self._labels = [
            f"{i:02d}-{random.randint(10000, 99999)}" for i in range(2, 14)
        ]

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)   # 20 fps

    @staticmethod
    def _gen_row():
        return "  ".join(str(random.randint(1, 99999999)) for _ in range(9))

    def _tick(self):
        self._scroll = (self._scroll + 0.04) % 1.0
        for i in range(4):
            self._targets[i] += random.uniform(-0.6, 0.6)
            self._targets[i] = max(82.0, min(113.0, self._targets[i]))
            diff = self._targets[i] - self._levels[i]
            self._levels[i] += diff * 0.10 + random.uniform(-0.15, 0.15)
        self._warp_out = int(200 + sum(self._levels) / 4 * 0.25)
        if random.random() < 0.2:
            self._data.pop(0)
            self._data.append(self._gen_row())
        self.update()

    # ── paint dispatch ────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()

        HDR_H = max(80,  int(H * 0.22))
        SEP_H = max(12,  int(H * 0.038))
        SEP_Y = HDR_H
        MTR_Y = SEP_Y + SEP_H + 6
        MTR_H = H - MTR_Y - 4

        self._paint_header(p, W, HDR_H)
        self._paint_separator(p, W, SEP_Y, SEP_H)
        self._paint_meters(p, W, MTR_Y, MTR_H)
        p.end()

    # ── header ────────────────────────────────────────────────────────────────
    def _paint_header(self, p, W, H):
        LBL_W = max(90, int(W * 0.11))

        # Blue/lavender left panel
        p.fillRect(0, 0, LBL_W, H, QColor(130, 130, 200))

        lbl_font = QFont("Arial Narrow", 9, QFont.Bold)
        p.setFont(lbl_font)
        p.setPen(QPen(QColor(BG_BLACK)))
        p.drawText(4,  6, LBL_W - 8, 18, Qt.AlignLeft | Qt.AlignVCenter, "LCARS 23295")
        p.drawText(4, 28, LBL_W - 8, 18, Qt.AlignLeft | Qt.AlignVCenter, "01-23564")

        # Scrolling data numbers
        data_font = QFont("Courier New", 13, QFont.Bold)
        p.setFont(data_font)
        p.setPen(QPen(QColor(GOLD)))
        row_h = max(14, (H - 8) // max(1, len(self._data)))
        for i, row in enumerate(self._data):
            p.drawText(LBL_W + 6, 4 + i * row_h,
                       int(W * 0.52), row_h,
                       Qt.AlignLeft | Qt.AlignVCenter, row)

        # Title
        tsz = max(14, int(H * 0.18))
        p.setFont(QFont("Arial Narrow", tsz, QFont.Bold))
        p.setPen(QPen(QColor(GOLD)))
        p.drawText(int(W * 0.47), 2, int(W * 0.53) - 10, int(H * 0.52),
                   Qt.AlignRight | Qt.AlignTop,
                   f"WARP FIELD OUTPUT {self._warp_out}")

        # Buttons (top-right)
        BW  = max(80, int(W * 0.10))
        BH  = max(20, int(H * 0.26))
        BY  = int(H * 0.52)
        GAP = 6
        p.fillRect(W - BW * 2 - GAP * 2, BY,              BW, BH, QColor("#9090CC"))
        p.fillRect(W - BW - GAP,          BY,              BW, BH, QColor(TANGERINE))
        p.fillRect(W - BW - GAP,          BY + BH + GAP,   BW, BH, QColor(LILAC))

        p.setFont(QFont("Arial Narrow", 9, QFont.Bold))
        p.setPen(QPen(QColor(BG_BLACK)))
        p.drawText(W - BW * 2 - GAP * 2, BY,            BW, BH, Qt.AlignCenter, "07-3215")
        p.drawText(W - BW - GAP,          BY,            BW, BH, Qt.AlignCenter, "QUIT")
        p.drawText(W - BW - GAP,          BY + BH + GAP, BW, BH, Qt.AlignCenter, "10-6215")

    # ── separator bands ───────────────────────────────────────────────────────
    def _paint_separator(self, p, W, y, h):
        h1 = h * 2 // 3
        p.fillRect(0, y,      W, h1,     QColor(TANGERINE))
        p.fillRect(0, y + h1, W, h - h1, QColor(LILAC))
        for xp in [int(W * 0.44), int(W * 0.49)]:
            p.fillRect(xp, y,      16, h1,     QColor(GOLD))
            p.fillRect(xp, y + h1, 16, h - h1, QColor(120, 90, 130))

    # ── meters ────────────────────────────────────────────────────────────────
    def _paint_meters(self, p, W, y, h):
        LBL_W = max(90, int(W * 0.12))
        self._paint_sidebar(p, 0, y, LBL_W, h)

        avail = W - LBL_W
        cw    = avail // 4

        specs = [
            (QColor(LIGHT_BLUE), QColor(TANGERINE), False),   # col 0
            (QColor("#AABBEE"),  QColor(GOLD),      True),    # col 1 – special
            (QColor(GOLD),       QColor("#CCCCCC"),  False),   # col 2
            (QColor(GOLD),       QColor("#CCCCCC"),  False),   # col 3
        ]
        for i, (bc, ac, sp) in enumerate(specs):
            self._paint_coil(p, LBL_W + i * cw, y, cw, h,
                             self._levels[i], bc, ac, special=sp)

    def _paint_sidebar(self, p, x, y, w, h):
        n     = len(self._labels)
        row_h = h // (n + 1)
        p.setFont(QFont("Arial Narrow", 9))
        for i, lbl in enumerate(self._labels):
            ly = y + (i + 1) * row_h - row_h // 2
            bg = QColor(TANGERINE) if i in (3, 8) else QColor(LIGHT_BLUE)
            p.fillRect(x + 2, ly - 10, w - 8, 18, bg)
            p.setPen(QPen(QColor(BG_BLACK)))
            p.drawText(x + 2, ly - 10, w - 8, 18,
                       Qt.AlignRight | Qt.AlignVCenter, lbl)
            p.setPen(QPen(QColor(LILAC), 1))
            p.drawLine(w - 2, ly, w + 2, ly)

    def _paint_coil(self, p, x, y, w, h, level, bar_color, arrow_color, special=False):
        sr    = self._SMAX - self._SMIN
        SCL_W = max(26, int(w * 0.28))
        ARW_W = max(14, int(w * 0.14))
        PAD   = 3
        cx1   = x + SCL_W
        cw    = w - SCL_W - ARW_W - PAD
        cy1   = y + PAD
        ch    = h - PAD * 2

        # Column background
        p.fillRect(cx1, cy1, cw, ch, QColor(10, 10, 18))

        # Level pixel position (top = scale_min, bottom = scale_max)
        t_lvl = max(0.0, min(1.0, (level - self._SMIN) / sr))
        lvl_y = cy1 + int(t_lvl * ch)

        # ── Animated coil stripes ─────────────────────────────────────────────
        N_BARS = 6 if special else 5
        bar_w  = max(4, (cw - 6 - (N_BARS - 1) * 2) // N_BARS)
        SEG_H  = 9
        SEG_G  = 2
        soff   = int(self._scroll * (SEG_H + SEG_G)) % (SEG_H + SEG_G)

        for bi in range(N_BARS):
            bx = cx1 + 3 + bi * (bar_w + 2)
            sy = cy1 - soff
            while sy < cy1 + ch:
                top = max(sy, cy1)
                bot = min(sy + SEG_H, cy1 + ch)
                if bot > top:
                    mid = (top + bot) / 2
                    if mid <= lvl_y:
                        dist = lvl_y - mid
                        brt  = max(0.25, 1.0 - dist / (ch * 0.45))
                        c    = QColor(bar_color)
                        c.setAlpha(int(70 + 165 * brt))
                    else:
                        c = QColor(bar_color)
                        c.setAlpha(22)
                    p.fillRect(bx, top, bar_w, bot - top, c)
                sy += SEG_H + SEG_G

        # ── Warp-core overlay (2nd column) ────────────────────────────────────
        if special:
            mid_x  = cx1 + cw // 2
            bh     = max(6, int(cw * 0.12))
            xbar_h = max(8, int(ch * 0.05))
            # Top & bottom cross-bars
            p.fillRect(cx1 + 2, cy1 + int(ch * 0.10), cw - 4, xbar_h,
                       QColor(140, 160, 210, 150))
            p.fillRect(cx1 + 2, cy1 + int(ch * 0.84), cw - 4, xbar_h,
                       QColor(140, 160, 210, 150))
            # Center vertical shaft
            p.fillRect(mid_x - bh, cy1 + int(ch * 0.15),
                       bh * 2, int(ch * 0.69), QColor(80, 100, 180, 60))
            # Red diamond at level
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor("#CC2222")))
            dp = QPainterPath()
            dp.moveTo(mid_x,      lvl_y - 11)
            dp.lineTo(mid_x + 16, lvl_y)
            dp.lineTo(mid_x,      lvl_y + 11)
            dp.lineTo(mid_x - 16, lvl_y)
            dp.closeSubpath()
            p.drawPath(dp)

        # ── Bracket frame ─────────────────────────────────────────────────────
        p.setPen(QPen(QColor(TANGERINE), 2))
        p.setBrush(Qt.NoBrush)
        arm = max(12, int(ch * 0.07))
        cx2 = cx1 + cw
        p.drawLine(cx1 - 1, cy1 + arm,          cx1 - 1, cy1)
        p.drawLine(cx1 - 1, cy1,                 cx2,     cy1)
        p.drawLine(cx2,     cy1,                 cx2,     cy1 + arm)
        p.drawLine(cx1 - 1, cy1 + ch - arm,     cx1 - 1, cy1 + ch)
        p.drawLine(cx1 - 1, cy1 + ch,            cx2,     cy1 + ch)
        p.drawLine(cx2,     cy1 + ch,            cx2,     cy1 + ch - arm)

        # ── Scale markers ─────────────────────────────────────────────────────
        p.setFont(QFont("Arial Narrow", 9))
        p.setPen(QPen(QColor(190, 190, 190)))
        for val in range(self._SMIN, self._SMAX + 1, 10):
            t  = (val - self._SMIN) / sr
            vy = cy1 + int(t * ch)
            p.drawLine(cx1 - 7, vy, cx1 - 1, vy)
            p.drawText(x, vy - 7, SCL_W - 9, 14,
                       Qt.AlignRight | Qt.AlignVCenter, f"— {val}")

        # ── Arrow indicator ───────────────────────────────────────────────────
        ax = cx2 + PAD + 1
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(arrow_color))
        ap = QPainterPath()
        ap.moveTo(ax + ARW_W, lvl_y - 9)
        ap.lineTo(ax + 1,     lvl_y)
        ap.lineTo(ax + ARW_W, lvl_y + 9)
        ap.closeSubpath()
        p.drawPath(ap)


class VoicePage(QWidget):
    """Voice AI — command log and recognition status."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        header = QLabel("VOICE-AI  —  COMMAND INTERFACE")
        header.setStyleSheet(
            f"color: {GOLD}; font-size: 20px; font-family: 'Arial Narrow'; font-weight: bold;"
        )
        header.setAlignment(Qt.AlignRight)
        layout.addWidget(header)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFrameStyle(QFrame.NoFrame)
        self.log.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_BLACK}; color: {LIGHT_BLUE};
                font-family: 'Courier New'; font-size: 13px;
                border: 1px solid {GOLD}; border-radius: 5px;
            }}
            QScrollBar:vertical {{ width: 0px; }}
        """)
        layout.addWidget(self.log)
        self.log.append(
            f'<span style="color:{LILAC}">  SAY "COMPUTER ..." TO ISSUE A COMMAND</span>'
        )
        self.log.append(
            f'<span style="color:{LIGHT_BLUE}">'
            f'  COMMANDS: NAVIGATION · ENGINEERING · TACTICAL · SYSTEM · WARPFIELD · VOICE · EXIT</span>'
        )

    def add_command(self, cmd):
        self.log.append(f'<span style="color:#66FF66">▶ RECEIVED: {cmd.upper()}</span>')
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def set_status(self, online: bool):
        color  = "#66FF66" if online else "#FF6644"
        status = "ONLINE"  if online else "OFFLINE"
        self.log.append(f'<span style="color:{color}">  VOICE SYSTEM: {status}</span>')
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())


# ═════════════════════════════════════════════════════════════════════════════
#  BOOT SCREEN  (from main3.py)
# ═════════════════════════════════════════════════════════════════════════════

class BootScreen(QWidget):
    """Persistent LCARS interface: animated boot, then nav via sidebar buttons."""
    boot_complete = Signal()

    # (label, colour, content-stack index)
    _NAV = [
        ("SYS-CORE",   LILAC,      1),
        ("NAV-ARRAY",  LIGHT_BLUE, 2),
        ("ENG-GRID",   LILAC,      3),
        ("TAC-MODULE", TANGERINE,  4),
        ("WARP-FIELD", LIGHT_BLUE, 5),
        ("VOICE-AI",   GOLD,       6),
    ]

    def __init__(self, player):
        super().__init__()
        self._player = player
        self._diag_sound = Beeper(resource_path("sounds/diagnosticcomplete_ep.mp3"))
        self.setStyleSheet(f"background-color: {BG_BLACK};")

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

        self._elbow = QFrame()
        self._elbow.setFixedWidth(160)
        self._elbow.setStyleSheet(
            f"background-color: {TANGERINE}; border-top-left-radius: 40px;"
        )
        sidebar.addWidget(self._elbow)

        # Nav buttons — hidden/disabled until boot animation brings them online
        self._nav_buttons = []
        for label, color, _ in self._NAV:
            btn = QPushButton(f"  {label}")
            btn.setMinimumHeight(32)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color}; color: black; border-radius: 15px;
                    font-family: 'Arial Narrow'; font-weight: bold; font-size: 13px;
                    text-align: left; border: none;
                }}
                QPushButton:pressed {{ background-color: white; }}
                QPushButton:hover   {{ background-color: white; }}
            """)
            btn.hide()
            btn.setEnabled(False)
            sidebar.addWidget(btn)
            self._nav_buttons.append(btn)

        sidebar.addStretch()

        self._voice_lbl = QLabel("  VOICE: ACTIVE")
        self._voice_lbl.setStyleSheet(
            "color: #66FF66; font-family: 'Arial Narrow'; font-size: 11px;"
        )
        self._voice_lbl.hide()
        sidebar.addWidget(self._voice_lbl)

        self._exit_btn = LcarsButton("EXIT", GOLD)
        self._exit_btn.clicked.connect(self._safe_exit)
        self._exit_btn.hide()
        sidebar.addWidget(self._exit_btn)

        body.addWidget(sidebar_widget)

        # ── Content stack ─────────────────────────────────────────────────────
        self._stack = QStackedWidget()

        # Index 0: boot log (shown only during animation)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFrameStyle(QFrame.NoFrame)
        self.log.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_BLACK}; color: {LIGHT_BLUE};
                font-family: 'Courier New'; font-size: 13px; border: none;
            }}
        """)
        self._stack.addWidget(self.log)           # 0 – boot log

        # Application pages (indices 1-5, matching _NAV)
        self._voice_page = VoicePage()
        self._stack.addWidget(SysPage())          # 1 – SYS-CORE
        self._stack.addWidget(NavPage())          # 2 – NAV-ARRAY
        self._stack.addWidget(EngPage())          # 3 – ENG-GRID
        self._stack.addWidget(TacPage(player))    # 4 – TAC-MODULE
        self._stack.addWidget(WarpPage())         # 5 – WARP-FIELD
        self._stack.addWidget(self._voice_page)   # 6 – VOICE-AI

        body.addWidget(self._stack)
        outer.addLayout(body)

        # Wire nav buttons
        for i, (_, _, stack_idx) in enumerate(self._NAV):
            self._nav_buttons[i].clicked.connect(
                lambda checked, si=stack_idx: self._change_page(si)
            )

        # Elbow grow animation
        self._elbow_anim = QPropertyAnimation(self._elbow, b"minimumHeight")
        self._elbow_anim.setDuration(700)
        self._elbow_anim.setStartValue(0)
        self._elbow_anim.setEndValue(100)
        self._elbow_anim.setEasingCurve(QEasingCurve.OutExpo)

        self._btn_idx = 0
        self._btn_timer = QTimer()
        self._btn_timer.timeout.connect(self._reveal_next)

        # Stardate ticker
        self._sd_timer = QTimer()
        self._sd_timer.timeout.connect(self._update_stardate)
        self._sd_timer.start(1000)
        self._update_stardate()

        # Voice recognition
        self._voice_worker = VoiceWorker()
        self._voice_worker.command_received.connect(self._handle_voice)
        self._voice_worker.error_occurred.connect(self._voice_error)
        self._voice_worker.start()

        QTimer.singleShot(300, self._start)

    def _start(self):
        self.log.append(
            f'<span style="color:{GOLD}">▶ INITIALIZING LCARS INTERFACE v7.4.2...</span>'
        )
        self._elbow_anim.start()
        self._btn_timer.start(280)

    def _reveal_next(self):
        if self._btn_idx < len(self._nav_buttons):
            btn = self._nav_buttons[self._btn_idx]
            btn.show()
            self.log.append(
                f'<span style="color:{LIGHT_BLUE}">  SUBSYSTEM {btn.text().strip()} '
                f'... <span style="color:#66FF66">ONLINE</span></span>'
            )
            self._btn_idx += 1
        else:
            self._btn_timer.stop()
            self.log.append(
                f'<span style="color:{GOLD}">▶ ALL SYSTEMS NOMINAL. LCARS READY.</span>'
            )
            QTimer.singleShot(800, self._boot_done)

    def _boot_done(self):
        for btn in self._nav_buttons:
            btn.setEnabled(True)
        self._voice_lbl.show()
        self._exit_btn.show()
        self._change_page(1)   # default: SYS-CORE
        ready_sound = Beeper(resource_path("sounds/programinitiatedenterwhenready_ep.mp3"))
        QTimer.singleShot(300, ready_sound.play)
        self._ready_sound = ready_sound  # keep reference alive
        self.boot_complete.emit()

    def _change_page(self, stack_index):
        self._player.play()
        self._stack.setCurrentIndex(stack_index)
        if stack_index == 3:  # ENG-GRID
            QTimer.singleShot(2000, self._play_diag_complete)

    def _play_diag_complete(self):
        # Only play if still on ENG-GRID
        if self._stack.currentIndex() == 3:
            self._diag_sound.play()


    def _update_stardate(self):
        now = datetime.datetime.now()
        stardate = 2026 + (now.timetuple().tm_yday / 365.0)
        self._stardate_lbl.setText(
            f"STARDATE  {stardate:.1f}   {now.strftime('%H:%M:%S')}"
        )

    def _handle_voice(self, cmd):
        self._voice_page.add_command(cmd)
        if "engineering" in cmd:
            self._change_page(3)
        elif "tactical" in cmd:
            self._change_page(4)
        elif "navigation" in cmd:
            self._change_page(2)
        elif "system" in cmd or "core" in cmd:
            self._change_page(1)
        elif "warpfield" in cmd or "warp field" in cmd:
            self._change_page(5)
        elif "warp" in cmd:
            self._change_page(5)
        elif "voice" in cmd:
            self._change_page(6)
        elif "exit" in cmd or "quit" in cmd:
            self._safe_exit()

    def _voice_error(self, msg):
        self._voice_lbl.setText("  VOICE: OFFLINE")
        self._voice_lbl.setStyleSheet(
            "color: #FF6644; font-family: 'Arial Narrow'; font-size: 11px;"
        )
        self._voice_page.set_status(False)
        if msg:
            self._voice_page.log.append(
                f'<span style="color:#FF6644">  ERROR: {msg}</span>'
            )

    def _safe_exit(self):
        self._voice_worker.quit()
        self.window().close()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self._safe_exit()
        elif key == Qt.Key_1:
            self._change_page(1)
        elif key == Qt.Key_2:
            self._change_page(2)
        elif key == Qt.Key_3:
            self._change_page(3)
        elif key == Qt.Key_4:
            self._change_page(4)
        elif key == Qt.Key_5:
            self._change_page(5)
        elif key == Qt.Key_6:
            self._change_page(6)


# ═════════════════════════════════════════════════════════════════════════════
#  ROOT APP
# ═════════════════════════════════════════════════════════════════════════════

class LcarsApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LCARS")

        sound = resource_path("sounds/computerbeep_26.mp3")
        player = Beeper(sound)
        self._player = player

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._screen = BootScreen(player)
        layout.addWidget(self._screen)


if __name__ == "__main__":
    import PySide6
    plugin_path = os.path.join(os.path.dirname(PySide6.__file__), "plugins")
    os.environ["QT_PLUGIN_PATH"] = plugin_path
    app = QApplication(sys.argv)
    window = LcarsApp()
    window.setWindowFlags(Qt.FramelessWindowHint)
    window.showFullScreen()
    sys.exit(app.exec())