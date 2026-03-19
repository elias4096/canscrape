from PySide6.QtGui import QColor, QPaintEvent, QPainter
from PySide6.QtWidgets import QWidget

class DotWidget(QWidget):
    def __init__(self, color: QColor = QColor("red")):
        super().__init__()
        self.color = color
        self.setFixedSize(14, 14)

    def set_color(self, color_name: str):
        self.color = QColor(color_name)
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setBrush(self.color)
        painter.drawEllipse(2, 2, 10, 10)