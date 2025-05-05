from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QGraphicsView, QGraphicsScene
from PyQt5.QtGui import QPixmap, QPainter
from PyQt5.QtCore import Qt, QRectF, QPointF, QSizeF

class PanZoomView(QGraphicsView):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        scene = QGraphicsScene(self)
        self.pix_item = scene.addPixmap(pixmap)
        self.setScene(scene)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def wheelEvent(self, event):
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.scale(factor, factor)
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Expand the scene rect so users can pan even when image is smaller than view
        rect = self.pix_item.boundingRect()
        vp = self.viewport().size()
        expanded = QRectF(
            rect.x() - vp.width() / 2,
            rect.y() - vp.height() / 2,
            rect.width() + vp.width(),
            rect.height() + vp.height()
        )
        self.setSceneRect(expanded)

    def drawForeground(self, painter, rect):
        painter.save()
        painter.resetTransform()
        vp = self.viewport().rect()
        side = min(vp.width(), vp.height()) * 0.8
        half = side / 2
        center = QPointF(vp.width() / 2, vp.height() / 2)
        top_left = QPointF(center.x() - half, center.y() - half)
        square = QRectF(top_left, QSizeF(side, side))
        painter.setPen(Qt.red)
        painter.drawRect(square)
        painter.restore()

    def getCropRectInImage(self):
        vp = self.viewport().rect()
        side = min(vp.width(), vp.height()) * 0.8
        half = side / 2
        tl_v = QPointF(vp.width() / 2 - half, vp.height() / 2 - half)
        br_v = QPointF(vp.width() / 2 + half, vp.height() / 2 + half)
        tl_s = self.mapToScene(tl_v.toPoint())
        br_s = self.mapToScene(br_v.toPoint())
        return QRectF(tl_s, br_s)

class CropDialog(QDialog):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crop and Zoom")
        self.resize(800, 600)

        pixmap = QPixmap(image_path)
        self.view = PanZoomView(pixmap)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.view.fitInView(self.view.sceneRect(), Qt.KeepAspectRatio)

        self.ok_btn = QPushButton("OK")
        self.cancel_btn = QPushButton("Cancel")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        layout.addLayout(btn_layout)

    def getCropped(self):
        rect = self.view.getCropRectInImage().toRect()
        img = self.view.pix_item.pixmap().toImage()
        crop_rect = rect.intersected(img.rect())
        cropped_img = img.copy(crop_rect)
        return QPixmap.fromImage(cropped_img).scaled(
            600, 600,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation
        )
