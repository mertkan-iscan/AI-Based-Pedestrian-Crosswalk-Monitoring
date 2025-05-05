import os
import shutil
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QFileDialog

from gui.CropDialog import CropDialog
from region import LocationManager
from stream.FrameExtractor import FrameExtractor
from gui.HomographySetterDialog import HomographySetterDialog

class EditLocationDialog(QtWidgets.QDialog):
    def __init__(self, location, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Location")
        self.resize(300, 420)
        self._original_location = location
        self.location = location.copy()
        self.homography_matrix = self.location.get("homography_matrix")
        self.bird_image_path = self.location.get("birds_eye_image")
        self.setupUI()

    def setupUI(self):
        layout = QtWidgets.QVBoxLayout(self)

        name_label = QtWidgets.QLabel("Location Name:")
        self.name_edit = QtWidgets.QLineEdit(self.location.get("name", ""))
        layout.addWidget(name_label)
        layout.addWidget(self.name_edit)

        type_group = QtWidgets.QGroupBox("Source Type:")
        type_layout = QtWidgets.QHBoxLayout(type_group)
        self.stream_radio = QtWidgets.QRadioButton("Live Stream")
        self.video_radio = QtWidgets.QRadioButton("Video File")
        if self.location.get("video_path"):
            self.video_radio.setChecked(True)
        else:
            self.stream_radio.setChecked(True)
        type_layout.addWidget(self.stream_radio)
        type_layout.addWidget(self.video_radio)
        layout.addWidget(type_group)

        self.stream_widget = QtWidgets.QWidget()
        s_layout = QtWidgets.QVBoxLayout(self.stream_widget)
        s_label = QtWidgets.QLabel("Stream URL:")
        self.stream_edit = QtWidgets.QLineEdit(self.location.get("stream_url", ""))
        s_layout.addWidget(s_label)
        s_layout.addWidget(self.stream_edit)
        layout.addWidget(self.stream_widget)

        self.video_widget = QtWidgets.QWidget()
        v_layout = QtWidgets.QVBoxLayout(self.video_widget)
        v_label = QtWidgets.QLabel("Video File:")
        self.video_path_edit = QtWidgets.QLineEdit(self.location.get("video_path", ""))
        browse_video_btn = QtWidgets.QPushButton("Browse Video")
        browse_video_btn.clicked.connect(self.browseVideoFile)
        file_layout = QtWidgets.QHBoxLayout()
        file_layout.addWidget(self.video_path_edit)
        file_layout.addWidget(browse_video_btn)
        v_layout.addWidget(v_label)
        v_layout.addLayout(file_layout)
        layout.addWidget(self.video_widget)

        self.stream_radio.toggled.connect(self.toggle_source_fields)
        self.video_radio.toggled.connect(self.toggle_source_fields)
        self.toggle_source_fields()

        upload_btn = QtWidgets.QPushButton("Upload Bird’s-Eye Image")
        upload_btn.clicked.connect(self.browseSatelliteImage)
        self.birdImageLabel = QtWidgets.QLabel()
        self.birdImageLabel.setFixedSize(150, 150)
        self.birdImageLabel.setAlignment(QtCore.Qt.AlignCenter)
        if self.bird_image_path:
            pix = QtGui.QPixmap(self.bird_image_path)
            self.birdImageLabel.setPixmap(pix)
        layout.addWidget(upload_btn)
        layout.addWidget(self.birdImageLabel)

        homo_btn = QtWidgets.QPushButton("Set Homography")
        homo_btn.clicked.connect(self.setHomography)
        self.homo_status = QtWidgets.QLabel(
            "Homography set." if self.homography_matrix else "Homography not set."
        )
        layout.addWidget(homo_btn)
        layout.addWidget(self.homo_status)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def toggle_source_fields(self):
        is_stream = self.stream_radio.isChecked()
        self.stream_widget.setVisible(is_stream)
        self.video_widget.setVisible(not is_stream)

    def browseVideoFile(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "", "Video Files (*.mp4 *.avi *.mkv *.mov)"
        )
        if path:
            self.video_path_edit.setText(path)

    def browseSatelliteImage(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Satellite Image", "", "Images (*.png *.jpg)"
        )
        if not path:
            return
        dlg = CropDialog(path, self)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        cropped = dlg.getCropped()
        name, ext = os.path.splitext(os.path.basename(path))
        save_dir = os.path.join(os.getcwd(), "resources", "satellite_images")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, f"{name}_cropped{ext}")
        cropped.save(save_path)
        self.bird_image_path = save_path
        self.birdImageLabel.setPixmap(cropped)

    def setHomography(self):
        if not self.bird_image_path:
            QtWidgets.QMessageBox.critical(self, "Error", "Upload a bird’s-eye image first.")
            return
        if self.video_radio.isChecked():
            frame = FrameExtractor.get_single_frame_file(self.video_path_edit.text().strip())
        else:
            frame = FrameExtractor.get_single_frame(self.stream_edit.text().strip())
        if frame is None:
            QtWidgets.QMessageBox.critical(self, "Error", "Cannot grab camera frame.")
            return
        dlg = HomographySetterDialog(frame, self.bird_image_path, self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.homography_matrix = dlg.get_homography()
            self.homo_status.setText("Homography set.")
        else:
            self.homo_status.setText("Homography not set.")

    def _on_ok(self):
        self._original_location["name"] = self.name_edit.text().strip()
        if self.video_radio.isChecked():
            self._original_location["video_path"] = self.video_path_edit.text().strip()
            self._original_location.pop("stream_url", None)
        else:
            self._original_location["stream_url"] = self.stream_edit.text().strip()
            self._original_location.pop("video_path", None)
        if hasattr(self, 'bird_image_path') and self.bird_image_path:
            self._original_location["birds_eye_image"] = self.bird_image_path
        if self.homography_matrix is not None:
            if hasattr(self.homography_matrix, "tolist"):
                self._original_location["homography_matrix"] = self.homography_matrix.tolist()
            else:
                self._original_location["homography_matrix"] = self.homography_matrix
        self.accept()

    def get_updated_location(self):
        return self._original_location
