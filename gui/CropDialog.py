from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QGraphicsView, QGraphicsScene
from PyQt5.QtGui import QPixmap, QPainter
from PyQt5.QtCore import Qt, QRectF, QPointF

class PanZoomView(QGraphicsView):
    def __init__(self, pixmap, square_size=400, parent=None):
        super().__init__(parent)
        scene = QGraphicsScene(self)
        self.pixmap_item = scene.addPixmap(pixmap)
        self.setScene(scene)
        self.square_size = square_size
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.fitInView(self.pixmap_item.boundingRect(), Qt.KeepAspectRatio)
        self._update_scene_rect()

    def _update_scene_rect(self):
        pix = self.pixmap_item.boundingRect()
        scale = self.transform().m11()
        half = self.square_size / 2 / scale
        rect = QRectF(pix.left()-half, pix.top()-half,
                      pix.width()+2*half, pix.height()+2*half)
        self.setSceneRect(rect)

    def wheelEvent(self, event):
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        old_scale = self.transform().m11()
        new_scale = old_scale * factor
        pix = self.pixmap_item.boundingRect()
        min_scale = max(self.square_size/pix.width(), self.square_size/pix.height())
        if new_scale < min_scale:
            factor = min_scale/old_scale
        self.scale(factor, factor)
        self._update_scene_rect()
        self._clamp_pan()
        event.accept()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._clamp_pan()

    def _clamp_pan(self):
        sel = self.get_crop_rect_in_image()
        pix = self.pixmap_item.boundingRect()
        dx = dy = 0.0
        if sel.left() < pix.left(): dx = sel.left()-pix.left()
        if sel.right() > pix.right(): dx = sel.right()-pix.right()
        if sel.top() < pix.top(): dy = sel.top()-pix.top()
        if sel.bottom() > pix.bottom(): dy = sel.bottom()-pix.bottom()
        if dx or dy:
            center = self.mapToScene(self.viewport().rect().center())
            self.centerOn(QPointF(center.x()-dx, center.y()-dy))

    def drawForeground(self, painter, rect):
        painter.save()
        painter.resetTransform()
        vp = self.viewport().rect()
        half = self.square_size/2
        center = QPointF(vp.width()/2, vp.height()/2)
        square = QRectF(center.x()-half, center.y()-half,
                        self.square_size, self.square_size)
        painter.setPen(Qt.red)
        painter.drawRect(square)
        painter.restore()

    def get_crop_rect_in_image(self):
        vp = self.viewport().rect()
        half = self.square_size/2
        cx, cy = vp.width()/2, vp.height()/2
        tl = QPointF(cx-half, cy-half)
        br = QPointF(cx+half, cy+half)
        tl_s = self.mapToScene(tl.toPoint())
        br_s = self.mapToScene(br.toPoint())
        return QRectF(tl_s, br_s)

class CropDialog(QDialog):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crop and Zoom")
        self.resize(800, 600)
        pix = QPixmap(image_path)
        self.view = PanZoomView(pix)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)

        ok = QPushButton("OK"); cancel = QPushButton("Cancel")
        ok.clicked.connect(self.accept); cancel.clicked.connect(self.reject)
        hb = QHBoxLayout(); hb.addWidget(ok); hb.addWidget(cancel)

        vb = QVBoxLayout(self)
        vb.addWidget(self.view)
        vb.addLayout(hb)

    def getCropped(self):
        rect = self.view.get_crop_rect_in_image().toRect()
        img = self.view.pixmap_item.pixmap().toImage()
        cr = rect.intersected(img.rect())
        c = img.copy(cr)
        return QPixmap.fromImage(c).scaled(
            600, 600, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
