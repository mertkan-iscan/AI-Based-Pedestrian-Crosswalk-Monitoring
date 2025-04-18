import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen


def apply_homography(pt, H_matrix):
    """
    Applies a homography to a 2D point.
    pt: (x, y)
    Returns: (x', y')
    """
    point = np.array([pt[0], pt[1], 1.0]).reshape(3, 1)
    transformed = np.dot(H_matrix, point)
    transformed /= transformed[2, 0]
    return (float(transformed[0, 0]), float(transformed[1, 0]))


class ClickableImageLabel(QLabel):
    """
    QLabel that emits a clicked(x,y) signal.
    Also draws small circles for each selected point.
    """
    clicked = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_points = []  # List of (x,y) tuples

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            x, y = event.pos().x(), event.pos().y()
            self.selected_points.append((x, y))
            self.clicked.emit(x, y)
            self.update()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        pen = QPen(Qt.green)
        pen.setWidth(5)
        painter.setPen(pen)
        for pt in self.selected_points:
            painter.drawEllipse(pt[0] - 3, pt[1] - 3, 7, 7)
        painter.end()


class HomographySetterDialog(QDialog):
    """
    A dialog that displays two images side by side – one for the bird‑eye view (uploaded by the user)
    and one for the camera image (obtained from your frame extractor).

    The user is instructed to select corresponding points in alternating order: first on the
    bird‑eye view image, then on the CAMERA image. Once a minimum of 4 pairs are collected,
    the user can compute the homography transformation matrix.

    This updated version limits the displayed camera frame size (e.g., maximum width=800, height=600)
    and stores a scale factor so that click coordinates are mapped back to the original camera frame.
    """

    def __init__(self, camera_image, parent=None):
        """
        :param camera_image: A BGR (numpy array) image from the camera (frame extractor result)
        """
        super().__init__(parent)
        self.setWindowTitle("Homography Setter")
        self.camera_image = camera_image.copy()  # original camera image (numpy array)
        self.bird_image = None  # will be loaded via file dialog

        # We store corresponding points (each as (x,y))
        self.bird_points = []
        self.camera_points = []

        # For converting clicks, store scale factors for images (if scaled for display)
        self.camera_scale = 1.0
        self.bird_scale = 1.0

        # The computed homography matrix.
        self.homography_matrix = None

        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout(self)

        # Instruction label.
        self.instruction_label = QLabel("Upload bird‑eye view image and then click points.\n" +
                                        "Select point pairs in order: first on BIRD image, then on CAMERA image.")
        self.instruction_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.instruction_label)

        # Create two image display labels side by side.
        images_layout = QHBoxLayout()
        self.bird_label = ClickableImageLabel()
        self.bird_label.setText("No bird‑eye view image.\nClick 'Load Bird Image' below.")
        self.bird_label.setAlignment(Qt.AlignCenter)
        images_layout.addWidget(self.bird_label)

        self.camera_label = ClickableImageLabel()
        self.updateCameraLabel()
        images_layout.addWidget(self.camera_label)
        main_layout.addLayout(images_layout)

        # Buttons layout: Load Bird Image, Compute Homography, Clear Points, Cancel.
        btn_layout = QHBoxLayout()
        load_btn = QPushButton("Load Bird Image")
        load_btn.clicked.connect(self.loadBirdImage)
        btn_layout.addWidget(load_btn)

        self.compute_btn = QPushButton("Compute Homography")
        self.compute_btn.clicked.connect(self.computeHomography)
        self.compute_btn.setEnabled(False)
        btn_layout.addWidget(self.compute_btn)

        clear_btn = QPushButton("Clear Points")
        clear_btn.clicked.connect(self.clearPoints)
        btn_layout.addWidget(clear_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        main_layout.addLayout(btn_layout)

        # Connect signals: when a point is clicked, call our handler.
        self.bird_label.clicked.connect(lambda x, y: self.handleClick(x, y, "bird"))
        self.camera_label.clicked.connect(lambda x, y: self.handleClick(x, y, "camera"))

    def updateCameraLabel(self):
        """
        Converts camera_image (BGR numpy array) to a QPixmap,
        scales it down if its dimensions exceed a maximum size, and displays it.
        Also stores the scale factor (camera_scale) for converting coordinates.
        """
        if self.camera_image is not None:
            rgb = cv2.cvtColor(self.camera_image, cv2.COLOR_BGR2RGB)
            height, width, channels = rgb.shape
            bytes_per_line = 3 * width
            qimg = QImage(rgb.data, width, height, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)

            # Limit camera image display size.
            max_width = 800
            max_height = 600
            self.camera_scale = 1.0  # default (no scaling)
            if pixmap.width() > max_width or pixmap.height() > max_height:
                scale_factor = min(max_width / pixmap.width(), max_height / pixmap.height())
                self.camera_scale = scale_factor
                pixmap = pixmap.scaled(int(pixmap.width() * scale_factor),
                                       int(pixmap.height() * scale_factor),
                                       Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.camera_label.setPixmap(pixmap)
            self.camera_label.setFixedSize(pixmap.size())

    def loadBirdImage(self):
        # Open file dialog for the user to select a bird‑eye view image.
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Bird‑Eye View Image", "",
                                                   "Images (*.png *.jpg *.bmp)")
        if file_path:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                QMessageBox.critical(self, "Error", "Failed to load the image.")
                return
            # Optionally, you can also limit the bird image display size.
            self.bird_scale = 1.0
            max_width = 800
            max_height = 600
            if pixmap.width() > max_width or pixmap.height() > max_height:
                scale_factor = min(max_width / pixmap.width(), max_height / pixmap.height())
                self.bird_scale = scale_factor
                pixmap = pixmap.scaled(int(pixmap.width() * scale_factor),
                                       int(pixmap.height() * scale_factor),
                                       Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.bird_label.setPixmap(pixmap)
            self.bird_label.setFixedSize(pixmap.size())
            self.bird_image = cv2.imread(file_path)  # store original bird image (BGR)
            self.bird_points = []  # reset any previous selections
            self.camera_points = []
            self.compute_btn.setEnabled(False)
            self.instruction_label.setText("Bird image loaded. Now select corresponding points:\n" +
                                           "Click a point on the BIRD image, then on the CAMERA image.")

    def handleClick(self, x, y, view):
        """
        Records the clicked point and converts display coordinates to original coordinates,
        if the image was scaled.
        """
        if view == "bird":
            if self.bird_image is None:
                QMessageBox.information(self, "Info", "Please load a bird‑eye view image first.")
                return
            # Convert clicked display coordinate to original coordinate using bird_scale.
            orig_x = x / self.bird_scale
            orig_y = y / self.bird_scale
            self.bird_points.append((orig_x, orig_y))
            print(f"Bird point {len(self.bird_points)}: ({orig_x}, {orig_y})")
            self.instruction_label.setText("Now click the corresponding point on the CAMERA image.")
        elif view == "camera":
            # Convert display coordinates back to original using camera_scale.
            orig_x = x / self.camera_scale
            orig_y = y / self.camera_scale
            self.camera_points.append((orig_x, orig_y))
            print(f"Camera point {len(self.camera_points)}: ({orig_x}, {orig_y})")
            self.instruction_label.setText("Select the next point on the BIRD image.")

        # Enable compute button if we have at least 4 corresponding pairs.
        if len(self.bird_points) >= 4 and len(self.camera_points) >= 4:
            self.compute_btn.setEnabled(True)

    def clearPoints(self):
        self.bird_points = []
        self.camera_points = []
        self.bird_label.selected_points = []
        self.bird_label.update()
        self.camera_label.selected_points = []
        self.camera_label.update()
        self.compute_btn.setEnabled(False)
        self.instruction_label.setText("Points cleared. Please reselect corresponding points.")

    def computeHomography(self):
        n_pairs = min(len(self.bird_points), len(self.camera_points))
        if n_pairs < 4:
            QMessageBox.warning(self, "Error", "At least 4 pairs are needed.")
            return
        pts_bird = np.array(self.bird_points[:n_pairs], dtype=np.float32)
        pts_cam = np.array(self.camera_points[:n_pairs], dtype=np.float32)
        H_matrix, mask = cv2.findHomography(pts_cam, pts_bird, cv2.RANSAC, 5.0)
        if H_matrix is None:
            QMessageBox.warning(self, "Error", "Homography computation failed. Please reselect points.")
            return
        self.homography_matrix = H_matrix
        result_text = "Computed Homography Matrix:\n" + np.array2string(H_matrix, precision=4)
        QMessageBox.information(self, "Homography", result_text)
        self.accept()

    def get_homography(self):
        """
        After the dialog is accepted, return the computed homography matrix.
        Returns None if no valid homography was computed.
        """
        return self.homography_matrix
