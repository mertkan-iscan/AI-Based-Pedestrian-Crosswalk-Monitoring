from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt

class OverlayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.detections = []
        self.original_frame_size = (1, 1)  # Placeholder to prevent division by zero
        self.scaled_pixmap_size = (1, 1)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def set_detections(self, detections, original_frame_size, scaled_pixmap_size):
        self.detections = detections
        self.original_frame_size = original_frame_size
        self.scaled_pixmap_size = scaled_pixmap_size
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(QtGui.QColor(255, 0, 0), 2)
        painter.setPen(pen)

        ow, oh = self.original_frame_size
        sw, sh = self.scaled_pixmap_size

        scale_x = sw / ow
        scale_y = sh / oh
        scale = min(scale_x, scale_y)

        offset_x = (self.width() - ow * scale) / 2
        offset_y = (self.height() - oh * scale) / 2

        for obj in self.detections:
            x1, y1, x2, y2 = obj.bbox
            rect = QtCore.QRectF(
                offset_x + x1 * scale,
                offset_y + y1 * scale,
                (x2 - x1) * scale,
                (y2 - y1) * scale
            )
            painter.drawRect(rect)
            painter.drawText(rect.topLeft(), f"ID: {obj.id}")
