from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPainterPath, QColor
from PySide6.QtCore import Qt

TANGERINE = "#FF9966"
LILAC = "#CC99CC"
GOLD = "#FFCC00"
LIGHT_BLUE = "#99CCFF"

class LcarsHollowElbow(QWidget):
    def __init__(self, color=TANGERINE, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.setMinimumSize(160, 100)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing) # Essential for smooth curves
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.color)

        # Dimensions
        w = self.width()
        h = self.height()
        thickness = 30  # Thickness of the bars
        radius = 40     # External radius
        inner_r = 20    # The critical "inner" curve radius

        # Create the LCARS "Hook" Path
        path = QPainterPath()
        
        # Start at top right of the horizontal bar
        path.moveTo(w, 0)
        # Top edge to top-left corner
        path.lineTo(radius, 0)
        # Outer top-left curve
        path.arcTo(0, 0, radius * 2, radius * 2, 90, 90)
        # Down the left edge to the bottom
        path.lineTo(0, h)
        # Across the bottom edge
        path.lineTo(thickness, h)
        # Up the inner edge to the inner curve start
        path.lineTo(thickness, thickness + inner_r)
        
        # THE INNER CURVE: This is what makes it LCARS
        # This connects the vertical bar to the horizontal bar internally
        path.arcTo(thickness, thickness, inner_r * 2, inner_r * 2, 180, -90)
        
        # Back to the start
        path.lineTo(w, thickness)
        path.closeSubpath()

        painter.drawPath(path)

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = LcarsHollowElbow()
    w.setWindowTitle("LCARS Elbow Test")
    w.resize(300, 200)
    w.show()
    sys.exit(app.exec())