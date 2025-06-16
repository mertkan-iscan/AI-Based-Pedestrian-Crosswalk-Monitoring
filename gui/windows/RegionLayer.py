from PyQt5 import QtCore, QtGui, QtWidgets
import numpy as np

class RegionLayer(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.regions = []
        self.original_frame_size = (1, 1)
        self.scaled_pixmap_size = (1, 1)

    def set_regions(self, regions, original_frame_size, scaled_pixmap_size):
        self.regions = regions
        self.original_frame_size = original_frame_size
        self.scaled_pixmap_size = scaled_pixmap_size
        self.update()

    def paintEvent(self, event):
        if not self.regions or self.original_frame_size == (1, 1):
            return
        painter = QtGui.QPainter(self)
        color_map = {
            "detection_blackout": QtGui.QColor(50, 50, 50, 120),
            "road": QtGui.QColor(50, 50, 50, 120),
            "sidewalk": QtGui.QColor(255, 255, 0, 120),
            "deletion_area": QtGui.QColor(255, 0, 255, 120),
            "deletion_line": QtGui.QColor(0, 255, 255, 120),
            "crop_area": QtGui.QColor(0, 255, 0, 60),
            "crosswalk": QtGui.QColor(0, 255, 255, 80),
            "car_wait": QtGui.QColor(255, 102, 102, 90),
            "pedes_wait": QtGui.QColor(0, 153, 0, 80),
        }
        ow, oh = self.original_frame_size
        sw, sh = self.scaled_pixmap_size

        scale = min(sw / ow, sh / oh) if ow and oh else 1.0
        off_x = (self.width() - ow * scale) / 2
        off_y = (self.height() - oh * scale) / 2

        for region in self.regions:
            rtype = region.get("type", "")
            pts = region.get("points", [])

            if len(pts) == 0:
                continue

            poly = np.array(pts, np.int32)
            poly = ((poly * scale) + np.array([off_x, off_y])).astype(int)
            color = color_map.get(rtype, QtGui.QColor(255, 0, 0, 60))

            if rtype == "deletion_line":
                painter.setPen(QtGui.QPen(color, 3))
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.drawPolyline(QtGui.QPolygon([QtCore.QPoint(pt[0], pt[1]) for pt in poly]))

            elif rtype == "crop_area" and len(pts) == 2:
                painter.setPen(QtGui.QPen(color, 2))
                painter.setBrush(color)
                painter.drawRect(QtCore.QRect(QtCore.QPoint(*poly[0]), QtCore.QPoint(*poly[1])))

            else:
                painter.setPen(QtGui.QPen(color, 2))
                painter.setBrush(color)
                painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(pt[0], pt[1]) for pt in poly]))

        painter.end()
