from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt
import numpy as np
import time

class DetectionLayerWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.detections = []
        self.original_frame_size = (1, 1)
        self.scaled_pixmap_size = (1, 1)
        self.H_inv = None
        self._first_seen = {}

        # cost parameters
        self.motion_weight = 1.0
        self.appearance_weight = 1.0
        self.max_distance = None

        # widget attributes
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

    def set_cost_params(self, motion_weight, appearance_weight, max_distance):
        """
        Set weights and threshold for combined cost highlighting.
        """
        self.motion_weight = motion_weight
        self.appearance_weight = appearance_weight
        self.max_distance = max_distance

    def _to_pixel(self, pt):
        if self.H_inv is None:
            return pt
        vec = np.array([pt[0], pt[1], 1.0], dtype=float)
        dst = self.H_inv @ vec
        if dst[2] == 0:
            return pt
        return (dst[0] / dst[2], dst[1] / dst[2])

    def set_traffic_light_overlays(self, overlays):
        self.traffic_light_overlays = overlays
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)

        small_font = painter.font()
        small_font.setPointSize(8)
        small_font.setBold(False)

        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        now = time.time()
        ow, oh = self.original_frame_size
        sw, sh = self.scaled_pixmap_size
        scale = min(sw / ow, sh / oh) if ow and oh else 1.0
        off_x = (self.width() - ow * scale) / 2
        off_y = (self.height() - oh * scale) / 2

        for obj in self.detections:
            # choose box color as before
            first_seen = self._first_seen.get(obj.id, 0)
            if now - first_seen < 1.0:
                box_color = QtGui.QColor(255, 0, 0)
            elif obj.object_type == "person":
                box_color = QtGui.QColor(255, 255, 0)
            else:
                box_color = QtGui.QColor(0, 0, 255)

            # draw bounding box
            pen_box = QtGui.QPen(box_color, 2)
            painter.setPen(pen_box)
            x1, y1, x2, y2 = obj.bbox
            rect = QtCore.QRectF(
                off_x + x1 * scale,
                off_y + y1 * scale,
                (x2 - x1) * scale,
                (y2 - y1) * scale
            )
            painter.drawRect(rect)

            # draw ID and confidence
            small_font = painter.font()
            small_font.setPointSize(8)
            small_font.setBold(False)
            painter.setFont(small_font)
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
            fm = painter.fontMetrics()
            lines = [f"ID: {obj.id}"]
            if hasattr(obj, "confidence"):
                lines.append(f"{obj.confidence:.2f}")
            for i, line in enumerate(lines):
                text_pos = rect.topLeft() + QtCore.QPointF(0, -6 + i * fm.height())
                painter.drawText(text_pos, line)

            # draw cost metrics (motion & appearance) as before
            motion = getattr(obj, 'motion_distance', None)
            app = getattr(obj, 'appearance_distance', None)
            if motion is not None and app is not None:
                combined = self.motion_weight * motion + self.appearance_weight * app
                highlight = self.max_distance is not None and combined > self.max_distance
                cost_text = f"M:{motion:.2f} A:{app:.2f}"
                w = fm.horizontalAdvance(cost_text)
                h = fm.height()
                cost_pos = rect.topLeft() + QtCore.QPointF(0, 16)
                bg_rect = QtCore.QRectF(cost_pos.x() - 2, cost_pos.y() - h, w + 4, h + 4)
                if highlight:
                    painter.fillRect(bg_rect, QtGui.QColor(255, 0, 0, 160))
                    painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2))
                else:
                    painter.fillRect(bg_rect, QtGui.QColor(0, 0, 0, 100))
                    painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
                painter.drawText(cost_pos, cost_text)

            # draw transformed centroids and foot-points unchanged…
            if hasattr(obj, 'surface_point') and obj.surface_point is not None:
                cx, cy = self._to_pixel(obj.surface_point)
                sx, sy = off_x + cx * scale, off_y + cy * scale
                old_pen, old_brush = painter.pen(), painter.brush()
                painter.setPen(QtGui.QPen(QtGui.QColor(0, 128, 255), 2))
                painter.setBrush(QtGui.QColor(0, 128, 255))
                painter.drawEllipse(QtCore.QPointF(sx, sy), 5, 5)
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
                # use small font for TP text
                painter.setFont(small_font)
                painter.drawText(QtCore.QPointF(sx + 6, sy), f"TP: {obj.id}")
                painter.setPen(old_pen)
                painter.setBrush(old_brush)

                for tl in getattr(self, "traffic_light_overlays", []):
                    center = tl["center"]
                    status = tl["status"]

                    sw, sh = self.scaled_pixmap_size
                    ow, oh = self.original_frame_size
                    scale = min(sw / ow, sh / oh) if ow and oh else 1.0
                    off_x = (self.width() - ow * scale) / 2
                    off_y = (self.height() - oh * scale) / 2
                    cx = off_x + center[0] * scale
                    cy = off_y + center[1] * scale

                    color_map = {
                        "green": QtGui.QColor(0, 255, 0),
                        "red": QtGui.QColor(255, 0, 0),
                        "yellow": QtGui.QColor(255, 255, 0),
                        "UNKNOWN": QtGui.QColor(128, 128, 128),
                    }
                    text_color = color_map.get(status, QtGui.QColor(128, 128, 128))

                    font = painter.font()
                    font.setBold(True)
                    font.setPointSize(12)
                    painter.setFont(font)
                    painter.setPen(QtGui.QPen(text_color, 2))

                    label_text = status.upper()
                    fm = painter.fontMetrics()
                    text_width = fm.horizontalAdvance(label_text)
                    text_height = fm.height()
                    text_x = cx - text_width / 2
                    offset = text_height
                    text_y = cy - offset
                    painter.drawText(QtCore.QPointF(text_x, text_y), label_text)
        painter.end()