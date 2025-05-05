import os
import uuid
import json
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QFileDialog
from gui.CropDialog import CropDialog
from region import LocationManager
from stream.FrameExtractor import FrameExtractor
from gui.HomographySetterDialog import HomographySetterDialog

class AddLocationDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Location")
        self.resize(300, 420)
        self.homography_matrix = None
        self.bird_image_path = None
        self.setupUI()

    def setupUI(self):
        layout = QtWidgets.QVBoxLayout(self)

        name_label = QtWidgets.QLabel("Location Name:")
        self.name_edit = QtWidgets.QLineEdit()
        layout.addWidget(name_label)
        layout.addWidget(self.name_edit)

        type_group = QtWidgets.QGroupBox("Source Type:")
        type_layout = QtWidgets.QHBoxLayout(type_group)
        self.stream_radio = QtWidgets.QRadioButton("Live Stream")
        self.video_radio = QtWidgets.QRadioButton("Video File")
        self.stream_radio.setChecked(True)
        type_layout.addWidget(self.stream_radio)
        type_layout.addWidget(self.video_radio)
        layout.addWidget(type_group)

        self.stream_widget = QtWidgets.QWidget()
        stream_layout = QtWidgets.QVBoxLayout(self.stream_widget)
        stream_label = QtWidgets.QLabel("Stream URL:")
        self.stream_edit = QtWidgets.QLineEdit()
        stream_layout.addWidget(stream_label)
        stream_layout.addWidget(self.stream_edit)
        layout.addWidget(self.stream_widget)

        self.video_widget = QtWidgets.QWidget()
        video_layout = QtWidgets.QVBoxLayout(self.video_widget)
        video_label = QtWidgets.QLabel("Video File:")
        self.video_path_edit = QtWidgets.QLineEdit()
        browse_video_btn = QtWidgets.QPushButton("Browse")
        browse_video_btn.clicked.connect(self.browseVideoFile)
        file_layout = QtWidgets.QHBoxLayout()
        file_layout.addWidget(self.video_path_edit)
        file_layout.addWidget(browse_video_btn)
        video_layout.addWidget(video_label)
        video_layout.addLayout(file_layout)
        layout.addWidget(self.video_widget)

        upload_btn = QtWidgets.QPushButton("Upload Bird’s-Eye Image")
        upload_btn.clicked.connect(self.browseSatelliteImage)
        self.birdImageLabel = QtWidgets.QLabel()
        self.birdImageLabel.setFixedSize(150, 150)
        self.birdImageLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.birdImageLabel.setScaledContents(True)
        layout.addWidget(upload_btn)
        layout.addWidget(self.birdImageLabel)

        homo_btn = QtWidgets.QPushButton("Set Homography")
        homo_btn.clicked.connect(self.setHomography)
        self.homo_status = QtWidgets.QLabel("Homography not set.")
        layout.addWidget(homo_btn)
        layout.addWidget(self.homo_status)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self.stream_radio.toggled.connect(self.toggle_source_fields)
        self.video_radio.toggled.connect(self.toggle_source_fields)
        self.toggle_source_fields()

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
            QtWidgets.QMessageBox.critical(
                self, "Error", "Please upload a bird’s-eye image first."
            )
            return
        cam_frame = FrameExtractor.get_single_frame(
            self.stream_edit.text().strip()
        )
        if cam_frame is None:
            QtWidgets.QMessageBox.critical(
                self, "Error", "Could not retrieve a camera frame."
            )
            return
        dlg = HomographySetterDialog(cam_frame, self.bird_image_path, self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.homography_matrix = dlg.get_homography()
            self.homo_status.setText("Homography set successfully.")
        else:
            self.homo_status.setText("Homography not set.")

    def _on_ok(self):
        name = self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Validation", "Name is required.")
            return
        loc = {"name": name,
               "polygons_file": os.path.join(
                   "resources", "location_regions", f"polygons_{uuid.uuid4().hex}.json"
               )}
        if self.stream_radio.isChecked():
            loc["stream_url"] = self.stream_edit.text().strip()
        else:
            loc["video_path"] = self.video_path_edit.text().strip()
        if self.bird_image_path:
            loc["birds_eye_image"] = self.bird_image_path
        if self.homography_matrix is not None:
            loc["homography_matrix"] = self.homography_matrix.tolist()
        LocationManager.add_location(loc)
        os.makedirs(os.path.dirname(loc["polygons_file"]), exist_ok=True)
        with open(loc["polygons_file"], "w") as f:
            json.dump([], f, indent=4)
        self.accept()
