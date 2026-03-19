import sys
import random
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFrame, QTextEdit)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect

# Colors
TANGERINE = "#FF9966"
LILAC = "#CC99CC"
GOLD = "#FFCC00"
LIGHT_BLUE = "#99CCFF"
BG_BLACK = "#000000"

class LcarsButton(QPushButton):
    def __init__(self, text, color=GOLD):
        super().__init__(text)
        self.setMinimumHeight(30)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: black;
                border-radius: 15px;
                font-family: 'Arial Narrow';
                font-weight: bold;
                text-align: right;
                padding-right: 15px;
                border: none;
            }}
            QPushButton:hover {{ background-color: white; }}
        """)

class LcarsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SYSTEM BOOT SEQUENCE")
        self.setStyleSheet(f"background-color: {BG_BLACK};")
        self.resize(800, 500)

        # Main Layout
        self.main_layout = QHBoxLayout(self)
        
        # 1. Sidebar Container
        self.sidebar_container = QWidget()
        self.sidebar = QVBoxLayout(self.sidebar_container)
        self.sidebar.setContentsMargins(0, 0, 0, 0)
        
        # The Animated Elbow
        self.elbow = QFrame()
        self.elbow.setFixedWidth(150)
        self.elbow.setStyleSheet(f"background-color: {TANGERINE}; border-top-left-radius: 40px;")
        self.sidebar.addWidget(self.elbow)
        
        # Buttons
        self.btns = []
        for label in ["NAV-01", "SEN-02", "ENG-03", "TAC-04"]:
            btn = LcarsButton(label, LILAC)
            btn.hide() # Hide initially for the staggered reveal
            self.sidebar.addWidget(btn)
            self.btns.append(btn)
            
        self.sidebar.addStretch()
        self.main_layout.addWidget(self.sidebar_container)

        # 2. Content Area
        self.content = QVBoxLayout()
        self.feed = QTextEdit()
        self.feed.setReadOnly(True)
        self.feed.setFrameStyle(QFrame.NoFrame)
        self.feed.setStyleSheet(f"background-color: {BG_BLACK}; color: {LIGHT_BLUE}; font-family: 'Courier';")
        self.content.addWidget(self.feed)
        self.main_layout.addLayout(self.content)

        # --- ANIMATION LOGIC ---
        
        # A. Animate the Elbow height
        self.elbow_anim = QPropertyAnimation(self.elbow, b"minimumHeight")
        self.elbow_anim.setDuration(800)
        self.elbow_anim.setStartValue(0)
        self.elbow_anim.setEndValue(100)
        self.elbow_anim.setEasingCurve(QEasingCurve.OutExpo)
        
        # B. Timer to stagger button appearance
        self.boot_timer = QTimer()
        self.boot_timer.timeout.connect(self.reveal_next_button)
        self.current_btn_idx = 0
        
        # Start sequence
        QTimer.singleShot(200, self.start_boot)

    def start_boot(self):
        self.feed.append("> INITIALIZING LCARS CORE...")
        self.elbow_anim.start()
        self.boot_timer.start(150) # Reveal a button every 150ms

    def reveal_next_button(self):
        if self.current_btn_idx < len(self.btns):
            self.btns[self.current_btn_idx].show()
            self.feed.append(f"> SUBSYSTEM {self.btns[self.current_btn_idx].text()} ONLINE")
            self.current_btn_idx += 1
        else:
            self.boot_timer.stop()
            self.feed.append("> ALL SYSTEMS NOMINAL.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LcarsWindow()
    window.show()
    sys.exit(app.exec())