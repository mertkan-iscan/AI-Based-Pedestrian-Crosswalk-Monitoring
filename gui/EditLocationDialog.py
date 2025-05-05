import os
import shutil

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QFileDialog, QDialog

from gui.CropDialog import CropDialog
from stream.FrameExtractor import FrameExtractor
from gui.HomographySetterDialog import HomographySetterDialog


class EditLocationDialog(QtWidgets.QDialog):
    def __init__(self, location, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Location")
        self.location = location.copy()
        self.homography_matrix = self.location.get("homography_matrix", None)
        self.satellite_image = self.location.get("birds_eye_image", None)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)

        # Name field
        self.name_edit = QtWidgets.QLineEdit(self.location.get("name", ""))
        layout.addRow("Name:", self.name_edit)

        # Source field: stream or video
        if self.location.get("video_path"):
            self.location_type = "video"
            self.edit_field = QtWidgets.QLineEdit(self.location["video_path"])
            browse_src = QtWidgets.QPushButton("Browse")
            browse_src.clicked.connect(self._browse_video_file)
            src_layout = QtWidgets.QHBoxLayout()
            src_layout.addWidget(self.edit_field)
            src_layout.addWidget(browse_src)
            layout.addRow("Video File:", src_layout)
        else:
            self.location_type = "stream"
            self.edit_field = QtWidgets.QLineEdit(self.location.get("stream_url", ""))
            layout.addRow("Stream URL:", self.edit_field)

        # Bird’s-eye upload
        upload_btn = QtWidgets.QPushButton("Upload Bird’s-Eye Image")
        upload_btn.clicked.connect(self._upload_bird_image)
        self.bird_status = QtWidgets.QLabel(
            f"Selected: {self.satellite_image}" if self.satellite_image else "No image selected"
        )
        layout.addRow(upload_btn, self.bird_status)

        # Homography
        homo_btn = QtWidgets.QPushButton("Set Homography")
        homo_btn.clicked.connect(self.setHomography)
        self.homo_status = QtWidgets.QLabel(
            "Homography set." if self.homography_matrix else "Homography not set."
        )
        layout.addRow(homo_btn, self.homo_status)

        # Dialog buttons
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _browse_video_file(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.avi *.mkv *.mov *.flv);;All Files (*)"
        )
        if file_name:
            self.edit_field.setText(file_name)

    def _upload_bird_image(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Bird’s-Eye Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
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
        self.bird_status.setText(f"Selected: {rel_path}")

    def setHomography(self):
        if not self.satellite_image:
            QtWidgets.QMessageBox.critical(self, "Error", "Upload a bird’s-eye image first.")
            return
        if self.location.get("video_path"):
            frame = FrameExtractor.get_single_frame_file(self.location["video_path"])
        else:
            frame = FrameExtractor.get_single_frame(self.location["stream_url"])
        if frame is None:
            QtWidgets.QMessageBox.critical(self, "Error", "Cannot grab camera frame.")
            return
        dlg = HomographySetterDialog(frame, self.satellite_image, self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.homography_matrix = dlg.get_homography()
            self.homo_status.setText("Homography set.")
        else:
            self.homo_status.setText("Homography not set.")

    def get_updated_location(self):
        loc = self.location.copy()
        loc["name"] = self.name_edit.text().strip()
        if getattr(self, "location_type", "stream") == "video":
            loc["video_path"] = self.edit_field.text().strip()
            loc.pop("stream_url", None)
        else:
            loc["stream_url"] = self.edit_field.text().strip()
            loc.pop("video_path", None)
        if self.satellite_image:
            loc["birds_eye_image"] = self.satellite_image
        else:
            loc.pop("birds_eye_image", None)
        if self.homography_matrix is not None:
            loc["homography_matrix"] = (
                self.homography_matrix.tolist()
                if hasattr(self.homography_matrix, "tolist")
                else self.homography_matrix
            )
        return loc

    def changeSatelliteImage(self):
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
        self.selected_location["bird_image"] = save_path
        self.birdImagePreview.setPixmap(cropped)