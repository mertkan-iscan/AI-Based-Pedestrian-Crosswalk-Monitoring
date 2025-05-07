from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt
import numpy as np
import time

class OverlayWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.detections = []
        self.original_frame_size = (1, 1)
        self.scaled_pixmap_size = (1, 1)
        self.H_inv = None
        self._first_seen = {}
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def set_detections(self, detections, original_frame_size, scaled_pixmap_size):
        now = time.time()
        for obj in detections:
            if obj.id not in self._first_seen:
                self._first_seen[obj.id] = now
        self.detections = detections
        self.original_frame_size = original_frame_size
        self.scaled_pixmap_size = scaled_pixmap_size
        self.update()

    def set_inverse_homography(self, H_inv):
        self.H_inv = np.asarray(H_inv) if H_inv is not None else None

    def _to_pixel(self, pt):
        if self.H_inv is None:
            return pt
        vec = np.array([pt[0], pt[1], 1.0], dtype=float)
        dst = self.H_inv @ vec
        if dst[2] == 0:
            return pt
        return (dst[0] / dst[2], dst[1] / dst[2])

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        now = time.time()
        ow, oh = self.original_frame_size
        sw, sh = self.scaled_pixmap_size
        scale = min(sw / ow, sh / oh)
        off_x = (self.width() - ow * scale) / 2
        off_y = (self.height() - oh * scale) / 2

        for obj in self.detections:
            first_seen = self._first_seen.get(obj.id, 0)
            if now - first_seen < 1.0:
                color = QtGui.QColor(255, 0, 0)
            elif obj.object_type == "person":
                color = QtGui.QColor(255, 255, 0)
            else:
                color = QtGui.QColor(0, 0, 255)

            pen_box = QtGui.QPen(color, 2)
            painter.setPen(pen_box)
            x1, y1, x2, y2 = obj.bbox
            rect = QtCore.QRectF(
                off_x + x1 * scale,
                off_y + y1 * scale,
                (x2 - x1) * scale,
                (y2 - y1) * scale
            )
            painter.drawRect(rect)
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
            text_pos = rect.topLeft() + QtCore.QPointF(0, -6)
            painter.drawText(text_pos, f"ID: {obj.id}")

            if obj.centroid_coordinate is not None:
                cx, cy = self._to_pixel(obj.centroid_coordinate)
                sx, sy = off_x + cx * scale, off_y + cy * scale
                old_pen, old_brush = painter.pen(), painter.brush()
                painter.setPen(QtGui.QPen(QtGui.QColor(0, 128, 255), 2))
                painter.setBrush(QtGui.QColor(0, 128, 255))
                painter.drawEllipse(QtCore.QPointF(sx, sy), 5, 5)
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
                painter.drawText(QtCore.QPointF(sx + 6, sy), f"TP: {obj.id}")
                painter.setPen(old_pen)
                painter.setBrush(old_brush)

            if obj.foot_coordinate is not None:
                fx, fy = obj.foot_coordinate
                sx, sy = off_x + fx * scale, off_y + fy * scale
                old_pen, old_brush = painter.pen(), painter.brush()
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), 2))
                painter.setBrush(QtGui.QColor(255, 255, 0))
                painter.drawEllipse(QtCore.QPointF(sx, sy), 5, 5)
                painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
                painter.drawText(QtCore.QPointF(sx + 6, sy), f"FP: {obj.id}")
                painter.setPen(old_pen)
                painter.setBrush(old_brush)
