# CropDialog.py
from PyQt5.QtWidgets import QDialog, QLabel, QRubberBand, QPushButton, QVBoxLayout, QHBoxLayout
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QRect, QSize

class CropDialog(QDialog):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.orig_pixmap = QPixmap(image_path)
        self.label = QLabel(self)
        self.label.setPixmap(self.orig_pixmap)
        self.label.setAlignment(Qt.AlignCenter)
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self.label)
        self.origin = None
        self.crop_rect = None
        self.ok_btn = QPushButton("OK", self)
        self.cancel_btn = QPushButton("Cancel", self)

        v = QVBoxLayout(self)
        v.addWidget(self.label)
        h = QHBoxLayout()
        h.addWidget(self.ok_btn)
        h.addWidget(self.cancel_btn)
        v.addLayout(h)

        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        self.label.mousePressEvent = self._start
        self.label.mouseMoveEvent = self._move
        self.label.mouseReleaseEvent = self._end

    def _start(self, e):
        if e.button() == Qt.LeftButton:
            self.origin = e.pos()
            self.rubberBand.setGeometry(QRect(self.origin, QSize()))
            self.rubberBand.show()

    def _move(self, e):
        if self.origin:
            d = max(abs(e.x()-self.origin.x()), abs(e.y()-self.origin.y()))
            r = QRect(self.origin, QSize(d, d)).normalized()
            self.rubberBand.setGeometry(r)

    def _end(self, e):
        if e.button() == Qt.LeftButton:
            self.crop_rect = self.rubberBand.geometry()
            self.rubberBand.hide()

    def getCropped(self):
        if not self.crop_rect:
            return None
        pm = self.orig_pixmap.copy(self.crop_rect)
        return pm.scaled(600, 600, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
