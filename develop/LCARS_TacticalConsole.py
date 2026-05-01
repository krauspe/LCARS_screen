import sys
from PySide6.QtWidgets import (QApplication, QWidget, QGridLayout, 
                             QPushButton, QVBoxLayout, QHBoxLayout)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

class LcarsKey(QPushButton):
    """A tactical keypad button that plays a sound when clicked."""
    def __init__(self, text, color="#FFCC00", player=None):
        super().__init__(text)
        self.player = player
        self.setFixedSize(80, 40)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: black;
                border-radius: 5px;
                font-family: 'Arial Narrow';
                font-weight: bold;
                font-size: 12px;
                border: none;
            }}
            QPushButton:pressed {{
                background-color: white;
            }}
        """)
        if self.player:
            self.clicked.connect(self.play_sound)

    def play_sound(self):
        self.player.stop() # Reset if already playing
        self.player.play()

class LcarsTacticalConsole(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TACTICAL CONSOLE")
        self.setStyleSheet("background-color: black;")

        # Audio Setup
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setSource(QUrl.fromLocalFile("beep.mp3"))
        self.audio_output.setVolume(50)

        # Layouts
        self.main_layout = QVBoxLayout(self)
        self.grid = QGridLayout()
        self.grid.setSpacing(5)

        # Create a 4x4 Tactical Grid
        colors = ["#FF9966", "#CC99CC", "#99CCFF", "#FFCC00"]
        for row in range(4):
            for col in range(4):
                btn_color = colors[row % len(colors)]
                btn_text = f"{random.randint(100, 999)}"
                btn = LcarsKey(btn_text, btn_color, self.player)
                self.grid.addWidget(btn, row, col)

        self.main_layout.addLayout(self.grid)

if __name__ == "__main__":
    import random
    app = QApplication(sys.argv)
    window = LcarsTacticalConsole()
    window.show()
    sys.exit(app.exec())