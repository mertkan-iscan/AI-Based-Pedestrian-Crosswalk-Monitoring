import os
import shutil
import uuid
import json
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QFileDialog, QDialog

from gui.CropDialog import CropDialog
from region import LocationManager
from stream.FrameExtractor import FrameExtractor
from gui.HomographySetterDialog import HomographySetterDialog

class AddLocationDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Location")
        self.resize(300, 380)
        self.homography_matrix = None
        self.satellite_image = None
        self.setupUI()

    def setupUI(self):
        layout = QtWidgets.QVBoxLayout(self)

        name_label = QtWidgets.QLabel("Location Name:")
        self.name_edit = QtWidgets.QLineEdit()
        layout.addWidget(name_label)
        layout.addWidget(self.name_edit)

        # Source type as radio buttons side by side
        type_group = QtWidgets.QGroupBox("Source Type:")
        type_layout = QtWidgets.QHBoxLayout(type_group)
        self.stream_radio = QtWidgets.QRadioButton("Live Stream")
        self.video_radio = QtWidgets.QRadioButton("Video File")
        self.stream_radio.setChecked(True)
        type_layout.addWidget(self.stream_radio)
        type_layout.addWidget(self.video_radio)
        layout.addWidget(type_group)

        # Stream URL field
        self.stream_widget = QtWidgets.QWidget()
        stream_layout = QtWidgets.QVBoxLayout(self.stream_widget)
        stream_label = QtWidgets.QLabel("Stream URL:")
        self.stream_edit = QtWidgets.QLineEdit()
        stream_layout.addWidget(stream_label)
        stream_layout.addWidget(self.stream_edit)
        layout.addWidget(self.stream_widget)

        # Video file field
        self.video_widget = QtWidgets.QWidget()
        video_layout = QtWidgets.QVBoxLayout(self.video_widget)
        video_label = QtWidgets.QLabel("Video File:")
        self.video_path_edit = QtWidgets.QLineEdit()
        browse_btn = QtWidgets.QPushButton("Browse")
        browse_btn.clicked.connect(self.browseVideoFile)
        file_layout = QtWidgets.QHBoxLayout()
        file_layout.addWidget(self.video_path_edit)
        file_layout.addWidget(browse_btn)
        video_layout.addWidget(video_label)
        video_layout.addLayout(file_layout)
        layout.addWidget(self.video_widget)

        # Bird's eye view image field
        upload_btn = QtWidgets.QPushButton("Upload Bird’s-Eye Image")
        upload_btn.clicked.connect(self._upload_bird_image)
        self.bird_status = QtWidgets.QLabel("No image selected")
        layout.addWidget(upload_btn)
        layout.addWidget(self.bird_status)

        # Homography setter
        homo_btn = QtWidgets.QPushButton("Set Homography")
        homo_btn.clicked.connect(self.setHomography)
        self.homo_status = QtWidgets.QLabel("Homography not set.")
        layout.addWidget(homo_btn)
        layout.addWidget(self.homo_status)

        # Add/Cancel buttons
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        # Connect radio buttons to toggle
        self.stream_radio.toggled.connect(self.toggle_source_fields)
        self.video_radio.toggled.connect(self.toggle_source_fields)
        self.toggle_source_fields()

    def toggle_source_fields(self):
        is_stream = self.stream_radio.isChecked()
        self.stream_widget.setVisible(is_stream)
        self.video_widget.setVisible(not is_stream)

    def browseVideoFile(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Video File", "", "Video Files (*.mp4 *.avi *.mkv *.mov)"
        )
        if file_path:
            self.video_path_edit.setText(file_path)

    def browseSatelliteImage(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Satellite Image", "", "Images (*.png *.jpg)")
        if not path:
            return
        dlg = CropDialog(path, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        cropped = dlg.getCropped()
        name, ext = os.path.splitext(os.path.basename(path))
        save_dir = os.path.join(os.getcwd(), "resources", "satellite_images")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, f"{name}_cropped{ext}")
        cropped.save(save_path)
        self.bird_image_path = save_path
        self.birdImageLabel.setPixmap(cropped)

    def browseBirdsEyeImage(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Bird's Eye View Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not file_path:
            return
        dest_dir = os.path.join("resources", "satellite_images")
        os.makedirs(dest_dir, exist_ok=True)
        fname = os.path.basename(file_path)
        dest_path = os.path.join(dest_dir, fname)
        shutil.copy(file_path, dest_path)
        rel_path = os.path.relpath(dest_path, os.getcwd())
        self.satellite_image = rel_path
        self.birdseye_path_edit.setText(rel_path)

    def setHomography(self):
        # retrieve a camera frame as before
        camera_frame = FrameExtractor.get_single_frame(self.stream_edit.text().strip())
        if camera_frame is None:
            QtWidgets.QMessageBox.critical(self, "Error", "Could not retrieve a frame.")
            return
        if not self.satellite_image:
            QtWidgets.QMessageBox.critical(self, "Error", "Please select a bird’s-eye image first.")
            return
        dialog = HomographySetterDialog(camera_frame, self.satellite_image, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            H = dialog.get_homography()
            self.homography_matrix = H
            self.homography_status_label.setText("Homography set successfully.")
        else:
            self.homography_status_label.setText("Homography not set.")

    def add_location(self):
        name = self.name_edit.text().strip()
        # [ validate source fields as before ... ]
        new_loc = {"name": name, "polygons_file": os.path.join("resources", "location_regions", f"polygons_{uuid.uuid4().hex}.json")}
        if self.stream_radio.isChecked():
            new_loc["stream_url"] = self.stream_edit.text().strip()
        else:
            new_loc["video_path"] = self.video_path_edit.text().strip()
        if self.satellite_image:
            new_loc["birds_eye_image"] = self.satellite_image
        if self.homography_matrix is not None:
            new_loc["homography_matrix"] = self.homography_matrix.tolist()
        LocationManager.add_location(new_loc)
        # ensure polygons file exists
        if not os.path.exists(new_loc["polygons_file"]):
            with open(new_loc["polygons_file"], "w") as f:
                json.dump([], f, indent=4)
        self.accept()

    def _upload_bird_image(self):
        fp, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Bird’s-Eye Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not fp:
            return
        dest = os.path.join("resources", "satellite_images")
        os.makedirs(dest, exist_ok=True)
        name = os.path.basename(fp)
        dst = os.path.join(dest, name)
        shutil.copy(fp, dst)
        rel = os.path.relpath(dst, os.getcwd())
        self.satellite_image = rel
        self.bird_status.setText(f"Selected: {rel}")

    def setHomography(self):
        if not self.satellite_image:
            QtWidgets.QMessageBox.critical(self, "Error", "Upload a bird’s-eye image first.")
            return
        frame = FrameExtractor.get_single_frame(self.stream_edit.text().strip())
        if frame is None:
            QtWidgets.QMessageBox.critical(self, "Error", "Cannot grab camera frame.")
            return
        dlg = HomographySetterDialog(frame, self.satellite_image, self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.homography_matrix = dlg.get_homography()
            self.homo_status.setText("Homography set.")
        else:
            self.homo_status.setText("Homography not set.")

    def _on_ok(self):
        name = self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Validation", "Name is required.")
            return
        loc = {
            "name": name,
            "polygons_file": os.path.join(
                "resources", "location_regions", f"polygons_{uuid.uuid4().hex}.json"
            )
        }
        if self.stream_radio.isChecked():
            loc["stream_url"] = self.stream_edit.text().strip()
        else:
            loc["video_path"] = self.video_path_edit.text().strip()
        if self.satellite_image:
            loc["birds_eye_image"] = self.satellite_image
        if self.homography_matrix is not None:
            loc["homography_matrix"] = self.homography_matrix.tolist()
        LocationManager.add_location(loc)
        os.makedirs(os.path.dirname(loc["polygons_file"]), exist_ok=True)
        with open(loc["polygons_file"], "w") as f:
            json.dump([], f, indent=4)
        self.accept()