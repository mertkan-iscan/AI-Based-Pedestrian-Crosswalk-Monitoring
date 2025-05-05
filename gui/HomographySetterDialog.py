import cv2
import numpy as np
from PyQt5.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox
from PyQt5.QtCore    import Qt, pyqtSignal
from PyQt5.QtGui     import QPixmap, QImage, QPainter, QPen

def apply_homography(pt, H):
    p = np.array([pt[0], pt[1], 1.0]).reshape(3,1)
    t = H.dot(p)
    t /= t[2,0]
    return (float(t[0,0]), float(t[1,0]))

class ClickableImageLabel(QLabel):
    clicked = pyqtSignal(int,int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_points = []
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            x,y = e.pos().x(), e.pos().y()
            self.selected_points.append((x,y))
            self.clicked.emit(x,y)
            self.update()
        super().mousePressEvent(e)
    def paintEvent(self, ev):
        super().paintEvent(ev)
        painter = QPainter(self)
        pen = QPen(Qt.green); pen.setWidth(5)
        painter.setPen(pen)
        for pt in self.selected_points:
            painter.drawEllipse(pt[0]-3, pt[1]-3, 7,7)
        painter.end()

class HomographySetterDialog(QDialog):
    def __init__(self, camera_image, bird_image_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Homography Setter")
        self.camera_image = camera_image.copy()
        self.bird_image   = cv2.imread(bird_image_path)
        self.bird_points  = []
        self.camera_points= []
        self.camera_scale = 1.0
        self.bird_scale   = 1.0
        self.homography_matrix = None
        self.initUI()
        self.display_bird_image()

    def initUI(self):
        layout = QVBoxLayout(self)
        self.instruction_label = QLabel("Select point pairs: first on BIRD image, then on CAMERA image.")
        self.instruction_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.instruction_label)

        img_layout = QHBoxLayout()
        self.bird_label   = ClickableImageLabel()
        self.bird_label.setAlignment(Qt.AlignCenter)
        img_layout.addWidget(self.bird_label)
        self.camera_label = ClickableImageLabel()
        img_layout.addWidget(self.camera_label)
        layout.addLayout(img_layout)

        btn_layout = QHBoxLayout()
        self.compute_btn = QPushButton("Compute Homography")
        self.compute_btn.setEnabled(False)
        self.compute_btn.clicked.connect(self.computeHomography)
        clear_btn = QPushButton("Clear Points"); clear_btn.clicked.connect(self.clearPoints)
        cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.compute_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.bird_label.clicked.connect(lambda x,y: self.handleClick(x,y,"bird"))
        self.camera_label.clicked.connect(lambda x,y: self.handleClick(x,y,"camera"))

    def display_bird_image(self):
        rgb = cv2.cvtColor(self.bird_image, cv2.COLOR_BGR2RGB)
        h,w,_ = rgb.shape
        bytes_line = 3 * w
        qimg = QImage(rgb.data, w, h, bytes_line, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        max_w, max_h = 800, 600
        if pix.width()>max_w or pix.height()>max_h:
            sf = min(max_w/pix.width(), max_h/pix.height())
            self.bird_scale = sf
            pix = pix.scaled(int(pix.width()*sf), int(pix.height()*sf), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.bird_label.setPixmap(pix)
        self.bird_label.setFixedSize(pix.size())
        self.updateCameraLabel()

    def updateCameraLabel(self):
        rgb = cv2.cvtColor(self.camera_image, cv2.COLOR_BGR2RGB)
        h,w,_ = rgb.shape
        qimg = QImage(rgb.data, w, h, 3*w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        max_w, max_h = 800,600
        if pix.width()>max_w or pix.height()>max_h:
            sf = min(max_w/pix.width(), max_h/pix.height())
            self.camera_scale = sf
            pix = pix.scaled(int(pix.width()*sf), int(pix.height()*sf), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.camera_label.setPixmap(pix)
        self.camera_label.setFixedSize(pix.size())

    def handleClick(self, x, y, view):
        if view=="bird":
            ox,oy = x/self.bird_scale, y/self.bird_scale
            self.bird_points.append((ox,oy))
            self.instruction_label.setText("Now select on CAMERA image.")
        else:
            ox,oy = x/self.camera_scale, y/self.camera_scale
            self.camera_points.append((ox,oy))
            self.instruction_label.setText("Now select on BIRD image.")
        if len(self.bird_points)>=4 and len(self.camera_points)>=4:
            self.compute_btn.setEnabled(True)

    def clearPoints(self):
        self.bird_points=[]; self.camera_points=[]
        self.bird_label.selected_points=[]; self.bird_label.update()
        self.camera_label.selected_points=[]; self.camera_label.update()
        self.compute_btn.setEnabled(False)
        self.instruction_label.setText("Points cleared.")

    def computeHomography(self):
        n = min(len(self.bird_points), len(self.camera_points))
        if n<4:
            QMessageBox.warning(self, "Error", "Need at least 4 pairs.")
            return
        pts_b = np.array(self.bird_points[:n], dtype=np.float32)
        pts_c = np.array(self.camera_points[:n], dtype=np.float32)
        H, mask = cv2.findHomography(pts_c, pts_b, cv2.RANSAC, 5.0)
        if H is None:
            QMessageBox.warning(self, "Error", "Homography failed.")
            return
        self.homography_matrix = H
        QMessageBox.information(self, "Result", "Homography computed.")
        self.accept()

    def get_homography(self):
        return self.homography_matrix
