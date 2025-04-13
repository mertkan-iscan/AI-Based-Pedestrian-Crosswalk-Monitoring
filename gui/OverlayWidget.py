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
        painter.setRenderHint(QtGui.QPainter.Antialiasing, False)

        # Calculate scale factors and offsets.
        ow, oh = self.original_frame_size
        sw, sh = self.scaled_pixmap_size
        scale_x = sw / ow
        scale_y = sh / oh
        scale = min(scale_x, scale_y)
        offset_x = (self.width() - ow * scale) / 2
        offset_y = (self.height() - oh * scale) / 2

        for obj in self.detections:
            # Draw bounding box in red.
            pen_box = QtGui.QPen(QtGui.QColor(255, 0, 0), 2)
            painter.setPen(pen_box)
            x1, y1, x2, y2 = obj.bbox
            rect = QtCore.QRectF(
                offset_x + x1 * scale,
                offset_y + y1 * scale,
                (x2 - x1) * scale,
                (y2 - y1) * scale
            )
            painter.drawRect(rect)
            painter.drawText(rect.topLeft(), f"ID: {obj.id}")

            # Draw the tracker point (centroid) if available.
            if obj.centroid_coordinate is not None:
                cx, cy = obj.centroid_coordinate
                scaled_cx = offset_x + cx * scale
                scaled_cy = offset_y + cy * scale
                old_pen = painter.pen()
                old_brush = painter.brush()
                marker_pen = QtGui.QPen(QtGui.QColor(0, 0, 255), 2)  # Blue marker for centroid.
                painter.setPen(marker_pen)
                painter.setBrush(QtGui.QColor(0, 0, 255))
                painter.drawEllipse(QtCore.QPointF(scaled_cx, scaled_cy), 5, 5)
                painter.drawText(QtCore.QPointF(scaled_cx + 6, scaled_cy), f"TP: {obj.id}")
                painter.setPen(old_pen)
                painter.setBrush(old_brush)

            # Draw the foot location point if available.
            if obj.foot_coordinate is not None:
                fx, fy = obj.foot_coordinate
                scaled_fx = offset_x + fx * scale
                scaled_fy = offset_y + fy * scale
                old_pen = painter.pen()
                old_brush = painter.brush()
                marker_pen = QtGui.QPen(QtGui.QColor(0, 255, 0), 2)  # Green marker for foot location.
                painter.setPen(marker_pen)
                painter.setBrush(QtGui.QColor(0, 255, 0))
                painter.drawEllipse(QtCore.QPointF(scaled_fx, scaled_fy), 5, 5)
                painter.drawText(QtCore.QPointF(scaled_fx + 6, scaled_fy), f"FP: {obj.id}")
                painter.setPen(old_pen)
                painter.setBrush(old_brush)
