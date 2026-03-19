import sys
import random
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFrame, QTextEdit)
from PySide6.QtCore import Qt, QTimer

# LCARS Color Palette
TANGERINE = "#FF9966"
LILAC = "#CC99CC"
GOLD = "#FFCC00"
LIGHT_BLUE = "#99CCFF"
BG_BLACK = "#000000"

class LcarsButton(QPushButton):
    def __init__(self, text, color=GOLD):
        super().__init__(text)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: black;
                border-radius: 12px;
                font-family: 'Arial Narrow';
                font-weight: bold;
                text-align: right;
                padding-right: 10px;
                height: 25px;
            }}
            QPushButton:hover {{ background-color: white; }}
        """)

class LcarsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("USS PySide6 - Bridge Interface")
        self.setStyleSheet(f"background-color: {BG_BLACK};")
        self.resize(800, 500)

        # Main Layout
        self.main_layout = QHBoxLayout(self)
        
        # 1. Left Sidebar (Frame & Nav)
        self.sidebar = QVBoxLayout()
        self.sidebar.setSpacing(5)
        
        # Top Elbow
        top_elbow = QFrame()
        top_elbow.setFixedSize(150, 80)
        top_elbow.setStyleSheet(f"background-color: {TANGERINE}; border-top-left-radius: 40px;")
        self.sidebar.addWidget(top_elbow)
        
        for label in ["LOGS", "SCAN", "COMM", "DATA"]:
            self.sidebar.addWidget(LcarsButton(label, LILAC))
            
        self.sidebar.addStretch()
        self.main_layout.addLayout(self.sidebar)

        # 2. Central Content Area
        self.content = QVBoxLayout()
        
        # Header text
        header = QLabel("SENSOR ARRAY : SECTOR 001")
        header.setStyleSheet(f"color: {GOLD}; font-size: 24px; font-family: 'Arial Narrow';")
        self.content.addWidget(header, alignment=Qt.AlignRight)

        # 3. The Scrolling Data Feed
        self.feed = QTextEdit()
        self.feed.setReadOnly(True)
        self.feed.setFrameStyle(QFrame.NoFrame)
        # Vertical scrollbar styling to match LCARS
        self.feed.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_BLACK};
                color: {LIGHT_BLUE};
                font-family: 'Courier New';
                font-size: 13px;
                border: 1px solid {TANGERINE};
                border-radius: 5px;
            }}
            QScrollBar:vertical {{ width: 0px; }} /* Hide scrollbar for immersion */
        """)
        self.content.addWidget(self.feed)
        
        self.main_layout.addLayout(self.content)

        # Setup Timer for data simulation
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_feed)
        self.timer.start(200) # Update every 200ms

    def update_feed(self):
        # Simulate LCARS-style telemetry
        prefix = random.choice(["TRN", "SUB", "VEC", "MAG", "GRV"])
        val1 = random.randint(1000, 9999)
        val2 = random.random() * 100
        new_entry = f"{prefix}-{val1} : STABLE : {val2:.4f} m/s²"
        
        self.feed.append(new_entry)
        
        # Auto-scroll to bottom
        scrollbar = self.feed.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LcarsWindow()
    window.show()
    sys.exit(app.exec())