import sys
import os
import random
import datetime
import math
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False

    def stop(self):
        self._running = False

    def run(self):
        self._running = True
        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)
                while self._running:
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
#  STELLAR NAVIGATION CHART
# ═════════════════════════════════════════════════════════════════════════════

class StellarChartWidget(QWidget):
    """Animated stellar navigation chart: stars, planets, galaxies, starbases,
    nebulae, wormholes, trajectories with travelling blips, and flashing points."""

    _CATALOG = [
        # Stars
        {"type": "star",     "name": "ALGOL-7",    "nx": 0.15, "ny": 0.20, "drift": 0.0, "color": "#FFFFFF", "size": 5},
        {"type": "star",     "name": "VEGA-III",   "nx": 0.72, "ny": 0.14, "drift": 0.3, "color": "#FFFFAA", "size": 4},
        {"type": "star",     "name": "RIGEL-II",   "nx": 0.55, "ny": 0.68, "drift": 0.0, "color": "#FFDDAA", "size": 6},
        {"type": "star",     "name": "SIRIUS-A",   "nx": 0.85, "ny": 0.42, "drift": 0.2, "color": "#AACCFF", "size": 3},
        {"type": "star",     "name": "PROXIMA",    "nx": 0.30, "ny": 0.78, "drift": 0.0, "color": "#FFBB88", "size": 4},
        # Planets
        {"type": "planet",   "name": "KAITOS-IV",  "nx": 0.25, "ny": 0.35, "drift": 0.5, "color": "#3399FF", "size": 10},
        {"type": "planet",   "name": "MIRA-II",    "nx": 0.62, "ny": 0.55, "drift": 0.0, "color": "#66CC44", "size": 12},
        {"type": "planet",   "name": "DELPHI-IX",  "nx": 0.45, "ny": 0.22, "drift": 0.4, "color": "#CC4422", "size":  8},
        {"type": "planet",   "name": "ORIN-V",     "nx": 0.78, "ny": 0.75, "drift": 0.0, "color": "#AA8833", "size": 11},
        {"type": "planet",   "name": "LUXOR-I",    "nx": 0.10, "ny": 0.60, "drift": 0.6, "color": "#33BBAA", "size":  9},
        # Galaxies
        {"type": "galaxy",   "name": "M-31",       "nx": 0.90, "ny": 0.20, "drift": 0.0, "color": "#CC66FF", "size": 22},
        {"type": "galaxy",   "name": "NGC-7293",   "nx": 0.18, "ny": 0.88, "drift": 0.0, "color": "#FF99CC", "size": 18},
        # Starbases
        {"type": "starbase", "name": "SB-11",      "nx": 0.50, "ny": 0.45, "drift": 0.0, "color": "#FFCC00", "size": 13},
        {"type": "starbase", "name": "DS-39",      "nx": 0.38, "ny": 0.12, "drift": 0.0, "color": "#00FFFF", "size": 11},
        # Nebulae (rendered first, underneath all)
        {"type": "nebula",   "name": "CYGNUS-NEB", "nx": 0.65, "ny": 0.30, "drift": 0.0, "color": "#8833CC", "size": 45},
        {"type": "nebula",   "name": "LYRA-RIFT",  "nx": 0.20, "ny": 0.55, "drift": 0.0, "color": "#003388", "size": 38},
        # Wormhole
        {"type": "wormhole", "name": "WH-ALPHA",   "nx": 0.82, "ny": 0.58, "drift": 0.0, "color": "#FF00FF", "size": 16},
    ]

    # Quadratic bezier trajectories: (nx0,ny0, ctrl_nx,ctrl_ny, nx1,ny1, label, color)
    _TRAJECTORIES = [
        (0.50, 0.45, 0.40, 0.30, 0.25, 0.35, "COURSE-α", TANGERINE),
        (0.38, 0.12, 0.55, 0.25, 0.62, 0.55, "TRJ-07",   LILAC),
        (0.82, 0.58, 0.78, 0.68, 0.78, 0.75, "TRJ-12",   LIGHT_BLUE),
        (0.10, 0.60, 0.30, 0.65, 0.50, 0.45, "ROUTE-Σ",  TANGERINE),
        (0.15, 0.20, 0.25, 0.10, 0.38, 0.12, "VEC-03",   LILAC),
    ]

    _N_FLASH = 18

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self._phase = 0.0

        # Seeded RNG for stable initial positions
        rng = random.Random(42)
        self._flash_pts = []
        for _ in range(self._N_FLASH):
            self._flash_pts.append({
                "nx":        rng.uniform(0.03, 0.97),
                "ny":        rng.uniform(0.03, 0.97),
                "phase":     rng.uniform(0, 2 * math.pi),
                "speed":     rng.uniform(1.5, 4.0),
                "hue":       rng.uniform(0, 360),
                "hue_drift": rng.uniform(0.5, 2.0) * rng.choice([-1, 1]),
                "jump_cd":   rng.randint(8, 24),
                "jump_t":    0,
            })

        # Blip positions along each trajectory (staggered starts)
        n = len(self._TRAJECTORIES)
        self._blip_t     = [i / n for i in range(n)]
        self._blip_speed = [0.0030, 0.0025, 0.0040, 0.0028, 0.0035]

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(50)

    def _step(self):
        self._phase = (self._phase + 0.06) % (2 * math.pi)

        for i in range(len(self._blip_t)):
            self._blip_t[i] = (self._blip_t[i] + self._blip_speed[i]) % 1.0

        for fp in self._flash_pts:
            fp["hue"] = (fp["hue"] + fp["hue_drift"]) % 360
            fp["jump_t"] += 1
            if fp["jump_t"] >= fp["jump_cd"]:
                fp["hue"]       = random.uniform(0, 360)
                fp["hue_drift"] = random.uniform(0.5, 3.0) * random.choice([-1, 1])
                fp["jump_cd"]   = random.randint(8, 30)
                fp["jump_t"]    = 0

        self.update()

    def _map(self, nx, ny, margin=14):
        """Map normalised [0,1] → widget pixel coords respecting margin."""
        w = self.width()  - margin * 2
        h = self.height() - margin * 2
        return margin + nx * w, margin + ny * h

    @staticmethod
    def _bezier(t, p0, ctrl, p1):
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * ctrl[0] + t ** 2 * p1[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * ctrl[1] + t ** 2 * p1[1]
        return x, y

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(BG_BLACK))

        margin = 14
        W, H   = self.width(), self.height()

        # ── Grid overlay ──────────────────────────────────────────────────────
        gc = QColor(LIGHT_BLUE)
        gc.setAlpha(25)
        p.setPen(QPen(gc, 1))
        step = 72
        x = margin
        while x < W - margin:
            p.drawLine(int(x), margin, int(x), H - margin)
            x += step
        y = margin
        while y < H - margin:
            p.drawLine(margin, int(y), W - margin, int(y))
            y += step

        # Sector corner labels
        p.setFont(QFont("Arial Narrow", 7))
        lc = QColor(LIGHT_BLUE)
        lc.setAlpha(80)
        p.setPen(lc)
        p.drawText(margin + 3,  margin + 11, "ALPHA-IV")
        p.drawText(W - margin - 60, margin + 11, "BETA-VII")
        p.drawText(margin + 3,  H - margin - 4, "GAMMA-II")
        p.drawText(W - margin - 60, H - margin - 4, "DELTA-IX")

        # ── Border ────────────────────────────────────────────────────────────
        p.setPen(QPen(QColor(TANGERINE), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(margin, margin, W - margin * 2, H - margin * 2)

        # ── Nebulae (bottom layer) ─────────────────────────────────────────────
        for obj in self._CATALOG:
            if obj["type"] != "nebula":
                continue
            ox, oy = self._map(obj["nx"], obj["ny"], margin)
            sz = obj["size"]
            grad = QRadialGradient(ox, oy, sz)
            c0 = QColor(obj["color"]); c0.setAlpha(55)
            c1 = QColor(obj["color"]); c1.setAlpha(0)
            grad.setColorAt(0.0, c0)
            grad.setColorAt(1.0, c1)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawEllipse(int(ox - sz), int(oy - sz), sz * 2, sz * 2)

        # ── Trajectories ──────────────────────────────────────────────────────
        dash_pen = QPen()
        dash_pen.setWidth(1)
        dash_pen.setStyle(Qt.DashLine)

        for i, (nx0, ny0, ncx, ncy, nx1, ny1, label, col) in enumerate(self._TRAJECTORIES):
            x0, y0 = self._map(nx0, ny0, margin)
            cx, cy = self._map(ncx, ncy, margin)
            x1, y1 = self._map(nx1, ny1, margin)

            dash_pen.setColor(QColor(col))
            p.setPen(dash_pen)
            p.setBrush(Qt.NoBrush)
            path = QPainterPath()
            path.moveTo(x0, y0)
            path.quadTo(cx, cy, x1, y1)
            p.drawPath(path)

            # Trajectory label near control point
            p.setFont(QFont("Arial Narrow", 7))
            p.setPen(QColor(col))
            p.drawText(int(cx) + 4, int(cy) - 3, label)

            # Travelling blip dot
            bx, by = self._bezier(self._blip_t[i], (x0, y0), (cx, cy), (x1, y1))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(col))
            p.drawEllipse(int(bx) - 3, int(by) - 3, 6, 6)

        # ── Catalog objects ───────────────────────────────────────────────────
        font_lbl = QFont("Arial Narrow", 8)

        for obj in self._CATALOG:
            if obj["type"] == "nebula":
                continue

            drift = obj.get("drift", 0.0)
            dpx = math.sin(self._phase * drift) * 4.0 if drift else 0.0
            dpy = math.cos(self._phase * drift * 0.7) * 3.0 if drift else 0.0

            ox, oy = self._map(obj["nx"], obj["ny"], margin)
            ox += dpx
            oy += dpy
            sz   = obj["size"]
            col  = QColor(obj["color"])
            kind = obj["type"]

            if kind == "star":
                alpha = int(180 + 75 * math.sin(self._phase * 1.3 + obj["nx"] * 10))
                col.setAlpha(alpha)
                p.setPen(Qt.NoPen)
                p.setBrush(col)
                p.drawEllipse(int(ox - sz / 2), int(oy - sz / 2), sz, sz)
                glow = QColor(obj["color"]); glow.setAlpha(38)
                p.setBrush(glow)
                p.drawEllipse(int(ox - sz), int(oy - sz), sz * 2, sz * 2)

            elif kind == "planet":
                p.setPen(Qt.NoPen)
                p.setBrush(col)
                p.drawEllipse(int(ox - sz / 2), int(oy - sz / 2), sz, sz)
                hl = QColor("#FFFFFF"); hl.setAlpha(60)
                p.setBrush(hl)
                hs = max(sz // 3, 2)
                p.drawEllipse(int(ox - sz / 2 + 2), int(oy - sz / 2 + 2), hs, hs)

            elif kind == "galaxy":
                rx, ry = sz, int(sz * 0.55)
                p.save()
                p.translate(ox, oy)
                p.rotate(30)
                col.setAlpha(160)
                p.setPen(Qt.NoPen)
                p.setBrush(col)
                p.drawEllipse(-rx, -ry, rx * 2, ry * 2)
                core = QColor("#FFFFFF"); core.setAlpha(200)
                p.setBrush(core)
                p.drawEllipse(-3, -2, 6, 4)
                tick_pen = QPen(QColor(obj["color"]), 1)
                p.setPen(tick_pen)
                for arm in range(4):
                    a = math.radians(arm * 90)
                    p.drawLine(int(5 * math.cos(a)), int(3 * math.sin(a)),
                               int(rx * 0.8 * math.cos(a)), int(ry * 0.8 * math.sin(a)))
                p.restore()

            elif kind == "starbase":
                half = sz // 2
                p.save()
                p.translate(ox, oy)
                p.rotate(45)
                p.setPen(QPen(col, 2))
                p.setBrush(Qt.NoBrush)
                p.drawRect(-half, -half, half * 2, half * 2)
                p.drawLine(-half, 0, half, 0)
                p.drawLine(0, -half, 0, half)
                p.restore()
                blink_a = int(100 + 155 * math.sin(self._phase * 2.5 + obj["nx"] * 5))
                bc = QColor(obj["color"]); bc.setAlpha(blink_a)
                p.setPen(Qt.NoPen)
                p.setBrush(bc)
                p.drawEllipse(int(ox - 2), int(oy - 2), 4, 4)

            elif kind == "wormhole":
                for ring in range(3):
                    r = sz // 2 + ring * 6
                    rc = QColor(obj["color"])
                    rc.setAlpha(220 - ring * 60)
                    rp = QPen(rc, 1)
                    rp.setStyle(Qt.DashLine if ring % 2 == 0 else Qt.DotLine)
                    p.setPen(rp)
                    p.setBrush(Qt.NoBrush)
                    p.drawEllipse(int(ox - r), int(oy - r), r * 2, r * 2)
                pr = int(4 + 3 * math.sin(self._phase * 3))
                cc = QColor(obj["color"]); cc.setAlpha(200)
                p.setPen(Qt.NoPen)
                p.setBrush(cc)
                p.drawEllipse(int(ox - pr), int(oy - pr), pr * 2, pr * 2)

            # Object label
            lc2 = QColor(LIGHT_BLUE); lc2.setAlpha(200)
            p.setPen(lc2)
            p.setFont(font_lbl)
            p.drawText(int(ox) + sz // 2 + 3, int(oy) + 4, obj["name"])

        # ── Flashing colored points ────────────────────────────────────────────
        for fp in self._flash_pts:
            fx, fy = self._map(fp["nx"], fp["ny"], margin)
            brightness = (math.sin(self._phase * fp["speed"] + fp["phase"]) + 1) / 2
            fc = QColor.fromHsvF(fp["hue"] / 360.0, 0.9, 0.95,
                                 brightness * 0.88 + 0.12)
            p.setPen(Qt.NoPen)
            p.setBrush(fc)
            r = max(int(1 + brightness * 2.5), 1)
            p.drawEllipse(int(fx) - r, int(fy) - r, r * 2, r * 2)

        # ── Chart footer label ─────────────────────────────────────────────────
        p.setPen(QColor(GOLD))
        p.setFont(QFont("Arial Narrow", 8, QFont.Bold))
        p.drawText(margin + 4, H - margin - 5, "STELLAR CARTOGRAPHY  ·  LIVE SCAN")


# ═════════════════════════════════════════════════════════════════════════════
#  PAGES
# ═════════════════════════════════════════════════════════════════════════════

class NavPage(QWidget):
    """Scrolling live sensor-telemetry feed + stellar navigation chart."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        header = QLabel("STELLAR CARTOGRAPHY  —  SECTOR 001-ALPHA")
        header.setStyleSheet(
            f"color: {GOLD}; font-size: 20px; font-family: 'Arial Narrow'; font-weight: bold;"
        )
        header.setAlignment(Qt.AlignRight)
        layout.addWidget(header)

        # Body: telemetry feed on the left, chart fills the rest
        body = QHBoxLayout()
        body.setSpacing(8)
        layout.addLayout(body)

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
        self.feed.setFixedWidth(225)
        body.addWidget(self.feed)

        self._chart = StellarChartWidget()
        body.addWidget(self._chart, stretch=1)

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


# ─────────────────────────────────────────────────────────────────────────────
#  ENG-GRID SUPPLEMENTAL WIDGETS
# ─────────────────────────────────────────────────────────────────────────────

class WarpCoreDiagram(QWidget):
    """Animated M/ARA cross-section: concentric coil rings + rotating spokes."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(240, 200)
        self._phase = 0.0
        self._rotor = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(50)

    def _step(self):
        self._phase = (self._phase + 0.08) % (2 * math.pi)
        self._rotor = (self._rotor + 2) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(BG_BLACK))
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        ring_r = min(w // 2, h // 2) - 20

        # --- EPS connector labels around outer ring ---
        eps_labels = ["EPS-01", "EPS-02", "EPS-03", "EPS-04", "EPS-05", "EPS-06"]
        p.setFont(QFont("Arial Narrow", 7))
        p.setPen(QColor(LIGHT_BLUE))
        for i, lbl in enumerate(eps_labels):
            ang = math.radians(-90 + i * 60)
            lx = int(cx + (ring_r + 14) * math.cos(ang)) - 14
            ly = int(cy + (ring_r + 14) * math.sin(ang)) + 4
            p.drawText(lx, ly, lbl)

        # --- concentric rings ---
        ring_specs = [
            (ring_r,            TANGERINE,  2, 0.0),
            (int(ring_r * 0.74), LILAC,     2, 0.5),
            (int(ring_r * 0.52), GOLD,      2, 1.0),
            (int(ring_r * 0.32), LIGHT_BLUE,2, 1.5),
            (int(ring_r * 0.16), "#FF6644", 3, 2.0),
        ]
        for r, clr, lw, offset in ring_specs:
            pulse = 0.35 + 0.65 * abs(math.sin(self._phase + offset))
            c = QColor(clr)
            c.setAlphaF(pulse)
            p.setPen(QPen(c, lw))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # --- rotating spokes ---
        inner_r = int(ring_r * 0.16)
        spoke_r = int(ring_r * 0.52)
        p.setPen(QPen(QColor(GOLD), 1))
        for i in range(6):
            ang = math.radians(self._rotor + i * 60)
            p.drawLine(
                cx + int(inner_r * math.cos(ang)), cy + int(inner_r * math.sin(ang)),
                cx + int(spoke_r * math.cos(ang)), cy + int(spoke_r * math.sin(ang)),
            )

        # --- pulsing inner glow ---
        pulse_c = 0.4 + 0.6 * abs(math.sin(self._phase * 2.5))
        glow_r = int(inner_r * 2.2)
        grad = QRadialGradient(cx, cy, glow_r)
        cc = QColor(LIGHT_BLUE)
        cc.setAlphaF(pulse_c)
        grad.setColorAt(0.0, cc)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2)

        # --- centre dot ---
        p.setBrush(QBrush(QColor("#FF6644")))
        p.drawEllipse(cx - 4, cy - 4, 8, 8)

        # --- title ---
        p.setFont(QFont("Arial Narrow", 8))
        p.setPen(QColor(TANGERINE))
        p.drawText(4, 14, "M/ARA CROSS-SECTION")
        p.end()


class VerticalWarpCoreDiagram(QWidget):
    """Animated vertical warp core — TNG/VOY-style field-coil column."""
    NUM_COILS = 9

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(240, 200)
        self._phase = 0.0
        self._pulse_pos = 0.0
        self._pulse_dir = 1
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(50)

    def _step(self):
        self._phase = (self._phase + 0.06) % (2 * math.pi)
        self._pulse_pos += self._pulse_dir * 0.018
        if self._pulse_pos >= 1.0:
            self._pulse_pos = 1.0
            self._pulse_dir = -1
        elif self._pulse_pos <= 0.0:
            self._pulse_pos = 0.0
            self._pulse_dir = 1
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(BG_BLACK))
        w, h = self.width(), self.height()
        cx = w // 2
        margin_top, margin_bot = 26, 22
        col_hw = max(16, w // 7)
        coil_extra = int(col_hw * 0.65)
        core_top = margin_top
        core_bot = h - margin_bot
        core_h = core_bot - core_top
        cy_mid = core_top + core_h // 2

        # tube shell
        tube_x = cx - col_hw
        tube_w = col_hw * 2
        p.setPen(QPen(QColor(TANGERINE), 2))
        p.setBrush(QBrush(QColor("#040418")))
        p.drawRoundedRect(tube_x, core_top, tube_w, core_h, 6, 6)

        # plasma glow
        glob_pulse = 0.5 + 0.5 * abs(math.sin(self._phase))
        grad = QRadialGradient(cx, cy_mid, col_hw)
        c1 = QColor("#00CCFF"); c1.setAlphaF(0.85 * glob_pulse)
        c2 = QColor("#0033AA"); c2.setAlphaF(0.35)
        c3 = QColor(0, 0, 0, 0)
        grad.setColorAt(0.0, c1); grad.setColorAt(0.5, c2); grad.setColorAt(1.0, c3)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRect(tube_x + 2, core_top + 2, tube_w - 4, core_h - 4)

        # field coil bands
        n, coil_h = self.NUM_COILS, 10
        for i in range(n):
            t = i / (n - 1)
            y = int(core_top + t * (core_h - coil_h))
            dist = abs(t - self._pulse_pos)
            glow = max(0.0, 1.0 - dist * 4.0)
            base = 0.3 + 0.2 * abs(math.sin(self._phase + t * math.pi * 2))
            brightness = min(1.0, base + glow * 0.8)
            coil_c = QColor("#00CCFF"); coil_c.setAlphaF(brightness)
            cx1 = tube_x - coil_extra
            cw  = tube_w + coil_extra * 2
            p.setPen(QPen(coil_c, 2)); p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(cx1, y, cw, coil_h, 3, 3)
            if brightness > 0.5:
                fill_c = QColor("#004488"); fill_c.setAlphaF(brightness * 0.5)
                p.setPen(Qt.NoPen); p.setBrush(fill_c)
                p.drawRoundedRect(cx1 + 1, y + 1, cw - 2, coil_h - 2, 2, 2)
            p.setFont(QFont("Arial Narrow", 7))
            p.setPen(QColor(LIGHT_BLUE))
            label = f"FC-{i+1:02d}"
            if i % 2 == 0:
                p.drawText(cx1 + cw + 4, y + 8, label)
            else:
                p.drawText(max(0, cx1 - 30), y + 8, label)

        # travelling pulse highlight
        py = int(core_top + self._pulse_pos * (core_h - 6))
        pg = QRadialGradient(cx, py, col_hw * 2)
        pc = QColor("#FFFFFF"); pc.setAlphaF(0.5)
        pg.setColorAt(0.0, pc); pg.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen); p.setBrush(QBrush(pg))
        p.drawRect(cx - col_hw * 3, py - 3, col_hw * 6, 6)

        # reaction chamber caps
        p.setPen(Qt.NoPen); p.setBrush(QColor(TANGERINE))
        p.drawRoundedRect(tube_x - 10, core_top - 9, tube_w + 20, 11, 3, 3)
        p.drawRoundedRect(tube_x - 10, core_bot - 2, tube_w + 20, 11, 3, 3)

        # labels
        p.setFont(QFont("Arial Narrow", 8))
        p.setPen(QColor(TANGERINE))
        p.drawText(4, 14, "WARP CORE — VERTICAL")
        p.setFont(QFont("Arial Narrow", 7)); p.setPen(QColor(GOLD))
        p.drawText(cx - 16, core_top - 2, "M/ARA")
        p.drawText(cx - 14, core_bot + 18, "D-RXN")
        p.end()


class NacelleFlowDiagram(QWidget):
    """Top-down animated plasma-flow routing to port/starboard nacelles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(240, 200)
        self._phase = 0.0
        self._flow = [65.0 + random.uniform(-5, 5) for _ in range(2)]
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(50)

    def _step(self):
        self._phase = (self._phase + 0.025) % 1.0
        for i in range(2):
            self._flow[i] = max(45.0, min(99.0,
                self._flow[i] + random.uniform(-1.0, 1.0)))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(BG_BLACK))
        w, h = self.width(), self.height()
        cx = w // 2

        nacel_w, nacel_h = max(52, int(w * 0.27)), 14
        core_w, core_h   = 36, 28
        core_x = cx - core_w // 2
        core_y = h - 50

        pn_x, pn_y = 6, 18
        sn_x, sn_y = w - 6 - nacel_w, 18

        # pylon endpoints (on the core and on each nacelle midpoint)
        src_p  = (core_x,              core_y + core_h // 2)
        src_s  = (core_x + core_w,     core_y + core_h // 2)
        dst_p  = (pn_x + nacel_w,      pn_y + nacel_h // 2)
        dst_s  = (sn_x,                sn_y + nacel_h // 2)

        def draw_flow(x0, y0, x1, y1, phase_off):
            lc = QColor(LIGHT_BLUE); lc.setAlphaF(0.25)
            p.setPen(QPen(lc, 2)); p.setBrush(Qt.NoBrush)
            p.drawLine(x0, y0, x1, y1)
            n_dots = 9
            for i in range(n_dots):
                t = ((i / n_dots) + self._phase + phase_off) % 1.0
                dx = x0 + (x1 - x0) * t
                dy = y0 + (y1 - y0) * t
                alpha = math.sin(t * math.pi)
                dc = QColor("#00FFFF"); dc.setAlphaF(alpha * 0.85)
                p.setPen(Qt.NoPen); p.setBrush(dc)
                p.drawEllipse(int(dx) - 3, int(dy) - 3, 6, 6)

        draw_flow(*src_p, *dst_p, 0.0)
        draw_flow(*src_s, *dst_s, 0.5)

        # secondary hull outline
        hull_x = cx - 22
        hull_y = core_y - 18
        hull_w, hull_h = 44, core_h + 20
        p.setPen(QPen(QColor(TANGERINE), 1)); p.setBrush(QBrush(QColor("#0d0500")))
        p.drawRoundedRect(hull_x, hull_y, hull_w, hull_h + 2, 5, 5)

        # engineering core block
        p.setPen(QPen(QColor(TANGERINE), 2)); p.setBrush(QBrush(QColor("#1A0800")))
        p.drawRoundedRect(core_x, core_y, core_w, core_h, 4, 4)

        # core glow pulse
        gp = 0.4 + 0.4 * abs(math.sin(self._phase * 2 * math.pi * 2))
        for r, al in [(14, gp * 0.45), (7, gp * 0.85)]:
            gc = QColor(TANGERINE); gc.setAlphaF(al)
            p.setPen(Qt.NoPen); p.setBrush(gc)
            p.drawEllipse(core_x + core_w//2 - r, core_y + core_h//2 - r, r*2, r*2)

        p.setFont(QFont("Arial Narrow", 7)); p.setPen(QColor(GOLD))
        p.drawText(core_x + 2, core_y + core_h//2 + 4, "M/ARA")

        # port nacelle
        p.setPen(QPen(QColor(LILAC), 2)); p.setBrush(QBrush(QColor("#110022")))
        p.drawRoundedRect(pn_x, pn_y, nacel_w, nacel_h, 4, 4)
        p.setPen(QColor(LILAC))
        p.drawText(pn_x + 3, pn_y + 10, f"PORT  {self._flow[0]:.0f}%")

        # starboard nacelle
        p.setPen(QPen(QColor(GOLD), 2)); p.setBrush(QBrush(QColor("#201000")))
        p.drawRoundedRect(sn_x, sn_y, nacel_w, nacel_h, 4, 4)
        p.setPen(QColor(GOLD))
        p.drawText(sn_x + 3, sn_y + 10, f"STBD  {self._flow[1]:.0f}%")

        # flow rate readout labels at bottom
        p.setFont(QFont("Arial Narrow", 7)); p.setPen(QColor(LIGHT_BLUE))
        p.drawText(4, h - 5, f"PORT: {self._flow[0]:.1f} GW/s")
        p.drawText(w - 80, h - 5, f"STBD: {self._flow[1]:.1f} GW/s")

        # title
        p.setFont(QFont("Arial Narrow", 8)); p.setPen(QColor(TANGERINE))
        p.drawText(4, 14, "NACELLE PLASMA FLOW")
        p.end()


class EngDiagramStack(QWidget):
    """Cycles through warp-core diagram views every 10 seconds."""
    _LABELS = [
        "VIEW: M/ARA CROSS-SECTION",
        "VIEW: WARP CORE — VERTICAL",
        "VIEW: NACELLE PLASMA FLOW",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._stack = QStackedWidget()
        self._stack.addWidget(WarpCoreDiagram())
        self._stack.addWidget(VerticalWarpCoreDiagram())
        self._stack.addWidget(NacelleFlowDiagram())
        layout.addWidget(self._stack)

        self._lbl = QLabel(self._LABELS[0])
        self._lbl.setAlignment(Qt.AlignCenter)
        self._lbl.setFixedHeight(16)
        self._lbl.setStyleSheet(
            f"color:{LILAC}; font-family:'Arial Narrow'; font-size:9px;"
        )
        layout.addWidget(self._lbl)

        self._idx = 0
        self._cycle = QTimer(self)
        self._cycle.timeout.connect(self._next)
        self._cycle.start(10000)

    def _next(self):
        self._idx = (self._idx + 1) % self._stack.count()
        self._stack.setCurrentIndex(self._idx)
        self._lbl.setText(self._LABELS[self._idx])


class EngTelemetryFeed(QWidget):
    """Scrolling engineering subsystem telemetry readout."""
    _SYSTEMS = [
        ("M/AM INJECTOR-α", TANGERINE),
        ("M/AM INJECTOR-β", TANGERINE),
        ("PLASMA CONDUIT A", LILAC),
        ("PLASMA CONDUIT B", LILAC),
        ("EPS RELAY   A-04", LIGHT_BLUE),
        ("WARP COIL   PRI ", GOLD),
        ("WARP COIL   SEC ", GOLD),
        ("FIELD STAB  UNIT", "#66FF66"),
        ("ANTIMATTER  POD ", TANGERINE),
        ("BUSSARD SCOOP   ", LIGHT_BLUE),
        ("INJECTOR RAIL-01", LILAC),
        ("PLASMA MANIFOLD ", GOLD),
        ("POWER RELAY  B-2", LIGHT_BLUE),
    ]
    _UNITS = ["GW", "TJ/s", "m³/s", "μT", "kPa", "MW", "PJ", "mT/s"]
    _STATUS = (
        ["NOMINAL"] * 5 + ["STABLE"] * 3 + ["OPTIMAL"] * 2 + ["CAUTION"]
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        hdr = QLabel("SUBSYSTEM TELEMETRY")
        hdr.setStyleSheet(
            f"color:{GOLD}; font-family:'Arial Narrow'; font-size:22px; font-weight:bold;"
        )
        layout.addWidget(hdr)

        self.feed = QTextEdit()
        self.feed.setReadOnly(True)
        self.feed.setFrameStyle(QFrame.NoFrame)
        self.feed.setStyleSheet(f"""
            QTextEdit {{
                background-color:{BG_BLACK}; color:{LIGHT_BLUE};
                font-family:'Courier New'; font-size:22px;
                border:1px solid {LILAC}; border-radius:4px;
            }}
            QScrollBar:vertical {{ width:0px; }}
        """)
        layout.addWidget(self.feed)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(700)

    def _tick(self):
        name, color = random.choice(self._SYSTEMS)
        val   = random.uniform(0.001, 9.999)
        unit  = random.choice(self._UNITS)
        stat  = random.choice(self._STATUS)
        sc    = "#66FF66" if stat in ("NOMINAL", "STABLE", "OPTIMAL") else "#FFCC00"
        ts    = datetime.datetime.now().strftime("%H:%M:%S")
        self.feed.append(
            f'<span style="color:#555">{ts}</span> '
            f'<span style="color:{color}">{name}</span> '
            f'<span style="color:#aaa">{val:6.3f} {unit}</span> '
            f'<span style="color:{sc}">[{stat}]</span>'
        )
        sb = self.feed.verticalScrollBar()
        sb.setValue(sb.maximum())


class EngSystemStatus(QWidget):
    """Bottom row of blinking LCARS status dots for major engine systems."""
    _ITEMS = [
        ("ANTIMATTER", TANGERINE),
        ("PLASMA GEN", LILAC),
        ("WARP COILS", GOLD),
        ("FIELD STAB", LIGHT_BLUE),
        ("EPS RELAYS", TANGERINE),
        ("M/AM INJ-A", LILAC),
        ("M/AM INJ-B", GOLD),
        ("BUSSARD   ", LIGHT_BLUE),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._lights = []
        for label, color in self._ITEMS:
            col = QVBoxLayout()
            col.setSpacing(1)
            lbl = QLabel(label.strip())
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                f"color:{color}; font-family:'Arial Narrow'; font-size:9px;"
            )
            dot = QLabel("●")
            dot.setAlignment(Qt.AlignCenter)
            dot.setStyleSheet(
                f"color:{color}; font-family:'Arial Narrow'; font-size:18px;"
            )
            self._lights.append((dot, color))
            col.addWidget(lbl)
            col.addWidget(dot)
            layout.addLayout(col)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._pulse)
        self._timer.start(550)

    def _pulse(self):
        dot, color = random.choice(self._lights)
        dot.setStyleSheet("color:white; font-family:'Arial Narrow'; font-size:18px;")
        QTimer.singleShot(130, lambda: dot.setStyleSheet(
            f"color:{color}; font-family:'Arial Narrow'; font-size:18px;"
        ))


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

        # ── animated engineering content ──────────────────────────────────
        mid_row = QHBoxLayout()
        mid_row.setSpacing(8)

        self._core_diagram = EngDiagramStack()
        mid_row.addWidget(self._core_diagram, stretch=1)

        self._telemetry = EngTelemetryFeed()
        mid_row.addWidget(self._telemetry, stretch=1)

        layout.addLayout(mid_row)
        layout.addWidget(EngSystemStatus())

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


class TacConsoleWidget(QWidget):
    """Animated LCARS Weapon System 06-0722 — photon torpedo bay.
    Cycles between rack view (7 torpedoes with individual fire animations)
    and cutaway diagram view with gold leader-line callouts.
    """

    _N_TORPS = 7

    _SIDEBAR_ITEMS = [
        ("LCARS ACCESS",      GOLD,       True),
        ("KEY SYSTEMS",       LIGHT_BLUE, False),
        ("WEAPONS SYSTEMS",   LIGHT_BLUE, False),
        ("SCIENCE-01",        LIGHT_BLUE, False),
        ("SCAN",              LIGHT_BLUE, False),
        ("DEFENSIVE SYSTEMS", LIGHT_BLUE, False),
        ("EMITTERS",          LIGHT_BLUE, False),
        ("OPS MANAGEMENT",    LIGHT_BLUE, False),
        ("COMMUNICATIONS",    LIGHT_BLUE, False),
        ("LOCK",              GOLD,       True),
        ("MODE SELECT",       LIGHT_BLUE, False),
    ]

    _PILL_BTNS = [
        ("TARGET SCAN",  LIGHT_BLUE),
        ("RESET",        TANGERINE),
        ("EXIT",         "#CC7722"),
        ("ALERT",        LIGHT_BLUE),
        ("DATA RESEARCH","#BB6611"),
        ("LCARS-19720",  LIGHT_BLUE),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase     = 0.0
        self._fire      = [0.0] * self._N_TORPS
        self._fire_cd   = 60
        self._view_mode = 0    # 0=rack  1=cutaway
        self._view_t    = 0
        self._act_btn   = 0
        self._rows      = []
        self._row_t     = 0
        rng = random.Random(17)
        for _ in range(9):
            self._rows.append(self._gen_row(rng))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(50)

    @staticmethod
    def _gen_row(rng=None):
        r = rng or random
        return "  ".join(str(r.randint(10, 9999999)) for _ in range(r.randint(7, 11)))

    def _step(self):
        self._phase    = (self._phase + 0.05) % (2 * math.pi)
        self._view_t  += 1
        self._row_t   += 1
        self._fire_cd -= 1

        if self._view_t >= 240:
            self._view_t    = 0
            self._view_mode = 1 - self._view_mode
            if self._view_mode == 0:
                self._act_btn = random.randint(0, len(self._PILL_BTNS) - 1)

        if self._row_t >= 6:
            self._row_t = 0
            self._rows.append(self._gen_row())
            if len(self._rows) > 14:
                self._rows.pop(0)

        for i in range(self._N_TORPS):
            if self._fire[i] > 0:
                self._fire[i] = min(1.0, self._fire[i] + 0.022)
                if self._fire[i] >= 1.0:
                    self._fire[i] = 0.0

        if self._fire_cd <= 0 and self._view_mode == 0:
            idle = [i for i, s in enumerate(self._fire) if s == 0.0]
            if idle:
                self._fire[random.choice(idle)] = 0.01
            self._fire_cd = random.randint(45, 110)

        self.update()

    # ── paint entry point ─────────────────────────────────────────────────────

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(BG_BLACK))
        W, H  = self.width(), self.height()
        sbw   = max(128, min(162, int(W * 0.135)))
        hdr_h = max(88,  int(H * 0.27))
        sep_h = max(22,  int(H * 0.06))
        self._p_sidebar(p, 0, 0, sbw, H)
        self._p_header(p, sbw, 0, W - sbw, hdr_h)
        self._p_statusbar(p, sbw, hdr_h, W - sbw, sep_h)
        bay_y = hdr_h + sep_h
        self._p_bay(p, sbw, bay_y, W - sbw, H - bay_y)
        p.end()

    # ── sidebar ───────────────────────────────────────────────────────────────

    def _p_sidebar(self, p, x, y, w, h):
        p.fillRect(x, y, w, h, QColor(BG_BLACK))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(LIGHT_BLUE))
        p.drawRect(x, y, 16, h)
        pad = 3
        ih  = max(22, (h - 4) // len(self._SIDEBAR_ITEMS) - pad)
        p.setFont(QFont("Arial Narrow", 8, QFont.Bold))
        for i, (lbl, color, active) in enumerate(self._SIDEBAR_ITEMS):
            iy = y + 2 + i * (ih + pad)
            ix = x + 19
            iw = w - 22
            bc = QColor(color)
            if not active:
                bc.setAlpha(195)
            p.setPen(Qt.NoPen)
            p.setBrush(bc)
            p.drawRoundedRect(ix, iy, iw, ih, ih // 2, ih // 2)
            p.setPen(QColor(BG_BLACK))
            p.drawText(ix + 6, iy + ih - 6, lbl)

    # ── header ────────────────────────────────────────────────────────────────

    def _p_header(self, p, x, y, w, h):
        p.fillRect(x, y, w, h, QColor(5, 5, 16))
        dw  = int(w * 0.50)
        rx  = x + dw

        p.setFont(QFont("Courier New", 8))
        p.setPen(QColor(LIGHT_BLUE))
        lh  = 13
        vis = min(len(self._rows), h // lh)
        for i in range(vis):
            p.drawText(x + 5, y + 11 + i * lh, self._rows[-(vis - i)])

        p.setFont(QFont("Arial Narrow", max(10, int(h * 0.17)), QFont.Bold))
        p.setPen(QColor("#FFFFFF"))
        p.drawText(rx + 5, y + int(h * 0.21), "WEAPON SYSTEM 06-0722")
        p.setFont(QFont("Arial Narrow", max(8, int(h * 0.12)), QFont.Bold))
        p.setPen(QColor(LIGHT_BLUE))
        p.drawText(rx + 5, y + int(h * 0.36), "EQUIPMENT AND TECHNOLOGY 68-3")

        ba_y      = y + int(h * 0.41)
        ba_h      = h - int(h * 0.41) - 4
        cols, rows = 3, 2
        pad        = 4
        bw         = (w - dw - pad * (cols + 1)) // cols
        bh         = max(20, (ba_h - pad * (rows + 1)) // rows)
        for idx, (lbl, col) in enumerate(self._PILL_BTNS):
            c   = idx % cols
            r   = idx // cols
            bx  = rx + pad + c * (bw + pad)
            _by = ba_y + pad + r * (bh + pad)
            bc  = QColor(col)
            if idx == self._act_btn:
                fl  = (math.sin(self._phase * 4) + 1) / 2
                bc  = bc.lighter(int(100 + 55 * fl))
            p.setPen(Qt.NoPen)
            p.setBrush(bc)
            p.drawRoundedRect(bx, _by, bw, bh, bh // 2, bh // 2)
            p.setPen(QColor(BG_BLACK))
            p.setFont(QFont("Arial Narrow", 7, QFont.Bold))
            p.drawText(bx + 6, _by + bh - 7, lbl)

    # ── status bar strip ──────────────────────────────────────────────────────

    def _p_statusbar(self, p, x, y, w, h):
        p.fillRect(x, y, w, h, QColor(4, 4, 14))
        half = w // 2
        for i, lbl in enumerate(["TRACTOR BEAM", "NETWORK"]):
            by   = y + 2 + i * (h // 2 - 1)
            barw = half // 2 - 4
            fill = int(barw * (0.55 + 0.30 * math.sin(self._phase + i)))
            p.setPen(QPen(QColor(LIGHT_BLUE), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRect(x + 2, by + 2, barw, h // 2 - 6)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(LIGHT_BLUE))
            p.drawRect(x + 2, by + 2, fill, h // 2 - 6)
            p.setPen(QColor(LIGHT_BLUE))
            p.setFont(QFont("Arial Narrow", 7))
            p.drawText(x + barw + 8, by + h // 2 - 4, lbl)
        rlbls = [
            ("SUBSPACE SYSTEMS",         LIGHT_BLUE),
            ("PHOTON/QUANTUM TORPEDOES", TANGERINE),
            ("PROPULSION SYSTEMS",       LIGHT_BLUE),
            ("SYSTEM LOCATIONS",         LIGHT_BLUE),
        ]
        rh2 = h // 2 - 2
        for i, (lbl, col) in enumerate(rlbls):
            ci   = i % 2
            ri   = i // 2
            _by  = y + 2 + ri * rh2
            _bx  = x + half + ci * (half // 2)
            bw2  = half // 2 - 68
            fill = int(bw2 * (0.6 + 0.28 * math.sin(self._phase * 0.9 + i * 0.7)))
            fc   = QColor(col)
            p.setPen(QPen(fc, 1))
            p.setBrush(Qt.NoBrush)
            p.drawRect(_bx + 66, _by + 2, bw2, rh2 - 4)
            p.setPen(Qt.NoPen)
            p.setBrush(fc)
            p.drawRect(_bx + 66, _by + 2, fill, rh2 - 4)
            p.setPen(QColor(LIGHT_BLUE))
            p.setFont(QFont("Arial Narrow", 6))
            p.drawText(_bx + 2, _by + rh2 - 3, lbl)

    # ── torpedo bay ───────────────────────────────────────────────────────────

    def _p_bay(self, p, x, y, w, h):
        if self._view_mode == 1:
            self._p_cutaway(p, x, y, w, h)
        else:
            self._p_rack(p, x, y, w, h)
        p.setPen(QColor(LIGHT_BLUE))
        p.setFont(QFont("Arial Narrow", 15, QFont.Bold))
        p.drawText(x + 10, y + h - 8, "PHOTON TORPEDO Mk-V")

    # ── rack view ─────────────────────────────────────────────────────────────

    def _p_rack(self, p, x, y, w, h):
        slot = (h - 28) // self._N_TORPS
        tw   = int(w * 0.58)
        tx   = x + int(w * 0.16)
        for i in range(self._N_TORPS):
            th   = max(18, slot - 10)
            ty   = y + 4 + i * slot + (slot - th) // 2
            fs   = self._fire[i]
            off  = int(fs * w * 0.38)
            alph = max(0, int(255 * (1.0 - fs * 1.45)))
            puls = 0.82 + 0.18 * math.sin(self._phase * 1.6 + i * 0.65) if fs == 0 else 1.0
            self._p_torp(p, tx + off, ty, tw, th, alph, puls, fs > 0)

    # ── single torpedo ────────────────────────────────────────────────────────

    def _p_torp(self, p, x, y, w, h, alpha=255, pulse=1.0, firing=False):
        """Dark capsule body + red stripe + blinking indicator dot + nose glow."""
        cy = y + h // 2
        # Body
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(int(52 * pulse), int(52 * pulse), int(58 * pulse), alpha))
        p.drawRoundedRect(x, y, w, h, h // 2, h // 2)
        # Rim
        p.setPen(QPen(QColor(int(90 * pulse), int(90 * pulse), int(100 * pulse), alpha), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(x, y, w, h, h // 2, h // 2)
        # Red accent stripe
        sx  = x + h // 2
        sw  = max(1, w - h)
        sh  = max(2, h // 5)
        sc  = QColor(255 if firing else 200, 28 if firing else 18, 0, alpha)
        p.setPen(Qt.NoPen)
        p.setBrush(sc)
        p.drawRect(sx, cy - sh // 2, sw, sh)
        if firing:
            gc = QColor(255, 80, 0, int(alpha * 0.35))
            p.setBrush(gc)
            p.drawRect(sx - 3, cy - sh - 2, sw + 6, sh * 2 + 4)
        # Indicator dot
        dr    = max(3, h // 5)
        dx    = x + w - h // 2 - 4
        blink = int(alpha * (0.45 + 0.55 * abs(math.sin(self._phase * 3.5))))
        dc    = QColor(255, 160, 0, blink) if firing else QColor(200, 20, 20, blink)
        p.setPen(Qt.NoPen)
        p.setBrush(dc)
        p.drawEllipse(dx - dr, cy - dr, dr * 2, dr * 2)
        # Nose radial highlight
        ng = QRadialGradient(x + h // 2, cy, h // 2)
        ng.setColorAt(0.0, QColor(130, 130, 140, int(alpha * 0.55)))
        ng.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(ng))
        p.drawEllipse(x, y, h, h)

    # ── cutaway view ──────────────────────────────────────────────────────────

    def _p_cutaway(self, p, x, y, w, h):
        """Large single torpedo with gold leader-line callouts."""
        tw = int(w * 0.70)
        th = max(55, int(h * 0.30))
        tx = x + int(w * 0.12)
        ty = y + int(h * 0.32)
        self._p_torp(p, tx, ty, tw, th, 255, 1.0, False)

        # Interior section dividers
        p.setPen(QPen(QColor(72, 72, 84), 1))
        for frac in [0.22, 0.48, 0.72]:
            lx = int(tx + th // 2 + frac * (tw - th))
            p.drawLine(lx, ty + 3, lx, ty + th - 3)

        # Pulsing outer glow
        pulse = 0.22 + 0.16 * math.sin(self._phase * 2)
        grd   = QRadialGradient(tx + tw // 2, ty + th // 2, max(tw, th) // 2 + 30)
        gc    = QColor(200, 50, 50)
        gc.setAlphaF(pulse)
        grd.setColorAt(0.0, QColor(0, 0, 0, 0))
        grd.setColorAt(0.7, QColor(0, 0, 0, 0))
        grd.setColorAt(1.0, gc)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grd))
        p.drawEllipse(tx - 30, ty - 30, tw + 60, th + 60)

        # Gold callout leader lines
        gold       = QColor(GOLD)
        body_start = tx + th // 2
        body_len   = tw - th
        lbl_y_top  = ty - max(16, int(h * 0.15))
        lbl_y_bot  = ty + th + max(12, int(h * 0.10))

        for lbl, frac in [
            ("SUSTAINER ENGINE MODULES", 0.13),
            ("DEUTERIUM SUPPLY",         0.47),
            ("ANTIMATTER SUPPLY",        0.76),
        ]:
            ax = int(body_start + frac * body_len)
            p.setPen(QPen(gold, 1))
            p.drawLine(ax, ty, ax, lbl_y_top + 6)
            p.drawLine(ax, lbl_y_top + 6, ax + 5, lbl_y_top + 6)
            p.setPen(Qt.NoPen)
            p.setBrush(gold)
            p.drawEllipse(ax - 3, ty - 3, 6, 6)
            p.setPen(gold)
            p.setFont(QFont("Arial Narrow", 8, QFont.Bold))
            p.drawText(ax + 8, lbl_y_top + 10, lbl)

        for lbl, frac in [
            ("REACTION CHAMBERS",   0.37),
            ("GUIDANCE PROCESSORS", 0.63),
        ]:
            ax = int(body_start + frac * body_len)
            p.setPen(QPen(gold, 1))
            p.drawLine(ax, ty + th, ax, lbl_y_bot - 5)
            p.drawLine(ax, lbl_y_bot - 5, ax + 5, lbl_y_bot - 5)
            p.setPen(Qt.NoPen)
            p.setBrush(gold)
            p.drawEllipse(ax - 3, ty + th - 3, 6, 6)
            p.setPen(gold)
            p.setFont(QFont("Arial Narrow", 8, QFont.Bold))
            p.drawText(ax + 8, lbl_y_bot, lbl)


class TacPage(QWidget):
    """Animated LCARS tactical weapons console — Photon Torpedo Mk-V."""
    def __init__(self, player):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._console = TacConsoleWidget()
        layout.addWidget(self._console)


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
        self._voice_worker.stop()
        self._voice_worker.quit()
        self._voice_worker.wait(6000)
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

    def closeEvent(self, event):
        worker = self._screen.findChild(VoiceWorker)
        if worker and worker.isRunning():
            worker.stop()
            worker.quit()
            worker.wait(6000)
        super().closeEvent(event)


if __name__ == "__main__":
    import PySide6
    plugin_path = os.path.join(os.path.dirname(PySide6.__file__), "plugins")
    os.environ["QT_PLUGIN_PATH"] = plugin_path
    app = QApplication(sys.argv)
    window = LcarsApp()
    window.setWindowFlags(Qt.FramelessWindowHint)
    window.showFullScreen()
    sys.exit(app.exec())