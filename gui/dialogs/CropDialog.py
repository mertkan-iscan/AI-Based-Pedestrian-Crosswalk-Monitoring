from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QGraphicsView,
    QGraphicsScene,
)
from PyQt5.QtGui import QPixmap, QPainter, QPen
from PyQt5.QtCore import Qt, QRectF, QPointF


class PanZoomView(QGraphicsView):
    def __init__(self, pixmap: QPixmap, square_size: int = 400, parent=None):
        super().__init__(parent)
        self.square_size = square_size

        scene = QGraphicsScene(self)
        self.pixmap_item = scene.addPixmap(pixmap)
        self.setScene(scene)

        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setRenderHint(QPainter.SmoothPixmapTransform)

        self.fitInView(self.pixmap_item.boundingRect(), Qt.KeepAspectRatio)
        self._update_scene_rect()

    def _update_scene_rect(self):
        pix = self.pixmap_item.boundingRect()
        scale = self.transform().m11()
        half = self.square_size / 2 / scale
        self.setSceneRect(
            QRectF(
                pix.left() - half,
                pix.top() - half,
                pix.width() + 2 * half,
                pix.height() + 2 * half,
            )
        )

    def wheelEvent(self, event):
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        cur_scale = self.transform().m11()
        pix = self.pixmap_item.boundingRect()
        min_scale = max(self.square_size / pix.width(), self.square_size / pix.height())
        if cur_scale * factor < min_scale:
            factor = min_scale / cur_scale
        self.scale(factor, factor)
        self._update_scene_rect()
        self._clamp_pan()
        event.accept()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.viewport().update()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._clamp_pan()

    def _clamp_pan(self):
        crop_rect = self.get_crop_rect_in_image()
        pix = self.pixmap_item.boundingRect()
        dx = dy = 0.0
        if crop_rect.left() < pix.left():
            dx = crop_rect.left() - pix.left()
        if crop_rect.right() > pix.right():
            dx = crop_rect.right() - pix.right()
        if crop_rect.top() < pix.top():
            dy = crop_rect.top() - pix.top()
        if crop_rect.bottom() > pix.bottom():
            dy = crop_rect.bottom() - pix.bottom()
        if dx or dy:
            center = self.mapToScene(self.viewport().rect().center())
            self.centerOn(QPointF(center.x() - dx, center.y() - dy))

    def drawForeground(self, painter: QPainter, _rect):
        painter.save()
        painter.resetTransform()
        vp = self.viewport().rect()
        half = self.square_size / 2
        center = QPointF(vp.width() / 2, vp.height() / 2)
        square = QRectF(
            center.x() - half,
            center.y() - half,
            self.square_size,
            self.square_size,
        )
        painter.setPen(QPen(Qt.red, 2))
        painter.drawRect(square)
        painter.restore()

    def get_crop_rect_in_image(self) -> QRectF:
        vp = self.viewport().rect()
        half = self.square_size / 2
        cx, cy = vp.width() / 2, vp.height() / 2
        tl = QPointF(cx - half, cy - half)
        br = QPointF(cx + half, cy + half)
        return QRectF(
            self.mapToScene(int(tl.x()), int(tl.y())),
            self.mapToScene(int(br.x()), int(br.y())),
        )


class CropDialog(QDialog):
    def __init__(
        self,
        image_path: str,
        parent=None,
        square_size: int = 400,
        preview_size: int = 600,
    ):
        super().__init__(parent)
        self.square_size = square_size
        self.preview_size = preview_size
        self.setWindowTitle("Crop Image")
        self.resize(800, 600)

        pixmap = QPixmap(image_path)
        self.view = PanZoomView(pixmap, square_size=square_size)

        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        btns = QHBoxLayout()
        btns.addStretch()
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        layout.addLayout(btns)

    def getCropped(self) -> QPixmap:
        rect = self.view.get_crop_rect_in_image().toRect()
        image = self.view.pixmap_item.pixmap().toImage()
        crop = rect.intersected(image.rect())
        return QPixmap.fromImage(image.copy(crop)).scaled(
            self.preview_size,
            self.preview_size,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation,
        )
